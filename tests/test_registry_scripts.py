from scripts.registry import get_scripts


def test_dni_tool_not_registered():
    pdf_scripts = get_scripts("PDF")
    assert "Unir PDFs por DNI" not in pdf_scripts
    assert "unir_pdfs_por_nombre_dni" not in {
        module.__name__ for module in pdf_scripts.values()
    }


def test_eml_tool_still_registered():
    eml_scripts = get_scripts("EML")
    assert "EML a PDF" in eml_scripts


def test_mbox_tools_still_registered():
    mbox_scripts = get_scripts("MBOX")
    assert "Extraer adjuntos de MBOX" in mbox_scripts
    assert "MBOX a EML" in mbox_scripts
