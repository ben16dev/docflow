import tkinter as tk

from ui.styles import (
    BTN_BG,
    BTN_BG_DISABLED,
    BTN_BG_HOVER,
    BTN_BG_PRESSED,
    BTN_FG,
    BTN_FG_DISABLED_SURFACE,
    BTN_FOCUS_COLOR,
)


# =========================
# Botón corporativo reutilizable
# =========================

class CorporateButton(tk.Frame):
    """
    Botón principal de ejecución con apariencia controlada por DocFlow.

    Usa Frame + Label para evitar el pintado inconsistente de tk.Button en Aqua.
    Compatibilidad parcial con tk.Button: grid/pack, config/configure/cget
    para state, text y command.
    """

    def __init__(self, parent, text="", command=None, **kwargs):
        super().__init__(
            parent,
            bg=BTN_BG,
            highlightthickness=2,
            highlightbackground=BTN_BG,
            highlightcolor=BTN_FOCUS_COLOR,
            bd=1,
            relief="raised",
            cursor="hand2",
            takefocus=1,
        )

        self._command = command
        self._state = "normal"
        self._hovered = False
        self._pressed = False
        self._focused = False

        self._label = tk.Label(
            self,
            text=text,
            bg=BTN_BG,
            fg=BTN_FG,
            font=("Segoe UI", 10),
            width=40,
            padx=8,
            pady=12,
            cursor="hand2",
            takefocus=0,
        )
        self._label.pack(fill="both", expand=True)

        self._bind_surface("<Enter>", self._on_enter)
        self._bind_surface("<Leave>", self._on_leave)
        self._bind_surface("<ButtonPress-1>", self._on_press)
        self._bind_surface("<ButtonRelease-1>", self._on_release)
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)
        self.bind("<Return>", self._on_activate_key)
        self.bind("<space>", self._on_activate_key)
        self._label.bind("<ButtonPress-1>", self._focus_self, add="+")

        self._apply_visual()

    def _bind_surface(self, sequence, handler):
        self.bind(sequence, handler)
        self._label.bind(sequence, handler)

    def _focus_self(self, _event=None):
        if self._state == "normal":
            self.focus_set()

    def _is_enabled(self) -> bool:
        return self._state == "normal"

    def _event_inside(self, event) -> bool:
        try:
            x = self.winfo_rootx()
            y = self.winfo_rooty()
            w = self.winfo_width()
            h = self.winfo_height()
        except tk.TclError:
            return False
        return x <= event.x_root < x + w and y <= event.y_root < y + h

    def _on_enter(self, _event=None):
        if not self._is_enabled():
            return
        self._hovered = True
        self._apply_visual()

    def _on_leave(self, _event=None):
        self._hovered = False
        if self._pressed and self._is_enabled():
            # Mantiene aspecto pulsado solo mientras el puntero sigue dentro;
            # al salir, vuelve a normal/hover sin ejecutar.
            self._apply_visual()
            return
        self._apply_visual()

    def _on_press(self, event=None):
        if not self._is_enabled():
            return "break"
        self._focus_self()
        self._pressed = True
        self._hovered = True
        self._apply_visual()
        return "break"

    def _on_release(self, event=None):
        if not self._pressed:
            return "break"
        self._pressed = False
        inside = event is None or self._event_inside(event)
        should_run = self._is_enabled() and inside
        self._hovered = inside and self._is_enabled()
        self._apply_visual()
        if should_run:
            self._invoke()
        return "break"

    def _on_focus_in(self, _event=None):
        self._focused = True
        self._apply_visual()

    def _on_focus_out(self, _event=None):
        self._focused = False
        self._apply_visual()

    def _on_activate_key(self, _event=None):
        if not self._is_enabled():
            return "break"
        self._invoke()
        return "break"

    def _invoke(self):
        if not self._is_enabled():
            return
        if callable(self._command):
            self._command()

    def _apply_visual(self):
        if not self._is_enabled():
            bg, fg = BTN_BG_DISABLED, BTN_FG_DISABLED_SURFACE
            relief = "raised"
            cursor = "arrow"
        elif self._pressed and self._hovered:
            bg, fg = BTN_BG_PRESSED, BTN_FG
            relief = "sunken"
            cursor = "hand2"
        elif self._hovered:
            bg, fg = BTN_BG_HOVER, BTN_FG
            relief = "raised"
            cursor = "hand2"
        else:
            bg, fg = BTN_BG, BTN_FG
            relief = "raised"
            cursor = "hand2"

        highlight_bg = BTN_FOCUS_COLOR if self._focused else bg

        # Usar super().configure para no reentrar en la API de compatibilidad.
        super().configure(
            bg=bg,
            relief=relief,
            cursor=cursor,
            highlightbackground=highlight_bg,
            highlightcolor=BTN_FOCUS_COLOR,
        )
        self._label.configure(
            bg=bg,
            fg=fg,
            cursor=cursor,
        )

    def configure(self, cnf=None, **kwargs):
        if cnf is None:
            cnf = {}
        elif not isinstance(cnf, dict):
            # cget-style: configure("state")
            return self.cget(cnf)

        options = dict(cnf, **kwargs)
        if not options:
            return super().configure()

        handled = {}
        if "state" in options:
            state = options.pop("state")
            if state not in ("normal", "disabled"):
                raise tk.TclError(f'bad state "{state}": must be normal or disabled')
            self._state = state
            if state == "disabled":
                self._pressed = False
                self._hovered = False
            handled["state"] = True

        if "text" in options:
            self._label.configure(text=options.pop("text"))
            handled["text"] = True

        if "command" in options:
            self._command = options.pop("command")
            handled["command"] = True

        # Campos visuales propios de tk.Button: se ignoran de forma segura
        # para no romper llamadas residuales; la apariencia la controla _apply_visual.
        for key in (
            "bg",
            "fg",
            "background",
            "foreground",
            "activebackground",
            "activeforeground",
            "disabledforeground",
            "highlightbackground",
            "cursor",
            "relief",
        ):
            options.pop(key, None)

        result = None
        if options:
            result = super().configure(**options)

        if handled:
            self._apply_visual()

        return result

    config = configure

    def cget(self, key):
        if key == "state":
            return self._state
        if key == "text":
            return self._label.cget("text")
        if key == "command":
            return self._command
        if key in ("bg", "background"):
            return self._label.cget("bg")
        if key in ("fg", "foreground"):
            return self._label.cget("fg")
        if key == "activebackground":
            return BTN_BG_HOVER
        if key == "activeforeground":
            return BTN_FG
        if key == "disabledforeground":
            return BTN_FG_DISABLED_SURFACE
        if key == "highlightbackground":
            return self.tk.call(self._w, "cget", "-highlightbackground")
        if key == "highlightcolor":
            return self.tk.call(self._w, "cget", "-highlightcolor")
        if key == "relief":
            return self.tk.call(self._w, "cget", "-relief")
        if key == "takefocus":
            return self.tk.call(self._w, "cget", "-takefocus")
        if key == "cursor":
            return self.tk.call(self._w, "cget", "-cursor")
        return super().cget(key)

    def __getitem__(self, key):
        return self.cget(key)

    def __setitem__(self, key, value):
        self.configure({key: value})

    def invoke(self):
        """Ejecuta el comando si el botón está habilitado."""
        self._invoke()


def create_corporate_button(parent, app, text, command, pack=True):
    btn = CorporateButton(parent, text=text, command=command)

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
