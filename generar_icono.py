"""
Generador de iconos para DocFlow.

Genera assets/icon.ico (Windows, multirresolución) y, en macOS,
assets/icon.icns a partir de assets/icon.png.

Uso:
    python generar_icono.py

Requisitos:
    - assets/icon.png debe existir y ser un PNG cuadrado (recomendado 1024×1024).
    - Pillow instalado en el entorno virtual.
    - Para generar .icns en macOS se usa la herramienta nativa `iconutil`.
      En Windows o Linux sólo se genera el .ico.
"""

import shutil
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow no está instalado. Ejecuta: pip install Pillow")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Rutas — siempre relativas a la ubicación de este script
# ---------------------------------------------------------------------------

BASE_DIR: Path = Path(__file__).resolve().parent
PNG_SRC: Path = BASE_DIR / "assets" / "icon.png"
ICO_DST: Path = BASE_DIR / "assets" / "icon.ico"
ICNS_DST: Path = BASE_DIR / "assets" / "icon.icns"

ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]

ICNS_SIZES = {
    "icon_16x16.png": 16,
    "icon_16x16@2x.png": 32,
    "icon_32x32.png": 32,
    "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128,
    "icon_128x128@2x.png": 256,
    "icon_256x256.png": 256,
    "icon_256x256@2x.png": 512,
    "icon_512x512.png": 512,
    "icon_512x512@2x.png": 1024,
}


# ---------------------------------------------------------------------------
# Validación del archivo fuente
# ---------------------------------------------------------------------------

def _validar_fuente() -> Image.Image:
    if not PNG_SRC.exists():
        print(f"ERROR: No se encontró el archivo fuente: {PNG_SRC}")
        print("       Crea o coloca assets/icon.png (PNG cuadrado, 1024×1024 recomendado).")
        sys.exit(1)

    if PNG_SRC.suffix.lower() != ".png":
        print(f"ERROR: El archivo fuente debe ser PNG, pero se encontró: {PNG_SRC.suffix}")
        sys.exit(1)

    try:
        img = Image.open(PNG_SRC)
        img.verify()
    except Exception as exc:
        print(f"ERROR: No se puede abrir/verificar {PNG_SRC}: {exc}")
        sys.exit(1)

    img = Image.open(PNG_SRC).convert("RGBA")
    w, h = img.size

    if w != h:
        print(f"ADVERTENCIA: La imagen no es cuadrada ({w}×{h} px).")
        print("             Se recomienda 1024×1024. El icono puede distorsionarse.")

    if w < 256 or h < 256:
        print(f"ADVERTENCIA: La imagen es pequeña ({w}×{h} px).")
        print("             Se recomienda un mínimo de 512×512, ideal 1024×1024.")

    return img


# ---------------------------------------------------------------------------
# Generación del .ico (Windows, multirresolución)
# ---------------------------------------------------------------------------

def _generar_ico(img: Image.Image) -> None:
    sizes = [(s, s) for s in ICO_SIZES]
    try:
        img.save(ICO_DST, format="ICO", sizes=sizes)
        print(f"  [OK] icon.ico generado: {ICO_DST}")
        print(f"       Resoluciones incluidas: {', '.join(str(s) for s in ICO_SIZES)} px")
    except Exception as exc:
        print(f"  [ERROR] No se pudo generar icon.ico: {exc}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Generación del .icns (macOS, mediante iconutil)
# ---------------------------------------------------------------------------

def _generar_icns(img: Image.Image) -> None:
    if sys.platform != "darwin":
        print("  [INFO] La generación de .icns requiere macOS (iconutil).")
        print("         Omitiendo icon.icns en esta plataforma.")
        return

    if not shutil.which("iconutil"):
        print("  [ERROR] No se encontró 'iconutil' en el sistema.")
        print("          Instala Xcode Command Line Tools: xcode-select --install")
        return

    iconset_dir: Path = BASE_DIR / "assets" / "DocFlow.iconset"
    try:
        iconset_dir.mkdir(parents=True, exist_ok=True)

        for filename, size in ICNS_SIZES.items():
            resized = img.resize((size, size), Image.LANCZOS)
            resized.save(iconset_dir / filename, format="PNG")

        result = subprocess.run(
            ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(ICNS_DST)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"  [ERROR] iconutil falló: {result.stderr.strip()}")
        else:
            print(f"  [OK] icon.icns generado: {ICNS_DST}")

    except Exception as exc:
        print(f"  [ERROR] Error durante la generación de .icns: {exc}")
    finally:
        if iconset_dir.exists():
            try:
                shutil.rmtree(iconset_dir)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def main() -> None:
    print("DocFlow — Generador de iconos")
    print(f"Fuente: {PNG_SRC}\n")

    img = _validar_fuente()
    w, h = img.size
    print(f"  Imagen cargada: {w}×{h} px, modo {img.mode}\n")

    print("Generando icon.ico (Windows)…")
    _generar_ico(img)

    print("\nGenerando icon.icns (macOS)…")
    _generar_icns(img)

    print("\nListo.")
    print("Archivos que NO deben editarse manualmente: icon.ico, icon.icns")
    print("Edita únicamente assets/icon.png y vuelve a ejecutar este script.")


if __name__ == "__main__":
    main()
