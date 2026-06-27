SCRIPT_META = {
    "name": "EML a PDF",
    "category": "EML"
}
 
import re
import html as html_lib
import tempfile
import subprocess
import shutil
from pathlib import Path
 
from email import policy
from email.parser import BytesParser
from email.header import decode_header
 
from config import get_ruta
from ui.exceptions import CancelledByUser
from logger import logger
 
from scripts.common.filenames import resolve_conflict, sanitize_filename
from scripts.common.results import build_result, build_cancelled_result
 
 
# -------------------------------------------------
# Chrome / Edge autodetect (Windows)
# -------------------------------------------------
_CHROME_CACHE = None
 
 
def _find_chrome_exe() -> str:
    global _CHROME_CACHE
    if _CHROME_CACHE:
        return _CHROME_CACHE
 
    p = shutil.which("chrome") or shutil.which("chrome.exe")
    if p:
        _CHROME_CACHE = p
        return p
 
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
 
    for c in candidates:
        if Path(c).exists():
            _CHROME_CACHE = c
            return c
 
    raise RuntimeError(
        "No se encontró Google Chrome ni Microsoft Edge. "
        "Es necesario tener uno de ellos instalado para convertir EML a PDF."
    )
 
 
# -------------------------------------------------
# Utilidades MIME / HTML
# -------------------------------------------------
 
def _decode_mime_header(value):
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
 
 
def _sanitize_filename(name, max_length=150):
    """
    Wrapper local para mantener compatibilidad interna.
    """
    name = _decode_mime_header(name or "")
    return sanitize_filename(
        name,
        max_len=max_length,
        fallback="correo"
    )
 
 
def _force_utf8_html(html):
    if not isinstance(html, str):
        html = str(html)
 
    html = re.sub(
        r'(?i)(<meta\s+charset\s*=\s*)([\'"]?)[^\'">\s]+(\2)',
        r'\1"utf-8"',
        html
    )
 
    if "<head" not in html.lower():
        html = (
            '<!DOCTYPE html>'
            '<html><head><meta charset="utf-8"></head>'
            f'<body>{html}</body></html>'
        )
 
    return html
 
 
def _format_size(num_bytes):
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.1f} MB"
 
 
def _extract_attachments_info(msg):
    """
    Devuelve una lista de dicts con los adjuntos del correo:
    nombre, tipo MIME, tamaño e indicador de si va insertado
    en el cuerpo (inline, p. ej. imágenes de firma).
    """
    adjuntos = []
 
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
 
        filename = part.get_filename()
        disposition = part.get_content_disposition()
 
        if disposition != "attachment" and not filename:
            continue
 
        try:
            payload = part.get_payload(decode=True) or b""
        except Exception:
            payload = b""
 
        adjuntos.append({
            "nombre": _decode_mime_header(filename) or "(sin nombre)",
            "tipo": part.get_content_type(),
            "tamano": _format_size(len(payload)),
            "inline": disposition == "inline",
        })
 
    return adjuntos
 
 
def _build_attachments_html(adjuntos):
    if not adjuntos:
        return "<p><strong>Adjuntos:</strong> Sin adjuntos</p>"
 
    items = []
    for a in adjuntos:
        nota = " <em>(insertado en el cuerpo)</em>" if a["inline"] else ""
        items.append(
            f"<li>{html_lib.escape(a['nombre'])} "
            f"&mdash; {html_lib.escape(a['tipo'])} "
            f"&mdash; {a['tamano']}{nota}</li>"
        )
 
    return (
        f"<p><strong>Adjuntos ({len(adjuntos)}):</strong></p>"
        f"<ul style='margin-top:0;'>{''.join(items)}</ul>"
    )
 
 
