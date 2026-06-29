"""
Gestión de estado de sesión para "Renombrar archivos".

SesionRenombrado es el único punto de verdad sobre qué archivos
están en cola durante la sesión de la aplicación.

Responsabilidades:
  - Mantener el orden de los archivos.
  - Prevenir duplicados.
  - Exponer operaciones de manipulación seguras.

Diseñado para ser testeable sin dependencias de UI ni de disco.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from scripts.common.rename_models import ArchivoEntrada


class SesionRenombrado:
    """
    Gestiona la lista de archivos seleccionados para renombrar.

    El estado persiste en memoria durante toda la sesión de la aplicación.
    No realiza ninguna operación de I/O salvo la comprobación de existencia
    en `agregar()`.
    """

    def __init__(self) -> None:
        self._archivos: List[ArchivoEntrada] = []
        self._nombres: List[str] = []

    # --------------------------------------------------
    # MUTACIONES
    # --------------------------------------------------

    def agregar(self, rutas: List[Path]) -> int:
        """
        Añade archivos a la sesión, ignorando duplicados y rutas inválidas.

        Un archivo se considera duplicado si su ruta resuelta ya está en
        la lista. Se ignoran también rutas que no correspondan a archivos.

        Args:
            rutas: Rutas absolutas o relativas a los archivos a añadir.

        Returns:
            Número de archivos efectivamente añadidos.
        """
        rutas_existentes = {
            a.ruta_original.resolve() for a in self._archivos
        }
        nuevos = 0
        for ruta in rutas:
            ruta = Path(ruta)
            if not ruta.is_file():
                continue
            ruta_resuelta = ruta.resolve()
            if ruta_resuelta in rutas_existentes:
                continue
            self._archivos.append(ArchivoEntrada(ruta_original=ruta))
            rutas_existentes.add(ruta_resuelta)
            nuevos += 1
        return nuevos

    def eliminar(self, indice: int) -> None:
        """
        Elimina el archivo en la posición indicada (0-based).

        No hace nada si el índice está fuera de rango.
        """
        if 0 <= indice < len(self._archivos):
            del self._archivos[indice]

    def limpiar(self) -> None:
        """Vacía la lista completamente."""
        self._archivos.clear()

    def subir(self, indice: int) -> None:
        """
        Sube el elemento en la posición indicada una posición.

        No hace nada si ya está en la primera posición o si el índice
        está fuera de rango.
        """
        if 0 < indice < len(self._archivos):
            self._archivos[indice - 1], self._archivos[indice] = (
                self._archivos[indice],
                self._archivos[indice - 1],
            )

    def bajar(self, indice: int) -> None:
        """
        Baja el elemento en la posición indicada una posición.

        No hace nada si ya está en la última posición o si el índice
        está fuera de rango.
        """
        if 0 <= indice < len(self._archivos) - 1:
            self._archivos[indice], self._archivos[indice + 1] = (
                self._archivos[indice + 1],
                self._archivos[indice],
            )

    # --------------------------------------------------
    # CONSULTAS
    # --------------------------------------------------

    def archivos(self) -> List[ArchivoEntrada]:
        """Devuelve una copia de la lista en el orden actual."""
        return list(self._archivos)

    def contiene(self, ruta: Path) -> bool:
        """Comprueba si una ruta ya está en la sesión (por ruta resuelta)."""
        ruta_resuelta = Path(ruta).resolve()
        return any(
            a.ruta_original.resolve() == ruta_resuelta
            for a in self._archivos
        )

    def total(self) -> int:
        """Número de archivos en la sesión."""
        return len(self._archivos)

    def esta_vacia(self) -> bool:
        """True si no hay ningún archivo en la sesión."""
        return len(self._archivos) == 0

    def establecer_nombres(self, nombres: List[str]) -> None:
        """
        Almacena la lista de nuevos nombres introducidos por el usuario.

        Cada elemento corresponde al nuevo nombre base (sin extensión)
        del archivo en la misma posición de `archivos()`.
        """
        self._nombres = [str(n) for n in nombres]

    def nombres(self) -> List[str]:
        """Devuelve la lista de nuevos nombres en el orden almacenado."""
        return list(self._nombres)
