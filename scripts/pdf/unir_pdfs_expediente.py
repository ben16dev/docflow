SCRIPT_META = {
    "name": "Unir PDFs por Expediente",
    "category": "PDF"
}

import re
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

from pypdf import PdfReader, PdfWriter

from ui.exceptions import CancelledByUser
from ui.ui_thread import call_ui
from ui.window_icon import set_window_icon
from logger import logger

from scripts.common.filenames import resolve_conflict, sanitize_filename
from scripts.common.results import build_result, build_cancelled_result


class ConfigUnirExpediente(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        set_window_icon(self)

        self.title("Unir PDFs por expediente")
        self.resizable(False, False)

        self.resultado = None

        self.var_base = tk.StringVar()
        self.var_sec = tk.StringVar()
        self.var_patron = tk.StringVar(value="EXP")

        self.var_modo_nombre = tk.StringVar(value="original")
        self.var_nombre_custom = tk.StringVar()

        frame = tk.Frame(self)
        frame.pack(padx=12, pady=12)

        tk.Label(frame, text="Carpeta base:").grid(row=0, column=0, sticky="w")
        tk.Entry(frame, textvariable=self.var_base, width=40).grid(row=0, column=1)
        tk.Button(
            frame,
            text="Seleccionar",
            command=self._sel_base
        ).grid(row=0, column=2, padx=5)

        tk.Label(
            frame,
            text="Carpeta secundaria:"
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))
        tk.Entry(
            frame,
            textvariable=self.var_sec,
            width=40
        ).grid(row=1, column=1, pady=(8, 0))
        tk.Button(
            frame,
            text="Seleccionar",
            command=self._sel_sec
        ).grid(row=1, column=2, padx=5, pady=(8, 0))

        tk.Label(
            frame,
            text="Patrón expediente:"
        ).grid(row=2, column=0, sticky="w", pady=(8, 0))
        tk.Entry(
            frame,
            textvariable=self.var_patron
        ).grid(row=2, column=1, sticky="w", pady=(8, 0))

        tk.Label(
            frame,
            text="Nombre del archivo generado:"
        ).grid(row=3, column=0, sticky="w", pady=(12, 0), columnspan=3)

        tk.Radiobutton(
            frame,
            text="Mantener nombre del PDF base",
            variable=self.var_modo_nombre,
            value="original",
            command=self._toggle_nombre
        ).grid(row=4, column=0, columnspan=3, sticky="w")

        tk.Radiobutton(
            frame,
            text="Nombre personalizado:",
            variable=self.var_modo_nombre,
            value="custom",
            command=self._toggle_nombre
        ).grid(row=5, column=0, sticky="w")

        self.entry_nombre = tk.Entry(
            frame,
            textvariable=self.var_nombre_custom,
            width=30,
            state="disabled"
        )
        self.entry_nombre.grid(row=5, column=1, sticky="w")

        btns = tk.Frame(self)
        btns.pack(pady=10)

        tk.Button(
            btns,
            text="Cancelar",
            command=self._cancelar
        ).pack(side="left", padx=5)

        tk.Button(
            btns,
            text="Aceptar",
            command=self._aceptar
        ).pack(side="right", padx=5)

        self.transient(parent)
        self.grab_set()
        self.wait_window()

    def _toggle_nombre(self):
        self.entry_nombre.config(
            state="normal"
            if self.var_modo_nombre.get() == "custom"
            else "disabled"
        )

    def _sel_base(self):
        ruta = filedialog.askdirectory(parent=self)
        if ruta:
            self.var_base.set(ruta)

    def _sel_sec(self):
        ruta = filedialog.askdirectory(parent=self)
        if ruta:
            self.var_sec.set(ruta)

    def _aceptar(self):
        base = Path(self.var_base.get())
        sec = Path(self.var_sec.get())
        patron = self.var_patron.get().strip()

        if not base.is_dir():
            messagebox.showerror("Error", "Carpeta base inválida", parent=self)
            return

        if not sec.is_dir():
            messagebox.showerror(
                "Error",
                "Carpeta secundaria inválida",
                parent=self
            )
            return

        if not patron:
            messagebox.showerror(
                "Error",
                "Introduce un patrón de expediente",
                parent=self
            )
            return

        if (
            self.var_modo_nombre.get() == "custom"
            and not self.var_nombre_custom.get().strip()
        ):
            messagebox.showerror(
                "Error",
                "Introduce un nombre personalizado",
                parent=self
            )
            return

        self.resultado = {
            "carpeta_base": base,
            "carpeta_secundaria": sec,
            "patron": patron,
            "modo_nombre": self.var_modo_nombre.get(),
            "nombre_personalizado": self.var_nombre_custom.get().strip()
        }

        self.destroy()

    def _cancelar(self):
        self.resultado = None
        self.destroy()


