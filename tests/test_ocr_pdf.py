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
    assert result["stats"]["procesados"] == len(result["files"])
    assert all(Path(f).is_file() for f in result["files"])
    assert all(Path(f).parent == dest for f in result["files"])
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

    with pytest.raises(RuntimeError, match="No se pudo generar ningún PDF OCR"):
        ocr_pdf.run(pdf_paths=[pdf], output_dir=dest)

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

    with pytest.raises(RuntimeError, match="No se pudo generar ningún PDF OCR"):
        ocr_pdf.run(pdf_paths=[pdf], output_dir=dest)

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
        out.write_bytes(b"%PDF-1.4 ok")
        return out

    monkeypatch.setattr(ocr_pdf, "process_one_pdf", selective)

    result = ocr_pdf.run(pdf_paths=pdfs, output_dir=dest)

    assert result["stats"]["procesados"] == 1
    assert result["stats"]["errores"] == 1
    assert result["stats"]["procesados"] == len(result["files"])
    assert all(Path(f).is_file() for f in result["files"])
    assert all(Path(f).parent.resolve() == dest.resolve() for f in result["files"])
    assert "con error" in result["message"]
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

    with pytest.raises(RuntimeError, match="No se pudo generar ningún PDF OCR"):
        ocr_pdf.run(pdf_paths=[pdf], output_dir=dest)


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
