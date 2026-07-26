"""
Renombrar archivos — DocFlow

Herramienta general para renombrado masivo de archivos de cualquier tipo.

Flujo completo:
  1. Selección de archivos (cualquier tipo y extensión).
  2. Visualización y gestión de la lista (eliminar, limpiar, reordenar).
  3. Introducción de nuevos nombres (vía TXT o pegado directo).
  4. Previsualización y validación.
  5. Elección de carpeta destino y ejecución real (modo COPIAR_A_CARPETA).
  6. Resumen final.

Restricciones de producto:
  - La extensión original siempre se conserva.
  - El único modo implementado es COPIAR_A_CARPETA: nunca modifica ni
    borra los archivos originales.
  - Nunca se permite sobrescribir archivos existentes en destino.
  - La ejecución se bloquea si se detectan conflictos en la previsualización.

Sprint 5: este módulo es el único punto real de ejecución. `run()` no
contiene lógica de copia: construye la operación a partir de la sesión
inyectada por la pestaña "Archivos" y delega el trabajo de disco en
scripts.files.rename_executor. Aquí solo se adapta el resultado interno
al contrato `build_result` que ya conocen ScriptRunner y ui/app.py.
"""

from __future__ import annotations

from pathlib import Path

from scripts.common.results import build_result
from scripts.files.preview_logic import construir_entradas
from scripts.files.rename_executor import ResultadoEjecucion, ejecutar_renombrado
from scripts.common.rename_models import OperacionRenombrado

# ======================================================
# METADATOS
# ======================================================

SCRIPT_META = {
    "name": "Renombrar archivos",
    "category": "ARCHIVOS",
    "description": (
        "Renombrado masivo de archivos de cualquier tipo mediante copia a una "
        "carpeta destino. La extensión original siempre se conserva y los "
        "archivos originales nunca se modifican."
    ),
    "version": "0.5.0",
    "author": "DocFlow",
}


# ======================================================
# RUN
# ======================================================

def run(progress=None, is_cancelled=None, sesion=None):
    """
    Punto de entrada real del renombrador de archivos.

    'sesion' es una SesionRenombrado inyectada por tab_archivos.py (ver
    _PanelPrevisualizacion._cmd_ejecutar) con archivos, nombres y carpeta
    destino ya establecidos. ScriptRunner invoca esta función únicamente
    con los kwargs 'progress' e 'is_cancelled'; 'sesion' llega ligada de
    antemano mediante functools.partial, sin alterar el contrato de
    ScriptRunner.
    """
    if sesion is None:
        raise RuntimeError("No hay una sesión de renombrado activa.")

    carpeta_destino = sesion.carpeta_destino()
    if not carpeta_destino:
        raise RuntimeError("No se ha seleccionado una carpeta de destino.")

    entradas = construir_entradas(sesion.archivos(), sesion.nombres())
    operacion = OperacionRenombrado(
        entradas=entradas,
        carpeta_destino=Path(carpeta_destino),
        modo=sesion.modo(),
    )

    resultado = ejecutar_renombrado(
        operacion,
        progress=progress,
        is_cancelled=is_cancelled,
    )

    return _adaptar_a_build_result(resultado)


# ======================================================
# ADAPTACIÓN AL CONTRATO build_result
# ======================================================

def _adaptar_a_build_result(resultado: ResultadoEjecucion) -> dict:
    """
    Traduce el resultado estructurado interno del ejecutor al contrato
    estándar de `build_result`, sin que el resto de la aplicación
    (ScriptRunner, StatusBar, ui/app.py) necesite conocer ResultadoEjecucion.
    """
    return build_result(
        message=_construir_mensaje(resultado),
        output_dir=resultado.carpeta_destino,
        total=resultado.total,
        procesados=resultado.procesados,
        errores=resultado.errores,
        omitidos=resultado.omitidos,
        copiados=resultado.copiados,
        cancelado=resultado.cancelado,
        incidencias=list(resultado.incidencias),
    )


def _construir_mensaje(resultado: ResultadoEjecucion) -> str:
    if resultado.cancelado:
        return "Cancelado"

    if resultado.errores or resultado.omitidos:
        return (
            f"Renombrado finalizado con incidencias — "
            f"copiados: {resultado.copiados}, omitidos: {resultado.omitidos}, "
            f"errores: {resultado.errores}"
        )

    return f"Renombrado completado — {resultado.copiados} archivo(s) copiado(s)"
