SCRIPT_META = {
    "name": "Nuevo cliente",
    "category": "PDF"
}

import re
import shutil
import unicodedata
from pathlib import Path
from typing import Optional, Dict, Any, List

import tkinter as tk
from tkinter import messagebox

from openpyxl import load_workbook

from ui.ui_thread import call_ui
from ui.window_icon import set_window_icon
from ui.exceptions import CancelledByUser
from logger import logger

from scripts.common.filenames import sanitize_filename
from scripts.common.results import build_result


# ======================================================
# RUTAS (M:\)
# ======================================================

NUEVOS_CLIENTES_BASE = Path(
    r"M:\2.1 Clientes Archivo Asuntos\01491 CALIDAD\ORDENADO\BANCARIO\00_GENERAL\++NUEVOS CLIENTES"
)

PLANTILLA_DIR = Path(
    r"M:\2.1 Clientes Archivo Asuntos\01491 CALIDAD\ORDENADO\BANCARIO\00_GENERAL\00_DOC PREVIA NUEVOS CLIENTES"
)

PROCURADORES_DIR = Path(
    r"M:\2.1 Clientes Archivo Asuntos\01491 CALIDAD\ORDENADO\BANCARIO\00_GENERAL\05_PROCURADORES (PPP)\MINUTAS"
)


# ======================================================
# UTILIDADES
# ======================================================

def _ensure_dir_accessible(p: Path, what: str) -> None:
    if not p.exists():
        raise RuntimeError(f"No existe la ruta de {what}:\n{p}")
    if not p.is_dir():
        raise RuntimeError(f"La ruta de {what} no es una carpeta:\n{p}")


def _tokens_upper(s: str) -> List[str]:
    s = (s or "").upper()
    return re.findall(r"[A-ZÁÉÍÓÚÜÑ]+", s)


def _normalize_text(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = s.encode("ascii", "ignore").decode("utf-8")
    return s.upper()


def _match_exact_provincia_ciudad(
    filename_stem: str,
    provincia: str,
    ciudad: str
) -> bool:
    stem = (filename_stem or "")
    stem_u = stem.upper()

    prov = (provincia or "").strip()
    city = (ciudad or "").strip()

    if not prov and not city:
        return False

    def phrase_re(phrase: str) -> Optional[re.Pattern]:
        phrase = (phrase or "").strip()
        if not phrase:
            return None
        return re.compile(rf"(^|[\W_]){re.escape(phrase.upper())}($|[\W_])")

    prov_re = phrase_re(prov)
    city_re = phrase_re(city)

    if prov_re and prov_re.search(stem_u):
        return True
    if city_re and city_re.search(stem_u):
        return True

    toks = _tokens_upper(stem_u)
    prov_toks = _tokens_upper(prov)
    city_toks = _tokens_upper(city)

    if prov_toks and all(t in toks for t in prov_toks):
        return True
    if city_toks and all(t in toks for t in city_toks):
        return True

    return False


# ======================================================
# UI: Diálogo
# ======================================================

class NuevoClienteDialog:
    def __init__(self, parent: tk.Misc):
        self.resultado: Optional[Dict[str, str]] = None

        self.win = tk.Toplevel(parent)
        set_window_icon(self.win)
        self.win.title("Nuevo cliente")
        self.win.resizable(False, False)
        self.win.grab_set()

        tk.Label(
            self.win,
            text="Introduce los datos del cliente:",
            font=("Segoe UI", 10, "bold")
        ).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w",
            padx=14,
            pady=(12, 8)
        )

        tk.Label(
            self.win,
            text="Nombre completo:"
        ).grid(row=1, column=0, sticky="e", padx=14, pady=6)

        tk.Label(
            self.win,
            text="Provincia:"
        ).grid(row=2, column=0, sticky="e", padx=14, pady=6)

        tk.Label(
            self.win,
            text="Ciudad:"
        ).grid(row=3, column=0, sticky="e", padx=14, pady=6)

        self.var_nombre = tk.StringVar()
        self.var_prov = tk.StringVar()
        self.var_city = tk.StringVar()

        self.e_nombre = tk.Entry(
            self.win,
            width=44,
            textvariable=self.var_nombre
        )
        self.e_prov = tk.Entry(
            self.win,
            width=44,
            textvariable=self.var_prov
        )
        self.e_city = tk.Entry(
            self.win,
            width=44,
            textvariable=self.var_city
        )

        self.e_nombre.grid(row=1, column=1, sticky="w", padx=(0, 14), pady=6)
        self.e_prov.grid(row=2, column=1, sticky="w", padx=(0, 14), pady=6)
        self.e_city.grid(row=3, column=1, sticky="w", padx=(0, 14), pady=6)

        btns = tk.Frame(self.win)
        btns.grid(row=4, column=0, columnspan=2, pady=(10, 12))

        tk.Button(
            btns,
            text="Aceptar",
            width=12,
            command=self._aceptar
        ).pack(side="left", padx=6)

        tk.Button(
            btns,
            text="Cancelar",
            width=12,
            command=self._cancelar
        ).pack(side="left", padx=6)

        self.e_nombre.focus_set()
        self.win.protocol("WM_DELETE_WINDOW", self._cancelar)

        self.win.wait_window()

    def _aceptar(self):
        nombre = (self.var_nombre.get() or "").strip()
        prov = (self.var_prov.get() or "").strip()
        city = (self.var_city.get() or "").strip()

        if not nombre:
            messagebox.showerror(
                "Dato requerido",
                "Debes introducir el nombre completo.",
                parent=self.win
            )
            return

        self.resultado = {
            "nombre": nombre,
            "provincia": prov,
            "ciudad": city
        }
        self.win.destroy()

    def _cancelar(self):
        self.resultado = None
        self.win.destroy()


