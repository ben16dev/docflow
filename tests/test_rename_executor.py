"""
Tests de la ejecución real de "Renombrar archivos" (Sprint 5).

Cubren:
  - scripts/files/rename_executor.py (función pura ejecutar_renombrado).
  - scripts/files/renombrar_archivos.py::run() (adaptación a build_result).

No incluyen tests de interfaz Tk: la pestaña se limita a delegar y no
contiene lógica propia que valga la pena testear aquí.
"""

from __future__ import annotations

import functools
import shutil
from pathlib import Path

import pytest

from scripts.common.rename_models import (
    ArchivoEntrada,
    EntradaRenombrado,
    OperacionRenombrado,
    ResultadoValidacion,
)
from scripts.files import renombrar_archivos
from scripts.files.rename_executor import ejecutar_renombrado
from scripts.files.session import SesionRenombrado


# ======================================================
# HELPERS
# ======================================================

def _entrada(carpeta: Path, nombre_original: str, nuevo_nombre: str,
             contenido: bytes = b"contenido", crear: bool = True) -> EntradaRenombrado:
    origen = carpeta / nombre_original
    if crear:
        origen.write_bytes(contenido)
    return EntradaRenombrado(
        archivo=ArchivoEntrada(ruta_original=origen),
        nuevo_nombre=nuevo_nombre,
    )


def _sin_validacion_previa(monkeypatch) -> None:
    """
    Sustituye validar_operacion() por un "ok" incondicional, para poder
    testear en aislamiento las comprobaciones defensivas que el propio
    bucle de ejecución realiza en tiempo real (colisión de última hora,
    archivo desaparecido), simulando que la operación fue válida en el
    momento de la previsualización pero el disco cambió después.
    """
    monkeypatch.setattr(
        "scripts.files.rename_executor.validar_operacion",
        lambda _operacion: ResultadoValidacion.ok(),
    )


# ======================================================
# COPIA BÁSICA
# ======================================================

class TestCopiaBasica:

    def test_copia_archivo_con_exito(self, tmp_path):
        origen_dir = tmp_path / "origen"
        origen_dir.mkdir()
        destino_dir = tmp_path / "destino"

        entrada = _entrada(origen_dir, "informe.pdf", "Informe Final", contenido=b"contenido pdf")
        operacion = OperacionRenombrado(entradas=[entrada], carpeta_destino=destino_dir)

        resultado = ejecutar_renombrado(operacion)

        assert resultado.copiados == 1
        assert resultado.errores == 0
        assert resultado.omitidos == 0
        assert resultado.cancelado is False

        destino_final = destino_dir / "Informe Final.pdf"
        assert destino_final.exists()
        assert destino_final.read_bytes() == b"contenido pdf"

        # El original nunca se modifica ni se borra.
        assert entrada.archivo.ruta_original.exists()
        assert entrada.archivo.ruta_original.read_bytes() == b"contenido pdf"

    def test_conserva_extension_original(self, tmp_path):
        origen_dir = tmp_path / "origen"
        origen_dir.mkdir()
        destino_dir = tmp_path / "destino"

        entrada = _entrada(origen_dir, "documento.DOCX", "nuevo_nombre")
        operacion = OperacionRenombrado(entradas=[entrada], carpeta_destino=destino_dir)

        ejecutar_renombrado(operacion)

        assert (destino_dir / "nuevo_nombre.DOCX").exists()

    def test_no_deja_temporales_tras_ejecucion_exitosa(self, tmp_path):
        origen_dir = tmp_path / "origen"
        origen_dir.mkdir()
        destino_dir = tmp_path / "destino"

        entrada = _entrada(origen_dir, "a.pdf", "nuevo")
        operacion = OperacionRenombrado(entradas=[entrada], carpeta_destino=destino_dir)

        ejecutar_renombrado(operacion)

        nombres_destino = [p.name for p in destino_dir.iterdir()]
        assert nombres_destino == ["nuevo.pdf"]

    def test_progress_se_llama_por_cada_archivo_procesado(self, tmp_path):
        origen_dir = tmp_path / "origen"
        origen_dir.mkdir()
        destino_dir = tmp_path / "destino"

        entradas = [_entrada(origen_dir, f"f{i}.pdf", f"nuevo_{i}") for i in range(3)]
        operacion = OperacionRenombrado(entradas=entradas, carpeta_destino=destino_dir)

        llamadas = []
        ejecutar_renombrado(operacion, progress=lambda actual, total: llamadas.append((actual, total)))

        assert llamadas == [(1, 3), (2, 3), (3, 3)]

    def test_crea_la_carpeta_destino_si_no_existe(self, tmp_path):
        origen_dir = tmp_path / "origen"
        origen_dir.mkdir()
        destino_dir = tmp_path / "no_existe_todavia"

        entrada = _entrada(origen_dir, "a.pdf", "nuevo")
        operacion = OperacionRenombrado(entradas=[entrada], carpeta_destino=destino_dir)

        resultado = ejecutar_renombrado(operacion)

        assert destino_dir.is_dir()
        assert resultado.copiados == 1


