"""Tests del componente StepIndicator."""

import tkinter as tk

import pytest

from ui.common import StepIndicator
from ui.styles import (
    STEP_ACTIVE_BG,
    STEP_COMPLETED_BG,
    STEP_PENDING_BG,
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


def test_create_with_steps(root):
    ind = StepIndicator(root, steps=("A", "B", "C"), active=0)
    assert ind.steps == ("A", "B", "C")
    assert ind.active == 0
    assert ind.step_state(0) == "activo"
    assert ind.step_state(1) == "pendiente"
    assert ind.step_state(2) == "pendiente"


def test_initial_active_colors(root):
    ind = StepIndicator(root, steps=("Uno", "Dos"), active=0)
    assert ind._markers[0].cget("bg") == STEP_ACTIVE_BG
    assert ind._markers[1].cget("bg") == STEP_PENDING_BG


def test_set_active_updates_states(root):
    ind = StepIndicator(root, steps=("A", "B", "C"), active=0)
    ind.set_active(1)
    assert ind.active == 1
    assert ind.step_state(0) == "completado"
    assert ind.step_state(1) == "activo"
    assert ind.step_state(2) == "pendiente"
    assert ind._markers[0].cget("bg") == STEP_COMPLETED_BG
    assert ind._markers[1].cget("bg") == STEP_ACTIVE_BG
    assert ind._markers[2].cget("bg") == STEP_PENDING_BG

    ind.set_active(2)
    assert ind.step_state(0) == "completado"
    assert ind.step_state(1) == "completado"
    assert ind.step_state(2) == "activo"


def test_empty_steps_raises(root):
    with pytest.raises(ValueError, match="al menos un paso"):
        StepIndicator(root, steps=[], active=0)


def test_out_of_range_set_active_raises(root):
    ind = StepIndicator(root, steps=("A", "B"), active=0)
    with pytest.raises(IndexError, match="fuera de rango"):
        ind.set_active(2)
    with pytest.raises(IndexError, match="fuera de rango"):
        ind.set_active(-1)


def test_out_of_range_step_state_raises(root):
    ind = StepIndicator(root, steps=("A",), active=0)
    with pytest.raises(IndexError, match="fuera de rango"):
        ind.step_state(1)


def test_geometry_stable_across_states(root):
    ind = StepIndicator(root, steps=("Selección", "Nombres", "Previsualización"), active=0)
    ind.pack()
    root.update_idletasks()
    root.update()

    def keys():
        return [
            (
                m.winfo_reqwidth(),
                m.winfo_reqheight(),
                str(m.cget("width")),
            )
            for m in ind._markers
        ] + [
            (c.winfo_reqwidth(), int(c.cget("height") or 0), int(c.cget("width") or 0))
            for c in ind._connectors
        ]

    before = keys()
    for step in (1, 2, 0, 2):
        ind.set_active(step)
        root.update_idletasks()
        assert keys() == before
