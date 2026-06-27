import traceback
from typing import Callable, Tuple, Any

def ejecutar(funcion: Callable[[], Any]) -> Tuple[bool, Any]:
    try:
        resultado = funcion()
        return True, resultado
    except Exception:
        return False, traceback.format_exc()
