"""
Tests unitarios para scripts/files/preview_logic.py

Verifica la lógica pura de previsualización:
  - Construcción de entradas (pareado archivos ↔ nombres).
  - Normalización de nombres (extensión duplicada).
  - Detección de conflictos: nombre vacío, caracteres inválidos, duplicados.
  - Resumen de totales.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.common.rename_models import ArchivoEntrada
from scripts.files.preview_logic import (
    FilaPreview,
    ResumenPreview,
    _normalizar_nombre,
    construir_entradas,
    construir_preview,
)


# ======================================================
# HELPERS
# ======================================================

def _archivo(nombre: str) -> ArchivoEntrada:
    """Crea un ArchivoEntrada con ruta ficticia (no requiere que exista en disco)."""
    return ArchivoEntrada(ruta_original=Path(f"/tmp/test/{nombre}"))


# ======================================================
# _normalizar_nombre
# ======================================================

class TestNormalizarNombre:
    def test_nombre_sin_extension_no_cambia(self):
        assert _normalizar_nombre("contrato", ".pdf") == "contrato"

    def test_extension_incluida_se_elimina(self):
        assert _normalizar_nombre("contrato.pdf", ".pdf") == "contrato"

    def test_extension_mayusculas_se_elimina(self):
        assert _normalizar_nombre("CONTRATO.PDF", ".pdf") == "CONTRATO"

    def test_sin_extension_original_no_cambia(self):
        assert _normalizar_nombre("contrato.pdf", "") == "contrato.pdf"

    def test_espacios_extremos_se_eliminan(self):
        assert _normalizar_nombre("  contrato  ", ".pdf") == "contrato"

    def test_extension_distinta_no_se_elimina(self):
        assert _normalizar_nombre("contrato.docx", ".pdf") == "contrato.docx"


# ======================================================
# construir_entradas
# ======================================================

class TestConstruirEntradas:
    def test_pareado_basico(self):
        archivos = [_archivo("a.pdf"), _archivo("b.pdf")]
        nombres = ["Nombre A", "Nombre B"]
        entradas = construir_entradas(archivos, nombres)
        assert len(entradas) == 2
        assert entradas[0].nuevo_nombre == "Nombre A"
        assert entradas[1].nuevo_nombre == "Nombre B"

    def test_mas_archivos_que_nombres_rellena_con_vacio(self):
        archivos = [_archivo("a.pdf"), _archivo("b.pdf"), _archivo("c.pdf")]
        nombres = ["Solo uno"]
        entradas = construir_entradas(archivos, nombres)
        assert entradas[1].nuevo_nombre == ""
        assert entradas[2].nuevo_nombre == ""

    def test_extension_duplicada_se_elimina(self):
        archivos = [_archivo("doc.pdf")]
        nombres = ["nuevo_nombre.pdf"]
        entradas = construir_entradas(archivos, nombres)
        assert entradas[0].nuevo_nombre == "nuevo_nombre"

    def test_lista_vacia_devuelve_vacia(self):
        assert construir_entradas([], []) == []

    def test_nombre_final_conserva_extension(self):
        archivos = [_archivo("informe.docx")]
        nombres = ["Informe 2025"]
        entradas = construir_entradas(archivos, nombres)
        assert entradas[0].nombre_final == "Informe 2025.docx"


# ======================================================
# construir_preview — casos sin conflicto
# ======================================================

class TestConstruirPreviewSinConflicto:
    def test_todos_validos(self):
        archivos = [_archivo("a.pdf"), _archivo("b.pdf")]
        nombres = ["Nombre A", "Nombre B"]
        filas, resumen = construir_preview(archivos, nombres)

        assert resumen.total == 2
        assert resumen.validos == 2
        assert resumen.conflictos == 0
        assert all(f.estado == "OK" for f in filas)
        assert all(f.conflicto == "" for f in filas)

    def test_orden_correlativo(self):
        archivos = [_archivo("x.pdf"), _archivo("y.pdf"), _archivo("z.pdf")]
        nombres = ["Uno", "Dos", "Tres"]
        filas, _ = construir_preview(archivos, nombres)
        assert [f.orden for f in filas] == [1, 2, 3]

    def test_nombre_final_correcto(self):
        archivos = [_archivo("original.pdf")]
        nombres = ["nuevo"]
        filas, _ = construir_preview(archivos, nombres)
        assert filas[0].nombre_final == "nuevo.pdf"
        assert filas[0].extension == ".pdf"
        assert filas[0].nombre_actual == "original"
        assert filas[0].nombre_nuevo == "nuevo"

    def test_sin_archivos_devuelve_vacio(self):
        filas, resumen = construir_preview([], [])
        assert filas == []
        assert resumen.total == 0
        assert resumen.validos == 0
        assert resumen.conflictos == 0


# ======================================================
# construir_preview — conflictos: nombre vacío
# ======================================================

class TestConflictoNombreVacio:
    def test_nombre_vacio_es_conflicto(self):
        archivos = [_archivo("doc.pdf")]
        nombres = [""]
        filas, resumen = construir_preview(archivos, nombres)
        assert filas[0].estado == "Conflicto"
        assert "Nombre vacío" in filas[0].conflicto
        assert resumen.conflictos == 1

    def test_nombre_solo_espacios_es_conflicto(self):
        archivos = [_archivo("doc.pdf")]
        nombres = ["   "]
        filas, _ = construir_preview(archivos, nombres)
        assert filas[0].estado == "Conflicto"

    def test_archivo_sin_nombre_correspondiente_es_conflicto(self):
        archivos = [_archivo("a.pdf"), _archivo("b.pdf")]
        nombres = ["Solo uno"]
        filas, resumen = construir_preview(archivos, nombres)
        assert filas[1].estado == "Conflicto"
        assert resumen.conflictos == 1


# ======================================================
# construir_preview — conflictos: caracteres inválidos
# ======================================================

class TestConflictoCaracteresInvalidos:
    def test_barra_invertida_es_conflicto(self):
        archivos = [_archivo("doc.pdf")]
        nombres = ["nombre\\invalido"]
        filas, resumen = construir_preview(archivos, nombres)
        assert filas[0].estado == "Conflicto"
        assert "Caracteres no permitidos" in filas[0].conflicto
        assert resumen.conflictos == 1

    def test_dos_puntos_es_conflicto(self):
        archivos = [_archivo("doc.pdf")]
        nombres = ["nombre:invalido"]
        filas, _ = construir_preview(archivos, nombres)
        assert filas[0].estado == "Conflicto"

    def test_nombre_valido_no_es_conflicto(self):
        archivos = [_archivo("doc.pdf")]
        nombres = ["nombre válido con acentos y espacios"]
        filas, _ = construir_preview(archivos, nombres)
        assert filas[0].estado == "OK"


# ======================================================
# construir_preview — conflictos: duplicados
# ======================================================

class TestConflictoDuplicados:
    def test_dos_nombres_iguales_son_conflicto(self):
        archivos = [_archivo("a.pdf"), _archivo("b.pdf")]
        nombres = ["mismo", "mismo"]
        filas, resumen = construir_preview(archivos, nombres)
        assert filas[0].estado == "Conflicto"
        assert filas[1].estado == "Conflicto"
        assert resumen.conflictos == 2

    def test_duplicado_case_insensitive(self):
        archivos = [_archivo("a.pdf"), _archivo("b.pdf")]
        nombres = ["Nombre", "NOMBRE"]
        filas, resumen = construir_preview(archivos, nombres)
        assert resumen.conflictos == 2

    def test_duplicado_en_tres_archivos(self):
        archivos = [_archivo("a.pdf"), _archivo("b.pdf"), _archivo("c.pdf")]
        nombres = ["dup", "único", "dup"]
        filas, resumen = construir_preview(archivos, nombres)
        assert filas[0].estado == "Conflicto"
        assert filas[1].estado == "OK"
        assert filas[2].estado == "Conflicto"
        assert resumen.conflictos == 2
        assert resumen.validos == 1

    def test_nombre_unico_no_es_conflicto(self):
        archivos = [_archivo("a.pdf"), _archivo("b.pdf")]
        nombres = ["primero", "segundo"]
        filas, resumen = construir_preview(archivos, nombres)
        assert resumen.conflictos == 0


# ======================================================
# construir_preview — múltiples errores en misma fila
# ======================================================

class TestMultiplesErrores:
    def test_vacio_y_duplicado_acumulan_mensajes(self):
        """
        Dos filas vacías: reciben conflicto por 'Nombre vacío' y 'Duplicado'.
        """
        archivos = [_archivo("a.pdf"), _archivo("b.pdf")]
        nombres = ["", ""]
        filas, resumen = construir_preview(archivos, nombres)
        assert resumen.conflictos == 2
        # Ambas filas tienen al menos el error de nombre vacío
        assert "Nombre vacío" in filas[0].conflicto
        assert "Nombre vacío" in filas[1].conflicto


# ======================================================
# Tests de sesión — nuevos métodos nombres/establecer_nombres
# ======================================================

class TestSesionNombres:
    def test_nombres_inicial_vacio(self):
        from scripts.files.session import SesionRenombrado
        sesion = SesionRenombrado()
        assert sesion.nombres() == []

    def test_establecer_nombres(self):
        from scripts.files.session import SesionRenombrado
        sesion = SesionRenombrado()
        sesion.establecer_nombres(["alfa", "beta"])
        assert sesion.nombres() == ["alfa", "beta"]

    def test_establecer_nombres_sobreescribe(self):
        from scripts.files.session import SesionRenombrado
        sesion = SesionRenombrado()
        sesion.establecer_nombres(["primero"])
        sesion.establecer_nombres(["nuevo"])
        assert sesion.nombres() == ["nuevo"]

    def test_nombres_devuelve_copia(self):
        from scripts.files.session import SesionRenombrado
        sesion = SesionRenombrado()
        sesion.establecer_nombres(["x"])
        lista = sesion.nombres()
        lista.append("extra")
        assert sesion.nombres() == ["x"]
