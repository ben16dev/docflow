# DEPRECATED — Fase 1: retirado del registro e interfaz de DocFlow.
# No volver a registrar en scripts/registry.py.
# Sustituto futuro: agrupación por patrón configurable.
SCRIPT_META = {
    "name": "Unir PDFs por DNI",
    "category": "PDF"
}

import re
import shutil
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

from pypdf import PdfWriter

from config import get_ruta
from ui.exceptions import CancelledByUser
from ui.ui_thread import call_ui
from ui.window_icon import set_window_icon
from logger import logger

from scripts.common.filenames import resolve_conflict, sanitize_filename_ascii
from scripts.common.results import build_result, build_cancelled_result


# ======================================================
# LIMPIEZA NOMBRE ARCHIVO
# ======================================================

def limpiar_nombre_archivo(texto: str, max_len: int = 120):
    """
    Wrapper local para mantener compatibilidad interna del script.
    """
    texto = sanitize_filename_ascii(
        texto,
        max_len=max_len,
        fallback="SALIDA"
    )
    return texto.replace(" ", "_")


# ======================================================
# VALIDACIÓN DNI / NIE
# ======================================================

LETRAS_DNI = "TRWAGMYFPDXBNJZSQVHLCKE"

dni_regex = re.compile(
    r"(?<![A-Za-z0-9])((?:\d{8}|[XYZxyz]\d{7})[A-Za-z])(?![A-Za-z0-9])"
)


def validar_dni(dni: str):
    numero = int(dni[:-1])
    letra = dni[-1]
    return LETRAS_DNI[numero % 23] == letra


def normalizar_nie(dni: str):
    if dni[0] in "XYZ":
        tabla = {"X": "0", "Y": "1", "Z": "2"}
        dni = tabla[dni[0]] + dni[1:]
    return dni


def extraer_dni_y_sufijo(nombre_archivo: str):
    """
    Extrae (dni_normalizado, sufijo) del nombre del archivo.

    sufijo: entero del trailing '_N' después del DNI (ej: 2 para '_2'), o None si no existe.
    Devuelve (None, None) si no se encuentra un DNI válido.

    Ejemplos:
        DOCUMENTO_MIGUEL_48999375Z.pdf      → ('48999375Z', None)
        DOCUMENTO_MIGUEL_48999375Z_2.pdf    → ('48999375Z', 2)
        RE_DOCUMENTO_MIGUEL_48999375Z_2.pdf → ('48999375Z', 2)
    """
    stem = Path(nombre_archivo).stem
    match = dni_regex.search(stem)

    if not match:
        return None, None

    dni = match.group(1).upper()
    dni_normalizado = normalizar_nie(dni)

    if not validar_dni(dni_normalizado):
        return None, None

    after_dni = stem[match.end():]
    sufijo_match = re.match(r'^_(\d+)$', after_dni)
    sufijo = int(sufijo_match.group(1)) if sufijo_match else None

    return dni_normalizado, sufijo


# ======================================================
# EXTRAER NOMBRE + DNI (para naming en modo custom)
# ======================================================

def extraer_nombre_persona(nombre_archivo: str):
    """
    Extrae la parte NOMBRE_DNI del stem, ignorando prefijos y el sufijo numérico (_2, _3...).
    """
    stem = Path(nombre_archivo).stem
    match = dni_regex.search(stem)

    if match:
        return stem[:match.end()]

    # Fallback: últimas dos partes separadas por '_'
    partes = stem.split("_")
    if len(partes) >= 2:
        return "_".join(partes[-2:])

    return stem


# ======================================================
# CONFIG DIÁLOGO
# ======================================================

