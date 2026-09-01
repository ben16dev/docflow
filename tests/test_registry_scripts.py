from scripts.metadata import VALID_CATEGORIES, extract_metadata
from scripts.pdf import img_a_pdf, ocr_pdf
from scripts.registry import get_scripts


def test_dni_tool_not_registered():
    pdf_scripts = get_scripts("PDF")
    assert "Unir PDFs por DNI" not in pdf_scripts
    assert "unir_pdfs_por_nombre_dni" not in {
        module.__name__ for module in pdf_scripts.values()
    }


def test_mbox_and_eml_categories_empty():
    """Las categorías MBOX y EML ya no existen en el registro."""
    assert get_scripts("MBOX") == {}
    assert get_scripts("EML") == {}


def test_mbox_tools_in_conversion():
    """Herramientas MBOX ahora registradas en CONVERSIÓN."""
    conversion_scripts = get_scripts("CONVERSIÓN")
    assert "Extraer adjuntos de MBOX" in conversion_scripts
    assert "MBOX a EML" in conversion_scripts


def test_eml_tool_in_conversion():
    """Herramienta EML ahora registrada en CONVERSIÓN."""
    conversion_scripts = get_scripts("CONVERSIÓN")
    assert "EML a PDF" in conversion_scripts


def test_imagen_a_pdf_moved_to_conversion():
    assert "Imagen a PDF" not in get_scripts("PDF")
    conversion_scripts = get_scripts("CONVERSIÓN")
    assert "Imagen a PDF" in conversion_scripts
    assert conversion_scripts["Imagen a PDF"] is img_a_pdf


def test_ocr_pdf_registered_in_conversion():
    conversion_scripts = get_scripts("CONVERSIÓN")
    assert "PDF escaneado a PDF OCR" in conversion_scripts
    assert conversion_scripts["PDF escaneado a PDF OCR"] is ocr_pdf
    assert "PDF escaneado a PDF OCR" not in get_scripts("PDF")


def test_conversion_category_is_valid():
    assert "CONVERSIÓN" in VALID_CATEGORIES


def test_mbox_and_eml_not_valid_categories():
    """MBOX y EML ya no son categorías válidas."""
    assert "MBOX" not in VALID_CATEGORIES
    assert "EML" not in VALID_CATEGORIES


def test_conversion_has_five_tools():
    """CONVERSIÓN contiene exactamente 5 herramientas."""
    conversion_scripts = get_scripts("CONVERSIÓN")
    assert len(conversion_scripts) == 5


def test_no_duplicate_tools_in_conversion():
    """No hay herramientas duplicadas en CONVERSIÓN."""
    conversion_scripts = get_scripts("CONVERSIÓN")
    names = list(conversion_scripts.keys())
    assert len(names) == len(set(names))


def test_img_a_pdf_metadata_category():
    meta = extract_metadata(img_a_pdf)
    assert meta["category"] == "CONVERSIÓN"
    assert meta["name"] == "Imagen a PDF"


def test_ocr_pdf_metadata_category():
    meta = extract_metadata(ocr_pdf)
    assert meta["category"] == "CONVERSIÓN"
    assert meta["name"] == "PDF escaneado a PDF OCR"
