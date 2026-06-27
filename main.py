print("1 - inicio main")
print("2 - antes de UI")
print("3 - antes mainloop")

import sys
import os
import ctypes
from pathlib import Path

# 🔥 1. AppID antes de TODO
if os.name == "nt":
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "EDV.AppScript"
        )
    except Exception:
        pass

# 🔥 2. Luego añadir ruta base
base_path = Path(__file__).resolve().parent
if str(base_path) not in sys.path:
    sys.path.append(str(base_path))

# 🔥 3. Ahora sí importamos la app
from ui.app import App

if __name__ == "__main__":
    print("ANTES DE CREAR APP")
    app = App()
    print("APP CREADA")
    app.mainloop()
    print("DESPUÉS DE MAINLOOP")