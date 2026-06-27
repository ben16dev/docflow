SCRIPT_META = {
    "name": "Numerar páginas PDF",
    "category": "PDF"
}

import os
import re
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.colors import Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

try:
    import fitz  # PyMuPDF
    _PYMUPDF_OK = True
except ImportError:
    fitz = None
    _PYMUPDF_OK = False

from config import get_ruta
from ui.exceptions import CancelledByUser
from ui.dialog_prefijo import solicitar_configuracion
from ui.ui_thread import call_ui
from logger import logger

try:
    from scripts.common.results import build_result, build_cancelled_result
except Exception:
    def build_result(message, output_dir, total=0, procesados=0, errores=0, omitidos=0, **kwargs):
        return {
            "message": message,
            "output_dir": str(output_dir) if output_dir else None,
            "stats": {
                "total": total,
                "procesados": procesados,
                "errores": errores,
                "omitidos": omitidos,
            }
        }

    def build_cancelled_result(output_dir, total=0, procesados=0, errores=0, omitidos=0, **kwargs):
        return build_result(
            message="Cancelado",
            output_dir=output_dir,
            total=total,
            procesados=procesados,
            errores=errores,
            omitidos=omitidos,
        )


# ==========================================================
# Registro / localización de fuentes
# ==========================================================

_VERDANA_FONT_PATH = None
_VERDANA_BOLD_FONT_PATH = None
_VERDANA_FONT_SCANNED = False


def _scan_verdana_fonts():
    """
    Busca Verdana regular y negrita una sola vez por ejecución.

    Motivo:
    recorrer C:\\Windows\\Fonts para cada PDF penaliza bastante en lotes
    grandes. Cachear la ruta no cambia el resultado y reduce I/O.
    """
    global _VERDANA_FONT_PATH, _VERDANA_BOLD_FONT_PATH, _VERDANA_FONT_SCANNED

    if _VERDANA_FONT_SCANNED:
        return

    _VERDANA_FONT_SCANNED = True
    fonts_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"

    try:
        candidatos = list(fonts_dir.iterdir())

        # Nombres habituales en Windows:
        # verdana.ttf  -> regular
        # verdanab.ttf -> bold
        for fname in candidatos:
            name = fname.name.lower()

            if name == "verdana.ttf":
                _VERDANA_FONT_PATH = str(fname)

            elif name == "verdanab.ttf":
                _VERDANA_BOLD_FONT_PATH = str(fname)

        # Fallbacks defensivos si el nombre exacto cambia.
        for fname in candidatos:
            name = fname.name.lower()

            if not name.endswith(".ttf"):
                continue

            if _VERDANA_FONT_PATH is None:
                if name.startswith("verdana") and "bold" not in name and name != "verdanab.ttf":
                    _VERDANA_FONT_PATH = str(fname)

            if _VERDANA_BOLD_FONT_PATH is None:
                if name.startswith("verdana") and ("bold" in name or name == "verdanab.ttf"):
                    _VERDANA_BOLD_FONT_PATH = str(fname)

    except Exception:
        pass


def _buscar_verdana_ttf(bold: bool = False):
    _scan_verdana_fonts()
    return _VERDANA_BOLD_FONT_PATH if bold else _VERDANA_FONT_PATH


def _registrar_verdana():
    """
    Registra Verdana regular y, si existe, Verdana-Bold para el fallback
    ReportLab/pypdf.

    Devuelve la fuente por defecto que verá el diálogo.
    """
    fuente_regular = _buscar_verdana_ttf(False)
    fuente_bold = _buscar_verdana_ttf(True)

    if fuente_regular:
        try:
            pdfmetrics.registerFont(TTFont("Verdana", fuente_regular))
            if fuente_bold:
                try:
                    pdfmetrics.registerFont(TTFont("Verdana-Bold", fuente_bold))
                except Exception:
                    pass
            return "Verdana"
        except Exception:
            pass

    return "Helvetica"


def _ruta_fuente_verdana(bold: bool = False):
    """
    Devuelve la ruta del TTF de Verdana si existe en Windows.
    Se usa solo para el estampado PyMuPDF.
    """
    return _buscar_verdana_ttf(bold)


