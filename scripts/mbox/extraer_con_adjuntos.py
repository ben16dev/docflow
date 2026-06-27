SCRIPT_META = {
    "name": "Extraer adjuntos de MBOX",
    "category": "MBOX"
}

import mailbox
from pathlib import Path
from datetime import datetime
from email.header import decode_header
from email.utils import parsedate_to_datetime, parseaddr
from email import policy
from email.parser import BytesParser

import tkinter as tk
from tkinter import filedialog

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm

from config import get_ruta
from ui.exceptions import CancelledByUser
from ui.ui_thread import call_ui
from logger import logger

from scripts.common.filenames import resolve_conflict, sanitize_filename
from scripts.common.results import build_result, build_cancelled_result


# ======================================================
# UTILIDADES BÁSICAS
# ======================================================

def _decode_mime(value):
    if not value:
        return ""

    parts = decode_header(value)
    out = []

    for chunk, enc in parts:
        if isinstance(chunk, bytes):
            out.append(chunk.decode(enc or "utf-8", errors="ignore"))
        else:
            out.append(str(chunk))

    return "".join(out).strip()


def _format_date(dt):
    return f"{dt.day:02d}.{dt.month:02d}.{dt.year}"


def _strip_html(s):
    import re
    return re.sub(r"<[^>]+>", " ", s or "")


# ======================================================
# CUERPO DEL CORREO
# ======================================================

def _extract_body(msg):
    """
    Devuelve el texto visible del correo (prefiere text/plain;
    si no hay, limpia el HTML).
    """

    text_body = ""
    html_body = ""

    if msg.is_multipart():
        for part in msg.walk():
            if part.is_multipart():
                continue
            if part.get_filename():
                continue

            ctype = (part.get_content_type() or "").lower()
            payload = part.get_payload(decode=True) or b""
            cs = part.get_content_charset()

            try:
                content = payload.decode(cs or "utf-8", errors="ignore")
            except Exception:
                content = payload.decode("latin1", errors="ignore")

            if ctype == "text/plain" and not text_body:
                text_body = content
            elif ctype == "text/html" and not html_body:
                html_body = content
    else:
        payload = msg.get_payload(decode=True) or b""
        cs = msg.get_content_charset()

        try:
            text_body = payload.decode(cs or "utf-8", errors="ignore")
        except Exception:
            text_body = payload.decode("latin1", errors="ignore")

    text_visible = text_body.strip()

    if not text_visible and html_body.strip():
        text_visible = _strip_html(html_body)

    if not text_visible.strip():
        text_visible = "(Sin contenido)"

    return text_visible


# ======================================================
# ADJUNTOS: ITERADORES Y GUARDADO
# ======================================================

def _iter_attachment_parts(msg):
    """
    Itera por partes que parecen ser adjuntos reales:
    no multipart, con filename o name en Content-Type.
    """

    for part in msg.walk():
        if part.is_multipart():
            continue

        filename = part.get_filename()
        name_ct = part.get_param("name", header="Content-Type")

        if not filename and not name_ct:
            continue

        yield part, filename, name_ct


def _save_attachments(msg, folder):
    counter = 1

    for part, filename, name_ct in _iter_attachment_parts(msg):
        payload = part.get_payload(decode=True) or b""
        if not payload:
            continue

        if filename:
            filename = sanitize_filename(
                _decode_mime(filename),
                max_len=150,
                fallback="SIN_NOMBRE"
            )
            ext = Path(filename).suffix
        else:
            name_ct = sanitize_filename(
                _decode_mime(name_ct),
                max_len=150,
                fallback="SIN_NOMBRE"
            )
            ext = Path(name_ct).suffix or ".bin"

        if not ext:
            ext = ".bin"

        save_path = resolve_conflict(
            folder / f"Doc_Adjunto_{counter:02d}{ext}",
            pattern="_{i}"
        )
        save_path.write_bytes(payload)

        counter += 1


# ======================================================
# PDF DEL CORREO
# ======================================================

