import tkinter as tk
from tkinter import ttk, colorchooser, messagebox

from ui.common import CorporateButton, create_toolbar_button
from ui.exceptions import CancelledByUser
from ui.styles import (
    CONFIG_DIALOG_BG,
    CONFIG_DIALOG_LABEL_FG,
    CONFIG_DIALOG_PADX,
    CONFIG_DIALOG_PADY,
    CONFIG_DIALOG_PANEL_BG,
    CONFIG_DIALOG_PANEL_BORDER,
    CONFIG_DIALOG_PREVIEW_BORDER,
    CONFIG_DIALOG_TITLE_FG,
    FLOW_NOTICE_SAFE_BG,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    SPACE_MD,
    SPACE_SM,
    SPACE_XS,
    font_ui,
)
from ui.window_icon import set_window_icon


def solicitar_configuracion(font_default: str, pymupdf_disponible=None):

    root = tk._default_root
    created_root = False

    if root is None:
        root = tk.Tk()
        root.withdraw()
        created_root = True

    win = tk.Toplevel(root)
    win.title("Numeración PDF - Configuración")
    win.resizable(False, False)
    set_window_icon(win)
    win.transient(root)
    win.grab_set()
    win.configure(bg=CONFIG_DIALOG_BG)

    # ======================================================
    # VARIABLES
    # ======================================================

    modo_var = tk.StringVar(value="numero")
    prefijo_var = tk.StringVar(value="")

    vertical_var = tk.StringVar(value="top")
    horizontal_var = tk.StringVar(value="right")

    font_var = tk.StringVar(value=font_default)
    size_var = tk.IntVar(value=14)
    bold_var = tk.BooleanVar(value=False)

    fondo_var = tk.BooleanVar(value=True)

    recursivo_var = tk.BooleanVar(value=False)
    eliminar_var = tk.BooleanVar(value=False)

    text_rgb = {"value": (0, 0, 128)}
    bg_rgb = {"value": (255, 255, 255)}

    result = {}

    frm = tk.Frame(
        win,
        bg=CONFIG_DIALOG_BG,
        padx=CONFIG_DIALOG_PADX,
        pady=CONFIG_DIALOG_PADY,
    )
    frm.grid(row=0, column=0, sticky="nsew")

    def _section_title(parent, text, **grid_opts):
        lbl = tk.Label(
            parent,
            text=text,
            bg=CONFIG_DIALOG_BG,
            fg=CONFIG_DIALOG_TITLE_FG,
            font=font_ui(FONT_SIZE_MD, "bold"),
            anchor="w",
        )
        lbl.grid(**grid_opts)
        return lbl

    def _field_label(parent, text, **grid_opts):
        lbl = tk.Label(
            parent,
            text=text,
            bg=CONFIG_DIALOG_BG,
            fg=CONFIG_DIALOG_LABEL_FG,
            font=font_ui(FONT_SIZE_SM),
            anchor="w",
        )
        lbl.grid(**grid_opts)
        return lbl

    # ======================================================
    # UTILIDADES COLOR / PREVIEW
    # ======================================================

    def _rgb_to_hex(rgb):
        return "#{:02x}{:02x}{:02x}".format(
            int(rgb[0]),
            int(rgb[1]),
            int(rgb[2])
        )

    def _texto_preview():

        num = "12"
        nombre = "Documento"

        pref = prefijo_var.get().strip()
        modo = modo_var.get()

        if modo == "numero":
            return num

        if modo == "prefijo_numero":
            return f"{pref} {num}".strip()

        if modo == "prefijo_numero_nombre":
            return f"{pref} {num} {nombre}".strip()

        return num

    def _font_preview():
        weight = "bold" if bold_var.get() else "normal"
        return (font_var.get(), int(size_var.get()), weight)

    # ======================================================
    # PREVIEW
    # ======================================================

    preview_wrap = tk.Frame(
        frm,
        bg=CONFIG_DIALOG_PANEL_BORDER,
        highlightthickness=0,
        bd=0,
    )
    preview_wrap.grid(
        row=0,
        column=0,
        columnspan=4,
        sticky="ew",
        pady=(0, SPACE_XS),
    )

    preview_inner = tk.Frame(preview_wrap, bg=CONFIG_DIALOG_PANEL_BG)
    preview_inner.pack(fill="both", expand=True, padx=1, pady=1)

    preview = tk.Canvas(
        preview_inner,
        width=360,
        height=120,
        bg="white",
        highlightthickness=1,
        highlightbackground=CONFIG_DIALOG_PREVIEW_BORDER,
    )

    preview.pack(padx=SPACE_SM, pady=(SPACE_SM, SPACE_XS))

    def actualizar_preview():

        preview.delete("all")

        texto = _texto_preview() or "(vacío)"

        fg = _rgb_to_hex(text_rgb["value"])
        bg = _rgb_to_hex(bg_rgb["value"])

        canvas_width = 360
        canvas_height = 120

        margin = 20
        padding = 8

        temp_id = preview.create_text(
            0,
            0,
            text=texto,
            font=_font_preview(),
            anchor="nw"
        )

        bbox = preview.bbox(temp_id)
        preview.delete(temp_id)

        if not bbox:
            return

        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        rect_width = text_width + padding * 2
        rect_height = text_height + padding

        if horizontal_var.get() == "left":
            x_rect = margin

        elif horizontal_var.get() == "center":
            x_rect = (canvas_width - rect_width) / 2

        else:
            x_rect = canvas_width - margin - rect_width

        if vertical_var.get() == "bottom":
            y_rect = canvas_height - margin - rect_height

        else:
            y_rect = margin

        if fondo_var.get():
            preview.create_rectangle(
                x_rect,
                y_rect,
                x_rect + rect_width,
                y_rect + rect_height,
                fill=bg,
                outline=""
            )

        preview.create_text(
            x_rect + padding,
            y_rect + rect_height / 2,
            text=texto,
            font=_font_preview(),
            fill=fg,
            anchor="w"
        )

    btn_preview = create_toolbar_button(
        preview_inner,
        text="Actualizar vista previa",
        command=actualizar_preview,
        variant="secondary",
    )
    btn_preview.pack(pady=(0, SPACE_SM))

    # ======================================================
    # NUMERACIÓN
    # ======================================================

    _section_title(
        frm,
        "Tipo de numeración:",
        row=2,
        column=0,
        columnspan=4,
        sticky="w",
        pady=(SPACE_SM, SPACE_XS),
    )

    ttk.Radiobutton(
        frm,
        text="Solo número",
        variable=modo_var,
        value="numero",
        command=actualizar_preview
    ).grid(
        row=3,
        column=0,
        columnspan=2,
        sticky="w",
        pady=2
    )

    ttk.Radiobutton(
        frm,
        text="Prefijo personalizado + número",
        variable=modo_var,
        value="prefijo_numero",
        command=actualizar_preview
    ).grid(
        row=4,
        column=0,
        sticky="w",
        pady=2
    )

    ttk.Radiobutton(
        frm,
        text="Prefijo personalizado + número + nombre del documento",
        variable=modo_var,
        value="prefijo_numero_nombre",
        command=actualizar_preview
    ).grid(
        row=5,
        column=0,
        sticky="w",
        pady=2
    )

    ent_pref = ttk.Entry(
        frm,
        textvariable=prefijo_var,
        width=24
    )

    ent_pref.grid(
        row=4,
        column=1,
        rowspan=2,
        sticky="w",
        padx=(SPACE_SM, 0)
    )

    def actualizar_estado_prefijo(*_):

        if modo_var.get() == "numero":
            ent_pref.configure(state="disabled")

        else:
            ent_pref.configure(state="normal")

        actualizar_preview()

    modo_var.trace_add("write", actualizar_estado_prefijo)
    prefijo_var.trace_add("write", lambda *_: actualizar_preview())

    # ======================================================
    # POSICIÓN + ESTILO (dos columnas)
    # ======================================================

    _section_title(
        frm,
        "Posición:",
        row=6,
        column=0,
        sticky="w",
        pady=(SPACE_MD, SPACE_XS),
    )

    _field_label(
        frm,
        "Vertical",
        row=7,
        column=0,
        sticky="w",
    )

    cmb_vertical = ttk.Combobox(
        frm,
        textvariable=vertical_var,
        values=["top", "bottom"],
        state="readonly",
        width=10
    )
    cmb_vertical.grid(
        row=7,
        column=1,
        sticky="w",
        padx=(SPACE_SM, 0)
    )
    cmb_vertical.bind("<<ComboboxSelected>>", lambda _e: actualizar_preview())

    _field_label(
        frm,
        "Horizontal",
        row=8,
        column=0,
        sticky="w",
    )

    cmb_horizontal = ttk.Combobox(
        frm,
        textvariable=horizontal_var,
        values=["left", "center", "right"],
        state="readonly",
        width=10
    )
    cmb_horizontal.grid(
        row=8,
        column=1,
        sticky="w",
        padx=(SPACE_SM, 0)
    )
    cmb_horizontal.bind("<<ComboboxSelected>>", lambda _e: actualizar_preview())

    _section_title(
        frm,
        "Estilo:",
        row=6,
        column=2,
        sticky="w",
        pady=(SPACE_MD, SPACE_XS),
        padx=(18, 0),
    )

    fuentes = []

    if font_default and font_default not in fuentes:
        fuentes.append(font_default)

    for f in ["Helvetica", "Courier", "Times-Roman"]:
        if f not in fuentes:
            fuentes.append(f)

    _field_label(
        frm,
        "Fuente",
        row=7,
        column=2,
        sticky="w",
        padx=(18, 0),
    )

    cmb_fuente = ttk.Combobox(
        frm,
        textvariable=font_var,
        values=fuentes,
        state="readonly",
        width=16
    )
    cmb_fuente.grid(
        row=7,
        column=3,
        sticky="w"
    )
    cmb_fuente.bind("<<ComboboxSelected>>", lambda _e: actualizar_preview())

    _field_label(
        frm,
        "Tamaño",
        row=8,
        column=2,
        sticky="w",
        padx=(18, 0),
    )

    spn_size = ttk.Spinbox(
        frm,
        from_=8,
        to=72,
        textvariable=size_var,
        width=6,
        command=actualizar_preview
    )
    spn_size.grid(
        row=8,
        column=3,
        sticky="w"
    )
    size_var.trace_add("write", lambda *_: actualizar_preview())

    ttk.Checkbutton(
        frm,
        text="Fondo",
        variable=fondo_var,
        command=actualizar_preview
    ).grid(
        row=9,
        column=2,
        columnspan=2,
        sticky="w",
        padx=(18, 0),
        pady=(SPACE_SM, 0)
    )

    ttk.Checkbutton(
        frm,
        text="Texto en negrita",
        variable=bold_var,
        command=actualizar_preview
    ).grid(
        row=10,
        column=2,
        columnspan=2,
        sticky="w",
        padx=(18, 0),
        pady=(2, 0)
    )

    # ======================================================
    # COLORES MANUALES
    # ======================================================

    def elegir_color_texto():

        c = colorchooser.askcolor(
            color=_rgb_to_hex(text_rgb["value"]),
            title="Color del texto"
        )[0]

        if c:
            text_rgb["value"] = (
                int(c[0]),
                int(c[1]),
                int(c[2])
            )
            actualizar_preview()

    def elegir_color_fondo():

        c = colorchooser.askcolor(
            color=_rgb_to_hex(bg_rgb["value"]),
            title="Color del fondo"
        )[0]

        if c:
            bg_rgb["value"] = (
                int(c[0]),
                int(c[1]),
                int(c[2])
            )
            actualizar_preview()

    color_row = tk.Frame(frm, bg=CONFIG_DIALOG_BG)
    color_row.grid(
        row=11,
        column=2,
        columnspan=2,
        sticky="w",
        padx=(18, 0),
        pady=(SPACE_SM, 0),
    )

    create_toolbar_button(
        color_row,
        text="Color texto",
        command=elegir_color_texto,
        variant="secondary",
    ).pack(side="left", padx=(0, SPACE_SM))

    create_toolbar_button(
        color_row,
        text="Color fondo",
        command=elegir_color_fondo,
        variant="secondary",
    ).pack(side="left")

    # ======================================================
    # PROCESAMIENTO
    # ======================================================

    ttk.Separator(frm).grid(
        row=14,
        column=0,
        columnspan=4,
        sticky="ew",
        pady=(SPACE_MD, SPACE_SM)
    )

    _section_title(
        frm,
        "Opciones de procesamiento:",
        row=15,
        column=0,
        columnspan=4,
        sticky="w",
    )

    ttk.Checkbutton(
        frm,
        text="Procesar subcarpetas (modo recursivo)",
        variable=recursivo_var
    ).grid(
        row=16,
        column=0,
        columnspan=4,
        sticky="w",
        pady=2
    )

    aviso = tk.Frame(frm, bg=FLOW_NOTICE_SAFE_BG)
    aviso.grid(
        row=17,
        column=0,
        columnspan=4,
        sticky="ew",
        pady=(SPACE_XS, 0),
    )

    ttk.Checkbutton(
        aviso,
        text="Eliminar originales tras procesar (⚠ irreversible)",
        variable=eliminar_var
    ).pack(anchor="w", padx=SPACE_SM, pady=SPACE_XS)

    # ======================================================
    # BOTONES
    # ======================================================

    btns = tk.Frame(frm, bg=CONFIG_DIALOG_BG)

    btns.grid(
        row=22,
        column=0,
        columnspan=4,
        sticky="e",
        pady=(SPACE_MD, 0)
    )

    def aceptar():

        modo = modo_var.get()
        pref = prefijo_var.get().strip()

        if modo != "numero" and not pref:
            messagebox.showwarning(
                "Prefijo requerido",
                "Debe introducir un prefijo.",
                parent=win
            )
            return

        result.update({
            "modo_numeracion": modo,
            "prefijo": pref,
            "vertical": vertical_var.get(),
            "horizontal": horizontal_var.get(),
            "font": font_var.get(),
            "fontsize": int(size_var.get()),
            "bold": bool(bold_var.get()),
            "background": bool(fondo_var.get()),
            "text_color": text_rgb["value"],
            "bg_color": bg_rgb["value"],
            "recursivo": bool(recursivo_var.get()),
            "eliminar_original": bool(eliminar_var.get()),
        })

        win.destroy()

    def cancelar():
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", cancelar)

    CorporateButton(
        btns,
        text="Cancelar",
        command=cancelar,
        variant="secondary",
        width=None,
        padx=12,
        pady=6,
    ).pack(side="left", padx=(0, SPACE_SM))

    CorporateButton(
        btns,
        text="Aceptar",
        command=aceptar,
        variant="diagnostic",
        width=None,
        padx=12,
        pady=6,
    ).pack(side="left")

    actualizar_estado_prefijo()
    actualizar_preview()

    win.wait_window()

    if created_root:
        root.destroy()

    if not result:
        raise CancelledByUser()

    return result
