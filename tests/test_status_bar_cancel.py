"""Tests del ciclo de vida del botón Cancelar en StatusBar."""

import tkinter as tk

import pytest

from ui.status_bar import StatusBar


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
