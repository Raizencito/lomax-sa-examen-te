"""Crea la tabla DynamoDB lomax-productos en FLOCI/LocalStack (idempotente)."""
import os, sys
import boto3
from botocore.exceptions import ClientError

ENDPOINT = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
REGION = os.getenv("AWS_REGION", "us-east-1")
TABLE = os.getenv("DYNAMODB_TABLE", "lomax-productos")

def client():
    return boto3.client("dynamodb", endpoint_url=ENDPOINT, region_name=REGION,
                        aws_access_key_id="test", aws_secret_access_key="test")

def main():
    d = client()
    try:
        d.describe_table(TableName=TABLE)
        print(f"Tabla {TABLE} ya existe. OK (idempotente).")
        return 0
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
    d.create_table(
        TableName=TABLE,
        KeySchema=[{"AttributeName": "producto_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "producto_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    w = d.get_waiter("table_exists")
    w.wait(TableName=TABLE)
    print(f"Tabla {TABLE} creada.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
