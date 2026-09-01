"""
Tests del núcleo OCR DocFlow (ocrmypdf + tesseract + pypdfium).

Los tests unitarios usan mocks. Los que requieren Tesseract real
se marcan con skip si no está disponible.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import stat
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.common.ocr_io import (
    OcrValidationError,
    ensure_output_visible,
    make_temp_pdf_path,
    pdf_has_extractable_text,
    promote_temp_to_final,
    resolve_output_path,
    safe_unlink,
    validate_ocr_output,
)
from scripts.common import ocr_runtime
from scripts.common.ocr_runtime import (
    BUNDLED_TESSERACT_DIRNAME,
    OCR_BASE_FLAGS,
    DependencyOrigin,
    OcrDependencyError,
    build_ocr_command,
    build_subprocess_env,
    locate_ocrmypdf,
    locate_tesseract,
    locate_tessdata,
    redact_process_text,
    require_runtime,
)
from scripts.pdf import ocr_pdf
from ui.exceptions import CancelledByUser

SPIKE_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "spikes"
    / "ocr"
    / "fixtures"
    / "scan_es_sintetico.pdf"
)


def _tesseract_available() -> bool:
    return shutil.which("tesseract") is not None or Path(
        "/opt/homebrew/bin/tesseract"
    ).is_file()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_minimal_pdf(path: Path, text: str = "DocFlow OCR") -> None:
    """PDF mínimo con texto extraíble (reportlab)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=A4)
    c.drawString(72, 720, text)
    c.save()


# ---------------------------------------------------------------------------
# 1–4: construcción del comando / flags / sin Ghostscript
# ---------------------------------------------------------------------------


def test_build_command_contains_base_flags(tmp_path):
    inp = tmp_path / "in.pdf"
    out = tmp_path / "out.pdf"
    inp.write_bytes(b"%PDF-1.4")
    cmd = build_ocr_command(inp, out, ocrmypdf_bin=Path("/fake/ocrmypdf"))
    assert Path(cmd[0]) == Path("/fake/ocrmypdf")
    assert "--language" in cmd and "spa" in cmd
    assert "--output-type" in cmd and "pdf" in cmd
    assert "--optimize" in cmd and "0" in cmd
    assert "--jobs" in cmd and "1" in cmd
    assert "--no-progress-bar" in cmd
    assert str(inp) in cmd
    assert str(out) in cmd


def test_command_uses_mode_skip(tmp_path):
    cmd = build_ocr_command(
        tmp_path / "a.pdf",
        tmp_path / "b.pdf",
        ocrmypdf_bin=Path("ocrmypdf"),
    )
    assert "--mode" in cmd
    assert cmd[cmd.index("--mode") + 1] == "skip"
    assert "skip" in OCR_BASE_FLAGS


def test_command_uses_rasterizer_pypdfium(tmp_path):
    cmd = build_ocr_command(
        tmp_path / "a.pdf",
        tmp_path / "b.pdf",
        ocrmypdf_bin=Path("ocrmypdf"),
    )
    assert "--rasterizer" in cmd
    assert cmd[cmd.index("--rasterizer") + 1] == "pypdfium"


def test_command_has_no_ghostscript(tmp_path):
    cmd = build_ocr_command(
        tmp_path / "a.pdf",
        tmp_path / "b.pdf",
        ocrmypdf_bin=Path("ocrmypdf"),
    )
    joined = " ".join(cmd).lower()
    assert "ghostscript" not in joined
    assert " --gs" not in joined
    assert not any(part == "gs" for part in cmd)


def test_command_omits_deskew_rotate_pdfa(tmp_path):
    cmd = build_ocr_command(
        tmp_path / "a.pdf",
        tmp_path / "b.pdf",
        ocrmypdf_bin=Path("ocrmypdf"),
    )
    assert "--deskew" not in cmd
    assert "--rotate-pages" not in cmd
    assert "pdfa" not in " ".join(cmd).lower()


# ---------------------------------------------------------------------------
# 5: selección de varios PDF
# ---------------------------------------------------------------------------


def test_run_accepts_multiple_pdfs(tmp_path, monkeypatch):
    pdfs = []
    for name in ("a.pdf", "b.pdf", "c.pdf"):
        p = tmp_path / name
        _write_minimal_pdf(p, f"page {name}")
        pdfs.append(p)
    dest = tmp_path / "out"
    dest.mkdir()

    calls = {"n": 0}

    def fake_process(input_pdf, output_dir, **kwargs):
        calls["n"] += 1
        out = output_dir / f"{input_pdf.stem}_ocr.pdf"
        _write_minimal_pdf(out, f"page {input_pdf.name}")
        return out

    monkeypatch.setattr(ocr_pdf, "process_one_pdf", fake_process)
    monkeypatch.setattr(
        ocr_pdf,
        "require_runtime",
        lambda: (
            MagicMock(path=Path("ocrmypdf"), origin=MagicMock(value="system")),
            MagicMock(path=Path("tesseract"), origin=MagicMock(value="system")),
            MagicMock(path=Path("tessdata"), origin=MagicMock(value="system")),
        ),
    )
    monkeypatch.setattr(
        ocr_pdf,
        "build_subprocess_env",
        lambda **kw: {"PATH": "/bin"},
    )

    progress_log = []
    result = ocr_pdf.run(
        progress=lambda a, t: progress_log.append((a, t)),
        pdf_paths=pdfs,
        output_dir=dest,
    )
    assert calls["n"] == 3
    assert result["stats"]["total"] == 3
    assert result["stats"]["procesados"] == 3
    assert result["stats"]["procesados"] == len(result["files"])
    assert all(Path(f).is_file() for f in result["files"])
    assert all(Path(f).parent == dest for f in result["files"])
    assert progress_log[0] == (0, 3)
    assert progress_log[-1] == (3, 3)


def test_pdf_dialog_preserves_two_selected_pdf_paths(tmp_path, monkeypatch):
    import tkinter as tk
    import tkinter.filedialog as filedialog
    import ui.ui_thread as ui_thread

    first = tmp_path / "documento_a.pdf"
    second = tmp_path / "documento_b.pdf"
    _write_minimal_pdf(first)
    _write_minimal_pdf(second)
    monkeypatch.setattr(tk, "_get_default_root", lambda: None)
    monkeypatch.setattr(ui_thread, "call_ui", lambda func: func())
    monkeypatch.setattr(
        filedialog,
        "askopenfilenames",
        lambda **kwargs: (str(first), str(second)),
    )

    selected = ocr_pdf._select_pdfs_ui()

    assert isinstance(selected, list)
    assert all(isinstance(path, Path) for path in selected)
    assert [path.name for path in selected] == [
        "documento_a.pdf",
        "documento_b.pdf",
    ]


def test_pdf_dialog_empty_selection_is_cancelled(monkeypatch):
    import tkinter as tk
    import tkinter.filedialog as filedialog
    import ui.ui_thread as ui_thread

    monkeypatch.setattr(tk, "_get_default_root", lambda: None)
    monkeypatch.setattr(ui_thread, "call_ui", lambda func: func())
    monkeypatch.setattr(filedialog, "askopenfilenames", lambda **kwargs: ())

    with pytest.raises(CancelledByUser):
        ocr_pdf._select_pdfs_ui()


def test_run_with_pdf_dialog_processes_two_selected_paths(tmp_path, monkeypatch):
    import tkinter as tk
    import tkinter.filedialog as filedialog
    import ui.ui_thread as ui_thread

    input_dir = tmp_path / "entrada"
    dest = tmp_path / "salida"
    input_dir.mkdir()
    dest.mkdir()
    first = input_dir / "documento_a.pdf"
    second = input_dir / "documento_b.pdf"
    _write_minimal_pdf(first)
    _write_minimal_pdf(second)
    _mock_runtime(monkeypatch)
    monkeypatch.setattr(tk, "_get_default_root", lambda: None)
    monkeypatch.setattr(ui_thread, "call_ui", lambda func: func())
    monkeypatch.setattr(
        filedialog,
        "askopenfilenames",
        lambda **kwargs: (str(first), str(second)),
    )
    monkeypatch.setattr(filedialog, "askdirectory", lambda **kwargs: str(dest))
    processed = []

    def fake_process(input_pdf, output_dir, **kwargs):
        processed.append(input_pdf.name)
        out = output_dir / f"{input_pdf.stem}_ocr.pdf"
        _write_minimal_pdf(out, input_pdf.name)
        return out

    monkeypatch.setattr(ocr_pdf, "process_one_pdf", fake_process)
    progress = []

    result = ocr_pdf.run(progress=lambda a, t: progress.append((a, t)))

    assert processed == ["documento_a.pdf", "documento_b.pdf"]
    assert progress == [(0, 2), (1, 2), (2, 2)]
    assert result["stats"]["total"] == 2
    assert result["stats"]["procesados"] == 2
    assert len(result["files"]) == 2
    assert sorted(path.name for path in dest.glob("*.pdf")) == [
        "documento_a_ocr.pdf",
        "documento_b_ocr.pdf",
    ]


