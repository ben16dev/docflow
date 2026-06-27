SCRIPT_META = {
    "name": "Unir PDFs por Orden Manual",
    "category": "PDF"
}

import os
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from config import get_ruta
from ui.exceptions import CancelledByUser
from ui.ui_thread import call_ui
from ui.window_icon import set_window_icon
from logger import logger

from scripts.common.filenames import resolve_conflict, sanitize_filename
from scripts.common.results import build_result, build_cancelled_result


class OrdenUnirPDFs(tk.Toplevel):
    def __init__(self, parent, archivos):
        super().__init__(parent)
        set_window_icon(self)

        self.title("Unir PDFs (orden manual)")
        self.geometry("620x500")
        self.resizable(False, False)

        self.archivos = archivos
        self.resultado = None
        self.vars = []

        tk.Label(
            self,
            text="Marca los PDFs a unir y ordénalos",
            font=("Segoe UI", 11, "bold")
        ).pack(pady=10)

        frame_lista = tk.Frame(self)
        frame_lista.pack(fill="both", expand=True, padx=10)

        canvas = tk.Canvas(frame_lista)
        scrollbar = tk.Scrollbar(
            frame_lista,
            orient="vertical",
            command=canvas.yview
        )
        self.inner = tk.Frame(canvas)

        self.inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for f in archivos:
            var = tk.BooleanVar(value=False)
            chk = tk.Checkbutton(
                self.inner,
                text=f.name,
                variable=var,
                anchor="w"
            )
            chk.pack(fill="x", padx=5)
            self.vars.append((var, f.name))

        frame_btns = tk.Frame(self)
        frame_btns.pack(pady=6)

        tk.Button(
            frame_btns,
            text="↑ Subir",
            width=10,
            command=self._subir
        ).pack(side="left", padx=5)

        tk.Button(
            frame_btns,
            text="↓ Bajar",
            width=10,
            command=self._bajar
        ).pack(side="left", padx=5)

        frame_nombre = tk.Frame(self)
        frame_nombre.pack(fill="x", padx=12, pady=10)

        self.var_usar_primero = tk.BooleanVar(value=True)

        tk.Checkbutton(
            frame_nombre,
            text="Usar nombre del primer PDF marcado",
            variable=self.var_usar_primero,
            command=self._toggle_nombre
        ).pack(anchor="w")

        self.entry_nombre = tk.Entry(frame_nombre, state="disabled")
        self.entry_nombre.pack(fill="x", pady=4)

        frame_final = tk.Frame(self)
        frame_final.pack(pady=10)

        tk.Button(
            frame_final,
            text="Cancelar",
            width=12,
            command=self._cancelar
        ).pack(side="left", padx=10)

        tk.Button(
            frame_final,
            text="Unir PDFs",
            width=14,
            command=self._confirmar
        ).pack(side="right", padx=10)

        self.transient(parent)
        self.grab_set()
        self.wait_window()

    def _subir(self):
        for i in range(1, len(self.vars)):
            var, _ = self.vars[i]
            prev_var, _ = self.vars[i - 1]
            if var.get() and not prev_var.get():
                self.vars[i - 1], self.vars[i] = self.vars[i], self.vars[i - 1]
                self._rebuild()
                break

    def _bajar(self):
        for i in range(len(self.vars) - 2, -1, -1):
            var, _ = self.vars[i]
            next_var, _ = self.vars[i + 1]
            if var.get() and not next_var.get():
                self.vars[i + 1], self.vars[i] = self.vars[i], self.vars[i + 1]
                self._rebuild()
                break

    def _rebuild(self):
        for w in self.inner.winfo_children():
            w.destroy()

        for var, name in self.vars:
            chk = tk.Checkbutton(
                self.inner,
                text=name,
                variable=var,
                anchor="w"
            )
            chk.pack(fill="x", padx=5)

    def _toggle_nombre(self):
        self.entry_nombre.config(
            state="disabled" if self.var_usar_primero.get() else "normal"
        )

    def _confirmar(self):
        seleccionados = [name for var, name in self.vars if var.get()]

        if len(seleccionados) < 2:
            messagebox.showerror(
                "Selección insuficiente",
                "Debes marcar al menos dos PDFs para unir.",
                parent=self
            )
            return

        nombre = None
        if not self.var_usar_primero.get():
            nombre = self.entry_nombre.get().strip()
            if not nombre:
                messagebox.showerror(
                    "Nombre requerido",
                    "Introduce un nombre para el PDF final.",
                    parent=self
                )
                return

        self.resultado = {
            "orden": seleccionados,
            "usar_primero": self.var_usar_primero.get(),
            "nombre": nombre,
        }
        self.destroy()

    def _cancelar(self):
        self.resultado = None
        self.destroy()


# ======================================================
# RUN
# ======================================================

def run(progress=None, is_cancelled=None):

    ruta_raw = get_ruta("pdf")
    if not ruta_raw or not os.path.isdir(ruta_raw):
        raise RuntimeError("No se ha seleccionado una carpeta PDF válida")

    carpeta = Path(ruta_raw)
    pdfs = sorted(p for p in carpeta.iterdir() if p.suffix.lower() == ".pdf")

    if len(pdfs) < 2:
        raise RuntimeError("Se necesitan al menos dos PDFs en la carpeta")

    parent = call_ui(lambda: tk._get_default_root())

    dialog_res = call_ui(lambda: OrdenUnirPDFs(parent, pdfs).resultado)
    if not dialog_res:
        raise CancelledByUser()

    orden = dialog_res["orden"]
    usar_primero = dialog_res["usar_primero"]
    nombre_custom = dialog_res["nombre"]

    salida = carpeta / "PDF_unidos"
    salida.mkdir(exist_ok=True)

    nombre_final = Path(orden[0]).stem if usar_primero else nombre_custom
    nombre_final = sanitize_filename(
        nombre_final,
        max_len=120,
        fallback="PDF_unido"
    )

    pdf_salida = resolve_conflict(
        salida / f"{nombre_final}.pdf",
        pattern="_v{i}"
    )

    writer = PdfWriter()

    total = len(orden)
    procesados = 0
    errores = 0

    logger.info(f"[PDF-UNIR-ORDEN] Uniendo {total} PDFs")

    try:

        for i, fname in enumerate(orden, start=1):

            if is_cancelled and is_cancelled():
                raise CancelledByUser()

            try:
                pdf_path = carpeta / fname

                with open(pdf_path, "rb") as f:
                    reader = PdfReader(f)
                    for page in reader.pages:
                        writer.add_page(page)

                procesados += 1

            except Exception as e:
                errores += 1
                logger.error(f"[PDF-UNIR-ORDEN] Error en {fname}: {e}")
                continue

            if progress:
                progress(i, total)

        try:
            with open(pdf_salida, "wb") as f:
                writer.write(f)

            writer.close()

        except Exception as e:
            logger.error(f"[PDF-UNIR-ORDEN] Error guardando resultado: {e}")
            raise RuntimeError("No se pudo guardar el PDF final.")

    except CancelledByUser:
        logger.info("[PDF-UNIR-ORDEN] Cancelado por usuario")

        try:
            writer.close()
        except Exception:
            pass

        return build_cancelled_result(
            output_dir=salida,
            total=total,
            procesados=procesados,
            errores=errores,
        )

    logger.info(
        f"[PDF-UNIR-ORDEN] Finalizado. "
        f"Procesados: {procesados}. "
        f"Errores: {errores}"
    )

    return build_result(
        message="Proceso finalizado",
        output_dir=salida,
        total=total,
        procesados=procesados,
        errores=errores,
    )






