SCRIPT_META = {
    "name": "MBOX a EML",
    "category": "MBOX"
}

import mailbox
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

from email.generator import BytesGenerator
from email.policy import default
from email.header import decode_header

from config import get_ruta
from ui.exceptions import CancelledByUser
from ui.ui_thread import call_ui
from logger import logger

from scripts.common.filenames import resolve_conflict, sanitize_filename_ascii
from scripts.common.results import build_result, build_cancelled_result


def decode_mime(value: str) -> str:
    if not value:
        return ""

    parts = decode_header(value)
    out = []

    for chunk, enc in parts:
        if isinstance(chunk, bytes):
            try:
                out.append(chunk.decode(enc or "utf-8", errors="ignore"))
            except Exception:
                out.append(chunk.decode("latin1", errors="ignore"))
        else:
            out.append(chunk)

    return "".join(out)


def run(progress=None, is_cancelled=None):
    parent = call_ui(lambda: tk._get_default_root())

    mbox_path = call_ui(lambda: filedialog.askopenfilename(
        title="Seleccionar archivo MBOX",
        filetypes=[("Archivos MBOX", "*.mbox")],
        parent=parent
    ))

    if not mbox_path:
        raise CancelledByUser()

    mbox_path = Path(mbox_path)

    base_dir_raw = get_ruta("mbox")
    if not base_dir_raw:
        raise RuntimeError(
            "Ruta de trabajo MBOX no válida.\n"
            "Selecciona primero una carpeta de trabajo."
        )

    base_dir = Path(base_dir_raw)
    if not base_dir.is_dir():
        raise RuntimeError(
            "Ruta de trabajo MBOX no válida.\n"
            "Selecciona primero una carpeta de trabajo."
        )

    output_dir = base_dir / "EML_extraidos"
    output_dir.mkdir(exist_ok=True)

    logger.info(f"[MBOX-EML] Procesando archivo: {mbox_path}")

    try:
        mbox = mailbox.mbox(mbox_path)
    except Exception:
        raise RuntimeError(
            "No se pudo abrir el archivo MBOX. "
            "Puede estar dañado, en uso o no ser un MBOX válido."
        )

    total = len(mbox)
    extraidos = 0
    errores = 0

    try:

        for i, msg in enumerate(mbox, start=1):

            if is_cancelled and is_cancelled():
                raise CancelledByUser()

            try:
                subject_raw = msg.get("subject", "") or ""
                subject = decode_mime(subject_raw)
                safe_name = sanitize_filename_ascii(
                    subject,
                    max_len=90,
                    fallback="sin_asunto"
                )

                eml_path = resolve_conflict(
                    output_dir / f"{safe_name}.eml",
                    pattern="_{i}"
                )

                with eml_path.open("wb") as f:
                    gen = BytesGenerator(f, policy=default)
                    gen.flatten(msg)

                extraidos += 1

            except Exception as e:
                errores += 1
                logger.error(f"[MBOX-EML] Error en mensaje {i}: {e}")
                continue

            if progress:
                progress(i, total)

    except CancelledByUser:
        logger.info("[MBOX-EML] Cancelado por usuario")
        return build_cancelled_result(
            output_dir=output_dir,
            total=total,
            procesados=extraidos,
            errores=errores,
        )

    if extraidos == 0:
        raise RuntimeError("No se pudo extraer ningún EML del archivo MBOX.")

    omitidos = total - extraidos - errores

    logger.info(
        f"[MBOX-EML] Finalizado. Procesados: {extraidos} de {total}. "
        f"Errores: {errores}. Omitidos: {omitidos}"
    )

    return build_result(
        message="Proceso finalizado",
        output_dir=output_dir,
        total=total,
        procesados=extraidos,
        errores=errores,
        omitidos=omitidos,
    )