def _extract_html(msg):
    subject = _decode_mime_header(msg.get("subject", "Sin asunto"))
    sender = _decode_mime_header(msg.get("from", ""))
    recipient = _decode_mime_header(msg.get("to", ""))
    date = _decode_mime_header(msg.get("date", ""))
 
    html_body = ""
    text_body = ""
 
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
 
            # Los adjuntos no forman parte del cuerpo del correo.
            # Sin este filtro, un adjunto .html podía tomarse como cuerpo.
            if part.get_content_disposition() == "attachment":
                continue
 
            payload = part.get_payload(decode=True) or b""
            cs = part.get_content_charset() or "utf-8"
 
            if ctype == "text/html" and not html_body:
                html_body = payload.decode(cs, errors="ignore")
            elif ctype == "text/plain" and not text_body:
                text_body = payload.decode(cs, errors="ignore")
    else:
        payload = msg.get_payload(decode=True) or b""
        cs = msg.get_content_charset() or "utf-8"
 
        if msg.get_content_type() == "text/html":
            html_body = payload.decode(cs, errors="ignore")
        else:
            text_body = payload.decode(cs, errors="ignore")
 
    if not html_body:
        html_body = f"<pre>{html_lib.escape(text_body) or '(Sin contenido)'}</pre>"
 
    adjuntos = _extract_attachments_info(msg)
    adjuntos_html = _build_attachments_html(adjuntos)
 
    header = f"""
    <div style="font-family:Arial;">
        <p><strong>Asunto:</strong> {html_lib.escape(subject)}</p>
        <p><strong>De:</strong> {html_lib.escape(sender)}</p>
        <p><strong>Para:</strong> {html_lib.escape(recipient)}</p>
        <p><strong>Fecha:</strong> {html_lib.escape(date)}</p>
        {adjuntos_html}
        <hr>
    </div>
    """
 
    return _force_utf8_html(header + html_body)
 
 
def _render_pdf(chrome_exe: str, html_path: Path, pdf_path: Path) -> bool:
    result = subprocess.run(
        [
            chrome_exe,
            "--headless",
            "--disable-gpu",
            f"--print-to-pdf={str(pdf_path)}",
            str(html_path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0
 
 
# -------------------------------------------------
# RUN
# -------------------------------------------------
 
def run(progress=None, is_cancelled=None):
 
    ruta_raw = get_ruta("eml")
    if not ruta_raw:
        raise RuntimeError("No se ha seleccionado ninguna carpeta EML")
 
    carpeta = Path(ruta_raw)
    if not carpeta.is_dir():
        raise RuntimeError("La ruta EML seleccionada no es válida")
 
    emls = sorted(p for p in carpeta.iterdir() if p.suffix.lower() == ".eml")
    if not emls:
        raise RuntimeError("No se encontraron archivos EML en la carpeta")
 
    output = carpeta / "PDF_email"
    output.mkdir(exist_ok=True)
 
    chrome = _find_chrome_exe()
 
    total = len(emls)
    procesados = 0
    errores = 0
 
    logger.info(f"[EML-A-PDF] Procesando {total} EML(s)")
 
    try:
 
        for i, eml_path in enumerate(emls, start=1):
 
            if is_cancelled and is_cancelled():
                raise CancelledByUser()
 
            html_path = None
 
            try:
                with eml_path.open("rb") as f:
                    msg = BytesParser(policy=policy.default).parse(f)
 
                html = _extract_html(msg)
 
                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=".html",
                    mode="w",
                    encoding="utf-8"
                ) as tmp:
                    tmp.write(html)
                    html_path = Path(tmp.name)
 
                pdf_out = resolve_conflict(
                    output / f"{_sanitize_filename(eml_path.stem)}.pdf",
                    pattern="_v{i}"
                )
 
                ok = _render_pdf(chrome, html_path, pdf_out)
 
                if ok and pdf_out.exists() and pdf_out.stat().st_size > 0:
                    procesados += 1
                else:
                    errores += 1
 
            except Exception as e:
                errores += 1
                logger.error(f"[EML-A-PDF] Error en {eml_path.name}: {e}")
                continue
 
            finally:
                if html_path:
                    try:
                        html_path.unlink()
                    except Exception:
                        pass
 
            if progress:
                progress(i, total)
 
    except CancelledByUser:
        logger.info("[EML-A-PDF] Cancelado por usuario")
        return build_cancelled_result(
            output_dir=output,
            total=total,
            procesados=procesados,
            errores=errores,
        )
 
    logger.info(
        f"[EML-A-PDF] Finalizado. "
        f"Procesados: {procesados}. "
        f"Errores: {errores}"
    )
 
    return build_result(
        message="Proceso finalizado",
        output_dir=output,
        total=total,
        procesados=procesados,
        errores=errores,
    )

