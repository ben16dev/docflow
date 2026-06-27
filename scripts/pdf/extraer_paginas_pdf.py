SCRIPT_META = {
    "name": "Extraer páginas PDF",
    "category": "PDF"
}

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from config import get_ruta
from ui.exceptions import CancelledByUser
from ui.ui_thread import call_ui
from ui.window_icon import set_window_icon
from logger import logger

from scripts.common.filenames import resolve_conflict, sanitize_filename
from scripts.common.pdf_ranges import parse_ranges, expand_ranges_to_pages
from scripts.common.results import build_result, build_cancelled_result


class ExtraerPaginasDialog(tk.Toplevel):

    def __init__(self, parent, default_name: str):
        super().__init__(parent)
        set_window_icon(self)
        self.title("Extraer páginas PDF")
        self.resizable(False, False)

        self.resultado = None

        self.var_modo = tk.StringVar(value="single")
        self.var_todas = tk.BooleanVar(value=False)
        self.var_rangos = tk.StringVar(value="1-1")
        self.var_usar_original = tk.BooleanVar(value=True)
        self.var_nombre = tk.StringVar(value=default_name)

        main = ttk.Frame(self, padding=12)
        main.pack(fill="both", expand=True)

        lf1 = ttk.LabelFrame(main, text="Modo", padding=10)
        lf1.pack(fill="x")

        ttk.Radiobutton(
            lf1,
            text="Single (un PDF con todas las páginas seleccionadas)",
            variable=self.var_modo,
            value="single"
        ).pack(anchor="w")

        ttk.Radiobutton(
            lf1,
            text="Multi (un PDF por cada rango)",
            variable=self.var_modo,
            value="multi"
        ).pack(anchor="w")

        lf2 = ttk.LabelFrame(main, text="Páginas", padding=10)
        lf2.pack(fill="x", pady=(10, 0))

        ttk.Checkbutton(
            lf2,
            text="Extraer todas las páginas",
            variable=self.var_todas,
            command=self._toggle_rangos_state
        ).pack(anchor="w")

        row = ttk.Frame(lf2)
        row.pack(fill="x", pady=(6, 0))

        ttk.Label(
            row,
            text="Rangos (ej: 1-3, 5, 8-10):"
        ).pack(side="left")

        self.ent_rangos = ttk.Entry(
            row,
            textvariable=self.var_rangos,
            width=26
        )
        self.ent_rangos.pack(side="left", padx=8)

        lf3 = ttk.LabelFrame(main, text="Nombre de salida", padding=10)
        lf3.pack(fill="x", pady=(10, 0))

        ttk.Checkbutton(
            lf3,
            text="Usar nombre original como base",
            variable=self.var_usar_original,
            command=self._toggle_nombre_state
        ).pack(anchor="w")

        row2 = ttk.Frame(lf3)
        row2.pack(fill="x", pady=(6, 0))

        ttk.Label(
            row2,
            text="Nombre base (si no usas original):"
        ).pack(side="left")

        self.ent_nombre = ttk.Entry(
            row2,
            textvariable=self.var_nombre,
            width=26
        )
        self.ent_nombre.pack(side="left", padx=8)

        btns = ttk.Frame(main)
        btns.pack(fill="x", pady=(12, 0))

        ttk.Button(
            btns,
            text="Cancelar",
            command=self._on_cancel
        ).pack(side="right")

        ttk.Button(
            btns,
            text="Aceptar",
            command=self._on_ok
        ).pack(side="right", padx=(0, 8))

        self._toggle_rangos_state()
        self._toggle_nombre_state()

        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self.wait_window(self)

    def _toggle_rangos_state(self):
        self.ent_rangos.configure(
            state="disabled" if self.var_todas.get() else "normal"
        )

    def _toggle_nombre_state(self):
        self.ent_nombre.configure(
            state="disabled" if self.var_usar_original.get() else "normal"
        )

    def _on_ok(self):
        modo = self.var_modo.get().strip()
        if modo not in ("single", "multi"):
            messagebox.showerror("Error", "Modo inválido.", parent=self)
            return

        todas = bool(self.var_todas.get())

        rangos = []
        if not todas:
            try:
                rangos = parse_ranges(self.var_rangos.get())
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=self)
                return

        usar_original = bool(self.var_usar_original.get())
        nombre_base = self.var_nombre.get().strip()

        if not usar_original and not nombre_base:
            messagebox.showerror(
                "Error",
                "Introduce un nombre base o marca 'Usar nombre original'.",
                parent=self
            )
            return

        self.resultado = {
            "modo": modo,
            "todas": todas,
            "rangos": rangos,
            "usar_original": usar_original,
            "nombre_base": sanitize_filename(
                nombre_base,
                max_len=120,
                fallback="PDF_extraido"
            ) if nombre_base else "",
        }
        self.destroy()

    def _on_cancel(self):
        self.resultado = None
        self.destroy()


