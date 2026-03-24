import json
import os
import time
import boto3

ddb = boto3.client("dynamodb")
TABLE = os.environ["TABLE_NAME"]

def log(level, message, **fields):
    payload = {
        "ts": int(time.time()),
        "level": level,
        "message": message,
        **fields,
    }
    print(json.dumps(payload, separators=(",", ":")))

def handler(event, context):
    for rec in event.get("Records", []):
        request_id = context.aws_request_id

        msg = json.loads(rec["body"])
        tenant_id = msg["tenant_id"]
        item_id = msg["item_id"]

        log(
            "INFO",
            "job_received",
            request_id=request_id,
            tenant_id=tenant_id,
            item_id=item_id,
        )

        ddb.update_item(
            TableName=TABLE,
            Key={
                "PK": {"S": f"TENANT#{tenant_id}"},
                "SK": {"S": f"ITEM#{item_id}"},
            },
            UpdateExpression="SET #s = :done",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":done": {"S": "DONE"},
            },
        )

        log(
            "INFO",
            "job_completed",
            request_id=request_id,
            tenant_id=tenant_id,
            item_id=item_id,
        )