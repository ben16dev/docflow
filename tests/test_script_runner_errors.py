import pytest

from core.script_runner import ScriptRunner


def test_runner_passes_user_message_and_log_file(monkeypatch):
    logged = []

    monkeypatch.setattr(
        "core.script_runner.logger.error",
        lambda msg: logged.append(msg),
    )

    captured = []

    def on_error(payload):
        captured.append(payload)

    finished = {"done": False}

    def on_finally():
        finished["done"] = True

    runner = ScriptRunner()
    runner.run(
        funcion=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("mensaje prueba")),
        progress=None,
        is_cancelled=None,
        on_success=lambda result: None,
        on_error=on_error,
        on_finally=on_finally,
    )
    runner._thread.join(timeout=5)

    assert finished["done"] is True
    assert len(captured) == 1
    assert captured[0]["user_message"] == "mensaje prueba"
    assert captured[0]["log_file"]
    assert any("Traceback" in entry for entry in logged)
    assert any("mensaje prueba" in entry for entry in logged)


def test_format_user_error_for_permission_error():
    from core.errors import format_user_error

    message = format_user_error(PermissionError("denied"))
    assert "permisos" in message.lower()


def test_format_user_error_generic_exception():
    from core.errors import format_user_error

    message = format_user_error(ValueError("detalle interno"))
    assert "inesperado" in message.lower()
    assert "detalle interno" not in message