def _normalizar_font_reportlab(font_name: str, bold: bool) -> str:
    """
    Devuelve una fuente válida para medición/escritura con ReportLab.

    Mantiene compatibilidad con las fuentes base y con Verdana si está
    registrada. Si la variante negrita no existe, cae a Helvetica-Bold.
    """
    font_name = font_name or "Helvetica"

    if not bold:
        return font_name

    base = str(font_name).lower()

    if base == "verdana":
        if "Verdana-Bold" in pdfmetrics.getRegisteredFontNames():
            return "Verdana-Bold"
        return "Helvetica-Bold"

    if base in ("helvetica", "helv"):
        return "Helvetica-Bold"

    if base in ("courier", "cour"):
        return "Courier-Bold"

    if base in ("times-roman", "times", "tiro"):
        return "Times-Bold"

    # Fallback estable
    return "Helvetica-Bold"


def _font_pymupdf(font_name_cfg: str, bold: bool):
    """
    Devuelve (fontname, fontfile) para PyMuPDF.

    Para Verdana se intenta incrustar TTF real. Para fuentes base se usan
    alias internos de PyMuPDF. Si algo falla, el llamador tiene fallback.
    """
    base = str(font_name_cfg or "Helvetica").lower()

    if base == "verdana":
        fontfile = _ruta_fuente_verdana(bold)
        if fontfile:
            return ("Verdana-Bold" if bold else "Verdana"), fontfile

        # Si no tenemos Verdana Bold, caemos a fuente base.
        return ("hebo" if bold else "helv"), None

    if base in ("courier", "cour"):
        return ("cobo" if bold else "cour"), None

    if base in ("times-roman", "times", "tiro"):
        return ("tibo" if bold else "tiro"), None

    return ("hebo" if bold else "helv"), None


# ==========================================================
# Watermark de numeración nueva
# ==========================================================

def _crear_watermark(texto, width, height, config):
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=(width, height))

    margin = 10 * mm
    padding = 4 * mm

    bold = bool(config.get("bold", False))
    font_name = _normalizar_font_reportlab(config.get("font", "Helvetica"), bold)
    fontsize = int(config["fontsize"])

    tr, tg, tb = config["text_color"]
    br, bg, bb = config["bg_color"]
    text_color = Color(tr / 255, tg / 255, tb / 255)
    bg_color = Color(br / 255, bg / 255, bb / 255)

    try:
        text_width = c.stringWidth(texto, font_name, fontsize)
    except Exception:
        font_name = "Helvetica-Bold" if bold else "Helvetica"
        text_width = c.stringWidth(texto, font_name, fontsize)

    text_height = fontsize

    rect_width = text_width + 2 * padding
    rect_height = text_height + padding

    if config["horizontal"] == "left":
        x_rect = margin
    elif config["horizontal"] == "center":
        x_rect = (width - rect_width) / 2
    else:
        x_rect = width - margin - rect_width

    if config["vertical"] == "bottom":
        y_rect = margin
    else:
        y_rect = height - margin - rect_height

    if config["background"]:
        c.setFillColor(bg_color)
        c.rect(x_rect, y_rect, rect_width, rect_height, fill=1, stroke=0)

    c.setFont(font_name, fontsize)
    c.setFillColor(text_color)
    c.drawString(
        x_rect + padding,
        y_rect + (rect_height - text_height) / 2,
        texto
    )

    c.save()
    packet.seek(0)
    return PdfReader(packet).pages[0]


