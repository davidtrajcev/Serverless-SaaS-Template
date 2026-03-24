import json
import os
import time
import uuid
import boto3

ddb = boto3.client("dynamodb")
TABLE = os.environ["TABLE_NAME"]
sqs = boto3.client("sqs")
QUEUE_URL = os.environ["QUEUE_URL"]
cognito = boto3.client("cognito-idp")
USER_POOL_ID = os.environ["USER_POOL_ID"]

ssm = boto3.client("ssm")

ADMIN_EMAIL_PARAM = os.environ["ADMIN_EMAIL_PARAM"]
_cached_admin_email = None

def get_admin_email():
    global _cached_admin_email
    if _cached_admin_email:
        return _cached_admin_email
    resp = ssm.get_parameter(Name=ADMIN_EMAIL_PARAM, WithDecryption=True)
    _cached_admin_email = resp["Parameter"]["Value"].lower().strip()
    return _cached_admin_email

def log(level, message, **fields):
    payload = {
        "ts": int(time.time()),
        "level": level,
        "message": message,
        **fields,
    }
    print(json.dumps(payload, separators=(",", ":")))

def _json_body(event):
    try:
        return json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return None

def _resp(code, body):
    return {
        "statusCode": code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }

def _user_sub(event):
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )
    return claims.get("sub", "unknown")

def _ddb_put_pending_user(sub: str, email: str):
    """Idempotently mark user as pending approval."""
    now = int(time.time())
    item = {
        "PK": {"S": f"USER#{sub}"},
        "SK": {"S": "STATUS"},
        "status": {"S": "PENDING"},
        "email": {"S": (email or "").lower()},
        "created_at": {"N": str(now)},
    }
    # only create if not exists
    ddb.put_item(
        TableName=TABLE,
        Item=item,
        ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)"
    )

def _user_status_record(sub: str):
    resp = ddb.get_item(
        TableName=TABLE,
        Key={"PK": {"S": f"USER#{sub}"}, "SK": {"S": "STATUS"}},
    )
    return resp.get("Item")

def _list_user_tenants(sub: str):
    """
    Returns list of {tenant_id, role}.
    Supports:
      - new model: USER#sub / TENANT#<id>
      - legacy:    USER#sub / TENANT
    """
    tenants = []

    resp = ddb.query(
        TableName=TABLE,
        KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
        ExpressionAttributeValues={
            ":pk": {"S": f"USER#{sub}"},
            ":sk": {"S": "TENANT#"},
        },
    )
    for it in resp.get("Items", []):
        tenant_id = it["SK"]["S"].split("#", 1)[1]
        role = it.get("role", {"S": "member"})["S"]
        tenants.append({"tenant_id": tenant_id, "role": role})

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

def _claims(event):
    return (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )

def _user_email(event):
    return (_claims(event).get("email") or "").lower()

def _is_admin(event):
    return _user_email(event) == get_admin_email()

def _tenant_from_header(event) -> str:
    headers = event.get("headers") or {}
    # API Gateway may normalize headers differently
    return (
        headers.get("x-tenant-id")
        or headers.get("X-Tenant-Id")
        or headers.get("X-TENANT-ID")
        or ""
    ).strip()

def _list_user_tenants(sub: str):
    """
    Returns list of {tenant_id, role} for the user.
    Backwards-compatible:
      - new model: USER#sub / TENANT#<id>
      - legacy:    USER#sub / TENANT
    """
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
        sk = it["SK"]["S"]              # TENANT#<id>
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
    """
    True if user has membership in tenant_id.
    Backwards-compatible with legacy USER#sub / TENANT.
    """
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

def _get_membership(sub):
    resp = ddb.get_item(
        TableName=TABLE,
        Key={"PK": {"S": f"USER#{sub}"}, "SK": {"S": "TENANT"}},
    )
    item = resp.get("Item")
    if not item:
        return None
    return {
        "tenant_id": item["tenant_id"]["S"],
        "role": item.get("role", {"S": "member"})["S"],
    }

def _find_sub_by_email(email: str):
    # Cognito filter requires quotes around the value
    resp = cognito.list_users(
        UserPoolId=USER_POOL_ID,
        Filter=f'email = "{email}"',
        Limit=1
    )
    users = resp.get("Users", [])
    if not users:
        return None

    attrs = {a["Name"]: a["Value"] for a in users[0].get("Attributes", [])}
    return attrs.get("sub")

