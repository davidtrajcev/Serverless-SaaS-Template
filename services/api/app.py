import json
import os
import time
import uuid
import boto3

ddb = boto3.client("dynamodb")
TABLE = os.environ["TABLE_NAME"]
sqs = boto3.client("sqs")
QUEUE_URL = os.environ["QUEUE_URL"]

def _resp(code, body):
    return {
        "statusCode": code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }

def _tenant_id(event):
    # Comes from API Gateway JWT authorizer (Cognito)
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )
    # For now we use Cognito user's sub as the tenant/user scope
    return claims.get("sub", "unknown")

def handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    path   = event.get("rawPath", "")

    tenant = _tenant_id(event)

    if path == "/items" and method == "POST":
        body = json.loads(event.get("body") or "{}")
        text = body.get("text", "").strip()
        if not text:
            return _resp(400, {"error": "text is required"})

        item_id = str(uuid.uuid4())
        now = int(time.time())

        ddb.put_item(
            TableName=TABLE,
            Item={
                "PK": {"S": f"TENANT#{tenant}"},
                "SK": {"S": f"ITEM#{item_id}"},
                "item_id": {"S": item_id},
                "created_at": {"N": str(now)},
                "text": {"S": text},
                "status": {"S": "PENDING"},
            },
        )

        sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps({"tenant_id": tenant, "item_id": item_id}),
        )

        return _resp(201, {"item_id": item_id, "status": "PENDING"})

    if path == "/items" and method == "GET":
        resp = ddb.query(
            TableName=TABLE,
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
            ExpressionAttributeValues={
                ":pk": {"S": f"TENANT#{tenant}"},
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

    return _resp(404, {"error": "not_found"})