"""Lomax SA - API FastAPI. Endpoints segun especificacion Etapa 4."""
import os, io, json, uuid
from datetime import datetime, timezone
from typing import Optional

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError
from fastapi import FastAPI, UploadFile, File, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
import psycopg2
import psycopg2.extras
from PIL import Image

# ---------------- config ----------------
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:admin123@localhost:7001/admin")
AWS_ENDPOINT = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
DDB_TABLE = os.getenv("DYNAMODB_TABLE", "lomax-productos")
S3_ORIG = os.getenv("S3_BUCKET_ORIGINALES", "lomax-originales")
S3_THUMB = os.getenv("S3_BUCKET_MINIATURAS", "lomax-miniaturas")
LAMBDA_FN = os.getenv("LAMBDA_FUNCTION", "lomax-thumbnail")
MAX_BYTES = 5 * 1024 * 1024
INSTANCE_ID = os.getenv("HOSTNAME", str(uuid.uuid4())[:8])

app = FastAPI(title="Lomax SA - Catalogo", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.exception_handler(RequestValidationError)
async def validation_400(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=400, content={"detail": "entrada invalida", "errores": exc.errors()})

def db():
    return psycopg2.connect(DATABASE_URL)

def s3c():
    return boto3.client("s3", endpoint_url=AWS_ENDPOINT, region_name=AWS_REGION,
                        aws_access_key_id="test", aws_secret_access_key="test")
def ddbc():
    return boto3.client("dynamodb", endpoint_url=AWS_ENDPOINT, region_name=AWS_REGION,
                        aws_access_key_id="test", aws_secret_access_key="test")
def lambdac():
    return boto3.client("lambda", endpoint_url=AWS_ENDPOINT, region_name=AWS_REGION,
                        aws_access_key_id="test", aws_secret_access_key="test")

def ensure_buckets():
    s = s3c()
    for b in (S3_ORIG, S3_THUMB):
        try:
            s.head_bucket(Bucket=b)
        except ClientError:
            try:
                s.create_bucket(Bucket=b)
            except ClientError:
                pass

class ProductoIn(BaseModel):
    codigo: str = Field(min_length=1, max_length=50)
    nombre: str = Field(min_length=1, max_length=200)
    descripcion: Optional[str] = ""
    precio: float = Field(ge=0)
    categoria_id: int
    atributos: dict = Field(min_length=1)

def _ddb_get(pid: str):
    try:
        r = ddbc().get_item(TableName=DDB_TABLE, Key={"producto_id": {"S": pid}})
        return r.get("Item")
    except (ClientError, EndpointConnectionError):
        return None

def _ddb_to_simple(item):
    if not item:
        return None
    out = {}
    for k, v in item.items():
        if "S" in v: out[k] = v["S"]
        elif "N" in v: out[k] = v["N"]
        elif "M" in v:
            out[k] = {kk: list(vv.values())[0] for kk, vv in v["M"].items()}
    return out

def invocar_lambda(pid: str, key_orig: str) -> dict:
    """Invoca Lambda sincrona en FLOCI; si no existe/falla, procesa localmente
    con la misma logica (Pillow) para no bloquear la practica. Retorna dict con estado."""
    payload = {"producto_id": pid, "bucket_original": S3_ORIG, "key_original": key_orig,
               "bucket_miniatura": S3_THUMB, "dynamodb_table": DDB_TABLE}
    # 1) intento Lambda real
    try:
        fn = lambdac()
        r = fn.invoke(FunctionName=LAMBDA_FN, InvocationType="RequestResponse",
                      Payload=json.dumps(payload).encode())
        data = r["Payload"].read()
        parsed = json.loads(data) if data else {}
        # FLOCI devuelve a veces {"statusCode":...} directo
        if isinstance(parsed, dict) and parsed.get("estado") in ("LISTA", "ERROR"):
            return {"via": "lambda", **parsed}
    except Exception as e:
        last_err = str(e)
    else:
        last_err = "lambda_sin_resultado"
    # 2) fallback local (misma logica que lambda_function.py)
    try:
        s = s3c()
        obj = s.get_object(Bucket=S3_ORIG, Key=key_orig)
        raw = obj["Body"].read()
        with Image.open(io.BytesIO(raw)) as im:
            im.verify()
        with Image.open(io.BytesIO(raw)) as im:
            im = im.convert("RGB")
            im.thumbnail((300, 300), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=85, optimize=True)
            dims = f"{im.size[0]}x{im.size[1]}"
            thumb = buf.getvalue()
        out_key = f"miniaturas/{pid}.jpg"
        s.put_object(Bucket=S3_THUMB, Key=out_key, Body=thumb, ContentType="image/jpeg")
        try:
            ddbc().update_item(TableName=DDB_TABLE, Key={"producto_id": {"S": pid}},
                UpdateExpression="SET miniatura_key=:m, estado_procesamiento=:e",
                ExpressionAttributeValues={":m": {"S": out_key}, ":e": {"S": "LISTA"}})
        except Exception:
            pass
        return {"via": "local-fallback", "statusCode": 200, "producto_id": pid,
                "miniatura_key": out_key, "dimensiones": dims, "estado": "LISTA",
                "nota": f"lambda no disponible ({last_err}); procesado local"}
    except Exception as e:
        try:
            ddbc().update_item(TableName=DDB_TABLE, Key={"producto_id": {"S": pid}},
                UpdateExpression="SET estado_procesamiento=:e",
                ExpressionAttributeValues={":e": {"S": "ERROR"}})
        except Exception:
            pass
        return {"via": "local-fallback", "statusCode": 500, "producto_id": pid,
                "estado": "ERROR", "error": str(e)}

def publicar_si_listo(pid: str) -> bool:
    item = _ddb_get(pid)
    s = _ddb_to_simple(item) if item else {}
    if not s or not s.get("atributos") or s.get("estado_procesamiento") != "LISTA" or not s.get("miniatura_key"):
        return False
    # verifica objeto en S3
    try:
        s3c().head_object(Bucket=S3_THUMB, Key=s["miniatura_key"])
    except ClientError:
        return False
    con = db(); cur = con.cursor()
    cur.execute("UPDATE productos SET estado='PUBLICADO' WHERE producto_id=%s", (int(pid),))
    con.commit(); cur.close(); con.close()
    return True

# ---------------- endpoints ----------------
@app.get("/health")
def health():
    try:
        con = db(); cur = con.cursor(); cur.execute("SELECT 1"); cur.close(); con.close()
        rds = "ok"
    except Exception as e:
        rds = f"error: {e}"
    return {"status": "OK", "instance": INSTANCE_ID, "rds": rds}

@app.get("/categorias")
def categorias():
    try:
        con = db(); cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT categoria_id, nombre, descripcion FROM categorias ORDER BY categoria_id")
        rows = cur.fetchall(); cur.close(); con.close()
        return {"total": len(rows), "categorias": rows, "instance": INSTANCE_ID}
    except Exception as e:
        raise HTTPException(503, {"paso": "rds", "error": str(e)})

@app.post("/productos", status_code=201)
def crear(p: ProductoIn):
    codigo = p.codigo.strip(); nombre = p.nombre.strip()
    if not codigo or not nombre: raise HTTPException(400, "codigo y nombre obligatorios")
    if not p.atributos: raise HTTPException(400, "atributos obligatorios")
    con = db(); cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("SELECT 1 FROM categorias WHERE categoria_id=%s", (p.categoria_id,))
        if not cur.fetchone():
            raise HTTPException(400, {"paso": "rds", "error": f"categoria {p.categoria_id} no existe"})
        try:
            cur.execute(
                "INSERT INTO productos (codigo,nombre,descripcion,precio,categoria_id,estado) VALUES (%s,%s,%s,%s,%s,'PENDIENTE') RETURNING producto_id, estado",
                (codigo, nombre, p.descripcion or "", float(p.precio), p.categoria_id))
            row = cur.fetchone(); con.commit()
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            raise HTTPException(409, f"codigo {codigo} duplicado")
        pid = str(row["producto_id"])
        try:
            ddbc().put_item(TableName=DDB_TABLE, Item={
                "producto_id": {"S": pid},
                "atributos": {"M": {k: {"S": str(v)} for k, v in p.atributos.items()}},
                "estado_procesamiento": {"S": "PENDIENTE"},
                "actualizado_en": {"S": datetime.now(timezone.utc).isoformat()}})
        except Exception as e:
            cur2 = con.cursor(); cur2.execute("DELETE FROM productos WHERE producto_id=%s", (int(pid),)); con.commit(); cur2.close()
            raise HTTPException(502, {"paso": "dynamodb", "error": str(e)})
        return {"producto_id": int(pid), "estado": "PENDIENTE", "instance": INSTANCE_ID}
    finally:
        cur.close(); con.close()

def _guardar_original(pid: str, up: UploadFile) -> str:
    ctype = (up.content_type or "").lower()
    raw = up.file.read()
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "archivo mayor a 5 MB")
    if ctype not in ("image/jpeg", "image/png", "image/jpg"):
        # intenta detectar por contenido
        try:
            with Image.open(io.BytesIO(raw)) as im:
                fmt = (im.format or "").upper()
                if fmt not in ("JPEG", "JPG", "PNG"):
                    raise ValueError(fmt)
        except HTTPException: raise
        except Exception:
            raise HTTPException(415, "formato no permitido (solo JPEG/PNG)")
    else:
        try:
            with Image.open(io.BytesIO(raw)) as im:
                im.verify()
        except Exception:
            raise HTTPException(400, {"paso": "validacion-imagen", "error": "imagen invalida o corrupta"})
    ext = ".jpg" if ctype in ("image/jpeg", "image/jpg") else ".png"
    if not ctype:
        ext = ".jpg"
    key = f"originales/{pid}{ext}"  # determinista por producto
    try:
        ensure_buckets()
        s3c().put_object(Bucket=S3_ORIG, Key=key, Body=raw,
                         ContentType="image/jpeg" if ext == ".jpg" else "image/png")
    except Exception as e:
        raise HTTPException(503, {"paso": "s3", "error": str(e)})
    try:
        ddbc().update_item(TableName=DDB_TABLE, Key={"producto_id": {"S": pid}},
            UpdateExpression="SET imagen_original_key=:k",
            ExpressionAttributeValues={":k": {"S": key}})
    except Exception as e:
        raise HTTPException(502, {"paso": "dynamodb", "error": str(e)})
    return key