def _estampar_primera_pagina_pymupdf(pdf_bytes: bytes, texto: str, config: dict) -> bytes:
    """
    Estampa la numeración nueva en la primera página usando PyMuPDF.

    Motivo técnico:
    evita pypdf.Page.merge_page(), que en algunos PDFs heredados genera
    content streams aceptados por varios visores pero rechazados por Acrobat
    con el aviso "Hay un error en esta página".

    Conserva páginas, imágenes y contenido existente. Solo añade una capa
    de dibujo/texto en la primera página.
    """
    if not _PYMUPDF_OK:
        raise RuntimeError("PyMuPDF no está disponible")

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    try:
        if doc.page_count == 0:
            raise RuntimeError("El PDF no contiene páginas")

        paginas_origen = doc.page_count
        page = doc[0]

        width = float(page.rect.width)
        height = float(page.rect.height)

        margin = 10 * mm
        padding = 4 * mm

        font_name_cfg = config.get("font") or "Helvetica"
        fontsize = int(config.get("fontsize", 12))
        bold = bool(config.get("bold", False))

        tr, tg, tb = config["text_color"]
        br, bg, bb = config["bg_color"]

        text_color = (tr / 255.0, tg / 255.0, tb / 255.0)
        bg_color = (br / 255.0, bg / 255.0, bb / 255.0)

        font_reportlab = _normalizar_font_reportlab(font_name_cfg, bold)

        try:
            text_width = pdfmetrics.stringWidth(texto, font_reportlab, fontsize)
        except Exception:
            text_width = pdfmetrics.stringWidth(
                texto,
                "Helvetica-Bold" if bold else "Helvetica",
                fontsize
            )

        text_height = fontsize
        rect_width = text_width + 2 * padding
        rect_height = text_height + padding

        horizontal = config.get("horizontal", "right")
        vertical = config.get("vertical", "top")

        if horizontal == "left":
            x_rect = margin
        elif horizontal == "center":
            x_rect = (width - rect_width) / 2
        else:
            x_rect = width - margin - rect_width

        # PyMuPDF usa origen arriba-izquierda.
        if vertical == "bottom":
            y_rect = height - margin - rect_height
        else:
            y_rect = margin

        rect = fitz.Rect(
            x_rect,
            y_rect,
            x_rect + rect_width,
            y_rect + rect_height,
        )

        if config.get("background"):
            page.draw_rect(rect, color=None, fill=bg_color, overlay=True)

        fontname, fontfile = _font_pymupdf(font_name_cfg, bold)

        baseline_x = x_rect + padding
        baseline_y = y_rect + (rect_height + fontsize) / 2 - 1

        try:
            page.insert_text(
                fitz.Point(baseline_x, baseline_y),
                texto,
                fontsize=fontsize,
                fontname=fontname,
                fontfile=fontfile,
                color=text_color,
                overlay=True,
            )
        except Exception:
            # Fallback conservador. Si falla la fuente externa o el alias,
            # usamos fuente base Helvetica/Helvetica-Bold.
            page.insert_text(
                fitz.Point(baseline_x, baseline_y),
                texto,
                fontsize=fontsize,
                fontname="hebo" if bold else "helv",
                color=text_color,
                overlay=True,
            )

        if doc.page_count != paginas_origen:
            raise RuntimeError(
                f"El conteo de páginas cambió durante el estampado "
                f"({paginas_origen} -> {doc.page_count})"
            )

        out = BytesIO()
        doc.save(
            out,
            garbage=4,
            deflate=True,
            incremental=False,
        )

        nuevo = out.getvalue()

        check = fitz.open(stream=nuevo, filetype="pdf")
        try:
            if check.page_count != paginas_origen:
                raise RuntimeError(
                    f"El PDF estampado quedó con {check.page_count} páginas "
                    f"(original: {paginas_origen})"
                )
        finally:
            check.close()

        return nuevo

    finally:
        doc.close()


def _estampar_con_pypdf_fallback(pdf_bytes: bytes, texto: str, config: dict) -> bytes:
    """
    Fallback para entornos sin PyMuPDF. Se mantiene por compatibilidad,
    aunque el camino preferido es PyMuPDF.
    """
    writer = PdfWriter()

    try:
        reader = PdfReader(BytesIO(pdf_bytes))

        primera = reader.pages[0]
        media = primera.mediabox

        watermark = _crear_watermark(
            texto=texto,
            width=float(media.width),
            height=float(media.height),
            config=config,
        )

        primera.merge_page(watermark)
        writer.add_page(primera)

        for p in reader.pages[1:]:
            writer.add_page(p)

        out = BytesIO()
        writer.write(out)
        return out.getvalue()

    finally:
        try:
            writer.close()
        except Exception:
            pass


# ==========================================================
# Procesamiento de cada PDF
# ==========================================================

def _procesar_pdf(ruta_entrada: Path, ruta_salida: Path, config: dict) -> str:

    base = ruta_entrada.stem
    match = re.match(r"^(\d{2})", base)

    if not match:
        return "omitido"

    num = match.group(1)
    nombre_sin_num = base[len(num):].strip(" -_")

    modo = config.get("modo_numeracion")

    if not modo:
        if config.get("prefijo"):
            modo = "prefijo_numero"
        else:
            modo = "numero"

    pref = config.get("prefijo", "").strip()

    if modo == "numero":
        texto = num
    elif modo == "prefijo_numero":
        texto = f"{pref} {num}".strip()
    elif modo == "prefijo_numero_nombre":
        texto = f"{pref} {num} {nombre_sin_num}".strip()
    else:
        texto = num

    try:
        with open(ruta_entrada, "rb") as f:
            pdf_bytes = f.read()
    except Exception:
        raise RuntimeError(f"No se pudo leer el PDF: {ruta_entrada.name}")

    try:
        if _PYMUPDF_OK:
            pdf_resultado = _estampar_primera_pagina_pymupdf(
                pdf_bytes=pdf_bytes,
                texto=texto,
                config=config,
            )
        else:
            pdf_resultado = _estampar_con_pypdf_fallback(
                pdf_bytes=pdf_bytes,
                texto=texto,
                config=config,
            )

    except Exception as e:
        raise RuntimeError(
            f"No se pudo procesar el PDF: {ruta_entrada.name}. Detalle: {e}"
        )

    ruta_salida.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(ruta_salida, "wb") as f:
            f.write(pdf_resultado)
    except Exception:
        raise RuntimeError(f"No se pudo escribir el PDF: {ruta_salida.name}")

    return "estampado"


