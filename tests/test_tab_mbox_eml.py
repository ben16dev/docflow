"""Tests de las pestañas MBOX y EML con ToolCard."""

import tkinter as tk
from types import SimpleNamespace

import pytest

from scripts.registry import get_scripts
from ui.common import ToolCard
from ui.tabs import tab_eml, tab_mbox


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


def _build_tab(root, build_fn, tab_name):
    calls = []

    def _ejecutar(funcion, *args, **kwargs):
        calls.append((funcion, kwargs.get("action"), kwargs.get("tab")))

    app = SimpleNamespace(
        var_ruta=tk.StringVar(master=root, value=""),
        _seleccionar_carpeta=lambda: None,
        _ejecutar=_ejecutar,
    )
    tab = tk.Frame(root)
    build_fn(tab, app)
    return tab, calls, tab_name


def test_mbox_one_card_per_registered_tool_in_order(root):
    tab, _, _ = _build_tab(root, tab_mbox.build_tab, "MBOX")
    cards = _collect_tool_cards(tab)
    registered = [
        name
        for name, module in get_scripts("MBOX").items()
        if getattr(module, "run", None) is not None
    ]
    assert len(cards) == len(registered)
    assert [c.cget("title") for c in cards] == registered
    assert len(cards) == len(set(c.cget("title") for c in cards))


def test_mbox_card_invokes_ejecutar(root):
    tab, calls, _ = _build_tab(root, tab_mbox.build_tab, "MBOX")
    cards = {c.cget("title"): c for c in _collect_tool_cards(tab)}
    first_name = next(iter(get_scripts("MBOX")))
    cards[first_name].invoke()
    assert len(calls) == 1
    funcion, action, tab_name = calls[0]
    assert action == first_name
    assert tab_name == "MBOX"
    assert callable(funcion)


def test_eml_one_card_per_registered_tool(root):
    tab, _, _ = _build_tab(root, tab_eml.build_tab, "EML")
    cards = _collect_tool_cards(tab)
    registered = [
        name
        for name, module in get_scripts("EML").items()
        if getattr(module, "run", None) is not None
    ]
    assert len(cards) == len(registered)
    assert [c.cget("title") for c in cards] == registered


def test_eml_card_invokes_ejecutar(root):
    tab, calls, _ = _build_tab(root, tab_eml.build_tab, "EML")
    cards = {c.cget("title"): c for c in _collect_tool_cards(tab)}
    name = "EML a PDF"
    cards[name].invoke()
    assert len(calls) == 1
    _, action, tab_name = calls[0]
    assert action == name
    assert tab_name == "EML"


def test_mbox_and_eml_use_toolcard_only(root):
    for build_fn in (tab_mbox.build_tab, tab_eml.build_tab):
        tab, _, _ = _build_tab(root, build_fn, "X")
        cards = _collect_tool_cards(tab)
        assert cards
        assert all(isinstance(c, ToolCard) for c in cards)
