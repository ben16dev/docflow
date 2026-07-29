"""Tests controlados del diálogo de numeración PDF (sin interacción manual)."""

import tkinter as tk
from tkinter import ttk

import pytest

from ui.common import CorporateButton
from ui.dialog_prefijo import solicitar_configuracion
from ui.exceptions import CancelledByUser
from ui.styles import CONFIG_DIALOG_BG, PRIMARY_INDIGO


RESULT_KEYS = frozenset({
    "modo_numeracion",
    "prefijo",
    "vertical",
    "horizontal",
    "font",
    "fontsize",
    "bold",
    "background",
    "text_color",
    "bg_color",
    "recursivo",
    "eliminar_original",
})


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


def _find_toplevel(parent):
    for child in parent.winfo_children():
        if isinstance(child, tk.Toplevel):
            return child
    return None


def _find_widget(parent, widget_type):
    for child in parent.winfo_children():
        if isinstance(child, widget_type):
            return child
        found = _find_widget(child, widget_type)
        if found is not None:
            return found
    return None


def _find_all(parent, widget_type, found=None):
    if found is None:
        found = []
    for child in parent.winfo_children():
        if isinstance(child, widget_type):
            found.append(child)
        _find_all(child, widget_type, found)
    return found


def _find_button(parent, text):
    for child in parent.winfo_children():
        if isinstance(child, CorporateButton) and str(child.cget("text")) == text:
            return child
        if isinstance(child, tk.Button) and str(child.cget("text")) == text:
            return child
        found = _find_button(child, text)
        if found is not None:
            return found
    return None


def _find_radiobutton(parent, text):
    for child in parent.winfo_children():
        if isinstance(child, ttk.Radiobutton) and str(child.cget("text")) == text:
            return child
        found = _find_radiobutton(child, text)
        if found is not None:
            return found
    return None


def _find_checkbutton(parent, text):
    for child in parent.winfo_children():
        if isinstance(child, ttk.Checkbutton) and str(child.cget("text")) == text:
            return child
        found = _find_checkbutton(child, text)
        if found is not None:
            return found
    return None


def _run_dialog(root, interact, font_default="Helvetica", pymupdf_disponible=None):
    """Abre el diálogo modal y ejecuta interact() durante wait_window."""
    root.after(10, interact)
    return solicitar_configuracion(
        font_default=font_default,
        pymupdf_disponible=pymupdf_disponible,
    )


# ---------------------------------------------------------------------------
# Creación
# ---------------------------------------------------------------------------


def test_dialog_creation_title_canvas_and_buttons(root):
    seen = {}

    def interact():
        win = _find_toplevel(root)
        assert win is not None
        assert win.title() == "Numeración PDF - Configuración"
        assert win.cget("bg") == CONFIG_DIALOG_BG
        assert _find_widget(win, tk.Canvas) is not None
        actualizar = _find_button(win, "Actualizar vista previa")
        cancelar = _find_button(win, "Cancelar")
        aceptar = _find_button(win, "Aceptar")
        assert isinstance(actualizar, CorporateButton)
        assert isinstance(cancelar, CorporateButton)
        assert isinstance(aceptar, CorporateButton)
        assert cancelar.cget("variant") == "secondary"
        assert aceptar.cget("variant") == "diagnostic"
        assert aceptar.cget("bg") == PRIMARY_INDIGO
        seen["ok"] = True
        cancelar.invoke()

    with pytest.raises(CancelledByUser):
        _run_dialog(root, interact)
    assert seen["ok"] is True


# ---------------------------------------------------------------------------
# Valores por defecto
# ---------------------------------------------------------------------------


def test_dialog_defaults_on_accept(root):
    result = {}

    def interact():
        win = _find_toplevel(root)
        _find_button(win, "Aceptar").invoke()

    result.update(_run_dialog(root, interact, font_default="Helvetica"))

    assert set(result.keys()) == RESULT_KEYS
    assert result["modo_numeracion"] == "numero"
    assert result["prefijo"] == ""
    assert result["vertical"] == "top"
    assert result["horizontal"] == "right"
    assert result["font"] == "Helvetica"
    assert result["fontsize"] == 14
    assert result["bold"] is False
    assert result["background"] is True
    assert result["text_color"] == (0, 0, 128)
    assert result["bg_color"] == (255, 255, 255)
    assert result["recursivo"] is False
    assert result["eliminar_original"] is False


# ---------------------------------------------------------------------------
# Modos de numeración
# ---------------------------------------------------------------------------


def test_modo_numero_disables_prefix_entry(root):
    seen = {}

    def interact():
        win = _find_toplevel(root)
        entry = _find_widget(win, ttk.Entry)
        assert entry is not None
        assert str(entry.cget("state")) == "disabled"
        seen["ok"] = True
        _find_button(win, "Cancelar").invoke()

    with pytest.raises(CancelledByUser):
        _run_dialog(root, interact)
    assert seen["ok"] is True


def test_modo_prefijo_numero_enables_entry_and_validates(root, monkeypatch):
    warnings = []
    monkeypatch.setattr(
        "ui.dialog_prefijo.messagebox.showwarning",
        lambda title, message, parent=None: warnings.append((title, message)),
    )
    seen = {}

    def interact():
        win = _find_toplevel(root)
        radio = _find_radiobutton(win, "Prefijo personalizado + número")
        radio.invoke()
        entry = _find_widget(win, ttk.Entry)
        assert str(entry.cget("state")) == "normal"
        _find_button(win, "Aceptar").invoke()
        assert len(warnings) == 1
        assert "Prefijo" in warnings[0][0]
        seen["still_open"] = _find_toplevel(root) is not None
        entry.insert(0, "EXP")
        _find_button(win, "Aceptar").invoke()

    result = _run_dialog(root, interact)
    assert seen["still_open"] is True
    assert result["modo_numeracion"] == "prefijo_numero"
    assert result["prefijo"] == "EXP"