def _iterar_pdfs(base_dir: Path, recursivo: bool):
    if recursivo:
        return sorted([p for p in base_dir.rglob("*.pdf") if p.is_file()])
    return sorted([p for p in base_dir.iterdir() if p.suffix.lower() == ".pdf"])


# ==========================================================
# Entry point
# ==========================================================

def run(progress=None, is_cancelled=None):

    ruta_raw = get_ruta("pdf")
    if not ruta_raw:
        raise RuntimeError("No hay ruta de trabajo configurada para PDF.")

    carpeta_base = Path(ruta_raw)
    if not carpeta_base.exists() or not carpeta_base.is_dir():
        raise RuntimeError("La carpeta PDF seleccionada no es válida")

    carpeta_out = carpeta_base / "PDF_salida"
    carpeta_out.mkdir(exist_ok=True)

    font_default = _registrar_verdana()

    # Compatibilidad:
    # El diálogo actual puede seguir teniendo internamente la opción
    # "limpiar_previa". Este script la ignora deliberadamente porque la
    # limpieza pasa a ser responsabilidad de limpiar_numeracion_pdf.py.
    try:
        config = call_ui(
            lambda: solicitar_configuracion(
                font_default=font_default,
                pymupdf_disponible=_PYMUPDF_OK,
            )
        )
    except TypeError:
        config = call_ui(lambda: solicitar_configuracion(font_default))

    if not config:
        raise CancelledByUser()

    recursivo = bool(config.get("recursivo", False))
    eliminar_original = bool(config.get("eliminar_original", False))
    bold = bool(config.get("bold", False))

    pdfs = _iterar_pdfs(carpeta_base, recursivo)

    if not pdfs:
        raise RuntimeError("No se encontró ningún PDF en la carpeta seleccionada")

    total = len(pdfs)
    procesados = 0
    omitidos = 0
    errores = 0

    logger.info(
        f"[PDF-NUMERAR] Procesando {total} PDF(s) | "
        f"Recursivo: {recursivo} | "
        f"Eliminar originales: {eliminar_original} | "
        f"Negrita: {bold}"
    )

    try:

        for i, pdf in enumerate(pdfs, start=1):

            if is_cancelled and is_cancelled():
                raise CancelledByUser()

            if progress:
                progress(i, total)

            try:

                if recursivo:
                    ruta_rel = pdf.relative_to(carpeta_base)
                    dst = carpeta_out / ruta_rel
                else:
                    dst = carpeta_out / pdf.name

                resultado = _procesar_pdf(pdf, dst, config)

                if resultado == "estampado":
                    procesados += 1

                    if eliminar_original:
                        if dst.exists() and dst.stat().st_size > 0:
                            try:
                                pdf.unlink()
                                logger.info(
                                    f"[PDF-NUMERAR] Eliminado original: {pdf}"
                                )
                            except Exception as e:
                                logger.warning(
                                    f"[PDF-NUMERAR] No se pudo eliminar "
                                    f"{pdf.name}: {e}"
                                )
                else:
                    omitidos += 1

            except Exception as e:
                errores += 1
                logger.error(f"[PDF-NUMERAR] Error en {pdf.name}: {e}")
                continue

    except CancelledByUser:
        logger.info("[PDF-NUMERAR] Cancelado por usuario")
        return build_cancelled_result(
            output_dir=carpeta_out,
            total=total,
            procesados=procesados,
            errores=errores,
            omitidos=omitidos,
        )

    logger.info(
        f"[PDF-NUMERAR] Finalizado. "
        f"Estampados: {procesados}. "
        f"Omitidos: {omitidos}. "
        f"Errores: {errores}"
    )

    return build_result(
        message="Proceso finalizado",
        output_dir=carpeta_out,
        total=total,
        procesados=procesados,
        errores=errores,
        omitidos=omitidos,
    )