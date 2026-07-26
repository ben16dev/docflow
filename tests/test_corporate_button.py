"""Tests del componente CorporateButton (factoría create_corporate_button)."""

import tkinter as tk

import pytest

from ui.common import CorporateButton, create_corporate_button
from ui.styles import BTN_BG, BTN_BG_DISABLED, BTN_FG, BTN_FG_DISABLED_SURFACE


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
    btn.grid(row=0, column=0)
    btn.invoke()
    assert calls == [1]


def test_disabled_does_not_invoke(root):
    calls = []
    btn = CorporateButton(root, text="X", command=lambda: calls.append(1))
    btn.configure(state="disabled")
    assert btn["state"] == "disabled"
    assert btn.cget("bg") == BTN_BG_DISABLED
    assert btn.cget("fg") == BTN_FG_DISABLED_SURFACE
    btn.invoke()
    assert calls == []


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
