"""Genera imagen de prueba 1200x800 y un archivo invalido para E3."""
from PIL import Image, ImageDraw

img = Image.new("RGB", (1200, 800), (30, 90, 200))
d = ImageDraw.Draw(img)
d.rectangle([100, 100, 1100, 700], outline=(255, 255, 255), width=8)
d.text((480, 390), "LOMAX 1200x800", fill=(255, 255, 0))
img.save("test-1200x800.jpg", "JPEG", quality=90)
print("OK test-1200x800.jpg 1200x800")

with open("invalido.txt", "w") as f:
    f.write("esto no es una imagen")
print("OK invalido.txt")
