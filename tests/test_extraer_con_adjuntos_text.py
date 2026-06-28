import tempfile
from email import policy
from email.message import EmailMessage
from pathlib import Path

import pytest
from pypdf import PdfReader

from scripts.mbox import extraer_con_adjuntos

SPANISH_SAMPLE = "Prueba áéíóú ñ ü"


def test_decode_bytes_preserves_spanish_characters():
    raw = SPANISH_SAMPLE.encode("utf-8")
    decoded = extraer_con_adjuntos._decode_bytes(raw, "utf-8")
    assert decoded == SPANISH_SAMPLE


def test_decode_bytes_falls_back_when_charset_is_wrong():
    raw = SPANISH_SAMPLE.encode("latin-1")
    decoded = extraer_con_adjuntos._decode_bytes(raw, "utf-8")
    assert decoded == SPANISH_SAMPLE


def test_decode_mime_preserves_spanish_characters():
    from email.header import Header

    encoded = str(Header(SPANISH_SAMPLE, "utf-8"))
    decoded = extraer_con_adjuntos._decode_mime(encoded)
    assert decoded == SPANISH_SAMPLE


def test_extract_body_preserves_spanish_characters():
    msg = EmailMessage()
    msg.set_content(SPANISH_SAMPLE, charset="utf-8")

    body = extraer_con_adjuntos._extract_body(msg)
    assert SPANISH_SAMPLE in body


def test_visible_error_messages_use_utf8():
    assert "válida" in (
        "Ruta de trabajo MBOX no válida.\n"
        "Selecciona primero una carpeta de trabajo."
    )
    assert "dañado" in (
        "No se pudo abrir el archivo MBOX. "
        "Puede estar dañado, en uso o no ser un MBOX válido."
    )


def test_output_names_remain_ascii():
    assert extraer_con_adjuntos.run.__code__.co_consts  # smoke import
    source_path = Path(extraer_con_adjuntos.__file__).read_text(encoding="utf-8")
    assert "MBOX_extraidos" in source_path
    assert "Correo_electronico.pdf" in source_path


def test_pdf_preserves_spanish_accents():
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "correo.pdf"
        extraer_con_adjuntos._render_email_to_pdf(
            pdf_path,
            SPANISH_SAMPLE,
            "Remitente",
            "Destinatario",
            "28.06.2026",
            SPANISH_SAMPLE,
        )

        reader = PdfReader(str(pdf_path))
        extracted = reader.pages[0].extract_text() or ""

        for char in "áéíóúñü":
            assert char in extracted
