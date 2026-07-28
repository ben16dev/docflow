"""Tests del componente CorporateButton (factoría create_corporate_button)."""

import tkinter as tk

import pytest

from ui.common import CorporateButton, create_corporate_button
from ui.styles import (
    ACTION_CANCEL,
    ACTION_CANCEL_HOVER,
    ACTION_CANCEL_PRESSED,
    ACTION_SUCCESS,
    BTN_BG,
    BTN_BG_DISABLED,
    BTN_BG_HOVER,
    BTN_BG_PRESSED,
    BTN_FG,
    BTN_FG_DISABLED_SURFACE,
    BUTTON_VARIANTS,
    PRIMARY_INDIGO,
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


def test_create_corporate_button_signature(root):
    calls = []
    btn = create_corporate_button(
        root,
        app=None,
        text="Demo",
        command=lambda: calls.append(1),
        pack=False,
    )
    assert isinstance(btn, CorporateButton)
    assert btn.cget("text") == "Demo"
    assert btn.cget("state") == "normal"
    assert btn.cget("variant") == "primary"
    btn.grid(row=0, column=0)
    btn.invoke()
    assert calls == [1]


def test_default_variant_is_primary(root):
    btn = CorporateButton(root, text="X")
    assert btn.cget("variant") == "primary"
    assert btn.cget("bg") == BTN_BG
    assert btn.cget("fg") == BTN_FG


@pytest.mark.parametrize("variant", sorted(BUTTON_VARIANTS))
def test_each_variant_applies_palette(root, variant):
    palette = BUTTON_VARIANTS[variant]
    btn = CorporateButton(root, text=variant, variant=variant)
    assert btn.cget("variant") == variant
    assert btn.cget("bg") == palette["bg"]
    assert btn.cget("fg") == palette["fg"]


def test_invalid_variant_raises(root):
    with pytest.raises(ValueError, match="variante inválida"):
        CorporateButton(root, text="X", variant="neon")


def test_configure_invalid_variant_raises(root):
    btn = CorporateButton(root, text="X")
    with pytest.raises(ValueError, match="variante inválida"):
        btn.configure(variant="neon")


def test_hover_applies_hover_color(root):
    btn = CorporateButton(root, text="H", variant="cancel")
    btn._on_enter()
    assert btn.cget("bg") == ACTION_CANCEL_HOVER
    btn._on_leave()
    assert btn.cget("bg") == ACTION_CANCEL


def test_pressed_applies_pressed_color(root):
    btn = CorporateButton(root, text="P", variant="cancel")
    btn._on_press()
    assert btn.cget("bg") == ACTION_CANCEL_PRESSED
    assert btn.cget("relief") == "sunken"


def test_disabled_does_not_invoke(root):
    calls = []
    btn = CorporateButton(root, text="X", command=lambda: calls.append(1))
    btn.configure(state="disabled")
    assert btn["state"] == "disabled"
    assert btn.cget("bg") == BTN_BG_DISABLED
    assert btn.cget("fg") == BTN_FG_DISABLED_SURFACE
    btn.invoke()
    assert calls == []
    btn._on_enter()
    assert btn.cget("bg") == BTN_BG_DISABLED


def test_disabled_variant_uses_variant_palette(root):
    btn = CorporateButton(root, text="S", variant="success")
    btn.configure(state="disabled")
    palette = BUTTON_VARIANTS["success"]
    assert btn.cget("bg") == palette["disabled_bg"]
    assert btn.cget("fg") == palette["disabled_fg"]


def test_configure_text_and_command(root):
    calls = []
    btn = CorporateButton(root, text="A", command=lambda: calls.append("old"))
    btn.config(text="B", command=lambda: calls.append("new"))
    assert btn.cget("text") == "B"
    btn.invoke()
    assert calls == ["new"]


def test_reenable_restores_normal_colors(root):
    btn = CorporateButton(root, text="Y", command=None)
    btn.configure(state="disabled")
    btn.configure(state="normal")
    assert btn.cget("state") == "normal"
    assert btn.cget("bg") == BTN_BG
    assert btn.cget("fg") == BTN_FG


def test_factory_accepts_variant(root):
    btn = create_corporate_button(
        root,
        app=None,
        text="Diag",
        command=None,
        pack=False,
        variant="diagnostic",
        width=None,
    )
    assert btn.cget("variant") == "diagnostic"
    assert btn.cget("bg") == PRIMARY_INDIGO


def test_cget_active_colors_follow_variant(root):
    btn = CorporateButton(root, text="C", variant="cancel")
    assert btn.cget("activebackground") == ACTION_CANCEL_HOVER
    assert btn.cget("activeforeground") == BUTTON_VARIANTS["cancel"]["fg"]


def test_primary_hover_pressed_legacy_colors(root):
    btn = CorporateButton(root, text="P")
    btn._on_enter()
    assert btn.cget("bg") == BTN_BG_HOVER
    btn._on_press()
    assert btn.cget("bg") == BTN_BG_PRESSED


def test_success_variant_colors(root):
    btn = CorporateButton(root, text="OK", variant="success")
    assert btn.cget("bg") == ACTION_SUCCESS
