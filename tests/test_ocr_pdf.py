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
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.common.ocr_io import (
    make_temp_pdf_path,
    promote_temp_to_final,
    resolve_output_path,
    safe_unlink,
    validate_ocr_output,
)
from scripts.common.ocr_runtime import (
    OCR_BASE_FLAGS,
    OcrDependencyError,
    build_ocr_command,
    build_subprocess_env,
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
    assert cmd[0] == "/fake/ocrmypdf"
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
        out.write_bytes(b"%PDF-1.4 fake")
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
    assert progress_log[0] == (0, 3)
    assert progress_log[-1] == (3, 3)


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
        out.write_bytes(b"%PDF")
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
    with pytest.raises(CancelledByUser):
        ocr_pdf.process_one_pdf(original, dest, is_cancelled=lambda: False)
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
        out.write_bytes(b"%PDF")
        return out

    monkeypatch.setattr(ocr_pdf, "process_one_pdf", fake_process)

    with caplog.at_level(logging.INFO):
        ocr_pdf.run(pdf_paths=[pdf], output_dir=dest)

    joined = " ".join(r.message for r in caplog.records)
    assert str(pdf.resolve()) not in joined
    assert str(dest.resolve()) not in joined
    assert "DATOS CONFIDENCIALES" not in joined
    assert "documento_secreto_cliente" not in joined


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
    assert env["TESSDATA_PREFIX"] == "/opt/homebrew/share/tessdata"
    assert env["PATH"].startswith("/opt/homebrew/bin")
    assert dict(os.environ) == before
    assert os.environ.get("TESSDATA_PREFIX") == before.get("TESSDATA_PREFIX")


def test_safe_unlink_missing():
    safe_unlink(Path("/tmp/docflow_no_existe_xyz.pdf"))
