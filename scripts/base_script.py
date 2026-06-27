"""
Contrato base para scripts de DocFlow.

Este archivo define el interfaz esperado para cualquier script
ejecutable desde la aplicación.

No es obligatorio heredar ni importar este módulo para que un
script funcione, pero sirve como referencia oficial de cómo
debe estructurarse un script.
"""

from pathlib import Path
from typing import Callable, Optional, Dict, Any


# ==========================================================
# TIPOS DE CALLBACK
# ==========================================================

ProgressCallback = Callable[[int, int], None]
CancelCallback = Callable[[], bool]


# ==========================================================
# RESULTADO ESTÁNDAR
# ==========================================================

ScriptResult = Dict[str, Any]

"""
Formato esperado del resultado:

{
    "message": str,          # mensaje final mostrado en la barra de estado
    "output_dir": str|Path   # carpeta de salida (opcional)
}
"""


# ==========================================================
# INTERFAZ BASE
# ==========================================================

def run(
    input_dir: Path,
    progress: Optional[ProgressCallback] = None,
    is_cancelled: Optional[CancelCallback] = None,
) -> ScriptResult:
    """
    Función principal que debe implementar cada script.

    Parámetros
    ----------
    input_dir : Path
        Carpeta de trabajo seleccionada por el usuario.

    progress : callable(actual, total)
        Callback para actualizar la barra de progreso.

    is_cancelled : callable() -> bool
        Devuelve True si el usuario ha cancelado la ejecución.

    Retorno
    -------
    dict
        Resultado estructurado:

        {
            "message": str,
            "output_dir": str | Path
        }
    """

    raise NotImplementedError("El script debe implementar la función run()")