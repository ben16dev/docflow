# -*- mode: python ; coding: utf-8 -*-
#
# DocFlow.spec — Archivo de empaquetado con PyInstaller.
#
# Selección del icono según plataforma:
#   Windows → assets/icon.ico
#   macOS   → assets/icon.icns
#   Linux   → assets/icon.png (sin icono nativo específico)
#
# Los recursos deben existir antes de compilar.
# Ejecuta primero: python generar_icono.py
#
# Bundle identifier provisional: com.docflow.app
# TODO: cambiar por un identificador basado en el dominio o empresa definitivos
#       antes de distribución pública.

import sys
import re
from pathlib import Path

BASE = Path(SPECPATH)

# Leer APP_VERSION desde version.py sin importar el módulo (más seguro en el
# contexto del spec, que se ejecuta en el entorno de PyInstaller).
_version_text = (BASE / "version.py").read_text(encoding="utf-8")
_ver_match = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', _version_text)
APP_VERSION = _ver_match.group(1) if _ver_match else "0.0.0"


def _asset_if_exists(relative: str) -> list:
    """Incluye un asset sólo si el archivo existe en el momento de compilar."""
    p = BASE / relative
    if p.exists():
        dest = str(Path(relative).parent)
        return [(str(p), dest)]
    return []


datas = []
datas += _asset_if_exists("assets/icon.png")
datas += _asset_if_exists("assets/icon.ico")
datas += _asset_if_exists("assets/icon.icns")
datas += _asset_if_exists("assets/logo.png")

icons_dir = BASE / "ui" / "icons"
if icons_dir.exists():
    datas.append((str(icons_dir), "ui/icons"))


# Selección y validación del icono requerido por la plataforma actual.
# Se lanza un error descriptivo si falta el icono necesario.
if sys.platform == "win32":
    _icon_path = BASE / "assets" / "icon.ico"
    if not _icon_path.exists():
        raise FileNotFoundError(
            f"Icono requerido para Windows no encontrado: {_icon_path}\n"
            "Ejecuta: python generar_icono.py"
        )
    icon_file = str(_icon_path)
elif sys.platform == "darwin":
    _icon_path = BASE / "assets" / "icon.icns"
    if not _icon_path.exists():
        raise FileNotFoundError(
            f"Icono requerido para macOS no encontrado: {_icon_path}\n"
            "Ejecuta: python generar_icono.py"
        )
    icon_file = str(_icon_path)
else:
    _icon_path = BASE / "assets" / "icon.png"
    icon_file = str(_icon_path) if _icon_path.exists() else None


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=["pypdf", "fitz", "reportlab", "docx"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="DocFlow",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)

# ── macOS: envuelve el ejecutable en un bundle .app nativo ──────────────────
# En Windows solo se genera dist/DocFlow.exe; en Linux, dist/DocFlow.
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="DocFlow.app",
        icon=icon_file,
        bundle_identifier="com.docflow.app",
        info_plist={
            "CFBundleName": "DocFlow",
            "CFBundleDisplayName": "DocFlow",
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundleVersion": APP_VERSION,
            "CFBundleIdentifier": "com.docflow.app",
            "NSHighResolutionCapable": True,
        },
    )
