"""
Ejecución real de "Renombrar archivos" — modo COPIAR_A_CARPETA.

Función pura: sin Tkinter, sin conocimiento de SesionRenombrado ni de
ScriptRunner. Recibe una OperacionRenombrado ya construida y devuelve un
resultado estructurado (ResultadoEjecucion), sin acoplarse al contrato
de `build_result` (eso es responsabilidad de scripts/files/renombrar_archivos.py).

Reglas de seguridad aplicadas:
  - El archivo original nunca se modifica ni se borra.
  - Nunca se sobrescribe un archivo ya existente en destino.
  - Cada archivo se copia primero a un temporal en la carpeta destino y se
    sustituye de forma atómica por el nombre definitivo (os.replace), de
    modo que nunca puede quedar un archivo final parcialmente escrito
    tras una cancelación o una excepción.
  - La cancelación es cooperativa y solo se comprueba entre archivos,
    nunca a mitad de la copia de uno de ellos.
  - Una incidencia en un archivo (colisión, desaparición, permisos) se
    registra y el resto del lote continúa. Solo un fallo global (p. ej.
    no se puede crear/usar la carpeta destino, o la operación ya no es
    válida) aborta la ejecución completa mediante una excepción.
"""

from __future__ import annotations

import os
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from scripts.common.rename_models import OperacionRenombrado
from scripts.common.rename_validators import validar_operacion
from ui.exceptions import CancelledByUser


@dataclass
class ResultadoEjecucion:
    """Resultado estructurado interno de una ejecución de renombrado."""
    total: int
    procesados: int = 0
    copiados: int = 0
    omitidos: int = 0
    errores: int = 0
    cancelado: bool = False
    carpeta_destino: Optional[Path] = None
    incidencias: List[str] = field(default_factory=list)


def _copiar_archivo_seguro(origen: Path, destino: Path) -> None:
    """
    Copia 'origen' a 'destino' de forma segura frente a cortes o cancelación.

    1. Copia a un archivo temporal en la misma carpeta de destino.
    2. Verifica que el tamaño copiado coincide con el del original.
    3. Sustituye de forma atómica el temporal por el nombre definitivo,
       comprobando justo antes que no haya aparecido una colisión.

    Si cualquier paso falla, el temporal se elimina: nunca queda un
    archivo con el nombre definitivo a medio copiar.
    """
    carpeta = destino.parent
    temporal = carpeta / f".{destino.name}.tmp-{uuid.uuid4().hex[:8]}"

    try:
        shutil.copy2(origen, temporal)

        if temporal.stat().st_size != origen.stat().st_size:
            raise OSError(f"La copia de '{origen.name}' no se completó correctamente")

        if destino.exists():
            raise FileExistsError(
                f"Colisión de última hora al finalizar la copia: {destino.name}"
            )

        os.replace(temporal, destino)

    except BaseException:
        if temporal.exists():
            try:
                temporal.unlink()
            except OSError:
                pass
        raise


def ejecutar_renombrado(
    operacion: OperacionRenombrado,
    progress: Optional[Callable[[int, int], None]] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> ResultadoEjecucion:
    """
    Ejecuta el modo COPIAR_A_CARPETA sobre una operación ya construida.

    Antes de tocar disco, revalida la operación completa con
    validar_operacion(): defensa en profundidad frente a cambios ocurridos
    entre la previsualización y el momento de la ejecución. Si la
    revalidación falla, se lanza RuntimeError (fallo global, no hay nada
    seguro que ejecutar).

    Nunca propaga CancelledByUser: una cancelación se refleja en
    resultado.cancelado = True junto con las cifras acumuladas hasta ese
    punto, para que el llamador siempre reciba un resultado utilizable.
    """
    total = operacion.total()
    resultado = ResultadoEjecucion(total=total, carpeta_destino=operacion.carpeta_destino)

    validacion = validar_operacion(operacion)
    if not validacion.valida:
        raise RuntimeError(
            "La operación de renombrado ya no es válida:\n" + "\n".join(validacion.errores)
        )

    operacion.carpeta_destino.mkdir(parents=True, exist_ok=True)

    try:
        for i, entrada in enumerate(operacion.entradas, start=1):
            if is_cancelled and is_cancelled():
                raise CancelledByUser()

            if progress:
                progress(i, total)

            try:
                if not entrada.archivo.existe():
                    resultado.omitidos += 1
                    resultado.incidencias.append(
                        f"Omitido — el archivo ya no existe: {entrada.archivo.nombre_completo}"
                    )
                    continue

                destino = operacion.carpeta_destino / entrada.nombre_final
                if destino.exists():
                    resultado.errores += 1
                    resultado.incidencias.append(
                        f"Colisión — ya existe en destino: {entrada.nombre_final}"
                    )
                    continue

                _copiar_archivo_seguro(entrada.archivo.ruta_original, destino)
                resultado.copiados += 1

            except PermissionError as exc:
                resultado.errores += 1
                resultado.incidencias.append(
                    f"Permisos insuficientes — {entrada.archivo.nombre_completo}: {exc}"
                )
            except OSError as exc:
                resultado.errores += 1
                resultado.incidencias.append(
                    f"Error de E/S — {entrada.archivo.nombre_completo}: {exc}"
                )
            finally:
                resultado.procesados += 1

    except CancelledByUser:
        resultado.cancelado = True

    return resultado
