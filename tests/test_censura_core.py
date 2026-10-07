"""
Tests de "Censurar PDF por palabras" (fail-closed): núcleo + lote.

Todos los PDFs son sintéticos y se generan con PyMuPDF en tmp_path.
"""

from __future__ import annotations

import hashlib
import inspect
import logging
import re
import sys
from pathlib import Path

import fitz
import pytest

from scripts.metadata import extract_metadata
from scripts.pdf import censura_core as core
from scripts.pdf import censurar_pdf_por_palabras as script
from scripts.pdf.censura_core import (
    EstadoCensura,
    MotivoCensura,
    ResultadoCensura,
    ResumenLote,
    censurar_pdf,
    detectar_importes_auto,
    normalizar_texto,
    validar_terminos,
)
from ui.exceptions import CancelledByUser

TERMINO = "ZORRILLO"


# ---------------------------------------------------------------------------
# Generadores de PDFs sintéticos
# ---------------------------------------------------------------------------


def _escribir(page, lineas, *, y0=100, fuente="helv", tam=12):
    """Escribe líneas de texto Unicode (TextWriter) en la página."""
    if isinstance(lineas, str):
        lineas = lineas.split("\n")
    tw = fitz.TextWriter(page.rect)
    font = fitz.Font(fuente)
    for i, linea in enumerate(lineas):
        tw.append((72, y0 + i * 16), linea, font=font, fontsize=tam)
    tw.write_text(page)


def _insertar_imagen_renderizada(doc, texto):
    """Página que solo contiene la imagen renderizada de un texto (escaneo simulado)."""
    src = fitz.open()
    sp = src.new_page()
    _escribir(sp, texto, tam=20)
    pix = sp.get_pixmap(dpi=72)
    src.close()
    page = doc.new_page()
    page.insert_image(page.rect, pixmap=pix)
    return page


def _crear_pdf(path: Path, paginas, *, metadata=None, toc=None, xmp=None, adjunto=False):
    """paginas: lista de str (texto) o None (página en blanco)."""
    doc = fitz.open()
    for texto in paginas:
        page = doc.new_page()
        if texto:
            _escribir(page, texto)
    if metadata:
        doc.set_metadata(metadata)
    if toc:
        doc.set_toc(toc)
    if xmp:
        doc.set_xml_metadata(xmp)
    if adjunto:
        doc.embfile_add("adjunto.txt", f"contenido {TERMINO}".encode(), filename="adjunto.txt")
    doc.save(str(path))
    doc.close()
    return path


def _crear_pdf_solo_imagen(path: Path, texto=f"cliente {TERMINO}"):
    doc = fitz.open()
    _insertar_imagen_renderizada(doc, texto)
    doc.save(str(path))
    doc.close()
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _archivos(carpeta: Path):
    return sorted(p.name for p in carpeta.iterdir()) if carpeta.exists() else []


def _texto_pdf(path: Path) -> str:
    doc = fitz.open(str(path))
    try:
        return "\n".join(p.get_text() for p in doc)
    finally:
        doc.close()


def _sin_temporales(carpeta: Path) -> bool:
    return not list(carpeta.glob(".docflow_censura_*")) if carpeta.exists() else True


@pytest.fixture
def log_docflow(caplog):
    """El logger de DocFlow no propaga: se engancha el handler de caplog directamente."""
    base = logging.getLogger("DocFlow")
    base.addHandler(caplog.handler)
    caplog.set_level(logging.DEBUG, logger="DocFlow")
    yield caplog
    base.removeHandler(caplog.handler)


# ---------------------------------------------------------------------------
# Normalización y términos
# ---------------------------------------------------------------------------


def test_normalizar_texto_casefold_espacios_y_guiones():
    assert normalizar_texto("  CONFIDEN-\n  cial   ") == "confidencial"
    assert normalizar_texto("Juan\u00a0\n Pérez") == "juan pérez"
    assert normalizar_texto("o\ufb01cina") == "oficina"          # NFKC: ligadura
    assert normalizar_texto("con\u00adfidencial") == "confidencial"  # guion blando
    assert normalizar_texto(None) == ""


def test_normalizar_sin_unir_guiones_conserva_el_guion():
    assert normalizar_texto("pérez- garcía", unir_guiones=False) == "pérez- garcía"
    assert normalizar_texto("pérez- garcía", unir_guiones=True) == "pérezgarcía"


def test_validar_terminos_lista_vacia_sin_importes_es_error():
    with pytest.raises(ValueError):
        validar_terminos([], detectar_importes=False)
    with pytest.raises(ValueError):
        validar_terminos(["  ", "\u200b"], detectar_importes=False)


def test_validar_terminos_lista_vacia_con_importes_se_permite():
    assert validar_terminos([], detectar_importes=True) == []


def test_validar_terminos_deduplica_sin_distinguir_mayusculas():
    assert validar_terminos(["Ana", " ana ", "ANA", "Luis"], False) == ["Ana", "Luis"]


def test_core_rechaza_lista_vacia_sin_importes(tmp_path):
    pdf = _crear_pdf(tmp_path / "a.pdf", [f"cliente {TERMINO}"])
    with pytest.raises(ValueError):
        censurar_pdf(pdf, tmp_path / "out", [], detectar_importes=False)
    assert _archivos(tmp_path / "out") == []


# ---------------------------------------------------------------------------
# Regla "Siendo X € lo pagado"
# ---------------------------------------------------------------------------


def test_importes_calcula_15_y_85():
    texto = "Siendo 1.000,00 € lo pagado.\nHonorarios 150,00 €\nResto 850,00 €\nOtro 12,00 €"
    assert detectar_importes_auto(texto) == ["150,00 €", "850,00 €"]