# ======================================================
# VALIDACIÓN PREVIA (última comprobación antes de tocar disco)
# ======================================================

class TestValidacionPrevia:

    def test_operacion_invalida_aborta_con_runtime_error(self, tmp_path):
        entrada = _entrada(tmp_path, "fantasma.pdf", "nuevo", crear=False)
        operacion = OperacionRenombrado(entradas=[entrada], carpeta_destino=tmp_path / "salida")

        with pytest.raises(RuntimeError):
            ejecutar_renombrado(operacion)

    def test_operacion_invalida_no_toca_disco(self, tmp_path):
        destino_dir = tmp_path / "salida"
        entrada = _entrada(tmp_path, "fantasma.pdf", "nuevo", crear=False)
        operacion = OperacionRenombrado(entradas=[entrada], carpeta_destino=destino_dir)

        with pytest.raises(RuntimeError):
            ejecutar_renombrado(operacion)

        assert not destino_dir.exists()


# ======================================================
# COLISIÓN DE ÚLTIMA HORA
# ======================================================

class TestColisionDeUltimaHora:

    def test_colision_se_registra_como_incidencia_y_continua(self, tmp_path, monkeypatch):
        origen_dir = tmp_path / "origen"
        origen_dir.mkdir()
        destino_dir = tmp_path / "destino"
        destino_dir.mkdir()

        entrada_colision = _entrada(origen_dir, "a.pdf", "nuevo_a")
        entrada_ok = _entrada(origen_dir, "b.pdf", "nuevo_b")
        operacion = OperacionRenombrado(
            entradas=[entrada_colision, entrada_ok],
            carpeta_destino=destino_dir,
        )

        # La operación fue válida en la previsualización; simulamos que,
        # justo después, algo externo crea el archivo de destino antes de
        # que el ejecutor llegue a copiarlo.
        _sin_validacion_previa(monkeypatch)
        (destino_dir / "nuevo_a.pdf").write_bytes(b"externo")

        resultado = ejecutar_renombrado(operacion)

        assert resultado.errores == 1
        assert resultado.copiados == 1
        assert resultado.total == 2
        assert any("Colisión" in inc for inc in resultado.incidencias)

        # El archivo ya existente en destino nunca se sobrescribe.
        assert (destino_dir / "nuevo_a.pdf").read_bytes() == b"externo"
        assert (destino_dir / "nuevo_b.pdf").exists()


# ======================================================
# ARCHIVO DESAPARECIDO
# ======================================================

