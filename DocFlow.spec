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

import sys
from pathlib import Path

BASE = Path(SPECPATH)


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

icons_dir = BASE / "ui" / "icons"
if icons_dir.exists():
    datas.append((str(icons_dir), "ui/icons"))


if sys.platform == "win32":
    icon_file = str(BASE / "assets" / "icon.ico")
elif sys.platform == "darwin":
    icon_file = str(BASE / "assets" / "icon.icns")
else:
    icon_path = BASE / "assets" / "icon.png"
    icon_file = str(icon_path) if icon_path.exists() else None


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
