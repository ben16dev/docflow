import re
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

from docx import Document

from config import get_ruta
from ui.exceptions import CancelledByUser
from ui.ui_thread import call_ui
from ui.window_icon import set_window_icon
from logger import logger

from scripts.common.filenames import sanitize_filename
from scripts.common.results import build_result, build_cancelled_result


class SelectorIndice(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        set_window_icon(self)

        self.title("Seleccionar índice Word")
        self.geometry("520x180")
        self.resizable(False, False)

        self.resultado = None

        tk.Label(
            self,
            text="Selecciona el documento Word con el índice",
            font=("Segoe UI", 11, "bold")
        ).pack(pady=(15, 8))

        frame = tk.Frame(self)
        frame.pack(fill="x", padx=12)

        self.var_docx = tk.StringVar()

        tk.Entry(frame, textvariable=self.var_docx)\
            .pack(side="left", fill="x", expand=True, padx=(0, 6))

        tk.Button(
            frame,
            text="Seleccionar Word",
            command=self._seleccionar
        ).pack(side="left")

        frame_btn = tk.Frame(self)
        frame_btn.pack(pady=18)

        tk.Button(
            frame_btn,
            text="Cancelar",
            width=12,
            command=self._cancelar
        ).pack(side="left", padx=10)

        tk.Button(
            frame_btn,
            text="Aceptar",
            width=12,
            command=self._confirmar
        ).pack(side="right", padx=10)

        self.transient(parent)
        self.grab_set()
        self.wait_window()

    def _seleccionar(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar índice Word",
            filetypes=[("Documentos Word", "*.docx")],
            parent=self
        )
        if ruta:
            self.var_docx.set(ruta)

    def _confirmar(self):
        ruta = self.var_docx.get().strip()
        if not ruta or not Path(ruta).is_file():
            messagebox.showerror(
                "Error",
                "Selecciona un archivo Word válido.",
                parent=self
            )
            return

        self.resultado = ruta
        self.destroy()

    def _cancelar(self):
        self.resultado = None
        self.destroy()


# ======================================================
# UTILIDADES
# ======================================================

def _leer_indice_word(ruta_word: Path):
    try:
        doc = Document(str(ruta_word))
    except Exception:
        raise RuntimeError(
            "No se pudo abrir el documento Word. "
            "Comprueba que no esté dañado o en uso."
        )

    entradas = []
    for p in doc.paragraphs:
        texto = p.text.strip()
        if not texto:
            continue
        if texto.lower() == "indice":
            continue

        texto = re.sub(
            r"^documento\s+\d+\s*[.\-:]\s*",
            "",
            texto,
            flags=re.I
        )
        entradas.append(texto)

    return entradas


def _indexar_pdfs_por_prefijo(carpeta: Path, prefijos):
    """
    Un solo pase sobre la carpeta: mapa prefijo -> Path y lista de PDFs.
    Conserva el criterio original (primer PDF en orden de iterdir por prefijo).
    """
    pdfs = []
    indice = {}
    prefijos_pendientes = set(prefijos)

    for f in carpeta.iterdir():
        if f.suffix.lower() != ".pdf":
            continue
        pdfs.append(f)
        if not prefijos_pendientes:
            continue
        for prefijo in list(prefijos_pendientes):
            if f.name.startswith(prefijo):
                indice[prefijo] = f
                prefijos_pendientes.discard(prefijo)

    return indice, pdfs


# ======================================================
# RUN
# ======================================================

def run(progress=None, is_cancelled=None):

    ruta_raw = get_ruta("pdf")
    if not ruta_raw:
        raise RuntimeError("No se ha seleccionado ninguna carpeta de PDFs")

    carpeta_base = Path(ruta_raw)
    if not carpeta_base.exists() or not carpeta_base.is_dir():
        raise RuntimeError("La carpeta seleccionada no es válida")

    parent = call_ui(lambda: tk._get_default_root())

    ruta_word = call_ui(lambda: SelectorIndice(parent).resultado)
    if not ruta_word:
        raise CancelledByUser()

    ruta_word = Path(ruta_word)
    entradas = _leer_indice_word(ruta_word)

    if not entradas:
        raise RuntimeError("El índice Word no contiene entradas válidas")

    carpeta_salida = carpeta_base / "PDF_renombrados_indice"
    carpeta_salida.mkdir(exist_ok=True)

    esperados = {
        f"{i:02d}": titulo
        for i, titulo in enumerate(entradas, start=1)
    }
    encontrados = {}

    indice_pdfs, pdfs_en_carpeta = _indexar_pdfs_por_prefijo(
        carpeta_base,
        esperados.keys(),
    )

    total = len(esperados)
    procesados = 0
    errores = 0

    logger.info(f"[PDF-RENOMBRAR] Esperados según índice: {total}")

    try:

        for i, (num, titulo) in enumerate(esperados.items(), start=1):

            if is_cancelled and is_cancelled():
                raise CancelledByUser()

            if progress:
                progress(i, total)

            try:
                pdf = indice_pdfs.get(num)
                if not pdf:
                    continue

                encontrados[num] = pdf.name

                nombre_limpio = sanitize_filename(
                    titulo,
                    max_len=150,
                    fallback="documento"
                )
                nuevo_nombre = f"{num} {nombre_limpio}.pdf"

                shutil.copy2(
                    pdf,
                    carpeta_salida / nuevo_nombre
                )

                procesados += 1

            except Exception as e:
                errores += 1
                logger.error(f"[PDF-RENOMBRAR] Error con {num}: {e}")
                continue

    except CancelledByUser:
        logger.info("[PDF-RENOMBRAR] Cancelado por usuario")
        return build_cancelled_result(
            output_dir=carpeta_salida,
            total=total,
            procesados=procesados,
            errores=errores,
        )

    if progress:
        progress(total, total)

    omitidos = total - procesados - errores

    faltantes = [
        f"{num} → {titulo}"
        for num, titulo in esperados.items()
        if num not in encontrados
    ]

    pdfs_usados = set(indice_pdfs.values())
    sobrantes = [
        f.name for f in pdfs_en_carpeta
        if f not in pdfs_usados
    ]

    mensaje = [f"PDFs generados: {procesados}"]

    if faltantes:
        mensaje.append("\nFaltan PDFs para:")
        mensaje.extend(f"- {f}" for f in faltantes)

    if sobrantes:
        mensaje.append("\nPDFs sin entrada en el índice:")
        mensaje.extend(f"- {f}" for f in sobrantes)

    mensaje.append("\nCarpeta de salida:")
    mensaje.append(str(carpeta_salida))

    call_ui(lambda: messagebox.showinfo(
        "Resultado – Renombrar PDFs según índice Word",
        "\n".join(mensaje),
        parent=parent
    ))

    logger.info(
        f"[PDF-RENOMBRAR] Finalizado. "
        f"Procesados: {procesados}. "
        f"Omitidos: {omitidos}. "
        f"Errores: {errores}"
    )

    return build_result(
        message="Proceso finalizado",
        output_dir=carpeta_salida,
        total=total,
        procesados=procesados,
        errores=errores,
        omitidos=omitidos,
    )




