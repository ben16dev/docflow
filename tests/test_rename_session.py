"""
Tests de SesionRenombrado.

Cubren el ciclo completo de gestión de estado: añadir, eliminar,
reordenar, limpiar y consultar, sin dependencias de UI.
"""

from pathlib import Path

import pytest

from scripts.files.session import SesionRenombrado


# ======================================================
# FIXTURES
# ======================================================

@pytest.fixture
def sesion():
    return SesionRenombrado()


def _crear_archivos(tmp_path: Path, *nombres: str) -> list[Path]:
    """Crea archivos vacíos en tmp_path y devuelve sus rutas."""
    rutas = []
    for nombre in nombres:
        ruta = tmp_path / nombre
        ruta.touch()
        rutas.append(ruta)
    return rutas


# ======================================================
# ESTADO INICIAL
# ======================================================

class TestEstadoInicial:

    def test_sesion_nueva_esta_vacia(self, sesion):
        assert sesion.esta_vacia() is True

    def test_sesion_nueva_tiene_cero_archivos(self, sesion):
        assert sesion.total() == 0

    def test_archivos_devuelve_lista_vacia(self, sesion):
        assert sesion.archivos() == []


# ======================================================
# AGREGAR
# ======================================================

class TestAgregar:

    def test_agregar_archivo_valido(self, sesion, tmp_path):
        rutas = _crear_archivos(tmp_path, "a.pdf")
        n = sesion.agregar(rutas)

        assert n == 1
        assert sesion.total() == 1

    def test_agregar_multiples_archivos(self, sesion, tmp_path):
        rutas = _crear_archivos(tmp_path, "a.pdf", "b.docx", "c.txt")
        n = sesion.agregar(rutas)

        assert n == 3
        assert sesion.total() == 3

    def test_agregar_ignora_duplicados(self, sesion, tmp_path):
        rutas = _crear_archivos(tmp_path, "a.pdf")
        sesion.agregar(rutas)
        n = sesion.agregar(rutas)  # segunda vez

        assert n == 0
        assert sesion.total() == 1

    def test_agregar_detecta_duplicado_por_ruta_resuelta(self, sesion, tmp_path):
        archivo = tmp_path / "a.pdf"
        archivo.touch()
        sesion.agregar([archivo])
        # Misma ruta, representación diferente (relativa vs absoluta no aplica
        # aquí, pero sí un duplicado directo)
        n = sesion.agregar([archivo])

        assert n == 0

    def test_agregar_ignora_directorios(self, sesion, tmp_path):
        directorio = tmp_path / "subcarpeta"
        directorio.mkdir()
        n = sesion.agregar([directorio])

        assert n == 0
        assert sesion.esta_vacia()

    def test_agregar_ignora_ruta_inexistente(self, sesion, tmp_path):
        n = sesion.agregar([tmp_path / "no_existe.pdf"])

        assert n == 0
        assert sesion.esta_vacia()

    def test_agregar_lista_vacia(self, sesion):
        n = sesion.agregar([])
        assert n == 0

    def test_agregar_mezcla_validos_e_invalidos(self, sesion, tmp_path):
        valido = tmp_path / "real.pdf"
        valido.touch()
        n = sesion.agregar([valido, tmp_path / "fantasma.pdf"])

        assert n == 1
        assert sesion.total() == 1

    def test_agregar_preserva_orden_de_insercion(self, sesion, tmp_path):
        rutas = _crear_archivos(tmp_path, "primero.pdf", "segundo.pdf", "tercero.txt")
        sesion.agregar(rutas)

        nombres = [a.nombre_completo for a in sesion.archivos()]
        assert nombres == ["primero.pdf", "segundo.pdf", "tercero.txt"]


# ======================================================
# ELIMINAR
# ======================================================

class TestEliminar:

    def test_eliminar_primer_elemento(self, sesion, tmp_path):
        rutas = _crear_archivos(tmp_path, "a.pdf", "b.pdf", "c.pdf")
        sesion.agregar(rutas)
        sesion.eliminar(0)

        nombres = [a.nombre_completo for a in sesion.archivos()]
        assert nombres == ["b.pdf", "c.pdf"]

    def test_eliminar_elemento_intermedio(self, sesion, tmp_path):
        rutas = _crear_archivos(tmp_path, "a.pdf", "b.pdf", "c.pdf")
        sesion.agregar(rutas)
        sesion.eliminar(1)

        nombres = [a.nombre_completo for a in sesion.archivos()]
        assert nombres == ["a.pdf", "c.pdf"]

    def test_eliminar_ultimo_elemento(self, sesion, tmp_path):
        rutas = _crear_archivos(tmp_path, "a.pdf", "b.pdf")
        sesion.agregar(rutas)
        sesion.eliminar(1)

        assert sesion.total() == 1
        assert sesion.archivos()[0].nombre_completo == "a.pdf"

    def test_eliminar_indice_fuera_de_rango_no_falla(self, sesion, tmp_path):
        rutas = _crear_archivos(tmp_path, "a.pdf")
        sesion.agregar(rutas)
        sesion.eliminar(99)

        assert sesion.total() == 1

    def test_eliminar_indice_negativo_no_falla(self, sesion):
        sesion.eliminar(-1)
        assert sesion.esta_vacia()

    def test_eliminar_en_sesion_vacia_no_falla(self, sesion):
        sesion.eliminar(0)
        assert sesion.esta_vacia()


# ======================================================
# LIMPIAR
# ======================================================

