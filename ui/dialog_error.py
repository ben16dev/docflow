"""Diálogo modal para errores de ejecución con acceso al log."""

import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from ui.common import CorporateButton
from ui.styles import (
    ERROR_DIALOG_BG,
    ERROR_DIALOG_DETAIL_BG,
    ERROR_DIALOG_DETAIL_BORDER,
    ERROR_DIALOG_DETAIL_FG,
    ERROR_DIALOG_HEADER_FG,
    ERROR_DIALOG_LABEL_FG,
    ERROR_DIALOG_LOG_FG,
    ERROR_DIALOG_PADX,
    ERROR_DIALOG_PADY,
    FONT_SIZE_LG,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    SPACE_SM,
    font_ui,
)
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
    win.configure(bg=ERROR_DIALOG_BG)

    frame = tk.Frame(
        win,
        bg=ERROR_DIALOG_BG,
        padx=ERROR_DIALOG_PADX,
        pady=ERROR_DIALOG_PADY,
    )
    frame.pack(fill="both", expand=True)

    tk.Label(
        frame,
        text="Se ha producido un error",
        bg=ERROR_DIALOG_BG,
        fg=ERROR_DIALOG_HEADER_FG,
        font=font_ui(FONT_SIZE_LG, "bold"),
        anchor="w",
    ).pack(fill="x", pady=(0, SPACE_SM))

    tk.Label(
        frame,
        text="Detalle:",
        bg=ERROR_DIALOG_BG,
        fg=ERROR_DIALOG_LABEL_FG,
        font=font_ui(FONT_SIZE_SM, "bold"),
        anchor="w",
    ).pack(fill="x")

    text_frame = tk.Frame(
        frame,
        bg=ERROR_DIALOG_DETAIL_BORDER,
        highlightthickness=1,
        highlightbackground=ERROR_DIALOG_DETAIL_BORDER,
        bd=0,
    )
    text_frame.pack(fill="both", expand=True, pady=(4, 10))

    inner = tk.Frame(text_frame, bg=ERROR_DIALOG_DETAIL_BG)
    inner.pack(fill="both", expand=True, padx=1, pady=1)

    scrollbar = tk.Scrollbar(inner, orient="vertical")
    scrollbar.pack(side="right", fill="y")

    text_message = tk.Text(
        inner,
        height=6,
        wrap="word",
        font=font_ui(FONT_SIZE_MD),
        bg=ERROR_DIALOG_DETAIL_BG,
        fg=ERROR_DIALOG_DETAIL_FG,
        insertbackground=ERROR_DIALOG_DETAIL_FG,
        relief="flat",
        bd=0,
        highlightthickness=0,
        yscrollcommand=scrollbar.set,
    )
    text_message.pack(side="left", fill="both", expand=True)
    scrollbar.config(command=text_message.yview)

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
        bg=ERROR_DIALOG_BG,
        fg=ERROR_DIALOG_LOG_FG,
        font=font_ui(FONT_SIZE_SM),
        justify="left",
        anchor="w",
    ).pack(fill="x", pady=(0, 12))

    btn_row = tk.Frame(frame, bg=ERROR_DIALOG_BG)
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

    def _make_button(text, command, variant="secondary"):
        btn = CorporateButton(
            btn_row,
            text=text,
            command=command,
            variant=variant,
            width=None,
            padx=12,
            pady=6,
        )
        btn.pack(side="left", padx=(0, SPACE_SM))
        return btn

    _make_button("Copiar mensaje", _copiar, variant="secondary")
    if log_path:
        _make_button("Abrir log", _abrir_log, variant="secondary")
    _make_button("Cerrar", _cerrar, variant="diagnostic")

    win.protocol("WM_DELETE_WINDOW", _cerrar)
    win.wait_window()