@app.post("/productos/{pid}/imagen")
def subir_imagen(pid: int, imagen: UploadFile = File(...)):
    con = db(); cur = con.cursor()
    cur.execute("SELECT producto_id FROM productos WHERE producto_id=%s", (pid,))
    if not cur.fetchone():
        cur.close(); con.close(); raise HTTPException(404, "producto no existe")
    cur.close(); con.close()
    key = _guardar_original(str(pid), imagen)
    res = invocar_lambda(str(pid), key)
    if res.get("estado") != "LISTA":
        raise HTTPException(502, {"paso": "lambda", "error": res.get("error", "fallo procesamiento"), "detalle": res})
    if publicar_si_listo(str(pid)):
        return {"producto_id": pid, "estado": "PUBLICADO", "miniatura_key": res.get("miniatura_key"), "instance": INSTANCE_ID}
    raise HTTPException(502, {"paso": "publicacion", "error": "atributos o miniatura no disponibles", "detalle": res})

@app.post("/productos/{pid}/reprocesar")
def reprocesar(pid: int):
    con = db(); cur = con.cursor()
    cur.execute("SELECT producto_id FROM productos WHERE producto_id=%s", (pid,))
    if not cur.fetchone():
        cur.close(); con.close(); raise HTTPException(404, "producto no existe")
    cur.close(); con.close()
    item = _ddb_to_simple(_ddb_get(str(pid)))
    orig = (item or {}).get("imagen_original_key")
    if not orig:
        raise HTTPException(409, "no existe original para reprocesar")
    res = invocar_lambda(str(pid), orig)
    if res.get("estado") != "LISTA":
        raise HTTPException(502, {"paso": "lambda", "error": res.get("error"), "detalle": res})
    if publicar_si_listo(str(pid)):
        return {"producto_id": pid, "estado": "PUBLICADO", "miniatura_key": res.get("miniatura_key"), "instance": INSTANCE_ID}
    return {"producto_id": pid, "estado": "PENDIENTE", "detalle": res, "instance": INSTANCE_ID}

