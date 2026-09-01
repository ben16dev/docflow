"""
E/S segura para OCR en DocFlow: temporales, colisiones, validación y promoción.
"""

from __future__ import annotations

import os
import secrets
import stat
import sys
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


def ensure_output_visible(path: Path) -> None:
    """
    En macOS, elimina únicamente UF_HIDDEN del archivo final.

    Los temporales `.docflow_ocr_*` heredan UF_HIDDEN; os.replace conserva
    el inode y el flag, así que el PDF final seguiría oculto en Finder.
    En otros sistemas es un no-op seguro.
    """
    path = Path(path)
    if sys.platform != "darwin":
        return

    chflags = getattr(os, "chflags", None)
    uf_hidden = getattr(stat, "UF_HIDDEN", None)
    if chflags is None or uf_hidden is None:
        raise OcrValidationError(
            "hidden_flag_clear_failed",
            "No se pudo hacer visible el PDF OCR generado.",
        )

    try:
        current_flags = path.stat().st_flags
    except OSError as exc:
        raise OcrValidationError(
            "hidden_flag_clear_failed",
            "No se pudo comprobar la visibilidad del PDF OCR generado.",
        ) from exc

    if not (current_flags & uf_hidden):
        return

    try:
        chflags(path, current_flags & ~uf_hidden)
        remaining = path.stat().st_flags
    except OSError as exc:
        raise OcrValidationError(
            "hidden_flag_clear_failed",
            "No se pudo hacer visible el PDF OCR generado.",
        ) from exc

    if remaining & uf_hidden:
        raise OcrValidationError(
            "hidden_flag_clear_failed",
            "No se pudo hacer visible el PDF OCR generado.",
        )


def promote_temp_to_final(temp_path: Path, final_path: Path) -> Path:
    """
    Promueve el temporal al nombre final con replace atómico en el mismo volumen.

    Si final_path ya existiera (condición de carrera), se resuelve colisión.
    Verifica que el archivo final exista tras el replace y no quede UF_HIDDEN.
    """
    temp_path = Path(temp_path)
    final_path = Path(final_path)

    if not temp_path.exists():
        raise OcrValidationError("missing_temp", "No existe el PDF temporal a promover.")

    if final_path.exists():
        final_path = resolve_conflict(final_path, pattern="_v{i}")

    final_path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(temp_path, final_path)

    if not final_path.is_file():
        raise OcrValidationError(
            "missing_promoted_output",
            "El OCR terminó, pero no se encontró el archivo final tras la promoción.",
        )

    # Tras replace el inode conserva UF_HIDDEN del temporal con punto.
    # Si falla, el PDF ya promovido se conserva y la incidencia se propaga.
    ensure_output_visible(final_path)

    return final_path


def assert_output_not_source(output_path: Path, source_path: Path) -> None:
    """Postcondición: una salida OCR nunca puede ser el PDF de entrada."""
    output_path = Path(output_path)
    source_path = Path(source_path)

    try:
        if output_path.resolve() == source_path.resolve():
            raise OcrValidationError(
                "output_matches_source",
                "La salida OCR coincide con el PDF de entrada.",
            )
    except FileNotFoundError:
        if output_path.absolute() == source_path.absolute():
            raise OcrValidationError(
                "output_matches_source",
                "La salida OCR coincide con el PDF de entrada.",
            )


def assert_final_in_destination(final_path: Path, output_dir: Path) -> Path:
    """
    Postcondición: el PDF final existe y pertenece a la carpeta de destino.
    """
    final_path = Path(final_path)
    output_dir = Path(output_dir)

    if not final_path.is_file():
        raise OcrValidationError(
            "missing_promoted_output",
            "El OCR terminó, pero no se encontró el archivo final.",
        )

    try:
        final_path.resolve().relative_to(output_dir.resolve())
    except ValueError as exc:
        raise OcrValidationError(
            "output_outside_destination",
            "El archivo OCR se generó fuera de la carpeta de destino.",
        ) from exc

    return final_path


def create_work_dir(prefix: str = "docflow_ocr_") -> Path:
    """Directorio temporal seguro para residuos auxiliares."""
    return Path(tempfile.mkdtemp(prefix=prefix))
