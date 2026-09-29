"""Carga 20 productos publicados (requiere backend en :8000). Codigos unicos deterministas."""
import io, sys
from PIL import Image, ImageDraw
import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

JOBS = []
for i in range(1, 9):
    JOBS.append((f"TEC-{i:03d}", f"Teclado {i}", 50 + i * 10.5, 1,
                 {"conexion": "USB-C" if i % 2 else "2.4GHz", "distribucion": "ES" if i % 2 else "US",
                  "retroiluminado": "RGB" if i % 2 else "No"}))
for i in range(1, 8):
    JOBS.append((f"MON-{i:03d}", f"Pantalla {i}", 150 + i * 25.0, 2,
                 {"pulgadas": str(24 + i), "resolucion": "2560x1440", "tasa_refresco": "165Hz"}))
for i in range(1, 6):
    JOBS.append((f"AUD-{i:03d}", f"Audifono {i}", 80 + i * 12.0, 3,
                 {"tipo": "Over-ear", "conexion": "Bluetooth", "cancelacion_ruido": "Si" if i % 2 else "No"}))
assert len(JOBS) == 20

def img_bytes(text, color):
    im = Image.new("RGB", (1200, 800), color)
    d = ImageDraw.Draw(im); d.text((500, 390), text, fill=(255, 255, 255))
    b = io.BytesIO(); im.save(b, "JPEG", quality=85); return b.getvalue()

def main():
    ok = 0
    for idx, (code, name, price, cat, attrs) in enumerate(JOBS, 1):
        r = requests.post(f"{BASE}/productos", json={
            "codigo": code, "nombre": name, "descripcion": f"{name} Lomax SA",
            "precio": price, "categoria_id": cat, "atributos": attrs})
        if r.status_code == 409:
            print(f"{code} ya existe, se reutiliza"); continue
        r.raise_for_status()
        pid = r.json()["producto_id"]
        raw = img_bytes(code, (40 + idx * 8 % 180, 90, 180))
        f = requests.post(f"{BASE}/productos/{pid}/imagen",
                          files={"imagen": (f"{code}.jpg", raw, "image/jpeg")})
        print(code, pid, f.status_code, f.json().get("estado"))
        assert f.json().get("estado") == "PUBLICADO", f.text
        ok += 1
    print(f"OK nuevos publicados: {ok}")

if __name__ == "__main__":
    main()
