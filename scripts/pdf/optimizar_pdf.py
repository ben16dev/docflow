SCRIPT_META = {
    "name": "Optimizar PDF",
    "category": "PDF"
}

import os
import uuid
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


# ==========================================================
# Diálogo
# ==========================================================

class OptimizarPDFDialog(tk.Toplevel):
    """
    Modos:
    - seguro: reescritura estructural conservando texto real.
    - maximo: renderiza cada página como imagen y reconstruye el PDF.
      Reduce capas/OCR/contenido complejo, pero pierde texto seleccionable.

    Protección:
    - si la salida pesa igual o más que el original, no se conserva.
    """

    def __init__(self, parent):
        super().__init__(parent)
        set_window_icon(self)

        self.title("Optimizar PDF")
        self.resizable(False, False)
        self.resultado = None

        self.var_modo = tk.StringVar(value="seguro")
        self.var_dpi = tk.IntVar(value=120)
        self.var_recursivo = tk.BooleanVar(value=False)
        self.var_eliminar_original = tk.BooleanVar(value=False)

        main = ttk.Frame(self, padding=12)
        main.pack(fill="both", expand=True)

        ttk.Label(
            main,
            text="Reducir peso de archivos PDF",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        lf_modo = ttk.LabelFrame(main, text="Modo de optimización", padding=10)
        lf_modo.pack(fill="x")

        ttk.Radiobutton(
            lf_modo,
            text="Modo seguro: conservar texto real y estructura del documento",
            variable=self.var_modo,
            value="seguro",
            command=self._toggle_dpi,
        ).pack(anchor="w")

        ttk.Radiobutton(
            lf_modo,
            text="Máxima reducción: aplanar cada página como imagen",
            variable=self.var_modo,
            value="maximo",
            command=self._toggle_dpi,
        ).pack(anchor="w", pady=(4, 0))

        lf_dpi = ttk.LabelFrame(main, text="Calidad para máxima reducción", padding=10)
        lf_dpi.pack(fill="x", pady=(10, 0))

        row = ttk.Frame(lf_dpi)
        row.pack(fill="x")

        ttk.Label(row, text="Resolución:").pack(side="left")
        self.combo_dpi = ttk.Combobox(
            row,
            width=10,
            state="readonly",
            values=["100", "120", "150"],
        )
        self.combo_dpi.set(str(self.var_dpi.get()))
        self.combo_dpi.pack(side="left", padx=(8, 0))

        ttk.Label(
            lf_dpi,
            text="120 dpi suele reducir más peso manteniendo legibilidad razonable.",
            wraplength=500,
        ).pack(anchor="w", pady=(6, 0))

        lf_opciones = ttk.LabelFrame(main, text="Opciones", padding=10)
        lf_opciones.pack(fill="x", pady=(10, 0))

        ttk.Checkbutton(
            lf_opciones,
            text="Procesar subcarpetas",
            variable=self.var_recursivo,
        ).pack(anchor="w")

        ttk.Checkbutton(
            lf_opciones,
            text="Eliminar PDF original tras generar salida válida y más ligera",
            variable=self.var_eliminar_original,
        ).pack(anchor="w", pady=(4, 0))

        self.lbl_aviso = ttk.Label(main, wraplength=520)
        self.lbl_aviso.pack(anchor="w", pady=(10, 0))

        btns = ttk.Frame(main)
        btns.pack(fill="x", pady=(12, 0))

        ttk.Button(btns, text="Cancelar", command=self._cancelar).pack(side="right")
        ttk.Button(btns, text="Optimizar", command=self._aceptar).pack(side="right", padx=(0, 8))

        self._toggle_dpi()

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

    def _toggle_dpi(self):
        modo = self.var_modo.get()
        if modo == "maximo":
            self.combo_dpi.configure(state="readonly")
            self.lbl_aviso.configure(
                text="Aviso: la máxima reducción aplana el PDF como imagen. "
                     "El documento seguirá siendo legible, pero perderá texto "
                     "seleccionable, OCR, enlaces y formularios. Si el resultado "
                     "pesa igual o más que el original, se omitirá automáticamente."
            )
        else:
            self.combo_dpi.configure(state="disabled")
            self.lbl_aviso.configure(
                text="Modo seguro: conserva texto seleccionable y legibilidad. "
                     "La reducción puede ser menor en PDFs escaneados. Si no reduce "
                     "peso, el PDF se omitirá automáticamente."
            )

    def _aceptar(self):
        modo = self.var_modo.get()

        try:
            dpi = int(self.combo_dpi.get())
            if dpi not in (100, 120, 150):
                raise ValueError
        except Exception:
            messagebox.showerror(
                "Resolución inválida",
                "Selecciona 100, 120 o 150 dpi.",
                parent=self
            )
            return

        if modo == "maximo":
            ok = messagebox.askyesno(
                "Confirmar máxima reducción",
                "El modo de máxima reducción aplana el PDF como imagen. "
                "El documento seguirá siendo legible, pero perderá texto "
                "seleccionable, OCR, enlaces y formularios.\n\n"
                "Si el resultado pesa igual o más que el original, se descartará "
                "automáticamente y no se eliminará el original.\n\n"
                "¿Quieres continuar?",
                parent=self,
            )
            if not ok:
                return

        if self.var_eliminar_original.get():
            ok = messagebox.askyesno(
                "Confirmar eliminación",
                "Se eliminarán los PDFs originales solo si la salida se genera "
                "correctamente y pesa menos que el archivo original.\n\n"
                "¿Quieres continuar?",
                parent=self,
            )
            if not ok:
                return

        self.resultado = {
            "modo": modo,
            "dpi": dpi,
            "recursivo": bool(self.var_recursivo.get()),
            "eliminar_original": bool(self.var_eliminar_original.get()),
        }
        self.destroy()

    def _cancelar(self):
        self.resultado = None
        self.destroy()


# ==========================================================
# Utilidades
# ==========================================================

def _iterar_pdfs(base_dir: Path, recursivo: bool, output_dir: Path):
    """
    Evita reprocesar la propia carpeta de salida cuando el modo recursivo
    está activo.
    """
    if recursivo:
        return sorted([
            p for p in base_dir.rglob("*.pdf")
            if p.is_file() and output_dir not in p.parents
        ])

    return sorted([
        p for p in base_dir.iterdir()
        if p.is_file() and p.suffix.lower() == ".pdf"
    ])


def _tamano(path: Path) -> int:
    try:
        return path.stat().st_size
    except Exception:
        return 0


def _tmp_path_for(output_path: Path) -> Path:
    return output_path.with_name(
        f".tmp_{output_path.stem}_{uuid.uuid4().hex}{output_path.suffix}"
    )


def _safe_unlink(path: Path):
    try:
        if path and path.exists():
            path.unlink()
    except Exception:
        pass


def _replace_output(tmp_path: Path, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    tmp_path.replace(output_path)


def _guardar_seguro(doc, output_path: Path):
    """
    Guardado estructural conservador:
    - garbage=4 elimina objetos no usados.
    - deflate comprime streams.
    - clean sanea sintaxis interna cuando es seguro para PyMuPDF.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(
        str(output_path),
        garbage=4,
        deflate=True,
        clean=True,
        incremental=False,
    )


def _verificar_paginas(output_path: Path, paginas_origen: int):
    check = fitz.open(str(output_path))
    try:
        if check.page_count != paginas_origen:
            raise RuntimeError(
                f"El PDF generado quedó con {check.page_count} páginas "
                f"(original: {paginas_origen})"
            )
    finally:
        check.close()


def _optimizar_modo_seguro(input_path: Path, output_path: Path):
    """
    Conserva texto real, OCR, enlaces y contenido vectorial en la medida en que
    PyMuPDF los mantenga al reescribir el documento.
    """
    doc = fitz.open(str(input_path))
    try:
        paginas_origen = doc.page_count
        if paginas_origen == 0:
            raise RuntimeError("El PDF no contiene páginas")

        # Limpieza de metadatos no crítica. No bloquea el proceso si falla.
        try:
            doc.set_metadata({})
        except Exception:
            pass

        _guardar_seguro(doc, output_path)

    finally:
        doc.close()

    _verificar_paginas(output_path, paginas_origen)


def _optimizar_modo_maximo(input_path: Path, output_path: Path, dpi: int,
                           is_cancelled=None):
    """
    Aplana cada página como imagen JPEG y reconstruye el PDF.
    Robusto para PDFs escaneados y digitales, pero elimina texto real/OCR.

    Importante:
    este modo no garantiza reducción si el PDF original ya venía con imágenes
    muy comprimidas. La protección de tamaño se aplica fuera de esta función.
    """
    src = fitz.open(str(input_path))
    dst = fitz.open()

    try:
        paginas_origen = src.page_count
        if paginas_origen == 0:
            raise RuntimeError("El PDF no contiene páginas")

        for idx in range(src.page_count):
            if is_cancelled and is_cancelled():
                raise CancelledByUser()

            page = src[idx]
            rect = page.rect

            pix = page.get_pixmap(
                dpi=dpi,
                alpha=False,
                colorspace=fitz.csRGB,
            )

            # JPEG suele reducir más que PNG en documentos escaneados.
            img_bytes = pix.tobytes("jpeg")

            new_page = dst.new_page(width=rect.width, height=rect.height)
            new_page.insert_image(
                new_page.rect,
                stream=img_bytes,
                keep_proportion=True,
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        dst.save(
            str(output_path),
            garbage=4,
            deflate=True,
            incremental=False,
        )

    finally:
        dst.close()
        src.close()

    _verificar_paginas(output_path, paginas_origen)


def _optimizar_pdf_validado(input_path: Path, output_path: Path, config: dict,
                            is_cancelled=None):
    """
    Genera una salida solo si pesa menos que el original.

    Retorna:
        (estado, bytes_antes, bytes_despues)

    estado:
        "optimizado" -> se ha creado output_path y pesa menos.
        "omitido"    -> no se ha conservado salida porque no reducía peso.
    """
    modo = config.get("modo", "seguro")
    dpi = int(config.get("dpi", 120))

    antes = _tamano(input_path)
    if antes <= 0:
        raise RuntimeError("El archivo original no tiene tamaño válido")

    tmp = _tmp_path_for(output_path)
    tmp_seguro = None

    try:
        if modo == "seguro":
            _optimizar_modo_seguro(input_path, tmp)

        elif modo == "maximo":
            _optimizar_modo_maximo(input_path, tmp, dpi, is_cancelled)

        else:
            raise RuntimeError(f"Modo de optimización no válido: {modo}")

        despues = _tamano(tmp)

        if despues > 0 and despues < antes:
            _replace_output(tmp, output_path)
            return "optimizado", antes, despues

        logger.info(
            f"[PDF-OPTIMIZAR] Salida descartada por no reducir peso: "
            f"{input_path.name} | {antes} -> {despues} bytes"
        )

        _safe_unlink(tmp)

        # Fallback conservador:
        # si el modo máximo no reduce, probamos reescritura segura.
        if modo == "maximo":
            tmp_seguro = _tmp_path_for(output_path)
            _optimizar_modo_seguro(input_path, tmp_seguro)
            despues_seguro = _tamano(tmp_seguro)

            if despues_seguro > 0 and despues_seguro < antes:
                _replace_output(tmp_seguro, output_path)
                return "optimizado", antes, despues_seguro

            logger.info(
                f"[PDF-OPTIMIZAR] Fallback seguro también descartado: "
                f"{input_path.name} | {antes} -> {despues_seguro} bytes"
            )

            _safe_unlink(tmp_seguro)

        return "omitido", antes, 0

    except Exception:
        _safe_unlink(tmp)
        _safe_unlink(tmp_seguro)
        raise


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
    config = call_ui(lambda: OptimizarPDFDialog(parent).resultado)

    if not config:
        raise CancelledByUser()

    recursivo = bool(config.get("recursivo", False))
    eliminar_original = bool(config.get("eliminar_original", False))
    modo = config.get("modo", "seguro")

    carpeta_out = carpeta_base / "PDF_optimizados"
    carpeta_out.mkdir(exist_ok=True)

    pdfs = _iterar_pdfs(carpeta_base, recursivo, carpeta_out)

    if not pdfs:
        raise RuntimeError("No se encontró ningún PDF en la carpeta seleccionada")

    total = len(pdfs)
    procesados = 0
    errores = 0
    omitidos = 0
    bytes_antes = 0
    bytes_despues = 0

    logger.info(
        f"[PDF-OPTIMIZAR] Procesando {total} PDF(s) | "
        f"Modo: {modo} | Recursivo: {recursivo} | "
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

                estado, antes, despues = _optimizar_pdf_validado(
                    input_path=pdf,
                    output_path=dst,
                    config=config,
                    is_cancelled=is_cancelled,
                )

                bytes_antes += antes

                if estado == "optimizado":
                    bytes_despues += despues
                    procesados += 1

                    logger.info(
                        f"[PDF-OPTIMIZAR] {pdf.name} | "
                        f"{antes} -> {despues} bytes"
                    )

                    if eliminar_original:
                        try:
                            pdf.unlink()
                            logger.info(f"[PDF-OPTIMIZAR] Eliminado original: {pdf}")
                        except Exception as e:
                            logger.warning(
                                f"[PDF-OPTIMIZAR] No se pudo eliminar {pdf.name}: {e}"
                            )

                else:
                    omitidos += 1
                    logger.info(
                        f"[PDF-OPTIMIZAR] Omitido por no reducir tamaño: {pdf.name}"
                    )

            except CancelledByUser:
                raise

            except Exception as e:
                errores += 1
                logger.error(f"[PDF-OPTIMIZAR] Error en {pdf.name}: {e}")
                continue

    except CancelledByUser:
        logger.info("[PDF-OPTIMIZAR] Cancelado por usuario")
        return build_cancelled_result(
            output_dir=carpeta_out,
            total=total,
            procesados=procesados,
            errores=errores,
            omitidos=omitidos,
        )

    ahorro = 0.0
    if bytes_antes > 0 and bytes_despues > 0:
        ahorro = max(0.0, (1.0 - (bytes_despues / bytes_antes)) * 100.0)

    logger.info(
        f"[PDF-OPTIMIZAR] Finalizado. Procesados: {procesados}. "
        f"Omitidos: {omitidos}. Errores: {errores}. "
        f"Ahorro aproximado: {ahorro:.1f}%"
    )

    if procesados == 0 and omitidos > 0 and errores == 0:
        msg = (
            "No se generó ningún PDF optimizado porque los resultados no "
            "reducían el tamaño original."
        )
    else:
        msg = f"Proceso finalizado. Ahorro aproximado: {ahorro:.1f}%"

    return build_result(
        message=msg,
        output_dir=carpeta_out,
        total=total,
        procesados=procesados,
        errores=errores,
        omitidos=omitidos,
    )
