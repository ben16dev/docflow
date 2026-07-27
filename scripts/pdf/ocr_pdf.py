"""
OCR de PDFs escaneados → PDF con capa de texto (OCRmyPDF + Tesseract).

Herramienta documental independiente. Aún no registrada en la UI.
"""

SCRIPT_META = {
    "name": "PDF escaneado a PDF OCR",
    "category": "CONVERSIÓN",
}

import platform
import subprocess
import time
from pathlib import Path
from typing import Callable, Optional, Sequence

from logger import logger
from ui.exceptions import CancelledByUser

from scripts.common.ocr_io import (
    OcrValidationError,
    make_temp_pdf_path,
    promote_temp_to_final,
    resolve_output_path,
    safe_unlink,
    validate_ocr_output,
)
from scripts.common.ocr_runtime import (
    OcrDependencyError,
    assert_command_has_no_ghostscript,
    build_ocr_command,
    build_subprocess_env,
    popen_creationflags,
    redact_process_text,
    require_runtime,
    should_start_new_session,
    summarize_dependency_origins,
)
from scripts.common.results import build_result

ProgressCallback = Callable[[int, int], None]
CancelCallback = Callable[[], bool]

_POLL_INTERVAL_S = 0.1
_TERM_WAIT_S = 5.0


class OcrProcessError(RuntimeError):
    """Fallo técnico del subproceso OCR (mensaje ya redactado)."""

    def __init__(self, category: str, message: str, returncode: Optional[int] = None):
        self.category = category
        self.returncode = returncode
        super().__init__(message)


def _check_cancelled(is_cancelled: Optional[CancelCallback]) -> None:
    if is_cancelled and is_cancelled():
        raise CancelledByUser()


def _select_pdfs_ui() -> list[Path]:
    import tkinter as tk
    from tkinter import filedialog

    from ui.ui_thread import call_ui

    parent = call_ui(lambda: tk._get_default_root())
    paths = call_ui(
        lambda: filedialog.askopenfilenames(
            title="Selecciona uno o varios PDF",
            filetypes=[("PDF", "*.pdf")],
            parent=parent,
        )
    )
    if not paths:
        raise CancelledByUser()

    pdfs = [Path(p) for p in paths if Path(p).suffix.lower() == ".pdf"]
    if not pdfs:
        raise RuntimeError("No se han seleccionado PDF válidos.")
    return pdfs


def _select_output_dir_ui() -> Path:
    import tkinter as tk
    from tkinter import filedialog

    from ui.ui_thread import call_ui

    parent = call_ui(lambda: tk._get_default_root())
    output_dir = call_ui(
        lambda: filedialog.askdirectory(
            title="Selecciona carpeta de destino",
            parent=parent,
        )
    )
    if not output_dir:
        raise CancelledByUser()
    return Path(output_dir)


def _terminate_process_group(proc: subprocess.Popen) -> None:
    """
    Cancelación del proceso OCR y descendientes.

    macOS/Linux: SIGTERM/SIGKILL al process group (start_new_session).
    Windows: terminación del árbol (preparado; no validado en esta fase).
    """
    if proc.poll() is not None:
        return

    system = platform.system()

    if system == "Windows":
        _terminate_windows_tree(proc)
        return

    import os
    import signal

    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.terminate()
        except ProcessLookupError:
            return

    deadline = time.monotonic() + _TERM_WAIT_S
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return
        time.sleep(_POLL_INTERVAL_S)

    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except ProcessLookupError:
            pass

    try:
        proc.wait(timeout=_TERM_WAIT_S)
    except subprocess.TimeoutExpired:
        pass


def _terminate_windows_tree(proc: subprocess.Popen) -> None:
    """
    Finalización controlada en Windows (preparada, no validada).

    Intenta CTRL_BREAK al grupo y, si sigue vivo, taskkill /T.
    """
    import signal

    try:
        proc.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
    except (AttributeError, OSError, ValueError):
        try:
            proc.terminate()
        except OSError:
            pass

    deadline = time.monotonic() + _TERM_WAIT_S
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return
        time.sleep(_POLL_INTERVAL_S)

    # Árbol de procesos: preparado para validación posterior.
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        try:
            proc.kill()
        except OSError:
            pass

    try:
        proc.wait(timeout=_TERM_WAIT_S)
    except subprocess.TimeoutExpired:
        pass


