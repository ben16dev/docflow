from pathlib import Path

from scripts.common.filenames import (
    sanitize_filename,
    sanitize_filename_ascii,
    resolve_conflict,
)


def test_sanitize_filename_removes_windows_invalid_chars():
    result = sanitize_filename('Cliente: prueba / test * final?.pdf')
    assert ":" not in result
    assert "/" not in result
    assert "*" not in result
    assert "?" not in result


def test_sanitize_filename_uses_fallback_when_empty():
    assert sanitize_filename("", fallback="salida") == "salida"
    assert sanitize_filename("   ", fallback="salida") == "salida"


def test_sanitize_filename_respects_max_len():
    result = sanitize_filename("A" * 200, max_len=20)
    assert len(result) == 20


def test_sanitize_filename_ascii_removes_accents():
    result = sanitize_filename_ascii("ÁÉÍÓÚ Ñ cliente")
    assert "Á" not in result
    assert "É" not in result
    assert "Ñ" in result or "N" in result


def test_resolve_conflict_returns_same_path_if_free(tmp_path):
    target = tmp_path / "archivo.pdf"
    assert resolve_conflict(target) == target


def test_resolve_conflict_adds_suffix_if_exists(tmp_path):
    target = tmp_path / "archivo.pdf"
    target.write_text("test", encoding="utf-8")

    resolved = resolve_conflict(target, pattern="_v{i}")

    assert resolved == tmp_path / "archivo_v2.pdf"