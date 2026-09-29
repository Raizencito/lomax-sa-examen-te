"""Verifica correspondencia RDS<->DynamoDB y limpia huerfanos de Dynamo.
Uso: python scripts/check_ids.py [BASE_API] [TABLA] [--clean]"""
import boto3, requests, sys, os

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
TABLE = sys.argv[2] if len(sys.argv) > 2 else os.getenv("DYNAMODB_TABLE", "lomax-productos")
CLEAN = "--clean" in sys.argv

d = boto3.client("dynamodb", endpoint_url="http://localhost:4566", region_name="us-east-1",
                 aws_access_key_id="test", aws_secret_access_key="test")
dyn_ids = sorted(int(i["producto_id"]["S"]) for i in d.scan(TableName=TABLE)["Items"])
api_ids = sorted(p["producto_id"] for p in requests.get(f"{BASE}/productos").json()["productos"])
print(f"tabla: {TABLE} dynamo: {len(dyn_ids)} {dyn_ids}")
print(f"api {BASE} rds: {len(api_ids)} {api_ids}")
orphans = [i for i in dyn_ids if i not in api_ids]
print("huerfanos:", orphans)
if CLEAN:
    for pid in orphans:
        d.delete_item(TableName=TABLE, Key={"producto_id": {"S": str(pid)}})
    print("limpieza lista")
