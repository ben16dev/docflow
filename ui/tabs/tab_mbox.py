import tkinter as tk
from ui.common import (
    create_corporate_button,
    create_route_frame,
    create_help_panel
)
from ui.styles import FRAME_BG

from scripts.registry import get_scripts


def build_tab(tab, app):
    frame = tk.Frame(tab, bg=FRAME_BG)
    frame.pack(fill="both", expand=True)

    # Panel de ayuda actualizado
    create_help_panel(
        frame,
        "Ayuda – MBOX",
        "▶ MBOX → EML: Extrae correos individuales (.eml) desde un archivo MBOX.\n\n"
        "▶ Extraer adjuntos de MBOX: Por cada correo crea una carpeta con el PDF "
        "del correo, el .eml original y todos los adjuntos. Organiza por fecha y "
        "asunto del mensaje (o remitente si no hay asunto).\n\n"
        "⚠ Siempre se te pedirá seleccionar el archivo MBOX a procesar."
    )

    # Ruta de trabajo
    create_route_frame(frame, app.var_ruta, app._seleccionar_carpeta)

    # =========================
    # Frame de botones (GRID)
    # =========================
    buttons_frame = tk.Frame(frame, bg=FRAME_BG)
    buttons_frame.pack(anchor="w", padx=30, pady=20)

    scripts = get_scripts("MBOX")
    botones = list(scripts.items())

    max_cols = 3

    for i, (texto, module) in enumerate(botones):
        row = i // max_cols
        col = i % max_cols

        funcion = getattr(module, "run", None)

        if funcion is None:
            continue

        btn = create_corporate_button(
            buttons_frame,
            app,
            texto,
            lambda f=funcion, a=texto: app._ejecutar(
                f,
                tab="MBOX",
                action=a
            ),
            pack=False
        )

        btn.grid(row=row, column=col, padx=10, pady=10, sticky="w")