def _normalize_returncode(returncode: Optional[int], stderr: str) -> None:
    """Traduce códigos de OCRmyPDF a errores técnicos controlados."""
    if returncode == 0:
        return

    redacted = redact_process_text(stderr or "")
    category = "ocr_failed"
    message = "OCRmyPDF no pudo completar el OCR."

    if returncode == 2:
        category = "invalid_args"
        message = "Argumentos OCR no válidos."
    elif returncode == 3:
        category = "input_error"
        message = "El PDF de entrada no se pudo procesar."
    elif returncode == 4:
        category = "dependency_error"
        message = "Falta una dependencia externa de OCR."
    elif returncode == 6:
        category = "already_has_text"
        message = "El PDF ya tenía texto y se omitió el OCR (--mode skip)."
    elif returncode is not None and returncode < 0:
        category = "terminated"
        message = "El proceso OCR terminó de forma inesperada."

    if redacted:
        logger.error(
            "[OCR-PDF] Fallo técnico category=%s returncode=%s detail=%s",
            category,
            returncode,
            redacted,
        )
    else:
        logger.error(
            "[OCR-PDF] Fallo técnico category=%s returncode=%s",
            category,
            returncode,
        )

    raise OcrProcessError(category, message, returncode=returncode)


def run_ocrmypdf_process(
    input_pdf: Path,
    temp_output: Path,
    *,
    is_cancelled: Optional[CancelCallback] = None,
    env: Optional[dict] = None,
    command: Optional[list[str]] = None,
) -> tuple[int, float]:
    """
    Ejecuta OCRmyPDF con Popen (shell=False) y soporta cancelación.

    Devuelve (returncode, duration_s).
    Propaga CancelledByUser si se cancela durante la ejecución.
    """
    cmd = command or build_ocr_command(input_pdf, temp_output)
    assert_command_has_no_ghostscript(cmd)

    if env is None:
        _, tesseract, tessdata = require_runtime()
        env = build_subprocess_env(tesseract=tesseract, tessdata=tessdata)

    kwargs: dict = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "env": env,
        "shell": False,
    }

    if should_start_new_session():
        kwargs["start_new_session"] = True

    creationflags = popen_creationflags()
    if creationflags:
        kwargs["creationflags"] = creationflags

    logger.info("[OCR-PDF] Iniciando subproceso OCR (sin rutas ni comando completo)")

    t0 = time.monotonic()
    proc = subprocess.Popen(cmd, **kwargs)

    cancelled = False
    stdout = ""
    stderr = ""

    try:
        while proc.poll() is None:
            if is_cancelled and is_cancelled():
                cancelled = True
                _terminate_process_group(proc)
                break
            time.sleep(_POLL_INTERVAL_S)

        try:
            out_b, err_b = proc.communicate(timeout=30)
            stdout = out_b or ""
            stderr = err_b or ""
        except subprocess.TimeoutExpired:
            _terminate_process_group(proc)
            out_b, err_b = proc.communicate(timeout=10)
            stdout = out_b or ""
            stderr = err_b or ""
    except Exception:
        _terminate_process_group(proc)
        raise

    duration = time.monotonic() - t0

    if cancelled:
        safe_unlink(temp_output)
        logger.info(
            "[OCR-PDF] Cancelado durante OCR duration_s=%.2f returncode=%s",
            duration,
            proc.returncode,
        )
        raise CancelledByUser()

    # Si quedó salida parcial con código distinto de 0, limpiar.
    if proc.returncode not in (0, None) and temp_output.exists():
        # Algunos códigos dejan salida válida; validación posterior decide.
        pass

    _normalize_returncode(proc.returncode, stderr)
    logger.info(
        "[OCR-PDF] Subproceso OK duration_s=%.2f returncode=%s",
        duration,
        proc.returncode,
    )
    # Evitar uso accidental de stdout (puede contener rutas).
    del stdout
    return int(proc.returncode or 0), duration