class TestLimpiar:

    def test_limpiar_vacia_la_lista(self, sesion, tmp_path):
        rutas = _crear_archivos(tmp_path, "a.pdf", "b.pdf")
        sesion.agregar(rutas)
        sesion.limpiar()

        assert sesion.esta_vacia()

    def test_limpiar_sesion_vacia_no_falla(self, sesion):
        sesion.limpiar()
        assert sesion.esta_vacia()

    def test_se_puede_agregar_tras_limpiar(self, sesion, tmp_path):
        rutas = _crear_archivos(tmp_path, "a.pdf")
        sesion.agregar(rutas)
        sesion.limpiar()
        sesion.agregar(rutas)

        assert sesion.total() == 1


# ======================================================
# SUBIR
# ======================================================

class TestSubir:

    def test_subir_mueve_elemento_hacia_arriba(self, sesion, tmp_path):
        rutas = _crear_archivos(tmp_path, "a.pdf", "b.pdf", "c.pdf")
        sesion.agregar(rutas)
        sesion.subir(1)  # sube "b.pdf" a posición 0

        nombres = [a.nombre_completo for a in sesion.archivos()]
        assert nombres == ["b.pdf", "a.pdf", "c.pdf"]

    def test_subir_primer_elemento_no_hace_nada(self, sesion, tmp_path):
        rutas = _crear_archivos(tmp_path, "a.pdf", "b.pdf")
        sesion.agregar(rutas)
        sesion.subir(0)

        nombres = [a.nombre_completo for a in sesion.archivos()]
        assert nombres == ["a.pdf", "b.pdf"]

    def test_subir_ultimo_elemento(self, sesion, tmp_path):
        rutas = _crear_archivos(tmp_path, "a.pdf", "b.pdf", "c.pdf")
        sesion.agregar(rutas)
        sesion.subir(2)

        nombres = [a.nombre_completo for a in sesion.archivos()]
        assert nombres == ["a.pdf", "c.pdf", "b.pdf"]

    def test_subir_indice_fuera_de_rango_no_falla(self, sesion, tmp_path):
        rutas = _crear_archivos(tmp_path, "a.pdf")
        sesion.agregar(rutas)
        sesion.subir(99)

        assert sesion.total() == 1

    def test_subir_en_sesion_vacia_no_falla(self, sesion):
        sesion.subir(0)


# ======================================================
# BAJAR
# ======================================================

class TestBajar:

    def test_bajar_mueve_elemento_hacia_abajo(self, sesion, tmp_path):
        rutas = _crear_archivos(tmp_path, "a.pdf", "b.pdf", "c.pdf")
        sesion.agregar(rutas)
        sesion.bajar(0)  # baja "a.pdf" a posición 1

        nombres = [a.nombre_completo for a in sesion.archivos()]
        assert nombres == ["b.pdf", "a.pdf", "c.pdf"]

    def test_bajar_ultimo_elemento_no_hace_nada(self, sesion, tmp_path):
        rutas = _crear_archivos(tmp_path, "a.pdf", "b.pdf")
        sesion.agregar(rutas)
        sesion.bajar(1)

        nombres = [a.nombre_completo for a in sesion.archivos()]
        assert nombres == ["a.pdf", "b.pdf"]

    def test_bajar_primer_elemento(self, sesion, tmp_path):
        rutas = _crear_archivos(tmp_path, "a.pdf", "b.pdf", "c.pdf")
        sesion.agregar(rutas)
        sesion.bajar(0)

        nombres = [a.nombre_completo for a in sesion.archivos()]
        assert nombres == ["b.pdf", "a.pdf", "c.pdf"]

    def test_bajar_indice_fuera_de_rango_no_falla(self, sesion, tmp_path):
        rutas = _crear_archivos(tmp_path, "a.pdf")
        sesion.agregar(rutas)
        sesion.bajar(99)

        assert sesion.total() == 1

    def test_bajar_en_sesion_vacia_no_falla(self, sesion):
        sesion.bajar(0)


# ======================================================
# CONTIENE
# ======================================================

class TestContiene:

    def test_contiene_true_si_archivo_en_sesion(self, sesion, tmp_path):
        rutas = _crear_archivos(tmp_path, "a.pdf")
        sesion.agregar(rutas)

        assert sesion.contiene(rutas[0]) is True

    def test_contiene_false_si_archivo_no_en_sesion(self, sesion, tmp_path):
        rutas = _crear_archivos(tmp_path, "a.pdf", "b.pdf")
        sesion.agregar(rutas[:1])  # solo "a.pdf"

        assert sesion.contiene(rutas[1]) is False

    def test_contiene_false_en_sesion_vacia(self, sesion, tmp_path):
        ruta = tmp_path / "cualquiera.pdf"
        assert sesion.contiene(ruta) is False


# ======================================================
# ARCHIVOS (copia defensiva)
# ======================================================

class TestArchivos:

    def test_archivos_devuelve_copia(self, sesion, tmp_path):
        rutas = _crear_archivos(tmp_path, "a.pdf")
        sesion.agregar(rutas)

        lista = sesion.archivos()
        lista.clear()  # modificar la copia no debe afectar la sesión

        assert sesion.total() == 1

    def test_archivos_refleja_estado_actual(self, sesion, tmp_path):
        rutas = _crear_archivos(tmp_path, "a.pdf", "b.pdf")
        sesion.agregar(rutas)
        sesion.eliminar(0)

        nombres = [a.nombre_completo for a in sesion.archivos()]
        assert nombres == ["b.pdf"]