# ======================================================
# LÓGICA
# ======================================================

def _crear_carpeta_cliente(base_dir: Path, nombre_cliente: str) -> Path:
    safe = sanitize_filename(
        nombre_cliente,
        max_len=120,
        fallback="NUEVO_CLIENTE"
    )
    carpeta = base_dir / safe
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def _copiar_plantilla(plantilla_dir: Path, destino_dir: Path) -> List[Path]:
    copiados: List[Path] = []

    for item in plantilla_dir.iterdir():
        if item.is_file():
            dst = destino_dir / item.name
            shutil.copy2(item, dst)
            copiados.append(dst)

    return copiados


def _renombrar_excel_sheet(
    destino_dir: Path,
    nombre_cliente: str
) -> Optional[Path]:
    xlsx_files = sorted([
        p for p in destino_dir.iterdir()
        if p.is_file() and p.suffix.lower() == ".xlsx"
    ])

    if not xlsx_files:
        return None

    xlsx_path = xlsx_files[0]

    try:
        wb = load_workbook(xlsx_path)
        ws = wb.active if wb.worksheets else None

        if ws is None:
            return xlsx_path

        new_title = (nombre_cliente or "").strip()[:31] or "CLIENTE"
        ws.title = new_title
        wb.save(xlsx_path)
        wb.close()

        return xlsx_path

    except Exception as e:
        raise RuntimeError(
            f"No se pudo renombrar la hoja del Excel:\n"
            f"{xlsx_path.name}\n\n"
            f"Detalle: {e}"
        )


def _renombrar_archivo_tabla(
    destino_dir: Path,
    nombre_cliente: str
) -> Optional[Path]:
    for f in destino_dir.iterdir():
        if not f.is_file():
            continue

        clave = f.name.upper()

        if clave.startswith("TABLA DE CANTIDADES_BANCARIO_CLIENTE"):
            ext = f.suffix
            nuevo = destino_dir / (
                f"TABLA DE CANTIDADES_BANCARIO_"
                f"{(nombre_cliente or '').upper()}{ext}"
            )

            try:
                f.rename(nuevo)
            except Exception:
                logger.warning(
                    "[NUEVO-CLIENTE] No se pudo renombrar el archivo TABLA."
                )
                return f

            return nuevo

    return None


def _copiar_procuradores(
    procuradores_dir: Path,
    destino_dir: Path,
    provincia: str,
    ciudad: str
) -> List[str]:
    encontrados: List[str] = []

    for f in procuradores_dir.iterdir():
        if not f.is_file():
            continue

        if _match_exact_provincia_ciudad(f.stem, provincia, ciudad):
            dst = destino_dir / f.name
            shutil.copy2(f, dst)
            encontrados.append(f.name)

    return encontrados


# ======================================================
# RUN
# ======================================================

def run(progress=None, is_cancelled=None) -> Dict[str, Any]:
    parent = call_ui(lambda: tk._get_default_root())

    _ensure_dir_accessible(NUEVOS_CLIENTES_BASE, "salida (Nuevos clientes)")
    _ensure_dir_accessible(PLANTILLA_DIR, "plantilla")
    _ensure_dir_accessible(PROCURADORES_DIR, "procuradores")

    cfg = call_ui(lambda: NuevoClienteDialog(parent).resultado)
    if not cfg:
        raise CancelledByUser()

    nombre = cfg["nombre"]
    provincia = cfg.get("provincia", "")
    ciudad = cfg.get("ciudad", "")

    if is_cancelled and is_cancelled():
        raise CancelledByUser()

    carpeta_cliente = _crear_carpeta_cliente(NUEVOS_CLIENTES_BASE, nombre)

    logger.info(f"[NUEVO-CLIENTE] Cliente: {nombre}")
    logger.info(f"[NUEVO-CLIENTE] Carpeta destino: {carpeta_cliente}")

    copiados_plantilla = _copiar_plantilla(PLANTILLA_DIR, carpeta_cliente)

    excel_generado = any(
        p.suffix.lower() == ".xlsx"
        for p in copiados_plantilla
    )

    guia_copiada = any(
        "GUIA PARA OBTENER EL APODERAMIENTO" in _normalize_text(p.name)
        for p in copiados_plantilla
    )

    hoja_encargo_copiada = any(
        "HOJA DE ENCARGO_BANCARIO" in _normalize_text(p.name)
        for p in copiados_plantilla
    )

    excel_mod = _renombrar_excel_sheet(carpeta_cliente, nombre)
    tabla_ren = _renombrar_archivo_tabla(carpeta_cliente, nombre)
    copiados = _copiar_procuradores(
        PROCURADORES_DIR,
        carpeta_cliente,
        provincia,
        ciudad
    )

    msg_parts = ["Proceso completado"]

    if excel_mod:
        msg_parts.append("Excel actualizado")

    if tabla_ren:
        msg_parts.append(f"Tabla renombrada: {tabla_ren.name}")

    if copiados:
        msg_parts.append(f"Procuradores copiados: {len(copiados)}")
    else:
        msg_parts.append("Sin procuradores coincidentes")

    return build_result(
        message=" | ".join(msg_parts),
        output_dir=carpeta_cliente,
        procuradores_copiados=len(copiados),
        excel_generado=excel_generado,
        guia_copiada=guia_copiada,
        hoja_encargo_copiada=hoja_encargo_copiada,
    )