def test_script_runner_preserves_two_pdf_paths_in_adapter(tmp_path, monkeypatch):
    from core.script_runner import ScriptRunner

    first = tmp_path / "documento_a.pdf"
    second = tmp_path / "documento_b.pdf"
    dest = tmp_path / "salida"
    dest.mkdir()
    _write_minimal_pdf(first)
    _write_minimal_pdf(second)
    captured = {}
    done = threading.Event()

    def fake_batch_run(progress=None, is_cancelled=None, *, pdf_paths=None, output_dir=None):
        captured["pdf_paths"] = list(pdf_paths)
        captured["output_dir"] = output_dir
        return {
            "message": "ok",
            "output_dir": str(output_dir),
            "stats": {"total": len(pdf_paths), "procesados": len(pdf_paths)},
            "files": [],
        }

    def adapter(progress=None, is_cancelled=None):
        return fake_batch_run(
            progress=progress,
            is_cancelled=is_cancelled,
            pdf_paths=[first, second],
            output_dir=dest,
        )

    ScriptRunner().run(
        funcion=adapter,
        progress=lambda actual, total: None,
        is_cancelled=lambda: False,
        on_success=lambda result: captured.setdefault("result", result),
        on_error=lambda error: captured.setdefault("error", error),
        on_cancelled=lambda result: captured.setdefault("cancelled", result),
        on_finally=done.set,
    )

    assert done.wait(5)
    assert "error" not in captured
    assert [path.name for path in captured["pdf_paths"]] == [
        "documento_a.pdf",
        "documento_b.pdf",
    ]
    assert captured["output_dir"] == dest
    assert captured["result"]["stats"]["total"] == 2


# ---------------------------------------------------------------------------
# 6: colisiones
# ---------------------------------------------------------------------------


def test_resolve_output_avoids_overwrite(tmp_path):
    existing = tmp_path / "doc_ocr.pdf"
    existing.write_bytes(b"x")
    resolved = resolve_output_path(tmp_path, "doc.pdf")
    assert resolved.name == "doc_ocr_v2.pdf"
    assert not resolved.exists() or resolved != existing


# ---------------------------------------------------------------------------
# 7–9: temporal → validación → promoción / limpieza
# ---------------------------------------------------------------------------


def test_temp_validate_promote_success(tmp_path):
    original = tmp_path / "orig.pdf"
    _write_minimal_pdf(original, "Texto validacion DocFlow")
    temp = make_temp_pdf_path(tmp_path, "orig")
    assert temp.name.startswith(".docflow_ocr_")
    shutil.copy(original, temp)

    validation = validate_ocr_output(original, temp)
    assert validation.ok
    assert validation.page_count_original == validation.page_count_output
    assert validation.has_extractable_text

    final = resolve_output_path(tmp_path, "orig.pdf")
    promoted = promote_temp_to_final(temp, final)
    assert promoted.exists()
    assert not temp.exists()
    assert promoted.name.startswith("orig_ocr")
    if sys.platform == "darwin":
        import stat as st

        assert not (promoted.stat().st_flags & st.UF_HIDDEN)


@pytest.mark.skipif(sys.platform != "darwin", reason="Requiere filesystem macOS con UF_HIDDEN")
def test_ensure_output_visible_clears_uf_hidden_on_macos(tmp_path):
    import stat as st

    path = tmp_path / "visible.pdf"
    path.write_bytes(b"%PDF-1.4")
    os.chflags(path, path.stat().st_flags | st.UF_HIDDEN)
    assert path.stat().st_flags & st.UF_HIDDEN

    ensure_output_visible(path)

    assert not (path.stat().st_flags & st.UF_HIDDEN)


@pytest.mark.skipif(sys.platform != "darwin", reason="Requiere filesystem macOS con UF_HIDDEN")
def test_ensure_output_visible_preserves_other_compatible_flags(tmp_path):
    import stat as st

    path = tmp_path / "flags.pdf"
    path.write_bytes(b"%PDF-1.4")
    # UF_NODUMP es un flag BSD compatible y distinto de UF_HIDDEN.
    desired = st.UF_NODUMP | st.UF_HIDDEN
    os.chflags(path, desired)
    assert path.stat().st_flags & st.UF_HIDDEN
    assert path.stat().st_flags & st.UF_NODUMP

    ensure_output_visible(path)

    remaining = path.stat().st_flags
    assert not (remaining & st.UF_HIDDEN)
    assert remaining & st.UF_NODUMP


def test_ensure_output_visible_noop_when_not_hidden(tmp_path, monkeypatch):
    path = tmp_path / "plain.pdf"
    path.write_bytes(b"%PDF-1.4")
    calls = []

    class _Stat:
        st_flags = 0

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(stat, "UF_HIDDEN", 0x8000, raising=False)
    monkeypatch.setattr(Path, "stat", lambda self, *a, **k: _Stat())
    monkeypatch.setattr(
        os, "chflags", lambda *a, **k: calls.append(a), raising=False
    )

    ensure_output_visible(path)
    assert calls == []


def test_ensure_output_visible_noop_outside_macos(tmp_path, monkeypatch):
    path = tmp_path / "other.pdf"
    path.write_bytes(b"%PDF-1.4")

    monkeypatch.setattr(sys, "platform", "linux")

    ensure_output_visible(path)


def test_ensure_output_visible_clears_uf_hidden_simulated_darwin(tmp_path, monkeypatch):
    uf_hidden = 0x8000
    uf_nodump = 0x0001
    path = tmp_path / "hidden.pdf"
    path.write_bytes(b"%PDF-1.4")
    calls = []
    current_flags = [uf_hidden | uf_nodump]

    class _Stat:
        @property
        def st_flags(self):
            return current_flags[0]

    def fake_chflags(_path, flags):
        calls.append(flags)
        current_flags[0] = flags

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(stat, "UF_HIDDEN", uf_hidden, raising=False)
    monkeypatch.setattr(Path, "stat", lambda self, *a, **k: _Stat())
    monkeypatch.setattr(os, "chflags", fake_chflags, raising=False)

    ensure_output_visible(path)

    assert calls == [uf_nodump]
    assert not (current_flags[0] & uf_hidden)
    assert current_flags[0] & uf_nodump


def test_ensure_output_visible_missing_chflags_raises(tmp_path, monkeypatch):
    uf_hidden = 0x8000
    path = tmp_path / "hidden.pdf"
    path.write_bytes(b"%PDF-1.4")

    class _Stat:
        st_flags = uf_hidden

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(stat, "UF_HIDDEN", uf_hidden, raising=False)
    monkeypatch.setattr(Path, "stat", lambda self, *a, **k: _Stat())
    monkeypatch.delattr(os, "chflags", raising=False)

    with pytest.raises(OcrValidationError) as excinfo:
        ensure_output_visible(path)

    assert excinfo.value.category == "hidden_flag_clear_failed"


def test_ensure_output_visible_missing_uf_hidden_raises(tmp_path, monkeypatch):
    path = tmp_path / "plain.pdf"
    path.write_bytes(b"%PDF-1.4")

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.delattr(stat, "UF_HIDDEN", raising=False)
    monkeypatch.setattr(os, "chflags", lambda *a, **k: None, raising=False)

    with pytest.raises(OcrValidationError) as excinfo:
        ensure_output_visible(path)

    assert excinfo.value.category == "hidden_flag_clear_failed"


def test_ensure_output_visible_chflags_failure_raises(tmp_path, monkeypatch):
    uf_hidden = 0x8000
    path = tmp_path / "hidden.pdf"
    path.write_bytes(b"%PDF-1.4")

    class _Stat:
        st_flags = uf_hidden

    def boom(*args, **kwargs):
        raise OSError("chflags denied")

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(stat, "UF_HIDDEN", uf_hidden, raising=False)
    monkeypatch.setattr(Path, "stat", lambda self, *a, **k: _Stat())
    monkeypatch.setattr(os, "chflags", boom, raising=False)

    with pytest.raises(OcrValidationError) as excinfo:
        ensure_output_visible(path)

    assert excinfo.value.category == "hidden_flag_clear_failed"


