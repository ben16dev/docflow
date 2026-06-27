import tkinter as tk


# =========================
# Botón corporativo reutilizable
# =========================

def create_corporate_button(parent, app, text, command, pack=True):
    btn = tk.Button(
        parent,
        text=text,
        width=40,
        height=2,
        bg="#1f4e79",
        fg="white",
        activebackground="#2f6fa3",
        activeforeground="white",
        bd=1,
        relief="raised",
        cursor="hand2",
        command=command
    )

    btn.bind("<Enter>", lambda e: btn.config(bg="#2f6fa3"))
    btn.bind("<Leave>", lambda e: btn.config(bg="#1f4e79"))

    if pack:
        btn.pack(pady=6, anchor="w")

    return btn


# =========================
# Frame de ruta con placeholder
# =========================

def create_route_frame(parent, ruta_var, seleccionar_callback):
    PLACEHOLDER = "Selecciona la carpeta de trabajo aquí"

    frame = tk.Frame(parent, bg=parent["bg"])
    frame.pack(fill="x", padx=30, pady=(10, 20))

    entry = tk.Entry(frame, textvariable=ruta_var)
    entry.pack(fill="x", pady=(0, 6))

    def set_placeholder():
        if not (ruta_var.get() or "").strip():
            ruta_var.set(PLACEHOLDER)
            entry.config(fg="#777777")

    def clear_placeholder(_=None):
        if ruta_var.get() == PLACEHOLDER:
            ruta_var.set("")
            entry.config(fg="#000000")

    def on_focus_out(_=None):
        if not (ruta_var.get() or "").strip():
            set_placeholder()

    entry.bind("<FocusIn>", clear_placeholder)
    entry.bind("<FocusOut>", on_focus_out)

    if not (ruta_var.get() or "").strip():
        set_placeholder()
    else:
        entry.config(fg="#000000")

    tk.Button(
        frame,
        text="Seleccionar carpeta",
        command=seleccionar_callback
    ).pack(anchor="w")

    return frame


# =========================
# Panel de ayuda más legible
# =========================

def create_help_panel(parent, title, text):
    frame = tk.LabelFrame(
        parent,
        text=title,
        bg=parent["bg"],
        fg="#1f4e79",
        font=("Segoe UI", 11, "bold"),
        padx=20,
        pady=15
    )
    frame.pack(fill="x", padx=30, pady=(20, 15))

    label = tk.Label(
        frame,
        text=text,
        justify="left",
        anchor="w",
        bg=parent["bg"],
        wraplength=850,
        font=("Segoe UI", 10),
    )
    label.pack(anchor="w")

    return frame


