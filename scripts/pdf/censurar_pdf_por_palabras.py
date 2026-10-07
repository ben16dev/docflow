SCRIPT_META = {
    "name": "Censurar PDF por palabras",
    "category": "PDF"
}

import os
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

from config import get_ruta
from ui.exceptions import CancelledByUser
from ui.ui_thread import call_ui
from ui.window_icon import set_window_icon
from logger import logger

from scripts.common.pdf_ranges import parse_ranges, ranges_to_pages_set
from scripts.common.results import build_result
from scripts.pdf.censura_core import (
    MotivoCensura,
    ResultadoCensura,
    ResumenLote,
    censurar_pdf,
    contar_paginas,
    validar_terminos,
)


# ======================================================
# DIÁLOGO UI
# ======================================================

class CensurarDialog(tk.Toplevel):

    def __init__(self, parent):
        super().__init__(parent)
        set_window_icon(self)

        self.title("Censurar información en PDF")
        self.geometry("680x560")
        self.resizable(False, False)

        self.resultado = None

        self.var_todas = tk.BooleanVar(value=True)
        self.var_rango = tk.StringVar(value="1")
        self.var_importes = tk.BooleanVar(value=True)

        tk.Label(
            self,
            text="Introduce las palabras o expresiones a censurar (una por línea)",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", padx=12, pady=(12, 6))

        self.txt_words = tk.Text(self, height=8)
        self.txt_words.pack(fill="both", padx=12, pady=(0, 8))

        tk.Checkbutton(
            self,
            text="Detectar importes del 15 % y 85 % (caso 'Siendo X € lo pagado')",
            variable=self.var_importes
        ).pack(anchor="w", padx=12, pady=(0, 4))

        frame_pages = tk.LabelFrame(self, text="Páginas")
        frame_pages.pack(fill="x", padx=12, pady=8)

        tk.Checkbutton(
            frame_pages,
            text="Usar todas las páginas",
            variable=self.var_todas,
            command=self._toggle_rango
        ).pack(anchor="w", padx=10, pady=(6, 2))

        row = tk.Frame(frame_pages)
        row.pack(fill="x", padx=10, pady=(0, 8))

        tk.Label(
            row,
            text="Solo estas páginas:",
            width=16,
            anchor="w"
        ).pack(side="left")

        self.entry_rango = tk.Entry(
            row,
            textvariable=self.var_rango,
            state="disabled"
        )
        self.entry_rango.pack(side="left", fill="x", expand=True)

        frame_btn = tk.Frame(self)
        frame_btn.pack(fill="x", padx=12, pady=12)

        tk.Button(
            frame_btn,
            text="Cancelar",
            command=self._cancelar
        ).pack(side="left")

        tk.Button(
            frame_btn,
            text="Censurar PDFs",
            command=self._confirmar
        ).pack(side="right")

        self._toggle_rango()

        self.transient(parent)
        self.grab_set()
        self.wait_window()

    def _toggle_rango(self):
        self.entry_rango.config(
            state="disabled" if self.var_todas.get() else "normal"
        )

    def _confirmar(self):
        words_raw = self.txt_words.get("1.0", "end")
        words = [w.strip() for w in words_raw.splitlines() if w.strip()]
        importes = bool(self.var_importes.get())

        try:
            words = validar_terminos(words, importes)
        except ValueError as e:
            messagebox.showerror("Faltan términos", str(e), parent=self)
            return

        if self.var_todas.get():
            ranges = None
        else:
            try:
                ranges = parse_ranges(self.var_rango.get())
            except Exception as e:
                messagebox.showerror("Rango inválido", str(e), parent=self)
                return

        self.resultado = {
            "words": words,
            "all_pages": self.var_todas.get(),
            "ranges": ranges,
            "detectar_importes": importes,
        }

        self.destroy()

    def _cancelar(self):
        self.resultado = None
        self.destroy()


# ======================================================
# LOTE (sin diálogos: testable)
# ======================================================

class CensuraLoteCancelada(CancelledByUser):
    """Cancelación que conserva el resultado parcial (ScriptRunner lo entrega a on_cancelled)."""

    def __init__(self, result: dict):
        self.result = result
        super().__init__("Cancelado")


def _resultado_lote(resumen: ResumenLote, salida_dir: Path, *, cancelado: bool = False) -> dict:
    pendientes = max(
        resumen.total - resumen.procesados - resumen.omitidos - resumen.errores, 0
    )

    extra = {f"errores_{m.value}": n for m, n in resumen.errores_por_motivo.items()}

    # Si no se creó la carpeta de salida (nada procesado), se apunta a la de origen.
    output_dir = salida_dir if salida_dir.is_dir() else salida_dir.parent

    return build_result(
        message="Cancelado" if cancelado else resumen.mensaje(),
        output_dir=output_dir,
        total=resumen.total,
        procesados=resumen.procesados,
        errores=resumen.errores,
        omitidos=resumen.omitidos + (pendientes if cancelado else 0),
        files=resumen.archivos_existentes(),
        terminos_sin_coincidencias=resumen.terminos_sin_coincidencias,
        paginas_con_imagenes=resumen.paginas_con_imagenes,
        paginas_solo_vectoriales=resumen.paginas_solo_vectoriales,
        **extra,
    )


def _procesar_un_pdf(pdf_path, salida_dir, cfg, is_cancelled) -> ResultadoCensura:
    """Resuelve el rango de páginas y delega en el núcleo."""
    try:
        if cfg["all_pages"]:
            pages = None
        else:
            pages = ranges_to_pages_set(cfg["ranges"], contar_paginas(pdf_path))
    except ValueError:
        return ResultadoCensura.fallo(MotivoCensura.RANGO_INVALIDO)
    except Exception:
        return ResultadoCensura.fallo(MotivoCensura.PDF_NO_ABRE)

    return censurar_pdf(
        pdf_path,
        salida_dir,
        cfg["words"],
        pages,
        detectar_importes=cfg.get("detectar_importes", True),
        is_cancelled=is_cancelled,
    )


def _ejecutar_lote(pdf_paths, cfg, progress=None, is_cancelled=None) -> dict:
    # Defensa en profundidad: lista vacía solo con la casilla de importes activa.
    validar_terminos(cfg["words"], cfg.get("detectar_importes", True))

    pdf_paths = [Path(p) for p in pdf_paths]
    salida_dir = pdf_paths[0].parent / "PDF_censurados"
    total = len(pdf_paths)
    resumen = ResumenLote(total=total)

    # Nunca se registran términos, texto, nombres de archivo ni rutas.
    logger.info(f"[PDF-CENSURA] Procesando {total} PDF(s)")

    try:
        for idx, pdf_path in enumerate(pdf_paths, start=1):

            if is_cancelled and is_cancelled():
                raise CancelledByUser()

            resultado = _procesar_un_pdf(pdf_path, salida_dir, cfg, is_cancelled)
            resumen.agregar(resultado)

            logger.info(
                f"[PDF-CENSURA] archivo {idx} de {total}: "
                f"estado={resultado.estado.value} motivo={resultado.motivo.value} "
                f"coincidencias={resultado.coincidencias} "
                f"paginas_afectadas={resultado.paginas_afectadas} "
                f"terminos_sin_coincidencias={resultado.terminos_sin_coincidencias} "
                f"paginas_con_imagenes={resultado.paginas_con_imagenes} "
                f"paginas_solo_vectoriales={resultado.paginas_solo_vectoriales}"
            )

            if progress:
                progress(idx, total)

    except CancelledByUser:
        logger.info(
            f"[PDF-CENSURA] Cancelado por usuario. "
            f"Procesados: {resumen.procesados}. Omitidos: {resumen.omitidos}. "
            f"Errores: {resumen.errores}"
        )
        raise CensuraLoteCancelada(_resultado_lote(resumen, salida_dir, cancelado=True))

    logger.info(
        f"[PDF-CENSURA] Finalizado. Procesados: {resumen.procesados}. "
        f"Omitidos: {resumen.omitidos}. Errores: {resumen.errores}"
    )

    return _resultado_lote(resumen, salida_dir)


# ======================================================
# RUN
# ======================================================

def run(progress=None, is_cancelled=None):

    parent = call_ui(lambda: tk._get_default_root())

    ruta_inicial = get_ruta("pdf")
    initial_dir = ruta_inicial if ruta_inicial and os.path.isdir(ruta_inicial) else None

    pdf_paths = call_ui(lambda: filedialog.askopenfilenames(
        parent=parent,
        title="Selecciona uno o varios PDFs",
        initialdir=initial_dir,
        filetypes=[("PDF", "*.pdf")]
    ))

    if not pdf_paths:
        raise CancelledByUser()

    pdf_paths = [Path(p) for p in pdf_paths]

    def _abrir_dialogo():
        dlg = CensurarDialog(parent)
        return dlg.resultado

    cfg = call_ui(_abrir_dialogo)

    if not cfg:
        raise CancelledByUser()

    return _ejecutar_lote(pdf_paths, cfg, progress, is_cancelled)
