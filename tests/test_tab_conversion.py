"""Tests de la pestaña CONVERSIÓN: registro UI y flujos de ejecución."""

import inspect
import tkinter as tk
from types import SimpleNamespace

import pytest

from scripts.pdf import img_a_pdf, ocr_pdf
from scripts.registry import get_scripts
from ui.common import ToolCard
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


def _collect_tool_cards(widget):
    cards = []
    if isinstance(widget, ToolCard):
        cards.append(widget)
    for child in widget.winfo_children():
        cards.extend(_collect_tool_cards(child))
    return cards


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


def _cards_by_title(tab):
    return {c.cget("title"): c for c in _collect_tool_cards(tab)}


def test_conversion_one_card_per_registered_tool_in_order(root):
    tab, _ = _build_conversion_tab(root)
    cards = _collect_tool_cards(tab)
    registered = [
        name
        for name, module in get_scripts("CONVERSIÓN").items()
        if getattr(module, "run", None) is not None
    ]
    assert len(cards) == len(registered)
    assert [c.cget("title") for c in cards] == registered
    assert all(isinstance(c, ToolCard) for c in cards)


def test_ocr_card_visible_in_conversion(root):
    tab, _ = _build_conversion_tab(root)
    cards = _cards_by_title(tab)
    assert "PDF escaneado a PDF OCR" in cards
    assert "Imagen a PDF" in cards


def test_ocr_card_uses_herramienta_flow(root):
    tab, calls = _build_conversion_tab(root)
    cards = _cards_by_title(tab)

    cards["PDF escaneado a PDF OCR"].invoke()

    assert len(calls) == 1
    flow, funcion, action = calls[0]
    assert flow == "herramienta"
    assert funcion is ocr_pdf.run
    assert action == "PDF escaneado a PDF OCR"


def test_img_a_pdf_keeps_ejecutar_flow(root):
    tab, calls = _build_conversion_tab(root)
    cards = _cards_by_title(tab)

    cards["Imagen a PDF"].invoke()

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