class ConfigUnirDNI(tk.Toplevel):

    def __init__(self, parent):
        super().__init__(parent)
        set_window_icon(self)

        self.title("Unir PDFs por DNI")
        self.resizable(False, False)

        self.resultado = None

        self.var_modo_nombre = tk.StringVar(value="original")
        self.var_nombre_custom = tk.StringVar()

        frame = tk.Frame(self)
        frame.pack(padx=12, pady=12)

        tk.Label(
            frame,
            text="Nombre del archivo generado:"
        ).grid(row=0, column=0, sticky="w", columnspan=2)

        tk.Radiobutton(
            frame,
            text="Mantener nombre del PDF de Carpeta A",
            variable=self.var_modo_nombre,
            value="original",
            command=self._toggle
        ).grid(row=1, column=0, columnspan=2, sticky="w")

        tk.Radiobutton(
            frame,
            text="Nombre personalizado:",
            variable=self.var_modo_nombre,
            value="custom",
            command=self._toggle
        ).grid(row=2, column=0, sticky="w")

        self.entry_nombre = tk.Entry(
            frame,
            textvariable=self.var_nombre_custom,
            width=30,
            state="disabled"
        )
        self.entry_nombre.grid(row=2, column=1, sticky="w")

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

    def _toggle(self):
        if self.var_modo_nombre.get() == "custom":
            self.entry_nombre.config(state="normal")
        else:
            self.entry_nombre.config(state="disabled")

    def _aceptar(self):
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
            "modo_nombre": self.var_modo_nombre.get(),
            "nombre_personalizado": self.var_nombre_custom.get().strip()
        }
        self.destroy()

    def _cancelar(self):
        self.resultado = None
        self.destroy()


# ======================================================
# INDEXAR CARPETA B
# ======================================================

def indexar_pdfs_por_dni(carpeta_b: Path):
    """
    Indexa los PDFs de Carpeta B por clave (dni, sufijo).
    """
    indice = {}

    archivos = [
        f for f in carpeta_b.iterdir()
        if f.suffix.lower() == ".pdf"
    ]

    logger.info(f"[PDF-UNIR-DNI] Indexando {len(archivos)} PDFs de Carpeta B")

    for archivo in archivos:
        dni, sufijo = extraer_dni_y_sufijo(archivo.name)
        if not dni:
            continue
        clave = (dni, sufijo)
        indice.setdefault(clave, []).append(archivo)

    return indice


# ======================================================
# MOVER ARCHIVOS PROCESADOS
# ======================================================

def mover_a_procesados(archivos: list, carpeta_origen: Path):
    """
    Mueve los archivos procesados a '_procesados' dentro de su carpeta de origen.
    Los no procesados permanecen en la raíz de la carpeta para identificación visual.
    """
    destino = carpeta_origen / "_procesados"
    destino.mkdir(exist_ok=True)

    for archivo in archivos:
        try:
            dest_archivo = resolve_conflict(destino / archivo.name, pattern="_{i}")
            shutil.move(str(archivo), str(dest_archivo))
        except Exception as e:
            logger.warning(f"[PDF-UNIR-DNI] No se pudo mover {archivo.name}: {e}")


# ======================================================
# RUN
# ======================================================

