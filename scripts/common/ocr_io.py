"""
E/S segura para OCR en DocFlow: temporales, colisiones, validación y promoción.
"""

from __future__ import annotations

import os
import secrets
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from scripts.common.filenames import resolve_conflict, sanitize_filename


class OcrValidationError(RuntimeError):
    """El PDF OCR no superó la validación previa a la promoción."""

    def __init__(self, category: str, message: str):
        self.category = category
        super().__init__(message)


@dataclass(frozen=True)
class OcrValidationResult:
    ok: bool
    category: str
    page_count_original: int
    page_count_output: int
    has_extractable_text: bool
    size_bytes: int


def make_temp_pdf_path(output_dir: Path, source_stem: str) -> Path:
    """
    Crea un nombre temporal propio de DocFlow en el mismo volumen de destino.

    El archivo aún no se crea; solo se reserva la ruta.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_stem = sanitize_filename(source_stem, max_len=40, fallback="doc")
    token = secrets.token_hex(6)
    name = f".docflow_ocr_{safe_stem}_{token}.pdf"
    return output_dir / name


def resolve_output_path(output_dir: Path, source_name: str, *, suffix: str = "_ocr") -> Path:
    """
    Nombre final en destino usando el helper de colisiones de DocFlow.

    Ejemplo: informe.pdf → informe_ocr.pdf → informe_ocr_v2.pdf
    """
    stem = Path(source_name).stem
    safe = sanitize_filename(f"{stem}{suffix}", max_len=120, fallback="documento_ocr")
    return resolve_conflict(Path(output_dir) / f"{safe}.pdf", pattern="_v{i}")


def safe_unlink(path: Optional[Path]) -> None:
    """Elimina un archivo si existe; ignora errores de ausencia."""
    if path is None:
        return
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


def safe_rmtree(path: Optional[Path]) -> None:
    """Elimina un directorio temporal de forma best-effort."""
    if path is None:
        return
    import shutil

    try:
        shutil.rmtree(path, ignore_errors=True)
    except OSError:
        pass


def pdf_page_count(path: Path) -> int:
    """Número de páginas; prefiere PyMuPDF, fallback pypdf."""
    path = Path(path)
    try:
        import fitz

        doc = fitz.open(path)
        try:
            return int(doc.page_count)
        finally:
            doc.close()
    except Exception:
        from pypdf import PdfReader

        return len(PdfReader(str(path)).pages)


def pdf_has_extractable_text(path: Path, *, min_chars: int = 3) -> bool:
    """
    Comprueba si hay texto extraíble.

    No devuelve ni registra el contenido.
    """
    path = Path(path)
    text_len = 0
    try:
        import fitz

        doc = fitz.open(path)
        try:
            for page in doc:
                fragment = page.get_text("text") or ""
                text_len += len(fragment.strip())
                if text_len >= min_chars:
                    return True
        finally:
            doc.close()
    except Exception:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        for page in reader.pages:
            fragment = page.extract_text() or ""
            text_len += len(fragment.strip())
            if text_len >= min_chars:
                return True
    return text_len >= min_chars


def pdf_opens(path: Path) -> bool:
    """Comprueba que el PDF abre sin error."""
    try:
        pdf_page_count(path)
        return True
    except Exception:
        return False


def validate_ocr_output(
    original: Path,
    candidate: Path,
    *,
    require_text: bool = True,
) -> OcrValidationResult:
    """
    Valida el PDF OCR antes de promoverlo al nombre final.

    Comprueba: existe, tamaño > 0, abre, mismas páginas, texto extraíble.
    No registra el texto extraído.
    """
    original = Path(original)
    candidate = Path(candidate)

    if not candidate.exists():
        return OcrValidationResult(
            ok=False,
            category="missing_output",
            page_count_original=0,
            page_count_output=0,
            has_extractable_text=False,
            size_bytes=0,
        )

    try:
        size = candidate.stat().st_size
    except OSError:
        size = 0

    if size <= 0:
        return OcrValidationResult(
            ok=False,
            category="empty_output",
            page_count_original=0,
            page_count_output=0,
            has_extractable_text=False,
            size_bytes=size,
        )

    try:
        pages_orig = pdf_page_count(original)
        pages_out = pdf_page_count(candidate)
    except Exception:
        return OcrValidationResult(
            ok=False,
            category="unreadable_pdf",
            page_count_original=0,
            page_count_output=0,
            has_extractable_text=False,
            size_bytes=size,
        )

    if pages_orig != pages_out:
        return OcrValidationResult(
            ok=False,
            category="page_count_mismatch",
            page_count_original=pages_orig,
            page_count_output=pages_out,
            has_extractable_text=False,
            size_bytes=size,
        )

    has_text = pdf_has_extractable_text(candidate)
    if require_text and not has_text:
        return OcrValidationResult(
            ok=False,
            category="no_extractable_text",
            page_count_original=pages_orig,
            page_count_output=pages_out,
            has_extractable_text=False,
            size_bytes=size,
        )

    return OcrValidationResult(
        ok=True,
        category="ok",
        page_count_original=pages_orig,
        page_count_output=pages_out,
        has_extractable_text=has_text,
        size_bytes=size,
    )


def promote_temp_to_final(temp_path: Path, final_path: Path) -> Path:
    """
    Promueve el temporal al nombre final con replace atómico en el mismo volumen.

    Si final_path ya existiera (condición de carrera), se resuelve colisión.
    """
    temp_path = Path(temp_path)
    final_path = Path(final_path)

    if not temp_path.exists():
        raise OcrValidationError("missing_temp", "No existe el PDF temporal a promover.")

    if final_path.exists():
        final_path = resolve_conflict(final_path, pattern="_v{i}")

    final_path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(temp_path, final_path)
    return final_path


def create_work_dir(prefix: str = "docflow_ocr_") -> Path:
    """Directorio temporal seguro para residuos auxiliares."""
    return Path(tempfile.mkdtemp(prefix=prefix))
