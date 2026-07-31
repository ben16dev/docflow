"""
Runtime OCR para DocFlow: localización de dependencias y construcción
del comando OCRmyPDF / entorno del subproceso.

No muta os.environ globalmente. Distingue macOS (sistema) y Windows
(runtime portable preparado, no validado aún).
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping, Optional, Sequence


class DependencyOrigin(str, Enum):
    SYSTEM = "system"
    BUNDLED = "bundled"
    MISSING = "missing"


class OcrDependencyError(RuntimeError):
    """Error controlado cuando falta una dependencia OCR."""

    def __init__(self, category: str, message: str):
        self.category = category
        super().__init__(message)


@dataclass(frozen=True)
class LocatedBinary:
    path: Optional[Path]
    origin: DependencyOrigin


@dataclass(frozen=True)
class LocatedTessdata:
    path: Optional[Path]
    origin: DependencyOrigin


# Flags base validados en el spike DocFlow (sin Ghostscript / sin PDF/A).
OCR_BASE_FLAGS: tuple[str, ...] = (
    "--language", "spa",
    "--output-type", "pdf",
    "--optimize", "0",
    "--mode", "skip",
    "--rasterizer", "pypdfium",
    "--jobs", "1",
    "--no-progress-bar",
)

# Nombre del directorio portable empaquetado (frozen / futuro Windows).
BUNDLED_TESSERACT_DIRNAME = "tesseract_bundle"


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"))


def _meipass() -> Optional[Path]:
    if _is_frozen():
        return Path(sys._MEIPASS)
    return None


def _frozen_search_roots() -> list[Path]:
    """
    Raíces candidatas donde PyInstaller puede colocar binarios y datas.

    Cubre onedir clásico, `_internal`, Contents/MacOS y Contents/Resources.
    """
    roots: list[Path] = []
    meipass = _meipass()
    if meipass is not None:
        roots.append(meipass)

    exe = Path(sys.executable)
    exe_dir = exe.parent
    roots.append(exe_dir)
    roots.append(exe_dir / "_internal")

    # DocFlow.app/Contents/MacOS → Contents/Resources[/_internal]
    if exe_dir.name == "MacOS":
        contents = exe_dir.parent
        resources = contents / "Resources"
        roots.append(resources)
        roots.append(resources / "_internal")
        roots.append(contents / "Frameworks")

    # Deduplicar conservando orden.
    seen: set[Path] = set()
    ordered: list[Path] = []
    for root in roots:
        try:
            key = root.resolve()
        except OSError:
            key = root
        if key in seen:
            continue
        seen.add(key)
        ordered.append(root)
    return ordered


def _bundled_tesseract_root() -> Optional[Path]:
    """Raíz del runtime Tesseract empaquetado, si existe."""
    if not _is_frozen():
        return None
    for root in _frozen_search_roots():
        candidate = root / BUNDLED_TESSERACT_DIRNAME
        if candidate.is_dir():
            return candidate
    return None


def _bundled_ocrmypdf_candidates() -> list[Path]:
    """Candidatos del helper OCRmyPDF empaquetado."""
    names = ("ocrmypdf", "ocrmypdf.exe")
    candidates: list[Path] = []
    for root in _frozen_search_roots():
        for name in names:
            candidates.append(root / name)
    return candidates


def locate_ocrmypdf() -> LocatedBinary:
    """
    Localiza el ejecutable OCRmyPDF.

    Frozen: solo helper empaquetado (sin fallback a venv/PATH del sistema).
    Desarrollo: binario junto al intérprete (venv) → PATH.
    """
    if _is_frozen():
        for path in _bundled_ocrmypdf_candidates():
            if path.is_file():
                return LocatedBinary(path=path, origin=DependencyOrigin.BUNDLED)
        return LocatedBinary(path=None, origin=DependencyOrigin.MISSING)

    candidates: list[tuple[Path, DependencyOrigin]] = []

    exe_dir = Path(sys.executable).parent
    for name in ("ocrmypdf", "ocrmypdf.exe"):
        candidates.append((exe_dir / name, DependencyOrigin.SYSTEM))

    # sys.prefix/bin cubre venvs donde el ejecutable no está junto al python.
    prefix_bin = Path(sys.prefix) / "bin"
    for name in ("ocrmypdf", "ocrmypdf.exe"):
        candidates.append((prefix_bin / name, DependencyOrigin.SYSTEM))
    prefix_scripts = Path(sys.prefix) / "Scripts"  # Windows venv
    for name in ("ocrmypdf", "ocrmypdf.exe"):
        candidates.append((prefix_scripts / name, DependencyOrigin.SYSTEM))

    seen: set[Path] = set()
    for path, origin in candidates:
        try:
            key = path.resolve() if path.exists() else path
        except OSError:
            key = path
        if key in seen:
            continue
        seen.add(key)
        if path.is_file():
            return LocatedBinary(path=path, origin=origin)

    which = shutil.which("ocrmypdf")
    if which:
        return LocatedBinary(path=Path(which), origin=DependencyOrigin.SYSTEM)

    return LocatedBinary(path=None, origin=DependencyOrigin.MISSING)


def locate_tesseract() -> LocatedBinary:
    """
    Localiza el ejecutable Tesseract.

    Frozen: solo tesseract_bundle (sin Homebrew).
    Desarrollo: sistema (Homebrew / PATH).
    """
    if _is_frozen():
        bundled = _bundled_tesseract_root()
        if bundled is not None:
            for name in ("tesseract", "tesseract.exe"):
                candidate = bundled / name
                if candidate.is_file():
                    return LocatedBinary(path=candidate, origin=DependencyOrigin.BUNDLED)
        return LocatedBinary(path=None, origin=DependencyOrigin.MISSING)

    # macOS / Linux: rutas habituales de Homebrew antes del PATH genérico.
    system = platform.system()
    if system == "Darwin":
        for candidate in (
            Path("/opt/homebrew/bin/tesseract"),
            Path("/usr/local/bin/tesseract"),
        ):
            if candidate.is_file():
                return LocatedBinary(path=candidate, origin=DependencyOrigin.SYSTEM)

    which = shutil.which("tesseract")
    if which:
        return LocatedBinary(path=Path(which), origin=DependencyOrigin.SYSTEM)

    return LocatedBinary(path=None, origin=DependencyOrigin.MISSING)


def locate_tessdata(*, language: str = "spa") -> LocatedTessdata:
    """
    Localiza el directorio tessdata que contiene el idioma solicitado.
    """
    if _is_frozen():
        bundled = _bundled_tesseract_root()
        if bundled is not None:
            td = bundled / "tessdata"
            if (td / f"{language}.traineddata").is_file():
                return LocatedTessdata(path=td, origin=DependencyOrigin.BUNDLED)
        return LocatedTessdata(path=None, origin=DependencyOrigin.MISSING)

    system = platform.system()
    candidates: list[Path] = []

    if system == "Darwin":
        candidates.extend([
            Path("/opt/homebrew/share/tessdata"),
            Path("/usr/local/share/tessdata"),
        ])
    elif system == "Windows":
        # Preparado para runtime portable; sin rutas de terceros.
        pass
    else:
        candidates.extend([
            Path("/usr/share/tesseract-ocr/5/tessdata"),
            Path("/usr/share/tesseract-ocr/4.00/tessdata"),
            Path("/usr/share/tessdata"),
        ])

    # Inferir desde el binario de Tesseract (share/tessdata relativo).
    tess = locate_tesseract()
    if tess.path is not None:
        parent = tess.path.resolve().parent
        candidates.append(parent.parent / "share" / "tessdata")

    env_prefix = os.environ.get("TESSDATA_PREFIX")
    if env_prefix:
        candidates.insert(0, Path(env_prefix))

    seen: set[Path] = set()
    for td in candidates:
        try:
            resolved = td.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if (resolved / f"{language}.traineddata").is_file():
            return LocatedTessdata(path=resolved, origin=DependencyOrigin.SYSTEM)

    return LocatedTessdata(path=None, origin=DependencyOrigin.MISSING)


def require_runtime(*, language: str = "spa") -> tuple[LocatedBinary, LocatedBinary, LocatedTessdata]:
    """
    Resuelve OCRmyPDF, Tesseract y tessdata o lanza OcrDependencyError.
    """
    ocrmypdf = locate_ocrmypdf()
    if ocrmypdf.path is None:
        raise OcrDependencyError(
            "missing_ocrmypdf",
            "No se encontró OCRmyPDF. Comprueba la instalación de DocFlow.",
        )

    tesseract = locate_tesseract()
    if tesseract.path is None:
        if _is_frozen():
            message = (
                "No se encontró Tesseract empaquetado. "
                "Reinstala DocFlow o regenera el build."
            )
        else:
            message = (
                "No se encontró Tesseract. En macOS instálalo con Homebrew "
                "(tesseract / tesseract-lang)."
            )
        raise OcrDependencyError("missing_tesseract", message)

    tessdata = locate_tessdata(language=language)
    if tessdata.path is None:
        raise OcrDependencyError(
            "missing_tessdata",
            f"No se encontró tessdata para el idioma '{language}'.",
        )

    return ocrmypdf, tesseract, tessdata


def build_ocr_command(
    input_pdf: Path,
    output_pdf: Path,
    *,
    ocrmypdf_bin: Optional[Path] = None,
) -> list[str]:
    """
    Construye el comando OCRmyPDF (lista para Popen, shell=False).

    No incluye Ghostscript, deskew, rotate-pages ni PDF/A.
    """
    if ocrmypdf_bin is None:
        located = locate_ocrmypdf()
        if located.path is None:
            raise OcrDependencyError(
                "missing_ocrmypdf",
                "No se encontró OCRmyPDF. Comprueba la instalación de DocFlow.",
            )
        ocrmypdf_bin = located.path

    return [
        str(ocrmypdf_bin),
        *OCR_BASE_FLAGS,
        str(input_pdf),
        str(output_pdf),
    ]


def build_subprocess_env(
    *,
    tesseract: Optional[LocatedBinary] = None,
    tessdata: Optional[LocatedTessdata] = None,
    base_environ: Optional[Mapping[str, str]] = None,
) -> dict[str, str]:
    """
    Construye un entorno específico para el subproceso OCR.

    Copia el entorno base; no modifica os.environ.
    No usa DYLD_LIBRARY_PATH como estrategia principal: las dylibs deben
    resolverse vía install names / rpaths del bundle.
    """
    env: dict[str, str] = dict(
        base_environ if base_environ is not None else os.environ
    )

    if tesseract is None:
        tesseract = locate_tesseract()
    if tessdata is None:
        tessdata = locate_tessdata()

    path_parts: list[str] = []

    if tesseract.path is not None:
        path_parts.append(str(tesseract.path.parent))

    if _is_frozen():
        # Helper OCRmyPDF junto a DocFlow / Contents/MacOS.
        for root in _frozen_search_roots():
            helper = root / "ocrmypdf"
            if helper.is_file():
                helper_dir = str(helper.parent)
                if helper_dir not in path_parts:
                    path_parts.append(helper_dir)

    bundled = _bundled_tesseract_root()
    if bundled is not None and str(bundled) not in path_parts:
        path_parts.append(str(bundled))

    if path_parts:
        current_path = env.get("PATH", "")
        env["PATH"] = os.pathsep.join(
            path_parts + ([current_path] if current_path else [])
        )

    if tessdata.path is not None:
        env["TESSDATA_PREFIX"] = str(tessdata.path)

    return env


def popen_creationflags() -> int:
    """Flags de creación de proceso para Windows; 0 en el resto."""
    if platform.system() != "Windows":
        return 0

    # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    create_no_window = getattr(subprocess_constants(), "CREATE_NO_WINDOW", 0x08000000)
    create_new_process_group = getattr(
        subprocess_constants(), "CREATE_NEW_PROCESS_GROUP", 0x00000200
    )
    return int(create_no_window | create_new_process_group)


def subprocess_constants():
    """Acceso lazy a constantes de subprocess (evita acoplar en import)."""
    import subprocess

    return subprocess


def should_start_new_session() -> bool:
    """macOS/Linux: nueva sesión para poder matar el process group."""
    return platform.system() != "Windows"


def redact_process_text(text: str) -> str:
    """
    Redacta stderr/stdout de OCRmyPDF/Tesseract antes de loguear.

    Elimina rutas absolutas y fragmentos largos que puedan contener texto OCR.
    """
    if not text:
        return ""

    import re

    redacted = text
    # Rutas Unix y Windows
    redacted = re.sub(r"(?i)([a-z]:\\[^\s\"']+)", "[path]", redacted)
    redacted = re.sub(r"(/(?:Users|home|tmp|var|private|opt)[^\s\"']*)", "[path]", redacted)
    redacted = re.sub(r"(/[^\s\"']+\.pdf)", "[pdf]", redacted)
    # Truncar
    if len(redacted) > 800:
        redacted = redacted[:800] + "…"
    return redacted


def summarize_dependency_origins(
    ocrmypdf: LocatedBinary,
    tesseract: LocatedBinary,
    tessdata: LocatedTessdata,
) -> dict[str, str]:
    """Resumen seguro para logs (origen, sin rutas)."""
    return {
        "ocrmypdf": ocrmypdf.origin.value,
        "tesseract": tesseract.origin.value,
        "tessdata": tessdata.origin.value,
    }


def assert_command_has_no_ghostscript(cmd: Sequence[str]) -> None:
    """Comprobación defensiva: el comando no debe invocar Ghostscript."""
    joined = " ".join(cmd).lower()
    if "ghostscript" in joined or joined.endswith(" gs") or " gs " in joined:
        raise OcrDependencyError(
            "ghostscript_forbidden",
            "La configuración OCR no permite Ghostscript.",
        )
