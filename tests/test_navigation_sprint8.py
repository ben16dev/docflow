"""Tests de navegación Sprint 8: validación de las 3 pestañas principales."""

import tkinter as tk

import pytest


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


def test_only_three_tabs_exist(root):
    """Valida que solo existen 3 pestañas."""
    from ui.app import App

    app = App()
    app.withdraw()

    try:
        tab_count = app.notebook.index("end")
        assert tab_count == 3
    finally:
        try:
            app.destroy()
        except tk.TclError:
            pass


def test_tab_order_is_correct(root):
    """Valida el orden: PDF → RENOMBRADO → CONVERSIÓN."""
    from ui.app import App

    app = App()
    app.withdraw()

    try:
        assert app.notebook.tab(0, "text") == "PDF"
        assert app.notebook.tab(1, "text") == "RENOMBRADO"
        assert app.notebook.tab(2, "text") == "CONVERSIÓN"
    finally:
        try:
            app.destroy()
        except tk.TclError:
            pass


def test_mbox_and_eml_tabs_do_not_exist(root):
    """Valida que MBOX y EML ya no existen como pestañas."""
    from ui.app import App

    app = App()
    app.withdraw()

    try:
        tab_texts = [
            app.notebook.tab(i, "text")
            for i in range(app.notebook.index("end"))
        ]
        assert "MBOX" not in tab_texts
        assert "EML" not in tab_texts
    finally:
        try:
            app.destroy()
        except tk.TclError:
            pass


def test_archivos_renamed_to_renombrado(root):
    """Valida que la pestaña Archivos ahora se llama RENOMBRADO."""
    from ui.app import App

    app = App()
    app.withdraw()

    try:
        tab_texts = [
            app.notebook.tab(i, "text")
            for i in range(app.notebook.index("end"))
        ]
        assert "RENOMBRADO" in tab_texts
        assert "Archivos" not in tab_texts
    finally:
        try:
            app.destroy()
        except tk.TclError:
            pass
