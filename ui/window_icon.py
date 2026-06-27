"""
Aplicación del icono de ventana de DocFlow.

Estrategia multiplataforma:
  1. iconphoto con assets/icon.png  → funciona en todas las plataformas.
  2. iconbitmap con assets/icon.ico → mejora visual en Windows (barra de título).
     Se omite en macOS porque iconbitmap puede lanzar excepciones allí.

Se conserva una referencia viva a la imagen Tkinter para evitar que el
recolector de basura la elimine antes de que la ventana la use.
"""

import sys
import tkinter as tk

from utils.resources import resource_path


def set_window_icon(window: tk.Misc) -> None:
    """
    Aplica el icono de DocFlow a una ventana Tk o Toplevel.

    No lanza excepciones: cualquier error en la carga del recurso
    se ignora de forma silenciosa para no bloquear el arranque.
    """
    try:
        png_path = resource_path("assets/icon.png")
        ico_path = resource_path("assets/icon.ico")

        # Windows: iconbitmap es la vía más estable para la barra de título.
        # En macOS puede provocar errores con archivos .ico, por eso se limita
        # explícitamente a la plataforma Windows.
        if sys.platform == "win32" and ico_path.exists():
            try:
                window.iconbitmap(str(ico_path))
            except Exception:
                pass

        # iconphoto funciona en todas las plataformas.
        # La referencia _docflow_icon se guarda en la ventana para evitar
        # que Python libere el objeto antes de que Tkinter lo haya utilizado.
        if png_path.exists():
            try:
                img = tk.PhotoImage(file=str(png_path))
                window._docflow_icon = img  # type: ignore[attr-defined]
                window.iconphoto(False, img)
            except Exception:
                pass

    except Exception:
        pass