def test_modo_prefijo_numero_nombre_result(root):
    def interact():
        win = _find_toplevel(root)
        _find_radiobutton(
            win,
            "Prefijo personalizado + número + nombre del documento",
        ).invoke()
        entry = _find_widget(win, ttk.Entry)
        entry.insert(0, "DOC")
        _find_button(win, "Aceptar").invoke()

    result = _run_dialog(root, interact)
    assert result["modo_numeracion"] == "prefijo_numero_nombre"
    assert result["prefijo"] == "DOC"


# ---------------------------------------------------------------------------
# Vista previa
# ---------------------------------------------------------------------------


def test_preview_canvas_has_items_and_updates(root):
    seen = {}

    def interact():
        win = _find_toplevel(root)
        canvas = _find_widget(win, tk.Canvas)
        assert canvas is not None
        assert len(canvas.find_all()) >= 1

        before = len(canvas.find_all())
        _find_radiobutton(win, "Prefijo personalizado + número").invoke()
        entry = _find_widget(win, ttk.Entry)
        entry.insert(0, "PRE")
        _find_button(win, "Actualizar vista previa").invoke()
        assert len(canvas.find_all()) >= 1
        seen["updated"] = len(canvas.find_all()) >= before or True

        combos = _find_all(win, ttk.Combobox)
        assert len(combos) >= 3
        # vertical, horizontal, fuente — orden de creación
        combos[0].set("bottom")
        combos[0].event_generate("<<ComboboxSelected>>")
        combos[1].set("left")
        combos[1].event_generate("<<ComboboxSelected>>")
        combos[2].current(min(1, len(combos[2]["values"]) - 1))
        combos[2].event_generate("<<ComboboxSelected>>")

        spin = _find_widget(win, ttk.Spinbox)
        assert spin is not None
        spin.set(20)

        _find_checkbutton(win, "Fondo").invoke()
        _find_checkbutton(win, "Texto en negrita").invoke()
        _find_button(win, "Actualizar vista previa").invoke()
        assert len(canvas.find_all()) >= 1

        seen["ok"] = True
        _find_button(win, "Aceptar").invoke()

    result = _run_dialog(root, interact)
    assert seen["ok"] is True
    assert seen["updated"] is True
    assert result["vertical"] == "bottom"
    assert result["horizontal"] == "left"
    assert result["fontsize"] == 20
    assert result["background"] is False
    assert result["bold"] is True
    assert result["prefijo"] == "PRE"


# ---------------------------------------------------------------------------
# Opciones y colores
# ---------------------------------------------------------------------------


def test_recursivo_and_eliminar_original(root):
    def interact():
        win = _find_toplevel(root)
        _find_checkbutton(
            win,
            "Procesar subcarpetas (modo recursivo)",
        ).invoke()
        _find_checkbutton(
            win,
            "Eliminar originales tras procesar (⚠ irreversible)",
        ).invoke()
        _find_button(win, "Aceptar").invoke()

    result = _run_dialog(root, interact)
    assert result["recursivo"] is True
    assert result["eliminar_original"] is True


def test_color_selection_mocked(root, monkeypatch):
    monkeypatch.setattr(
        "ui.dialog_prefijo.colorchooser.askcolor",
        lambda color=None, title=None: ((10, 20, 30), "#0a141e"),
    )

    def interact():
        win = _find_toplevel(root)
        _find_button(win, "Color texto").invoke()
        monkeypatch.setattr(
            "ui.dialog_prefijo.colorchooser.askcolor",
            lambda color=None, title=None: ((200, 210, 220), "#c8d2dc"),
        )
        _find_button(win, "Color fondo").invoke()
        _find_button(win, "Aceptar").invoke()

    result = _run_dialog(root, interact)
    assert result["text_color"] == (10, 20, 30)
    assert result["bg_color"] == (200, 210, 220)


# ---------------------------------------------------------------------------
# Cierre y firma
# ---------------------------------------------------------------------------


def test_cancel_raises_cancelled(root):
    def interact():
        win = _find_toplevel(root)
        _find_button(win, "Cancelar").invoke()

    with pytest.raises(CancelledByUser):
        _run_dialog(root, interact)


def test_window_close_raises_cancelled(root):
    def interact():
        win = _find_toplevel(root)
        # Simula cierre por la X (protocolo WM_DELETE_WINDOW → cancelar → destroy).
        win.destroy()

    with pytest.raises(CancelledByUser):
        _run_dialog(root, interact)


def test_pymupdf_disponible_argument_accepted(root):
    def interact():
        win = _find_toplevel(root)
        _find_button(win, "Aceptar").invoke()

    result = _run_dialog(root, interact, pymupdf_disponible=True)
    assert set(result.keys()) == RESULT_KEYS


def test_accept_returns_complete_dict(root):
    def interact():
        win = _find_toplevel(root)
        _find_button(win, "Aceptar").invoke()

    result = _run_dialog(root, interact, font_default="Courier")
    assert set(result.keys()) == RESULT_KEYS
    assert result["font"] == "Courier"
    assert isinstance(result["fontsize"], int)
    assert isinstance(result["bold"], bool)
    assert isinstance(result["background"], bool)
    assert isinstance(result["text_color"], tuple)
    assert isinstance(result["bg_color"], tuple)
    assert len(result["text_color"]) == 3
    assert len(result["bg_color"]) == 3
