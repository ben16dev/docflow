# ui/tabs/tab_archivos.py
"""
Pestaña "Archivos" — Renombrar archivos

Flujo de tres pasos:
  Paso 1 (Sprint 2): Selección, visualización y gestión de la lista.
  Paso 2 (Sprint 3): Introducción de nuevos nombres (TXT o pegado).
  Paso 3 (Sprint 4): Previsualización y validación completa.
  Sprint 5:          Ejecución real y resumen.

La sesión (SesionRenombrado) es compartida entre los tres paneles a través
del ControladorFlujo, que también gestiona la navegación entre pasos.
"""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from scripts.files.preview_logic import construir_preview
from scripts.files.session import SesionRenombrado
from ui.styles import FRAME_BG, TITLE_FG


# ======================================================
# CONTROLADOR DE FLUJO (gestiona navegación y sesión compartida)
# ======================================================

class _ControladorFlujo(tk.Frame):
    """
    Gestiona la navegación entre los tres pasos del flujo de renombrado.

    Es el propietario exclusivo de SesionRenombrado, que se pasa como
    referencia a cada panel para que compartan el mismo estado.
    """

    def __init__(self, parent: tk.Widget, app: tk.Tk) -> None:
        super().__init__(parent, bg=FRAME_BG)
        self._app = app
        self._sesion = SesionRenombrado()
        self._panel_actual: tk.Frame | None = None

        self._p1 = _PanelSeleccion(self, app, self._sesion, self._ir_a_p2)
        self._p2 = _PanelNombres(self, app, self._sesion, self._ir_a_p1, self._ir_a_p3)
        self._p3 = _PanelPrevisualizacion(self, app, self._sesion, self._ir_a_p2)

        self._mostrar(self._p1)

    def _mostrar(self, panel: tk.Frame) -> None:
        if self._panel_actual is not None:
            self._panel_actual.pack_forget()
        self._panel_actual = panel
        panel.pack(fill="both", expand=True)

    def _ir_a_p1(self) -> None:
        self._mostrar(self._p1)

    def _ir_a_p2(self) -> None:
        self._p2.al_mostrar()
        self._mostrar(self._p2)

    def _ir_a_p3(self) -> None:
        self._p3.al_mostrar()
        self._mostrar(self._p3)


# ======================================================
# PASO 1 — SELECCIÓN DE ARCHIVOS
# ======================================================