def run(progress=None, is_cancelled=None):

    parent = call_ui(lambda: tk._get_default_root())

    cfg = call_ui(lambda: ConfigUnirDNI(parent).resultado)

    if not cfg:
        raise CancelledByUser()

    modo_nombre = cfg["modo_nombre"]
    nombre_custom = cfg["nombre_personalizado"]

    carpeta_a = call_ui(lambda: filedialog.askdirectory(
        title="Selecciona la Carpeta A",
        parent=parent
    ))

    if not carpeta_a:
        raise CancelledByUser()

    carpeta_b = call_ui(lambda: filedialog.askdirectory(
        title="Selecciona la Carpeta B",
        parent=parent
    ))

    if not carpeta_b:
        raise CancelledByUser()

    carpeta_a = Path(carpeta_a)
    carpeta_b = Path(carpeta_b)

    if not carpeta_a.is_dir() or not carpeta_b.is_dir():
        raise RuntimeError("Carpeta A o B no válida")

    base_dir_raw = get_ruta("pdf")

    if not base_dir_raw:
        raise RuntimeError("Ruta de trabajo PDF no válida")

    output_dir = Path(base_dir_raw) / "PDF_unidos"
    output_dir.mkdir(exist_ok=True)

    logger.info(f"[PDF-UNIR-DNI] Carpeta A: {carpeta_a}")
    logger.info(f"[PDF-UNIR-DNI] Carpeta B: {carpeta_b}")

    # Agrupar Carpeta A por clave (dni, sufijo)
    grupos = {}

    for archivo in carpeta_a.iterdir():
        if archivo.suffix.lower() != ".pdf":
            continue
        dni, sufijo = extraer_dni_y_sufijo(archivo.name)
        if not dni:
            logger.warning(f"[PDF-UNIR-DNI] Sin DNI válido, omitido: {archivo.name}")
            continue
        clave = (dni, sufijo)
        grupos.setdefault(clave, []).append(archivo)

    if not grupos:
        raise RuntimeError("No se encontraron PDFs con DNI válido en Carpeta A")

    total = len(grupos)
    procesados = 0
    omitidos = 0
    errores = 0

    logger.info(f"[PDF-UNIR-DNI] Claves (DNI + sufijo) detectadas: {total}")

    indice_b = indexar_pdfs_por_dni(carpeta_b)

    try:

        for idx, (clave, archivos_a) in enumerate(grupos.items(), start=1):

            if is_cancelled and is_cancelled():
                raise CancelledByUser()

            dni, sufijo = clave
            coincidencias_b = indice_b.get(clave)

            if not coincidencias_b:
                sufijo_str = f"_{sufijo}" if sufijo is not None else ""
                logger.info(
                    f"[PDF-UNIR-DNI] Sin pareja en Carpeta B para {dni}{sufijo_str}, omitido"
                )
                omitidos += 1
                continue

            writer = PdfWriter()

            try:

                for archivo in archivos_a:
                    writer.append(str(archivo))

                for archivo in coincidencias_b:
                    writer.append(str(archivo))

                nombre_original = limpiar_nombre_archivo(archivos_a[0].stem)

                if modo_nombre == "original":
                    nombre_final = f"{nombre_original}.pdf"
                else:
                    nombre_persona = limpiar_nombre_archivo(
                        extraer_nombre_persona(archivos_a[0].name)
                    )
                    nombre_custom_safe = limpiar_nombre_archivo(nombre_custom)
                    sufijo_str = f"_{sufijo}" if sufijo is not None else ""
                    nombre_final = f"{nombre_custom_safe}_{nombre_persona}{sufijo_str}.pdf"

                salida = resolve_conflict(
                    output_dir / nombre_final,
                    pattern="_{i}"
                )

                with open(salida, "wb") as f:
                    writer.write(f)

                writer.close()

                # Mover fuentes procesadas a _procesados dentro de cada carpeta
                mover_a_procesados(archivos_a, carpeta_a)
                mover_a_procesados(coincidencias_b, carpeta_b)

                procesados += 1

            except Exception as e:

                try:
                    writer.close()
                except Exception:
                    pass

                errores += 1
                logger.error(f"[PDF-UNIR-DNI] Error en DNI {dni}: {e}")
                continue

            if progress:
                progress(idx, total)

    except CancelledByUser:
        logger.info("[PDF-UNIR-DNI] Cancelado por usuario")
        return build_cancelled_result(
            output_dir=output_dir,
            total=total,
            procesados=procesados,
            errores=errores,
            omitidos=omitidos,
        )

    logger.info(
        f"[PDF-UNIR-DNI] Finalizado. "
        f"Procesados: {procesados}. "
        f"Omitidos: {omitidos}. "
        f"Errores: {errores}"
    )

    return build_result(
        message="Proceso finalizado",
        output_dir=output_dir,
        total=total,
        procesados=procesados,
        errores=errores,
        omitidos=omitidos,
    )