# ======================================================
# RUN
# ======================================================

def run(progress=None, is_cancelled=None):

    parent = call_ui(lambda: tk._get_default_root())

    ruta_inicial = get_ruta("pdf")
    initial_dir = ruta_inicial if ruta_inicial and os.path.isdir(ruta_inicial) else None

    pdf_path = call_ui(lambda: filedialog.askopenfilename(
        parent=parent,
        title="Selecciona un PDF",
        initialdir=initial_dir,
        filetypes=[("PDF", "*.pdf")]
    ))

    if not pdf_path:
        raise CancelledByUser()

    pdf_path = Path(pdf_path)

    # Obtener número de páginas sin dejar lock
    try:
        with open(pdf_path, "rb") as f:
            reader = PdfReader(f)
            max_pages = len(reader.pages)
    except Exception:
        raise RuntimeError(
            "No se pudo abrir el PDF. Puede estar dañado, protegido o en uso."
        )

    res = call_ui(lambda: ExtraerPaginasDialog(parent, pdf_path.stem).resultado)
    if not res:
        raise CancelledByUser()

    modo = res["modo"]
    usar_original = res["usar_original"]
    nombre_base = pdf_path.stem if usar_original else res["nombre_base"]
    nombre_base = sanitize_filename(
        nombre_base,
        max_len=120,
        fallback="PDF_extraido"
    )

    salida_dir = pdf_path.parent / "PDF_extraidos"
    salida_dir.mkdir(exist_ok=True)

    procesados = 0
    errores = 0

    logger.info(f"[PDF-EXTRAER] Procesando archivo: {pdf_path.name}")

    try:

        if res["todas"]:
            rangos = (
                [(i, i) for i in range(1, max_pages + 1)]
                if modo == "multi"
                else [(1, max_pages)]
            )
        else:
            rangos = res["rangos"]

        # =========================
        # SINGLE
        # =========================
        if modo == "single":

            pages = expand_ranges_to_pages(rangos, max_pages)
            writer = PdfWriter()

            with open(pdf_path, "rb") as f:
                reader = PdfReader(f)

                for i, p in enumerate(pages, start=1):
                    if is_cancelled and is_cancelled():
                        raise CancelledByUser()

                    writer.add_page(reader.pages[p - 1])

                    if progress:
                        progress(i, len(pages))

            out = resolve_conflict(
                salida_dir / f"{nombre_base}.pdf",
                pattern="_v{i}"
            )

            with open(out, "wb") as f:
                writer.write(f)

            writer.close()
            procesados = 1

        # =========================
        # MULTI
        # =========================
        else:

            total_rangos = len(rangos)

            for idx, (start, end) in enumerate(rangos, start=1):

                if is_cancelled and is_cancelled():
                    raise CancelledByUser()

                writer = PdfWriter()

                with open(pdf_path, "rb") as f:
                    reader = PdfReader(f)

                    for p in range(start, end + 1):
                        writer.add_page(reader.pages[p - 1])

                out = resolve_conflict(
                    salida_dir / f"{nombre_base}_{idx:02d}.pdf",
                    pattern="_v{i}"
                )

                with open(out, "wb") as f:
                    writer.write(f)

                writer.close()
                procesados += 1

                if progress:
                    progress(idx, total_rangos)

    except CancelledByUser:
        logger.info("[PDF-EXTRAER] Cancelado por usuario")
        return build_cancelled_result(
            output_dir=salida_dir,
            total=1,
            procesados=procesados,
            errores=errores,
        )

    except Exception as e:
        errores += 1
        logger.error(f"[PDF-EXTRAER] Error: {e}")

    logger.info(
        f"[PDF-EXTRAER] Finalizado. Procesados: {procesados}. "
        f"Errores: {errores}"
    )

    return build_result(
        message="Proceso finalizado",
        output_dir=salida_dir,
        total=1,
        procesados=procesados,
        errores=errores,
    )