def _render_email_to_pdf(
    output_pdf_path,
    subject,
    from_h,
    to_h,
    date_str,
    body_text
):
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "EmailTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        spaceAfter=8,
    )

    meta_style = ParagraphStyle(
        "EmailMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        spaceAfter=6,
    )

    body_style = ParagraphStyle(
        "EmailBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        spaceAfter=10,
    )

    doc = SimpleDocTemplate(
        str(output_pdf_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    def esc(s):
        s = s or ""
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return s

    story = []
    story.append(Paragraph(f"Asunto: {esc(subject)}", title_style))
    story.append(Paragraph(f"De: {esc(from_h)}", meta_style))
    story.append(Paragraph(f"Para: {esc(to_h)}", meta_style))
    story.append(Paragraph(f"Fecha: {esc(date_str)}", meta_style))
    story.append(Spacer(1, 10))

    body_text = body_text or "(Sin contenido)"

    for line in body_text.splitlines():
        line = line.strip()
        if not line:
            story.append(Spacer(1, 8))
        else:
            story.append(Paragraph(esc(line), body_style))

    doc.build(story)


# ======================================================
# NOMBRE DE CARPETA
# ======================================================

def _build_folder_name(date_str, subject, sender_visible, index):
    """
    Organiza cada mensaje en una carpeta por fecha y asunto seguro.
    Si el asunto no aporta un identificador útil, usa el remitente.
    """

    subject_part = sanitize_filename(
        subject or "SIN_ASUNTO",
        max_len=80,
        fallback="SIN_ASUNTO",
    )

    if subject_part in {"SIN_ASUNTO", "(Sin asunto)"}:
        identifier = sender_visible or f"mensaje_{index:04d}"
    else:
        identifier = subject_part

    return sanitize_filename(
        f"{date_str}_{identifier}",
        max_len=150,
        fallback=f"{date_str}_mensaje_{index:04d}",
    )


# ======================================================
# RUN
# ======================================================

def run(progress=None, is_cancelled=None):
    parent = call_ui(lambda: tk._get_default_root())
    ruta_base = get_ruta("mbox")

    mbox_path = call_ui(lambda: filedialog.askopenfilename(
        parent=parent,
        title="Selecciona archivo MBOX",
        initialdir=ruta_base,
        filetypes=[("MBOX", "*.mbox")]
    ))

    if not mbox_path:
        raise CancelledByUser()

    if not ruta_base:
        raise RuntimeError(
            "Ruta de trabajo MBOX no válida.\n"
            "Selecciona primero una carpeta de trabajo."
        )

    mbox_path = Path(mbox_path)
    salida_base = Path(ruta_base) / "MBOX_extraidos"
    salida_base.mkdir(exist_ok=True)

    logger.info(f"[MBOX] Procesando archivo: {mbox_path}")

    try:
        mbox = mailbox.mbox(mbox_path)
    except Exception:
        raise RuntimeError(
            "No se pudo abrir el archivo MBOX. "
            "Puede estar dañado, en uso o no ser un MBOX válido."
        )

    total = len(mbox)
    procesados = 0
    errores = 0

    try:

        for i, msg_raw in enumerate(mbox, start=1):

            if is_cancelled and is_cancelled():
                raise CancelledByUser()

            try:
                msg = BytesParser(policy=policy.default).parsebytes(
                    msg_raw.as_bytes()
                )

                subject = (
                    _decode_mime(msg.get("subject", ""))
                    or "(Sin asunto)"
                )

                sender_name, sender_email = parseaddr(msg.get("from", ""))
                sender_visible = sanitize_filename(
                    _decode_mime(sender_name)
                    or sender_email
                    or "SIN_REMITENTE",
                    max_len=60,
                    fallback="SIN_REMITENTE"
                ).replace(" ", "_")

                to_h = _decode_mime(msg.get("to", ""))

                try:
                    dt = parsedate_to_datetime(msg.get("date"))
                except Exception:
                    dt = datetime.now()

                date_str = _format_date(dt)
                body_visible = _extract_body(msg)

                folder_name = _build_folder_name(
                    date_str, subject, sender_visible, i
                )
                folder_path = resolve_conflict(
                    salida_base / folder_name,
                    pattern="_{i}"
                )
                folder_path.mkdir(parents=True, exist_ok=True)

                pdf_path = resolve_conflict(
                    folder_path / f"{date_str}_Correo_electronico.pdf",
                    pattern="_{i}"
                )
                _render_email_to_pdf(
                    pdf_path,
                    subject,
                    sender_visible,
                    to_h,
                    date_str,
                    body_visible
                )

                eml_path = resolve_conflict(
                    folder_path / "correo.eml",
                    pattern="_{i}"
                )
                eml_path.write_bytes(msg_raw.as_bytes())

                _save_attachments(msg, folder_path)

                procesados += 1

            except Exception as e:
                errores += 1
                logger.error(f"[MBOX] Error en correo {i}: {e}")
                continue

            if progress:
                progress(i, total)

    except CancelledByUser:
        logger.info("[MBOX] Cancelado por el usuario")
        return build_cancelled_result(
            output_dir=salida_base,
            total=total,
            procesados=procesados,
            errores=errores,
        )

    logger.info(
        f"[MBOX] Finalizado. Procesados: {procesados}/{total}. "
        f"Errores: {errores}."
    )

    return build_result(
        message="Proceso finalizado",
        output_dir=salida_base,
        total=total,
        procesados=procesados,
        errores=errores,
    )
