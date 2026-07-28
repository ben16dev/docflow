"""Tests del componente ToolCard."""

import tkinter as tk

import pytest

from ui.common import ToolCard, create_tool_card
from ui.styles import (
    CARD_BG,
    CARD_BORDER,
    CARD_BORDER_FOCUS,
    CARD_BORDER_HOVER,
    CARD_BORDER_PRESSED,
    CARD_DISABLED_BG,
    CARD_DISABLED_FG,
    CARD_HOVER_BG,
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


def _geometry_keys(card):
    return {
        "highlightthickness": int(card.tk.call(card._w, "cget", "-highlightthickness")),
        "bd": int(card.tk.call(card._w, "cget", "-bd")),
        "relief": str(card.cget("relief")),
        "reqwidth": card.winfo_reqwidth(),
        "reqheight": card.winfo_reqheight(),
    }


def test_create_minimal(root):
    card = ToolCard(root)
    assert card.cget("title") == ""
    assert card.cget("description") == ""
    assert card.cget("state") == "normal"
    assert card.cget("bg") == CARD_BG


def test_title_and_description(root):
    card = ToolCard(root, title="Título", description="Descripción breve")
    assert card.cget("title") == "Título"
    assert card.cget("text") == "Título"
    assert card.cget("description") == "Descripción breve"


def test_empty_description(root):
    card = ToolCard(root, title="Solo título", description="")
    assert card.cget("description") == ""
    assert card.cget("title") == "Solo título"


def test_invoke_runs_command(root):
    calls = []
    card = ToolCard(root, title="A", command=lambda: calls.append(1))
    card.invoke()
    assert calls == [1]


def test_keyboard_activation(root):
    calls = []
    card = ToolCard(root, title="A", command=lambda: calls.append("key"))
    card._on_activate_key()
    assert calls == ["key"]


def test_hover_and_pressed(root):
    card = ToolCard(root, title="H")
    card.pack()
    root.update_idletasks()
    card._on_enter()
    assert card.cget("bg") == CARD_HOVER_BG
    assert card.cget("highlightbackground") == CARD_BORDER_HOVER
    card._on_press()
    assert card.cget("bg") == CARD_HOVER_BG
    assert card.cget("highlightbackground") == CARD_BORDER_PRESSED
    # pressed solo cambia color; relief permanece flat (sin desplazamiento)
    assert card.cget("relief") == "flat"


def test_normal_and_hover_keep_outer_geometry(root):
    card = ToolCard(root, title="Geo", description="Misma geometría exterior")
    card.pack()
    root.update_idletasks()
    root.update()
    before = _geometry_keys(card)
    assert before["highlightthickness"] == 2
    assert before["bd"] == 0
    assert before["relief"] == "flat"

    card._on_enter()
    root.update_idletasks()
    after = _geometry_keys(card)
    assert after == before
    assert card.cget("highlightbackground") == CARD_BORDER_HOVER


def test_pressed_keeps_geometry(root):
    card = ToolCard(root, title="P", description="Pressed estable")
    card.pack()
    root.update_idletasks()
    root.update()
    before = _geometry_keys(card)
    card._on_enter()
    card._on_press()
    root.update_idletasks()
    assert _geometry_keys(card) == before
    assert card.cget("highlightbackground") == CARD_BORDER_PRESSED


def test_focus_keeps_geometry(root):
    card = ToolCard(root, title="F", description="Focus estable")
    card.pack()
    root.update_idletasks()
    root.update()
    before = _geometry_keys(card)
    card._on_focus_in()
    root.update_idletasks()
    assert _geometry_keys(card) == before
    assert card.cget("highlightbackground") == CARD_BORDER_FOCUS
    card._on_focus_out()
    root.update_idletasks()
    assert _geometry_keys(card) == before
    assert card.cget("highlightbackground") == CARD_BORDER


def test_child_enter_leave_does_not_oscillate(root):
    card = ToolCard(root, title="Osc", description="Sin temblor interno")
    card.pack()
    root.update_idletasks()
    root.update()

    applies = []
    original = card._apply_visual

    def counting():
        applies.append(card._hovered)
        return original()

    card._apply_visual = counting

    class FakeEvent:
        def __init__(self, x, y):
            self.x_root = x
            self.y_root = y

    card._on_enter()
    assert card._hovered is True
    applies.clear()

    # Coordenadas dentro del área solicitada (estable aunque el root esté withdraw).
    inside = FakeEvent(
        card.winfo_rootx() + max(card.winfo_reqwidth() // 2, 2),
        card.winfo_rooty() + max(card.winfo_reqheight() // 2, 2),
    )
    card._on_leave(inside)
    card._on_enter(inside)
    card._on_leave(inside)

    assert card._hovered is True
    assert all(hovered is True for hovered in applies) or applies == []

    outside = FakeEvent(card.winfo_rootx() - 40, card.winfo_rooty() - 40)
    card._on_leave(outside)
    assert card._hovered is False


def test_disabled_blocks_invoke_and_keyboard(root):
    calls = []
    card = ToolCard(root, title="X", command=lambda: calls.append(1))
    card.configure(state="disabled")
    assert card["state"] == "disabled"
    assert card.cget("bg") == CARD_DISABLED_BG
    card.invoke()
    card._on_activate_key()
    card._on_enter()
    assert calls == []
    assert card.cget("bg") == CARD_DISABLED_BG
    assert card._title_label.cget("fg") == CARD_DISABLED_FG


def test_invalid_state_raises(root):
    card = ToolCard(root, title="X")
    with pytest.raises(tk.TclError, match="bad state"):
        card.configure(state="broken")


def test_configure_title_description_command(root):
    calls = []
    card = ToolCard(root, title="A", description="d1", command=lambda: calls.append("old"))
    card.configure(
        title="B",
        description="d2",
        command=lambda: calls.append("new"),
    )
    assert card.cget("title") == "B"
    assert card.cget("description") == "d2"
    card.invoke()
    assert calls == ["new"]


def test_reenable_restores_colors(root):
    card = ToolCard(root, title="Y")
    card.configure(state="disabled")
    card.configure(state="normal")
    assert card.cget("state") == "normal"
    assert card.cget("bg") == CARD_BG


def test_create_tool_card_factory(root):
    calls = []
    card = create_tool_card(
        root,
        title="Factory",
        description="via factory",
        command=lambda: calls.append(1),
    )
    assert isinstance(card, ToolCard)
    assert card.cget("title") == "Factory"
    card.invoke()
    assert calls == [1]
