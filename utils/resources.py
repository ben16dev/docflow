"""
Utilidad central para resolver rutas de recursos de DocFlow.

Detecta automáticamente si la aplicación se ejecuta desde código fuente
o empaquetada con PyInstaller (sys._MEIPASS), y devuelve la ruta correcta.
"""

import sys
from pathlib import Path


def resource_path(relative_path: str) -> Path:
    """
    Devuelve la ruta absoluta a un recurso, compatible con desarrollo
    y con ejecutables PyInstaller (--onefile / --onedir).

    En modo empaquetado PyInstaller, los recursos se extraen a un
    directorio temporal accesible en sys._MEIPASS.

    En desarrollo, la raíz del proyecto es el directorio que contiene
    este módulo (utils/../).

    Parámetros
    ----------
    relative_path:
        Ruta relativa al recurso desde la raíz del proyecto,
        por ejemplo ``"assets/icon.png"`` o ``"ui/icons/pdf.png"``.

    Ejemplo
    -------
    >>> icon = resource_path("assets/icon.png")
    >>> tab_icon = resource_path("ui/icons/pdf.png")
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent.parent

    return base / relative_path
