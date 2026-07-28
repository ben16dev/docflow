"""Tests de la pestaña PDF con ToolCard."""

import tkinter as tk
from types import SimpleNamespace

import pytest

from scripts.registry import get_scripts
from ui.common import ToolCard
from ui.tabs import tab_pdf


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


def _collect_tool_cards(widget):
    cards = []
    if isinstance(widget, ToolCard):
        cards.append(widget)
    for child in widget.winfo_children():
        cards.extend(_collect_tool_cards(child))
    return cards


def _build_pdf_tab(root):
    calls = []

    def _ejecutar(funcion, *args, **kwargs):
        calls.append((funcion, kwargs.get("action"), kwargs.get("tab")))

    app = SimpleNamespace(
        var_ruta=tk.StringVar(master=root, value=""),
        _seleccionar_carpeta=lambda: None,
        _ejecutar=_ejecutar,
    )
    tab = tk.Frame(root)
    tab_pdf.build_tab(tab, app)
    return tab, calls


def test_pdf_tab_creates_one_card_per_registered_tool(root):
    tab, _ = _build_pdf_tab(root)
    cards = _collect_tool_cards(tab)
    registered = [
        name
        for name, module in get_scripts("PDF").items()
        if getattr(module, "run", None) is not None
    ]
    assert len(cards) == len(registered)
    assert [c.cget("title") for c in cards] == registered


def test_pdf_card_invokes_ejecutar_with_registry_action(root):
    tab, calls = _build_pdf_tab(root)
    cards = {c.cget("title"): c for c in _collect_tool_cards(tab)}
    first_name = next(iter(get_scripts("PDF")))
    cards[first_name].invoke()
    assert len(calls) == 1
    funcion, action, tab_name = calls[0]
    assert action == first_name
    assert tab_name == "PDF"
    assert callable(funcion)