@app.get("/productos")
def listar():
    try:
        con = db(); cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""SELECT p.producto_id,p.codigo,p.nombre,p.descripcion,p.precio,p.categoria_id,
                       c.nombre AS categoria,p.fecha,p.estado FROM productos p
                       JOIN categorias c ON c.categoria_id=p.categoria_id
                       WHERE p.estado='PUBLICADO' ORDER BY p.producto_id""")
        rows = cur.fetchall(); cur.close(); con.close()
    except Exception as e:
        raise HTTPException(503, {"paso": "rds", "error": str(e)})
    out = []
    for r in rows:
        pid = str(r["producto_id"])
        s = _ddb_to_simple(_ddb_get(pid)) or {}
        out.append({**{k: (float(v) if k == "precio" else v) for k, v in dict(r).items()},
                    "atributos": s.get("atributos", {}), "miniatura_key": s.get("miniatura_key")})
    return {"total": len(out), "productos": out, "instance": INSTANCE_ID}

@app.get("/productos/{pid}")
def detalle(pid: int):
    con = db(); cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""SELECT p.producto_id,p.codigo,p.nombre,p.descripcion,p.precio,p.categoria_id,
                   c.nombre AS categoria,p.fecha,p.estado FROM productos p
                   JOIN categorias c ON c.categoria_id=p.categoria_id WHERE p.producto_id=%s""", (pid,))
    row = cur.fetchone(); cur.close(); con.close()
    if not row: raise HTTPException(404, "producto no existe")
    s = _ddb_to_simple(_ddb_get(str(pid))) or {}
    d = dict(row); d["precio"] = float(d["precio"])
    d.update({"atributos": s.get("atributos", {}), "imagen_original_key": s.get("imagen_original_key"),
              "miniatura_key": s.get("miniatura_key"), "estado_procesamiento": s.get("estado_procesamiento")})
    d["instance"] = INSTANCE_ID
    return d

@app.get("/productos/{pid}/imagen")
def imagen(pid: int):
    s = _ddb_to_simple(_ddb_get(str(pid))) or {}
    key = s.get("miniatura_key")
    if not key: raise HTTPException(404, "miniatura no disponible")
    try:
        o = s3c().get_object(Bucket=S3_THUMB, Key=key)
        return Response(content=o["Body"].read(), media_type=o.get("ContentType", "image/jpeg"))
    except ClientError:
        raise HTTPException(404, "miniatura no disponible")