def test_importes_sin_patron_devuelve_vacio():
    assert detectar_importes_auto("Documento sin ese patrón. 150,00 €") == []


@pytest.mark.parametrize(
    "frase",
    [
        "Siendo 1,234.56 € lo pagado",    # formato anglosajón: ambiguo, no se adivina
        "Siendo abc lo pagado",
        "Siendo 1.000,00 lo pagado",      # sin símbolo €
        "Siendo 12.34.56 € lo pagado",
    ],
)
def test_importes_presente_pero_no_interpretable_lanza(frase):
    with pytest.raises(core.ImporteNoInterpretable):
        detectar_importes_auto(frase)


def test_pdf_con_siendo_no_interpretable_es_error_sin_archivo(tmp_path):
    pdf = _crear_pdf(tmp_path / "a.pdf", ["Siendo 1,234.56 € lo pagado\nOtra cosa 150,00 €"])
    dest = tmp_path / "out"
    r = censurar_pdf(pdf, dest, ["Otra"], detectar_importes=True)
    assert r.estado == EstadoCensura.ERROR
    assert r.motivo == MotivoCensura.IMPORTE_NO_INTERPRETABLE
    assert _archivos(dest) == []


def test_pdf_con_siendo_no_interpretable_no_falla_si_casilla_desactivada(tmp_path):
    pdf = _crear_pdf(tmp_path / "a.pdf", ["Siendo 1,234.56 € lo pagado\nCliente ZORRILLO"])
    r = censurar_pdf(pdf, tmp_path / "out", [TERMINO], detectar_importes=False)
    assert r.estado == EstadoCensura.PROCESADO


def test_pdf_con_importes_automaticos_se_censura(tmp_path):
    pdf = _crear_pdf(
        tmp_path / "a.pdf",
        ["Siendo 1.000,00 € lo pagado\nHonorarios 150,00 €\nResto 850,00 €\nTotal 999,99 €"],
    )
    r = censurar_pdf(pdf, tmp_path / "out", [], detectar_importes=True)
    assert r.estado == EstadoCensura.PROCESADO
    texto = _texto_pdf(r.output_path)
    assert "150,00" not in texto and "850,00" not in texto
    assert "999,99" in texto  # lo que no es 15 %/85 % se conserva


def test_lista_vacia_con_importes_y_sin_patron_es_omitido(tmp_path):
    pdf = _crear_pdf(tmp_path / "a.pdf", ["Documento cualquiera"])
    r = censurar_pdf(pdf, tmp_path / "out", [], detectar_importes=True)
    assert r.estado == EstadoCensura.OMITIDO
    assert r.motivo == MotivoCensura.SIN_COINCIDENCIAS
    assert _archivos(tmp_path / "out") == []


# ---------------------------------------------------------------------------
# Caso base: PDF digital
# ---------------------------------------------------------------------------

XMP = (
    '<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
    'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    '<rdf:Description xmlns:dc="http://purl.org/dc/elements/1.1/">'
    "<dc:creator><rdf:Seq><rdf:li>Autor ZORRILLO</rdf:li></rdf:Seq></dc:creator>"
    "</rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end='w'?>"
)


def test_pdf_digital_procesado_sin_rastro(tmp_path):
    pdf = _crear_pdf(
        tmp_path / "expediente.pdf",
        [f"Cliente {TERMINO} con DNI 1234\nOtra línea", "Segunda página sin nada"],
        metadata={"author": f"Autor {TERMINO}", "title": "Titulo", "keywords": "k"},
        xmp=XMP,
        adjunto=True,
    )
    dest = tmp_path / "out"
    original_hash = _sha(pdf)

    r = censurar_pdf(pdf, dest, [TERMINO], detectar_importes=False)

    assert r.estado == EstadoCensura.PROCESADO
    assert r.motivo == MotivoCensura.OK
    assert r.coincidencias >= 1
    assert r.paginas_afectadas == 1
    assert r.terminos_sin_coincidencias == 0
    assert r.output_path is not None and r.output_path.is_file()
    assert r.output_path.parent == dest
    assert r.output_path.name == "expediente_censurado.pdf"
    assert _sin_temporales(dest)

    salida = fitz.open(str(r.output_path))
    try:
        assert salida.page_count == 2
        for page in salida:
            assert page.search_for(TERMINO) == []
        assert TERMINO.lower() not in normalizar_texto(_texto_pdf(r.output_path))
        assert not any(v for k, v in salida.metadata.items() if k not in ("format", "encryption"))
        assert (salida.get_xml_metadata() or "").strip() == ""
        assert salida.embfile_count() == 0
        # Lo que no era sensible se conserva.
        assert "Otra línea" in _texto_pdf(r.output_path)
    finally:
        salida.close()

    assert _sha(pdf) == original_hash


def test_original_no_se_modifica_en_ningun_estado(tmp_path):
    ok = _crear_pdf(tmp_path / "ok.pdf", [f"x {TERMINO}"])
    vacio = _crear_pdf(tmp_path / "vacio.pdf", ["nada"])
    img = _crear_pdf_solo_imagen(tmp_path / "img.pdf")
    hashes = {p: _sha(p) for p in (ok, vacio, img)}
    for p in (ok, vacio, img):
        censurar_pdf(p, tmp_path / "out", [TERMINO], detectar_importes=False)
    assert {p: _sha(p) for p in hashes} == hashes


# ---------------------------------------------------------------------------
# Capa de texto, imágenes y vectoriales
# ---------------------------------------------------------------------------