class _PanelSeleccion(tk.Frame):
    """
    Panel de selección y gestión de archivos para "Renombrar archivos".

    Encapsula la presentación del paso 1. El estado de la sesión es
    gestionado externamente por _ControladorFlujo.
    """

    def __init__(
        self,
        parent: tk.Widget,
        app: tk.Tk,
        sesion: SesionRenombrado,
        on_siguiente,
    ) -> None:
        super().__init__(parent, bg=FRAME_BG)
        self._app = app
        self._sesion = sesion
        self._on_siguiente = on_siguiente
        self._construir_ui()

    # --------------------------------------------------
    # CONSTRUCCIÓN DE LA UI
    # --------------------------------------------------

    def _construir_ui(self) -> None:
        self._construir_cabecera()
        self._construir_barra_acciones()
        self._construir_tabla()
        self._construir_pie()
        self._actualizar_botones()

    def _construir_cabecera(self) -> None:
        marco = tk.LabelFrame(
            self,
            text="Renombrar archivos — Paso 1 de 3: Selección de archivos",
            bg=FRAME_BG,
            fg=TITLE_FG,
            font=("Segoe UI", 11, "bold"),
            padx=20,
            pady=10,
        )
        marco.pack(fill="x", padx=30, pady=(20, 8))

        tk.Label(
            marco,
            text=(
                "Añade los archivos que deseas renombrar. Puedes usar cualquier "
                "tipo de archivo y reordenarlos libremente.\n"
                "La extensión original de cada archivo se conservará siempre."
            ),
            justify="left",
            anchor="w",
            bg=FRAME_BG,
            fg="#333333",
            font=("Segoe UI", 10),
            wraplength=900,
        ).pack(anchor="w")

    def _construir_barra_acciones(self) -> None:
        barra = tk.Frame(self, bg=FRAME_BG)
        barra.pack(fill="x", padx=30, pady=(4, 4))

        self._btn_anadir = tk.Button(
            barra,
            text="Añadir archivos…",
            command=self._cmd_anadir,
            bg="#1f4e79",
            fg="white",
            activebackground="#2f6fa3",
            activeforeground="white",
            cursor="hand2",
            relief="raised",
            bd=1,
            padx=12,
            pady=5,
            font=("Segoe UI", 10),
        )
        self._btn_anadir.pack(side="left", padx=(0, 4))
        self._btn_anadir.bind("<Enter>", lambda _: self._btn_anadir.config(bg="#2f6fa3"))
        self._btn_anadir.bind("<Leave>", lambda _: self._btn_anadir.config(bg="#1f4e79"))

        _separador(barra)

        self._btn_subir = _boton_secundario(barra, "↑  Subir", self._cmd_subir)
        self._btn_subir.pack(side="left", padx=(0, 4))

        self._btn_bajar = _boton_secundario(barra, "↓  Bajar", self._cmd_bajar)
        self._btn_bajar.pack(side="left", padx=(0, 0))

        _separador(barra)

        self._btn_eliminar = _boton_secundario(
            barra, "Eliminar seleccionado", self._cmd_eliminar
        )
        self._btn_eliminar.pack(side="left", padx=(0, 4))

        self._btn_limpiar = _boton_secundario(barra, "Limpiar lista", self._cmd_limpiar)
        self._btn_limpiar.pack(side="left")

    def _construir_tabla(self) -> None:
        contenedor = tk.Frame(self, bg=FRAME_BG)
        contenedor.pack(fill="both", expand=True, padx=30, pady=(6, 0))

        columnas = ("orden", "nombre", "extension", "ruta")

        self._tree = ttk.Treeview(
            contenedor,
            columns=columnas,
            show="headings",
            selectmode="browse",
        )

        self._tree.heading("orden",     text="#",             anchor="center")
        self._tree.heading("nombre",    text="Nombre",        anchor="w")
        self._tree.heading("extension", text="Extensión",     anchor="center")
        self._tree.heading("ruta",      text="Ruta completa", anchor="w")

        self._tree.column("orden",     width=42,  minwidth=42,  anchor="center", stretch=False)
        self._tree.column("nombre",    width=230, minwidth=100, anchor="w",      stretch=True)
        self._tree.column("extension", width=80,  minwidth=60,  anchor="center", stretch=False)
        self._tree.column("ruta",      width=480, minwidth=180, anchor="w",      stretch=True)

        scroll_v = ttk.Scrollbar(contenedor, orient="vertical",   command=self._tree.yview)
        scroll_h = ttk.Scrollbar(contenedor, orient="horizontal", command=self._tree.xview)

        self._tree.configure(
            yscrollcommand=scroll_v.set,
            xscrollcommand=scroll_h.set,
        )

        self._tree.grid(row=0, column=0, sticky="nsew")
        scroll_v.grid(row=0, column=1, sticky="ns")
        scroll_h.grid(row=1, column=0, sticky="ew")

        contenedor.grid_rowconfigure(0, weight=1)
        contenedor.grid_columnconfigure(0, weight=1)

        self._tree.bind("<<TreeviewSelect>>", self._on_seleccion)

    def _construir_pie(self) -> None:
        pie = tk.Frame(self, bg=FRAME_BG)
        pie.pack(fill="x", padx=30, pady=(6, 4))

        self._lbl_conteo = tk.Label(
            pie,
            text="Ningún archivo en la lista.",
            fg="#555555",
            bg=FRAME_BG,
            font=("Segoe UI", 9),
            anchor="w",
        )
        self._lbl_conteo.pack(side="left")

        aviso = tk.Frame(self, bg="#fff8e7")
        aviso.pack(fill="x", padx=30, pady=(4, 8))

        tk.Label(
            aviso,
            text=(
                "  Modo seguro activo: los archivos originales nunca se modifican. "
                "El resultado se copiará a una nueva carpeta de salida."
            ),
            justify="left",
            anchor="w",
            bg="#fff8e7",
            fg="#7a5c00",
            font=("Segoe UI", 9),
            pady=7,
            padx=10,
        ).pack(anchor="w")

        self._btn_siguiente = tk.Button(
            self,
            text="▶   Siguiente — Introducir nombres",
            command=self._on_siguiente,
            state="disabled",
            font=("Segoe UI", 10, "bold"),
            padx=20,
            pady=8,
            bd=1,
            relief="raised",
            cursor="hand2",
        )
        self._btn_siguiente.pack(anchor="e", padx=30, pady=(0, 20))

    # --------------------------------------------------
    # COMANDOS
    # --------------------------------------------------

    def _cmd_anadir(self) -> None:
        rutas_str = filedialog.askopenfilenames(
            title="Seleccionar archivos para renombrar",
            parent=self._app,
        )
        if not rutas_str:
            return

        rutas = [Path(r) for r in rutas_str]
        nuevos = self._sesion.agregar(rutas)

        self._refrescar_tabla()

        if nuevos == 0:
            messagebox.showinfo(
                "Sin cambios",
                "Los archivos seleccionados ya estaban en la lista.",
                parent=self._app,
            )

    def _cmd_eliminar(self) -> None:
        seleccion = self._tree.selection()
        if not seleccion:
            return
        indice = self._tree.index(seleccion[0])
        self._sesion.eliminar(indice)
        self._refrescar_tabla()

    def _cmd_limpiar(self) -> None:
        if self._sesion.esta_vacia():
            return
        total = self._sesion.total()
        plural = "archivos" if total != 1 else "archivo"
        confirmar = messagebox.askyesno(
            "Limpiar lista",
            f"¿Eliminar {total} {plural} de la lista?\n\n"
            "Los archivos originales no se modificarán.",
            parent=self._app,
        )
        if confirmar:
            self._sesion.limpiar()
            self._refrescar_tabla()

    def _cmd_subir(self) -> None:
        seleccion = self._tree.selection()
        if not seleccion:
            return
        indice = self._tree.index(seleccion[0])
        self._sesion.subir(indice)
        self._refrescar_tabla(mantener_en=max(0, indice - 1))

    def _cmd_bajar(self) -> None:
        seleccion = self._tree.selection()
        if not seleccion:
            return
        indice = self._tree.index(seleccion[0])
        ultimo = self._sesion.total() - 1
        self._sesion.bajar(indice)
        self._refrescar_tabla(mantener_en=min(ultimo, indice + 1))

    # --------------------------------------------------
    # ACTUALIZACIÓN DE LA VISTA
    # --------------------------------------------------

    def _refrescar_tabla(self, mantener_en: int = None) -> None:
        for iid in self._tree.get_children():
            self._tree.delete(iid)

        iid_a_seleccionar = None

        for i, archivo in enumerate(self._sesion.archivos()):
            ext = archivo.extension if archivo.extension else "(sin extensión)"
            iid = self._tree.insert(
                "",
                "end",
                values=(
                    i + 1,
                    archivo.nombre_original,
                    ext,
                    str(archivo.ruta_original),
                ),
            )
            if mantener_en is not None and i == mantener_en:
                iid_a_seleccionar = iid

        if iid_a_seleccionar:
            self._tree.selection_set(iid_a_seleccionar)
            self._tree.see(iid_a_seleccionar)

        self._actualizar_conteo()
        self._actualizar_botones()

    def _on_seleccion(self, _event=None) -> None:
        self._actualizar_botones()

    def _actualizar_conteo(self) -> None:
        total = self._sesion.total()
        if total == 0:
            texto = "Ningún archivo en la lista."
        elif total == 1:
            texto = "1 archivo en la lista."
        else:
            texto = f"{total} archivos en la lista."
        self._lbl_conteo.config(text=texto)

    def _actualizar_botones(self) -> None:
        total = self._sesion.total()
        seleccion = self._tree.selection()
        tiene_sel = bool(seleccion)
        indice = self._tree.index(seleccion[0]) if tiene_sel else -1

        _estado(self._btn_eliminar, tiene_sel)
        _estado(self._btn_limpiar, total > 0)
        _estado(self._btn_subir,   tiene_sel and indice > 0)
        _estado(self._btn_bajar,   tiene_sel and indice < total - 1)
        _estado(self._btn_siguiente, total > 0)


