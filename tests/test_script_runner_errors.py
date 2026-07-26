import pytest

from core.script_runner import ScriptRunner
from ui.exceptions import CancelledByUser


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


def test_runner_calls_on_cancelled_not_success_or_error():
    """Una cancelación debe notificarse por su propio callback, distinto
    de éxito y error, cuando el llamador lo proporciona."""
    success_calls = []
    error_calls = []
    cancelled_calls = []
    finished = {"done": False}

    runner = ScriptRunner()
    runner.run(
        funcion=lambda **kwargs: (_ for _ in ()).throw(CancelledByUser()),
        progress=None,
        is_cancelled=None,
        on_success=lambda resultado: success_calls.append(resultado),
        on_error=lambda payload: error_calls.append(payload),
        on_cancelled=lambda resultado: cancelled_calls.append(resultado),
        on_finally=lambda: finished.__setitem__("done", True),
    )
    runner._thread.join(timeout=5)

    assert finished["done"] is True
    assert success_calls == []
    assert error_calls == []
    assert len(cancelled_calls) == 1
    assert cancelled_calls[0]["message"] == "Cancelado"


def test_runner_falls_back_to_on_success_when_on_cancelled_missing():
    """Compatibilidad: si un llamador no pasa on_cancelled, la cancelación
    sigue notificándose por on_success con el mensaje 'Cancelado'."""
    success_calls = []
    finished = {"done": False}

    runner = ScriptRunner()
    runner.run(
        funcion=lambda **kwargs: (_ for _ in ()).throw(CancelledByUser()),
        progress=None,
        is_cancelled=None,
        on_success=lambda resultado: success_calls.append(resultado),
        on_error=lambda payload: None,
        on_finally=lambda: finished.__setitem__("done", True),
    )
    runner._thread.join(timeout=5)

    assert finished["done"] is True
    assert len(success_calls) == 1
    assert success_calls[0]["message"] == "Cancelado"


def test_runner_cancellation_does_not_trigger_error_dialog_path():
    """Una cancelación esperada nunca debe pasar por on_error."""
    error_calls = []
    finished = {"done": False}

    runner = ScriptRunner()
    runner.run(
        funcion=lambda **kwargs: (_ for _ in ()).throw(CancelledByUser()),
        progress=None,
        is_cancelled=None,
        on_success=lambda resultado: None,
        on_error=lambda payload: error_calls.append(payload),
        on_cancelled=lambda resultado: None,
        on_finally=lambda: finished.__setitem__("done", True),
    )
    runner._thread.join(timeout=5)

    assert finished["done"] is True
    assert error_calls == []
