"""
Lógica pura de previsualización para la herramienta "Renombrar archivos".

Todas las funciones son puras: sin Tkinter, sin I/O, sin efectos secundarios.
Diseñadas para ser testables de forma independiente.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from scripts.common.filenames import sanitize_filename
from scripts.common.rename_models import ArchivoEntrada, EntradaRenombrado


# ======================================================
# MODELOS DE PREVISUALIZACIÓN
# ======================================================

@dataclass
class FilaPreview:
    """Datos de una fila en la tabla de previsualización."""
    orden: int
    nombre_actual: str   # stem del archivo original
    nombre_nuevo: str    # nuevo nombre base (sin extensión)
    extension: str       # extensión original incluyendo el punto
    nombre_final: str    # nombre_nuevo + extension
    estado: str          # "OK" o "Conflicto"
    conflicto: str       # descripción del problema, o cadena vacía


@dataclass
class ResumenPreview:
    """Totales agregados para el panel de previsualización."""
    total: int
    validos: int
    conflictos: int


# ======================================================
# FUNCIONES PURAS
# ======================================================

def _normalizar_nombre(nuevo_nombre: str, extension: str) -> str:
    """
    Elimina la extensión del nuevo nombre si el usuario la incluyó.

    Evita que el nombre final resulte en 'archivo.pdf.pdf'.
    La comparación es insensible a mayúsculas/minúsculas.
    """
    nombre = nuevo_nombre.strip()
    if extension and nombre.lower().endswith(extension.lower()):
        nombre = nombre[: -len(extension)]
    return nombre


def construir_entradas(
    archivos: List[ArchivoEntrada],
    nombres: List[str],
) -> List[EntradaRenombrado]:
    """
    Construye la lista de EntradaRenombrado pareando archivos con nombres.

    - Los nombres se normalizan (espacios y extensión duplicada).
    - Si hay más archivos que nombres, los sobrantes reciben nombre vacío.
    """
    entradas: List[EntradaRenombrado] = []
    for i, archivo in enumerate(archivos):
        raw = nombres[i] if i < len(nombres) else ""
        nombre_base = _normalizar_nombre(raw, archivo.extension)
        entradas.append(EntradaRenombrado(archivo=archivo, nuevo_nombre=nombre_base))
    return entradas


def construir_preview(
    archivos: List[ArchivoEntrada],
    nombres: List[str],
) -> Tuple[List[FilaPreview], ResumenPreview]:
    """
    Genera la previsualización completa evaluando cada entrada.

    Validaciones aplicadas (por este orden):
      1. Nombre vacío.
      2. Caracteres no permitidos en nombre de archivo.
      3. Nombres finales duplicados entre filas.

    Devuelve la lista de filas y un resumen con los totales.
    """
    entradas = construir_entradas(archivos, nombres)
    errores: dict[int, list[str]] = {i: [] for i in range(len(entradas))}

    # 1. Nombres vacíos
    for i, entrada in enumerate(entradas):
        if not (entrada.nuevo_nombre or "").strip():
            errores[i].append("Nombre vacío")

    # 2. Caracteres no permitidos (solo si el nombre no está vacío)
    for i, entrada in enumerate(entradas):
        nombre = (entrada.nuevo_nombre or "").strip()
        if nombre:
            nombre_limpio = sanitize_filename(nombre, max_len=200)
            if nombre != nombre_limpio:
                errores[i].append("Caracteres no permitidos")

    # 3. Duplicados de nombre final
    vistos: dict[str, int] = {}
    for i, entrada in enumerate(entradas):
        clave = entrada.nombre_final.lower()
        if clave in vistos:
            j = vistos[clave]
            errores[i].append(f"Duplicado con fila #{j + 1}")
            msg_j = f"Duplicado con fila #{i + 1}"
            if msg_j not in errores[j]:
                errores[j].append(msg_j)
        else:
            vistos[clave] = i

    filas: List[FilaPreview] = []
    for i, entrada in enumerate(entradas):
        conflicto = "; ".join(errores[i])
        filas.append(FilaPreview(
            orden=i + 1,
            nombre_actual=entrada.archivo.nombre_original,
            nombre_nuevo=entrada.nuevo_nombre,
            extension=entrada.archivo.extension or "(sin ext.)",
            nombre_final=entrada.nombre_final,
            estado="Conflicto" if conflicto else "OK",
            conflicto=conflicto,
        ))

    total = len(filas)
    conflictos = sum(1 for f in filas if f.estado == "Conflicto")
    return filas, ResumenPreview(total=total, validos=total - conflictos, conflictos=conflictos)
