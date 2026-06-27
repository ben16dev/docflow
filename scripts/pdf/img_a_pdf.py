SCRIPT_META = {
    "name": "Imagen a PDF",
    "category": "PDF"
}

from pathlib import Path
from PIL import Image
import tkinter as tk
from tkinter import (
    filedialog,
    messagebox,
    BooleanVar,
    StringVar,
    Checkbutton,
    Button,
    Label,
    Entry,
)

from ui.exceptions import CancelledByUser
from ui.ui_thread import call_ui
from ui.window_icon import set_window_icon
from logger import logger

from scripts.common.filenames import resolve_conflict, sanitize_filename
from scripts.common.results import build_result, build_cancelled_result


VALID_EXT = {".png", ".jpg", ".jpeg"}


def _normalizar_img(img):
    return img.convert("RGB") if img.mode != "RGB" else img


class OpcionesImgPDF(tk.Toplevel):
    def __init__(self, parent, total_imgs, nombre_sugerido):
        super().__init__(parent)
        set_window_icon(self)

        self.title("Opciones de conversión")
        self.resizable(False, False)

        self.resultado = None

        self.var_un_solo_pdf = BooleanVar(self, value=False)
        self.var_usar_primero = BooleanVar(self, value=True)
        self.var_nombre = StringVar(self, value=nombre_sugerido)

        Label(
            self,
            text="Opciones de salida",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", padx=10, pady=(10, 0))

        if total_imgs > 1:
            Checkbutton(
                self,
                text="Generar un solo PDF con todas las imágenes",
                variable=self.var_un_solo_pdf
            ).pack(anchor="w", padx=20)
        else:
            self.var_un_solo_pdf.set(True)

        Label(
            self,
            text="Opciones de nombre",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", padx=10, pady=(10, 0))

        Checkbutton(
            self,
            text="Mantener el nombre del primer archivo",
            variable=self.var_usar_primero,
            command=self._toggle_nombre
        ).pack(anchor="w", padx=20)

        self.entry_nombre = Entry(
            self,
            textvariable=self.var_nombre,
            state="disabled",
            width=35
        )
        self.entry_nombre.pack(anchor="w", padx=40, pady=(4, 0))

        Button(
            self,
            text="Continuar",
            width=20,
            command=self._confirmar
        ).pack(pady=12)

        self._toggle_nombre()

        self.transient(parent)
        self.grab_set()
        self.wait_window()

    def _toggle_nombre(self):
        self.entry_nombre.config(
            state="disabled" if self.var_usar_primero.get() else "normal"
        )
        if not self.var_usar_primero.get():
            self.entry_nombre.focus_set()

    def _confirmar(self):
        if not self.var_usar_primero.get() and not self.var_nombre.get().strip():
            messagebox.showerror(
                "Nombre requerido",
                "Introduce un nombre base para el PDF.",
                parent=self
            )
            return

        self.resultado = {
            "un_solo_pdf": self.var_un_solo_pdf.get(),
            "nombre_base": self.var_nombre.get().strip(),
        }
        self.destroy()


# ======================================================
# RUN
# ======================================================

def run(progress=None, is_cancelled=None):

    parent = call_ui(lambda: tk._get_default_root())

    img_paths = call_ui(lambda: filedialog.askopenfilenames(
        title="Selecciona una o varias imágenes",
        filetypes=[("Imágenes", "*.png *.jpg *.jpeg")],
        parent=parent
    ))

    if not img_paths:
        raise CancelledByUser()

    img_paths = [
        Path(p) for p in img_paths
        if Path(p).suffix.lower() in VALID_EXT
    ]

    if not img_paths:
        raise RuntimeError("No se han seleccionado imágenes válidas.")

    output_dir = call_ui(lambda: filedialog.askdirectory(
        title="Selecciona carpeta de destino",
        parent=parent
    ))

    if not output_dir:
        raise CancelledByUser()

    output_dir = Path(output_dir)

    dialog_res = call_ui(lambda: OpcionesImgPDF(
        parent,
        len(img_paths),
        img_paths[0].stem
    ).resultado)

    if not dialog_res:
        raise CancelledByUser()

    un_solo_pdf = dialog_res["un_solo_pdf"]
    nombre_base = sanitize_filename(
        dialog_res["nombre_base"],
        max_len=120,
        fallback="imagenes"
    )

    total = len(img_paths)
    procesados = 0
    errores = 0

    logger.info(f"[IMG→PDF] Procesando {total} imagen(es)")

    try:

        # ==========================================
        # UN SOLO PDF
        # ==========================================
        if un_solo_pdf:

            imgs = []

            for i, p in enumerate(img_paths, start=1):

                if is_cancelled and is_cancelled():
                    raise CancelledByUser()

                try:
                    with Image.open(p) as img:
                        imgs.append(_normalizar_img(img.copy()))
                except Exception:
                    errores += 1
                    continue

                if progress:
                    progress(i, total)

            if not imgs:
                raise RuntimeError("No se pudo procesar ninguna imagen válida.")

            salida = resolve_conflict(
                output_dir / f"{nombre_base}.pdf",
                pattern="_v{i}"
            )

            imgs[0].save(
                salida,
                "PDF",
                save_all=True,
                append_images=imgs[1:],
                resolution=300
            )

            procesados = 1

        # ==========================================
        # UN PDF POR IMAGEN
        # ==========================================
        else:

            for i, p in enumerate(img_paths, start=1):

                if is_cancelled and is_cancelled():
                    raise CancelledByUser()

                try:
                    nombre = (
                        f"{nombre_base}.pdf"
                        if total == 1
                        else f"{nombre_base}_{i:02d}.pdf"
                    )

                    salida = resolve_conflict(
                        output_dir / nombre,
                        pattern="_v{i}"
                    )

                    with Image.open(p) as img:
                        img.convert("RGB").save(
                            salida,
                            "PDF",
                            resolution=300
                        )

                    procesados += 1

                except Exception:
                    errores += 1
                    continue

                if progress:
                    progress(i, total)

    except CancelledByUser:
        logger.info("[IMG→PDF] Cancelado por usuario")
        return build_cancelled_result(
            output_dir=output_dir,
            total=total,
            procesados=procesados,
            errores=errores,
        )

    logger.info(
        f"[IMG→PDF] Finalizado. Procesados: {procesados} de {total}. "
        f"Errores: {errores}. "
        f"Omitidos: {total - procesados - errores}"
    )

    return build_result(
        message="Proceso finalizado",
        output_dir=output_dir,
        total=total,
        procesados=procesados,
        errores=errores,
    )



