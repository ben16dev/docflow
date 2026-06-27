SCRIPT_META = {
    "name": "Limpiar Numeración PDF",
    "category": "PDF"
}

import os
import re
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from config import get_ruta
from ui.exceptions import CancelledByUser
from ui.ui_thread import call_ui
from ui.window_icon import set_window_icon
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


_MM_TO_PT = 72.0 / 25.4

_PATRONES_NUM_PREVIA = [
    re.compile(r"^\s*\d{1,4}\s*$"),                                       # 12
    re.compile(r"^\s*\d{1,4}\s*[\.\-]\s*$"),                              # 12. / 12-
    re.compile(r"^\s*[\-\–\—\s]+\d{1,4}[\-\–\—\s]+$"),                    # - 12 -
    re.compile(
        r"^\s*(?:P[áa]g(?:ina)?\.?|p\.|Folio)\s*\.?\s*\d{1,4}"
        r"(?:\s*(?:de|/)\s*\d{1,4})?\s*$",
        re.IGNORECASE,
    ),                                                                    # Pág. 12 de 30
    re.compile(r"^\s*\d{1,4}\s*(?:de|/)\s*\d{1,4}\s*$", re.IGNORECASE),   # 12 / 30
    re.compile(
        r"^\s*[A-Za-zÁÉÍÓÚáéíóúÑñ\.]{1,12}\.?\s*\d{1,4}\s*$"
    ),                                                                    # Doc 12, Anexo 3
]


# ==========================================================
# Diálogo
# ==========================================================

class LimpiarNumeracionDialog(tk.Toplevel):
    """
    Diálogo conservador:
    - Solo primera página o todas.
    - Zonas de margen predefinidas.
    - Recursivo opcional.
    """

    def __init__(self, parent):
        super().__init__(parent)
        set_window_icon(self)

        self.title("Limpiar numeración PDF")
        self.resizable(False, False)
        self.resultado = None

        self.var_paginas = tk.StringVar(value="primera")
        self.var_recursivo = tk.BooleanVar(value=False)
        self.var_eliminar_original = tk.BooleanVar(value=False)

        main = ttk.Frame(self, padding=12)
        main.pack(fill="both", expand=True)

        ttk.Label(
            main,
            text="Eliminar marcas de numeración existentes",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        lf_paginas = ttk.LabelFrame(main, text="Páginas", padding=10)
        lf_paginas.pack(fill="x")

        ttk.Radiobutton(
            lf_paginas,
            text="Solo primera página (recomendado)",
            variable=self.var_paginas,
            value="primera",
        ).pack(anchor="w")

        ttk.Radiobutton(
            lf_paginas,
            text="Todas las páginas",
            variable=self.var_paginas,
            value="todas",
        ).pack(anchor="w")

        lf_opciones = ttk.LabelFrame(main, text="Opciones", padding=10)
        lf_opciones.pack(fill="x", pady=(10, 0))

        ttk.Checkbutton(
            lf_opciones,
            text="Procesar subcarpetas",
            variable=self.var_recursivo,
        ).pack(anchor="w")

        ttk.Checkbutton(
            lf_opciones,
            text="Eliminar PDF original tras generar salida válida",
            variable=self.var_eliminar_original,
        ).pack(anchor="w", pady=(4, 0))

        aviso = (
            "La limpieza se limita a zonas de margen superior/inferior para "
            "evitar borrar contenido legítimo."
        )
        ttk.Label(main, text=aviso, wraplength=460).pack(anchor="w", pady=(10, 0))

        btns = ttk.Frame(main)
        btns.pack(fill="x", pady=(12, 0))

        ttk.Button(btns, text="Cancelar", command=self._cancelar).pack(side="right")
        ttk.Button(btns, text="Limpiar", command=self._aceptar).pack(side="right", padx=(0, 8))

        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancelar)

        self.update_idletasks()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            w = self.winfo_width()
            h = self.winfo_height()
            x = px + (pw - w) // 2
            y = py + (ph - h) // 2
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

        self.wait_window(self)

    def _aceptar(self):
        if self.var_eliminar_original.get():
            ok = messagebox.askyesno(
                "Confirmar eliminación",
                "Se eliminarán los PDFs originales solo si la salida se genera "
                "correctamente. ¿Quieres continuar?",
                parent=self,
            )
            if not ok:
                return

        self.resultado = {
            "paginas": self.var_paginas.get(),
            "recursivo": bool(self.var_recursivo.get()),
            "eliminar_original": bool(self.var_eliminar_original.get()),
        }
        self.destroy()

    def _cancelar(self):
        self.resultado = None
        self.destroy()


