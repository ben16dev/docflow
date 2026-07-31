"""
OCR de PDFs escaneados → PDF con capa de texto (OCRmyPDF + Tesseract).

Herramienta documental independiente. Registrada en la pestaña CONVERSIÓN.
"""

SCRIPT_META = {
    "name": "PDF escaneado a PDF OCR",
    "category": "CONVERSIÓN",
}

import platform
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal, Optional, Sequence

from logger import logger
from ui.exceptions import CancelledByUser

from scripts.common.ocr_io import (
    OcrValidationError,
    assert_final_in_destination,
    assert_output_not_source,
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


@dataclass(frozen=True)
class OCRFileResult:
    source: Path
    status: Literal["processed", "skipped", "error", "cancelled"]
    output_path: Optional[Path] = None
    error_code: Optional[str] = None

    def __fspath__(self) -> str:
        if self.output_path is None:
            raise TypeError("OCRFileResult no tiene output_path")
        return str(self.output_path)

    def __getattr__(self, name: str):
        if self.output_path is None:
            raise AttributeError(name)
        return getattr(self.output_path, name)

    def __eq__(self, other) -> bool:
        if isinstance(other, OCRFileResult):
            return (
                self.source == other.source
                and self.status == other.status
                and self.output_path == other.output_path
                and self.error_code == other.error_code
            )
        if self.output_path is not None and isinstance(other, (str, Path)):
            return self.output_path == Path(other)
        return False


class OcrProcessError(RuntimeError):
    """Fallo técnico del subproceso OCR (mensaje ya redactado)."""

    def __init__(self, category: str, message: str, returncode: Optional[int] = None):
        self.category = category
        self.returncode = returncode
        super().__init__(message)


class OcrBatchCancelled(CancelledByUser):
    """Cancelación con resultado estructurado del lote OCR."""

    def __init__(self, result: dict):
        self.result = result
        super().__init__("Cancelado")


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
) -> OCRFileResult:
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
    promoted: Optional[Path] = None

    assert_output_not_source(temp_path, input_pdf)
    assert_output_not_source(final_path, input_pdf)

    try:
        cmd = build_ocr_command(input_pdf, temp_path, ocrmypdf_bin=ocrmypdf_bin)
        try:
            run_ocrmypdf_process(
                input_pdf,
                temp_path,
                is_cancelled=is_cancelled,
                env=env,
                command=cmd,
            )
        except OcrProcessError as exc:
            if exc.category == "already_has_text":
                safe_unlink(temp_path)
                return OCRFileResult(
                    source=input_pdf,
                    status="skipped",
                    error_code=exc.category,
                )
            raise

        _check_cancelled(is_cancelled)

        validation = validate_ocr_output(input_pdf, temp_path)
        if not validation.ok:
            safe_unlink(temp_path)
            raise OcrValidationError(
                validation.category,
                f"Validación OCR fallida ({validation.category}).",
            )

        promoted = promote_temp_to_final(temp_path, final_path)
        assert_output_not_source(promoted, input_pdf)
        promoted = assert_final_in_destination(promoted, output_dir)
        final_validation = validate_ocr_output(input_pdf, promoted)
        if not final_validation.ok:
            raise OcrValidationError(
                final_validation.category,
                f"Validación OCR final fallida ({final_validation.category}).",
            )
        logger.info(
            "[OCR-PDF] Promovido OK pages=%s size_bytes=%s "
            "final_exists=True final_in_destination=True",
            final_validation.page_count_output,
            final_validation.size_bytes,
        )
        return OCRFileResult(
            source=input_pdf,
            status="processed",
            output_path=promoted,
        )

    except CancelledByUser:
        if promoted is None:
            safe_unlink(temp_path)
        return OCRFileResult(source=input_pdf, status="cancelled")
    except Exception:
        # No borrar un final ya promovido: solo el temporal si sigue existiendo.
        if promoted is None:
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
    omitidos = 0
    files: list[Path] = []
    seen_outputs: set[Path] = set()
    accepted_outputs: list[tuple[Path, Path]] = []
    error_details: list[str] = []

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
        try:
            _check_cancelled(is_cancelled)
            raw_result = process_one_pdf(
                pdf,
                dest,
                is_cancelled=is_cancelled,
                env=env,
                ocrmypdf_bin=ocrmypdf.path,
            )
            file_result = _coerce_file_result(pdf, raw_result)

            if file_result.status == "cancelled":
                logger.info(
                    "[OCR-PDF] Cancelado index=%s/%s procesados=%s omitidos=%s errores=%s",
                    index,
                    total,
                    procesados,
                    omitidos,
                    errores,
                )
                raise OcrBatchCancelled(
                    _build_cancelled_ocr_result(
                        dest=dest,
                        total=total,
                        procesados=procesados,
                        errores=errores,
                        omitidos=omitidos,
                        files=files,
                    )
                )

            if file_result.status == "skipped":
                omitidos += 1
                logger.info(
                    "[OCR-PDF] Omitido index=%s/%s category=%s",
                    index,
                    total,
                    file_result.error_code or "skipped",
                )
                continue

            if file_result.status != "processed" or file_result.output_path is None:
                raise OcrValidationError(
                    file_result.error_code or "invalid_file_result",
                    "Resultado OCR de archivo inválido.",
                )

            final_path = _validate_final_output_for_counting(
                file_result.source,
                file_result.output_path,
                dest,
                seen_outputs,
            )
            files.append(final_path)
            accepted_outputs.append((file_result.source, final_path))
            seen_outputs.add(final_path.resolve())
            procesados += 1
            logger.info(
                "[OCR-PDF] Aceptado index=%s/%s final_exists=True "
                "final_in_destination=True",
                index,
                total,
            )
        except CancelledByUser as exc:
            if isinstance(exc, OcrBatchCancelled):
                raise
            logger.info(
                "[OCR-PDF] Cancelado index=%s/%s procesados=%s omitidos=%s errores=%s",
                index,
                total,
                procesados,
                omitidos,
                errores,
            )
            raise OcrBatchCancelled(
                _build_cancelled_ocr_result(
                    dest=dest,
                    total=total,
                    procesados=procesados,
                    errores=errores,
                    omitidos=omitidos,
                    files=files,
                )
            )
        except (OcrProcessError, OcrValidationError, OcrDependencyError) as exc:
            errores += 1
            category = getattr(exc, "category", "unknown")
            error_details.append(f"archivo {index}: {category}")
            logger.error(
                "[OCR-PDF] Error archivo index=%s/%s category=%s",
                index,
                total,
                category,
            )
        except Exception as exc:
            errores += 1
            error_details.append(f"archivo {index}: {type(exc).__name__}")
            logger.error(
                "[OCR-PDF] Error inesperado index=%s/%s type=%s",
                index,
                total,
                type(exc).__name__,
            )

        if progress:
            progress(index, total)

    final_files: list[Path] = []
    final_seen_outputs: set[Path] = set()
    input_paths: set[Path] = set()
    for pdf in pdfs:
        try:
            input_paths.add(Path(pdf).resolve())
        except OSError:
            input_paths.add(Path(pdf).absolute())

    final_failures = 0
    for index, (source, output_path) in enumerate(accepted_outputs, start=1):
        try:
            final_path = assert_final_in_destination(output_path, dest)
            assert_output_not_source(final_path, source)
            resolved = final_path.resolve()
            if resolved in input_paths:
                raise OcrValidationError(
                    "output_matches_source",
                    "La salida OCR coincide con un PDF de entrada.",
                )
            if resolved in final_seen_outputs:
                raise OcrValidationError(
                    "duplicate_output",
                    "Dos documentos apuntan al mismo resultado OCR.",
                )
            validation = validate_ocr_output(source, final_path)
            if not validation.ok:
                raise OcrValidationError(
                    validation.category,
                    f"Validación OCR final fallida ({validation.category}).",
                )
        except (OcrValidationError, OSError) as exc:
            final_failures += 1
            category = getattr(exc, "category", type(exc).__name__)
            error_details.append(f"lote archivo {index}: {category}")
            logger.error(
                "[OCR-PDF] Discrepancia final index=%s/%s category=%s",
                index,
                len(accepted_outputs),
                category,
            )
            continue

        final_files.append(final_path)
        final_seen_outputs.add(resolved)

    files = final_files
    if (
        final_failures
        or len(files) != procesados
        or len(final_seen_outputs) != procesados
    ):
        logger.error(
            "[OCR-PDF] Discrepancia category=files_missing "
            "procesados=%s finales=%s rutas_unicas=%s",
            procesados,
            len(files),
            len(final_seen_outputs),
        )
        errores += final_failures or max(procesados - len(files), 1)
        if not final_failures:
            error_details.append("lote: inconsistent_generated_files")
        procesados = len(files)

    counted = procesados + errores + omitidos
    if counted != total:
        delta = total - counted
        logger.error(
            "[OCR-PDF] Discrepancia category=count_mismatch "
            "total=%s procesados=%s errores=%s omitidos=%s",
            total,
            procesados,
            errores,
            omitidos,
        )
        if delta > 0:
            errores += delta
            error_details.append("lote: count_mismatch")

    logger.info(
        "[OCR-PDF] Finalizado procesados=%s errores=%s omitidos=%s total=%s finales=%s",
        procesados,
        errores,
        omitidos,
        total,
        len(files),
    )

    if total > 0 and procesados == 0:
        message = (
            "No se generó ningún PDF OCR válido"
            if errores or omitidos
            else "Proceso finalizado sin resultados"
        )
    elif errores > 0 or omitidos > 0:
        message = (
            "Proceso finalizado con incidencias"
        )
    else:
        message = "Proceso finalizado correctamente"

    return build_result(
        message=message,
        output_dir=dest,
        total=total,
        procesados=procesados,
        errores=errores,
        omitidos=omitidos,
        files=files,
        detalles=error_details,
    )


