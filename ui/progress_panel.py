"""Franja de progreso independiente, situada encima de StatusBar."""

import tkinter as tk
from tkinter import ttk

from ui.styles import (
    FONT_SIZE_SM,
    PROGRESS_PANEL_BG,
    PROGRESS_PANEL_BORDER,
    PROGRESS_PANEL_HEIGHT,
    PROGRESS_PERCENT_FG,
    SPACE_SM,
    font_ui,
)


class ProgressPanel(tk.Frame):
    """
    Presentación visual del progreso de ejecución.

    No gestiona hilos, ScriptRunner, cancelación funcional ni pestañas.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=PROGRESS_PANEL_BG, bd=0, highlightthickness=0, **kwargs)

        self._state = "idle"
        self._indeterminate = False

        tk.Frame(self, height=1, bg=PROGRESS_PANEL_BORDER).pack(side="top", fill="x")

        row = tk.Frame(self, bg=PROGRESS_PANEL_BG)
        row.pack(fill="both", expand=True, padx=12, pady=SPACE_SM)

        self.progress = ttk.Progressbar(
            row,
            orient="horizontal",
            mode="determinate",
            style="DocFlow.Horizontal.TProgressbar",
        )
        self.progress.pack(side="left", fill="x", expand=True)

        self.lbl_percent = tk.Label(
            row,
            text="0 %",
            bg=PROGRESS_PANEL_BG,
            fg=PROGRESS_PERCENT_FG,
            font=font_ui(FONT_SIZE_SM),
            width=5,
            anchor="e",
        )
        self.lbl_percent.pack(side="right", padx=(SPACE_SM, 0))

        self.configure(height=PROGRESS_PANEL_HEIGHT)
        self.pack_propagate(False)
        self.pack(side="bottom", fill="x")

        self.set_idle()

    def _stop_indeterminate(self):
        if self._indeterminate:
            try:
                self.progress.stop()
            except tk.TclError:
                pass
            self._indeterminate = False

    def _set_percent_value(self, value):
        """Actualiza el texto de porcentaje (convención: 'N %')."""
        self.lbl_percent.config(text=f"{int(round(value))} %")

    def _set_percent_dash(self):
        self.lbl_percent.config(text="—")

    def set_idle(self):
        self._stop_indeterminate()
        self._state = "idle"
        self.progress["mode"] = "determinate"
        self.progress["value"] = 0
        self._set_percent_value(0)

    def start(self, indeterminate=False):
        self._stop_indeterminate()
        self._state = "running"
        if indeterminate:
            self._indeterminate = True
            self.progress["mode"] = "indeterminate"
            self.progress["value"] = 0
            self._set_percent_dash()
            self.progress.start(12)
        else:
            self.progress["mode"] = "determinate"
            self.progress["value"] = 0
            self._set_percent_value(0)

    def set_progress(self, current, total):
        if self._indeterminate:
            self._stop_indeterminate()
            self.progress["mode"] = "determinate"

        self._state = "running"

        if total and total > 0:
            value = max(0.0, min(100.0, (float(current) / float(total)) * 100.0))
            self.progress["value"] = value
            self._set_percent_value(value)
        else:
            self.progress["value"] = 0
            self._set_percent_value(0)

    def complete_progress(self):
        """Deja la barra visualmente al 100 % (éxito)."""
        self._stop_indeterminate()
        self._state = "success"
        self.progress["mode"] = "determinate"
        self.progress["value"] = 100
        self._set_percent_value(100)

    def set_error(self):
        self._stop_indeterminate()
        self._state = "error"
        self.progress["mode"] = "determinate"
        self.progress["value"] = 0
        self._set_percent_value(0)

    def set_cancelled(self):
        self._stop_indeterminate()
        self._state = "cancelled"
        self.progress["mode"] = "determinate"
        self.progress["value"] = 0
        self._set_percent_value(0)

    def reset_progress(self):
        self._stop_indeterminate()
        self._state = "idle"
        self.progress["mode"] = "determinate"
        self.progress["value"] = 0
        self._set_percent_value(0)
