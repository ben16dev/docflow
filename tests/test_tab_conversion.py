"""Tests de la pestaña CONVERSIÓN: registro UI y flujos de ejecución."""

import inspect
import tkinter as tk
from types import SimpleNamespace

import pytest

from scripts.pdf import img_a_pdf, ocr_pdf
from ui.common import CorporateButton
from ui.tabs import tab_conversion


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


def _build_conversion_tab(root):
    """Construye la pestaña con un app mínimo que registra el flujo usado."""
    calls = []

    def _ejecutar(funcion, *args, **kwargs):
        calls.append(("ejecutar", funcion, kwargs.get("action")))

    def _ejecutar_herramienta(funcion, *args, **kwargs):
        calls.append(("herramienta", funcion, kwargs.get("action")))

    app = SimpleNamespace(
        var_ruta=tk.StringVar(master=root, value=""),
        _seleccionar_carpeta=lambda: None,
        _ejecutar=_ejecutar,
        _ejecutar_herramienta=_ejecutar_herramienta,
    )

    tab = tk.Frame(root)
    tab_conversion.build_tab(tab, app)
    return tab, calls


def _buttons_by_text(tab):
    found = {}
    for widget in tab.winfo_children():
        for child in widget.winfo_children():
            if isinstance(child, tk.Frame):
                for btn in child.winfo_children():
                    if isinstance(btn, CorporateButton):
                        found[btn.cget("text")] = btn
    return found


def test_ocr_button_visible_in_conversion(root):
    tab, _ = _build_conversion_tab(root)
    buttons = _buttons_by_text(tab)
    assert "PDF escaneado a PDF OCR" in buttons
    assert "Imagen a PDF" in buttons


def test_ocr_button_uses_herramienta_flow(root):
    tab, calls = _build_conversion_tab(root)
    buttons = _buttons_by_text(tab)

    buttons["PDF escaneado a PDF OCR"].invoke()

    assert len(calls) == 1
    flow, funcion, action = calls[0]
    assert flow == "herramienta"
    assert funcion is ocr_pdf.run
    assert action == "PDF escaneado a PDF OCR"


def test_img_a_pdf_keeps_ejecutar_flow(root):
    tab, calls = _build_conversion_tab(root)
    buttons = _buttons_by_text(tab)

    buttons["Imagen a PDF"].invoke()

    assert len(calls) == 1
    flow, funcion, action = calls[0]
    assert flow == "ejecutar"
    assert funcion is img_a_pdf.run
    assert action == "Imagen a PDF"


def test_ocr_listed_as_self_contained():
    assert "PDF escaneado a PDF OCR" in tab_conversion._SELF_CONTAINED_TOOLS
    assert "Imagen a PDF" not in tab_conversion._SELF_CONTAINED_TOOLS


def test_ejecutar_herramienta_does_not_validate_folder():
    """El flujo de OCR no exige carpeta de trabajo previa."""
    from ui.app import App

    source = inspect.getsource(App._ejecutar_herramienta)
    assert "_validar_carpeta" not in source
    assert "askyesno" not in source

    source_ejecutar = inspect.getsource(App._ejecutar)
    assert "_validar_carpeta" in source_ejecutar


def test_ocr_cancellation_reaches_on_cancelled(monkeypatch):
    """Cancelación de OCR llega a on_cancelled vía ScriptRunner."""
    from core.script_runner import ScriptRunner
    from ui.exceptions import CancelledByUser

    def fake_run(progress=None, is_cancelled=None):
        raise CancelledByUser()

    monkeypatch.setattr(ocr_pdf, "run", fake_run)

    runner = ScriptRunner()
    cancelled = []
    success = []
    errors = []
    done = []

    runner.run(
        funcion=ocr_pdf.run,
        progress=lambda a, t: None,
        is_cancelled=lambda: False,
        on_success=lambda r: success.append(r),
        on_error=lambda e: errors.append(e),
        on_cancelled=lambda r: cancelled.append(r),
        on_finally=lambda: done.append(True),
    )

    runner._thread.join(timeout=5)

    assert done == [True]
    assert success == []
    assert errors == []
    assert len(cancelled) == 1
    assert cancelled[0]["message"] == "Cancelado"