@pytest.mark.skipif(sys.platform != "darwin", reason="Requiere filesystem macOS con UF_HIDDEN")
def test_promote_clears_uf_hidden_after_replace(tmp_path):
    import stat as st

    original = tmp_path / "orig.pdf"
    _write_minimal_pdf(original, "Texto visible DocFlow")
    before = _sha(original)
    temp = make_temp_pdf_path(tmp_path, "orig")
    shutil.copy(original, temp)
    # Los nombres con punto suelen marcar UF_HIDDEN; forzamos el flag.
    os.chflags(temp, temp.stat().st_flags | st.UF_HIDDEN)
    assert temp.stat().st_flags & st.UF_HIDDEN

    final = resolve_output_path(tmp_path, "orig.pdf")
    promoted = promote_temp_to_final(temp, final)

    assert promoted.is_file()
    assert not (promoted.stat().st_flags & st.UF_HIDDEN)
    assert _sha(original) == before
    assert not original.name.startswith(".")


@pytest.mark.skipif(sys.platform != "darwin", reason="Requiere filesystem macOS con UF_HIDDEN")
def test_promote_chflags_failure_is_not_silent_success(tmp_path, monkeypatch):
    import stat as st

    original = tmp_path / "orig.pdf"
    _write_minimal_pdf(original, "Texto DocFlow")
    before = _sha(original)
    temp = make_temp_pdf_path(tmp_path, "orig")
    shutil.copy(original, temp)
    os.chflags(temp, temp.stat().st_flags | st.UF_HIDDEN)
    final = resolve_output_path(tmp_path, "orig.pdf")

    def boom(*args, **kwargs):
        raise OSError("chflags denied")

    monkeypatch.setattr(os, "chflags", boom)

    with pytest.raises(OcrValidationError) as excinfo:
        promote_temp_to_final(temp, final)

    assert excinfo.value.category == "hidden_flag_clear_failed"
    # El PDF ya promovido se conserva; no se elimina documentación generada.
    assert final.is_file()
    assert final.stat().st_flags & st.UF_HIDDEN
    assert _sha(original) == before


def test_cleanup_after_success_removes_temp(tmp_path, monkeypatch):
    original = tmp_path / "in.pdf"
    _write_minimal_pdf(original, "DocFlow limpio")
    dest = tmp_path / "out"
    dest.mkdir()

    def fake_run(input_pdf, temp_output, **kwargs):
        shutil.copy(input_pdf, temp_output)
        return 0, 0.1

    monkeypatch.setattr(ocr_pdf, "run_ocrmypdf_process", fake_run)
    result = ocr_pdf.process_one_pdf(original, dest)
    assert result.exists()
    leftovers = list(dest.glob(".docflow_ocr_*"))
    assert leftovers == []


def test_cleanup_after_error_removes_temp(tmp_path, monkeypatch):
    original = tmp_path / "in.pdf"
    _write_minimal_pdf(original, "DocFlow error")
    dest = tmp_path / "out"
    dest.mkdir()

    def fake_run(input_pdf, temp_output, **kwargs):
        temp_output.write_bytes(b"%PDF-1.4 broken")
        raise ocr_pdf.OcrProcessError("ocr_failed", "fallo", returncode=1)

    monkeypatch.setattr(ocr_pdf, "run_ocrmypdf_process", fake_run)
    with pytest.raises(ocr_pdf.OcrProcessError):
        ocr_pdf.process_one_pdf(original, dest)
    assert list(dest.glob(".docflow_ocr_*")) == []


# ---------------------------------------------------------------------------
# 10–13: cancelación + CancelledByUser
# ---------------------------------------------------------------------------


def test_cancel_before_start(tmp_path):
    pdf = tmp_path / "a.pdf"
    _write_minimal_pdf(pdf)
    with pytest.raises(CancelledByUser):
        ocr_pdf.run(
            is_cancelled=lambda: True,
            pdf_paths=[pdf],
            output_dir=tmp_path,
        )


def test_cancel_between_files(tmp_path, monkeypatch):
    pdfs = []
    for name in ("a.pdf", "b.pdf", "c.pdf"):
        p = tmp_path / name
        _write_minimal_pdf(p)
        pdfs.append(p)

    state = {"done": 0}
    cancelled_after_first = {"flag": False}

    def process_and_arm(input_pdf, output_dir, **kwargs):
        state["done"] += 1
        out = output_dir / f"{input_pdf.stem}_ocr.pdf"
        _write_minimal_pdf(out, "DocFlow cancel")
        cancelled_after_first["flag"] = True
        return out

    monkeypatch.setattr(ocr_pdf, "process_one_pdf", process_and_arm)
    monkeypatch.setattr(
        ocr_pdf,
        "require_runtime",
        lambda: (
            MagicMock(path=Path("ocrmypdf"), origin=MagicMock(value="system")),
            MagicMock(path=Path("tesseract"), origin=MagicMock(value="system")),
            MagicMock(path=Path("tessdata"), origin=MagicMock(value="system")),
        ),
    )
    monkeypatch.setattr(ocr_pdf, "build_subprocess_env", lambda **kw: {})

    with pytest.raises(CancelledByUser):
        ocr_pdf.run(
            is_cancelled=lambda: cancelled_after_first["flag"],
            pdf_paths=pdfs,
            output_dir=tmp_path,
        )

    assert state["done"] == 1


def test_cancel_during_ocr_raises_cancelled(tmp_path, monkeypatch):
    original = tmp_path / "in.pdf"
    _write_minimal_pdf(original)
    dest = tmp_path / "out"
    dest.mkdir()

    def fake_run(input_pdf, temp_output, **kwargs):
        raise CancelledByUser()

    monkeypatch.setattr(ocr_pdf, "run_ocrmypdf_process", fake_run)
    result = ocr_pdf.process_one_pdf(original, dest, is_cancelled=lambda: False)
    assert result.status == "cancelled"
    assert list(dest.glob(".docflow_ocr_*")) == []


def test_cancelled_by_user_not_swallowed(tmp_path, monkeypatch):
    """ScriptRunner debe recibir CancelledByUser, no un dict de éxito."""
    pdf = tmp_path / "a.pdf"
    _write_minimal_pdf(pdf)

    monkeypatch.setattr(
        ocr_pdf,
        "require_runtime",
        lambda: (
            MagicMock(path=Path("ocrmypdf"), origin=MagicMock(value="system")),
            MagicMock(path=Path("tesseract"), origin=MagicMock(value="system")),
            MagicMock(path=Path("tessdata"), origin=MagicMock(value="system")),
        ),
    )
    monkeypatch.setattr(ocr_pdf, "build_subprocess_env", lambda **kw: {})

    def boom(*args, **kwargs):
        raise CancelledByUser()

    monkeypatch.setattr(ocr_pdf, "process_one_pdf", boom)

    with pytest.raises(CancelledByUser):
        ocr_pdf.run(pdf_paths=[pdf], output_dir=tmp_path)


# ---------------------------------------------------------------------------
# 14–16: original intacto / páginas / texto (integración si hay Tesseract)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _tesseract_available(), reason="Tesseract no disponible")
@pytest.mark.skipif(not SPIKE_FIXTURE.exists(), reason="Fixture spike ausente")
def test_integration_original_pages_and_text(tmp_path):
    dest = tmp_path / "out"
    dest.mkdir()
    before = _sha(SPIKE_FIXTURE)

    # Asegurar PATH Homebrew en el entorno del test sin mutar de forma permanente
    # más allá del proceso de test (pytest aisla parcialmente).
    brew = "/opt/homebrew/bin"
    if brew not in os.environ.get("PATH", ""):
        os.environ["PATH"] = brew + os.pathsep + os.environ.get("PATH", "")

    result = ocr_pdf.run(pdf_paths=[SPIKE_FIXTURE], output_dir=dest)
    assert result["stats"]["procesados"] == 1
    assert _sha(SPIKE_FIXTURE) == before

    outputs = list(dest.glob("*.pdf"))
    assert len(outputs) == 1
    out = outputs[0]
    validation = validate_ocr_output(SPIKE_FIXTURE, out)
    assert validation.ok
    assert validation.page_count_original == validation.page_count_output
    assert validation.has_extractable_text

    # Comprobar fragmentos sin registrar texto completo en asserts ruidosos
    import fitz

    doc = fitz.open(out)
    try:
        text = "".join(page.get_text("text") for page in doc)
    finally:
        doc.close()
    assert "DocFlow" in text
    assert "DF-OCR-2026-0042" in text


def test_page_count_mismatch_fails_validation(tmp_path):
    original = tmp_path / "orig.pdf"
    candidate = tmp_path / "cand.pdf"
    _write_minimal_pdf(original, "una pagina")

    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4

    c = canvas.Canvas(str(candidate), pagesize=A4)
    c.drawString(72, 720, "pagina 1")
    c.showPage()
    c.drawString(72, 720, "pagina 2")
    c.save()

    result = validate_ocr_output(original, candidate)
    assert not result.ok
    assert result.category == "page_count_mismatch"


def test_extractable_text_required(tmp_path):
    original = tmp_path / "orig.pdf"
    candidate = tmp_path / "cand.pdf"
    from pypdf import PdfWriter

    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    with original.open("wb") as fh:
        w.write(fh)
    shutil.copy(original, candidate)

    result = validate_ocr_output(original, candidate, require_text=True)
    assert not result.ok
    assert result.category == "no_extractable_text"


