import sys
from pathlib import Path
import tkinter as tk


def get_base_path() -> Path:
    """
    Devuelve la raíz del proyecto tanto en desarrollo como en ejecutable PyInstaller.
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)

    return Path(__file__).resolve().parent.parent


def set_window_icon(window: tk.Misc) -> None:
    """
    Aplica el icono corporativo de EDV AppScript a una ventana Tk/Toplevel.

    Prioridad:
    1. assets/icon.ico para Windows / iconbitmap.
    2. assets/icon.png para iconphoto.

    Mantiene referencias en la propia ventana para evitar que Tkinter libere
    la imagen por garbage collection.
    """
    try:
        base_path = get_base_path()
        ico_path = base_path / "assets" / "icon.ico"
        png_path = base_path / "assets" / "icon.png"

        # Windows: iconbitmap suele ser lo más estable para barra de título.
        if ico_path.exists():
            try:
                window.iconbitmap(str(ico_path))
            except Exception:
                pass

        # Tk/Toplevel: iconphoto ayuda a evitar el icono por defecto de Tk.
        if png_path.exists():
            try:
                img = tk.PhotoImage(file=str(png_path))
                window._edv_window_icon = img
                window.iconphoto(False, img)
            except Exception:
                pass

    except Exception:
        pass
