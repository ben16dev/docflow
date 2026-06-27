# ui/tabs/tab_pdf.py
import tkinter as tk

from ui.common import (
    create_corporate_button,
    create_route_frame,
)
from ui.styles import FRAME_BG

from scripts.registry import get_scripts


def build_tab(tab, app):
    frame = tk.Frame(tab, bg=FRAME_BG)
    frame.pack(fill="both", expand=True)

    # =================================================
    # PANEL DE AYUDA EN GRID (3 x 3)
    # =================================================

    help_frame = tk.LabelFrame(
        frame,
        text="Ayuda – Herramientas PDF",
        bg=FRAME_BG,
        fg="#1f4e79",
        font=("Segoe UI", 11, "bold"),
        padx=20,
        pady=15
    )
    help_frame.pack(fill="x", padx=30, pady=(20, 15))

    ayudas = [
        "▶ Imágenes a PDF\nConvierte PNG/JPG en PDF.",
        "▶ Numeración PDF\nEstampa identificadores configurables.",
        "▶ Censurar PDF\nCensura visual por palabras.",
        "▶ Renombrar por índice\nUsa un Word como índice.",
        "▶ Rotar páginas\nRota páginas específicas.",
        "▶ Extraer páginas\nExtrae rangos o páginas sueltas.",
        "▶ Unir (orden manual)\nSelecciona y ordena PDFs.",
        "▶ Unir por expediente\nUne por patrón + número.",
        "▶ Unir por DNI\nUne por coincidencia de datos.",
        "▶ Nuevo cliente\nGenera hoja de encargo, letrados y procuradores.",
        "▶ Limpiar numeración PDF\nElimina marcas de numeración previas.",
        "▶ Optimizar PDF\nReduce peso manteniendo legibilidad.",
    ]

    for i, texto in enumerate(ayudas):
        row = i // 3
        col = i % 3

        lbl = tk.Label(
            help_frame,
            text=texto,
            justify="left",
            anchor="nw",
            bg=FRAME_BG,
            font=("Segoe UI", 10),
            padx=10,
            pady=6
        )
        lbl.grid(row=row, column=col, sticky="nw", padx=10, pady=6)

    for c in range(3):
        help_frame.grid_columnconfigure(c, weight=1)

    # =================================================
    # Ruta de trabajo
    # =================================================

    create_route_frame(frame, app.var_ruta, app._seleccionar_carpeta)

    # =================================================
    # BOTONES
    # =================================================

    buttons_frame = tk.Frame(frame, bg=FRAME_BG)
    buttons_frame.pack(anchor="w", padx=30, pady=20)

    scripts = get_scripts("PDF")

    botones = list(scripts.items())

    for i, (texto, module) in enumerate(botones):
        row = i // 3
        col = i % 3

        funcion = getattr(module, "run", None)

        if funcion is None:
            continue

        btn = create_corporate_button(
            buttons_frame,
            app,
            texto,
            lambda f=funcion, a=texto: app._ejecutar(
                f,
                tab="PDF",
                action=a
            ),
            pack=False
        )

        btn.grid(row=row, column=col, padx=10, pady=10, sticky="w")
