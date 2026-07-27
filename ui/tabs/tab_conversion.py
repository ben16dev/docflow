import tkinter as tk
from ui.common import (
    create_corporate_button,
    create_route_frame,
    create_help_panel
)
from ui.styles import FRAME_BG

from scripts.registry import get_scripts

# Herramientas que eligen archivos y destino en sus propios diálogos
# y no dependen de la carpeta de trabajo de la pestaña.
_SELF_CONTAINED_TOOLS = {
    "PDF escaneado a PDF OCR",
}


def build_tab(tab, app):
    frame = tk.Frame(tab, bg=FRAME_BG)
    frame.pack(fill="both", expand=True)

    create_help_panel(
        frame,
        "Ayuda – Conversión",
        "▶ Imagen a PDF: Convierte imágenes PNG y JPG en un archivo PDF.\n"
        "▶ PDF escaneado a PDF OCR: Añade capa de texto a PDFs escaneados "
        "(elige PDF y carpeta destino; no requiere carpeta de trabajo).\n"
    )

    create_route_frame(frame, app.var_ruta, app._seleccionar_carpeta)

    buttons_frame = tk.Frame(frame, bg=FRAME_BG)
    buttons_frame.pack(anchor="w", padx=30, pady=20)

    scripts = get_scripts("CONVERSIÓN")
    botones = list(scripts.items())

    max_cols = 3

    for i, (texto, module) in enumerate(botones):
        row = i // max_cols
        col = i % max_cols

        funcion = getattr(module, "run", None)

        if funcion is None:
            continue

        if texto in _SELF_CONTAINED_TOOLS:
            executor = app._ejecutar_herramienta
        else:
            executor = app._ejecutar

        btn = create_corporate_button(
            buttons_frame,
            app,
            texto,
            lambda f=funcion, a=texto, ex=executor: ex(
                f,
                tab="CONVERSIÓN",
                action=a
            ),
            pack=False
        )

        btn.grid(row=row, column=col, padx=10, pady=10, sticky="w")
