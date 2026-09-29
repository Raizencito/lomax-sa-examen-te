"""Registra UN producto nuevo via API base (para E7 en EKS)."""
import io, sys
from PIL import Image, ImageDraw
import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8002"
CODE = sys.argv[2] if len(sys.argv) > 2 else "EKS-001"

r = requests.post(f"{BASE}/productos", json={
    "codigo": CODE, "nombre": "Teclado EKS", "descripcion": "Registrado desde EKS",
    "precio": 299.99, "categoria_id": 1,
    "atributos": {"conexion": "USB-C", "distribucion": "ES", "retroiluminado": "RGB"}})
print("POST:", r.status_code, r.text[:200])
if r.status_code == 409:
    print("ya existia, fin"); sys.exit(0)
r.raise_for_status()
pid = r.json()["producto_id"]
im = Image.new("RGB", (1200, 800), (10, 150, 60))
d = ImageDraw.Draw(im); d.text((500, 390), CODE, fill=(255, 255, 255))
b = io.BytesIO(); im.save(b, "JPEG", quality=85); b.seek(0)
f = requests.post(f"{BASE}/productos/{pid}/imagen", files={"imagen": (f"{CODE}.jpg", b, "image/jpeg")})
print("IMAGEN:", f.status_code, f.text[:200])
g = requests.get(f"{BASE}/productos")
print("TOTAL:", g.json()["total"])