def _path_is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _validate_final_output_for_counting(
    source: Path,
    output_path: Path,
    output_dir: Path,
    seen_outputs: set[Path],
) -> Path:
    final_path = assert_final_in_destination(output_path, output_dir)
    assert_output_not_source(final_path, source)

    if final_path.name.startswith(".docflow_ocr_"):
        raise OcrValidationError(
            "temporary_output",
            "El resultado final OCR sigue siendo un temporal.",
        )

    resolved = final_path.resolve()
    if resolved in seen_outputs:
        raise OcrValidationError(
            "duplicate_output",
            "Dos documentos apuntan al mismo resultado OCR.",
        )

    validation = validate_ocr_output(source, final_path)
    if not validation.ok:
        raise OcrValidationError(
            validation.category,
            f"Validación OCR final fallida ({validation.category}).",
        )

    return final_path


def _coerce_file_result(source: Path, result) -> OCRFileResult:
    if isinstance(result, OCRFileResult):
        return result
    if result is None:
        return OCRFileResult(
            source=Path(source),
            status="error",
            error_code="empty_file_result",
        )
    if isinstance(result, (str, Path)):
        return OCRFileResult(
            source=Path(source),
            status="processed",
            output_path=Path(result),
        )
    return OCRFileResult(
        source=Path(source),
        status="error",
        error_code="invalid_file_result",
    )


def _build_cancelled_ocr_result(
    *,
    dest: Path,
    total: int,
    procesados: int,
    errores: int,
    omitidos: int,
    files: Sequence[Path],
) -> dict:
    pending = max(total - procesados - errores - omitidos, 0)
    omitidos_final = omitidos + pending
    return build_result(
        message="Cancelado",
        output_dir=dest,
        total=total,
        procesados=procesados,
        errores=errores,
        omitidos=omitidos_final,
        files=_unique_existing_files_in_destination(files, dest),
        cancelled=True,
    )


def _unique_existing_files_in_destination(files: Sequence[Path], output_dir: Path) -> list[Path]:
    unique: list[Path] = []
    seen: set[Path] = set()
    for file_path in files:
        path = Path(file_path)
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        if path.is_file() and _path_is_relative_to(resolved, output_dir.resolve()):
            unique.append(path)
            seen.add(resolved)
    return unique


if __name__ == "__main__":
    run()