# ---------------------------------------------------------------------------
# 17: dependencia ausente
# ---------------------------------------------------------------------------


def test_missing_dependency_error(monkeypatch):
    monkeypatch.setattr(
        "scripts.common.ocr_runtime.locate_ocrmypdf",
        lambda: MagicMock(path=None, origin=MagicMock(value="missing")),
    )
    with pytest.raises(OcrDependencyError) as excinfo:
        require_runtime()
    assert excinfo.value.category == "missing_ocrmypdf"


def test_run_missing_tesseract_raises(tmp_path, monkeypatch):
    pdf = tmp_path / "a.pdf"
    _write_minimal_pdf(pdf)

    def boom():
        raise OcrDependencyError("missing_tesseract", "No se encontró Tesseract.")

    monkeypatch.setattr(ocr_pdf, "require_runtime", boom)
    with pytest.raises(RuntimeError, match="Tesseract"):
        ocr_pdf.run(pdf_paths=[pdf], output_dir=tmp_path)


# ---------------------------------------------------------------------------
# 18: logs sin rutas absolutas ni texto OCR
# ---------------------------------------------------------------------------


def test_logs_avoid_absolute_paths_and_ocr_text(tmp_path, monkeypatch, caplog):
    pdf = tmp_path / "documento_secreto_cliente.pdf"
    _write_minimal_pdf(pdf, "DATOS CONFIDENCIALES 99999")
    dest = tmp_path / "out"
    dest.mkdir()

    monkeypatch.setattr(
        ocr_pdf,
        "require_runtime",
        lambda: (
            MagicMock(path=Path("ocrmypdf"), origin=MagicMock(value="system")),
            MagicMock(path=Path("tesseract"), origin=MagicMock(value="system")),
            MagicMock(path=Path("tessdata"), origin=MagicMock(value="system")),
        ),
    )
    monkeypatch.setattr(ocr_pdf, "build_subprocess_env", lambda **kw: {})

    def fake_process(input_pdf, output_dir, **kwargs):
        out = output_dir / "ok_ocr.pdf"
        _write_minimal_pdf(out, "DocFlow logs")
        return out

    monkeypatch.setattr(ocr_pdf, "process_one_pdf", fake_process)

    with caplog.at_level(logging.DEBUG):
        ocr_pdf.run(pdf_paths=[pdf], output_dir=dest)

    joined = "\n".join(r.message for r in caplog.records)
    assert str(pdf.resolve()) not in joined
    assert str(dest.resolve()) not in joined
    assert "DATOS CONFIDENCIALES" not in joined
    assert "documento_secreto_cliente" not in joined
    for tag in ("ui_" + "selector", "ui_" + "state", "ocr_" + "run", "runner_" + "args"):
        assert tag not in joined


def test_pdf_dialog_does_not_emit_diagnostic_trace_tags(tmp_path, monkeypatch, caplog):
    import tkinter as tk
    import tkinter.filedialog as filedialog
    import ui.ui_thread as ui_thread

    first = tmp_path / "a.pdf"
    _write_minimal_pdf(first)
    monkeypatch.setattr(tk, "_get_default_root", lambda: None)
    monkeypatch.setattr(ui_thread, "call_ui", lambda func: func())
    monkeypatch.setattr(
        filedialog,
        "askopenfilenames",
        lambda **kwargs: (str(first),),
    )

    with caplog.at_level(logging.DEBUG):
        selected = ocr_pdf._select_pdfs_ui()

    joined = "\n".join(r.message for r in caplog.records)
    assert selected[0].name == "a.pdf"
    for tag in ("ui_" + "selector", "ui_" + "state", "ocr_" + "run", "runner_" + "args"):
        assert tag not in joined


def test_redact_process_text_strips_paths():
    raw = "ERROR reading /Users/alejandro/Desktop/DocFlow/secret.pdf page 1"
    redacted = redact_process_text(raw)
    assert "/Users/alejandro" not in redacted
    assert "secret.pdf" not in redacted or "[pdf]" in redacted


# ---------------------------------------------------------------------------
# 19: no mutación de os.environ
# ---------------------------------------------------------------------------


def test_build_subprocess_env_does_not_mutate_os_environ():
    before = dict(os.environ)
    tess = MagicMock(path=Path("/opt/homebrew/bin/tesseract"), origin=MagicMock())
    td = MagicMock(path=Path("/opt/homebrew/share/tessdata"), origin=MagicMock())
    env = build_subprocess_env(tesseract=tess, tessdata=td, base_environ={"PATH": "/bin"})
    assert Path(env["TESSDATA_PREFIX"]) == Path("/opt/homebrew/share/tessdata")
    assert Path(env["PATH"].split(os.pathsep)[0]) == Path("/opt/homebrew/bin")
    assert "DYLD_LIBRARY_PATH" not in env
    assert "DYLD_FALLBACK_LIBRARY_PATH" not in env
    assert dict(os.environ) == before
    assert os.environ.get("TESSDATA_PREFIX") == before.get("TESSDATA_PREFIX")


def test_safe_unlink_missing():
    safe_unlink(Path("/tmp/docflow_no_existe_xyz.pdf"))


# ---------------------------------------------------------------------------
# Empaquetado: resolución frozen vs desarrollo
# ---------------------------------------------------------------------------


def _make_frozen_bundle(tmp_path: Path) -> Path:
    """Layout mínimo tesseract_bundle + helper ocrmypdf bajo un MEIPASS falso."""
    meipass = tmp_path / "_meipass"
    bundle = meipass / BUNDLED_TESSERACT_DIRNAME
    (bundle / "lib").mkdir(parents=True)
    (bundle / "tessdata").mkdir(parents=True)
    tess = bundle / "tesseract"
    tess.write_bytes(b"\0")
    tess.chmod(0o755)
    (bundle / "tessdata" / "spa.traineddata").write_bytes(b"fake")
    helper = meipass / "ocrmypdf"
    helper.write_bytes(b"\0")
    helper.chmod(0o755)
    return meipass


def test_frozen_locate_ocrmypdf_helper(tmp_path, monkeypatch):
    meipass = _make_frozen_bundle(tmp_path)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(sys, "executable", str(meipass / "DocFlow"))

    located = locate_ocrmypdf()
    assert located.origin == DependencyOrigin.BUNDLED
    assert located.path == meipass / "ocrmypdf"


def test_frozen_locate_tesseract_bundle(tmp_path, monkeypatch):
    meipass = _make_frozen_bundle(tmp_path)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(sys, "executable", str(meipass / "DocFlow"))

    located = locate_tesseract()
    assert located.origin == DependencyOrigin.BUNDLED
    assert located.path == meipass / BUNDLED_TESSERACT_DIRNAME / "tesseract"


def test_frozen_locate_spa_traineddata(tmp_path, monkeypatch):
    meipass = _make_frozen_bundle(tmp_path)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(sys, "executable", str(meipass / "DocFlow"))

    located = locate_tessdata(language="spa")
    assert located.origin == DependencyOrigin.BUNDLED
    assert located.path == meipass / BUNDLED_TESSERACT_DIRNAME / "tessdata"
    assert (located.path / "spa.traineddata").is_file()


def test_frozen_prefers_bundle_over_system_paths(tmp_path, monkeypatch):
    meipass = _make_frozen_bundle(tmp_path)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(sys, "executable", str(meipass / "DocFlow"))
    monkeypatch.setenv("PATH", "/opt/homebrew/bin:/usr/bin")

    assert locate_tesseract().origin == DependencyOrigin.BUNDLED
    assert locate_ocrmypdf().origin == DependencyOrigin.BUNDLED
    assert locate_tessdata().origin == DependencyOrigin.BUNDLED


def test_frozen_missing_bundle_does_not_use_system(tmp_path, monkeypatch):
    meipass = tmp_path / "empty_meipass"
    meipass.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(sys, "executable", str(meipass / "DocFlow"))
    monkeypatch.setenv("PATH", "/opt/homebrew/bin:/usr/bin")

    assert locate_tesseract().origin == DependencyOrigin.MISSING
    assert locate_ocrmypdf().origin == DependencyOrigin.MISSING
    assert locate_tessdata().origin == DependencyOrigin.MISSING
    with pytest.raises(OcrDependencyError) as excinfo:
        require_runtime()
    assert excinfo.value.category == "missing_ocrmypdf"


