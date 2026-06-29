"""
Tests de los modelos de dominio para "Renombrar archivos".

Cubren los contratos básicos de ArchivoEntrada, EntradaRenombrado
y OperacionRenombrado sin necesitar disco ni UI.
"""

from pathlib import Path

import pytest

from scripts.common.rename_models import (
    ArchivoEntrada,
    EntradaRenombrado,
    ModoRenombrado,
    OperacionRenombrado,
    ResultadoValidacion,
)


# ======================================================
# ArchivoEntrada
# ======================================================

class TestArchivoEntrada:

    def test_propiedades_basicas(self, tmp_path):
        archivo = tmp_path / "informe_2024.pdf"
        archivo.touch()
        entrada = ArchivoEntrada(ruta_original=archivo)

        assert entrada.nombre_original == "informe_2024"
        assert entrada.extension == ".pdf"
        assert entrada.nombre_completo == "informe_2024.pdf"

    def test_acepta_string_como_ruta(self, tmp_path):
        archivo = tmp_path / "documento.docx"
        archivo.touch()
        entrada = ArchivoEntrada(ruta_original=str(archivo))

        assert isinstance(entrada.ruta_original, Path)
        assert entrada.extension == ".docx"

    def test_existe_devuelve_true_si_archivo_en_disco(self, tmp_path):
        archivo = tmp_path / "real.txt"
        archivo.touch()
        entrada = ArchivoEntrada(ruta_original=archivo)

        assert entrada.existe() is True

    def test_existe_devuelve_false_si_archivo_no_existe(self, tmp_path):
        entrada = ArchivoEntrada(ruta_original=tmp_path / "fantasma.pdf")

        assert entrada.existe() is False

    def test_es_inmutable(self, tmp_path):
        archivo = tmp_path / "test.pdf"
        entrada = ArchivoEntrada(ruta_original=archivo)

        with pytest.raises((AttributeError, TypeError)):
            entrada.ruta_original = tmp_path / "otro.pdf"

    def test_extension_sin_punto_no_tiene_extension(self, tmp_path):
        archivo = tmp_path / "sinext"
        archivo.touch()
        entrada = ArchivoEntrada(ruta_original=archivo)

        assert entrada.extension == ""
        assert entrada.nombre_original == "sinext"


# ======================================================
# EntradaRenombrado
# ======================================================

class TestEntradaRenombrado:

    def _make_archivo(self, tmp_path, nombre):
        archivo = tmp_path / nombre
        archivo.touch()
        return ArchivoEntrada(ruta_original=archivo)

    def test_nombre_final_conserva_extension(self, tmp_path):
        archivo = self._make_archivo(tmp_path, "acta_01.pdf")
        entrada = EntradaRenombrado(archivo=archivo, nuevo_nombre="Acta Reunión Enero")

        assert entrada.nombre_final == "Acta Reunión Enero.pdf"

    def test_tiene_cambio_true_cuando_nombre_difiere(self, tmp_path):
        archivo = self._make_archivo(tmp_path, "doc_viejo.txt")
        entrada = EntradaRenombrado(archivo=archivo, nuevo_nombre="doc_nuevo")

        assert entrada.tiene_cambio() is True

    def test_tiene_cambio_false_cuando_nombre_es_igual(self, tmp_path):
        archivo = self._make_archivo(tmp_path, "documento.txt")
        entrada = EntradaRenombrado(archivo=archivo, nuevo_nombre="documento")

        assert entrada.tiene_cambio() is False

    def test_nombre_final_sin_extension(self, tmp_path):
        archivo = tmp_path / "sinext"
        archivo.touch()
        af = ArchivoEntrada(ruta_original=archivo)
        entrada = EntradaRenombrado(archivo=af, nuevo_nombre="nuevo_sinext")

        assert entrada.nombre_final == "nuevo_sinext"


# ======================================================
# OperacionRenombrado
# ======================================================

class TestOperacionRenombrado:

    def _make_entrada(self, tmp_path, nombre_orig, nombre_nuevo):
        archivo = tmp_path / nombre_orig
        archivo.touch()
        af = ArchivoEntrada(ruta_original=archivo)
        return EntradaRenombrado(archivo=af, nuevo_nombre=nombre_nuevo)

    def test_total_devuelve_numero_de_entradas(self, tmp_path):
        entradas = [
            self._make_entrada(tmp_path, f"file_{i}.pdf", f"nuevo_{i}")
            for i in range(4)
        ]
        op = OperacionRenombrado(entradas=entradas, carpeta_destino=tmp_path)

        assert op.total() == 4

    def test_con_cambios_filtra_sin_cambio(self, tmp_path):
        con_cambio = self._make_entrada(tmp_path, "a.pdf", "nuevo_a")
        sin_cambio = self._make_entrada(tmp_path, "b.pdf", "b")

        op = OperacionRenombrado(
            entradas=[con_cambio, sin_cambio],
            carpeta_destino=tmp_path,
        )

        assert len(op.con_cambios()) == 1
        assert op.con_cambios()[0] is con_cambio

    def test_modo_por_defecto_es_copiar(self, tmp_path):
        op = OperacionRenombrado(entradas=[], carpeta_destino=tmp_path)

        assert op.modo == ModoRenombrado.COPIAR_A_CARPETA

    def test_lista_vacia_por_defecto(self):
        op = OperacionRenombrado(carpeta_destino=Path("."))

        assert op.entradas == []
        assert op.total() == 0


# ======================================================
# ResultadoValidacion
# ======================================================

class TestResultadoValidacion:

    def test_ok_es_valido_y_sin_errores(self):
        resultado = ResultadoValidacion.ok()

        assert resultado.valida is True
        assert resultado.errores == []

    def test_con_errores_es_invalido(self):
        resultado = ResultadoValidacion.con_errores(["Error A", "Error B"])

        assert resultado.valida is False
        assert len(resultado.errores) == 2
        assert "Error A" in resultado.errores

    def test_resultado_directo_valido(self):
        resultado = ResultadoValidacion(valida=True)

        assert resultado.errores == []
