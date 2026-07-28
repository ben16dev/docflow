"""Tests del ciclo de vida del botón Cancelar en StatusBar."""

import tkinter as tk

import pytest

from ui.common import CorporateButton
from ui.status_bar import StatusBar
from ui.styles import (
    ACTION_CANCEL,
    BUTTON_VARIANTS,
    PRIMARY_INDIGO,
    STATE_CANCELLED,
    STATE_IDLE,
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


def _make_status_bar(root, cancel_callback=None):
    return StatusBar(
        parent=root,
        app_name="DocFlow",
        app_version="0.0.0",
        app_author="Test",
        cancel_callback=cancel_callback,
    )


def test_cancel_button_disabled_at_rest(root):
    status_bar = _make_status_bar(root)
    assert str(status_bar.btn_cancel["state"]) == "disabled"


def test_cancel_button_enabled_during_execution(root):
    status_bar = _make_status_bar(root)
    status_bar.enable_cancel_button()
    assert str(status_bar.btn_cancel["state"]) == "normal"


def test_cancel_button_disables_immediately_on_click(root):
    calls = []
    status_bar = _make_status_bar(root, cancel_callback=lambda: calls.append(1))
    status_bar.enable_cancel_button()

    status_bar._cancelar()

    assert str(status_bar.btn_cancel["state"]) == "disabled"
    assert calls == [1]


def test_cancel_button_click_while_disabled_does_nothing(root):
    calls = []
    status_bar = _make_status_bar(root, cancel_callback=lambda: calls.append(1))
    # Reposo: sin ejecución activa, el botón está deshabilitado.
    status_bar._cancelar()

    assert calls == []
    assert str(status_bar.btn_cancel["state"]) == "disabled"


def test_cancel_button_disabled_after_finishing(root):
    status_bar = _make_status_bar(root)
    status_bar.enable_cancel_button()
    status_bar._cancelar()

    # on_finally llama a disable_cancel_button independientemente del resultado.
    status_bar.disable_cancel_button()

    assert str(status_bar.btn_cancel["state"]) == "disabled"


def test_status_bar_buttons_are_corporate_with_variants(root):
    status_bar = _make_status_bar(root)
    assert isinstance(status_bar.btn_cancel, CorporateButton)
    assert isinstance(status_bar.btn_open, CorporateButton)
    assert isinstance(status_bar.btn_diag, CorporateButton)
    assert status_bar.btn_cancel.cget("variant") == "cancel"
    assert status_bar.btn_open.cget("variant") == "success"
    assert status_bar.btn_diag.cget("variant") == "diagnostic"
    assert status_bar.btn_cancel.cget("bg") == BUTTON_VARIANTS["cancel"]["disabled_bg"]
    status_bar.enable_cancel_button()
    assert status_bar.btn_cancel.cget("bg") == ACTION_CANCEL
    assert status_bar.btn_open.cget("bg") == BUTTON_VARIANTS["success"]["disabled_bg"]
    assert status_bar.btn_diag.cget("bg") == PRIMARY_INDIGO


def test_btn_diag_command_can_be_replaced(root):
    calls = []
    status_bar = _make_status_bar(root)
    status_bar.btn_diag.config(command=lambda: calls.append("app"))
    status_bar.btn_diag.invoke()
    assert calls == ["app"]


def test_set_state_cancelado_uses_distinct_color(root):
    status_bar = _make_status_bar(root)
    status_bar.set_state("idle")
    idle_fg = status_bar.lbl_timer.cget("fg")
    assert idle_fg == STATE_IDLE

    status_bar.set_state("cancelado")
    cancelled_fg = status_bar.lbl_timer.cget("fg")
    assert cancelled_fg == STATE_CANCELLED
    assert cancelled_fg != idle_fg
    assert cancelled_fg != status_bar.COLORS["success"]
    assert cancelled_fg != status_bar.COLORS["error"]
    assert cancelled_fg != status_bar.COLORS["running"]
