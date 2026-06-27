from pathlib import Path
from typing import Any, Dict, Optional


def build_result(
    message: str = "Proceso finalizado",
    output_dir: Optional[str | Path] = None,
    total: Optional[int] = None,
    procesados: int = 0,
    errores: int = 0,
    omitidos: Optional[int] = None,
    **extra_stats: Any
) -> Dict[str, Any]:
    """
    Construye un resultado estándar para DocFlow.

    Formato:
    {
        "message": str,
        "output_dir": str | None,
        "stats": {...}
    }
    """

    stats = {}

    if total is not None:
        if omitidos is None:
            omitidos = max(total - procesados - errores, 0)

        stats.update({
            "total": total,
            "procesados": procesados,
            "errores": errores,
            "omitidos": omitidos,
        })

    stats.update(extra_stats)

    return {
        "message": message,
        "output_dir": str(output_dir) if output_dir else None,
        "stats": stats,
    }


def build_cancelled_result(
    output_dir: Optional[str | Path] = None,
    total: Optional[int] = None,
    procesados: int = 0,
    errores: int = 0,
    omitidos: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Resultado estándar para procesos cancelados.
    """

    return build_result(
        message="Cancelado",
        output_dir=output_dir,
        total=total,
        procesados=procesados,
        errores=errores,
        omitidos=omitidos,
    )