def test_pdf_solo_imagen_es_error_sin_capa_texto_y_sin_archivo(tmp_path):
    pdf = _crear_pdf_solo_imagen(tmp_path / "escaneo.pdf")
    dest = tmp_path / "out"
    r = censurar_pdf(pdf, dest, [TERMINO], detectar_importes=False)
    assert r.estado == EstadoCensura.ERROR
    assert r.motivo == MotivoCensura.SIN_CAPA_TEXTO
    assert r.paginas_sin_capa_texto == 1
    assert r.output_path is None
    assert _archivos(dest) == []


def _crear_mixto(path: Path):
    doc = fitz.open()
    p1 = doc.new_page()
    _escribir(p1, f"Página digital {TERMINO}")
    p2 = doc.new_page()
    _escribir(p2, f"Otra digital {TERMINO}")
    _insertar_imagen_renderizada(doc, f"escaneada {TERMINO}")
    doc.save(str(path))
    doc.close()
    return path


def test_mixto_rango_solo_paginas_con_texto_se_procesa(tmp_path):
    pdf = _crear_mixto(tmp_path / "mixto.pdf")
    r = censurar_pdf(pdf, tmp_path / "out", [TERMINO], pages={1, 2}, detectar_importes=False)
    assert r.estado == EstadoCensura.PROCESADO
    assert r.paginas_afectadas == 2
    out = fitz.open(str(r.output_path))
    try:
        assert out.page_count == 3
        assert out[0].search_for(TERMINO) == [] and out[1].search_for(TERMINO) == []
    finally:
        out.close()


def test_mixto_rango_que_incluye_pagina_escaneada_es_error(tmp_path):
    pdf = _crear_mixto(tmp_path / "mixto.pdf")
    dest = tmp_path / "out"
    r = censurar_pdf(pdf, dest, [TERMINO], pages={2, 3}, detectar_importes=False)
    assert r.estado == EstadoCensura.ERROR
    assert r.motivo == MotivoCensura.SIN_CAPA_TEXTO
    assert _archivos(dest) == []


def test_pagina_con_texto_e_imagen_cuenta_como_pagina_con_imagenes(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    _escribir(page, f"Cliente {TERMINO}")
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 20, 20), 0)
    pix.set_rect(pix.irect, (200, 0, 0))
    page.insert_image(fitz.Rect(300, 300, 340, 340), pixmap=pix)
    pdf = tmp_path / "logo.pdf"
    doc.save(str(pdf))
    doc.close()

    r = censurar_pdf(pdf, tmp_path / "out", [TERMINO], detectar_importes=False)
    assert r.estado == EstadoCensura.PROCESADO
    assert r.paginas_con_imagenes == 1
    assert r.paginas_solo_vectoriales == 0


def test_pagina_solo_vectorial_es_aviso_no_error(tmp_path):
    doc = fitz.open()
    p1 = doc.new_page()
    _escribir(p1, f"Cliente {TERMINO}")
    p2 = doc.new_page()
    shape = p2.new_shape()
    shape.draw_line(fitz.Point(72, 72), fitz.Point(300, 72))
    shape.finish(color=(0, 0, 0), width=1)
    shape.commit()
    p3 = doc.new_page()  # en blanco: válida y sin aviso
    pdf = tmp_path / "vec.pdf"
    doc.save(str(pdf))
    doc.close()

    r = censurar_pdf(pdf, tmp_path / "out", [TERMINO], detectar_importes=False)
    assert r.estado == EstadoCensura.PROCESADO
    assert r.paginas_solo_vectoriales == 1
    assert r.paginas_con_imagenes == 0


def test_texto_oculto_tipo_ocr_sobre_imagen_se_censura(tmp_path):
    """Capa OCR invisible (render_mode 3) sobre una imagen: el término se elimina."""
    doc = fitz.open()
    page = _insertar_imagen_renderizada(doc, "fondo")
    page.insert_text((72, 100), f"cliente {TERMINO}", render_mode=3)
    pdf = tmp_path / "ocr.pdf"
    doc.save(str(pdf))
    doc.close()

    r = censurar_pdf(pdf, tmp_path / "out", [TERMINO], detectar_importes=False)
    assert r.estado == EstadoCensura.PROCESADO
    assert r.paginas_con_imagenes == 1
    assert TERMINO.lower() not in normalizar_texto(_texto_pdf(r.output_path))


# ---------------------------------------------------------------------------
# Omitido, rangos y PDFs no válidos
# ---------------------------------------------------------------------------


def test_cero_coincidencias_es_omitido_sin_archivo(tmp_path):
    pdf = _crear_pdf(tmp_path / "a.pdf", ["Texto cualquiera sin nada sensible"])
    dest = tmp_path / "out"
    r = censurar_pdf(pdf, dest, ["inexistente", "otra"], detectar_importes=False)
    assert r.estado == EstadoCensura.OMITIDO
    assert r.motivo == MotivoCensura.SIN_COINCIDENCIAS
    assert r.terminos_sin_coincidencias == 2
    assert r.output_path is None
    assert _archivos(dest) == []


def test_terminos_sin_coincidencias_se_cuentan_en_procesado(tmp_path):
    pdf = _crear_pdf(tmp_path / "a.pdf", [f"Cliente {TERMINO}"])
    r = censurar_pdf(pdf, tmp_path / "out", [TERMINO, "nadie", "ninguno"], detectar_importes=False)
    assert r.estado == EstadoCensura.PROCESADO
    assert r.terminos_sin_coincidencias == 2


