SCRIPT_META = {
    "name": "Censurar PDF por palabras",
    "category": "PDF"
}

import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP

from config import get_ruta
from ui.exceptions import CancelledByUser
from ui.ui_thread import call_ui
from ui.window_icon import set_window_icon
from logger import logger

from scripts.common.filenames import resolve_conflict
from scripts.common.pdf_ranges import parse_ranges, ranges_to_pages_set
from scripts.common.results import build_result, build_cancelled_result

try:
    import fitz  # pymupdf
except Exception:
    fitz = None


# ======================================================
# UTILIDADES IMPORTES
# ======================================================

def _extraer_texto_pdf(path: Path) -> str:
    if fitz is None:
        raise RuntimeError("Falta dependencia 'pymupdf'.")

    doc = fitz.open(str(path))
    texto = ""

    try:
        for page in doc:
            texto += page.get_text()
    finally:
        doc.close()

    return texto


def _parse_euro(valor_str: str) -> Decimal:
    limpio = valor_str.replace("€", "").strip()
    limpio = limpio.replace(".", "").replace(",", ".")
    return Decimal(limpio)


def _format_euro(valor: Decimal) -> str:
    valor = valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    s = f"{valor:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} €"


def _extraer_importe_base(texto: str):
    match = re.search(
        r"Siendo\s+([\d\.,]+\s?€)\s+lo pagado",
        texto,
        re.IGNORECASE
    )
    return match.group(1) if match else None


def _detectar_importes_auto(texto: str):
    base_str = _extraer_importe_base(texto)

    if not base_str:
        return []

    try:
        base = _parse_euro(base_str)
    except Exception:
        return []

    imp_15 = _format_euro(base * Decimal("0.15"))
    imp_85 = _format_euro(base * Decimal("0.85"))

    encontrados = []

    for imp in [imp_15, imp_85]:
        if imp in texto:
            encontrados.append(imp)

    return encontrados


# ======================================================
# DIÁLOGO UI
# ======================================================

class CensurarDialog(tk.Toplevel):

    def __init__(self, parent):
        super().__init__(parent)
        set_window_icon(self)

        self.title("Censurar información en PDF")
        self.geometry("680x500")
        self.resizable(False, False)

        self.resultado = None

        self.var_todas = tk.BooleanVar(value=True)
        self.var_rango = tk.StringVar(value="1")

        tk.Label(
            self,
            text="Introduce las palabras o expresiones a censurar (una por línea)",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", padx=12, pady=(12, 6))

        self.txt_words = tk.Text(self, height=8)
        self.txt_words.pack(fill="both", padx=12, pady=(0, 8))

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
        }

        self.destroy()

    def _cancelar(self):
        self.resultado = None
        self.destroy()


# ======================================================
# LÓGICA PDF
# ======================================================

def _censurar_pdf(
    input_path: Path,
    output_path: Path,
    words,
    pages_to_process,
    is_cancelled=None
):

    if fitz is None:
        raise RuntimeError("Falta dependencia 'pymupdf'.")

    texto = _extraer_texto_pdf(input_path)
    auto_words = _detectar_importes_auto(texto)

    if auto_words:
        logger.info(f"[PDF-CENSURA] Importes detectados: {auto_words}")

    palabras_finales = list(set(words + auto_words))

    doc = fitz.open(str(input_path))

    try:
        for page_index in range(doc.page_count):

            if is_cancelled and is_cancelled():
                raise CancelledByUser()

            page_num = page_index + 1
            if page_num not in pages_to_process:
                continue

            page = doc.load_page(page_index)

            for term in palabras_finales:
                rects = page.search_for(term)
                for r in rects:
                    page.add_redact_annot(r, fill=(0, 0, 0))

            page.apply_redactions()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path), garbage=4, deflate=True)

    finally:
        doc.close()


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

    words = cfg["words"]

    salida_dir = pdf_paths[0].parent / "PDF_censurados"
    salida_dir.mkdir(exist_ok=True)

    total = len(pdf_paths)
    procesados = 0
    errores = 0

    logger.info(f"[PDF-CENSURA] Procesando {total} PDF(s)")

    try:

        for idx, pdf_path in enumerate(pdf_paths, start=1):

            if is_cancelled and is_cancelled():
                raise CancelledByUser()

            try:
                doc = fitz.open(str(pdf_path))
                try:
                    max_pages = doc.page_count
                finally:
                    doc.close()

                if cfg["all_pages"]:
                    pages = set(range(1, max_pages + 1))
                else:
                    pages = ranges_to_pages_set(cfg["ranges"], max_pages)

                out_path = resolve_conflict(
                    salida_dir / f"{pdf_path.stem}_censurado.pdf",
                    pattern="_{i:02d}"
                )

                _censurar_pdf(pdf_path, out_path, words, pages, is_cancelled)

                procesados += 1

            except CancelledByUser:
                raise

            except Exception as e:
                errores += 1
                logger.error(f"[PDF-CENSURA] Error en {pdf_path.name}: {e}")

            if progress:
                progress(idx, total)

    except CancelledByUser:
        logger.info("[PDF-CENSURA] Cancelado por usuario")
        return build_cancelled_result(
            output_dir=salida_dir,
            total=total,
            procesados=procesados,
            errores=errores,
        )

    logger.info(
        f"[PDF-CENSURA] Finalizado. "
        f"Procesados: {procesados}. "
        f"Errores: {errores}. "
        f"Omitidos: {total - procesados - errores}"
    )

    return build_result(
        message=f"{procesados} PDF(s) censurado(s)",
        output_dir=salida_dir,
        total=total,
        procesados=procesados,
        errores=errores,
    )


