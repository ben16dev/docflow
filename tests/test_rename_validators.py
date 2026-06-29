"""
Tests de los validadores para "Renombrar archivos".

Cubren cada función validadora de forma independiente y la
función de validación completa (validar_operacion).
"""

from pathlib import Path

import pytest

from scripts.common.rename_models import (
    ArchivoEntrada,
    EntradaRenombrado,
    ModoRenombrado,
    OperacionRenombrado,
)
from scripts.common.rename_validators import (
    validar_archivos_existen,
    validar_destino_libre,
    validar_nombres_no_vacios,
    validar_nombres_unicos,
    validar_nombres_validos,
    validar_operacion,
)


# ======================================================
# HELPERS
# ======================================================

def _archivo(tmp_path: Path, nombre: str, crear: bool = True) -> ArchivoEntrada:
    ruta = tmp_path / nombre
    if crear:
        ruta.touch()
    return ArchivoEntrada(ruta_original=ruta)


def _entrada(tmp_path: Path, nombre_orig: str, nuevo: str, crear: bool = True) -> EntradaRenombrado:
    return EntradaRenombrado(
        archivo=_archivo(tmp_path, nombre_orig, crear=crear),
        nuevo_nombre=nuevo,
    )


# ======================================================
# validar_archivos_existen
# ======================================================

class TestValidarArchivosExisten:

    def test_sin_errores_si_todos_existen(self, tmp_path):
        entradas = [
            _entrada(tmp_path, "a.pdf", "nuevo_a"),
            _entrada(tmp_path, "b.pdf", "nuevo_b"),
        ]
        assert validar_archivos_existen(entradas) == []

    def test_error_si_algun_archivo_no_existe(self, tmp_path):
        entradas = [
            _entrada(tmp_path, "existe.pdf", "ok"),
            _entrada(tmp_path, "no_existe.pdf", "falla", crear=False),
        ]
        errores = validar_archivos_existen(entradas)
        assert len(errores) == 1
        assert "no_existe.pdf" in errores[0]

    def test_lista_vacia_es_valida(self):
        assert validar_archivos_existen([]) == []


# ======================================================
# validar_nombres_no_vacios
# ======================================================

class TestValidarNombresNoVacios:

    def test_sin_errores_si_todos_tienen_nombre(self, tmp_path):
        entradas = [_entrada(tmp_path, "f.pdf", "nombre_valido")]
        assert validar_nombres_no_vacios(entradas) == []

    def test_error_si_nombre_vacio(self, tmp_path):
        entradas = [_entrada(tmp_path, "f.pdf", "")]
        errores = validar_nombres_no_vacios(entradas)
        assert len(errores) == 1

    def test_error_si_nombre_solo_espacios(self, tmp_path):
        entradas = [_entrada(tmp_path, "f.pdf", "   ")]
        errores = validar_nombres_no_vacios(entradas)
        assert len(errores) == 1

    def test_multiples_vacios(self, tmp_path):
        entradas = [
            _entrada(tmp_path, "a.pdf", ""),
            _entrada(tmp_path, "b.pdf", "valido"),
            _entrada(tmp_path, "c.pdf", ""),
        ]
        errores = validar_nombres_no_vacios(entradas)
        assert len(errores) == 2


# ======================================================
# validar_nombres_validos
# ======================================================

class TestValidarNombresValidos:

    def test_nombre_limpio_es_valido(self, tmp_path):
        entradas = [_entrada(tmp_path, "f.pdf", "Informe Final 2024")]
        assert validar_nombres_validos(entradas) == []

    def test_nombre_con_barra_es_invalido(self, tmp_path):
        entradas = [_entrada(tmp_path, "f.pdf", "informe/ilegal")]
        errores = validar_nombres_validos(entradas)
        assert len(errores) == 1

    def test_nombre_con_asterisco_es_invalido(self, tmp_path):
        entradas = [_entrada(tmp_path, "f.pdf", "doc*ilegal")]
        errores = validar_nombres_validos(entradas)
        assert len(errores) == 1

    def test_nombre_con_comillas_angulares_es_invalido(self, tmp_path):
        entradas = [_entrada(tmp_path, "f.pdf", "doc<mal>")]
        errores = validar_nombres_validos(entradas)
        assert len(errores) == 1

    def test_nombre_con_acentos_es_valido(self, tmp_path):
        entradas = [_entrada(tmp_path, "f.pdf", "Ánálisis Técnico")]
        assert validar_nombres_validos(entradas) == []


# ======================================================
# validar_nombres_unicos
# ======================================================