def process_one_pdf(
    input_pdf: Path,
    output_dir: Path,
    *,
    is_cancelled: Optional[CancelCallback] = None,
    env: Optional[dict] = None,
    ocrmypdf_bin: Optional[Path] = None,
) -> Path:
    """
    OCR de un PDF: temporal → validación → promoción.
    El original no se modifica.
    """
    input_pdf = Path(input_pdf)
    output_dir = Path(output_dir)

    if not input_pdf.is_file():
        raise OcrProcessError("input_missing", "El PDF de entrada no existe.")

    _check_cancelled(is_cancelled)

    temp_path = make_temp_pdf_path(output_dir, input_pdf.stem)
    final_path = resolve_output_path(output_dir, input_pdf.name)

    try:
        cmd = build_ocr_command(input_pdf, temp_path, ocrmypdf_bin=ocrmypdf_bin)
        run_ocrmypdf_process(
            input_pdf,
            temp_path,
            is_cancelled=is_cancelled,
            env=env,
            command=cmd,
        )

        _check_cancelled(is_cancelled)

        validation = validate_ocr_output(input_pdf, temp_path)
        if not validation.ok:
            safe_unlink(temp_path)
            raise OcrValidationError(
                validation.category,
                f"Validación OCR fallida ({validation.category}).",
            )

        promoted = promote_temp_to_final(temp_path, final_path)
        logger.info(
            "[OCR-PDF] Promovido OK pages=%s size_bytes=%s",
            validation.page_count_output,
            validation.size_bytes,
        )
        return promoted

    except CancelledByUser:
        safe_unlink(temp_path)
        raise
    except Exception:
        safe_unlink(temp_path)
        raise


def run(
    progress: Optional[ProgressCallback] = None,
    is_cancelled: Optional[CancelCallback] = None,
    *,
    pdf_paths: Optional[Sequence] = None,
    output_dir: Optional[Path | str] = None,
):
    """
    Punto de entrada DocFlow.

    Si no se pasan pdf_paths / output_dir, solicita selección por UI.
    La cancelación se propaga como CancelledByUser (ScriptRunner → on_cancelled).
    """
    if pdf_paths is None:
        pdfs = _select_pdfs_ui()
    else:
        pdfs = [Path(p) for p in pdf_paths]
        if not pdfs:
            raise CancelledByUser()

    _check_cancelled(is_cancelled)

    if output_dir is None:
        dest = _select_output_dir_ui()
    else:
        dest = Path(output_dir)

    _check_cancelled(is_cancelled)

    if not dest.exists() or not dest.is_dir():
        raise RuntimeError("La carpeta de destino no es válida.")

    total = len(pdfs)
    procesados = 0
    errores = 0

    if progress:
        progress(0, total)

    try:
        ocrmypdf, tesseract, tessdata = require_runtime()
    except OcrDependencyError as exc:
        logger.error(
            "[OCR-PDF] Dependencia ausente category=%s origin_hint=missing",
            exc.category,
        )
        raise RuntimeError(str(exc)) from exc

    env = build_subprocess_env(tesseract=tesseract, tessdata=tessdata)
    origins = summarize_dependency_origins(ocrmypdf, tesseract, tessdata)
    logger.info(
        "[OCR-PDF] Lote total=%s deps=%s",
        total,
        origins,
    )

    for index, pdf in enumerate(pdfs, start=1):
        _check_cancelled(is_cancelled)

        try:
            process_one_pdf(
                pdf,
                dest,
                is_cancelled=is_cancelled,
                env=env,
                ocrmypdf_bin=ocrmypdf.path,
            )
            procesados += 1
        except CancelledByUser:
            logger.info(
                "[OCR-PDF] Cancelado index=%s/%s procesados=%s",
                index,
                total,
                procesados,
            )
            raise
        except (OcrProcessError, OcrValidationError, OcrDependencyError) as exc:
            errores += 1
            category = getattr(exc, "category", "unknown")
            logger.error(
                "[OCR-PDF] Error archivo index=%s/%s category=%s",
                index,
                total,
                category,
            )
        except Exception as exc:
            errores += 1
            logger.error(
                "[OCR-PDF] Error inesperado index=%s/%s type=%s",
                index,
                total,
                type(exc).__name__,
            )

        if progress:
            progress(index, total)

    logger.info(
        "[OCR-PDF] Finalizado procesados=%s errores=%s total=%s",
        procesados,
        errores,
        total,
    )

    return build_result(
        message="Proceso finalizado",
        output_dir=dest,
        total=total,
        procesados=procesados,
        errores=errores,
    )


if __name__ == "__main__":
    run()