def _audit(tenant_id: str, action: str, actor_sub: str, request_id: str, **details):
    now = int(time.time())
    audit_id = f"{now}-{uuid.uuid4()}"
    item = {
        "PK": {"S": f"TENANT#{tenant_id}"},
        "SK": {"S": f"AUDIT#{audit_id}"},
        "action": {"S": action},
        "actor_sub": {"S": actor_sub},
        "request_id": {"S": request_id},
        "created_at": {"N": str(now)},
    }

    # Store optional details (as strings)
    for k, v in details.items():
        if v is None:
            continue
        item[k] = {"S": str(v)}

    ddb.put_item(TableName=TABLE, Item=item)

def handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    path   = event.get("rawPath", "")

    request_id = (
        event.get("requestContext", {}).get("requestId")
        or event.get("requestContext", {}).get("request_id")
        or context.aws_request_id
    )

    sub = _user_sub(event)
    membership = _get_membership(sub)
    tenant_id = membership["tenant_id"] if membership else None

    if path == "/me" and method == "GET":
        email = _user_email(event)
        if _is_admin(event):
            return _resp(200, {"status": "ADMIN", "email": email, "tenants": []})
        
        tenants = _list_user_tenants(sub)
        if tenants:
            return _resp(200, {"status": "MEMBER", "email": email, "tenants": tenants})

        # New user — auto-create tenant immediately
        new_tenant_id = str(uuid.uuid4())
        now = int(time.time())

        ddb.put_item(TableName=TABLE, Item={
            "PK": {"S": f"TENANT#{new_tenant_id}"},
            "SK": {"S": "META"},
            "tenant_id": {"S": new_tenant_id},
            "name": {"S": "My Workspace"},
            "owner_sub": {"S": sub},
            "created_at": {"N": str(now)},
        })

        ddb.put_item(TableName=TABLE, Item={
            "PK": {"S": f"USER#{sub}"},
            "SK": {"S": "TENANT"},
            "tenant_id": {"S": new_tenant_id},
            "role": {"S": "member"},
            "created_at": {"N": str(now)},
        })

        log("INFO", "tenant_auto_created", user_sub=sub, tenant_id=new_tenant_id)

        return _resp(200, {
            "status": "MEMBER",
            "email": email,
            "tenants": [{"tenant_id": new_tenant_id, "role": "member"}]
        })

    # ---- TENANT INIT ----
    if path == "/tenant/init" and method == "POST":
        if membership:
            log("INFO", "tenant_init_existing", request_id=request_id, tenant_id=tenant_id, role=membership.get("role"))
            return _resp(200, {"tenant_id": tenant_id, "role": membership["role"]})

        body = _json_body(event)
        if body is None:
            return _resp(400, {"error": "invalid_json"})

        tenant_name = (body.get("name") or "My Tenant").strip()
        new_tenant_id = str(uuid.uuid4())
        now = int(time.time())

        role = "admin" if _is_admin(event) else "member"

        # Tenant record
        ddb.put_item(
            TableName=TABLE,
            Item={
                "PK": {"S": f"TENANT#{new_tenant_id}"},
                "SK": {"S": "META"},
                "tenant_id": {"S": new_tenant_id},
                "name": {"S": tenant_name},
                "owner_sub": {"S": sub},
                "created_at": {"N": str(now)},
            },
            ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)"
        )

        # Membership record (user -> tenant)
        ddb.put_item(
            TableName=TABLE,
            Item={
                "PK": {"S": f"USER#{sub}"},
                "SK": {"S": "TENANT"},
                "tenant_id": {"S": new_tenant_id},
                "role": {"S": role},
                "created_at": {"N": str(now)},
            },
            ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)"
        )

        log("INFO", "tenant_initialized", request_id=request_id, tenant_id=new_tenant_id, user_sub=sub, role=role)
        return _resp(201, {"tenant_id": new_tenant_id, "role": role, "name": tenant_name})

    # ---- TENANT INVITE (admin-only) ----
    if path == "/tenant/invite" and method == "POST":
        if not membership:
            log("WARN", "invite_no_tenant", request_id=request_id, user_sub=sub, path=path)
            return _resp(403, {"error": "no_tenant", "hint": "Call POST /tenant/init first."})

        if not _is_admin(event):
            _audit(membership["tenant_id"], "invite_forbidden", sub, request_id, path=path)
            return _resp(403, {"error": "forbidden", "hint": "Admin only"})

        body = _json_body(event) 
        if body is None: 
            return _resp(400, {"error": "invalid_json"})
        email = (body.get("email") or "").strip().lower()
        role = (body.get("role") or "member").strip().lower()

        # Generic response for caller (prevents enumeration)
        generic_ok = {"ok": True}

        if not email:
            _audit(membership["tenant_id"], "invite_invalid", sub, request_id, reason="missing_email")
            return _resp(200, generic_ok)

        if role not in ("admin", "member"):
            _audit(membership["tenant_id"], "invite_invalid", sub, request_id, email=email, reason="invalid_role", role=role)
            return _resp(200, generic_ok)

        tenant_id = membership["tenant_id"]

        invited_sub = _find_sub_by_email(email)

        # If user doesn't exist: log internally, but don't reveal it
        if not invited_sub:
            _audit(tenant_id, "invite_target_not_found", sub, request_id, email=email, role=role)
            log("WARN", "invite_target_not_found", request_id=request_id, tenant_id=tenant_id, email=email)
            return _resp(200, generic_ok)

        now = int(time.time())

        try:
            ddb.put_item(
                TableName=TABLE,
                Item={
                    "PK": {"S": f"USER#{invited_sub}"},
                    "SK": {"S": "TENANT"},
                    "tenant_id": {"S": tenant_id},
                    "role": {"S": role},
                    "invited_by": {"S": sub},
                    "created_at": {"N": str(now)},
                },
                ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)"
            )

            _audit(tenant_id, "invite_success", sub, request_id, email=email, invited_sub=invited_sub, role=role)
            log("INFO", "invite_success", request_id=request_id, tenant_id=tenant_id, email=email, invited_sub=invited_sub, role=role)
            return _resp(200, generic_ok)

        except ddb.exceptions.ConditionalCheckFailedException:
            # User already has a tenant mapping - don't leak details
            _audit(tenant_id, "invite_already_mapped", sub, request_id, email=email, invited_sub=invited_sub, role=role)
            log("WARN", "invite_already_mapped", request_id=request_id, tenant_id=tenant_id, email=email, invited_sub=invited_sub)
            return _resp(200, generic_ok)

    # ---- Tenant enforcement for /items ----
    if path.startswith("/items"):
        requested_tenant = _tenant_from_header(event)

        if not requested_tenant:
            return _resp(400, {"error": "missing_tenant", "hint": "Send X-Tenant-Id header"})

        if _is_admin(event):
            tenant_id = requested_tenant  # admin can access any tenant
        else:
            if not _has_tenant(sub, requested_tenant):
                return _resp(403, {"error": "forbidden_tenant"})
            tenant_id = requested_tenant

    # POST /items
    if path == "/items" and method == "POST":
        body = _json_body(event) 
        if body is None: 
            return _resp(400, {"error": "invalid_json"})
        text = body.get("text", "").strip()
        if not text:
            return _resp(400, {"error": "text is required"})

        item_id = str(uuid.uuid4())
        now = int(time.time())

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

        sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps({"tenant_id": tenant_id, "item_id": item_id}),
        )

        log("INFO", "item_created", request_id=request_id, tenant_id=tenant_id, item_id=item_id)
        return _resp(201, {"item_id": item_id, "status": "PENDING"})

    # GET /items
    if path == "/items" and method == "GET":
        resp = ddb.query(
            TableName=TABLE,
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
            ExpressionAttributeValues={
                ":pk": {"S": f"TENANT#{tenant_id}"},
                ":sk": {"S": "ITEM#"},
            },
            ScanIndexForward=False,
        )
        items = [{
            "item_id": it["item_id"]["S"],
            "created_at": int(it["created_at"]["N"]),
            "text": it["text"]["S"],
            "status": it.get("status", {"S": "UNKNOWN"})["S"],
        } for it in resp.get("Items", [])]

        log("INFO", "items_listed", request_id=request_id, tenant_id=tenant_id, count=len(items))
        return _resp(200, {"items": items})

    log("INFO", "not_found", request_id=request_id, method=method, path=path)
    return _resp(404, {"error": "not_found"})