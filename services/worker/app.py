import json
import os
import time
import boto3

ddb = boto3.client("dynamodb")
TABLE = os.environ["TABLE_NAME"]

def handler(event, context):
    # event["Records"] contains SQS messages
    for rec in event.get("Records", []):
        msg = json.loads(rec["body"])

        tenant = msg["tenant_id"]
        item_id = msg["item_id"]

        # Simulate some background work
        time.sleep(0.2)

        ddb.update_item(
            TableName=TABLE,
            Key={
                "PK": {"S": f"TENANT#{tenant}"},
                "SK": {"S": f"ITEM#{item_id}"},
            },
            UpdateExpression="SET #s = :done",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":done": {"S": "DONE"}},
        )