# ======================================================
# PASO 2 — INTRODUCCIÓN DE NOMBRES
# ======================================================

class _PanelNombres(tk.Frame):
    """
    Panel para introducir los nuevos nombres de los archivos.

    El usuario puede pegar los nombres directamente (uno por línea)
    o cargarlos desde un archivo TXT.
    """

    def __init__(
        self,
        parent: tk.Widget,
        app: tk.Tk,
        sesion: SesionRenombrado,
        on_volver,
        on_siguiente,
    ) -> None:
        super().__init__(parent, bg=FRAME_BG)
        self._app = app
        self._sesion = sesion
        self._on_volver = on_volver
        self._on_siguiente = on_siguiente
        self._construir_ui()

    # --------------------------------------------------
    # CONSTRUCCIÓN DE LA UI
    # --------------------------------------------------

    def _construir_ui(self) -> None:
        self._construir_cabecera()
        self._construir_cuerpo()
        self._construir_pie()

    def _construir_cabecera(self) -> None:
        marco = tk.LabelFrame(
            self,
            text="Renombrar archivos — Paso 2 de 3: Introducir nombres",
            bg=FRAME_BG,
            fg=TITLE_FG,
            font=("Segoe UI", 11, "bold"),
            padx=20,
            pady=10,
        )
        marco.pack(fill="x", padx=30, pady=(20, 8))

        tk.Label(
            marco,
            text=(
                "Escribe o pega los nuevos nombres en el área de texto (uno por línea). "
                "El orden debe coincidir con el de la lista de archivos de la izquierda.\n"
                "No es necesario incluir la extensión: se conservará la original."
            ),
            justify="left",
            anchor="w",
            bg=FRAME_BG,
            fg="#333333",
            font=("Segoe UI", 10),
            wraplength=900,
        ).pack(anchor="w")

    def _construir_cuerpo(self) -> None:
        cuerpo = tk.Frame(self, bg=FRAME_BG)
        cuerpo.pack(fill="both", expand=True, padx=30, pady=(4, 4))
        cuerpo.grid_columnconfigure(0, weight=2)
        cuerpo.grid_columnconfigure(1, weight=3)
        cuerpo.grid_rowconfigure(0, weight=1)

        # --- Lista de archivos (izquierda) ---
        frame_archivos = tk.LabelFrame(
            cuerpo,
            text="Archivos seleccionados",
            bg=FRAME_BG,
            fg="#444444",
            font=("Segoe UI", 9),
            padx=6,
            pady=6,
        )
        frame_archivos.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        frame_archivos.grid_rowconfigure(0, weight=1)
        frame_archivos.grid_columnconfigure(0, weight=1)

        cols_arch = ("orden", "nombre")
        self._tree_arch = ttk.Treeview(
            frame_archivos,
            columns=cols_arch,
            show="headings",
            selectmode="none",
        )
        self._tree_arch.heading("orden",  text="#",      anchor="center")
        self._tree_arch.heading("nombre", text="Nombre", anchor="w")
        self._tree_arch.column("orden",  width=36,  minwidth=36,  anchor="center", stretch=False)
        self._tree_arch.column("nombre", width=220, minwidth=100, anchor="w",      stretch=True)

        sv_arch = ttk.Scrollbar(frame_archivos, orient="vertical",   command=self._tree_arch.yview)
        self._tree_arch.configure(yscrollcommand=sv_arch.set)

        self._tree_arch.grid(row=0, column=0, sticky="nsew")
        sv_arch.grid(row=0, column=1, sticky="ns")

        # --- Área de nombres (derecha) ---
        frame_nombres = tk.LabelFrame(
            cuerpo,
            text="Nuevos nombres (uno por línea)",
            bg=FRAME_BG,
            fg="#444444",
            font=("Segoe UI", 9),
            padx=6,
            pady=6,
        )
        frame_nombres.grid(row=0, column=1, sticky="nsew")
        frame_nombres.grid_rowconfigure(0, weight=1)
        frame_nombres.grid_columnconfigure(0, weight=1)

        self._txt_nombres = tk.Text(
            frame_nombres,
            font=("Courier New", 10),
            wrap="none",
            undo=True,
            relief="sunken",
            bd=1,
        )
        sv_txt_v = ttk.Scrollbar(frame_nombres, orient="vertical",   command=self._txt_nombres.yview)
        sv_txt_h = ttk.Scrollbar(frame_nombres, orient="horizontal", command=self._txt_nombres.xview)
        self._txt_nombres.configure(yscrollcommand=sv_txt_v.set, xscrollcommand=sv_txt_h.set)

        self._txt_nombres.grid(row=0, column=0, sticky="nsew")
        sv_txt_v.grid(row=0, column=1, sticky="ns")
        sv_txt_h.grid(row=1, column=0, sticky="ew")

        self._txt_nombres.bind("<<Modified>>", self._on_texto_modificado)

    def _construir_pie(self) -> None:
        barra = tk.Frame(self, bg=FRAME_BG)
        barra.pack(fill="x", padx=30, pady=(4, 4))

        self._btn_cargar = _boton_secundario(barra, "Cargar desde TXT…", self._cmd_cargar_txt)
        self._btn_cargar.pack(side="left", padx=(0, 8))

        self._btn_limpiar_txt = _boton_secundario(barra, "Limpiar nombres", self._cmd_limpiar_txt)
        self._btn_limpiar_txt.pack(side="left")

        pie = tk.Frame(self, bg=FRAME_BG)
        pie.pack(fill="x", padx=30, pady=(2, 4))

        self._lbl_info = tk.Label(
            pie,
            text="",
            fg="#555555",
            bg=FRAME_BG,
            font=("Segoe UI", 9),
            anchor="w",
        )
        self._lbl_info.pack(side="left")

        nav = tk.Frame(self, bg=FRAME_BG)
        nav.pack(fill="x", padx=30, pady=(4, 20))

        self._btn_volver = _boton_secundario(nav, "◀   Volver", self._on_volver)
        self._btn_volver.pack(side="left")

        self._btn_preview = tk.Button(
            nav,
            text="Ver previsualización   ▶",
            command=self._cmd_ver_preview,
            state="disabled",
            font=("Segoe UI", 10, "bold"),
            padx=20,
            pady=8,
            bd=1,
            relief="raised",
            cursor="hand2",
        )
        self._btn_preview.pack(side="right")

    # --------------------------------------------------
    # PUNTO DE ENTRADA AL MOSTRAR EL PANEL
    # --------------------------------------------------

    def al_mostrar(self) -> None:
        """Llamado por el controlador al navegar a este paso."""
        self._refrescar_lista_archivos()
        self._actualizar_info()

    # --------------------------------------------------
    # COMANDOS
    # --------------------------------------------------

    def _cmd_cargar_txt(self) -> None:
        ruta_str = filedialog.askopenfilename(
            title="Seleccionar archivo TXT con nombres",
            filetypes=[("Archivos de texto", "*.txt"), ("Todos los archivos", "*.*")],
            parent=self._app,
        )
        if not ruta_str:
            return
        try:
            contenido = Path(ruta_str).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            messagebox.showerror(
                "Error al leer el archivo",
                f"No se pudo leer el archivo seleccionado:\n{exc}",
                parent=self._app,
            )
            return
        self._txt_nombres.delete("1.0", "end")
        self._txt_nombres.insert("1.0", contenido.rstrip("\n"))
        self._actualizar_info()

    def _cmd_limpiar_txt(self) -> None:
        self._txt_nombres.delete("1.0", "end")
        self._actualizar_info()

    def _cmd_ver_preview(self) -> None:
        nombres = self._obtener_nombres()
        self._sesion.establecer_nombres(nombres)
        self._on_siguiente()

    # --------------------------------------------------
    # HELPERS
    # --------------------------------------------------

    def _obtener_nombres(self) -> list[str]:
        """Extrae la lista de líneas del área de texto."""
        texto = self._txt_nombres.get("1.0", "end-1c")
        return texto.splitlines()

    def _on_texto_modificado(self, _event=None) -> None:
        self._txt_nombres.edit_modified(False)
        self._actualizar_info()

    def _refrescar_lista_archivos(self) -> None:
        for iid in self._tree_arch.get_children():
            self._tree_arch.delete(iid)
        for i, archivo in enumerate(self._sesion.archivos()):
            self._tree_arch.insert(
                "", "end",
                values=(i + 1, archivo.nombre_completo),
            )

    def _actualizar_info(self) -> None:
        total_arch = self._sesion.total()
        nombres = self._obtener_nombres()
        total_nombres = sum(1 for n in nombres if n.strip())
        self._lbl_info.config(
            text=f"{total_arch} archivos · {total_nombres} nombres introducidos"
        )
        hay_suficientes = total_nombres >= total_arch and total_arch > 0
        _estado(self._btn_preview, hay_suficientes)