class TestArchivoDesaparecido:

    def test_archivo_desaparecido_se_omite_y_continua(self, tmp_path, monkeypatch):
        origen_dir = tmp_path / "origen"
        origen_dir.mkdir()
        destino_dir = tmp_path / "destino"

        entrada_fantasma = _entrada(origen_dir, "a.pdf", "nuevo_a")
        entrada_ok = _entrada(origen_dir, "b.pdf", "nuevo_b")
        operacion = OperacionRenombrado(
            entradas=[entrada_fantasma, entrada_ok],
            carpeta_destino=destino_dir,
        )

        _sin_validacion_previa(monkeypatch)
        # El archivo desaparece (p. ej. otro proceso lo borra) después de
        # haber pasado la previsualización.
        entrada_fantasma.archivo.ruta_original.unlink()

        resultado = ejecutar_renombrado(operacion)

        assert resultado.omitidos == 1
        assert resultado.copiados == 1
        assert resultado.errores == 0
        assert any("ya no existe" in inc for inc in resultado.incidencias)
        assert (destino_dir / "nuevo_b.pdf").exists()


# ======================================================
# PERMISOS INSUFICIENTES
# ======================================================

class TestPermisosInsuficientes:

    def test_permiso_denegado_se_registra_como_error_y_continua(self, tmp_path, monkeypatch):
        origen_dir = tmp_path / "origen"
        origen_dir.mkdir()
        destino_dir = tmp_path / "destino"

        entrada_sin_permiso = _entrada(origen_dir, "a.pdf", "nuevo_a")
        entrada_ok = _entrada(origen_dir, "b.pdf", "nuevo_b")
        operacion = OperacionRenombrado(
            entradas=[entrada_sin_permiso, entrada_ok],
            carpeta_destino=destino_dir,
        )

        copy2_original = shutil.copy2

        def copy2_falla_para_a(origen, destino, *args, **kwargs):
            if Path(origen).name == "a.pdf":
                raise PermissionError("Permiso denegado")
            return copy2_original(origen, destino, *args, **kwargs)

        monkeypatch.setattr("scripts.files.rename_executor.shutil.copy2", copy2_falla_para_a)

        resultado = ejecutar_renombrado(operacion)

        assert resultado.errores == 1
        assert resultado.copiados == 1
        assert any("Permisos insuficientes" in inc for inc in resultado.incidencias)
        assert not (destino_dir / "nuevo_a.pdf").exists()
        assert (destino_dir / "nuevo_b.pdf").exists()


# ======================================================
# CANCELACIÓN
# ======================================================

class TestCancelacion:

    def test_cancelacion_cooperativa_detiene_el_resto_del_lote(self, tmp_path):
        origen_dir = tmp_path / "origen"
        origen_dir.mkdir()
        destino_dir = tmp_path / "destino"

        entradas = [_entrada(origen_dir, f"f{i}.pdf", f"nuevo_{i}") for i in range(3)]
        operacion = OperacionRenombrado(entradas=entradas, carpeta_destino=destino_dir)

        estado = {"procesados": 0}

        def is_cancelled():
            return estado["procesados"] >= 1

        def progress(actual, total):
            estado["procesados"] = actual

        resultado = ejecutar_renombrado(operacion, progress=progress, is_cancelled=is_cancelled)

        assert resultado.cancelado is True
        assert resultado.copiados == 1
        assert resultado.total == 3
        assert (destino_dir / "nuevo_0.pdf").exists()
        assert not (destino_dir / "nuevo_1.pdf").exists()
        assert not (destino_dir / "nuevo_2.pdf").exists()

    def test_cancelacion_inmediata_no_procesa_ningun_archivo(self, tmp_path):
        origen_dir = tmp_path / "origen"
        origen_dir.mkdir()
        destino_dir = tmp_path / "destino"

        entrada = _entrada(origen_dir, "a.pdf", "nuevo_a")
        operacion = OperacionRenombrado(entradas=[entrada], carpeta_destino=destino_dir)

        resultado = ejecutar_renombrado(operacion, is_cancelled=lambda: True)

        assert resultado.cancelado is True
        assert resultado.copiados == 0
        assert resultado.procesados == 0

    def test_cancelacion_no_deja_archivos_parciales_ni_temporales(self, tmp_path):
        origen_dir = tmp_path / "origen"
        origen_dir.mkdir()
        destino_dir = tmp_path / "destino"

        entradas = [_entrada(origen_dir, f"f{i}.pdf", f"nuevo_{i}") for i in range(2)]
        operacion = OperacionRenombrado(entradas=entradas, carpeta_destino=destino_dir)

        # Cancelar tras el primer archivo.
        resultado_parcial = {"n": 0}

        def is_cancelled():
            return resultado_parcial["n"] >= 1

        def progress(actual, total):
            resultado_parcial["n"] = actual

        resultado = ejecutar_renombrado(operacion, progress=progress, is_cancelled=is_cancelled)

        assert resultado.cancelado is True
        # No debe quedar ningún archivo temporal ni parcial en destino.
        nombres_destino = [p.name for p in destino_dir.iterdir()]
        assert nombres_destino == ["nuevo_0.pdf"]


