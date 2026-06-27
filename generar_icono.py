from pathlib import Path
from PIL import Image

# Rutas
base_dir = Path(__file__).resolve().parent
png_path = base_dir / "assets" / "icon.png"
ico_path = base_dir / "assets" / "icon.ico"

# Abrir imagen
img = Image.open(png_path)

# Asegurar que tenga canal alpha
img = img.convert("RGBA")

# Tamaños requeridos para Windows
sizes = [
    (16, 16),
    (24, 24),
    (32, 32),
    (48, 48),
    (64, 64),
    (128, 128),
    (256, 256),
]

# Guardar como .ico multi-resolución
img.save(ico_path, format="ICO", sizes=sizes)

print("Icono generado correctamente en:", ico_path)