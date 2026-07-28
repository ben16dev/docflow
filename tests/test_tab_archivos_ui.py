"""Tests de UI del flujo Renombrar archivos (estado vacío y botones)."""

import tkinter as tk
from types import SimpleNamespace

import pytest

from scripts.files.session import SesionRenombrado
from ui.common import CorporateButton, EmptyState, create_toolbar_button
from ui.styles import ACTION_CANCEL, BUTTON_VARIANTS
from ui.tabs import tab_archivos


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
    sesion = SesionRenombrado()
    app = SimpleNamespace()
    panel = tab_archivos._PanelSeleccion(root, app, sesion, on_siguiente=lambda: None)
    panel.pack(fill="both", expand=True)
    root.update_idletasks()
    return panel, sesion


def test_empty_state_visible_when_list_empty(root):
    panel, _sesion = _make_panel(root)
    assert isinstance(panel._empty, EmptyState)
    assert panel._empty.grid_info()  # gestionado por grid (visible)
    assert panel._tree.get_children() == ()


def test_empty_state_hides_when_files_added(root, tmp_path):
    panel, sesion = _make_panel(root)
    f1 = tmp_path / "a.pdf"
    f1.write_text("x")
    sesion.agregar([f1])
    panel._refrescar_tabla()
    root.update_idletasks()

    assert panel._empty.grid_info() == {}
    assert len(panel._tree.get_children()) == 1
    assert panel._tree.item(panel._tree.get_children()[0], "values")[1] == "a"


def test_empty_state_returns_after_clear(root, tmp_path):
    panel, sesion = _make_panel(root)
    f1 = tmp_path / "b.txt"
    f1.write_text("y")
    sesion.agregar([f1])
    panel._refrescar_tabla()
    sesion.limpiar()
    panel._refrescar_tabla()
    root.update_idletasks()

    assert panel._empty.grid_info()
    assert panel._tree.get_children() == ()


def test_empty_state_does_not_alter_tree_columns(root):
    panel, _sesion = _make_panel(root)
    assert tuple(panel._tree["columns"]) == ("orden", "nombre", "extension", "ruta")
    assert panel._tree.heading("nombre", "text") == "Nombre"


def test_toolbar_destructive_variant(root):
    calls = []
    btn = create_toolbar_button(
        root,
        "Eliminar",
        command=lambda: calls.append(1),
        variant="destructive",
    )
    assert isinstance(btn, CorporateButton)
    assert btn.cget("variant") == "destructive"
    assert btn.cget("fg") == ACTION_CANCEL
    assert btn.cget("bg") == BUTTON_VARIANTS["destructive"]["bg"]
    btn.invoke()
    assert calls == [1]


def test_toolbar_disabled_does_not_invoke(root):
    calls = []
    btn = create_toolbar_button(root, "Subir", command=lambda: calls.append(1))
    btn.configure(state="disabled")
    btn.invoke()
    btn._on_activate_key()
    assert calls == []


def test_panel_buttons_are_corporate(root):
    panel, _sesion = _make_panel(root)
    assert isinstance(panel._btn_anadir, CorporateButton)
    assert isinstance(panel._btn_subir, CorporateButton)
    assert isinstance(panel._btn_eliminar, CorporateButton)
    assert panel._btn_eliminar.cget("variant") == "destructive"
    assert panel._btn_siguiente.cget("state") == "disabled"


def test_flow_steps_constant():
    assert tab_archivos._FLOW_STEPS == (
        "Selección",
        "Nombres",
        "Previsualización",
    )
