"""
Modelos de dominio para la herramienta "Renombrar archivos".

Estas clases son puras (sin Tkinter, sin I/O) para facilitar
los tests unitarios y la separación de responsabilidades.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List


# ======================================================
# ENUMERACIONES
# ======================================================

class ModoRenombrado(Enum):
    """
    Modo de operación al ejecutar el renombrado.

    COPIAR_A_CARPETA es el modo por defecto y el más seguro:
    nunca modifica los archivos originales.
    """
    COPIAR_A_CARPETA = "copiar"


# ======================================================
# MODELOS DE ENTRADA
# ======================================================

@dataclass(frozen=True)
class ArchivoEntrada:
    """
    Representa un archivo seleccionado por el usuario para renombrar.

    Inmutable para evitar mutaciones accidentales durante el flujo.
    """
    ruta_original: Path

    def __post_init__(self) -> None:
        if not isinstance(self.ruta_original, Path):
            object.__setattr__(self, "ruta_original", Path(self.ruta_original))

    @property
    def nombre_original(self) -> str:
        """Nombre del archivo sin extensión."""
        return self.ruta_original.stem

    @property
    def extension(self) -> str:
        """Extensión del archivo, incluyendo el punto (ej. '.pdf')."""
        return self.ruta_original.suffix

    @property
    def nombre_completo(self) -> str:
        """Nombre completo del archivo tal como está en disco."""
        return self.ruta_original.name

    def existe(self) -> bool:
        """Comprueba si el archivo sigue existiendo en disco."""
        return self.ruta_original.is_file()


@dataclass
class EntradaRenombrado:
    """
    Par (archivo original → nuevo nombre base).

    La extensión original siempre se conserva.
    El nuevo nombre no debe incluir extensión.
    """
    archivo: ArchivoEntrada
    nuevo_nombre: str

    @property
    def nombre_final(self) -> str:
        """Nombre completo resultante: nuevo_nombre + extensión original."""
        return f"{self.nuevo_nombre}{self.archivo.extension}"

    def tiene_cambio(self) -> bool:
        """Indica si el nuevo nombre difiere del nombre original."""
        return self.nuevo_nombre != self.archivo.nombre_original


# ======================================================
# OPERACIÓN COMPLETA
# ======================================================

@dataclass
class OperacionRenombrado:
    """
    Representa la operación completa de renombrado lista para ejecutar.

    Contiene la lista de pares (origen → destino), la carpeta de salida
    y el modo de operación elegido.
    """
    entradas: List[EntradaRenombrado] = field(default_factory=list)
    carpeta_destino: Path = field(default_factory=Path)
    modo: ModoRenombrado = ModoRenombrado.COPIAR_A_CARPETA

    def total(self) -> int:
        return len(self.entradas)

    def con_cambios(self) -> List[EntradaRenombrado]:
        """Devuelve solo los pares que implican un cambio real de nombre."""
        return [e for e in self.entradas if e.tiene_cambio()]


# ======================================================
# RESULTADO DE VALIDACIÓN
# ======================================================

@dataclass
class ResultadoValidacion:
    """
    Resultado de aplicar el validador sobre una operación.

    Si `valida` es False, `errores` contiene la lista de problemas
    encontrados, listos para mostrar al usuario.
    """
    valida: bool
    errores: List[str] = field(default_factory=list)

    @classmethod
    def ok(cls) -> "ResultadoValidacion":
        return cls(valida=True, errores=[])

    @classmethod
    def con_errores(cls, errores: List[str]) -> "ResultadoValidacion":
        return cls(valida=False, errores=errores)
