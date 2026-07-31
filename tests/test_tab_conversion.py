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


def test_cancelacion_sin_resultados_no_abre_carpeta(tmp_path):
    """Cancelación vacía: estado cancelado y sin carpeta disponible."""
    from ui.app import App

    try:
        app = App()
        app.withdraw()
    except tk.TclError as exc:
        pytest.skip(f"Tk no disponible en este entorno: {exc}")

    try:
        app.status_bar.disable_open_button()
        app._aplicar_resultado_cancelado(
            "PDF escaneado a PDF OCR",
            {"message": "Cancelado", "output_dir": None, "stats": {}},
        )
        app.update_idletasks()
        app.update()
        assert app.last_result["message"] == "Cancelado"
        assert app.last_result["output_dir"] is None
        assert "files" not in app.last_result
        assert app.status_bar.btn_open.cget("state") == "disabled"
        assert app.status_bar._output_dir is None
    finally:
        try:
            app.destroy()
        except tk.TclError:
            pass


def test_cancelacion_parcial_conserva_carpeta_y_stats(tmp_path):
    """Cancelación parcial: conserva destino/files/stats y habilita abrir carpeta."""
    from ui.app import App

    dest = tmp_path / "salida_ocr"
    dest.mkdir()
    generated = dest / "documento_a_ocr.pdf"
    generated.write_bytes(b"%PDF-1.4")

    try:
        app = App()
        app.withdraw()
    except tk.TclError as exc:
        pytest.skip(f"Tk no disponible en este entorno: {exc}")

    try:
        app.status_bar.disable_open_button()
        app._aplicar_resultado_cancelado(
            "PDF escaneado a PDF OCR",
            {
                "message": "Cancelado",
                "output_dir": str(dest),
                "stats": {
                    "total": 2,
                    "procesados": 1,
                    "errores": 0,
                    "omitidos": 1,
                },
                "files": [str(generated)],
            },
        )
        app.update_idletasks()
        app.update()

        assert app.last_result["message"] == "Cancelado"
        assert app.last_result["output_dir"] == str(dest)
        assert app.last_result["files"] == [str(generated)]
        assert app.last_result["stats"]["procesados"] == 1
        assert app.last_result["stats"]["total"] == 2
        assert app.status_bar.btn_open.cget("state") == "normal"
        assert app.status_bar._output_dir == str(dest)
        assert app._estado_resultado(app.last_result["stats"]) != "success"
    finally:
        try:
            app.destroy()
        except tk.TclError:
            pass


def test_herramienta_flow_omits_diagnostic_arg_trace():
    """La ruta self-contained no registra la traza diagnóstica temporal de args."""
    from ui.app import App

    source = inspect.getsource(App._ejecutar_herramienta)
    assert "runner_" + "args" not in source
    assert "_aplicar_resultado_cancelado" in source


def test_ejecutar_uses_shared_cancel_handler():
    from ui.app import App

    source = inspect.getsource(App._ejecutar)
    assert "_aplicar_resultado_cancelado" in source
    assert 'output_dir": None' not in source.split("def on_cancelled", 1)[1].split(
        "def on_finally", 1
    )[0]
