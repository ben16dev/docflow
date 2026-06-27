import threading
import traceback
from logger import logger
from ui.exceptions import CancelledByUser


class ScriptRunner:
    """
    Ejecuta scripts en un hilo separado y devuelve el resultado mediante callbacks.
    """

    def __init__(self):
        self._thread = None

    def run(self, funcion, progress, is_cancelled, on_success, on_error, on_finally):
        """
        Ejecuta un script en segundo plano.
        """

        def tarea():
            try:
                resultado = funcion(
                    progress=progress,
                    is_cancelled=is_cancelled
                )

                on_success(resultado)

            except CancelledByUser:
                logger.info("[ScriptRunner] Cancelado por usuario")
                on_success({
                    "message": "Cancelado",
                    "output_dir": None,
                    "stats": {}
                })

            except Exception:
                error_text = traceback.format_exc()
                logger.error(error_text)

                on_error("Se ha producido un error durante la ejecución.\nRevisa el log.")

            finally:
                on_finally()

        self._thread = threading.Thread(target=tarea, daemon=True)
        self._thread.start()