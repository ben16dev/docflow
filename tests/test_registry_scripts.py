from scripts.metadata import VALID_CATEGORIES, extract_metadata
from scripts.pdf import img_a_pdf
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


def test_imagen_a_pdf_moved_to_conversion():
    assert "Imagen a PDF" not in get_scripts("PDF")
    conversion_scripts = get_scripts("CONVERSIÓN")
    assert "Imagen a PDF" in conversion_scripts
    assert conversion_scripts["Imagen a PDF"] is img_a_pdf


def test_conversion_category_is_valid():
    assert "CONVERSIÓN" in VALID_CATEGORIES


def test_img_a_pdf_metadata_category():
    meta = extract_metadata(img_a_pdf)
    assert meta["category"] == "CONVERSIÓN"
    assert meta["name"] == "Imagen a PDF"
