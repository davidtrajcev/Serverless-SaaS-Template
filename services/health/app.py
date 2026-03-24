import json
import os
import time
import uuid
import boto3

ddb = boto3.client("dynamodb")
TABLE = os.environ["TABLE_NAME"]

# Optional (if you have SQS)
sqs = boto3.client("sqs")
QUEUE_URL = os.environ.get("QUEUE_URL")

# Optional: admin email (SSM SecureString)
ssm = boto3.client("ssm")
ADMIN_EMAIL_PARAM = os.environ.get("ADMIN_EMAIL_PARAM", "")
_cached_admin_email = None


# ---------------- helpers ----------------

def _resp(code, body, origin="*"):
    return {
        "statusCode": code,
        "headers": {
            "content-type": "application/json",
            "access-control-allow-origin": origin,
            "access-control-allow-headers": "authorization,content-type,x-tenant-id",
            "access-control-allow-methods": "GET,POST,OPTIONS",
        },
        "body": json.dumps(body),
    }


def _json_body(event):
    try:
        return json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return None


def _claims(event):
    return (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )


def _user_sub(event):
    return _claims(event).get("sub", "unknown")


def _user_email(event):
    return (_claims(event).get("email") or "").lower().strip()


def _get_admin_email():
    global _cached_admin_email
    if not ADMIN_EMAIL_PARAM:
        return ""
    if _cached_admin_email:
        return _cached_admin_email
    resp = ssm.get_parameter(Name=ADMIN_EMAIL_PARAM, WithDecryption=True)
    _cached_admin_email = (resp["Parameter"]["Value"] or "").lower().strip()
    return _cached_admin_email


def _is_admin(event):
    admin_email = _get_admin_email()
    return bool(admin_email) and _user_email(event) == admin_email


def _tenant_from_header(event) -> str:
    headers = event.get("headers") or {}
    return (
        headers.get("x-tenant-id")
        or headers.get("X-Tenant-Id")
        or headers.get("X-TENANT-ID")
        or ""
    ).strip()


def _list_user_tenants(sub: str):
    tenants = []

    # New model: many tenant memberships
    resp = ddb.query(
        TableName=TABLE,
        KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
        ExpressionAttributeValues={
            ":pk": {"S": f"USER#{sub}"},
            ":sk": {"S": "TENANT#"},
        },
    )
    for it in resp.get("Items", []):
        sk = it["SK"]["S"]  # TENANT#<id>
        tenant_id = sk.split("#", 1)[1]
        role = it.get("role", {"S": "member"})["S"]
        tenants.append({"tenant_id": tenant_id, "role": role})

    # Legacy fallback: single mapping
    if not tenants:
        legacy = ddb.get_item(
            TableName=TABLE,
            Key={"PK": {"S": f"USER#{sub}"}, "SK": {"S": "TENANT"}},
        ).get("Item")
        if legacy:
            tenants.append({
                "tenant_id": legacy["tenant_id"]["S"],
                "role": legacy.get("role", {"S": "member"})["S"],
            })

    return tenants


def _has_tenant(sub: str, tenant_id: str) -> bool:
    # New model
    resp = ddb.get_item(
        TableName=TABLE,
        Key={"PK": {"S": f"USER#{sub}"}, "SK": {"S": f"TENANT#{tenant_id}"}},
    )
    if resp.get("Item"):
        return True

    # Legacy model
    legacy = ddb.get_item(
        TableName=TABLE,
        Key={"PK": {"S": f"USER#{sub}"}, "SK": {"S": "TENANT"}},
    ).get("Item")

    return bool(legacy and legacy.get("tenant_id", {}).get("S") == tenant_id)


