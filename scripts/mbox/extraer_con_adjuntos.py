SCRIPT_META = {
    "name": "Extraer con adjuntos",
    "category": "MBOX"
}

import re
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
# CONSTANTES
# ======================================================

PREFIJOS_EXPEDIENTE = [
    "GHN", "GHCS", "CSGH", "GH", "CS", "IM",
    "COMAP", "RA", "365/360", "VIV", "NVIV",
    "PIAS", "CARTCAM"
]

_PREF_PATTERN = "|".join(re.escape(p) for p in PREFIJOS_EXPEDIENTE)

_EXPEDIENTE_RE = re.compile(
    rf"\b({_PREF_PATTERN})[\s\-_\/]*?(\d{{4}})[\s\-_\/]*?(\d+)\b"
)


# ------------------------------------------------------
# Regex para detectar al cliente en texto libre.
# Ancla: "en nombre de" / "en representación de".
# Captura 2-6 tokens con inicial mayúscula, admite
# partículas (de, del, de la, de los, de las, y).
# ------------------------------------------------------

_NAME_TOKEN = r"[A-ZÁÉÍÓÚÜÑ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ'\-]+"

_PARTICLE = r"(?:(?i:de\s+(?:la\s+|los\s+|las\s+)?|del\s+|y\s+))"

_NAME = (
    _NAME_TOKEN
    + r"(?:\s+(?:" + _PARTICLE + r")?" + _NAME_TOKEN + r"){1,5}"
)

_ANCHOR = r"(?i:en\s+nombre\s+de|en\s+representaci[oó]n\s+de)"

_FILLER = (
    r"(?:(?i:mi|su|el|la|nuestro|nuestra|este|esta)\s+"
    r"(?i:cliente|mandante|representado|representada|"
    r"defendido|defendida|patrocinad[oa])\s+)?"
    r"(?:(?i:D\.?ª?|Don|Do[ñn]a)\s+)?"
)

_STOP = (
    r"(?=\s*(?:[,;:\(\)\.\"]|"
    r"(?i:\bcon\b|\ben\s|\bmayor\b|\bvecin[oa]\b|"
    r"\bDNI\b|\bNIE\b|\bNIF\b|\bnacido[a]?\b)|"
    r"(?!(?i:de|del|y|i)\b)[a-záéíóúüñ]|"
    r"$))"
)

_CLIENTE_RE = re.compile(
    _ANCHOR + r"\s+" + _FILLER + r"(" + _NAME + r")" + _STOP
)


# Stop list: si el candidato contiene cualquiera de
# estos tokens, se considera entidad y se descarta.
_ENTITY_RE = re.compile(
    r"\b("
    r"S\.?\s?A\.?|S\.?\s?L\.?\s?U?\.?|S\.?\s?C\.?|"
    r"Banco|Caja|Aseguradora|Compa[ñn][ií]a|Sociedad|"
    r"Mutua|Cooperativa|Entidad|Asociaci[oó]n|"
    r"Fundaci[oó]n|Ltd|Limited|Inc|Corp|"
    r"Holding|Grupo|Group|Iberdrola|Endesa|Naturgy|"
    r"Repsol|Telef[oó]nica|Vodafone|Movistar|Orange|"
    r"Santander|BBVA|Sabadell|Bankinter|Bankia|"
    r"Caixa|Unicaja|Ibercaja|Liberbank|Abanca|Kutxabank|"
    r"Mapfre|Mutualidad|Adif|Renfe|Aena|Iberia"
    r")\b",
    re.IGNORECASE
)


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


