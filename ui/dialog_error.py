"""Diálogo modal para errores de ejecución con acceso al log."""

import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from ui.styles import BTN_BG, BTN_BG_HOVER, BTN_FG, FRAME_BG, TITLE_FG
from ui.window_icon import set_window_icon
from utils.platform_open import open_path


def show_error_dialog(parent, user_message: str, log_file: str | None = None) -> None:
    """
    Muestra un error comprensible con la ruta del log y acciones útiles.
    El traceback completo no se muestra aquí; debe estar solo en el log.
    """
    win = tk.Toplevel(parent)
    win.title("Error")
    win.resizable(True, True)
    win.minsize(480, 260)
    set_window_icon(win)
    win.transient(parent)
    win.grab_set()

    frame = tk.Frame(win, bg=FRAME_BG, padx=20, pady=16)
    frame.pack(fill="both", expand=True)

    tk.Label(
        frame,
        text="Se ha producido un error",
        bg=FRAME_BG,
        fg=TITLE_FG,
        font=("Segoe UI", 11, "bold"),
        anchor="w",
    ).pack(fill="x", pady=(0, 8))

    tk.Label(
        frame,
        text="Detalle:",
        bg=FRAME_BG,
        fg=TITLE_FG,
        font=("Segoe UI", 9, "bold"),
        anchor="w",
    ).pack(fill="x")

    text_message = tk.Text(
        frame,
        height=6,
        wrap="word",
        font=("Segoe UI", 10),
        relief="sunken",
        bd=1,
    )
    text_message.pack(fill="both", expand=True, pady=(4, 10))
    text_message.insert("1.0", user_message or "Error desconocido.")
    text_message.config(state="disabled")

    log_path = str(log_file) if log_file else ""
    log_exists = bool(log_path) and Path(log_path).exists()

    if log_path:
        log_label = (
            f"Log:\n{log_path}"
            if log_exists
            else f"Log (aún no creado):\n{log_path}"
        )
    else:
        log_label = "Log: no disponible"

    tk.Label(
        frame,
        text=log_label,
        bg=FRAME_BG,
        fg="#4f6d8a",
        font=("Segoe UI", 9),
        justify="left",
        anchor="w",
    ).pack(fill="x", pady=(0, 12))

    btn_row = tk.Frame(frame, bg=FRAME_BG)
    btn_row.pack(fill="x")

    def _copiar():
        parent.clipboard_clear()
        parent.clipboard_append(user_message or "")
        parent.update_idletasks()

    def _abrir_log():
        if not log_path:
            messagebox.showwarning(
                "Log no disponible",
                "No se ha podido determinar la ruta del log.",
                parent=win,
            )
            return
        if not Path(log_path).exists():
            messagebox.showwarning(
                "Log no disponible",
                "El archivo de log aún no existe o no es accesible.",
                parent=win,
            )
            return
        try:
            open_path(log_path)
        except Exception as exc:
            messagebox.showerror(
                "No se pudo abrir el log",
                str(exc),
                parent=win,
            )

    def _cerrar():
        win.destroy()

    def _make_button(text, command):
        btn = tk.Button(
            btn_row,
            text=text,
            command=command,
            bg=BTN_BG,
            fg=BTN_FG,
            activebackground=BTN_BG_HOVER,
            activeforeground=BTN_FG,
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2",
        )
        btn.pack(side="left", padx=(0, 8))
        return btn

    _make_button("Copiar mensaje", _copiar)
    if log_path:
        _make_button("Abrir log", _abrir_log)
    _make_button("Cerrar", _cerrar)

    win.protocol("WM_DELETE_WINDOW", _cerrar)
    win.wait_window()
