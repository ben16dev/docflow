"""Abrir archivos o carpetas con el handler predeterminado del sistema."""

import os
import subprocess
import sys
from pathlib import Path


def open_path(path: Path | str) -> None:
    """Abre un archivo o carpeta con la aplicación predeterminada del SO."""
    target = Path(path)

    if sys.platform.startswith("win"):
        os.startfile(str(target))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(target)])
    else:
        subprocess.Popen(["xdg-open", str(target)])
