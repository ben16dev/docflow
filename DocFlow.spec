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
#
# OCR macOS: en Darwin se genera onedir + BUNDLE con tesseract_bundle
# y helper ocrmypdf. En Windows/Linux se mantiene el EXE onefile previo.

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

BASE = Path(SPECPATH)

# Leer APP_VERSION desde version.py sin importar el módulo (más seguro en el
# contexto del spec, que se ejecuta en el entorno de PyInstaller).
_version_text = (BASE / "version.py").read_text(encoding="utf-8")
_ver_match = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', _version_text)
APP_VERSION = _ver_match.group(1) if _ver_match else "0.0.0"

BUNDLED_TESSERACT_DIRNAME = "tesseract_bundle"
_SYSTEM_LIB_PREFIXES = (
    "/usr/lib",
    "/System/",
    "/Library/Frameworks/",
)


def _asset_if_exists(relative: str) -> list:
    """Incluye un asset sólo si el archivo existe en el momento de compilar."""
    p = BASE / relative
    if p.exists():
        dest = str(Path(relative).parent)
        return [(str(p), dest)]
    return []


def _is_system_macho(path: Path) -> bool:
    text = str(path)
    return text.startswith(_SYSTEM_LIB_PREFIXES)


def _otool_dependencies(binary: Path) -> list[Path]:
    """Devuelve dependencias Mach-O absolutas no pertenecientes al sistema."""
    try:
        completed = subprocess.run(
            ["otool", "-L", str(binary)],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []

    deps: list[Path] = []
    for line in completed.stdout.splitlines()[1:]:
        raw = line.strip().split(" ", 1)[0]
        if not raw or raw.startswith("@"):
            continue
        dep = Path(raw)
        if not dep.is_absolute() or _is_system_macho(dep):
            continue
        try:
            resolved = dep.resolve()
        except OSError:
            continue
        if resolved.is_file():
            deps.append(resolved)
    return deps


def _collect_non_system_dylibs(root_binary: Path) -> list[Path]:
    """Recorre dependencias transitivas de un binario Mach-O."""
    pending = [root_binary.resolve()]
    seen: set[Path] = set()
    collected: list[Path] = []

    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        for dep in _otool_dependencies(current):
            if dep in seen or dep == root_binary.resolve():
                continue
            if _is_system_macho(dep):
                continue
            collected.append(dep)
            pending.append(dep)
    return collected


def _locate_tesseract_for_bundle() -> Path:
    which = shutil.which("tesseract")
    if which:
        return Path(which).resolve()
    for candidate in (
        Path("/opt/homebrew/bin/tesseract"),
        Path("/usr/local/bin/tesseract"),
    ):
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        "No se encontró tesseract en PATH para el empaquetado macOS."
    )


def _locate_spa_traineddata() -> Path:
    env_prefix = os.environ.get("TESSDATA_PREFIX")
    candidates: list[Path] = []
    if env_prefix:
        candidates.append(Path(env_prefix) / "spa.traineddata")
        candidates.append(Path(env_prefix) / "tessdata" / "spa.traineddata")

    tess = shutil.which("tesseract")
    if tess:
        parent = Path(tess).resolve().parent
        candidates.append(parent.parent / "share" / "tessdata" / "spa.traineddata")

    candidates.extend(
        [
            Path("/opt/homebrew/share/tessdata/spa.traineddata"),
            Path("/usr/local/share/tessdata/spa.traineddata"),
        ]
    )

    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate.resolve()
        except OSError:
            continue
    raise FileNotFoundError(
        "No se encontró spa.traineddata para el empaquetado macOS."
    )