def _normalize_spaces(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def _strip_html(s):
    return re.sub(r"<[^>]+>", " ", s or "")


# ======================================================
# DETECCIÓN EXPEDIENTE
# ======================================================

def _detect_expediente(subject):
    if not subject:
        return None

    m = _EXPEDIENTE_RE.search(subject.upper())
    if not m:
        return None

    pref, year, num = m.groups()
    return f"{pref}_{year}_{num}"


# ======================================================
# DETECCIÓN CLIENTE
# ======================================================

def _looks_like_entity(name):
    return bool(_ENTITY_RE.search(name or ""))


def _extract_cliente_from_text(text):
    """
    Busca el primer candidato a cliente en `text` usando
    las anclas 'en nombre de' / 'en representación de'.

    Descarta candidatos que parezcan entidades jurídicas.
    """

    if not text:
        return None

    norm = _normalize_spaces(text)

    for m in _CLIENTE_RE.finditer(norm):
        candidate = _normalize_spaces(m.group(1))

        if not candidate:
            continue

        if _looks_like_entity(candidate):
            continue

        tokens = candidate.split()

        if len(tokens) < 2:
            continue

        # Cada token debe empezar con mayúscula, salvo
        # partículas (que se aceptan en minúscula).
        if not all(
            t[:1].isupper()
            or t.lower() in {"de", "del", "la", "las", "los", "y"}
            for t in tokens
        ):
            continue

        return candidate

    return None


# ======================================================
# EXTRACCIÓN DE TEXTO DE PDF
# ======================================================

def _extract_text_from_pdf_bytes(pdf_bytes):
    """
    Extrae texto de un PDF en bytes.

    1) PyMuPDF (rápido).
    2) pdfplumber (fallback más lento).

    Devuelve "" si nada extrae texto utilizable.
    """

    from io import BytesIO

    try:
        import fitz

        chunks = []
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        try:
            for page in doc:
                t = page.get_text() or ""
                if t.strip():
                    chunks.append(t)
        finally:
            doc.close()

        text = "\n".join(chunks).strip()
        if text:
            return text

    except Exception as e:
        logger.warning(f"[MBOX] PyMuPDF falló: {e}")

    try:
        import pdfplumber

        chunks = []
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ""
                if t.strip():
                    chunks.append(t)

        return "\n".join(chunks).strip()

    except Exception as e:
        logger.warning(f"[MBOX] pdfplumber falló: {e}")
        return ""


# ======================================================
# CUERPO DEL CORREO
# ======================================================

def _extract_bodies(msg):
    """
    Devuelve (text_visible, text_busqueda):
      - text_visible: lo que se pinta en el PDF del correo
        (prefiere text/plain, si no hay limpia el html).
      - text_busqueda: texto unificado para regex
        (text/plain + html limpio).
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

    search_text = " ".join(
        filter(None, [text_body, _strip_html(html_body)])
    )

    return text_visible, search_text


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


def _detect_cliente(msg, search_text):
    """
    Busca al cliente:
      1) En cada PDF adjunto (en orden de aparición).
      2) Si no encuentra, en el cuerpo del correo.
    """

    for part, filename, name_ct in _iter_attachment_parts(msg):
        ref_name = _decode_mime(filename or name_ct)
        ext = Path(ref_name).suffix.lower()

        if ext != ".pdf":
            continue

        payload = part.get_payload(decode=True) or b""
        if not payload:
            continue

        try:
            pdf_text = _extract_text_from_pdf_bytes(payload)
        except Exception as e:
            logger.warning(f"[MBOX] Error extrayendo PDF: {e}")
            continue

        if not pdf_text:
            continue

        cliente = _extract_cliente_from_text(pdf_text)
        if cliente:
            return cliente

    cliente = _extract_cliente_from_text(search_text)
    if cliente:
        return cliente

    return None


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
        "EDV_Title",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        spaceAfter=8,
    )

    meta_style = ParagraphStyle(
        "EDV_Meta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        spaceAfter=6,
    )

    body_style = ParagraphStyle(
        "EDV_Body",
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

def _build_folder_name(date_str, expediente, cliente, sender_visible):
    """
    Prioridad:
      1) fecha + expediente
      2) fecha + cliente
      3) fecha + SIN_IDENTIFICAR + remitente
    """

    if expediente:
        identifier = expediente

    elif cliente:
        identifier = cliente.replace(" ", "_")

    else:
        identifier = f"SIN_IDENTIFICAR_{sender_visible}"

    return sanitize_filename(
        f"{date_str}_{identifier}",
        max_len=150,
        fallback=f"{date_str}_SIN_IDENTIFICAR"
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
    con_expediente = 0
    con_cliente = 0
    sin_identificar = 0

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

                # 1) Expediente desde el asunto
                expediente = _detect_expediente(subject)

                # 2) Cliente solo si no hay expediente
                body_visible, search_text = _extract_bodies(msg)

                cliente = None
                if not expediente:
                    cliente_raw = _detect_cliente(msg, search_text)
                    if cliente_raw:
                        cliente = sanitize_filename(
                            cliente_raw,
                            max_len=80,
                            fallback=""
                        ) or None

                # Contadores
                if expediente:
                    con_expediente += 1
                elif cliente:
                    con_cliente += 1
                else:
                    sin_identificar += 1

                # 3) Carpeta destino
                folder_name = _build_folder_name(
                    date_str, expediente, cliente, sender_visible
                )
                folder_path = salida_base / folder_name
                folder_path.mkdir(exist_ok=True)

                # 4) PDF del correo
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

                # 5) .eml original
                eml_path = resolve_conflict(
                    folder_path / "correo.eml",
                    pattern="_{i}"
                )
                eml_path.write_bytes(msg_raw.as_bytes())

                # 6) Adjuntos
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
        f"Expediente: {con_expediente}. "
        f"Cliente: {con_cliente}. "
        f"Sin identificar: {sin_identificar}. "
        f"Errores: {errores}."
    )

    return build_result(
        message="Proceso finalizado",
        output_dir=salida_base,
        total=total,
        procesados=procesados,
        errores=errores,
        con_expediente=con_expediente,
        con_cliente=con_cliente,
        sin_identificar=sin_identificar,
    )
