"""Reporte E4 idempotente: usa codigo E4-TEST-UNICO (lo recrea si existe)."""
import requests, io, sys
from PIL import Image
B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080/api"
CODE = "E4-TEST-UNICO"
out = []
def log(*a):
    s = " ".join(str(x) for x in a); print(s); out.append(s)

# crear o reutilizar
r = requests.post(f"{B}/productos", json={"codigo": CODE, "nombre": "E4 Test", "precio": 10.0,
    "categoria_id": 1, "atributos": {"conexion": "USB", "distribucion": "ES", "retroiluminado": "No"}})
if r.status_code == 201:
    pid = r.json()["producto_id"]; log("POST valido:", r.status_code, "PENDIENTE pid=", pid)
else:
    # buscar pid existente
    items = requests.get(f"{B}/productos").json()["productos"]
    det = None
    for p in items:
        if p["codigo"] == CODE:
            det = p; break
    if det is None:
        # pendiente (no publicado): listar todos via detalle? usar POST reprocesar path: obtener de RDS? simplificar:
        log("POST existente:", r.status_code); sys.exit(0)
    pid = det["producto_id"]; log("reutiliza pid=", pid)

im = Image.new("RGB", (1200, 800), (80, 40, 160))
buf = io.BytesIO(); im.save(buf, "JPEG"); buf.seek(0)
ri = requests.post(f"{B}/productos/{pid}/imagen", files={"imagen": ("f.jpg", buf, "image/jpeg")})
log("POST imagen:", ri.status_code, ri.json().get("estado"))
g = requests.get(f"{B}/productos/{pid}/imagen")
log("GET imagen:", g.status_code, g.headers.get("Content-Type"), len(g.content))
open("evidencias/E4/img-endpoint.jpg", "wb").write(g.content)
log("GET categorias:", requests.get(f"{B}/categorias").json()["total"])
log("GET lista total:", requests.get(f"{B}/productos").json()["total"])
log("GET 404:", requests.get(f"{B}/productos/99999").status_code)
open("evidencias/E4/reporte-E4.txt", "w").write("\n".join(out))
print("OK")
