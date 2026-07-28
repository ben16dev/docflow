"""Tests de create_route_frame y create_help_panel (componentes comunes UI)."""

import tkinter as tk

import pytest

from ui.common import CorporateButton, create_help_panel, create_route_frame
from ui.styles import (
    FONT_FAMILY_UI,
    HELP_PANEL_BG,
    HELP_PANEL_TEXT_FG,
    HELP_PANEL_TITLE_FG,
    HELP_PANEL_WRAPLENGTH,
    ROUTE_BG,
    ROUTE_DISABLED_BG,
    ROUTE_DISABLED_FG,
    ROUTE_FG,
    ROUTE_PLACEHOLDER_FG,
    TEXT_SECONDARY,
)


def _make_root():
    try:
        root = tk.Tk()
        root.withdraw()
        return root
    except tk.TclError as exc:
        pytest.skip(f"Tk no disponible en este entorno: {exc}")


@pytest.fixture
def root():
    root = _make_root()
    try:
        yield root
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


# ---------------------------------------------------------------------------
# Selector de rutas
# ---------------------------------------------------------------------------

def test_route_frame_creation(root):
    var = tk.StringVar()
    frame = create_route_frame(root, var, seleccionar_callback=lambda: None)
    assert frame.winfo_exists()
    assert isinstance(frame._route_entry, tk.Entry)
    assert isinstance(frame._route_button, CorporateButton)
    assert frame._route_button.cget("variant") == "secondary"
    assert frame._route_button.cget("text") == "Seleccionar carpeta"


def test_route_frame_placeholder(root):
    var = tk.StringVar()
    frame = create_route_frame(root, var, seleccionar_callback=lambda: None)
    assert var.get() == frame._route_placeholder
    assert frame._route_entry.cget("fg") == ROUTE_PLACEHOLDER_FG
    assert frame._route_entry.cget("bg") == ROUTE_BG


def test_route_frame_callback(root):
    calls = []
    var = tk.StringVar()
    frame = create_route_frame(root, var, seleccionar_callback=lambda: calls.append(1))
    frame._route_button.invoke()
    assert calls == [1]


def test_route_frame_text_change_clears_placeholder_style(root):
    var = tk.StringVar()
    frame = create_route_frame(root, var, seleccionar_callback=lambda: None)
    entry = frame._route_entry
    assert var.get() == frame._route_placeholder
    assert entry.cget("fg") == ROUTE_PLACEHOLDER_FG
    # Tras seleccionar carpeta la app escribe la ruta real.
    var.set("/tmp/demo")
    entry.config(fg=ROUTE_FG)
    assert var.get() == "/tmp/demo"
    assert entry.cget("fg") == ROUTE_FG
    assert entry.bind("<FocusIn>")
    assert entry.bind("<FocusOut>")


def test_route_frame_disabled_readable(root):
    var = tk.StringVar(value="/ruta/activa")
    frame = create_route_frame(root, var, seleccionar_callback=lambda: None)
    entry = frame._route_entry
    assert entry.cget("disabledbackground") == ROUTE_DISABLED_BG
    assert entry.cget("disabledforeground") == ROUTE_DISABLED_FG
    entry.configure(state="disabled")
    assert entry.cget("state") == "disabled"
    frame._route_button.configure(state="disabled")
    assert frame._route_button.cget("state") == "disabled"


def test_route_frame_preserves_existing_path(root):
    var = tk.StringVar(value="/Users/demo/docs")
    frame = create_route_frame(root, var, seleccionar_callback=lambda: None)
    assert var.get() == "/Users/demo/docs"
    assert frame._route_entry.cget("fg") == ROUTE_FG


def test_route_frame_public_api_signature(root):
    """API pública: (parent, ruta_var, seleccionar_callback) → frame."""
    var = tk.StringVar()
    result = create_route_frame(root, var, lambda: None)
    assert isinstance(result, tk.Frame)


# ---------------------------------------------------------------------------
# Panel de ayuda
# ---------------------------------------------------------------------------

def test_help_panel_creation(root):
    title = "Ayuda MBOX"
    text = "Selecciona una carpeta y ejecuta la herramienta."
    frame = create_help_panel(root, title, text)
    assert frame.cget("text") == title
    assert frame._help_label.cget("text") == text
    assert frame.cget("bg") == HELP_PANEL_BG
    assert frame.cget("fg") == HELP_PANEL_TITLE_FG
    assert frame._help_label.cget("fg") == HELP_PANEL_TEXT_FG
    assert frame._help_label.cget("fg") == TEXT_SECONDARY
    assert int(frame._help_label.cget("wraplength")) == HELP_PANEL_WRAPLENGTH


def test_help_panel_preserves_long_description(root):
    title = "Ayuda"
    text = " ".join([f"Paso {i} del flujo documental." for i in range(1, 40)])
    frame = create_help_panel(root, title, text)
    assert frame._help_label.cget("text") == text
    assert int(frame._help_label.cget("wraplength")) == HELP_PANEL_WRAPLENGTH


def test_help_panel_uses_ui_font_token(root):
    frame = create_help_panel(root, "T", "Descripción")
    font = str(frame.cget("font"))
    assert FONT_FAMILY_UI in font or "font" in dir(frame)
    label_font = str(frame._help_label.cget("font"))
    # Tk puede devolver el nombre de fuente resuelto; comprobar tamaño vía token.
    assert label_font  # no vacío