class TestValidarNombresUnicos:

    def test_sin_duplicados_es_valido(self, tmp_path):
        entradas = [
            _entrada(tmp_path, "a.pdf", "primero"),
            _entrada(tmp_path, "b.pdf", "segundo"),
        ]
        assert validar_nombres_unicos(entradas) == []

    def test_detecta_duplicado_exacto(self, tmp_path):
        entradas = [
            _entrada(tmp_path, "a.pdf", "mismo"),
            _entrada(tmp_path, "b.pdf", "mismo"),
        ]
        errores = validar_nombres_unicos(entradas)
        assert len(errores) == 1

    def test_duplicado_es_case_insensitive(self, tmp_path):
        entradas = [
            _entrada(tmp_path, "a.pdf", "Documento"),
            _entrada(tmp_path, "b.pdf", "documento"),
        ]
        errores = validar_nombres_unicos(entradas)
        assert len(errores) == 1

    def test_diferente_extension_no_es_duplicado(self, tmp_path):
        """Mismo stem pero extensiones distintas no genera conflicto."""
        af_pdf = _archivo(tmp_path, "x.pdf")
        af_txt = _archivo(tmp_path, "x.txt")
        entradas = [
            EntradaRenombrado(archivo=af_pdf, nuevo_nombre="salida"),
            EntradaRenombrado(archivo=af_txt, nuevo_nombre="salida"),
        ]
        # "salida.pdf" y "salida.txt" son nombres finales distintos
        errores = validar_nombres_unicos(entradas)
        assert errores == []


# ======================================================
# validar_destino_libre
# ======================================================

class TestValidarDestinoLibre:

    def test_sin_conflictos_si_destino_vacio(self, tmp_path):
        carpeta_destino = tmp_path / "salida"
        carpeta_destino.mkdir()
        entradas = [_entrada(tmp_path, "f.pdf", "nuevo")]
        assert validar_destino_libre(entradas, carpeta_destino) == []

    def test_error_si_archivo_ya_existe_en_destino(self, tmp_path):
        carpeta_destino = tmp_path / "salida"
        carpeta_destino.mkdir()

        # Simular archivo ya existente en destino
        (carpeta_destino / "nuevo.pdf").touch()

        entradas = [_entrada(tmp_path, "f.pdf", "nuevo")]
        errores = validar_destino_libre(entradas, carpeta_destino)
        assert len(errores) == 1
        assert "nuevo.pdf" in errores[0]

    def test_sin_error_si_nombre_diferente_al_existente(self, tmp_path):
        carpeta_destino = tmp_path / "salida"
        carpeta_destino.mkdir()
        (carpeta_destino / "otro.pdf").touch()

        entradas = [_entrada(tmp_path, "f.pdf", "distinto")]
        assert validar_destino_libre(entradas, carpeta_destino) == []


# ======================================================
# validar_operacion (integración)
# ======================================================

class TestValidarOperacion:

    def test_operacion_valida_completa(self, tmp_path):
        carpeta_destino = tmp_path / "salida"
        carpeta_destino.mkdir()

        entradas = [
            _entrada(tmp_path, "a.pdf", "Informe A"),
            _entrada(tmp_path, "b.pdf", "Informe B"),
        ]
        op = OperacionRenombrado(
            entradas=entradas,
            carpeta_destino=carpeta_destino,
        )
        resultado = validar_operacion(op)

        assert resultado.valida is True
        assert resultado.errores == []

    def test_operacion_invalida_archivo_inexistente(self, tmp_path):
        carpeta_destino = tmp_path / "salida"
        carpeta_destino.mkdir()

        entradas = [_entrada(tmp_path, "fantasma.pdf", "nombre", crear=False)]
        op = OperacionRenombrado(
            entradas=entradas,
            carpeta_destino=carpeta_destino,
        )
        resultado = validar_operacion(op)

        assert resultado.valida is False
        assert any("fantasma.pdf" in e for e in resultado.errores)

    def test_operacion_invalida_nombre_duplicado(self, tmp_path):
        carpeta_destino = tmp_path / "salida"
        carpeta_destino.mkdir()

        entradas = [
            _entrada(tmp_path, "a.pdf", "mismo"),
            _entrada(tmp_path, "b.pdf", "mismo"),
        ]
        op = OperacionRenombrado(
            entradas=entradas,
            carpeta_destino=carpeta_destino,
        )
        resultado = validar_operacion(op)

        assert resultado.valida is False

    def test_operacion_invalida_conflicto_destino(self, tmp_path):
        carpeta_destino = tmp_path / "salida"
        carpeta_destino.mkdir()
        (carpeta_destino / "nuevo.pdf").touch()

        entradas = [_entrada(tmp_path, "a.pdf", "nuevo")]
        op = OperacionRenombrado(
            entradas=entradas,
            carpeta_destino=carpeta_destino,
        )
        resultado = validar_operacion(op)

        assert resultado.valida is False

    def test_operacion_vacia_es_valida(self, tmp_path):
        carpeta_destino = tmp_path / "salida"
        carpeta_destino.mkdir()

        op = OperacionRenombrado(entradas=[], carpeta_destino=carpeta_destino)
        resultado = validar_operacion(op)

        assert resultado.valida is True
