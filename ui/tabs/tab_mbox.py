# ui/tabs/tab_mbox.py
"""
Pestaña MBOX — cuadrícula de tarjetas de herramientas (Light Indigo DS).

Las herramientas y el orden proceden de scripts.registry.get_scripts("MBOX").
Cada tarjeta lanza app._ejecutar con el mismo contrato que los botones previos.
"""

import tkinter as tk

from scripts.registry import get_scripts
from ui.common import ToolCard, create_route_frame
from ui.styles import (
    CARD_GAP,
    FONT_SIZE_LG,
    FONT_SIZE_MD,
    FRAME_BG,
    PAGE_PADX,
    SECTION_PADY,
    SPACE_MD,
    SPACE_SM,
    TEXT_SECONDARY,
    TITLE_FG,
)

# Descripciones tomadas del panel de ayuda previo (sin inventar funcionalidad).
_MBOX_DESCRIPTIONS = {
    "MBOX a EML": "Extrae correos individuales (.eml) desde un archivo MBOX.",
    "Extraer adjuntos de MBOX": (
        "Por cada correo crea una carpeta con el PDF del correo, "
        "el .eml original y todos los adjuntos."
    ),
}

# Pocas herramientas: dos columnas equilibradas (sin forzar huecos de 3).
_GRID_COLS = 2


def build_tab(tab, app):
    frame = tk.Frame(tab, bg=FRAME_BG)
    frame.pack(fill="both", expand=True)

    _build_intro(frame)
    create_route_frame(frame, app.var_ruta, app._seleccionar_carpeta)
    _build_cards(frame, app)


def _build_intro(parent):
    intro = tk.LabelFrame(
        parent,
        text="Herramientas MBOX",
        bg=FRAME_BG,
        fg=TITLE_FG,
        font=("Segoe UI", FONT_SIZE_LG, "bold"),
        padx=SPACE_MD,
        pady=SPACE_SM,
    )
    intro.pack(fill="x", padx=PAGE_PADX, pady=(SECTION_PADY, SPACE_SM))

    tk.Label(
        intro,
        text=(
            "Selecciona la carpeta de trabajo y elige una herramienta. "
            "Al ejecutar se te pedirá el archivo MBOX a procesar."
        ),
        justify="left",
        anchor="w",
        bg=FRAME_BG,
        fg=TEXT_SECONDARY,
        font=("Segoe UI", FONT_SIZE_MD),
        wraplength=900,
    ).pack(anchor="w")


def _build_cards(parent, app):
    grid = tk.Frame(parent, bg=FRAME_BG)
    grid.pack(fill="both", expand=True, padx=PAGE_PADX, pady=(SPACE_SM, SECTION_PADY))

    for col in range(_GRID_COLS):
        grid.grid_columnconfigure(col, weight=1, uniform="toolcards_mbox")

    scripts = get_scripts("MBOX")
    cards = []

    for i, (texto, module) in enumerate(scripts.items()):
        funcion = getattr(module, "run", None)
        if funcion is None:
            continue

        row = i // _GRID_COLS
        col = i % _GRID_COLS
        description = _MBOX_DESCRIPTIONS.get(texto, "")

        card = ToolCard(
            grid,
            title=texto,
            description=description,
            command=lambda f=funcion, a=texto: app._ejecutar(
                f,
                tab="MBOX",
                action=a,
            ),
        )
        card.grid(
            row=row,
            column=col,
            sticky="nsew",
            padx=CARD_GAP,
            pady=CARD_GAP,
        )
        cards.append(card)

    for row in range((len(cards) + _GRID_COLS - 1) // _GRID_COLS):
        grid.grid_rowconfigure(row, weight=1)

    return cards
