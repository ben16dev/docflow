"""Tests controlados del diálogo de error (sin ventanas visibles ni interacción manual)."""

import tkinter as tk
from unittest.mock import MagicMock

import pytest

from ui.common import CorporateButton
from ui.dialog_error import show_error_dialog
from ui.styles import (
    ERROR_DIALOG_BG,
    ERROR_DIALOG_DETAIL_BG,
    ERROR_DIALOG_HEADER_FG,
    ERROR_DIALOG_LOG_FG,
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


def _find_label_with_text(parent, text):
    for child in parent.winfo_children():
        if isinstance(child, tk.Label) and str(child.cget("text")) == text:
            return child
        found = _find_label_with_text(child, text)
        if found is not None:
            return found
    return None


def _run_dialog(root, user_message, log_file, interact):
    """Abre el diálogo modal y ejecuta interact() en el bucle anidado de wait_window."""
    root.after(10, interact)
    show_error_dialog(parent=root, user_message=user_message, log_file=log_file)


def test_dialog_shows_user_message(root):
    message = "Fallo controlado de prueba"
    seen = {}

    def interact():
        win = _find_toplevel(root)
        assert win is not None
        text = _find_widget(win, tk.Text)
        assert text is not None
        seen["content"] = text.get("1.0", "end-1c")
        _find_button(win, "Cerrar").invoke()

    _run_dialog(root, message, None, interact)
    assert seen["content"] == message


def test_dialog_does_not_show_traceback_unless_in_user_message(root):
    message = "Error de acceso al sistema de archivos."
    seen = {}

    def interact():
        win = _find_toplevel(root)
        text = _find_widget(win, tk.Text)
        seen["content"] = text.get("1.0", "end-1c")
        _find_button(win, "Cerrar").invoke()

    _run_dialog(root, message, None, interact)
    assert "Traceback" not in seen["content"]
    assert seen["content"] == message


def test_dialog_copy_message_to_clipboard(root):
    message = "Mensaje para copiar"

    def interact():
        win = _find_toplevel(root)
        _find_button(win, "Copiar mensaje").invoke()
        _find_button(win, "Cerrar").invoke()

    _run_dialog(root, message, None, interact)
    assert root.clipboard_get() == message


def test_dialog_open_log_calls_open_path(root, tmp_path, monkeypatch):
    log_file = tmp_path / "docflow_test.log"
    log_file.write_text("error técnico\n", encoding="utf-8")
    opened = MagicMock()
    monkeypatch.setattr("ui.dialog_error.open_path", opened)

    def interact():
        win = _find_toplevel(root)
        _find_button(win, "Abrir log").invoke()
        _find_button(win, "Cerrar").invoke()

    _run_dialog(root, "Error con log", str(log_file), interact)
    opened.assert_called_once_with(str(log_file))


def test_dialog_missing_log_shows_warning_without_crash(root, tmp_path, monkeypatch):
    missing = tmp_path / "no_existe.log"
    warnings = []
    monkeypatch.setattr(
        "ui.dialog_error.messagebox.showwarning",
        lambda title, message, parent=None: warnings.append((title, message)),
    )
    opened = MagicMock()
    monkeypatch.setattr("ui.dialog_error.open_path", opened)

    def interact():
        win = _find_toplevel(root)
        _find_button(win, "Abrir log").invoke()
        _find_button(win, "Cerrar").invoke()

    _run_dialog(root, "Error sin log", str(missing), interact)
    assert opened.call_count == 0
    assert len(warnings) == 1
    assert "no disponible" in warnings[0][0].lower() or "no" in warnings[0][1].lower()


def test_dialog_long_message_is_scrollable(root):
    lines = [f"Línea {i} del mensaje de error largo" for i in range(1, 41)]
    message = "\n".join(lines)
    seen = {}

    def interact():
        win = _find_toplevel(root)
        text = _find_widget(win, tk.Text)
        scrollbar = _find_widget(win, tk.Scrollbar)
        assert text is not None
        assert scrollbar is not None

        content = text.get("1.0", "end-1c")
        seen["content"] = content
        seen["has_first"] = "Línea 1 " in content
        seen["has_last"] = "Línea 40 " in content

        text.yview_moveto(1.0)
        bottom = text.yview()
        text.yview_moveto(0.0)
        top = text.yview()
        seen["scrolled"] = bottom != top or bottom[0] > 0 or top[0] == 0.0

        _find_button(win, "Cerrar").invoke()

    _run_dialog(root, message, None, interact)
    assert seen["content"] == message
    assert seen["has_first"] is True
    assert seen["has_last"] is True
    assert seen["scrolled"] is True


def test_dialog_uses_design_tokens_and_corporate_buttons(root):
    seen = {}

    def interact():
        win = _find_toplevel(root)
        assert win.cget("bg") == ERROR_DIALOG_BG
        text = _find_widget(win, tk.Text)
        assert text.cget("bg") == ERROR_DIALOG_DETAIL_BG
        copiar = _find_button(win, "Copiar mensaje")
        cerrar = _find_button(win, "Cerrar")
        assert isinstance(copiar, CorporateButton)
        assert isinstance(cerrar, CorporateButton)
        assert copiar.cget("variant") == "secondary"
        assert cerrar.cget("variant") == "diagnostic"
        assert cerrar.cget("bg") == PRIMARY_INDIGO
        header = None
        for child in win.winfo_children():
            header = _find_label_with_text(child, "Se ha producido un error")
            if header is not None:
                break
        assert header is not None
        assert header.cget("fg") == ERROR_DIALOG_HEADER_FG
        seen["ok"] = True
        cerrar.invoke()

    _run_dialog(root, "Error visual", None, interact)
    assert seen["ok"] is True


def test_dialog_close_releases_grab(root):
    def interact():
        win = _find_toplevel(root)
        _find_button(win, "Cerrar").invoke()

    _run_dialog(root, "Cierre limpio", None, interact)
    assert _find_toplevel(root) is None


def test_dialog_api_accepts_none_log(root):
    def interact():
        win = _find_toplevel(root)
        assert _find_button(win, "Abrir log") is None
        log_lbl = None
        for child in win.winfo_children():
            log_lbl = _find_label_with_text(child, "Log: no disponible")
            if log_lbl is not None:
                break
        assert log_lbl is not None
        assert log_lbl.cget("fg") == ERROR_DIALOG_LOG_FG
        _find_button(win, "Cerrar").invoke()

    _run_dialog(root, "Sin log", None, interact)
