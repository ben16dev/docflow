"""Tests del ciclo de vida de ProgressPanel y contrato App."""

import inspect
import tkinter as tk

import pytest

from ui.app import App
from ui.progress_panel import ProgressPanel
from ui.status_bar import StatusBar
from ui.styles import PROGRESS_PANEL_HEIGHT, STATUS_BAR_HEIGHT


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


def _make_panel(root):
    return ProgressPanel(root)


# ---------------------------------------------------------------------------
# ProgressPanel
# ---------------------------------------------------------------------------


def test_progress_panel_creation(root):
    panel = _make_panel(root)
    assert isinstance(panel, ProgressPanel)
    assert hasattr(panel, "progress")
    assert hasattr(panel, "lbl_percent")


def test_progress_initial_value_is_zero(root):
    panel = _make_panel(root)
    assert float(panel.progress["value"]) == 0.0
    assert panel.lbl_percent.cget("text") == "0 %"
    assert str(panel.progress["mode"]) == "determinate"
    assert panel._state == "idle"


def test_progress_resets_to_zero_on_start(root):
    panel = _make_panel(root)
    panel.set_progress(3, 4)
    assert float(panel.progress["value"]) == 75.0
    panel.reset_progress()
    assert float(panel.progress["value"]) == 0.0
    assert panel.lbl_percent.cget("text") == "0 %"


def test_progress_determined_fifty_percent(root):
    panel = _make_panel(root)
    panel.set_progress(1, 2)
    assert float(panel.progress["value"]) == 50.0
    assert panel.lbl_percent.cget("text") == "50 %"


def test_progress_clamps_lower_and_upper(root):
    panel = _make_panel(root)
    panel.set_progress(-5, 10)
    assert float(panel.progress["value"]) == 0.0
    panel.set_progress(20, 10)
    assert float(panel.progress["value"]) == 100.0


def test_progress_total_zero_does_not_fake_progress(root):
    panel = _make_panel(root)
    panel.set_progress(3, 0)
    assert float(panel.progress["value"]) == 0.0
    assert panel.lbl_percent.cget("text") == "0 %"


def test_progress_complete_sets_maximum(root):
    panel = _make_panel(root)
    panel.set_progress(1, 4)
    panel.complete_progress()
    assert float(panel.progress["value"]) == 100.0
    assert panel.lbl_percent.cget("text") == "100 %"
    assert str(panel.progress["mode"]) == "determinate"
    assert panel._state == "success"


def test_success_does_not_empty_progress(root):
    panel = _make_panel(root)
    panel.set_progress(4, 4)
    panel.complete_progress()
    assert float(panel.progress["value"]) == 100.0
    assert panel.lbl_percent.cget("text") == "100 %"


def test_reset_after_success_clears_progress(root):
    panel = _make_panel(root)
    panel.complete_progress()
    assert float(panel.progress["value"]) == 100.0
    panel.reset_progress()
    assert float(panel.progress["value"]) == 0.0
    assert panel.lbl_percent.cget("text") == "0 %"


def test_error_does_not_leave_progress_at_100(root):
    panel = _make_panel(root)
    panel.set_progress(2, 3)
    panel.set_error()
    assert float(panel.progress["value"]) == 0.0
    assert float(panel.progress["value"]) != 100.0
    assert panel._state == "error"


def test_cancel_does_not_leave_progress_at_100(root):
    panel = _make_panel(root)
    panel.complete_progress()
    panel.set_cancelled()
    assert float(panel.progress["value"]) == 0.0
    assert panel._state == "cancelled"


def test_cancel_and_error_via_reset_do_not_leave_100(root):
    panel = _make_panel(root)
    panel.set_progress(2, 3)
    panel.reset_progress()
    assert float(panel.progress["value"]) == 0.0

    panel.complete_progress()
    panel.reset_progress()
    assert float(panel.progress["value"]) == 0.0


def test_new_run_clears_previous_progress(root):
    panel = _make_panel(root)
    panel.complete_progress()
    assert float(panel.progress["value"]) == 100.0
    panel.reset_progress()
    assert float(panel.progress["value"]) == 0.0
    panel.set_progress(0, 5)
    assert float(panel.progress["value"]) == 0.0


def test_indeterminate_start_and_return_to_determinate(root):
    panel = _make_panel(root)
    panel.start(indeterminate=True)
    assert str(panel.progress["mode"]) == "indeterminate"
    assert panel.lbl_percent.cget("text") == "—"
    assert panel._indeterminate is True

    panel.complete_progress()
    assert str(panel.progress["mode"]) == "determinate"
    assert float(panel.progress["value"]) == 100.0
    assert panel._indeterminate is False

    panel.start(indeterminate=True)
    panel.set_error()
    assert str(panel.progress["mode"]) == "determinate"
    assert float(panel.progress["value"]) == 0.0

    panel.start(indeterminate=True)
    panel.reset_progress()
    assert str(panel.progress["mode"]) == "determinate"
    assert float(panel.progress["value"]) == 0.0


def test_progress_panel_requested_height_stable(root):
    panel = _make_panel(root)
    assert int(panel.cget("height")) == PROGRESS_PANEL_HEIGHT
    assert 46 <= PROGRESS_PANEL_HEIGHT <= 54
    panel.update_idletasks()
    assert panel.winfo_reqheight() == PROGRESS_PANEL_HEIGHT


# ---------------------------------------------------------------------------
# Integración App / StatusBar
# ---------------------------------------------------------------------------


def test_app_creates_progress_panel_without_status_progress():
    try:
        app = App()
        app.withdraw()
    except tk.TclError as exc:
        pytest.skip(f"Tk no disponible en este entorno: {exc}")

    try:
        assert isinstance(app.progress_panel, ProgressPanel)
        assert isinstance(app.status_bar, StatusBar)
        assert not hasattr(app.status_bar, "progress")
        assert hasattr(app.progress_panel, "progress")
        assert int(app.status_bar.cget("height")) == STATUS_BAR_HEIGHT
        assert 42 <= STATUS_BAR_HEIGHT <= 48
    finally:
        try:
            app.destroy()
        except tk.TclError:
            pass


def test_app_execution_progress_contract():
    """_ejecutar / _ejecutar_herramienta: progreso vía progress_panel; finally no vacía."""
    for method in (App._ejecutar, App._ejecutar_herramienta):
        source = inspect.getsource(method)
        assert "progress_panel.complete_progress" in source or (
            "complete_progress" in source and "progress_panel" in source
        )
        assert "progress_panel" in source
        assert "status_bar.set_progress" not in source
        assert "status_bar.complete_progress" not in source
        assert "status_bar.reset_progress" not in source
        assert "on_finally" in source
        finally_block = source.split("def on_finally", 1)[1]
        assert "reset_progress" not in finally_block
        assert "reset_progress" in source
        assert source.index("complete_progress") < source.index("def on_error")


def test_status_bar_height_reduced_without_progress(root):
    status_bar = StatusBar(
        parent=root,
        app_name="DocFlow",
        app_version="0.0.0",
        app_author="Test",
        cancel_callback=lambda: None,
    )
    assert not hasattr(status_bar, "progress")
    assert int(status_bar.cget("height")) == STATUS_BAR_HEIGHT
    assert status_bar.btn_cancel is not None
    assert status_bar.lbl_status is not None