# ==========================================================
# Detección y borrado
# ==========================================================

def _es_numeracion_previa(texto: str) -> bool:
    if not texto:
        return False
    t = texto.strip()
    if not t or len(t) > 40:
        return False
    return any(p.match(t) for p in _PATRONES_NUM_PREVIA)


def _detectar_watermark(page, bbox_texto, margen_busqueda_pt: float = 40.0,
                        max_expand_pt: float = 30.0):
    """
    A partir del bbox del texto detectado como numeración previa, expande el
    rectángulo para cubrir también el posible fondo coloreado del watermark.
    Devuelve (bbox_watermark, color_fondo_documento).
    """
    try:
        clip = fitz.Rect(
            bbox_texto.x0 - margen_busqueda_pt,
            bbox_texto.y0 - margen_busqueda_pt,
            bbox_texto.x1 + margen_busqueda_pt,
            bbox_texto.y1 + margen_busqueda_pt,
        ) & page.rect

        if clip.is_empty:
            return bbox_texto, (1.0, 1.0, 1.0)

        dpi = 150
        scale = dpi / 72.0
        pix = page.get_pixmap(clip=clip, dpi=dpi, alpha=False)
        if pix.n < 3 or pix.width < 4 or pix.height < 4:
            return bbox_texto, (1.0, 1.0, 1.0)

        n, stride, data = pix.n, pix.stride, pix.samples
        w_px, h_px = pix.width, pix.height

        def pixel(x, y):
            idx = y * stride + x * n
            return (data[idx], data[idx + 1], data[idx + 2])

        sample = min(8, w_px // 4, h_px // 4)
        if sample < 2:
            return bbox_texto, (1.0, 1.0, 1.0)

        rs, gs, bs = [], [], []
        for cy in range(sample):
            for cx in range(sample):
                for px in (
                    pixel(cx, cy),
                    pixel(w_px - 1 - cx, cy),
                    pixel(cx, h_px - 1 - cy),
                    pixel(w_px - 1 - cx, h_px - 1 - cy),
                ):
                    rs.append(px[0])
                    gs.append(px[1])
                    bs.append(px[2])

        rs.sort()
        gs.sort()
        bs.sort()
        mid = len(rs) // 2
        bg = (rs[mid], gs[mid], bs[mid])
        tol = 25

        def es_fondo(p):
            return (
                abs(p[0] - bg[0]) <= tol
                and abs(p[1] - bg[1]) <= tol
                and abs(p[2] - bg[2]) <= tol
            )

        bx0 = max(0, int((bbox_texto.x0 - clip.x0) * scale))
        by0 = max(0, int((bbox_texto.y0 - clip.y0) * scale))
        bx1 = min(w_px - 1, int((bbox_texto.x1 - clip.x0) * scale))
        by1 = min(h_px - 1, int((bbox_texto.y1 - clip.y0) * scale))

        if bx1 <= bx0 or by1 <= by0:
            return bbox_texto, (bg[0] / 255.0, bg[1] / 255.0, bg[2] / 255.0)

        cx_mid = (bx0 + bx1) // 2
        cy_mid = (by0 + by1) // 2

        max_expand_px = int(max_expand_pt * scale)
        gap_max = 4

        def expandir(start, end_px, step, fijo, modo):
            ext = start
            gap = 0
            cur = start
            while True:
                cur += step
                if step > 0 and cur >= end_px:
                    break
                if step < 0 and cur < 0:
                    break
                if abs(cur - start) > max_expand_px:
                    break

                p = pixel(cur, fijo) if modo == "h" else pixel(fijo, cur)

                if es_fondo(p):
                    gap += 1
                    if gap >= gap_max:
                        break
                else:
                    gap = 0
                    ext = cur

            return ext

        ext_left = expandir(bx0, 0, -1, cy_mid, "h")
        ext_right = expandir(bx1, w_px, +1, cy_mid, "h")
        ext_top = expandir(by0, 0, -1, cx_mid, "v")
        ext_bottom = expandir(by1, h_px, +1, cx_mid, "v")

        wm_rect = fitz.Rect(
            clip.x0 + ext_left / scale,
            clip.y0 + ext_top / scale,
            clip.x0 + (ext_right + 1) / scale,
            clip.y0 + (ext_bottom + 1) / scale,
        ) & page.rect

        wm_rect = wm_rect | bbox_texto
        bg_norm = (bg[0] / 255.0, bg[1] / 255.0, bg[2] / 255.0)

        return wm_rect, bg_norm

    except Exception:
        return bbox_texto, (1.0, 1.0, 1.0)


def _zonas_margen(page):
    w = page.rect.width
    h = page.rect.height

    margen_v = 30 * _MM_TO_PT
    margen_h = 90 * _MM_TO_PT

    return [
        fitz.Rect(0, 0, margen_h, margen_v),
        fitz.Rect(w - margen_h, 0, w, margen_v),
        fitz.Rect((w - margen_h) / 2, 0, (w + margen_h) / 2, margen_v),
        fitz.Rect(0, h - margen_v, margen_h, h),
        fitz.Rect(w - margen_h, h - margen_v, w, h),
        fitz.Rect((w - margen_h) / 2, h - margen_v, (w + margen_h) / 2, h),
    ]


def _detectar_redacciones_en_pagina(page):
    redacciones = []

    def registrar(rect_texto):
        rect_texto = rect_texto & page.rect
        if rect_texto.is_empty:
            return

        wm_rect, color_fondo = _detectar_watermark(
            page,
            rect_texto,
            margen_busqueda_pt=40.0,
            max_expand_pt=30.0,
        )
        wm_rect = (wm_rect + (-1, -1, 1, 1)) & page.rect
        if not wm_rect.is_empty:
            redacciones.append((wm_rect, color_fondo))

    for zona in _zonas_margen(page):
        try:
            data = page.get_text("dict", clip=zona)
        except Exception:
            continue

        for block in data.get("blocks", []):
            if block.get("type", 0) != 0:
                continue

            lineas_match = []
            lineas_total = 0

            for line in block.get("lines", []):
                spans = line.get("spans", [])
                texto_linea = "".join(s.get("text", "") for s in spans).strip()

                if not texto_linea:
                    continue

                lineas_total += 1

                if _es_numeracion_previa(texto_linea):
                    lx0, ly0, lx1, ly1 = line.get("bbox", (0, 0, 0, 0))
                    lineas_match.append(fitz.Rect(lx0, ly0, lx1, ly1))

            if not lineas_match:
                continue

            if lineas_total > 0 and len(lineas_match) == lineas_total:
                bx0, by0, bx1, by1 = block.get("bbox", (0, 0, 0, 0))
                registrar(fitz.Rect(bx0, by0, bx1, by1) & zona)
            else:
                for bb in lineas_match:
                    registrar(bb & zona)

    return redacciones


def _aplicar_redacciones(page, redacciones):
    if not redacciones:
        return 0

    for rect, color_fondo in redacciones:
        page.add_redact_annot(rect, fill=color_fondo)

    try:
        image_flag = fitz.PDF_REDACT_IMAGE_PIXELS
    except AttributeError:
        image_flag = fitz.PDF_REDACT_IMAGE_NONE

    try:
        page.apply_redactions(images=image_flag)
    except TypeError:
        page.apply_redactions()

    return len(redacciones)


def _limpiar_pdf(input_path: Path, output_path: Path, paginas_modo: str,
                 is_cancelled=None) -> int:
    if fitz is None:
        raise RuntimeError("Falta dependencia 'pymupdf'. Instala con: pip install pymupdf")

    doc = fitz.open(str(input_path))

    try:
        if doc.page_count == 0:
            raise RuntimeError("El PDF no contiene páginas")

        paginas_origen = doc.page_count
        total_redacciones = 0

        if paginas_modo == "todas":
            indices = range(doc.page_count)
        else:
            indices = range(1)

        for idx in indices:
            if is_cancelled and is_cancelled():
                raise CancelledByUser()

            page = doc[idx]
            redacciones = _detectar_redacciones_en_pagina(page)
            total_redacciones += _aplicar_redacciones(page, redacciones)

        if doc.page_count != paginas_origen:
            raise RuntimeError(
                f"El conteo de páginas cambió durante la limpieza "
                f"({paginas_origen} -> {doc.page_count})"
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(
            str(output_path),
            garbage=4,
            deflate=True,
            incremental=False,
        )

    finally:
        doc.close()

    # Verificación final
    check = fitz.open(str(output_path))
    try:
        if check.page_count != paginas_origen:
            raise RuntimeError(
                f"El PDF generado quedó con {check.page_count} páginas "
                f"(original: {paginas_origen})"
            )
    finally:
        check.close()

    return total_redacciones


def _iterar_pdfs(base_dir: Path, recursivo: bool):
    if recursivo:
        return sorted([p for p in base_dir.rglob("*.pdf") if p.is_file()])
    return sorted([p for p in base_dir.iterdir() if p.suffix.lower() == ".pdf"])


# ==========================================================
# Entry point
# ==========================================================

def run(progress=None, is_cancelled=None):

    if fitz is None:
        raise RuntimeError("Falta dependencia 'pymupdf'. Instala con: pip install pymupdf")

    ruta_raw = get_ruta("pdf")
    if not ruta_raw:
        raise RuntimeError("No hay ruta de trabajo configurada para PDF.")

    carpeta_base = Path(ruta_raw)
    if not carpeta_base.exists() or not carpeta_base.is_dir():
        raise RuntimeError("La carpeta PDF seleccionada no es válida")

    parent = call_ui(lambda: tk._get_default_root())
    config = call_ui(lambda: LimpiarNumeracionDialog(parent).resultado)

    if not config:
        raise CancelledByUser()

    recursivo = bool(config.get("recursivo", False))
    eliminar_original = bool(config.get("eliminar_original", False))
    paginas_modo = config.get("paginas", "primera")

    carpeta_out = carpeta_base / "PDF_sin_numeracion"
    carpeta_out.mkdir(exist_ok=True)

    pdfs = _iterar_pdfs(carpeta_base, recursivo)

    if not pdfs:
        raise RuntimeError("No se encontró ningún PDF en la carpeta seleccionada")

    total = len(pdfs)
    procesados = 0
    errores = 0
    omitidos = 0
    total_marcas = 0

    logger.info(
        f"[PDF-LIMPIAR-NUM] Procesando {total} PDF(s) | "
        f"Recursivo: {recursivo} | Páginas: {paginas_modo} | "
        f"Eliminar originales: {eliminar_original}"
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

                marcas = _limpiar_pdf(
                    input_path=pdf,
                    output_path=dst,
                    paginas_modo=paginas_modo,
                    is_cancelled=is_cancelled,
                )

                total_marcas += marcas
                procesados += 1

                if eliminar_original and dst.exists() and dst.stat().st_size > 0:
                    try:
                        pdf.unlink()
                        logger.info(f"[PDF-LIMPIAR-NUM] Eliminado original: {pdf}")
                    except Exception as e:
                        logger.warning(
                            f"[PDF-LIMPIAR-NUM] No se pudo eliminar {pdf.name}: {e}"
                        )

            except CancelledByUser:
                raise

            except Exception as e:
                errores += 1
                logger.error(f"[PDF-LIMPIAR-NUM] Error en {pdf.name}: {e}")
                continue

    except CancelledByUser:
        logger.info("[PDF-LIMPIAR-NUM] Cancelado por usuario")
        return build_cancelled_result(
            output_dir=carpeta_out,
            total=total,
            procesados=procesados,
            errores=errores,
            omitidos=omitidos,
        )

    logger.info(
        f"[PDF-LIMPIAR-NUM] Finalizado. "
        f"Procesados: {procesados}. Errores: {errores}. "
        f"Marcas detectadas/redactadas: {total_marcas}"
    )

    return build_result(
        message=f"Proceso finalizado. Marcas limpiadas: {total_marcas}",
        output_dir=carpeta_out,
        total=total,
        procesados=procesados,
        errores=errores,
        omitidos=omitidos,
    )