@pytest.mark.parametrize("pages", [{0}, {5}, set()])
def test_rango_invalido_es_error(tmp_path, pages):
    pdf = _crear_pdf(tmp_path / "a.pdf", [f"Cliente {TERMINO}"])
    r = censurar_pdf(pdf, tmp_path / "out", [TERMINO], pages, detectar_importes=False)
    assert r.estado == EstadoCensura.ERROR
    assert r.motivo == MotivoCensura.RANGO_INVALIDO
    assert _archivos(tmp_path / "out") == []


def test_pdf_corrupto_es_error_pdf_no_abre(tmp_path):
    malo = tmp_path / "malo.pdf"
    malo.write_bytes(b"esto no es un pdf")
    r = censurar_pdf(malo, tmp_path / "out", [TERMINO], detectar_importes=False)
    assert r.estado == EstadoCensura.ERROR
    assert r.motivo == MotivoCensura.PDF_NO_ABRE


def test_pdf_cifrado_es_error(tmp_path):
    doc = fitz.open()
    _escribir(doc.new_page(), f"Cliente {TERMINO}")
    pdf = tmp_path / "cifrado.pdf"
    doc.save(str(pdf), encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="u", owner_pw="o")
    doc.close()
    r = censurar_pdf(pdf, tmp_path / "out", [TERMINO], detectar_importes=False)
    assert r.estado == EstadoCensura.ERROR
    assert r.motivo == MotivoCensura.PDF_CIFRADO
    assert _archivos(tmp_path / "out") == []


# ---------------------------------------------------------------------------
# Falsos negativos de search_for: nunca sale un PDF con el término visible
# ---------------------------------------------------------------------------


def test_termino_partido_por_guion_y_mayusculas_no_se_filtra(tmp_path):
    pdf = _crear_pdf(tmp_path / "g.pdf", ["Dato CONFIDEN-\ncial del cliente\nNada más"])
    dest = tmp_path / "out"
    r = censurar_pdf(pdf, dest, ["confidencial"], detectar_importes=False)

    if r.estado == EstadoCensura.PROCESADO:
        # Ni con espacios, saltos ni guiones intermedios puede reconstruirse el término.
        compacto = re.sub(r"[\s\-]+", "", normalizar_texto(_texto_pdf(r.output_path)))
        assert "confidencial" not in compacto
        assert r.coincidencias >= 1
    else:
        assert r.estado == EstadoCensura.ERROR
        assert r.motivo == MotivoCensura.VERIFICACION_FALLIDA
        assert _archivos(dest) == []
    assert _sin_temporales(dest)


def test_ligadura_real_se_censura(tmp_path):
    """Con ligadura real, search_for por defecto no encuentra 'oficina': se compensa."""
    doc = fitz.open()
    page = doc.new_page()
    _escribir(page, "La o\ufb01cina del cliente", fuente="tiro")
    pdf = tmp_path / "lig.pdf"
    doc.save(str(pdf))
    doc.close()

    assert fitz.open(str(pdf))[0].search_for("oficina") == []  # el fallo de PyMuPDF existe

    r = censurar_pdf(pdf, tmp_path / "out", ["oficina"], detectar_importes=False)
    assert r.estado == EstadoCensura.PROCESADO
    assert "oficina" not in normalizar_texto(_texto_pdf(r.output_path))


def test_search_for_ciego_con_texto_presente_es_error_no_omitido(tmp_path, monkeypatch):
    """Si search_for no localiza nada pero el término SÍ está en el texto → error, no 'omitido'."""
    pdf = _crear_pdf(tmp_path / "a.pdf", [f"Cliente {TERMINO}"])
    dest = tmp_path / "out"
    monkeypatch.setattr(core, "_buscar", lambda page, term: [])

    r = censurar_pdf(pdf, dest, [TERMINO], detectar_importes=False)

    assert r.estado == EstadoCensura.ERROR
    assert r.motivo == MotivoCensura.VERIFICACION_FALLIDA
    assert "coincidencia_no_localizada" in r.fallos_verificacion
    assert _archivos(dest) == []


# ---------------------------------------------------------------------------
# Saneado de contenedores
# ---------------------------------------------------------------------------


def test_outline_titulo_con_termino_se_sustituye(tmp_path):
    pdf = _crear_pdf(
        tmp_path / "a.pdf",
        [f"Cliente {TERMINO}", "Otra"],
        toc=[[1, "Anexo Zorrillo (cliente)", 1], [1, "Capítulo neutro", 2]],
    )
    r = censurar_pdf(pdf, tmp_path / "out", [TERMINO], detectar_importes=False)
    assert r.estado == EstadoCensura.PROCESADO
    out = fitz.open(str(r.output_path))
    try:
        titulos = [t[1] for t in out.get_toc()]
    finally:
        out.close()
    assert titulos[0] == f"Anexo {core.MARCADOR_OUTLINE} (cliente)"
    assert titulos[1] == "Capítulo neutro"
    assert [t[2] for t in fitz.open(str(r.output_path)).get_toc()] == [1, 2]