def _normalizar(texto: str):
    return texto.lower().replace(" ", "").replace("_", "-")


def extraer_numero_expediente(nombre_archivo: str, patron: str):
    nombre_norm = _normalizar(nombre_archivo)
    patron_norm = _normalizar(patron)

    regex = rf"{re.escape(patron_norm)}[-]?(\d{{1,3}})"
    match = re.search(regex, nombre_norm)

    if not match:
        return None

    numero = int(match.group(1))
    return numero if 1 <= numero <= 999 else None


def indexar_pdfs_secundarios(carpeta_secundaria: Path, patron: str):
    indice = {}
    archivos = [
        f for f in carpeta_secundaria.iterdir()
        if f.suffix.lower() == ".pdf"
    ]

    logger.info(f"[PDF-UNIR-EXP] Indexando {len(archivos)} PDFs secundarios")

    for pdf in archivos:
        numero = extraer_numero_expediente(pdf.name, patron)
        if numero is not None:
            indice.setdefault(numero, []).append(pdf)

    return indice


def run(progress=None, is_cancelled=None):

    parent = call_ui(lambda: tk._get_default_root())
    cfg = call_ui(lambda: ConfigUnirExpediente(parent).resultado)

    if not cfg:
        raise CancelledByUser()

    carpeta_base = cfg["carpeta_base"]
    carpeta_sec = cfg["carpeta_secundaria"]
    patron = cfg["patron"]
    modo_nombre = cfg["modo_nombre"]
    nombre_custom = cfg["nombre_personalizado"]

    salida = carpeta_base.parent / "PDF_unidos_expediente"
    salida.mkdir(exist_ok=True)

    bases = sorted(
        f for f in carpeta_base.iterdir()
        if f.suffix.lower() == ".pdf"
    )

    total = len(bases)
    procesados = 0
    omitidos = 0
    errores = 0

    logger.info(f"[PDF-UNIR-EXP] PDFs base detectados: {total}")

    indice_secundarios = indexar_pdfs_secundarios(carpeta_sec, patron)

    try:

        for i, pdf_base in enumerate(bases, start=1):

            if is_cancelled and is_cancelled():
                raise CancelledByUser()

            try:
                numero = extraer_numero_expediente(pdf_base.name, patron)

                if numero is None:
                    omitidos += 1
                    continue

                secundarios = indice_secundarios.get(numero)
                if not secundarios:
                    omitidos += 1
                    continue

                writer = PdfWriter()

                try:
                    with open(pdf_base, "rb") as f:
                        reader_base = PdfReader(f)
                        for p in reader_base.pages:
                            writer.add_page(p)

                    for sec in sorted(secundarios):
                        with open(sec, "rb") as f:
                            reader_sec = PdfReader(f)
                            for p in reader_sec.pages:
                                writer.add_page(p)

                    if modo_nombre == "original":
                        nombre_archivo = sanitize_filename(
                            pdf_base.name,
                            max_len=150,
                            fallback="PDF_unido.pdf"
                        )
                    else:
                        nombre_custom_safe = sanitize_filename(
                            nombre_custom,
                            max_len=80,
                            fallback="PDF_unido"
                        )
                        base_safe = sanitize_filename(
                            pdf_base.stem,
                            max_len=100,
                            fallback="base"
                        )
                        nombre_archivo = f"{nombre_custom_safe}_{base_safe}.pdf"

                    destino = resolve_conflict(
                        salida / nombre_archivo,
                        pattern="_v{i}"
                    )

                    with open(destino, "wb") as f:
                        writer.write(f)

                    writer.close()

                    procesados += 1

                except Exception:
                    try:
                        writer.close()
                    except Exception:
                        pass
                    raise

            except Exception as e:
                errores += 1
                logger.error(f"[PDF-UNIR-EXP] Error en {pdf_base.name}: {e}")
                continue

            if progress:
                progress(i, total)

    except CancelledByUser:
        logger.info("[PDF-UNIR-EXP] Cancelado por usuario")
        return build_cancelled_result(
            output_dir=salida,
            total=total,
            procesados=procesados,
            errores=errores,
            omitidos=omitidos,
        )

    logger.info(
        f"[PDF-UNIR-EXP] Finalizado | "
        f"Total: {total} | "
        f"Procesados: {procesados} | "
        f"Omitidos: {omitidos} | "
        f"Errores: {errores}"
    )

    return build_result(
        message="Proceso finalizado",
        output_dir=salida,
        total=total,
        procesados=procesados,
        errores=errores,
        omitidos=omitidos,
    )