# ======================================================
# run() → build_result (contrato)
# ======================================================

class TestRunAdaptaABuildResult:

    def _sesion_basica(self, tmp_path, contenido: bytes = b"x") -> tuple[SesionRenombrado, Path]:
        origen_dir = tmp_path / "origen"
        origen_dir.mkdir(exist_ok=True)
        archivo = origen_dir / "a.pdf"
        archivo.write_bytes(contenido)
        destino_dir = tmp_path / "destino"

        sesion = SesionRenombrado()
        sesion.agregar([archivo])
        sesion.establecer_nombres(["nuevo_a"])
        sesion.establecer_carpeta_destino(destino_dir)
        return sesion, destino_dir

    def test_run_sin_sesion_lanza_runtime_error(self):
        with pytest.raises(RuntimeError):
            renombrar_archivos.run()

    def test_run_sin_carpeta_destino_lanza_runtime_error(self):
        sesion = SesionRenombrado()
        with pytest.raises(RuntimeError):
            renombrar_archivos.run(sesion=sesion)

    def test_run_devuelve_formato_build_result(self, tmp_path):
        sesion, destino_dir = self._sesion_basica(tmp_path)

        resultado = renombrar_archivos.run(sesion=sesion)

        assert resultado["message"]
        assert resultado["output_dir"] == str(destino_dir)
        assert resultado["stats"]["total"] == 1
        assert resultado["stats"]["procesados"] == 1
        assert resultado["stats"]["copiados"] == 1
        assert resultado["stats"]["errores"] == 0
        assert resultado["stats"]["omitidos"] == 0
        assert resultado["stats"]["cancelado"] is False
        assert resultado["stats"]["incidencias"] == []
        assert (destino_dir / "nuevo_a.pdf").exists()

    def test_run_reenvia_progress_e_is_cancelled_al_ejecutor(self, tmp_path):
        sesion, _ = self._sesion_basica(tmp_path)

        llamadas = []
        resultado = renombrar_archivos.run(
            progress=lambda actual, total: llamadas.append((actual, total)),
            is_cancelled=lambda: False,
            sesion=sesion,
        )

        assert llamadas == [(1, 1)]
        assert resultado["stats"]["copiados"] == 1

    def test_run_cancelado_devuelve_resultado_normal_sin_propagar_excepcion(self, tmp_path):
        sesion, _ = self._sesion_basica(tmp_path)

        resultado = renombrar_archivos.run(is_cancelled=lambda: True, sesion=sesion)

        assert resultado["message"] == "Cancelado"
        assert resultado["stats"]["cancelado"] is True
        assert resultado["stats"]["copiados"] == 0

    def test_run_ligado_con_functools_partial_es_compatible_con_script_runner(self, tmp_path):
        """
        ScriptRunner llama a la función exactamente así: funcion(progress=,
        is_cancelled=). Este test reproduce esa llamada tal cual la hace
        core/script_runner.py sobre la función ya ligada a la sesión.
        """
        sesion, destino_dir = self._sesion_basica(tmp_path)

        funcion = functools.partial(renombrar_archivos.run, sesion=sesion)
        resultado = funcion(progress=lambda actual, total: None, is_cancelled=lambda: False)

        assert resultado["stats"]["copiados"] == 1
        assert resultado["output_dir"] == str(destino_dir)
