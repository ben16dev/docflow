import tkinter as tk
from pathlib import Path
import time
import platform
import sys

from scripts.registry import get_scripts
from ui.common import CorporateButton
from ui.styles import (
    BACKGROUND_MUTED,
    STATE_CANCELLED,
    STATE_ERROR,
    STATE_IDLE,
    STATE_RUNNING,
    STATE_SUCCESS,
    STATUS_BAR_HEIGHT,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from utils.platform_open import open_path


class StatusBar(tk.Frame):

    COLORS = {
        "idle": STATE_IDLE,
        "running": STATE_RUNNING,
        "success": STATE_SUCCESS,
        "error": STATE_ERROR,
        "cancelado": STATE_CANCELLED,
    }

    def __init__(self, parent, app_name, app_version, app_author, cancel_callback):
        super().__init__(parent, bd=1, relief="sunken", bg=BACKGROUND_MUTED)

        self.app_name = app_name
        self.app_version = app_version
        self.app_author = app_author

        self.cancel_callback = cancel_callback
        self._output_dir = None

        # ==========================
        # TIMER CONTROL
        # ==========================
        self._timer_running = False
        self._timer_start = None
        self._after_id = None

        # ==========================
        # GRID LAYOUT (fila única)
        # ==========================
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        top_row = tk.Frame(self, bg=BACKGROUND_MUTED)
        top_row.grid(row=0, column=0, columnspan=2, sticky="nsew")
        top_row.grid_columnconfigure(0, weight=1)

        left = tk.Frame(top_row, bg=BACKGROUND_MUTED)
        left.grid(row=0, column=0, sticky="ew")
        left.grid_columnconfigure(0, weight=1)

        right = tk.Frame(top_row, bg=BACKGROUND_MUTED)
        right.grid(row=0, column=1, sticky="e")

        # ==========================
        # STATUS LABEL
        # ==========================
        self.lbl_status = tk.Label(
            left,
            text="Listo",
            bg=BACKGROUND_MUTED,
            fg=TEXT_PRIMARY,
            font=("Segoe UI", 9),
            anchor="w"
        )
        self.lbl_status.grid(row=0, column=0, sticky="ew", padx=(10, 10), pady=(4, 4))

        # INFO
        self.lbl_info = tk.Label(
            right,
            text=f"{app_name} {app_version} — {app_author}",
            bg=BACKGROUND_MUTED,
            fg=TEXT_SECONDARY,
            font=("Segoe UI", 8)
        )
        self.lbl_info.pack(side="right", padx=(10, 15), pady=(4, 4))

        # TIMER LABEL
        self.lbl_timer = tk.Label(
            right,
            text="00:00.000",
            bg=BACKGROUND_MUTED,
            fg=self.COLORS["idle"],
            font=("Segoe UI", 9, "bold")
        )
        self.lbl_timer.pack(side="right", padx=(10, 10), pady=(4, 4))

        # Compacto para caber en STATUS_BAR_HEIGHT sin progressbar.
        _btn_kwargs = {"width": None, "padx": 10, "pady": 3}

        # ==========================
        # BOTÓN DIAGNÓSTICO
        # ==========================
        self.btn_diag = CorporateButton(
            right,
            text="Diagnóstico",
            command=self._show_diagnostics,
            variant="diagnostic",
            **_btn_kwargs,
        )
        self.btn_diag.pack(side="right", padx=(10, 0), pady=(2, 2))

        # ==========================
        # BOTÓN ABRIR
        # ==========================
        self.btn_open = CorporateButton(
            right,
            text="Abrir carpeta destino",
            command=self._abrir_carpeta,
            variant="success",
            **_btn_kwargs,
        )
        self.btn_open.configure(state="disabled")
        self.btn_open.pack(side="right", padx=(10, 0), pady=(2, 2))

        # ==========================
        # BOTÓN CANCELAR
        # ==========================
        self.btn_cancel = CorporateButton(
            right,
            text="Cancelar",
            command=self._cancelar,
            variant="cancel",
            **_btn_kwargs,
        )
        self.btn_cancel.configure(state="disabled")
        self.btn_cancel.pack(side="right", padx=(10, 0), pady=(2, 2))

        # Altura fija tras construir hijos; pack al final para reservar espacio
        # antes del contenedor expandible de App.
        # grid_propagate: los hijos usan grid; pack_propagate solo no basta.
        self.configure(height=STATUS_BAR_HEIGHT)
        self.pack_propagate(False)
        self.grid_propagate(False)
        self.pack(side="bottom", fill="x")

    # ==================================================
    # DIAGNÓSTICO AVANZADO
    # ==================================================

    def _show_diagnostics(self):

        win = tk.Toplevel(self)
        win.title("Diagnóstico DocFlow")
        win.geometry("600x450")

        text = tk.Text(win, wrap="word", font=("Consolas", 10))
        text.pack(fill="both", expand=True, padx=10, pady=10)

        lines = []

        # Información del sistema
        lines.append(f"{self.app_name} {self.app_version}")
        lines.append("-" * 50)
        lines.append(f"Autor: {self.app_author}")
        lines.append("")
        lines.append(f"Python: {platform.python_version()}")
        lines.append(f"Sistema: {platform.system()} {platform.release()}")
        lines.append(f"Modo compilado: {'Sí' if getattr(sys, 'frozen', False) else 'No'}")
        lines.append("")
        lines.append(f"Directorio base: {Path(__file__).resolve().parents[2]}")
        lines.append(f"Directorio actual: {Path.cwd()}")
        lines.append("")

        total = 0

        # Scripts cargados
        for tab in ["PDF", "EML", "MBOX", "CONVERSIÓN"]:

            scripts = get_scripts(tab)

            lines.append(tab)
            for name in scripts:
                lines.append(f"  • {name}")
                total += 1

            lines.append("")

        lines.insert(4, f"Scripts cargados: {total}")
        lines.insert(5, "")

        text.insert("1.0", "\n".join(lines))
        text.config(state="disabled")

    # ==================================================
    # STATE MANAGEMENT
    # ==================================================

    def set_state(self, state):

        color = self.COLORS.get(state, self.COLORS["idle"])
        self.lbl_timer.config(fg=color)

        if state == "running":
            if not self._timer_running:
                self.start_timer()
        else:
            self.stop_timer()

    def set_status(self, text):
        self.lbl_status.config(text=text or "")

    # ==================================================
    # OPEN FOLDER
    # ==================================================

    def enable_open_button(self, folder):
        if folder and Path(folder).exists():
            self._output_dir = str(folder)
            self.btn_open.config(state="normal")

    def disable_open_button(self):
        self._output_dir = None
        self.btn_open.config(state="disabled")

    def _abrir_carpeta(self):

        if not self._output_dir:
            return

        path = Path(self._output_dir)

        if not path.exists():
            self.disable_open_button()
            return

        open_path(path)

    # ==================================================
    # CANCEL
    # ==================================================

    def enable_cancel_button(self):
        self.btn_cancel.config(state="normal")

    def disable_cancel_button(self):
        self.btn_cancel.config(state="disabled")

    def _cancelar(self):
        if str(self.btn_cancel["state"]) != "normal":
            return

        # Deshabilitar de inmediato evita solicitudes de cancelación repetidas
        # mientras el proceso en curso todavía coopera con is_cancelled().
        self.disable_cancel_button()

        if callable(self.cancel_callback):
            self.cancel_callback()

    # ==================================================
    # TIMER
    # ==================================================

    def start_timer(self):
        self.stop_timer()
        self._timer_running = True
        self._timer_start = time.perf_counter()
        self._tick()

    def stop_timer(self):

        self._timer_running = False

        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass

        self._after_id = None

    def reset_timer(self):
        self.stop_timer()
        self.lbl_timer.config(text="00:00.000")

    def _tick(self):

        if not self._timer_running:
            return

        elapsed = time.perf_counter() - self._timer_start

        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        ms = int((elapsed % 1) * 1000)

        self.lbl_timer.config(
            text=f"{minutes:02d}:{seconds:02d}.{ms:03d}"
        )

        self._after_id = self.after(50, self._tick)

    # ==================================================
    # OPTIONAL
    # ==================================================

    def update_history(self, items):
        return