def _locate_tesseract_configs_dir(*, beside_spa: Path) -> Path:
    """
    Localiza el directorio tessdata/configs.

    OCRmyPDF invoca configs como hocr/txt; la validación de empaquetado
    demostró que no basta con un único archivo.
    """
    candidates: list[Path] = [beside_spa.parent / "configs"]

    tess = shutil.which("tesseract")
    if tess:
        parent = Path(tess).resolve().parent
        candidates.append(parent.parent / "share" / "tessdata" / "configs")

    candidates.extend(
        [
            Path("/opt/homebrew/share/tessdata/configs"),
            Path("/usr/local/share/tessdata/configs"),
        ]
    )

    for candidate in candidates:
        try:
            if candidate.is_dir() and (candidate / "hocr").is_file():
                return candidate.resolve()
        except OSError:
            continue
    raise FileNotFoundError(
        "No se encontró tessdata/configs (requerido por OCRmyPDF)."
    )


def _tesseract_bundle_entries() -> tuple[list, list]:
    """
    Binaries + datas del layout tesseract_bundle/.

    Solo se usa en Darwin. Las dylibs se añaden como binaries para que
    PyInstaller reescriba install names.
    """
    tess_bin = _locate_tesseract_for_bundle()
    spa = _locate_spa_traineddata()
    configs_dir = _locate_tesseract_configs_dir(beside_spa=spa)
    dylibs = _collect_non_system_dylibs(tess_bin)

    binaries = [(str(tess_bin), BUNDLED_TESSERACT_DIRNAME)]
    for dylib in dylibs:
        binaries.append((str(dylib), f"{BUNDLED_TESSERACT_DIRNAME}/lib"))

    datas = [
        (str(spa), f"{BUNDLED_TESSERACT_DIRNAME}/tessdata"),
        (str(configs_dir), f"{BUNDLED_TESSERACT_DIRNAME}/tessdata/configs"),
    ]
    return binaries, datas


datas = []
datas += _asset_if_exists("assets/icon.png")
datas += _asset_if_exists("assets/icon.ico")
datas += _asset_if_exists("assets/icon.icns")
datas += _asset_if_exists("assets/logo.png")

icons_dir = BASE / "ui" / "icons"
if icons_dir.exists():
    datas.append((str(icons_dir), "ui/icons"))

binaries = []
hiddenimports = ["pypdf", "fitz", "reportlab", "docx"]

# OCR: metadata, datos y plugins dinámicos (sin collect_all indiscriminado).
datas += copy_metadata("ocrmypdf")
datas += copy_metadata("pikepdf")
datas += copy_metadata("pypdfium2")
datas += collect_data_files("ocrmypdf")
hiddenimports += collect_submodules("ocrmypdf")
hiddenimports += [
    "ocrmypdf.builtin_plugins",
    "ocrmypdf.builtin_plugins.pypdfium",
    "ocrmypdf.builtin_plugins.tesseract_ocr",
    "ocrmypdf.builtin_plugins.concurrency",
    "ocrmypdf.builtin_plugins.default_filters",
    "ocrmypdf.builtin_plugins.ghostscript",
    "ocrmypdf.builtin_plugins.optimize",
    "pypdfium2",
    "pikepdf",
]

if sys.platform == "darwin":
    tess_bins, tess_datas = _tesseract_bundle_entries()
    binaries += tess_bins
    datas += tess_datas


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
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# Helper OCRmyPDF: segundo Analysis mínimo; MERGE evita duplicar dependencias.
ocr_a = Analysis(
    [str(BASE / "scripts" / "common" / "ocrmypdf_entry.py")],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

MERGE((a, "DocFlow", "DocFlow"), (ocr_a, "ocrmypdf", "ocrmypdf"))

pyz = PYZ(a.pure)
ocr_pyz = PYZ(ocr_a.pure)

if sys.platform == "darwin":
    # onedir real: EXE sin binaries/datas → COLLECT → BUNDLE
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="DocFlow",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=icon_file,
    )
    ocr_exe = EXE(
        ocr_pyz,
        ocr_a.scripts,
        [],
        exclude_binaries=True,
        name="ocrmypdf",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        console=True,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        ocr_exe,
        ocr_a.binaries,
        ocr_a.zipfiles,
        ocr_a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="DocFlow",
    )
    app = BUNDLE(
        coll,
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
else:
    # Windows / Linux: mantiene el layout onefile previo.
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
