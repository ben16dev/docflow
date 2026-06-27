# ui/ui_thread.py
import threading
from typing import Callable, TypeVar, Optional, Any

T = TypeVar("T")

_app: Any = None
_ui_thread_id: Optional[int] = None
_lock = threading.Lock()


def set_app(app: Any) -> None:
    """
    Registra la instancia principal de Tk y el hilo UI.
    Llamar una vez al iniciar la app (en el hilo principal).
    """
    global _app, _ui_thread_id
    with _lock:
        _app = app
        _ui_thread_id = threading.get_ident()


def is_ui_thread() -> bool:
    return threading.get_ident() == _ui_thread_id


def call_ui(fn: Callable[[], T]) -> T:
    """
    Ejecuta 'fn' en el hilo UI y devuelve su resultado.
    - Si ya estamos en UI: ejecuta directo.
    - Si estamos en worker: agenda con after() y espera.
    """
    if _app is None or _ui_thread_id is None:
        return fn()

    if is_ui_thread():
        return fn()

    done = threading.Event()
    result = {"value": None, "exc": None}

    def _runner():
        try:
            result["value"] = fn()
        except Exception as e:
            result["exc"] = e
        finally:
            done.set()

    _app.after(0, _runner)
    done.wait()

    if result["exc"] is not None:
        raise result["exc"]

    return result["value"]

