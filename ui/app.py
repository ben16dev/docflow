import os
from collections import deque
from pathlib import Path

from ui.ui_thread import set_app
from core.script_runner import ScriptRunner

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import Image, ImageTk

from logger import logger
from version import (
    APP_NAME,
    APP_VERSION,
    APP_AUTHOR,
)

from ui.tabs.tab_mbox import build_tab as build_tab_mbox
from ui.tabs.tab_eml import build_tab as build_tab_eml
from ui.tabs.tab_pdf import build_tab as build_tab_pdf

from ui.dialog_error import show_error_dialog
from ui.status_bar import StatusBar
from config import set_ruta, get_ruta
from ui.window_icon import set_window_icon
from utils.resources import resource_path
from ui.styles import TOP_BG


RUTA_PLACEHOLDER = "Selecciona la carpeta de trabajo aquí"


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        # Registrar instancia principal para llamadas seguras al hilo UI
        set_app(self)

        self._icon_cache = {}
        self.last_result = None

        self._configurar_icono()

        self.title(f"{APP_NAME} — {APP_VERSION}")
        self.minsize(950, 920)
        self.geometry("1200x800")

        self._cancelado = False
        self._ejecutando = False
        self.historial = deque(maxlen=5)
        self.runner = ScriptRunner()

        self.var_ruta = tk.StringVar()
        ruta_inicial = get_ruta("pdf")
        self.var_ruta.set(str(ruta_inicial) if ruta_inicial else "")

        self._crear_estilos()

        self.main_container = tk.Frame(self)
        self.main_container.pack(fill="both", expand=True)

        self._crear_cabecera()
        self._crear_tabs()

        self.status_bar = StatusBar(
            parent=self,
            app_name=APP_NAME,
            app_version=APP_VERSION,
            app_author=APP_AUTHOR,
            cancel_callback=self._cancelar
        )

        try:
            self.status_bar.btn_diag.config(command=self._mostrar_ultimo_proceso)
        except Exception:
            pass

        self.status_bar.set_state("idle")
        self.status_bar.set_status("Listo")

    def _call_ui(self, func, *args, **kwargs):
        self.after(0, lambda: func(*args, **kwargs))

    def _load_icon(self, path, size):
        key = (str(path), size)

        if key in self._icon_cache:
            return self._icon_cache[key]

        try:
            img = Image.open(path).resize(size)
            icon = ImageTk.PhotoImage(img)
            self._icon_cache[key] = icon
            return icon
        except Exception:
            return None

    def _configurar_icono(self):
        try:
            set_window_icon(self)

            if os.name == "nt":
                try:
                    import ctypes
                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                        "DocFlow"
                    )
                except Exception:
                    pass

        except Exception:
            pass

    def _crear_cabecera(self):
        """Cabecera compacta con logo centrado sobre las pestañas."""
        LOGO_H = 48

        header = tk.Frame(self.main_container, bg=TOP_BG)
        header.pack(fill="x", side="top")

        self._logo_image = None

        try:
            logo_path = resource_path("assets/logo.png")
            img = Image.open(logo_path).convert("RGBA")
            orig_w, orig_h = img.size
            new_w = int(orig_w * LOGO_H / orig_h)
            img = img.resize((new_w, LOGO_H), Image.Resampling.LANCZOS)
            self._logo_image = ImageTk.PhotoImage(img)
            tk.Label(
                header,
                image=self._logo_image,
                bg=TOP_BG,
                bd=0,
                highlightthickness=0,
            ).pack(pady=(9, 9))
        except Exception as exc:
            logger.warning(f"No se pudo cargar assets/logo.png: {exc}")

        tk.Frame(self.main_container, height=1, bg="#c8ddf0").pack(fill="x", side="top")

    def _crear_estilos(self):
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure(
            "DocFlow.Horizontal.TProgressbar",
            troughcolor="#eaf4ff",
            background="#6de800",
            thickness=16
        )

    def _crear_tabs(self):
        self.notebook = ttk.Notebook(self.main_container)
        self.notebook.pack(fill="both", expand=True)

        self.tab_mbox = ttk.Frame(self.notebook)
        self.tab_eml = ttk.Frame(self.notebook)
        self.tab_pdf = ttk.Frame(self.notebook)

        try:
            self.icon_mbox = self._load_icon(resource_path("ui/icons/mbox.png"), (16, 16))
            self.icon_eml = self._load_icon(resource_path("ui/icons/eml.png"), (16, 16))
            self.icon_pdf = self._load_icon(resource_path("ui/icons/pdf.png"), (16, 16))

            self.notebook.add(
                self.tab_mbox,
                text="MBOX",
                image=self.icon_mbox,
                compound="left"
            )
            self.notebook.add(
                self.tab_eml,
                text="EML",
                image=self.icon_eml,
                compound="left"
            )
            self.notebook.add(
                self.tab_pdf,
                text="PDF",
                image=self.icon_pdf,
                compound="left"
            )

        except Exception:
            self.notebook.add(self.tab_mbox, text="MBOX")
            self.notebook.add(self.tab_eml, text="EML")
            self.notebook.add(self.tab_pdf, text="PDF")

        build_tab_mbox(self.tab_mbox, self)
        build_tab_eml(self.tab_eml, self)
        build_tab_pdf(self.tab_pdf, self)

    def _seleccionar_carpeta(self):
        ruta = filedialog.askdirectory(parent=self)
        if not ruta:
            return

        ruta = Path(ruta)
        self.var_ruta.set(str(ruta))

        set_ruta("pdf", ruta)
        set_ruta("mbox", ruta)
        set_ruta("eml", ruta)

    def _cancelar(self):
        self._cancelado = True
        self.status_bar.set_status("Cancelando…")
        self.status_bar.set_state("error")

    def _bloquear_tabs(self, bloquear=True):
        state = "disabled" if bloquear else "normal"
        for i in range(self.notebook.index("end")):
            self.notebook.tab(i, state=state)

    def _actualizar_historial(self, nombre_script):
        self.historial.appendleft(nombre_script)
        self.status_bar.update_history(list(self.historial))

    def _mostrar_ultimo_proceso(self):
        if not self.last_result:
            messagebox.showinfo(
                "Último proceso",
                "No hay ejecuciones recientes.",
                parent=self
            )
            return

        res = self.last_result

        script_name = res.get("script_name", "Proceso")
        mensaje = res.get("message", "Sin mensaje")
        carpeta = res.get("output_dir") or "N/A"
        stats = res.get("stats") or {}

        if stats:
            stats_text = "\n".join(f"{k}: {v}" for k, v in stats.items())
        else:
            stats_text = "Sin datos"

        texto = (
            f"Último proceso ejecutado\n"
            f"{'-' * 40}\n\n"
            f"Script: {script_name}\n"
            f"Mensaje: {mensaje}\n\n"
            f"{stats_text}\n\n"
            f"Carpeta de salida:\n{carpeta}"
        )

        messagebox.showinfo(
            "Diagnóstico",
            texto,
            parent=self
        )

    def _validar_carpeta(self, nombre_script):
        nombre_script = (nombre_script or "").strip()

        ruta_txt = (self.var_ruta.get() or "").strip()

        if not ruta_txt or ruta_txt == RUTA_PLACEHOLDER:
            messagebox.showwarning(
                "Ruta requerida",
                "Debes seleccionar una ruta de trabajo antes de ejecutar.",
                parent=self
            )
            return False

        ruta = Path(ruta_txt)

        if not ruta.exists():
            messagebox.showerror(
                "Error",
                "La carpeta seleccionada no existe.",
                parent=self
            )
            return False

        try:
            contenido = list(ruta.iterdir())
        except Exception:
            messagebox.showerror(
                "Error",
                "No se puede acceder a la carpeta seleccionada.",
                parent=self
            )
            return False

        if not contenido:
            messagebox.showwarning(
                "Carpeta vacía",
                "La carpeta seleccionada está vacía.",
                parent=self
            )
            return False

        nombre_script_l = nombre_script.lower()

        if "mbox" in nombre_script_l:
            extensiones = [".mbox"]
            archivos = [
                f for f in ruta.iterdir()
                if f.is_file() and f.suffix.lower() in extensiones
            ]

        elif "eml" in nombre_script_l:
            extensiones = [".eml"]
            archivos = [
                f for f in ruta.iterdir()
                if f.is_file() and f.suffix.lower() in extensiones
            ]

        elif "img" in nombre_script_l or "imagen" in nombre_script_l:
            extensiones = [
                ".jpg", ".jpeg", ".png", ".bmp",
                ".tiff", ".tif", ".webp"
            ]
            archivos = [
                f for f in ruta.iterdir()
                if f.is_file() and f.suffix.lower() in extensiones
            ]

        else:
            extensiones = [".pdf", ".mbox"]
            archivos = [
                f for f in ruta.rglob("*")
                if f.is_file() and f.suffix.lower() in extensiones
            ]

        if not archivos:
            messagebox.showwarning(
                "Sin archivos válidos",
                "No se encontraron archivos compatibles para este proceso.\n\n"
                f"Extensiones esperadas: {', '.join(extensiones)}",
                parent=self
            )
            return False

        return True

    def _ejecutar(self, funcion, *args, **kwargs):
        if self._ejecutando:
            return

        nombre_script = kwargs.get("action", "Script")
        ruta = (self.var_ruta.get() or "").strip()

        if not self._validar_carpeta(nombre_script):
            return

        confirmar = messagebox.askyesno(
            "Confirmar ejecución",
            f"¿Deseas ejecutar:\n\n{nombre_script}\n\nEn la ruta:\n{ruta} ?",
            parent=self
        )

        if not confirmar:
            return

        logger.info(f"Ejecutando script: {nombre_script}")
        logger.info(f"Ruta seleccionada: {ruta}")

        self._actualizar_historial(nombre_script)

        self._ejecutando = True
        self._cancelado = False

        self.config(cursor="watch")
        self.status_bar.reset_progress()
        self.status_bar.reset_timer()
        self.status_bar.disable_open_button()
        self.status_bar.set_status(f"Ejecutando: {nombre_script}")
        self.status_bar.set_state("running")
        self._bloquear_tabs(True)

        def progreso(actual, total):
            self._call_ui(self.status_bar.set_progress, actual, total)

        def cancelado():
            return self._cancelado

        def on_success(resultado):
            if isinstance(resultado, dict):
                mensaje = resultado.get("message", "Completado")
                carpeta = resultado.get("output_dir")
                stats = resultado.get("stats", {})
            else:
                mensaje = str(resultado)
                carpeta = None
                stats = {}

            self.last_result = {
                "script_name": nombre_script,
                "message": mensaje,
                "output_dir": carpeta,
                "stats": stats,
            }

            self._call_ui(self.status_bar.set_status, mensaje)
            self._call_ui(self.status_bar.set_state, "success")

            if carpeta:
                self._call_ui(self.status_bar.enable_open_button, carpeta)

        def on_error(error_payload=None):
            if isinstance(error_payload, dict):
                mensaje = error_payload.get("user_message") or "Error durante ejecución"
                log_file = error_payload.get("log_file")
            else:
                mensaje = error_payload or "Error durante ejecución"
                log_file = None

            self.last_result = {
                "script_name": nombre_script,
                "message": mensaje,
                "output_dir": None,
                "stats": {}
            }

            def _mostrar_error():
                show_error_dialog(
                    parent=self,
                    user_message=mensaje,
                    log_file=log_file,
                )

            self._call_ui(_mostrar_error)

            status = mensaje.split("\n", 1)[0]
            if len(status) > 80:
                status = status[:77] + "..."
            self._call_ui(self.status_bar.set_status, f"Error: {status}")
            self._call_ui(self.status_bar.set_state, "error")

        def on_finally():
            self._call_ui(self.config, cursor="")
            self._call_ui(self.status_bar.reset_progress)
            self._call_ui(self.status_bar.reset_timer)
            self._call_ui(self._bloquear_tabs, False)
            self._call_ui(setattr, self, "_ejecutando", False)

        self.runner.run(
            funcion=funcion,
            progress=progreso,
            is_cancelled=cancelado,
            on_success=on_success,
            on_error=on_error,
            on_finally=on_finally
        )


if __name__ == "__main__":
    app = App()
    app.mainloop()
