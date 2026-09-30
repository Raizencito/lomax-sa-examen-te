"""Repara DynamoDB+S3 desde RDS (tras wipe de FLOCI).
Reconstruye atributos deterministicos (mismo patron de seed_20_productos.py),
regenera imagenes, marca LISTA/PUBLICADO. Idempotente: omite lo ya consistente.
Uso (dentro de contenedor bridge o host):
  DATABASE_URL=... AWS_ENDPOINT_URL=... DYNAMODB_TABLE=... python scripts/repair.py
"""
import os, io
import boto3, psycopg2, psycopg2.extras
from PIL import Image, ImageDraw

DB = os.getenv("DATABASE_URL")
EP = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
REGION = os.getenv("AWS_REGION", "us-east-1")
TABLE = os.getenv("DYNAMODB_TABLE", "lomax-productos")
B_ORIG = os.getenv("S3_BUCKET_ORIGINALES", "lomax-originales")
B_THUMB = os.getenv("S3_BUCKET_MINIATURAS", "lomax-miniaturas")

def attrs_for(codigo, cat):
    if codigo == "EKS-001":
        return {"conexion": "USB-C", "distribucion": "ES", "retroiluminado": "RGB"}
    if codigo == "E4-TEST-UNICO":
        return {"conexion": "USB", "distribucion": "ES", "retroiluminado": "No"}
    try:
        i = int(codigo.split("-")[1])
    except Exception:
        i = 1
    if cat == 1:
        return {"conexion": "USB-C" if i % 2 else "2.4GHz",
                "distribucion": "ES" if i % 2 else "US",
                "retroiluminado": "RGB" if i % 2 else "No"}
    if cat == 2:
        return {"pulgadas": str(24 + i), "resolucion": "2560x1440", "tasa_refresco": "165Hz"}
    return {"tipo": "Over-ear", "conexion": "Bluetooth",
            "cancelacion_ruido": "Si" if i % 2 else "No"}

def img_bytes(code, idx):
    im = Image.new("RGB", (1200, 800), (40 + idx * 8 % 180, 90, 180))
    d = ImageDraw.Draw(im); d.text((500, 390), code, fill=(255, 255, 255))
    b = io.BytesIO(); im.save(b, "JPEG", quality=85); return b.getvalue()

def thumb(raw):
    with Image.open(io.BytesIO(raw)) as im:
        im = im.convert("RGB"); im.thumbnail((300, 300), Image.LANCZOS)
        b = io.BytesIO(); im.save(b, "JPEG", quality=85, optimize=True)
        return b.getvalue(), f"{im.size[0]}x{im.size[1]}"

def main():
    s3 = boto3.client("s3", endpoint_url=EP, region_name=REGION,
                      aws_access_key_id="test", aws_secret_access_key="test")
    ddb = boto3.client("dynamodb", endpoint_url=EP, region_name=REGION,
                       aws_access_key_id="test", aws_secret_access_key="test")
    for b in (B_ORIG, B_THUMB):
        try: s3.head_bucket(Bucket=b)
        except Exception:
            try: s3.create_bucket(Bucket=b)
            except Exception as e: print("bucket", b, e)
    try:
        ddb.describe_table(TableName=TABLE)
    except Exception:
        ddb.create_table(TableName=TABLE,
            KeySchema=[{"AttributeName": "producto_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "producto_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST")
        ddb.get_waiter("table_exists").wait(TableName=TABLE)
    con = psycopg2.connect(DB); cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT producto_id,codigo,categoria_id,estado FROM productos ORDER BY producto_id")
    rows = cur.fetchall()
    ok = skip = 0
    for n, r in enumerate(rows, 1):
        pid = str(r["producto_id"]); code = r["codigo"]
        try:
            s3.head_object(Bucket=B_THUMB, Key=f"miniaturas/{pid}.jpg")
            it = ddb.get_item(TableName=TABLE, Key={"producto_id": {"S": pid}}).get("Item", {})
            if it.get("estado_procesamiento", {}).get("S") == "LISTA" and it.get("atributos", {}).get("M"):
                skip += 1; continue
        except Exception:
            pass
        raw = img_bytes(code, n)
        s3.put_object(Bucket=B_ORIG, Key=f"originales/{pid}.jpg", Body=raw, ContentType="image/jpeg")
        th, _ = thumb(raw)
        s3.put_object(Bucket=B_THUMB, Key=f"miniaturas/{pid}.jpg", Body=th, ContentType="image/jpeg")
        at = attrs_for(code, r["categoria_id"])
        ddb.put_item(TableName=TABLE, Item={
            "producto_id": {"S": pid},
            "atributos": {"M": {k: {"S": v} for k, v in at.items()}},
            "imagen_original_key": {"S": f"originales/{pid}.jpg"},
            "miniatura_key": {"S": f"miniaturas/{pid}.jpg"},
            "estado_procesamiento": {"S": "LISTA"}})
        cur.execute("UPDATE productos SET estado='PUBLICADO' WHERE producto_id=%s", (r["producto_id"],))
        con.commit(); ok += 1
    print(f"reparados: {ok}, ya consistentes: {skip}, total RDS: {len(rows)}")
    cur.close(); con.close()

if __name__ == "__main__":
    main()
