import tkinter as tk

from ui.styles import (
    BUTTON_VARIANTS,
    CARD_ACCENT,
    CARD_ACCENT_WIDTH,
    CARD_BG,
    CARD_BORDER,
    CARD_BORDER_FOCUS,
    CARD_BORDER_HOVER,
    CARD_BORDER_PRESSED,
    CARD_DESC_FG,
    CARD_DISABLED_BG,
    CARD_DISABLED_FG,
    CARD_GAP,
    CARD_HOVER_BG,
    CARD_PADX,
    CARD_PADY,
    CARD_TITLE_FG,
    CARD_TITLE_GAP,
    CARD_WRAPLENGTH,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
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

    Variantes semánticas (colores solo desde ui.styles.BUTTON_VARIANTS):
    primary, secondary, cancel, success, diagnostic.
    """

    VALID_VARIANTS = frozenset(BUTTON_VARIANTS)

    def __init__(
        self,
        parent,
        text="",
        command=None,
        variant="primary",
        width=40,
        padx=8,
        pady=12,
        **kwargs,
    ):
        if variant not in self.VALID_VARIANTS:
            raise ValueError(
                f'variante inválida "{variant}": '
                f'debe ser una de {sorted(self.VALID_VARIANTS)}'
            )

        # kwargs residuales de tk.Button se ignoran de forma segura más abajo.
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
            "state",
        ):
            kwargs.pop(key, None)

        self._variant = variant
        self._palette = BUTTON_VARIANTS[variant]
        initial_bg = self._palette["bg"]
        focus_color = self._palette["focus"]

        super().__init__(
            parent,
            bg=initial_bg,
            highlightthickness=2,
            highlightbackground=initial_bg,
            highlightcolor=focus_color,
            bd=1,
            relief="raised",
            cursor="hand2",
            takefocus=1,
            **kwargs,
        )

        self._command = command
        self._state = "normal"
        self._hovered = False
        self._pressed = False
        self._focused = False

        label_opts = {
            "text": text,
            "bg": initial_bg,
            "fg": self._palette["fg"],
            "font": ("Segoe UI", 10),
            "padx": padx,
            "pady": pady,
            "cursor": "hand2",
            "takefocus": 0,
        }
        if width is not None:
            label_opts["width"] = width

        self._label = tk.Label(self, **label_opts)
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
        palette = self._palette
        focus_color = palette["focus"]

        if not self._is_enabled():
            bg, fg = palette["disabled_bg"], palette["disabled_fg"]
            relief = "raised"
            cursor = "arrow"
        elif self._pressed and self._hovered:
            bg, fg = palette["pressed"], palette["fg"]
            relief = "sunken"
            cursor = "hand2"
        elif self._hovered:
            bg, fg = palette["hover"], palette["fg"]
            relief = "raised"
            cursor = "hand2"
        else:
            bg, fg = palette["bg"], palette["fg"]
            relief = "raised"
            cursor = "hand2"

        highlight_bg = focus_color if self._focused else bg

        # Usar super().configure para no reentrar en la API de compatibilidad.
        super().configure(
            bg=bg,
            relief=relief,
            cursor=cursor,
            highlightbackground=highlight_bg,
            highlightcolor=focus_color,
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

        if "variant" in options:
            variant = options.pop("variant")
            if variant not in self.VALID_VARIANTS:
                raise ValueError(
                    f'variante inválida "{variant}": '
                    f'debe ser una de {sorted(self.VALID_VARIANTS)}'
                )
            self._variant = variant
            self._palette = BUTTON_VARIANTS[variant]
            handled["variant"] = True

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
        if key == "variant":
            return self._variant
        if key in ("bg", "background"):
            return self._label.cget("bg")
        if key in ("fg", "foreground"):
            return self._label.cget("fg")
        if key == "activebackground":
            return self._palette["hover"]
        if key == "activeforeground":
            return self._palette["fg"]
        if key == "disabledforeground":
            return self._palette["disabled_fg"]
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


def create_corporate_button(
    parent,
    app,
    text,
    command,
    pack=True,
    variant="primary",
    width=40,
    padx=8,
    pady=12,
):
    btn = CorporateButton(
        parent,
        text=text,
        command=command,
        variant=variant,
        width=width,
        padx=padx,
        pady=pady,
    )

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


# =========================
# Tarjeta de herramienta
# =========================

class ToolCard(tk.Frame):
    """
    Tarjeta activable para lanzar una herramienta DocFlow.

    Toda la superficie responde a clic y teclado (Return/Space).
    Colores exclusivamente desde tokens CARD_* de ui.styles.
    """

    def __init__(
        self,
        parent,
        title="",
        description="",
        command=None,
        state="normal",
        width=None,
        wraplength=None,
        **kwargs,
    ):
        for key in (
            "bg",
            "fg",
            "background",
            "foreground",
            "cursor",
            "relief",
            "highlightbackground",
        ):
            kwargs.pop(key, None)

        card_width = width
        self._wraplength = CARD_WRAPLENGTH if wraplength is None else wraplength

        super().__init__(
            parent,
            bg=CARD_BG,
            highlightthickness=2,
            highlightbackground=CARD_BORDER,
            highlightcolor=CARD_BORDER_FOCUS,
            bd=0,
            relief="flat",
            cursor="hand2",
            takefocus=1,
            **kwargs,
        )

        self._command = command
        self._state = "normal"
        self._hovered = False
        self._pressed = False
        self._focused = False
        self._title = title or ""
        self._description = description or ""

        body = tk.Frame(self, bg=CARD_BG, cursor="hand2", takefocus=0)
        body.pack(fill="both", expand=True)

        self._accent = tk.Frame(
            body,
            bg=CARD_ACCENT,
            width=CARD_ACCENT_WIDTH,
            cursor="hand2",
            takefocus=0,
        )
        self._accent.pack(side="left", fill="y")
        self._accent.pack_propagate(False)

        content = tk.Frame(body, bg=CARD_BG, cursor="hand2", takefocus=0)
        content.pack(side="left", fill="both", expand=True)

        self._content = content
        self._body = body

        self._title_label = tk.Label(
            content,
            text=self._title,
            bg=CARD_BG,
            fg=CARD_TITLE_FG,
            font=("Segoe UI", FONT_SIZE_MD, "bold"),
            anchor="w",
            justify="left",
            wraplength=self._wraplength,
            cursor="hand2",
            takefocus=0,
        )
        self._title_label.pack(
            fill="x",
            padx=(CARD_PADX, CARD_PADX),
            pady=(CARD_PADY, CARD_TITLE_GAP),
        )

        self._desc_label = tk.Label(
            content,
            text=self._description,
            bg=CARD_BG,
            fg=CARD_DESC_FG,
            font=("Segoe UI", FONT_SIZE_SM),
            anchor="nw",
            justify="left",
            wraplength=self._wraplength,
            cursor="hand2",
            takefocus=0,
        )
        self._desc_label.pack(
            fill="both",
            expand=True,
            padx=(CARD_PADX, CARD_PADX),
            pady=(0, CARD_PADY),
        )

        if card_width is not None:
            self.configure(width=card_width)
            self.pack_propagate(False)
        # Sin width fijo: en macOS/Tk, configure() con -width y height=0
        # colapsa reqheight a 1 en cada _apply_visual (temblor del grid).

        self._surfaces = (
            self,
            body,
            self._accent,
            content,
            self._title_label,
            self._desc_label,
        )
        for widget in self._surfaces:
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)
            widget.bind("<ButtonPress-1>", self._on_press)
            widget.bind("<ButtonRelease-1>", self._on_release)

        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)
        self.bind("<Return>", self._on_activate_key)
        self.bind("<space>", self._on_activate_key)
        for widget in (self._title_label, self._desc_label, content, self._accent, body):
            widget.bind("<ButtonPress-1>", self._focus_self, add="+")

        if state != "normal":
            self.configure(state=state)
        else:
            self._apply_visual()

    def _focus_self(self, _event=None):
        if self._state == "normal":
            self.focus_set()

    def _is_enabled(self) -> bool:
        return self._state == "normal"

    def _event_inside(self, event) -> bool:
        """True si el puntero sigue dentro de esta tarjeta (o un descendiente)."""
        if event is None:
            return False
        try:
            x = event.x_root
            y = event.y_root
        except AttributeError:
            return False

        try:
            widget = self.winfo_containing(x, y)
        except tk.TclError:
            widget = None
        while widget is not None:
            if widget == self:
                return True
            widget = getattr(widget, "master", None)

        # Fallback geométrico (p. ej. tests con root withdraw o containing nulo).
        try:
            rx = self.winfo_rootx()
            ry = self.winfo_rooty()
            rw = max(self.winfo_width(), self.winfo_reqwidth())
            rh = max(self.winfo_height(), self.winfo_reqheight())
        except tk.TclError:
            return False
        return rx <= x < rx + rw and ry <= y < ry + rh

    def _on_enter(self, _event=None):
        if not self._is_enabled():
            return
        if self._hovered:
            return
        self._hovered = True
        self._apply_visual()

    def _on_leave(self, event=None):
        # Leave de un hijo al pasar a otro hijo: el puntero sigue dentro.
        if self._event_inside(event):
            return
        if not self._hovered and not self._pressed:
            return
        self._hovered = False
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
        # relief siempre flat: sunken/raised alteran la geometría exterior.
        if not self._is_enabled():
            bg = CARD_DISABLED_BG
            title_fg = CARD_DISABLED_FG
            desc_fg = CARD_DISABLED_FG
            accent = CARD_DISABLED_FG
            border = CARD_BORDER
            cursor = "arrow"
        elif self._pressed and self._hovered:
            bg = CARD_HOVER_BG
            title_fg = CARD_TITLE_FG
            desc_fg = CARD_DESC_FG
            accent = CARD_BORDER_PRESSED
            border = CARD_BORDER_PRESSED
            cursor = "hand2"
        elif self._hovered:
            bg = CARD_HOVER_BG
            title_fg = CARD_TITLE_FG
            desc_fg = CARD_DESC_FG
            accent = CARD_ACCENT
            border = CARD_BORDER_HOVER
            cursor = "hand2"
        else:
            bg = CARD_BG
            title_fg = CARD_TITLE_FG
            desc_fg = CARD_DESC_FG
            accent = CARD_ACCENT
            border = CARD_BORDER
            cursor = "hand2"

        if self._focused and self._is_enabled():
            border = CARD_BORDER_FOCUS

        super().configure(
            bg=bg,
            cursor=cursor,
            relief="flat",
            highlightbackground=border,
            highlightcolor=CARD_BORDER_FOCUS,
        )
        for widget in (self._body, self._content):
            widget.configure(bg=bg, cursor=cursor)
        self._accent.configure(bg=accent, cursor=cursor)
        self._title_label.configure(bg=bg, fg=title_fg, cursor=cursor)
        self._desc_label.configure(bg=bg, fg=desc_fg, cursor=cursor)

    def configure(self, cnf=None, **kwargs):
        if cnf is None:
            cnf = {}
        elif not isinstance(cnf, dict):
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

        if "title" in options:
            self._title = options.pop("title") or ""
            self._title_label.configure(text=self._title)
            handled["title"] = True

        if "description" in options:
            self._description = options.pop("description") or ""
            self._desc_label.configure(text=self._description)
            handled["description"] = True

        if "text" in options:
            # Alias de title para compatibilidad con APIs tipo botón.
            self._title = options.pop("text") or ""
            self._title_label.configure(text=self._title)
            handled["title"] = True

        if "command" in options:
            self._command = options.pop("command")
            handled["command"] = True

        for key in (
            "bg",
            "fg",
            "background",
            "foreground",
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
        if key in ("title", "text"):
            return self._title
        if key == "description":
            return self._description
        if key == "command":
            return self._command
        if key in ("bg", "background"):
            return self._content.cget("bg")
        if key == "cursor":
            return self.tk.call(self._w, "cget", "-cursor")
        if key == "relief":
            return self.tk.call(self._w, "cget", "-relief")
        if key == "takefocus":
            return self.tk.call(self._w, "cget", "-takefocus")
        if key == "highlightbackground":
            return self.tk.call(self._w, "cget", "-highlightbackground")
        return super().cget(key)

    def __getitem__(self, key):
        return self.cget(key)

    def __setitem__(self, key, value):
        self.configure({key: value})

    def invoke(self):
        """Ejecuta el comando si la tarjeta está habilitada."""
        self._invoke()


def create_tool_card(
    parent,
    title,
    description,
    command,
    state="normal",
    width=None,
    pack=False,
):
    card = ToolCard(
        parent,
        title=title,
        description=description,
        command=command,
        state=state,
        width=width,
    )
    if pack:
        card.pack(fill="both", expand=True, padx=CARD_GAP, pady=CARD_GAP)
    return card