# ======================================================
# PASO 3 — PREVISUALIZACIÓN Y VALIDACIÓN
# ======================================================

class _PanelPrevisualizacion(tk.Frame):
    """
    Panel de previsualización y validación del renombrado.

    Muestra la tabla completa de cambios, diferencia visualmente las filas
    con conflicto y presenta un resumen. El botón "Ejecutar" solo se habilita
    si no hay conflictos.
    """

    _COL_ORDEN    = "orden"
    _COL_ACTUAL   = "actual"
    _COL_NUEVO    = "nuevo"
    _COL_EXT      = "ext"
    _COL_FINAL    = "final"
    _COL_ESTADO   = "estado"
    _COL_CONFLICTO = "conflicto"

    def __init__(
        self,
        parent: tk.Widget,
        app: tk.Tk,
        sesion: SesionRenombrado,
        on_volver,
    ) -> None:
        super().__init__(parent, bg=FRAME_BG)
        self._app = app
        self._sesion = sesion
        self._on_volver = on_volver
        self._construir_ui()

    # --------------------------------------------------
    # CONSTRUCCIÓN DE LA UI
    # --------------------------------------------------

    def _construir_ui(self) -> None:
        self._construir_cabecera()
        self._construir_tabla()
        self._construir_pie()

    def _construir_cabecera(self) -> None:
        marco = tk.LabelFrame(
            self,
            text="Renombrar archivos — Paso 3 de 3: Previsualización",
            bg=FRAME_BG,
            fg=TITLE_FG,
            font=("Segoe UI", 11, "bold"),
            padx=20,
            pady=10,
        )
        marco.pack(fill="x", padx=30, pady=(20, 8))

        tk.Label(
            marco,
            text=(
                "Revisa los cambios antes de ejecutar. "
                "Las filas marcadas como 'Conflicto' deben resolverse antes de continuar.\n"
                "Si todo es correcto, pulsa 'Ejecutar' para aplicar el renombrado."
            ),
            justify="left",
            anchor="w",
            bg=FRAME_BG,
            fg="#333333",
            font=("Segoe UI", 10),
            wraplength=900,
        ).pack(anchor="w")

    def _construir_tabla(self) -> None:
        contenedor = tk.Frame(self, bg=FRAME_BG)
        contenedor.pack(fill="both", expand=True, padx=30, pady=(4, 0))
        contenedor.grid_rowconfigure(0, weight=1)
        contenedor.grid_columnconfigure(0, weight=1)

        columnas = (
            self._COL_ORDEN,
            self._COL_ACTUAL,
            self._COL_NUEVO,
            self._COL_EXT,
            self._COL_FINAL,
            self._COL_ESTADO,
            self._COL_CONFLICTO,
        )

        self._tree = ttk.Treeview(
            contenedor,
            columns=columnas,
            show="headings",
            selectmode="browse",
        )

        self._tree.heading(self._COL_ORDEN,     text="#",            anchor="center")
        self._tree.heading(self._COL_ACTUAL,    text="Nombre actual", anchor="w")
        self._tree.heading(self._COL_NUEVO,     text="Nombre nuevo",  anchor="w")
        self._tree.heading(self._COL_EXT,       text="Extensión",     anchor="center")
        self._tree.heading(self._COL_FINAL,     text="Nombre final",  anchor="w")
        self._tree.heading(self._COL_ESTADO,    text="Estado",        anchor="center")
        self._tree.heading(self._COL_CONFLICTO, text="Conflicto",     anchor="w")

        self._tree.column(self._COL_ORDEN,     width=36,  minwidth=36,  anchor="center", stretch=False)
        self._tree.column(self._COL_ACTUAL,    width=180, minwidth=80,  anchor="w",      stretch=True)
        self._tree.column(self._COL_NUEVO,     width=180, minwidth=80,  anchor="w",      stretch=True)
        self._tree.column(self._COL_EXT,       width=70,  minwidth=50,  anchor="center", stretch=False)
        self._tree.column(self._COL_FINAL,     width=200, minwidth=80,  anchor="w",      stretch=True)
        self._tree.column(self._COL_ESTADO,    width=80,  minwidth=60,  anchor="center", stretch=False)
        self._tree.column(self._COL_CONFLICTO, width=220, minwidth=80,  anchor="w",      stretch=True)

        self._tree.tag_configure("ok",        foreground="#1a6b2a")
        self._tree.tag_configure("conflicto", foreground="#b71c1c")

        scroll_v = ttk.Scrollbar(contenedor, orient="vertical",   command=self._tree.yview)
        scroll_h = ttk.Scrollbar(contenedor, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=scroll_v.set, xscrollcommand=scroll_h.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        scroll_v.grid(row=0, column=1, sticky="ns")
        scroll_h.grid(row=1, column=0, sticky="ew")

    def _construir_pie(self) -> None:
        pie_resumen = tk.Frame(self, bg=FRAME_BG)
        pie_resumen.pack(fill="x", padx=30, pady=(6, 2))

        self._lbl_resumen = tk.Label(
            pie_resumen,
            text="",
            fg="#333333",
            bg=FRAME_BG,
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        )
        self._lbl_resumen.pack(side="left")

        nav = tk.Frame(self, bg=FRAME_BG)
        nav.pack(fill="x", padx=30, pady=(4, 20))

        self._btn_volver = _boton_secundario(nav, "◀   Volver", self._on_volver)
        self._btn_volver.pack(side="left")

        self._btn_ejecutar = tk.Button(
            nav,
            text="Ejecutar renombrado",
            command=self._cmd_ejecutar,
            state="disabled",
            bg="#1f4e79",
            fg="white",
            activebackground="#2f6fa3",
            activeforeground="white",
            disabledforeground="#aaaaaa",
            font=("Segoe UI", 10, "bold"),
            padx=20,
            pady=8,
            bd=1,
            relief="raised",
            cursor="hand2",
        )
        self._btn_ejecutar.pack(side="right")
        self._btn_ejecutar.bind("<Enter>", self._on_enter_ejecutar)
        self._btn_ejecutar.bind("<Leave>", self._on_leave_ejecutar)

    # --------------------------------------------------
    # PUNTO DE ENTRADA AL MOSTRAR EL PANEL
    # --------------------------------------------------

    def al_mostrar(self) -> None:
        """Recalcula y repopula la tabla cuando se navega a este paso."""
        archivos = self._sesion.archivos()
        nombres  = self._sesion.nombres()
        filas, resumen = construir_preview(archivos, nombres)
        self._repoblar_tabla(filas)
        self._actualizar_resumen(resumen)
        _estado(self._btn_ejecutar, resumen.conflictos == 0 and resumen.total > 0)

    # --------------------------------------------------
    # COMANDOS
    # --------------------------------------------------

    def _cmd_ejecutar(self) -> None:
        messagebox.showinfo(
            "Ejecutar renombrado",
            "La ejecución real del renombrado llegará en el Sprint 5.\n\n"
            "Todos los cambios validados están listos para aplicarse.",
            parent=self._app,
        )

    # --------------------------------------------------
    # ACTUALIZACIÓN DE LA VISTA
    # --------------------------------------------------

    def _repoblar_tabla(self, filas) -> None:
        for iid in self._tree.get_children():
            self._tree.delete(iid)

        for fila in filas:
            tag = "conflicto" if fila.estado == "Conflicto" else "ok"
            self._tree.insert(
                "", "end",
                values=(
                    fila.orden,
                    fila.nombre_actual,
                    fila.nombre_nuevo,
                    fila.extension,
                    fila.nombre_final,
                    fila.estado,
                    fila.conflicto,
                ),
                tags=(tag,),
            )

    def _actualizar_resumen(self, resumen) -> None:
        texto = (
            f"Total: {resumen.total}  ·  "
            f"Válidos: {resumen.validos}  ·  "
            f"Conflictos: {resumen.conflictos}"
        )
        color = "#b71c1c" if resumen.conflictos > 0 else "#1a6b2a"
        self._lbl_resumen.config(text=texto, fg=color)

    def _on_enter_ejecutar(self, _event=None) -> None:
        if self._btn_ejecutar["state"] == "normal":
            self._btn_ejecutar.config(bg="#2f6fa3")

    def _on_leave_ejecutar(self, _event=None) -> None:
        if self._btn_ejecutar["state"] == "normal":
            self._btn_ejecutar.config(bg="#1f4e79")


# ======================================================
# PUNTO DE ENTRADA DEL MÓDULO
# ======================================================

def build_tab(tab: tk.Widget, app: tk.Tk) -> None:
    """
    Construye e integra el flujo completo de "Renombrar archivos"
    en la pestaña "Archivos".

    El ControladorFlujo gestiona la sesión compartida y la navegación
    entre los tres pasos.
    """
    controlador = _ControladorFlujo(tab, app)
    controlador.pack(fill="both", expand=True)


# ======================================================
# HELPERS PRIVADOS
# ======================================================

def _separador(parent: tk.Widget) -> None:
    """Línea vertical decorativa entre grupos de botones."""
    tk.Frame(parent, width=1, bg="#c0c0c0").pack(
        side="left", fill="y", padx=10, pady=4
    )


def _boton_secundario(
    parent: tk.Widget, texto: str, comando
) -> tk.Button:
    """Botón secundario con estilo uniforme."""
    return tk.Button(
        parent,
        text=texto,
        command=comando,
        padx=9,
        pady=4,
        cursor="hand2",
        relief="raised",
        bd=1,
        font=("Segoe UI", 9),
    )


def _estado(boton: tk.Button, habilitado: bool) -> None:
    """Aplica el estado normal/disabled a un botón."""
    boton.config(state="normal" if habilitado else "disabled")