def test_dev_mode_can_use_system_when_not_frozen(monkeypatch):
    monkeypatch.setattr(ocr_runtime, "_is_frozen", lambda: False)
    monkeypatch.setattr(
        ocr_runtime,
        "shutil",
        MagicMock(which=lambda name: "/opt/homebrew/bin/tesseract" if name == "tesseract" else None),
    )
    # Sin rutas Homebrew reales: stubear is_file en Darwin candidates fallando
    # y forzar which.
    monkeypatch.setattr(
        Path,
        "is_file",
        lambda self: str(self) == "/opt/homebrew/bin/tesseract",
    )
    located = locate_tesseract()
    assert located.origin == DependencyOrigin.SYSTEM
    assert located.path == Path("/opt/homebrew/bin/tesseract")


def test_frozen_subprocess_env_sets_path_and_tessdata(tmp_path, monkeypatch):
    meipass = _make_frozen_bundle(tmp_path)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(sys, "executable", str(meipass / "DocFlow"))

    before = dict(os.environ)
    tess = locate_tesseract()
    td = locate_tessdata()
    env = build_subprocess_env(
        tesseract=tess,
        tessdata=td,
        base_environ={"PATH": "/usr/bin", "HOME": "/tmp"},
    )
    assert env["TESSDATA_PREFIX"] == str(meipass / BUNDLED_TESSERACT_DIRNAME / "tessdata")
    path_dirs = env["PATH"].split(os.pathsep)
    assert str(meipass / BUNDLED_TESSERACT_DIRNAME) in path_dirs
    assert str(meipass) in path_dirs
    assert "DYLD_LIBRARY_PATH" not in env
    assert dict(os.environ) == before


def test_command_still_has_no_ghostscript_after_runtime_update(tmp_path):
    cmd = build_ocr_command(
        tmp_path / "a.pdf",
        tmp_path / "b.pdf",
        ocrmypdf_bin=Path("ocrmypdf"),
    )
    joined = " ".join(cmd).lower()
    assert "ghostscript" not in joined
    assert not any(part == "gs" for part in cmd)


# ---------------------------------------------------------------------------
# Regresión: procesados ↔ archivo final en destino
# ---------------------------------------------------------------------------


def _mock_runtime(monkeypatch):
    monkeypatch.setattr(
        ocr_pdf,
        "require_runtime",
        lambda: (
            MagicMock(path=Path("ocrmypdf"), origin=MagicMock(value="system")),
            MagicMock(path=Path("tesseract"), origin=MagicMock(value="system")),
            MagicMock(path=Path("tessdata"), origin=MagicMock(value="system")),
        ),
    )
    monkeypatch.setattr(ocr_pdf, "build_subprocess_env", lambda **kw: {})


def _fake_ocr_copy(input_pdf, temp_output, **kwargs):
    """Mock de OCR: copia un PDF válido al temporal esperado."""
    shutil.copy(input_pdf, temp_output)
    return 0, 0.01


def test_process_one_pdf_returns_existing_file_in_destination(tmp_path, monkeypatch):
    original = tmp_path / "entrada.pdf"
    _write_minimal_pdf(original, "DocFlow destino")
    dest = tmp_path / "salida"
    dest.mkdir()
    monkeypatch.setattr(ocr_pdf, "run_ocrmypdf_process", _fake_ocr_copy)

    returned = ocr_pdf.process_one_pdf(original, dest)

    assert returned.is_file()
    assert returned.parent == dest
    assert returned.name == "entrada_ocr.pdf"
    assert list(dest.glob(".docflow_ocr_*")) == []
    assert list(dest.glob("*_ocr.pdf")) == [returned]


def test_run_with_mocked_ocr_writes_exactly_one_final(tmp_path, monkeypatch):
    original = tmp_path / "doc.pdf"
    _write_minimal_pdf(original, "DocFlow lote")
    dest = tmp_path / "out"
    dest.mkdir()
    _mock_runtime(monkeypatch)
    monkeypatch.setattr(ocr_pdf, "run_ocrmypdf_process", _fake_ocr_copy)

    result = ocr_pdf.run(pdf_paths=[original], output_dir=dest)

    assert result["stats"]["procesados"] == 1
    assert result["stats"]["errores"] == 0
    assert len(result["files"]) == 1
    final = Path(result["files"][0])
    assert final.is_file()
    assert final.parent == dest
    assert final.name == "doc_ocr.pdf"
    assert sorted(p.name for p in dest.iterdir()) == ["doc_ocr.pdf"]
    assert result["stats"]["procesados"] == len(result["files"])


def test_run_does_not_count_missing_returned_path(tmp_path, monkeypatch):
    pdf = tmp_path / "a.pdf"
    _write_minimal_pdf(pdf)
    dest = tmp_path / "out"
    dest.mkdir()
    _mock_runtime(monkeypatch)

    def ghost_process(input_pdf, output_dir, **kwargs):
        return output_dir / "no_existe_ocr.pdf"

    monkeypatch.setattr(ocr_pdf, "process_one_pdf", ghost_process)

    result = ocr_pdf.run(pdf_paths=[pdf], output_dir=dest)

    assert result["message"] == "No se generó ningún PDF OCR válido"
    assert result["stats"]["procesados"] == 0
    assert result["stats"]["errores"] == 1
    assert list(dest.iterdir()) == []


def test_run_rejects_path_outside_destination(tmp_path, monkeypatch):
    pdf = tmp_path / "a.pdf"
    _write_minimal_pdf(pdf)
    dest = tmp_path / "out"
    dest.mkdir()
    outsider = tmp_path / "fuera_ocr.pdf"
    outsider.write_bytes(b"%PDF-1.4")
    _mock_runtime(monkeypatch)

    def outside_process(input_pdf, output_dir, **kwargs):
        return outsider

    monkeypatch.setattr(ocr_pdf, "process_one_pdf", outside_process)

    result = ocr_pdf.run(pdf_paths=[pdf], output_dir=dest)

    assert result["message"] == "No se generó ningún PDF OCR válido"
    assert result["stats"]["procesados"] == 0
    assert result["stats"]["errores"] == 1
    assert not (dest / "fuera_ocr.pdf").exists()
    assert outsider.is_file()


def test_run_files_only_existing_and_in_destination(tmp_path, monkeypatch):
    pdfs = []
    for name in ("ok.pdf", "bad.pdf"):
        p = tmp_path / name
        _write_minimal_pdf(p, name)
        pdfs.append(p)
    dest = tmp_path / "out"
    dest.mkdir()
    _mock_runtime(monkeypatch)

    def selective(input_pdf, output_dir, **kwargs):
        if input_pdf.name == "bad.pdf":
            raise ocr_pdf.OcrProcessError("ocr_failed", "fallo", returncode=1)
        out = output_dir / f"{input_pdf.stem}_ocr.pdf"
        _write_minimal_pdf(out, f"DocFlow {input_pdf.stem}")
        return out

    monkeypatch.setattr(ocr_pdf, "process_one_pdf", selective)

    result = ocr_pdf.run(pdf_paths=pdfs, output_dir=dest)

    assert result["stats"]["procesados"] == 1
    assert result["stats"]["errores"] == 1
    assert result["stats"]["procesados"] == len(result["files"])
    assert all(Path(f).is_file() for f in result["files"])
    assert all(Path(f).parent.resolve() == dest.resolve() for f in result["files"])
    assert result["message"] == "Proceso finalizado con incidencias"
    assert list(dest.glob("*_ocr.pdf")) == [Path(result["files"][0])]


def test_run_all_failures_raise_not_empty_success(tmp_path, monkeypatch):
    pdf = tmp_path / "a.pdf"
    _write_minimal_pdf(pdf)
    dest = tmp_path / "out"
    dest.mkdir()
    _mock_runtime(monkeypatch)

    def boom(input_pdf, output_dir, **kwargs):
        raise ocr_pdf.OcrProcessError("ocr_failed", "fallo", returncode=1)

    monkeypatch.setattr(ocr_pdf, "process_one_pdf", boom)

    result = ocr_pdf.run(pdf_paths=[pdf], output_dir=dest)

    assert result["message"] == "No se generó ningún PDF OCR válido"
    assert result["stats"]["procesados"] == 0
    assert result["stats"]["errores"] == 1


def test_collision_still_generates_v2(tmp_path, monkeypatch):
    original = tmp_path / "informe.pdf"
    _write_minimal_pdf(original, "DocFlow v2")
    dest = tmp_path / "out"
    dest.mkdir()
    existing = dest / "informe_ocr.pdf"
    existing.write_bytes(b"%PDF-1.4 old")
    monkeypatch.setattr(ocr_pdf, "run_ocrmypdf_process", _fake_ocr_copy)

    returned = ocr_pdf.process_one_pdf(original, dest)

    assert returned.name == "informe_ocr_v2.pdf"
    assert returned.is_file()
    assert existing.is_file()
    assert existing.read_bytes() == b"%PDF-1.4 old"


