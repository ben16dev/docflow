"""
Validadores para la herramienta "Renombrar archivos".

Todas las funciones son puras: reciben datos, devuelven resultados.
No tienen efectos secundarios ni dependencias de UI.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from scripts.common.filenames import sanitize_filename
from scripts.common.rename_models import (
    EntradaRenombrado,
    OperacionRenombrado,
    ResultadoValidacion,
)


# ======================================================
# VALIDADORES INDIVIDUALES
# ======================================================

def validar_archivos_existen(entradas: List[EntradaRenombrado]) -> List[str]:
    """
    Comprueba que todos los archivos de origen siguen existiendo en disco.
    """
    errores = []
    for entrada in entradas:
        if not entrada.archivo.existe():
            errores.append(
                f"Archivo no encontrado: {entrada.archivo.nombre_completo}"
            )
    return errores


def validar_nombres_no_vacios(entradas: List[EntradaRenombrado]) -> List[str]:
    """
    Comprueba que ningún nombre nuevo esté vacío.
    """
    errores = []
    for i, entrada in enumerate(entradas, start=1):
        if not (entrada.nuevo_nombre or "").strip():
            errores.append(
                f"El nombre #{i} está vacío "
                f"(archivo original: {entrada.archivo.nombre_completo})"
            )
    return errores


def validar_nombres_validos(entradas: List[EntradaRenombrado]) -> List[str]:
    """
    Comprueba que los nuevos nombres sean válidos como nombres de archivo.

    Un nombre es inválido si, tras aplicar sanitize_filename, difiere
    del valor introducido (indica que contenía caracteres prohibidos).
    """
    errores = []
    for entrada in entradas:
        nombre = (entrada.nuevo_nombre or "").strip()
        nombre_limpio = sanitize_filename(nombre, max_len=200)
        if nombre != nombre_limpio:
            errores.append(
                f"Nombre inválido: '{nombre}' → "
                f"contiene caracteres no permitidos o es demasiado largo"
            )
    return errores


def validar_nombres_unicos(entradas: List[EntradaRenombrado]) -> List[str]:
    """
    Comprueba que no haya nombres finales duplicados en la lista.
    Un duplicado causaría colisión al copiar.
    """
    vistos: dict[str, int] = {}
    duplicados = []

    for i, entrada in enumerate(entradas, start=1):
        nombre_final = entrada.nombre_final.lower()
        if nombre_final in vistos:
            duplicados.append(
                f"Nombre duplicado: '{entrada.nombre_final}' "
                f"(filas #{vistos[nombre_final]} y #{i})"
            )
        else:
            vistos[nombre_final] = i

    return duplicados


def validar_destino_libre(
    entradas: List[EntradaRenombrado],
    carpeta_destino: Path,
) -> List[str]:
    """
    Comprueba que ningún archivo de destino ya exista en la carpeta.

    DocFlow nunca sobrescribe archivos: si existe conflicto, la ejecución
    se bloquea antes de comenzar.
    """
    errores = []
    for entrada in entradas:
        destino = carpeta_destino / entrada.nombre_final
        if destino.exists():
            errores.append(
                f"Ya existe en destino: '{entrada.nombre_final}'"
            )
    return errores


# ======================================================
# VALIDACIÓN COMPLETA
# ======================================================

def validar_operacion(operacion: OperacionRenombrado) -> ResultadoValidacion:
    """
    Ejecuta todas las validaciones sobre una operación de renombrado.

    Devuelve ResultadoValidacion.ok() si todo es correcto,
    o ResultadoValidacion.con_errores([...]) con la lista completa de
    problemas encontrados.

    El orden refleja la prioridad de los errores:
    1. Archivos de origen deben existir.
    2. Nombres no pueden estar vacíos.
    3. Nombres deben ser válidos como nombres de archivo.
    4. Nombres deben ser únicos entre sí.
    5. Destino no debe tener conflictos.
    """
    errores: List[str] = []

    errores.extend(validar_archivos_existen(operacion.entradas))
    errores.extend(validar_nombres_no_vacios(operacion.entradas))
    errores.extend(validar_nombres_validos(operacion.entradas))
    errores.extend(validar_nombres_unicos(operacion.entradas))
    errores.extend(
        validar_destino_libre(operacion.entradas, operacion.carpeta_destino)
    )

    if errores:
        return ResultadoValidacion.con_errores(errores)

    return ResultadoValidacion.ok()
