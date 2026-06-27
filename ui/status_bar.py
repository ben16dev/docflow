import tkinter as tk
from tkinter import ttk
from pathlib import Path
import subprocess
import sys
import os
import time
import platform

from scripts.registry import get_scripts


class StatusBar(tk.Frame):

    COLORS = {
        "idle": "#4f6d8a",
        "running": "#ffc31a",
        "success": "#6de800",
        "error": "#fc5217",
    }

    def __init__(self, parent, app_name, app_version, app_author, cancel_callback):
        super().__init__(parent, bd=1, relief="sunken", bg="#f7fbff")

        self.app_name = app_name
        self.app_version = app_version
        self.app_author = app_author

        # Siempre visible
        self.pack(side="bottom", fill="x")
        self.configure(height=70)
        self.pack_propagate(False)

        self.cancel_callback = cancel_callback
        self._output_dir = None

        # ==========================
        # TIMER CONTROL
        # ==========================
        self._timer_running = False
        self._timer_start = None
        self._after_id = None

        # ==========================
        # GRID LAYOUT
        # ==========================
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        top_row = tk.Frame(self, bg="#f7fbff")
        top_row.grid(row=0, column=0, columnspan=2, sticky="ew")
        top_row.grid_columnconfigure(0, weight=1)

        left = tk.Frame(top_row, bg="#f7fbff")
        left.grid(row=0, column=0, sticky="ew")
        left.grid_columnconfigure(0, weight=1)

        right = tk.Frame(top_row, bg="#f7fbff")
        right.grid(row=0, column=1, sticky="e")

        # ==========================
        # STATUS LABEL
        # ==========================
        self.lbl_status = tk.Label(
            left,
            text="Listo",
            bg="#f7fbff",
            fg="#1f4e79",
            font=("Segoe UI", 9),
            anchor="w"
        )
        self.lbl_status.grid(row=0, column=0, sticky="ew", padx=(10, 10), pady=(6, 2))

        # INFO
        self.lbl_info = tk.Label(
            right,
            text=f"{app_name} {app_version} — {app_author}",
            bg="#f7fbff",
            fg="#4f6d8a",
            font=("Segoe UI", 8)
        )
        self.lbl_info.pack(side="right", padx=(10, 15), pady=(6, 2))

        # TIMER LABEL
        self.lbl_timer = tk.Label(
            right,
            text="00:00.000",
            bg="#f7fbff",
            fg=self.COLORS["idle"],
            font=("Segoe UI", 9, "bold")
        )
        self.lbl_timer.pack(side="right", padx=(10, 10), pady=(6, 2))

        # ==========================
        # BOTÓN DIAGNÓSTICO
        # ==========================
        self.btn_diag = tk.Button(
            right,
            text="Diagnóstico",
            height=2,
            bg="#298cff",
            fg="#ffffff",
            relief="raised",
            command=self._show_diagnostics
        )
        self.btn_diag.pack(side="right", padx=(10, 0), pady=(4, 4))

        # ==========================
        # BOTÓN ABRIR
        # ==========================
        self.btn_open = tk.Button(
            right,
            text="Abrir carpeta destino",
            height=2,
            bg="#fff273",
            fg="#1f4e79",
            activebackground="#fff273",
            activeforeground="#1f4e79",
            relief="raised",
            state="disabled",
            command=self._abrir_carpeta
        )
        self.btn_open.pack(side="right", padx=(10, 0), pady=(4, 4))

        # ==========================
        # BOTÓN CANCELAR
        # ==========================
        self.btn_cancel = tk.Button(
            right,
            text="Cancelar",
            height=2,
            bg="#fc5217",
            fg="white",
            activebackground="#d63f10",
            activeforeground="white",
            relief="raised",
            command=self._cancelar
        )
        self.btn_cancel.pack(side="right", padx=(10, 0), pady=(4, 4))

        # ==========================
        # PROGRESS BAR
        # ==========================
        self.progress = ttk.Progressbar(
            self,
            orient="horizontal",
            mode="determinate",
            style="EDV.Horizontal.TProgressbar"
        )
        self.progress.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 8))

    # ==================================================
    # DIAGNÓSTICO AVANZADO
    # ==================================================

    def _show_diagnostics(self):

        win = tk.Toplevel(self)
        win.title("Diagnóstico EDV AppScript")
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
        for tab in ["PDF", "EML", "MBOX"]:

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
    # PROGRESS
    # ==================================================

    def set_progress(self, current, total):
        if total and total > 0:
            self.progress["value"] = (current / total) * 100
        else:
            self.progress["value"] = 0

    def reset_progress(self):
        self.progress["value"] = 0

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

        if sys.platform.startswith("win"):
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    # ==================================================
    # CANCEL
    # ==================================================

    def _cancelar(self):
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