def test_promote_does_not_delete_final_on_later_failure(tmp_path, monkeypatch):
    """Si tras promover falla una postcondición, el final no se borra."""
    original = tmp_path / "x.pdf"
    _write_minimal_pdf(original, "DocFlow keep")
    dest = tmp_path / "out"
    dest.mkdir()
    monkeypatch.setattr(ocr_pdf, "run_ocrmypdf_process", _fake_ocr_copy)

    def always_fail(final_path, output_dir):
        assert Path(final_path).is_file()
        raise ocr_pdf.OcrValidationError(
            "output_outside_destination",
            "El archivo OCR se generó fuera de la carpeta de destino.",
        )

    monkeypatch.setattr(ocr_pdf, "assert_final_in_destination", always_fail)

    with pytest.raises(ocr_pdf.OcrValidationError) as excinfo:
        ocr_pdf.process_one_pdf(original, dest)

    assert excinfo.value.category == "output_outside_destination"
    finals = list(dest.glob("*_ocr.pdf"))
    assert len(finals) == 1
    assert finals[0].is_file()
    assert list(dest.glob(".docflow_ocr_*")) == []


# ---------------------------------------------------------------------------
# Regresión Sprint 7: el original nunca puede ser salida ni ser sustituido
# ---------------------------------------------------------------------------


