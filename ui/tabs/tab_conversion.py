# ui/tabs/tab_conversion.py
"""
Pestaña Conversión — cuadrícula de tarjetas de herramientas (Light Indigo DS).

Las herramientas y el orden proceden de scripts.registry.get_scripts("CONVERSIÓN").
Las herramientas autocontenidas usan app._ejecutar_herramienta; el resto, app._ejecutar.
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

# Herramientas que eligen archivos y destino en sus propios diálogos
# y no dependen de la carpeta de trabajo de la pestaña.
_SELF_CONTAINED_TOOLS = {
    "PDF escaneado a PDF OCR",
}

# Descripciones tomadas del panel de ayuda previo (sin inventar funcionalidad).
_CONVERSION_DESCRIPTIONS = {
    "Imagen a PDF": "Convierte imágenes PNG y JPG en un archivo PDF.",
    "PDF escaneado a PDF OCR": (
        "Añade capa de texto a PDFs escaneados "
        "(elige PDF y carpeta destino; no requiere carpeta de trabajo)."
    ),
    "MBOX a EML": "Extrae correos individuales (.eml) desde un archivo MBOX.",
    "Extraer adjuntos de MBOX": (
        "Por cada correo crea una carpeta con el PDF del correo, "
        "el .eml original y todos los adjuntos."
    ),
    "EML a PDF": (
        "Convierte correos electrónicos a PDF. "
        "Recomendado tras extraer EML desde un archivo MBOX."
    ),
}

# Orden de herramientas.
_TOOL_ORDER = [
    "Imagen a PDF",
    "PDF escaneado a PDF OCR",
    "MBOX a EML",
    "Extraer adjuntos de MBOX",
    "EML a PDF",
]

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
        text="Herramientas de conversión",
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
            "Selecciona la carpeta de trabajo cuando la herramienta lo requiera. "
            "Algunas herramientas, como OCR, piden entrada y destino en sus propios diálogos."
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
        grid.grid_columnconfigure(col, weight=1, uniform="toolcards_conversion")

    scripts = get_scripts("CONVERSIÓN")
    cards = []

    for i, tool_name in enumerate(_TOOL_ORDER):
        # Obtener módulo del registro
        module = scripts.get(tool_name)
        if module is None:
            continue

        funcion = getattr(module, "run", None)
        if funcion is None:
            continue

        # Determinar executor
        if tool_name in _SELF_CONTAINED_TOOLS:
            executor = app._ejecutar_herramienta
        else:
            executor = app._ejecutar

        # Calcular posición en grid
        row = i // _GRID_COLS
        col = i % _GRID_COLS

        description = _CONVERSION_DESCRIPTIONS.get(tool_name, "")

        card = ToolCard(
            grid,
            title=tool_name,
            description=description,
            command=lambda f=funcion, a=tool_name, ex=executor: ex(
                f,
                tab="CONVERSIÓN",
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

    # Configurar peso de filas: weight=0 para que usen altura natural
    for row in range((len(cards) + _GRID_COLS - 1) // _GRID_COLS):
        grid.grid_rowconfigure(row, weight=0)

    return cards