def _ensure_tenant_for_user(event):
    """
    Idempotent:
      - if user already has a tenant mapping -> return it
      - else create tenant + legacy membership record
    """
    sub = _user_sub(event)
    existing = _list_user_tenants(sub)
    if existing:
        return existing[0]["tenant_id"], existing[0]["role"]

    tenant_id = str(uuid.uuid4())
    now = int(time.time())
    role = "admin" if _is_admin(event) else "member"

    # Tenant meta
    ddb.put_item(
        TableName=TABLE,
        Item={
            "PK": {"S": f"TENANT#{tenant_id}"},
            "SK": {"S": "META"},
            "tenant_id": {"S": tenant_id},
            "name": {"S": "My Tenant"},
            "owner_sub": {"S": sub},
            "created_at": {"N": str(now)},
        },
        ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)",
    )

    # Legacy membership (single tenant)
    ddb.put_item(
        TableName=TABLE,
        Item={
            "PK": {"S": f"USER#{sub}"},
            "SK": {"S": "TENANT"},
            "tenant_id": {"S": tenant_id},
            "role": {"S": role},
            "created_at": {"N": str(now)},
        },
        ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)",
    )

    return tenant_id, role


# ---------------- handler ----------------

def handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    path = event.get("rawPath", "")

    # Preflight
    if method == "OPTIONS":
        return _resp(200, {"ok": True})

    # Must be authenticated for everything below (JWT authorizer)
    sub = _user_sub(event)

    # GET /me (no tenant header required)
    if path == "/me" and method == "GET":
        if _is_admin(event):
            return _resp(200, {"status": "ADMIN", "tenants": []})
        tenants = _list_user_tenants(sub)
        if not tenants:
            return _resp(200, {"status": "PENDING", "tenants": []})
        return _resp(200, {"status": "MEMBER", "tenants": tenants})

    # POST /tenant/init (idempotent)
    if path == "/tenant/init" and method == "POST":
        body = _json_body(event)
        if body is None:
            return _resp(400, {"error": "invalid_json"})
        # you can store name if you want; keeping simple here
        tenant_id, role = _ensure_tenant_for_user(event)
        return _resp(200, {"tenant_id": tenant_id, "role": role, "name": body.get("name") or "My Tenant"})

    # Tenant enforcement for /items
    if path.startswith("/items"):
        tenant_id = _tenant_from_header(event)
        if not tenant_id:
            return _resp(400, {"error": "missing_tenant", "hint": "Send X-Tenant-Id header"})

        if not _is_admin(event):
            if not _has_tenant(sub, tenant_id):
                return _resp(403, {"error": "forbidden_tenant"})

    # POST /items
    if path == "/items" and method == "POST":
        body = _json_body(event)
        if body is None:
            return _resp(400, {"error": "invalid_json"})

        text = (body.get("text") or "").strip()
        if not text:
            return _resp(400, {"error": "text is required"})

        item_id = str(uuid.uuid4())
        now = int(time.time())
        tenant_id = _tenant_from_header(event)

        ddb.put_item(
            TableName=TABLE,
            Item={
                "PK": {"S": f"TENANT#{tenant_id}"},
                "SK": {"S": f"ITEM#{item_id}"},
                "item_id": {"S": item_id},
                "created_at": {"N": str(now)},
                "text": {"S": text},
                "status": {"S": "PENDING"},
                "owner_sub": {"S": sub},
            },
        )

        # Optional async (if you have the worker)
        if QUEUE_URL:
            sqs.send_message(
                QueueUrl=QUEUE_URL,
                MessageBody=json.dumps({"tenant_id": tenant_id, "item_id": item_id}),
            )

        return _resp(201, {"item_id": item_id, "status": "PENDING"})

    # GET /items
    if path == "/items" and method == "GET":
        tenant_id = _tenant_from_header(event)

        resp = ddb.query(
            TableName=TABLE,
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
            ExpressionAttributeValues={
                ":pk": {"S": f"TENANT#{tenant_id}"},
                ":sk": {"S": "ITEM#"},
            },
            ScanIndexForward=False,
        )

        items = []
        for it in resp.get("Items", []):
            items.append({
                "item_id": it["item_id"]["S"],
                "created_at": int(it["created_at"]["N"]),
                "text": it["text"]["S"],
                "status": it.get("status", {"S": "UNKNOWN"})["S"],
            })

        return _resp(200, {"items": items})

    return _resp(404, {"error": "not_found", "path": path, "method": method})