def _write_image_only_pdf(path: Path) -> None:
    """PDF de una página sin capa de texto."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (900, 1200), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype(
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            44,
        )
    except Exception:
        font = ImageFont.load_default()

    draw.text((80, 180), "Documento sintetico DocFlow", fill="black", font=font)
    draw.text((80, 260), "DocFlowSprint7RutaSegura", fill="black", font=font)
    image.save(path, "PDF", resolution=150.0)


def _fake_ocr_text_output(input_pdf, temp_output, **kwargs):
    """OCR simulado: escribe un PDF válido con texto en el temporal."""
    _write_minimal_pdf(temp_output, "DocFlowSprint7RutaSegura")
    return 0, 0.01


def test_run_preserves_image_only_original_with_distinct_destination(tmp_path, monkeypatch):
    original = tmp_path / "entrada" / "scan.pdf"
    original.parent.mkdir()
    _write_image_only_pdf(original)
    dest = tmp_path / "destino"
    dest.mkdir()
    _mock_runtime(monkeypatch)
    monkeypatch.setattr(ocr_pdf, "run_ocrmypdf_process", _fake_ocr_text_output)

    before_hash = _sha(original)
    before_size = original.stat().st_size
    before_mtime = original.stat().st_mtime_ns
    assert not pdf_has_extractable_text(original)

    result = ocr_pdf.run(pdf_paths=[original], output_dir=dest)

    assert _sha(original) == before_hash
    assert original.stat().st_size == before_size
    assert original.stat().st_mtime_ns == before_mtime
    assert not pdf_has_extractable_text(original)
    assert result["stats"]["procesados"] == 1
    assert len(result["files"]) == 1
    generated = Path(result["files"][0])
    assert generated.resolve() != original.resolve()
    assert generated.parent.resolve() == dest.resolve()
    assert generated.name == "scan_ocr.pdf"
    assert pdf_has_extractable_text(generated)


def test_run_preserves_original_when_destination_is_source_folder(tmp_path, monkeypatch):
    original = tmp_path / "scan.pdf"
    _write_image_only_pdf(original)
    _mock_runtime(monkeypatch)
    monkeypatch.setattr(ocr_pdf, "run_ocrmypdf_process", _fake_ocr_text_output)

    before_hash = _sha(original)
    result = ocr_pdf.run(pdf_paths=[original], output_dir=tmp_path)

    generated = Path(result["files"][0])
    assert _sha(original) == before_hash
    assert not pdf_has_extractable_text(original)
    assert generated.resolve() != original.resolve()
    assert generated.name == "scan_ocr.pdf"
    assert pdf_has_extractable_text(generated)


def test_output_candidate_equal_to_source_is_rejected_before_ocr(tmp_path, monkeypatch):
    original = tmp_path / "scan.pdf"
    _write_image_only_pdf(original)
    before_hash = _sha(original)
    calls = {"ocr": 0}

    def should_not_run(*args, **kwargs):
        calls["ocr"] += 1
        raise AssertionError("OCR no debe ejecutarse con salida igual a entrada")

    monkeypatch.setattr(ocr_pdf, "resolve_output_path", lambda output_dir, source_name: original)
    monkeypatch.setattr(ocr_pdf, "run_ocrmypdf_process", should_not_run)

    with pytest.raises(OcrValidationError) as excinfo:
        ocr_pdf.process_one_pdf(original, tmp_path)

    assert excinfo.value.category == "output_matches_source"
    assert calls["ocr"] == 0
    assert _sha(original) == before_hash
    assert not pdf_has_extractable_text(original)


def test_temp_candidate_equal_to_source_is_rejected_before_ocr(tmp_path, monkeypatch):
    original = tmp_path / "scan.pdf"
    _write_image_only_pdf(original)
    before_hash = _sha(original)

    monkeypatch.setattr(ocr_pdf, "make_temp_pdf_path", lambda output_dir, stem: original)

    with pytest.raises(OcrValidationError) as excinfo:
        ocr_pdf.process_one_pdf(original, tmp_path)

    assert excinfo.value.category == "output_matches_source"
    assert _sha(original) == before_hash
    assert not pdf_has_extractable_text(original)


def test_generated_files_never_include_source_path(tmp_path, monkeypatch):
    original = tmp_path / "scan.pdf"
    _write_image_only_pdf(original)
    before_hash = _sha(original)
    _mock_runtime(monkeypatch)

    def unsafe_process(input_pdf, output_dir, **kwargs):
        return input_pdf

    monkeypatch.setattr(ocr_pdf, "process_one_pdf", unsafe_process)

    result = ocr_pdf.run(pdf_paths=[original], output_dir=tmp_path)

    assert result["message"] == "No se generó ningún PDF OCR válido"
    assert result["stats"]["procesados"] == 0
    assert result["stats"]["errores"] == 1
    assert _sha(original) == before_hash
    assert not pdf_has_extractable_text(original)


def test_collision_generates_alternative_without_touching_original(tmp_path, monkeypatch):
    original = tmp_path / "scan.pdf"
    _write_image_only_pdf(original)
    existing = tmp_path / "scan_ocr.pdf"
    _write_minimal_pdf(existing, "resultado previo")
    _mock_runtime(monkeypatch)
    monkeypatch.setattr(ocr_pdf, "run_ocrmypdf_process", _fake_ocr_text_output)

    original_hash = _sha(original)
    existing_hash = _sha(existing)
    result = ocr_pdf.run(pdf_paths=[original], output_dir=tmp_path)

    generated = Path(result["files"][0])
    assert generated.name == "scan_ocr_v2.pdf"
    assert _sha(original) == original_hash
    assert _sha(existing) == existing_hash
    assert generated.resolve() != original.resolve()


def test_failure_during_ocr_preserves_original_hash(tmp_path, monkeypatch):
    original = tmp_path / "scan.pdf"
    _write_image_only_pdf(original)
    before_hash = _sha(original)

    def fail_ocr(input_pdf, temp_output, **kwargs):
        raise ocr_pdf.OcrProcessError("ocr_failed", "fallo", returncode=1)

    monkeypatch.setattr(ocr_pdf, "run_ocrmypdf_process", fail_ocr)

    with pytest.raises(ocr_pdf.OcrProcessError):
        ocr_pdf.process_one_pdf(original, tmp_path)

    assert _sha(original) == before_hash
    assert not pdf_has_extractable_text(original)
    assert list(tmp_path.glob(".docflow_ocr_*")) == []


def test_failure_during_validation_preserves_original_hash(tmp_path, monkeypatch):
    original = tmp_path / "scan.pdf"
    _write_image_only_pdf(original)
    before_hash = _sha(original)

    def write_invalid_output(input_pdf, temp_output, **kwargs):
        temp_output.write_bytes(b"%PDF-1.4 broken")
        return 0, 0.01

    monkeypatch.setattr(ocr_pdf, "run_ocrmypdf_process", write_invalid_output)

    with pytest.raises(OcrValidationError):
        ocr_pdf.process_one_pdf(original, tmp_path)

    assert _sha(original) == before_hash
    assert not pdf_has_extractable_text(original)
    assert list(tmp_path.glob(".docflow_ocr_*")) == []


def test_failure_during_replace_preserves_original_hash(tmp_path, monkeypatch):
    original = tmp_path / "scan.pdf"
    _write_image_only_pdf(original)
    before_hash = _sha(original)
    monkeypatch.setattr(ocr_pdf, "run_ocrmypdf_process", _fake_ocr_text_output)

    def fail_replace(src, dst):
        raise OSError("replace failed")

    monkeypatch.setattr("scripts.common.ocr_io.os.replace", fail_replace)

    with pytest.raises(OSError):
        ocr_pdf.process_one_pdf(original, tmp_path)

    assert _sha(original) == before_hash
    assert not pdf_has_extractable_text(original)
    assert list(tmp_path.glob(".docflow_ocr_*")) == []


def test_cancel_before_promotion_preserves_original_hash(tmp_path, monkeypatch):
    original = tmp_path / "scan.pdf"
    _write_image_only_pdf(original)
    before_hash = _sha(original)
    state = {"checks": 0}

    def cancel_after_ocr():
        state["checks"] += 1
        return state["checks"] >= 2

    monkeypatch.setattr(ocr_pdf, "run_ocrmypdf_process", _fake_ocr_text_output)

    result = ocr_pdf.process_one_pdf(original, tmp_path, is_cancelled=cancel_after_ocr)

    assert _sha(original) == before_hash
    assert result.status == "cancelled"
    assert not pdf_has_extractable_text(original)
    assert list(tmp_path.glob(".docflow_ocr_*")) == []
    assert list(tmp_path.glob("*_ocr.pdf")) == []


def test_symlink_equivalent_output_to_source_is_rejected(tmp_path, monkeypatch):
    original = tmp_path / "scan.pdf"
    _write_image_only_pdf(original)
    link = tmp_path / "scan_ocr.pdf"
    link.symlink_to(original)
    before_hash = _sha(original)

    monkeypatch.setattr(ocr_pdf, "resolve_output_path", lambda output_dir, source_name: link)

    with pytest.raises(OcrValidationError) as excinfo:
        ocr_pdf.process_one_pdf(original, tmp_path)

    assert excinfo.value.category == "output_matches_source"
    assert _sha(original) == before_hash
    assert link.is_symlink()


def test_dotdot_equivalent_output_to_source_is_rejected(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "input" / "out"
    output_dir.mkdir(parents=True)
    original = input_dir / "scan.pdf"
    _write_image_only_pdf(original)
    candidate = output_dir / ".." / "scan.pdf"
    before_hash = _sha(original)

    monkeypatch.setattr(ocr_pdf, "resolve_output_path", lambda output_dir, source_name: candidate)

    with pytest.raises(OcrValidationError) as excinfo:
        ocr_pdf.process_one_pdf(original, output_dir)

    assert excinfo.value.category == "output_matches_source"
    assert _sha(original) == before_hash


def test_script_runner_flow_preserves_original_and_reports_generated_file(tmp_path, monkeypatch):
    from core.script_runner import ScriptRunner

    original = tmp_path / "entrada" / "scan.pdf"
    original.parent.mkdir()
    _write_image_only_pdf(original)
    dest = tmp_path / "destino"
    dest.mkdir()
    _mock_runtime(monkeypatch)
    monkeypatch.setattr(ocr_pdf, "run_ocrmypdf_process", _fake_ocr_text_output)

    before_hash = _sha(original)
    done = threading.Event()
    captured = {}

    def wrapped_run(progress=None, is_cancelled=None):
        return ocr_pdf.run(
            progress=progress,
            is_cancelled=is_cancelled,
            pdf_paths=[original],
            output_dir=dest,
        )

    runner = ScriptRunner()
    runner.run(
        funcion=wrapped_run,
        progress=lambda actual, total: None,
        is_cancelled=lambda: False,
        on_success=lambda result: captured.setdefault("success", result),
        on_error=lambda error: captured.setdefault("error", error),
        on_cancelled=lambda result: captured.setdefault("cancelled", result),
        on_finally=done.set,
    )

    assert done.wait(5)
    assert "error" not in captured
    assert "cancelled" not in captured
    result = captured["success"]
    generated = Path(result["files"][0])
    assert _sha(original) == before_hash
    assert not pdf_has_extractable_text(original)
    assert generated.resolve() != original.resolve()
    assert generated.parent.resolve() == dest.resolve()
    assert pdf_has_extractable_text(generated)


# ---------------------------------------------------------------------------
# Regresión crítica: contabilidad OCR por resultado final real
# ---------------------------------------------------------------------------


def test_batch_two_valid_pdfs_count_two_unique_outputs(tmp_path, monkeypatch):
    pdfs = []
    for folder in ("a", "b"):
        source = tmp_path / folder / "scan.pdf"
        source.parent.mkdir()
        _write_image_only_pdf(source)
        pdfs.append(source)
    dest = tmp_path / "out"
    dest.mkdir()
    _mock_runtime(monkeypatch)
    monkeypatch.setattr(ocr_pdf, "run_ocrmypdf_process", _fake_ocr_text_output)

    result = ocr_pdf.run(pdf_paths=pdfs, output_dir=dest)

    outputs = [Path(p) for p in result["files"]]
    assert result["stats"] == {
        "total": 2,
        "procesados": 2,
        "errores": 0,
        "omitidos": 0,
        "detalles": [],
    }
    assert len(outputs) == 2
    assert len({p.resolve() for p in outputs}) == 2
    assert all(p.is_file() for p in outputs)
    assert sorted(p.name for p in outputs) == ["scan_ocr.pdf", "scan_ocr_v2.pdf"]


def test_batch_documento_a_b_creates_two_distinct_final_outputs(tmp_path, monkeypatch):
    input_dir = tmp_path / "entrada"
    dest = tmp_path / "salida"
    input_dir.mkdir()
    dest.mkdir()
    first = input_dir / "documento_a.pdf"
    second = input_dir / "documento_b.pdf"
    _write_image_only_pdf(first)
    _write_image_only_pdf(second)
    _mock_runtime(monkeypatch)
    monkeypatch.setattr(ocr_pdf, "run_ocrmypdf_process", _fake_ocr_text_output)

    result = ocr_pdf.run(pdf_paths=[first, second], output_dir=dest)

    outputs = [Path(p) for p in result["files"]]
    resolved = [p.resolve() for p in outputs]
    real_files = sorted(dest.glob("*.pdf"))
    inodes = [p.stat().st_ino for p in outputs]
    assert result["stats"] == {
        "total": 2,
        "procesados": 2,
        "errores": 0,
        "omitidos": 0,
        "detalles": [],
    }
    assert len(outputs) == 2
    assert len(set(resolved)) == 2
    assert len(set(inodes)) == 2
    assert sorted(p.name for p in outputs) == [
        "documento_a_ocr.pdf",
        "documento_b_ocr.pdf",
    ]
    assert real_files == sorted(outputs)
    assert all(p.is_file() for p in outputs)


def test_batch_same_returned_output_never_counts_two_processed(tmp_path, monkeypatch):
    input_dir = tmp_path / "entrada"
    dest = tmp_path / "salida"
    input_dir.mkdir()
    dest.mkdir()
    first = input_dir / "documento_a.pdf"
    second = input_dir / "documento_b.pdf"
    _write_minimal_pdf(first)
    _write_minimal_pdf(second)
    shared = dest / "documento_a_ocr.pdf"
    _write_minimal_pdf(shared, "resultado compartido")
    _mock_runtime(monkeypatch)

    def duplicate_result(input_pdf, output_dir, **kwargs):
        return ocr_pdf.OCRFileResult(
            source=input_pdf,
            status="processed",
            output_path=shared,
        )

    monkeypatch.setattr(ocr_pdf, "process_one_pdf", duplicate_result)

    result = ocr_pdf.run(pdf_paths=[first, second], output_dir=dest)

    assert result["message"] == "Proceso finalizado con incidencias"
    assert result["stats"]["procesados"] != 2
    assert result["stats"]["procesados"] == 1
    assert result["stats"]["errores"] == 1
    assert len(result["files"]) == 1
    assert len({Path(p).resolve() for p in result["files"]}) == 1


def test_batch_valid_and_invalid_counts_partial_failure(tmp_path, monkeypatch):
    ok = tmp_path / "ok.pdf"
    bad = tmp_path / "bad.pdf"
    _write_image_only_pdf(ok)
    bad.write_bytes(b"not a pdf")
    dest = tmp_path / "out"
    dest.mkdir()
    _mock_runtime(monkeypatch)

    def fake_ocr(input_pdf, temp_output, **kwargs):
        if input_pdf == bad:
            raise ocr_pdf.OcrProcessError("input_error", "fallo", returncode=3)
        _write_minimal_pdf(temp_output, "DocFlow OK")
        return 0, 0.01

    monkeypatch.setattr(ocr_pdf, "run_ocrmypdf_process", fake_ocr)

    result = ocr_pdf.run(pdf_paths=[ok, bad], output_dir=dest)

    assert result["message"] == "Proceso finalizado con incidencias"
    assert result["stats"]["total"] == 2
    assert result["stats"]["procesados"] == 1
    assert result["stats"]["errores"] == 1
    assert result["stats"]["omitidos"] == 0
    assert len(result["files"]) == 1
    assert Path(result["files"][0]).is_file()


def test_batch_valid_and_already_text_counts_skipped(tmp_path, monkeypatch):
    ok = tmp_path / "ok.pdf"
    skipped = tmp_path / "skipped.pdf"
    _write_image_only_pdf(ok)
    _write_minimal_pdf(skipped, "ya tiene texto")
    dest = tmp_path / "out"
    dest.mkdir()
    _mock_runtime(monkeypatch)

    def fake_ocr(input_pdf, temp_output, **kwargs):
        if input_pdf == skipped:
            raise ocr_pdf.OcrProcessError("already_has_text", "omitido", returncode=6)
        _write_minimal_pdf(temp_output, "DocFlow OK")
        return 0, 0.01

    monkeypatch.setattr(ocr_pdf, "run_ocrmypdf_process", fake_ocr)

    result = ocr_pdf.run(pdf_paths=[ok, skipped], output_dir=dest)

    assert result["message"] == "Proceso finalizado con incidencias"
    assert result["stats"]["procesados"] == 1
    assert result["stats"]["errores"] == 0
    assert result["stats"]["omitidos"] == 1
    assert len(result["files"]) == 1


def test_ocr_returncode_zero_without_output_is_error_not_processed(tmp_path, monkeypatch):
    source = tmp_path / "scan.pdf"
    _write_image_only_pdf(source)
    dest = tmp_path / "out"
    dest.mkdir()
    _mock_runtime(monkeypatch)

    def fake_ocr(input_pdf, temp_output, **kwargs):
        return 0, 0.01

    monkeypatch.setattr(ocr_pdf, "run_ocrmypdf_process", fake_ocr)

    result = ocr_pdf.run(pdf_paths=[source], output_dir=dest)

    assert result["message"] == "No se generó ningún PDF OCR válido"
    assert result["stats"]["procesados"] == 0
    assert result["stats"]["errores"] == 1
    assert result["files"] == []


def test_output_created_outside_destination_is_error(tmp_path, monkeypatch):
    source = tmp_path / "scan.pdf"
    _write_minimal_pdf(source)
    dest = tmp_path / "out"
    dest.mkdir()
    outside = tmp_path / "outside.pdf"
    _write_minimal_pdf(outside, "fuera")
    _mock_runtime(monkeypatch)
    monkeypatch.setattr(
        ocr_pdf,
        "process_one_pdf",
        lambda *args, **kwargs: ocr_pdf.OCRFileResult(
            source=source,
            status="processed",
            output_path=outside,
        ),
    )

    result = ocr_pdf.run(pdf_paths=[source], output_dir=dest)

    assert result["stats"]["procesados"] == 0
    assert result["stats"]["errores"] == 1
    assert result["files"] == []


def test_output_equal_to_input_is_error_in_batch(tmp_path, monkeypatch):
    source = tmp_path / "scan.pdf"
    _write_minimal_pdf(source)
    _mock_runtime(monkeypatch)
    monkeypatch.setattr(
        ocr_pdf,
        "process_one_pdf",
        lambda *args, **kwargs: ocr_pdf.OCRFileResult(
            source=source,
            status="processed",
            output_path=source,
        ),
    )

    result = ocr_pdf.run(pdf_paths=[source], output_dir=tmp_path)

    assert result["stats"]["procesados"] == 0
    assert result["stats"]["errores"] == 1
    assert result["files"] == []


def test_final_page_validation_failure_is_error(tmp_path, monkeypatch):
    source = tmp_path / "scan.pdf"
    _write_minimal_pdf(source)
    dest = tmp_path / "out"
    dest.mkdir()
    _mock_runtime(monkeypatch)

    def two_page_output(input_pdf, temp_output, **kwargs):
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(str(temp_output), pagesize=A4)
        c.drawString(72, 720, "pagina uno")
        c.showPage()
        c.drawString(72, 720, "pagina dos")
        c.save()
        return 0, 0.01

    monkeypatch.setattr(ocr_pdf, "run_ocrmypdf_process", two_page_output)

    result = ocr_pdf.run(pdf_paths=[source], output_dir=dest)

    assert result["stats"]["procesados"] == 0
    assert result["stats"]["errores"] == 1
    assert result["files"] == []


def test_final_text_validation_failure_is_error(tmp_path, monkeypatch):
    source = tmp_path / "scan.pdf"
    _write_image_only_pdf(source)
    dest = tmp_path / "out"
    dest.mkdir()
    _mock_runtime(monkeypatch)

    def blank_output(input_pdf, temp_output, **kwargs):
        from pypdf import PdfWriter

        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        with temp_output.open("wb") as fh:
            writer.write(fh)
        return 0, 0.01

    monkeypatch.setattr(ocr_pdf, "run_ocrmypdf_process", blank_output)

    result = ocr_pdf.run(pdf_paths=[source], output_dir=dest)

    assert result["stats"]["procesados"] == 0
    assert result["stats"]["errores"] == 1
    assert result["files"] == []


def test_duplicate_generated_file_is_detected(tmp_path, monkeypatch):
    first = tmp_path / "a.pdf"
    second = tmp_path / "b.pdf"
    _write_minimal_pdf(first)
    _write_minimal_pdf(second)
    dest = tmp_path / "out"
    dest.mkdir()
    shared = dest / "shared_ocr.pdf"
    _write_minimal_pdf(shared, "compartido")
    _mock_runtime(monkeypatch)

    def duplicate_result(input_pdf, output_dir, **kwargs):
        return ocr_pdf.OCRFileResult(
            source=input_pdf,
            status="processed",
            output_path=shared,
        )

    monkeypatch.setattr(ocr_pdf, "process_one_pdf", duplicate_result)

    result = ocr_pdf.run(pdf_paths=[first, second], output_dir=dest)

    assert result["message"] == "Proceso finalizado con incidencias"
    assert result["stats"]["procesados"] == 1
    assert result["stats"]["errores"] == 1
    assert len(result["files"]) == 1


def test_inconsistent_generated_files_prevents_total_success(tmp_path, monkeypatch):
    source = tmp_path / "scan.pdf"
    _write_minimal_pdf(source)
    dest = tmp_path / "out"
    dest.mkdir()
    final = dest / "scan_ocr.pdf"
    _write_minimal_pdf(final, "ok")
    _mock_runtime(monkeypatch)
    monkeypatch.setattr(
        ocr_pdf,
        "process_one_pdf",
        lambda *args, **kwargs: ocr_pdf.OCRFileResult(
            source=source,
            status="processed",
            output_path=final,
        ),
    )
    monkeypatch.setattr(ocr_pdf, "_unique_existing_files_in_destination", lambda files, output_dir: [])

    result = ocr_pdf.run(pdf_paths=[source], output_dir=dest)

    assert result["message"] == "No se generó ningún PDF OCR válido"
    assert result["stats"]["procesados"] == 0
    assert result["stats"]["errores"] == 1
    assert result["files"] == []


def test_script_runner_preserves_cancelled_ocr_stats(tmp_path, monkeypatch):
    from core.script_runner import ScriptRunner

    first = tmp_path / "a.pdf"
    second = tmp_path / "b.pdf"
    _write_minimal_pdf(first)
    _write_minimal_pdf(second)
    dest = tmp_path / "out"
    dest.mkdir()
    _mock_runtime(monkeypatch)
    state = {"n": 0}

    def process_then_cancel(input_pdf, output_dir, **kwargs):
        state["n"] += 1
        if state["n"] == 2:
            return ocr_pdf.OCRFileResult(source=input_pdf, status="cancelled")
        out = output_dir / f"{input_pdf.stem}_ocr.pdf"
        _write_minimal_pdf(out, "DocFlow ok")
        return ocr_pdf.OCRFileResult(source=input_pdf, status="processed", output_path=out)

    monkeypatch.setattr(ocr_pdf, "process_one_pdf", process_then_cancel)
    done = threading.Event()
    captured = {}

    def wrapped_run(progress=None, is_cancelled=None):
        return ocr_pdf.run(
            progress=progress,
            is_cancelled=is_cancelled,
            pdf_paths=[first, second],
            output_dir=dest,
        )

    ScriptRunner().run(
        funcion=wrapped_run,
        progress=lambda actual, total: None,
        is_cancelled=lambda: False,
        on_success=lambda result: captured.setdefault("success", result),
        on_error=lambda error: captured.setdefault("error", error),
        on_cancelled=lambda result: captured.setdefault("cancelled", result),
        on_finally=done.set,
    )

    assert done.wait(5)
    assert "error" not in captured
    assert "success" not in captured
    result = captured["cancelled"]
    assert result["message"] == "Cancelado"
    assert result["stats"]["total"] == 2
    assert result["stats"]["procesados"] == 1
    assert result["stats"]["errores"] == 0
    assert result["stats"]["omitidos"] == 1
    assert len(result["files"]) == 1
