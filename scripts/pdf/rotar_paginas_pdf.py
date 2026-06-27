SCRIPT_META = {
    "name": "Rotar páginas PDF",
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
from scripts.common.pdf_ranges import parse_ranges, ranges_to_pages_set
from scripts.common.results import build_result, build_cancelled_result


class RotarPaginasDialog(tk.Toplevel):

    def __init__(self, parent):
        super().__init__(parent)
        set_window_icon(self)
        self.title("Rotar páginas PDF")
        self.resizable(False, False)

        self.resultado = None

        self.var_grados = tk.IntVar(value=90)
        self.var_todas = tk.BooleanVar(value=True)
        self.var_rangos = tk.StringVar(value="")
        self.var_usar_original = tk.BooleanVar(value=True)
        self.var_nombre = tk.StringVar(value="PDF_rotado")

        main = ttk.Frame(self, padding=12)
        main.pack(fill="both", expand=True)

        lf1 = ttk.LabelFrame(main, text="Rotación", padding=10)
        lf1.pack(fill="x")

        row = ttk.Frame(lf1)
        row.pack(fill="x")
        ttk.Label(row, text="Grados:").pack(side="left")

        grados_values = [90, 180, 270]
        self.cmb_grados = ttk.Combobox(
            row,
            width=8,
            state="readonly",
            values=[str(v) for v in grados_values],
        )
        self.cmb_grados.set(str(self.var_grados.get()))
        self.cmb_grados.pack(side="left", padx=8)

        lf2 = ttk.LabelFrame(main, text="Páginas", padding=10)
        lf2.pack(fill="x", pady=(10, 0))

        ttk.Checkbutton(
            lf2,
            text="Rotar todas las páginas",
            variable=self.var_todas,
            command=self._toggle_rangos_state,
        ).pack(anchor="w")

        row2 = ttk.Frame(lf2)
        row2.pack(fill="x", pady=(6, 0))

        ttk.Label(
            row2,
            text="Rangos (ej: 1-3, 5, 8-10):"
        ).pack(side="left")

        self.ent_rangos = ttk.Entry(
            row2,
            textvariable=self.var_rangos,
            width=26
        )
        self.ent_rangos.pack(side="left", padx=8)

        lf3 = ttk.LabelFrame(main, text="Nombre de salida", padding=10)
        lf3.pack(fill="x", pady=(10, 0))

        ttk.Checkbutton(
            lf3,
            text="Usar nombre original",
            variable=self.var_usar_original,
            command=self._toggle_nombre_state,
        ).pack(anchor="w")

        row3 = ttk.Frame(lf3)
        row3.pack(fill="x", pady=(6, 0))

        ttk.Label(row3, text="Prefijo:").pack(side="left")

        self.ent_nombre = ttk.Entry(
            row3,
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
        try:
            grados = int(self.cmb_grados.get().strip())
            if grados not in (90, 180, 270):
                raise ValueError
        except Exception:
            messagebox.showerror(
                "Error",
                "Selecciona una rotación válida.",
                parent=self
            )
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
        nombre = self.var_nombre.get().strip()

        self.resultado = {
            "grados": grados,
            "todas": todas,
            "rangos": rangos,
            "usar_original": usar_original,
            "nombre": sanitize_filename(
                nombre,
                max_len=120,
                fallback="PDF_rotado"
            ) if nombre else "",
        }
        self.destroy()

    def _on_cancel(self):
        self.resultado = None
        self.destroy()


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

    res = call_ui(lambda: RotarPaginasDialog(parent).resultado)
    if not res:
        raise CancelledByUser()

    grados = res["grados"]

    salida_dir = pdf_paths[0].parent / "PDF_rotados"
    salida_dir.mkdir(exist_ok=True)

    total_files = len(pdf_paths)
    procesados = 0
    errores = 0

    logger.info(
        f"[PDF-ROTAR] Procesando {total_files} PDF(s) - Rotación {grados}°"
    )

    try:

        for idx, pdf_path in enumerate(pdf_paths, start=1):

            if is_cancelled and is_cancelled():
                raise CancelledByUser()

            try:
                writer = PdfWriter()

                with open(pdf_path, "rb") as f:
                    reader = PdfReader(f)
                    total_pages = len(reader.pages)

                    if res["todas"]:
                        paginas_a_rotar = set(range(1, total_pages + 1))
                    else:
                        try:
                            paginas_a_rotar = ranges_to_pages_set(
                                res["rangos"],
                                total_pages
                            )
                        except ValueError:
                            raise RuntimeError(
                                f"El PDF '{pdf_path.name}' tiene {total_pages} páginas."
                            )

                    for i, page in enumerate(reader.pages, start=1):
                        if is_cancelled and is_cancelled():
                            raise CancelledByUser()

                        if i in paginas_a_rotar:
                            page.rotate(grados)

                        writer.add_page(page)

                if res["usar_original"]:
                    nombre_base = pdf_path.stem
                else:
                    nombre_base = f"{res['nombre']}_{idx:02d}"

                nombre_safe = sanitize_filename(
                    nombre_base,
                    max_len=120,
                    fallback="PDF_rotado"
                )

                out_path = resolve_conflict(
                    salida_dir / f"{nombre_safe}.pdf",
                    pattern="_v{i}"
                )

                with open(out_path, "wb") as f:
                    writer.write(f)

                writer.close()

                procesados += 1

            except CancelledByUser:
                raise

            except Exception as e:
                errores += 1
                logger.error(f"[PDF-ROTAR] Error en {pdf_path.name}: {e}")
                continue

            if progress:
                progress(idx, total_files)

    except CancelledByUser:
        logger.info("[PDF-ROTAR] Cancelado por usuario")
        return build_cancelled_result(
            output_dir=salida_dir,
            total=total_files,
            procesados=procesados,
            errores=errores,
        )

    logger.info(
        f"[PDF-ROTAR] Finalizado. "
        f"Procesados: {procesados}. "
        f"Errores: {errores}. "
        f"Omitidos: {total_files - procesados - errores}"
    )

    return build_result(
        message="Proceso finalizado",
        output_dir=salida_dir,
        total=total_files,
        procesados=procesados,
        errores=errores,
    )