def test_anotacion_freetext_con_termino_se_elimina_y_el_resto_se_conserva(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    _escribir(page, f"Cliente {TERMINO}")
    a1 = page.add_freetext_annot(fitz.Rect(50, 200, 300, 240), f"Nota sobre {TERMINO}")
    a1.set_info(content=f"Nota sobre {TERMINO}")
    a1.update()
    a2 = page.add_freetext_annot(fitz.Rect(50, 260, 300, 300), "Nota inocua")
    a2.set_info(content="Nota inocua")
    a2.update()
    a3 = page.add_text_annot((400, 400), "x")
    a3.set_info(title=f"Autor {TERMINO}", content="neutro")
    pdf = tmp_path / "an.pdf"
    doc.save(str(pdf))
    doc.close()

    r = censurar_pdf(pdf, tmp_path / "out", [TERMINO], detectar_importes=False)

    assert r.estado == EstadoCensura.PROCESADO
    out = fitz.open(str(r.output_path))
    try:
        contenidos = [a.info["content"] for a in out[0].annots()]
        titulos = [a.info["title"] for a in out[0].annots()]
    finally:
        out.close()
    assert contenidos == ["Nota inocua"]  # sin crash de scrub con anotaciones restantes
    assert not any(TERMINO.lower() in t.lower() for t in contenidos + titulos)


def test_adjunto_embebido_y_anotacion_de_adjunto_se_eliminan(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    _escribir(page, f"Cliente {TERMINO}")
    page.add_file_annot((300, 300), f"secreto {TERMINO}".encode(), "adj.txt")
    doc.embfile_add("emb.txt", f"secreto {TERMINO}".encode(), filename="emb.txt")
    pdf = tmp_path / "adj.pdf"
    doc.save(str(pdf))
    doc.close()

    r = censurar_pdf(pdf, tmp_path / "out", [TERMINO], detectar_importes=False)

    assert r.estado == EstadoCensura.PROCESADO
    out = fitz.open(str(r.output_path))
    try:
        assert out.embfile_count() == 0
        assert list(out[0].annots(types=[fitz.PDF_ANNOT_FILE_ATTACHMENT])) == []
    finally:
        out.close()
    assert TERMINO.encode() not in r.output_path.read_bytes()


def test_campo_de_formulario_con_termino_en_el_nombre_es_error(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    _escribir(page, f"Cliente {TERMINO}")
    w = fitz.Widget()
    w.rect = fitz.Rect(50, 300, 250, 330)
    w.field_name = f"campo_{TERMINO}"
    w.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    w.field_value = "valor"
    page.add_widget(w)
    pdf = tmp_path / "form.pdf"
    doc.save(str(pdf))
    doc.close()

    dest = tmp_path / "out"
    r = censurar_pdf(pdf, dest, [TERMINO], detectar_importes=False)

    assert r.estado == EstadoCensura.ERROR
    assert r.motivo == MotivoCensura.VERIFICACION_FALLIDA
    assert "campos_formulario" in r.fallos_verificacion
    assert _archivos(dest) == []


def test_nombres_de_destino_con_termino_es_error(tmp_path, monkeypatch):
    """resolve_names() con el término → la verificación lo detecta (simulado)."""
    pdf = _crear_pdf(tmp_path / "a.pdf", [f"Cliente {TERMINO}"])
    dest = tmp_path / "out"
    original = fitz.Document.resolve_names
    monkeypatch.setattr(
        fitz.Document, "resolve_names",
        lambda self: {f"dest_{TERMINO}": {"page": 0}} if self.page_count else original(self),
    )
    r = censurar_pdf(pdf, dest, [TERMINO], detectar_importes=False)
    assert r.estado == EstadoCensura.ERROR
    assert "nombres_destino" in r.fallos_verificacion
    assert _archivos(dest) == []


# ---------------------------------------------------------------------------
# Fail-closed: verificación fallida, errores inesperados, cancelación
# ---------------------------------------------------------------------------


def test_verificacion_fallida_simulada_no_deja_archivo_ni_temporales(tmp_path, monkeypatch):
    pdf = _crear_pdf(tmp_path / "a.pdf", [f"Cliente {TERMINO}"])
    dest = tmp_path / "out"
    vistos = {}

    def falso_verificar(path, terminos, indices, paginas):
        vistos["temp_existia"] = Path(path).is_file()
        vistos["temp_oculto"] = Path(path).name.startswith(".")
        vistos["mismo_dir"] = Path(path).parent == dest
        return ["simulado"]

    monkeypatch.setattr(core, "verificar_salida", falso_verificar)

    r = censurar_pdf(pdf, dest, [TERMINO], detectar_importes=False)

    assert vistos == {"temp_existia": True, "temp_oculto": True, "mismo_dir": True}
    assert r.estado == EstadoCensura.ERROR
    assert r.motivo == MotivoCensura.VERIFICACION_FALLIDA
    assert r.fallos_verificacion == ("simulado",)
    assert r.output_path is None
    assert _archivos(dest) == []


def test_excepcion_en_verificacion_es_verificacion_fallida(tmp_path, monkeypatch):
    pdf = _crear_pdf(tmp_path / "a.pdf", [f"Cliente {TERMINO}"])
    dest = tmp_path / "out"

    def explota(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(core, "verificar_salida", explota)
    r = censurar_pdf(pdf, dest, [TERMINO], detectar_importes=False)
    assert r.estado == EstadoCensura.ERROR
    assert r.motivo == MotivoCensura.VERIFICACION_FALLIDA
    assert _archivos(dest) == []


def test_error_inesperado_no_deja_archivo_ni_filtra_en_el_log(tmp_path, monkeypatch, log_docflow):
    pdf = _crear_pdf(tmp_path / "a.pdf", [f"Cliente {TERMINO}"])
    dest = tmp_path / "out"

    def explota(doc):
        raise RuntimeError(f"fallo con {TERMINO} en {pdf}")

    monkeypatch.setattr(core, "_aplicar_scrub", explota)
    r = censurar_pdf(pdf, dest, [TERMINO], detectar_importes=False)

    assert r.estado == EstadoCensura.ERROR
    assert r.motivo == MotivoCensura.ERROR_INTERNO
    assert _archivos(dest) == []
    mensajes = "\n".join(rec.getMessage() for rec in log_docflow.records)
    assert mensajes  # se registró algo
    assert TERMINO not in mensajes and str(tmp_path) not in mensajes


@pytest.mark.parametrize("k", range(1, 12))
def test_cancelacion_en_cualquier_punto_no_deja_temporales(tmp_path, k):
    """Cancela en la llamada k-ésima a is_cancelled: o termina bien o no deja NADA."""
    pdf = _crear_pdf(tmp_path / "a.pdf", [f"A {TERMINO}", f"B {TERMINO}", f"C {TERMINO}"])
    dest = tmp_path / f"out{k}"
    llamadas = {"n": 0}

    def is_cancelled():
        llamadas["n"] += 1
        return llamadas["n"] >= k

    try:
        r = censurar_pdf(pdf, dest, [TERMINO], detectar_importes=False, is_cancelled=is_cancelled)
    except CancelledByUser:
        assert _archivos(dest) == []
    else:
        assert r.estado == EstadoCensura.PROCESADO
        assert _archivos(dest) == ["a_censurado.pdf"]
    assert _sin_temporales(dest)


# ---------------------------------------------------------------------------
# Nombre final, colisiones, flags
# ---------------------------------------------------------------------------


def test_colision_de_nombre_usa_sufijo_y_nunca_sobrescribe(tmp_path):
    pdf = _crear_pdf(tmp_path / "f.pdf", [f"Cliente {TERMINO}"])
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "f_censurado.pdf").write_bytes(b"previo-1")
    (dest / "f_censurado_02.pdf").write_bytes(b"previo-2")

    r = censurar_pdf(pdf, dest, [TERMINO], detectar_importes=False)

    assert r.estado == EstadoCensura.PROCESADO
    assert r.output_path.name == "f_censurado_03.pdf"
    assert (dest / "f_censurado.pdf").read_bytes() == b"previo-1"
    assert (dest / "f_censurado_02.pdf").read_bytes() == b"previo-2"
    assert _sin_temporales(dest)


def test_nombre_aparece_justo_antes_de_promover_no_se_sobrescribe(tmp_path, monkeypatch):
    pdf = _crear_pdf(tmp_path / "f.pdf", [f"Cliente {TERMINO}"])
    dest = tmp_path / "out"
    ocupado = dest / "f_censurado.pdf"
    llamadas = {"n": 0}
    original = core.resolve_conflict

    def carrera(path, pattern="_v{i}"):
        resultado = original(path, pattern=pattern)
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            resultado.write_bytes(b"alguien-me-gano")  # aparece tras elegir el nombre
        return resultado

    monkeypatch.setattr(core, "resolve_conflict", carrera)
    r = censurar_pdf(pdf, dest, [TERMINO], detectar_importes=False)

    assert r.estado == EstadoCensura.PROCESADO
    assert ocupado.read_bytes() == b"alguien-me-gano"
    assert r.output_path.name == "f_censurado_02.pdf"


@pytest.mark.skipif(sys.platform != "darwin", reason="UF_HIDDEN solo existe en macOS")
def test_archivo_final_no_queda_oculto_en_macos(tmp_path):
    import stat as st

    pdf = _crear_pdf(tmp_path / "f.pdf", [f"Cliente {TERMINO}"])
    r = censurar_pdf(pdf, tmp_path / "out", [TERMINO], detectar_importes=False)
    assert not (r.output_path.stat().st_flags & st.UF_HIDDEN)


# ---------------------------------------------------------------------------
# ResumenLote
# ---------------------------------------------------------------------------


def _res(estado, motivo, **kw):
    return ResultadoCensura(estado=estado, motivo=motivo, **kw)


def test_resumen_mensaje_con_las_tres_cifras_y_desglose():
    resumen = ResumenLote(total=6)
    resumen.agregar(_res(EstadoCensura.PROCESADO, MotivoCensura.OK,
                         terminos_sin_coincidencias=2, paginas_con_imagenes=3,
                         paginas_solo_vectoriales=1, output_path=Path("/x/a.pdf")))
    resumen.agregar(_res(EstadoCensura.OMITIDO, MotivoCensura.SIN_COINCIDENCIAS,
                         terminos_sin_coincidencias=1))
    for _ in range(2):
        resumen.agregar(ResultadoCensura.fallo(MotivoCensura.SIN_CAPA_TEXTO, paginas_con_imagenes=9))
    resumen.agregar(ResultadoCensura.fallo(MotivoCensura.VERIFICACION_FALLIDA))
    resumen.agregar(ResultadoCensura.fallo(MotivoCensura.IMPORTE_NO_INTERPRETABLE))

    msg = resumen.mensaje()
    assert (resumen.procesados, resumen.omitidos, resumen.errores) == (1, 1, 4)
    assert "1 procesado(s)" in msg and "1 omitido(s)" in msg and "4 con error" in msg
    assert "2 sin capa de texto: aplica OCR antes" in msg
    assert "1 no superaron la verificación final" in msg
    assert "Términos sin coincidencias: 3" in msg
    assert "3 página(s) con imágenes" in msg and "NO se censura" in msg  # los 9 de errores no suman
    assert "1 página(s) solo vectoriales" in msg
    assert not msg.startswith("No se censuró")


def test_resumen_sin_ningun_procesado_no_presenta_exito():
    resumen = ResumenLote(total=2)
    resumen.agregar(_res(EstadoCensura.OMITIDO, MotivoCensura.SIN_COINCIDENCIAS))
    resumen.agregar(ResultadoCensura.fallo(MotivoCensura.SIN_CAPA_TEXTO))
    assert resumen.mensaje().startswith("No se censuró ningún PDF.")


def test_resumen_archivos_solo_existentes(tmp_path):
    real = tmp_path / "real.pdf"
    real.write_bytes(b"x")
    resumen = ResumenLote(total=2)
    resumen.agregar(_res(EstadoCensura.PROCESADO, MotivoCensura.OK, output_path=real))
    resumen.agregar(_res(EstadoCensura.PROCESADO, MotivoCensura.OK, output_path=tmp_path / "fantasma.pdf"))
    assert resumen.archivos_existentes() == [real]


# ---------------------------------------------------------------------------
# Lote / run()
# ---------------------------------------------------------------------------


def _cfg(words=(TERMINO,), *, importes=False, all_pages=True, ranges=None):
    return {
        "words": list(words),
        "all_pages": all_pages,
        "ranges": ranges,
        "detectar_importes": importes,
    }


def test_script_conserva_meta_y_firma_de_run():
    meta = extract_metadata(script)
    assert meta["name"] == "Censurar PDF por palabras"
    assert meta["category"] == "PDF"
    assert list(inspect.signature(script.run).parameters) == ["progress", "is_cancelled"]


def test_lote_contabiliza_procesados_omitidos_y_errores(tmp_path):
    ok = _crear_pdf(tmp_path / "ok.pdf", [f"Cliente {TERMINO}"])
    vacio = _crear_pdf(tmp_path / "vacio.pdf", ["Nada sensible"])
    img = _crear_pdf_solo_imagen(tmp_path / "img.pdf")
    progreso = []

    res = script._ejecutar_lote(
        [ok, vacio, img], _cfg(), progress=lambda i, n: progreso.append((i, n))
    )

    stats = res["stats"]
    assert (stats["total"], stats["procesados"], stats["omitidos"], stats["errores"]) == (3, 1, 1, 1)
    assert stats["errores_sin_capa_texto"] == 1
    assert progreso == [(1, 3), (2, 3), (3, 3)]
    assert [Path(f).name for f in res["files"]] == ["ok_censurado.pdf"]
    assert all(Path(f).is_file() for f in res["files"])
    assert "sin capa de texto: aplica OCR antes" in res["message"]
    assert res["output_dir"] == str(tmp_path / "PDF_censurados")


def test_lote_todos_fallan_no_presenta_exito(tmp_path):
    a = _crear_pdf_solo_imagen(tmp_path / "a.pdf")
    b = _crear_pdf_solo_imagen(tmp_path / "b.pdf")

    res = script._ejecutar_lote([a, b], _cfg())

    assert res["stats"]["procesados"] == 0
    assert res["stats"]["errores"] == 2
    assert res["message"].startswith("No se censuró ningún PDF.")
    assert "2 sin capa de texto: aplica OCR antes" in res["message"]
    assert res["files"] == []
    assert _archivos(tmp_path / "PDF_censurados") == []
    # Apunta a la carpeta de origen si no se creó la de salida.
    assert res["output_dir"] == str(tmp_path)


def test_lote_todos_omitidos_no_presenta_exito(tmp_path):
    a = _crear_pdf(tmp_path / "a.pdf", ["Nada"])
    res = script._ejecutar_lote([a], _cfg())
    assert res["stats"]["omitidos"] == 1 and res["stats"]["procesados"] == 0
    assert res["message"].startswith("No se censuró ningún PDF.")


def test_lote_rango_fuera_de_limites_es_error_rango_invalido(tmp_path):
    a = _crear_pdf(tmp_path / "a.pdf", [f"Cliente {TERMINO}"])
    res = script._ejecutar_lote(
        [a], _cfg(all_pages=False, ranges=[(1, 7)])
    )
    assert res["stats"]["errores"] == 1
    assert res["stats"]["errores_rango_invalido"] == 1


def test_lote_rango_de_paginas_se_respeta(tmp_path):
    pdf = _crear_mixto(tmp_path / "m.pdf")
    res = script._ejecutar_lote([pdf], _cfg(all_pages=False, ranges=[(1, 2)]))
    assert res["stats"]["procesados"] == 1
    res2 = script._ejecutar_lote([pdf], _cfg(all_pages=False, ranges=[(3, 3)]))
    assert res2["stats"]["errores_sin_capa_texto"] == 1


def test_lote_lista_vacia_sin_importes_se_rechaza(tmp_path):
    a = _crear_pdf(tmp_path / "a.pdf", [f"Cliente {TERMINO}"])
    with pytest.raises(ValueError):
        script._ejecutar_lote([a], _cfg(words=[], importes=False))
    assert _archivos(tmp_path / "PDF_censurados") == []


def test_lote_cancelacion_entre_archivos_conserva_los_completados(tmp_path):
    pdfs = [_crear_pdf(tmp_path / f"{n}.pdf", [f"Cliente {TERMINO}"]) for n in "abc"]
    hechos = []

    with pytest.raises(CancelledByUser) as exc:
        script._ejecutar_lote(
            pdfs, _cfg(),
            progress=lambda i, n: hechos.append(i),
            is_cancelled=lambda: len(hechos) >= 1,
        )

    res = exc.value.result
    assert res["message"] == "Cancelado"
    assert res["stats"]["procesados"] == 1
    assert res["stats"]["omitidos"] == 2  # pendientes
    assert [Path(f).name for f in res["files"]] == ["a_censurado.pdf"]
    assert _archivos(tmp_path / "PDF_censurados") == ["a_censurado.pdf"]


def test_lote_cancelacion_a_mitad_de_un_pdf_no_deja_temporales(tmp_path):
    pdfs = [_crear_pdf(tmp_path / f"{n}.pdf", [f"A {TERMINO}", f"B {TERMINO}"]) for n in "ab"]
    dest = tmp_path / "PDF_censurados"
    estado = {"tras_primero": 0}

    def is_cancelled():
        if (dest / "a_censurado.pdf").exists():
            estado["tras_primero"] += 1
            return estado["tras_primero"] >= 4  # ya dentro del segundo PDF
        return False

    with pytest.raises(CancelledByUser) as exc:
        script._ejecutar_lote(pdfs, _cfg(), is_cancelled=is_cancelled)

    assert exc.value.result["stats"]["procesados"] == 1
    assert _archivos(dest) == ["a_censurado.pdf"]
    assert _sin_temporales(dest)


def test_lote_no_registra_terminos_nombres_ni_rutas(tmp_path, log_docflow):
    ok = _crear_pdf(tmp_path / "expedienteSECRETO77.pdf", [f"Cliente {TERMINO}"])
    img = _crear_pdf_solo_imagen(tmp_path / "escaneoPRIVADO88.pdf")
    vacio = _crear_pdf(tmp_path / "vacioRESERVADO99.pdf", ["Nada"])

    script._ejecutar_lote([ok, img, vacio], _cfg(words=[TERMINO, "Cliente"]))

    mensajes = "\n".join(r.getMessage() for r in log_docflow.records)
    assert "archivo 1 de 3" in mensajes and "archivo 3 de 3" in mensajes
    for prohibido in (TERMINO, TERMINO.lower(), "Cliente", "SECRETO77", "PRIVADO88",
                      "RESERVADO99", str(tmp_path), "PDF_censurados", ".pdf"):
        assert prohibido not in mensajes


def test_run_usa_dialogo_y_devuelve_resultado(tmp_path, monkeypatch):
    pdf = _crear_pdf(tmp_path / "a.pdf", [f"Cliente {TERMINO}"])

    class DialogoFalso:
        def __init__(self, parent):
            self.resultado = _cfg()

    monkeypatch.setattr(script.tk, "_get_default_root", lambda *a, **k: None)
    monkeypatch.setattr(script, "get_ruta", lambda clave: None)
    monkeypatch.setattr(script.filedialog, "askopenfilenames", lambda **kw: [str(pdf)])
    monkeypatch.setattr(script, "CensurarDialog", DialogoFalso)

    res = script.run()
    assert res["stats"]["procesados"] == 1
    assert (tmp_path / "PDF_censurados" / "a_censurado.pdf").is_file()


def test_run_dialogo_cancelado_lanza_cancelled(tmp_path, monkeypatch):
    pdf = _crear_pdf(tmp_path / "a.pdf", ["x"])

    class DialogoFalso:
        def __init__(self, parent):
            self.resultado = None

    monkeypatch.setattr(script.tk, "_get_default_root", lambda *a, **k: None)
    monkeypatch.setattr(script, "get_ruta", lambda clave: None)
    monkeypatch.setattr(script.filedialog, "askopenfilenames", lambda **kw: [str(pdf)])
    monkeypatch.setattr(script, "CensurarDialog", DialogoFalso)

    with pytest.raises(CancelledByUser):
        script.run()


# ---------------------------------------------------------------------------
# Diálogo (casilla de importes y validación de términos)
# ---------------------------------------------------------------------------


@pytest.fixture
def dialogo(monkeypatch):
    import tkinter as tk

    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError as exc:
        pytest.skip(f"Tk no disponible en este entorno: {exc}")

    # El diálogo real es modal y bloquea en wait_window()/grab_set().
    monkeypatch.setattr(tk.Toplevel, "wait_window", lambda self, *a, **k: None)
    monkeypatch.setattr(tk.Toplevel, "grab_set", lambda self: None)
    errores = []
    monkeypatch.setattr(
        script.messagebox, "showerror", lambda titulo, msg, **kw: errores.append((titulo, msg))
    )

    dlg = script.CensurarDialog(root)
    dlg.errores = errores
    try:
        yield dlg
    finally:
        try:
            dlg.destroy()
            root.destroy()
        except tk.TclError:
            pass


def _escribir_terminos(dlg, texto):
    dlg.txt_words.delete("1.0", "end")
    dlg.txt_words.insert("1.0", texto)


def test_dialogo_casilla_de_importes_activada_por_defecto(dialogo):
    assert dialogo.var_importes.get() is True


def test_dialogo_lista_vacia_sin_importes_se_rechaza_con_mensaje(dialogo):
    _escribir_terminos(dialogo, "  \n \n")
    dialogo.var_importes.set(False)
    dialogo._confirmar()
    assert dialogo.resultado is None
    assert len(dialogo.errores) == 1
    assert "al menos una palabra" in dialogo.errores[0][1]


def test_dialogo_lista_vacia_con_importes_se_acepta(dialogo):
    _escribir_terminos(dialogo, "")
    dialogo.var_importes.set(True)
    dialogo._confirmar()
    assert dialogo.errores == []
    assert dialogo.resultado == {
        "words": [], "all_pages": True, "ranges": None, "detectar_importes": True,
    }


def test_dialogo_con_terminos_y_rango(dialogo):
    _escribir_terminos(dialogo, "Ana\nana\nLuis\n")
    dialogo.var_importes.set(False)
    dialogo.var_todas.set(False)
    dialogo.var_rango.set("1-2, 4")
    dialogo._confirmar()
    assert dialogo.resultado == {
        "words": ["Ana", "Luis"],
        "all_pages": False,
        "ranges": [(1, 2), (4, 4)],
        "detectar_importes": False,
    }
