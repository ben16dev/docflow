import tkinter as tk
from tkinter import ttk, colorchooser, messagebox

from ui.exceptions import CancelledByUser
from ui.window_icon import set_window_icon


# ======================================================
# COLORES CORPORATIVOS
# ======================================================

COLORES_CORPORATIVOS = {
    "PIAS": {
        "text": (212, 175, 55),
        "bg": (40, 81, 164),
    },
    "GHN": {
        "text": (128, 0, 255),
        "bg": (128, 255, 128),
    },
    "IM": {
        "text": (255, 215, 0),
        "bg": (20, 20, 95),
    },
    "RA": {
        "text": (128, 0, 0),
        "bg": (192, 192, 192),
    },
    "COMAP": {
        "text": (245, 240, 245),
        "bg": (74, 20, 84),
    },
    "360/365": {
        "text": (255, 255, 255),
        "bg": (210, 90, 60),
    },
    "CS": {
        "text": (45, 45, 50),
        "bg": (190, 145, 160),
    },
    "CARTCAM": {
        "text": (255, 255, 255),
        "bg": (0, 102, 204),
    },
    "PPDD": {
        "text": (255, 255, 255),
        "bg": (180, 40, 40),
    },
    "VIV": {
        "text": (255, 158, 62),
        "bg": (30, 60, 130),
    },
    "NVIV": {
        "text": (255, 158, 62),
        "bg": (15, 175, 180),
    },
    "EXP": {
        "text": (245, 230, 185),
        "bg": (90, 65, 50),
    },
}


def solicitar_configuracion(font_default: str):

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

    producto_var = tk.StringVar(value="PIAS")

    text_rgb = {"value": (0, 0, 128)}
    bg_rgb = {"value": (255, 255, 255)}

    result = {}

    frm = ttk.Frame(win, padding=12)
    frm.grid(row=0, column=0, sticky="nsew")

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

    preview = tk.Canvas(
        frm,
        width=360,
        height=120,
        bg="white",
        highlightthickness=1
    )

    preview.grid(
        row=0,
        column=0,
        columnspan=4,
        pady=(0, 5),
        sticky="ew"
    )

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

    ttk.Button(
        frm,
        text="Actualizar vista previa",
        command=actualizar_preview
    ).grid(
        row=1,
        column=0,
        columnspan=4,
        pady=(0, 10)
    )

    # ======================================================
    # NUMERACIÓN
    # ======================================================

    ttk.Label(
        frm,
        text="Tipo de numeración:"
    ).grid(
        row=2,
        column=0,
        sticky="w"
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
        padx=(8, 0)
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
    # POSICIÓN
    # ======================================================

    ttk.Label(
        frm,
        text="Posición:"
    ).grid(
        row=6,
        column=0,
        sticky="w",
        pady=(10, 0)
    )

    ttk.Label(
        frm,
        text="Vertical"
    ).grid(
        row=7,
        column=0,
        sticky="w"
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
        padx=(8, 0)
    )
    cmb_vertical.bind("<<ComboboxSelected>>", lambda _e: actualizar_preview())

    ttk.Label(
        frm,
        text="Horizontal"
    ).grid(
        row=8,
        column=0,
        sticky="w"
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
        padx=(8, 0)
    )
    cmb_horizontal.bind("<<ComboboxSelected>>", lambda _e: actualizar_preview())

    # ======================================================
    # ESTILO
    # ======================================================

    ttk.Label(
        frm,
        text="Estilo:"
    ).grid(
        row=6,
        column=2,
        sticky="w",
        pady=(10, 0),
        padx=(18, 0)
    )

    fuentes = []

    if font_default and font_default not in fuentes:
        fuentes.append(font_default)

    for f in ["Helvetica", "Courier", "Times-Roman"]:
        if f not in fuentes:
            fuentes.append(f)

    ttk.Label(
        frm,
        text="Fuente"
    ).grid(
        row=7,
        column=2,
        sticky="w",
        padx=(18, 0)
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

    ttk.Label(
        frm,
        text="Tamaño"
    ).grid(
        row=8,
        column=2,
        sticky="w",
        padx=(18, 0)
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
        pady=(6, 0)
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

    ttk.Button(
        frm,
        text="Color texto",
        command=elegir_color_texto
    ).grid(
        row=11,
        column=2,
        sticky="w",
        padx=(18, 0),
        pady=(8, 0)
    )

    ttk.Button(
        frm,
        text="Color fondo",
        command=elegir_color_fondo
    ).grid(
        row=11,
        column=3,
        sticky="w",
        pady=(8, 0)
    )

    # ======================================================
    # COLORES CORPORATIVOS
    # ======================================================

    def aplicar_colores_corporativos():

        producto = producto_var.get()

        if producto not in COLORES_CORPORATIVOS:
            return

        colores = COLORES_CORPORATIVOS[producto]

        text_rgb["value"] = colores["text"]
        bg_rgb["value"] = colores["bg"]

        actualizar_preview()

    ttk.Label(
        frm,
        text="Colores corporativos:"
    ).grid(
        row=12,
        column=2,
        sticky="w",
        padx=(18, 0),
        pady=(12, 0)
    )

    cmb_producto = ttk.Combobox(
        frm,
        textvariable=producto_var,
        values=list(COLORES_CORPORATIVOS.keys()),
        state="readonly",
        width=16
    )
    cmb_producto.grid(
        row=13,
        column=2,
        sticky="w",
        padx=(18, 0),
        pady=(4, 0)
    )

    ttk.Button(
        frm,
        text="Aplicar",
        command=aplicar_colores_corporativos
    ).grid(
        row=13,
        column=3,
        sticky="w",
        pady=(4, 0)
    )

    cmb_producto.bind(
        "<<ComboboxSelected>>",
        lambda _e: aplicar_colores_corporativos()
    )

    # ======================================================
    # PROCESAMIENTO
    # ======================================================

    ttk.Separator(frm).grid(
        row=14,
        column=0,
        columnspan=4,
        sticky="ew",
        pady=(14, 6)
    )

    ttk.Label(
        frm,
        text="Opciones de procesamiento:"
    ).grid(
        row=15,
        column=0,
        columnspan=2,
        sticky="w"
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

    ttk.Checkbutton(
        frm,
        text="Eliminar originales tras procesar (⚠ irreversible)",
        variable=eliminar_var
    ).grid(
        row=17,
        column=0,
        columnspan=4,
        sticky="w",
        pady=2
    )

    # ======================================================
    # BOTONES
    # ======================================================

    btns = ttk.Frame(frm)

    btns.grid(
        row=22,
        column=0,
        columnspan=4,
        sticky="e",
        pady=(14, 0)
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

    ttk.Button(
        btns,
        text="Cancelar",
        command=cancelar
    ).grid(
        row=0,
        column=0,
        padx=(0, 8)
    )

    ttk.Button(
        btns,
        text="Aceptar",
        command=aceptar
    ).grid(
        row=0,
        column=1
    )

    actualizar_estado_prefijo()
    actualizar_preview()

    win.wait_window()

    if created_root:
        root.destroy()

    if not result:
        raise CancelledByUser()

    return result
