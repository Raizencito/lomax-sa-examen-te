# Lambda miniaturas Lomax SA
# Recibe (JSON): {"producto_id": "1", "bucket_original": "...", "key_original": "originales/1.jpg",
#                 "bucket_miniatura": "...", "dynamodb_table": "lomax-productos"}
# Produce miniatura proporcional max 300x300, clave determinista: miniaturas/{producto_id}.jpg
# Actualiza DynamoDB: miniatura_key + estado_procesamiento LISTA|ERROR
import os, io, json
import boto3
from PIL import Image

ENDPOINT = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
REGION = os.getenv("AWS_REGION", "us-east-1")

def _res():
    kw = dict(endpoint_url=ENDPOINT, region_name=REGION,
              aws_access_key_id="test", aws_secret_access_key="test")
    return boto3.client("s3", **kw), boto3.client("dynamodb", **kw)

def _thumb(data: bytes, max_size=(300, 300)) -> tuple[bytes, str]:
    with Image.open(io.BytesIO(data)) as im:
        im.verify()
    with Image.open(io.BytesIO(data)) as im:
        fmt = (im.format or "JPEG").upper()
        if fmt not in ("JPEG", "JPG", "PNG"):
            raise ValueError(f"Formato no permitido: {fmt}")
        im = im.convert("RGB")
        im.thumbnail(max_size, Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=85, optimize=True)
        return buf.getvalue(), f"{im.size[0]}x{im.size[1]}"

def lambda_handler(event, context=None):
    if isinstance(event, str):
        event = json.loads(event)
    pid = str(event["producto_id"])
    b_orig = event["bucket_original"]
    k_orig = event["key_original"]
    b_thumb = event.get("bucket_miniatura", event.get("bucket_thumb", b_orig))
    table = event.get("dynamodb_table", os.getenv("DYNAMODB_TABLE", "lomax-productos"))
    s3, ddb = _res()
    out_key = f"miniaturas/{pid}.jpg"  # determinista: repetir no crea extras
    try:
        obj = s3.get_object(Bucket=b_orig, Key=k_orig)
        data = obj["Body"].read()
        if len(data) > 5 * 1024 * 1024:
            raise ValueError("Archivo mayor a 5 MB")
        thumb, dims = _thumb(data)
        s3.put_object(Bucket=b_thumb, Key=out_key, Body=thumb, ContentType="image/jpeg")
        ddb.update_item(
            TableName=table, Key={"producto_id": {"S": pid}},
            UpdateExpression="SET miniatura_key=:m, estado_procesamiento=:e",
            ExpressionAttributeValues={":m": {"S": out_key}, ":e": {"S": "LISTA"}},
        )
        return {"statusCode": 200, "producto_id": pid, "miniatura_key": out_key,
                "dimensiones": dims, "estado": "LISTA"}
    except Exception as e:
        try:
            ddb.update_item(
                TableName=table, Key={"producto_id": {"S": pid}},
                UpdateExpression="SET estado_procesamiento=:e",
                ExpressionAttributeValues={":e": {"S": "ERROR"}},
            )
        except Exception:
            pass
        return {"statusCode": 500, "producto_id": pid, "estado": "ERROR", "error": str(e)}
