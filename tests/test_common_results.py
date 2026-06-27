from scripts.common.results import build_result, build_cancelled_result


def test_build_result_basic():
    result = build_result(
        message="OK",
        output_dir="C:/temp",
        total=10,
        procesados=7,
        errores=2,
    )

    assert result["message"] == "OK"
    assert result["output_dir"] == "C:/temp"
    assert result["stats"]["total"] == 10
    assert result["stats"]["procesados"] == 7
    assert result["stats"]["errores"] == 2
    assert result["stats"]["omitidos"] == 1


def test_build_result_without_total():
    result = build_result(
        message="OK",
        output_dir=None,
        custom=True,
    )

    assert result["message"] == "OK"
    assert result["output_dir"] is None
    assert result["stats"]["custom"] is True


def test_build_result_with_explicit_omitidos():
    result = build_result(
        message="OK",
        output_dir="salida",
        total=10,
        procesados=3,
        errores=1,
        omitidos=99,
    )

    assert result["stats"]["omitidos"] == 99


def test_build_cancelled_result():
    result = build_cancelled_result(
        output_dir="salida",
        total=5,
        procesados=2,
        errores=1,
    )

    assert result["message"] == "Cancelado"
    assert result["output_dir"] == "salida"
    assert result["stats"]["total"] == 5
    assert result["stats"]["procesados"] == 2
    assert result["stats"]["errores"] == 1
    assert result["stats"]["omitidos"] == 2