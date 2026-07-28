"""Tests del ciclo de vida de la progressbar (StatusBar + contrato App)."""

import inspect
import tkinter as tk

import pytest

from ui.app import App
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


def _make_status_bar(root):
    return StatusBar(
        parent=root,
        app_name="DocFlow",
        app_version="0.0.0",
        app_author="Test",
        cancel_callback=lambda: None,
    )


def test_progress_initial_value_is_zero(root):
    status_bar = _make_status_bar(root)
    assert float(status_bar.progress["value"]) == 0.0


def test_progress_resets_to_zero_on_start(root):
    status_bar = _make_status_bar(root)
    status_bar.set_progress(3, 4)
    assert float(status_bar.progress["value"]) == 75.0
    status_bar.reset_progress()
    assert float(status_bar.progress["value"]) == 0.0


def test_progress_complete_sets_maximum(root):
    status_bar = _make_status_bar(root)
    status_bar.set_progress(1, 4)
    status_bar.complete_progress()
    assert float(status_bar.progress["value"]) == 100.0
    assert str(status_bar.progress["mode"]) == "determinate"


def test_success_does_not_empty_progress(root):
    status_bar = _make_status_bar(root)
    status_bar.set_progress(4, 4)
    status_bar.complete_progress()
    # Tras éxito no se llama reset: la barra permanece llena.
    assert float(status_bar.progress["value"]) == 100.0


def test_cancel_and_error_do_not_leave_progress_at_100(root):
    status_bar = _make_status_bar(root)
    status_bar.set_progress(2, 3)
    status_bar.reset_progress()
    assert float(status_bar.progress["value"]) == 0.0
    assert float(status_bar.progress["value"]) != 100.0

    status_bar.complete_progress()
    status_bar.reset_progress()
    assert float(status_bar.progress["value"]) == 0.0


def test_new_run_clears_previous_progress(root):
    status_bar = _make_status_bar(root)
    status_bar.complete_progress()
    assert float(status_bar.progress["value"]) == 100.0
    status_bar.reset_progress()
    assert float(status_bar.progress["value"]) == 0.0
    status_bar.set_progress(0, 5)
    assert float(status_bar.progress["value"]) == 0.0


def test_app_execution_progress_contract():
    """_ejecutar / _ejecutar_herramienta: éxito completa; error/cancel reinicia; finally no vacía."""
    for method in (App._ejecutar, App._ejecutar_herramienta):
        source = inspect.getsource(method)
        assert "complete_progress" in source
        assert "on_finally" in source
        # El finally ya no debe vaciar la barra tras un éxito.
        finally_block = source.split("def on_finally", 1)[1]
        assert "reset_progress" not in finally_block
        assert "reset_progress" in source  # error / cancelado
        assert source.index("complete_progress") < source.index("def on_error")
