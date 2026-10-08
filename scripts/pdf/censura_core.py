"""
Núcleo de "Censurar PDF por palabras": lógica pura, sin Tkinter ni UI.

Principio: FAIL-CLOSED. Un PDF censurado que conserva un término sensible es
peor que no generar ningún archivo. Por eso:

  - Nunca se escribe sobre el nombre final hasta haber VERIFICADO el resultado
    reabriendo un temporal (texto, metadatos, outline, anotaciones, campos…).
  - Cualquier duda (página escaneada, verificación fallida, importe ilegible,
    excepción inesperada) acaba en estado "error" y SIN archivo de salida.
  - El PDF original no se modifica nunca.
  - Ni los resultados ni los logs contienen términos, texto ni rutas. Los nombres
    base de los PDFs omitidos o fallidos solo aparecen en ResumenLote.mensaje()
    (mensaje visible); nunca en logs ni en excepciones.
  - Campos de formulario con un término: se aplanan (Document.bake) y se tachan
    como texto de página; si no hay término en ningún campo, el formulario se conserva.

Nota sobre PyMuPDF 1.25.1 (verificado en el entorno del proyecto):
  - ``Document.scrub(reset_responses=True)`` lanza AttributeError con cualquier
    anotación (bug en ``Annot.delete_responses``) → se usa False.
  - ``Document.scrub(attached_files=True)`` lanza TypeError con anotaciones de
    adjunto (bug ``update_file(buffer=...)``) → se eliminan antes a mano.
  - ``Page.delete_annot`` devuelve un objeto inválido (crash nativo si se usa):
    nunca se reutiliza el valor devuelto.
"""

from __future__ import annotations

import os
import re
import secrets
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from dataclasses import fields as dataclass_fields
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
from typing import Callable, Collection, Iterable, List, Optional, Sequence, Tuple

from logger import logger
from scripts.common.filenames import resolve_conflict
from scripts.common.ocr_io import safe_unlink
from ui.exceptions import CancelledByUser

try:
    import fitz  # pymupdf
except Exception:  # pragma: no cover - depende del entorno
    fitz = None


# ======================================================
# CONSTANTES
# ======================================================

SUFIJO_SALIDA = "_censurado"
PATRON_CONFLICTO = "_{i:02d}"
PREFIJO_TEMPORAL = ".docflow_censura_"
MARCADOR_OUTLINE = "[CENSURADO]"


# ======================================================
# RESULTADO
# ======================================================

class EstadoCensura(str, Enum):
    PROCESADO = "procesado"
    OMITIDO = "omitido"
    ERROR = "error"


class MotivoCensura(str, Enum):
    OK = "ok"
    SIN_COINCIDENCIAS = "sin_coincidencias"
    SIN_CAPA_TEXTO = "sin_capa_texto"
    VERIFICACION_FALLIDA = "verificacion_fallida"
    IMPORTE_NO_INTERPRETABLE = "importe_no_interpretable"
    PDF_NO_ABRE = "pdf_no_abre"
    PDF_CIFRADO = "pdf_cifrado"
    RANGO_INVALIDO = "rango_invalido"
    ERROR_INTERNO = "error_interno"
    ARCHIVO_NO_ENCONTRADO = "archivo_no_encontrado"


# Frases del mensaje al usuario por motivo de error. "{n}" = nº de PDFs.
# Redactadas en español llano; sin términos y sin nombres de archivo (estos los
# añade ResumenLote, solo en el mensaje visible).
FRASES_ERROR = {
    MotivoCensura.SIN_CAPA_TEXTO:
        "{n} PDF(s) son imágenes escaneadas sin texto: conviértelos antes con "
        "«PDF escaneado a PDF OCR»",
    MotivoCensura.VERIFICACION_FALLIDA:
        "{n} PDF(s) no se han creado por seguridad: tras censurar, el texto "
        "seguía apareciendo en {causas}",
    MotivoCensura.IMPORTE_NO_INTERPRETABLE:
        "{n} PDF(s) tienen la frase «Siendo … lo pagado» con un importe que no "
        "se puede interpretar; revisa el formato, p. ej. 1.234,56 €",
    MotivoCensura.PDF_NO_ABRE: "{n} PDF(s) no se han podido abrir o están dañados",
    MotivoCensura.PDF_CIFRADO: "{n} PDF(s) están protegidos con contraseña",
    MotivoCensura.RANGO_INVALIDO:
        "{n} PDF(s) no tienen las páginas indicadas en el rango",
    MotivoCensura.ERROR_INTERNO:
        "{n} PDF(s) han fallado por un error inesperado; consulta el registro",
    MotivoCensura.ARCHIVO_NO_ENCONTRADO:
        "{n} PDF(s) no se pueden entregar: el archivo de salida no existe",
}

# Orden fijo de las frases de error en el mensaje.
ORDEN_ERRORES = (
    MotivoCensura.SIN_CAPA_TEXTO,
    MotivoCensura.VERIFICACION_FALLIDA,
    MotivoCensura.IMPORTE_NO_INTERPRETABLE,
    MotivoCensura.PDF_NO_ABRE,
    MotivoCensura.PDF_CIFRADO,
    MotivoCensura.RANGO_INVALIDO,
    MotivoCensura.ERROR_INTERNO,
    MotivoCensura.ARCHIVO_NO_ENCONTRADO,
)

# Categoría interna de verificación → causa legible.
CAUSA_COMPROBACION_INTERNA = "una comprobación interna"
CAUSAS_VERIFICACION = {
    "search_for": "el texto de las páginas",
    "texto_normalizado": "el texto de las páginas",
    "texto_fuera_de_pagina": "el texto de las páginas",
    "coincidencia_no_localizada": "el texto de las páginas",
    "anotaciones": "comentarios o anotaciones",
    "campos_formulario": "campos de formulario",
    "enlaces": "enlaces",
    "outline": "marcadores",
    "nombres_destino": "destinos internos",
    "adjuntos": "archivos adjuntos",
    "metadatos_info": "metadatos",
    "metadatos_xmp": "metadatos",
    "num_paginas": CAUSA_COMPROBACION_INTERNA,
    "error_verificacion": CAUSA_COMPROBACION_INTERNA,
}
# Orden de las causas en el mensaje.
ORDEN_CAUSAS = (
    "el texto de las páginas",
    "comentarios o anotaciones",
    "campos de formulario",
    "enlaces",
    "marcadores",
    "destinos internos",
    "archivos adjuntos",
    "metadatos",
    CAUSA_COMPROBACION_INTERNA,
)

# Máximo de nombres de archivo en el mensaje visible.
MAX_NOMBRES_MENSAJE = 5


@dataclass(frozen=True)
class ResultadoCensura:
    """Resultado por PDF. No contiene términos ni texto del documento."""

    estado: EstadoCensura
    motivo: MotivoCensura
    coincidencias: int = 0
    paginas_afectadas: int = 0
    terminos_sin_coincidencias: int = 0
    paginas_con_imagenes: int = 0
    paginas_solo_vectoriales: int = 0
    paginas_sin_capa_texto: int = 0
    # Términos buscados (los del usuario + los importes autodetectados).
    terminos_buscados: int = 0
    # Términos añadidos por la regla "Siendo … lo pagado" (15 % / 85 %).
    importes_autodetectados: int = 0
    # True si los campos de formulario se convirtieron en contenido fijo (bake).
    formularios_aplanados: bool = False
    # Categorías de verificación fallidas (p. ej. "texto_normalizado"); nunca términos.
    fallos_verificacion: tuple = ()
    output_path: Optional[Path] = None

    @classmethod
    def fallo(cls, motivo: MotivoCensura, **extra) -> "ResultadoCensura":
        return cls(estado=EstadoCensura.ERROR, motivo=motivo, **extra)


class ImporteNoInterpretable(ValueError):
    """Existe el patrón 'Siendo … lo pagado' pero el importe no se pudo interpretar."""


# ======================================================
# NORMALIZACIÓN Y TÉRMINOS
# ======================================================

_RE_ESPACIOS = re.compile(r"\s+")
_RE_GUION_FIN_LINEA = re.compile(r"[-\u2010]\s+")
_CARACTERES_INVISIBLES = {ord(c): None for c in "\u00ad\u200b\u200c\u200d\u2060\ufeff"}


def normalizar_texto(texto: Optional[str], *, unir_guiones: bool = True) -> str:
    """
    NFKC + sin caracteres invisibles + casefold + (unión de guiones de fin de
    línea "-\\s+" → "") + espacios colapsados.
    """
    t = unicodedata.normalize("NFKC", texto or "")
    t = t.translate(_CARACTERES_INVISIBLES).casefold()
    if unir_guiones:
        t = _RE_GUION_FIN_LINEA.sub("", t)
    return _RE_ESPACIOS.sub(" ", t).strip()


def _terminos_normalizados(terminos: Iterable[str]) -> List[str]:
    """Formas normalizadas no vacías de los términos (con y sin unión de guiones)."""
    resultado: List[str] = []
    for t in terminos:
        for unir in (False, True):
            n = normalizar_texto(t, unir_guiones=unir)
            if n and n not in resultado:
                resultado.append(n)
    return resultado


def _contiene_termino(texto: Optional[str], terminos_norm: Sequence[str]) -> bool:
    """
    True si el texto normalizado contiene algún término normalizado.

    Se comprueba con y sin unión de guiones: la unión es necesaria para
    "confiden-\\ncial", pero puede ocultar "Pérez- García" (guion legítimo).
    Probar ambas variantes solo puede añadir detecciones (fail-closed).
    """
    if not texto or not terminos_norm:
        return False
    variantes = (
        normalizar_texto(texto, unir_guiones=True),
        normalizar_texto(texto, unir_guiones=False),
    )
    return any(t in v for t in terminos_norm for v in variantes)


def preparar_terminos(words: Optional[Iterable[str]]) -> List[str]:
    """Limpia, descarta vacíos y deduplica (sin distinguir mayúsculas), conservando orden."""
    vistos = set()
    resultado: List[str] = []
    for w in words or []:
        w = (w or "").strip()
        clave = normalizar_texto(w, unir_guiones=False)
        if not clave or clave in vistos:
            continue
        vistos.add(clave)
        resultado.append(w)
    return resultado


def validar_terminos(words: Optional[Iterable[str]], detectar_importes: bool) -> List[str]:
    """
    Devuelve los términos limpios o lanza ValueError.

    Lista vacía solo se admite si la detección de importes está activa.
    """
    terminos = preparar_terminos(words)
    if not terminos and not detectar_importes:
        raise ValueError(
            "Introduce al menos una palabra o expresión a censurar, "
            "o activa la detección de importes."
        )
    return terminos


# ======================================================
# REGLA "SIENDO X € LO PAGADO" (15 % / 85 %)
# ======================================================

_RE_SIENDO = re.compile(r"Siendo\s+(.{1,40}?)\s+lo\s+pagado", re.IGNORECASE | re.DOTALL)
_RE_IMPORTE_ES = re.compile(r"^(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?$")


def _parse_euro(valor_str: str) -> Decimal:
    """Importe en formato español estricto ('1.234,56 €'); lanza ImporteNoInterpretable."""
    v = _RE_ESPACIOS.sub(" ", (valor_str or "").strip())
    if not v.endswith("€"):
        raise ImporteNoInterpretable("importe sin símbolo €")
    cifra = v[:-1].strip()
    if not _RE_IMPORTE_ES.match(cifra):
        raise ImporteNoInterpretable("formato de importe no reconocido")
    try:
        return Decimal(cifra.replace(".", "").replace(",", "."))
    except InvalidOperation as exc:
        raise ImporteNoInterpretable("importe no numérico") from exc


def _format_euro(valor: Decimal) -> str:
    valor = valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    s = f"{valor:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} €"


def detectar_importes_auto(texto: Optional[str]) -> List[str]:
    """
    Regla opcional: "Siendo X € lo pagado" → devuelve el 15 % y el 85 % de X
    que aparezcan en el texto.

    - Patrón ausente → [].
    - Patrón presente pero importe ilegible → ImporteNoInterpretable (nunca [] silencioso).
    """
    texto = texto or ""
    encontrados: List[str] = []
    texto_norm = normalizar_texto(texto, unir_guiones=False)

    for match in _RE_SIENDO.finditer(texto):
        base = _parse_euro(match.group(1))
        for factor in (Decimal("0.15"), Decimal("0.85")):
            imp = _format_euro(base * factor)
            if imp not in encontrados and normalizar_texto(imp, unir_guiones=False) in texto_norm:
                encontrados.append(imp)

    return encontrados


# ======================================================
# UTILIDADES PDF
# ======================================================

def _comprobar_cancelacion(is_cancelled: Optional[Callable[[], bool]]) -> None:
    if is_cancelled and is_cancelled():
        raise CancelledByUser()


def contar_paginas(path: Path) -> int:
    """Número de páginas del PDF (lanza si no se puede abrir)."""
    if fitz is None:
        raise RuntimeError("Falta dependencia 'pymupdf'.")
    doc = fitz.open(str(path))
    try:
        return int(doc.page_count)
    finally:
        doc.close()


def _resolver_paginas(pages: Optional[Collection[int]], total: int) -> Optional[List[int]]:
    """Índices 0-based de las páginas seleccionadas, o None si el rango no es válido."""
    if pages is None:
        return list(range(total))
    seleccion = sorted(set(pages))
    if not seleccion or seleccion[0] < 1 or seleccion[-1] > total:
        return None
    return [p - 1 for p in seleccion]


def _pagina_tiene_imagenes(page) -> bool:
    """
    Sin umbral de tamaño. Une get_images(full=True) (incluye XObjects de formulario)
    y get_image_info() (incluye imágenes inline) para no dejar pasar ninguna.
    """
    return bool(page.get_images(full=True)) or bool(page.get_image_info())


@dataclass
class _Analisis:
    sin_capa_texto: int = 0
    con_imagenes: int = 0
    solo_vectoriales: int = 0


def _analizar_paginas(doc, indices: Sequence[int], is_cancelled) -> _Analisis:
    a = _Analisis()
    for idx in indices:
        _comprobar_cancelacion(is_cancelled)
        page = doc.load_page(idx)
        tiene_texto = bool((page.get_text() or "").strip())
        tiene_imagenes = _pagina_tiene_imagenes(page)

        if not tiene_texto:
            if tiene_imagenes:
                a.sin_capa_texto += 1
            elif page.get_drawings():
                a.solo_vectoriales += 1
        elif tiene_imagenes:
            a.con_imagenes += 1
    return a


def _texto_documento(doc, is_cancelled) -> str:
    partes = []
    for page in doc:
        _comprobar_cancelacion(is_cancelled)
        partes.append(page.get_text())
    return "".join(partes)


def _texto_paginas(doc, indices: Sequence[int]) -> str:
    return "\n".join(doc.load_page(i).get_text() for i in indices)


# ======================================================
# REDACCIÓN Y SANEADO
# ======================================================

def _buscar(page, term: str) -> list:
    """
    search_for con los flags por defecto + search_for sin PRESERVE_LIGATURES.

    Con los flags por defecto, "oﬁcina" (ligadura real) no coincide con
    "oficina"; TEXTFLAGS_SEARCH descompone las ligaduras. Se unen ambos
    resultados sin duplicar rectángulos. La verificación final sigue siendo
    la garantía: esto solo reduce falsos negativos.
    """
    rects = list(page.search_for(term))
    vistos = {tuple(round(v, 1) for v in r) for r in rects}
    for r in page.search_for(term, flags=fitz.TEXTFLAGS_SEARCH):
        clave = tuple(round(v, 1) for v in r)
        if clave not in vistos:
            vistos.add(clave)
            rects.append(r)
    return rects


def _redactar(doc, indices, terminos, is_cancelled):
    """_buscar + add_redact_annot + apply_redactions (defaults de PyMuPDF)."""
    coincidencias = 0
    paginas_afectadas = 0
    terminos_con_hit = set()

    for idx in indices:
        _comprobar_cancelacion(is_cancelled)
        page = doc.load_page(idx)
        hits_pagina = 0

        for k, term in enumerate(terminos):
            rects = _buscar(page, term)
            for r in rects:
                page.add_redact_annot(r, fill=(0, 0, 0))
            if rects:
                terminos_con_hit.add(k)
                hits_pagina += len(rects)

        if hits_pagina:
            page.apply_redactions()
            coincidencias += hits_pagina
            paginas_afectadas += 1

    return coincidencias, paginas_afectadas, len(terminos) - len(terminos_con_hit)


def _reemplazar_terminos(titulo: str, terminos: Sequence[str]) -> str:
    """Sustituye cada término (sin distinguir mayúsculas) por un marcador neutro."""
    nuevo = titulo
    for t in terminos:
        nuevo = re.sub(re.escape(t), MARCADOR_OUTLINE, nuevo, flags=re.IGNORECASE)
    # Si por diferencias de normalización (ligaduras, etc.) aún quedara el término,
    # se descarta el título entero.
    if _contiene_termino(nuevo, _terminos_normalizados(terminos)):
        return MARCADOR_OUTLINE
    return nuevo


def _sanear_outline(doc, terminos: Sequence[str]) -> int:
    """Sustituye términos en los títulos del outline. Devuelve nº de títulos cambiados."""
    toc = doc.get_toc(simple=False)
    if not toc:
        return 0

    cambios = 0
    nuevo_toc = []
    for entry in toc:
        nivel, titulo, pagina = entry[0], entry[1], entry[2]
        destino = entry[3] if len(entry) > 3 else None
        nuevo_titulo = _reemplazar_terminos(titulo, terminos)
        if nuevo_titulo != titulo:
            cambios += 1
        nuevo_toc.append(
            [nivel, nuevo_titulo, pagina, destino] if destino else [nivel, nuevo_titulo, pagina]
        )

    if cambios:
        doc.set_toc(nuevo_toc)
    return cambios


def _textos_anotacion(annot) -> List[str]:
    info = annot.info or {}
    return [info.get("content") or "", info.get("title") or "", info.get("subject") or ""]


def _textos_widget(widget) -> List[str]:
    """
    Todos los textos de un campo de formulario: nombre, valor, etiqueta y
    cada elemento de choice_values (lista de opciones de combos y listas).
    """
    textos: List[str] = []

    def anadir(valor) -> None:
        if isinstance(valor, (list, tuple)):  # opciones como pares [exportado, visible]
            for v in valor:
                anadir(v)
        elif valor:
            textos.append(str(valor))

    anadir(widget.field_name)
    anadir(widget.field_value)
    anadir(widget.field_label)
    anadir(widget.choice_values)
    return textos


def _formularios_con_termino(doc, indices: Sequence[int], terminos: Sequence[str]) -> bool:
    """True si algún campo de formulario de las páginas seleccionadas contiene un término."""
    norm = _terminos_normalizados(terminos)
    for idx in indices:
        page = doc.load_page(idx)
        for widget in page.widgets():
            if any(_contiene_termino(t, norm) for t in _textos_widget(widget)):
                return True
    return False


def _aplanar_formularios(doc) -> None:
    """
    Convierte los campos de formulario en contenido fijo de página.

    ATENCIÓN: ``bake`` aplana los campos de TODO el documento (no solo los que
    contienen un término) y el PDF deja de ser un formulario. Las anotaciones
    (annots=False) y los enlaces se conservan. Tras el bake el valor de cada
    campo pasa a ser texto de página, que la redacción normal puede tachar.
    Los objetos Page anteriores quedan invalidados: hay que recargarlos con
    ``doc.load_page`` (``_redactar`` ya lo hace en cada iteración).
    """
    doc.bake(annots=False, widgets=True)


def _borrar_anotaciones(page, condicion) -> int:
    """
    Borra las anotaciones que cumplan la condición.

    No se reutiliza el valor devuelto por Page.delete_annot (inválido en 1.25.1):
    tras cada borrado se vuelve a recorrer la página desde cero.
    """
    borradas = 0
    limite = sum(1 for _ in page.annots()) + 1
    for _ in range(limite):
        objetivo = next((a for a in page.annots() if condicion(a)), None)
        if objetivo is None:
            return borradas
        page.delete_annot(objetivo)
        borradas += 1
    raise RuntimeError("No se pudieron eliminar todas las anotaciones previstas.")


def _sanear_anotaciones(doc, indices: Sequence[int], terminos: Sequence[str]) -> int:
    """Elimina anotaciones (en páginas seleccionadas) cuyo content/title/subject contenga un término."""
    norm = _terminos_normalizados(terminos)
    total = 0
    for idx in indices:
        page = doc.load_page(idx)
        total += _borrar_anotaciones(
            page, lambda a: any(_contiene_termino(t, norm) for t in _textos_anotacion(a))
        )
    return total


def _eliminar_adjuntos_anotacion(doc) -> int:
    """
    Elimina TODAS las anotaciones de fichero adjunto (todas las páginas).

    scrub(attached_files=True) falla con TypeError en PyMuPDF 1.25.1 si existe
    alguna, y vaciar el adjunto no es suficiente de todos modos.
    """
    total = 0
    for page in doc:
        total += _borrar_anotaciones(
            page, lambda a: a.type[0] == fitz.PDF_ANNOT_FILE_ATTACHMENT
        )
    return total


def _aplicar_scrub(doc) -> None:
    """scrub() con parámetros explícitos (no se depende de los valores por defecto)."""
    doc.scrub(
        metadata=True,          # Info
        xml_metadata=True,      # XMP
        attached_files=True,
        embedded_files=True,
        hidden_text=True,
        clean_pages=True,
        javascript=True,
        # URLs y mailto de los enlaces pueden contener datos del cliente.
        remove_links=True,
        # False: si ningún campo contiene un término, sus valores deben conservarse.
        # verificar_salida ya revisa nombre, valor, etiqueta y opciones de cada campo;
        # los campos con término se aplanan con bake antes de redactar.
        reset_fields=False,
        # False por un bug de PyMuPDF 1.25.1: delete_responses lanza AttributeError
        # con cualquier anotación. Las respuestas con término ya se eliminan en
        # _sanear_anotaciones y la verificación final revisa las anotaciones restantes.
        reset_responses=False,
        thumbnails=True,
        redactions=True,
        redact_images=0,
    )


# ======================================================
# VERIFICACIÓN DEL TEMPORAL
# ======================================================

def verificar_salida(
    path: Path,
    terminos: Sequence[str],
    indices: Sequence[int],
    paginas_originales: int,
) -> List[str]:
    """
    Reabre el PDF de salida y devuelve las categorías de fallo (vacía = verificado).
    Nunca incluye términos ni texto del documento.
    """
    fallos: List[str] = []

    def marcar(categoria: str) -> None:
        if categoria not in fallos:
            fallos.append(categoria)

    norm = _terminos_normalizados(terminos)
    flags_sin_recorte = fitz.TEXTFLAGS_TEXT & ~fitz.TEXT_MEDIABOX_CLIP

    doc = fitz.open(str(path))
    try:
        if doc.page_count != paginas_originales:
            marcar("num_paginas")

        for idx in indices:
            if idx >= doc.page_count:
                marcar("num_paginas")
                continue
            page = doc.load_page(idx)

            if any(_buscar(page, t) for t in terminos):
                marcar("search_for")
            if _contiene_termino(page.get_text(), norm):
                marcar("texto_normalizado")
            # Texto fuera del área visible de la página (MEDIABOX) también cuenta.
            if _contiene_termino(page.get_text("text", flags=flags_sin_recorte), norm):
                marcar("texto_fuera_de_pagina")

            for annot in page.annots():
                if any(_contiene_termino(t, norm) for t in _textos_anotacion(annot)):
                    marcar("anotaciones")

            for widget in page.widgets():
                if any(_contiene_termino(t, norm) for t in _textos_widget(widget)):
                    marcar("campos_formulario")

            for link in page.get_links():
                if _contiene_termino(str(link.get("uri") or ""), norm):
                    marcar("enlaces")

        # Metadatos Info: ningún valor (ni estándar ni personalizado).
        if any(v for k, v in (doc.metadata or {}).items() if k not in ("format", "encryption")):
            marcar("metadatos_info")
        info = doc.xref_get_key(-1, "Info")
        if info[0] == "xref":
            if doc.xref_get_keys(int(info[1].split()[0])):
                marcar("metadatos_info")

        if (doc.get_xml_metadata() or "").strip():
            marcar("metadatos_xmp")

        if doc.embfile_count() != 0:
            marcar("adjuntos")
        for page in doc:
            for annot in page.annots(types=[fitz.PDF_ANNOT_FILE_ATTACHMENT]):
                marcar("adjuntos")
                break

        if any(_contiene_termino(entry[1], norm) for entry in doc.get_toc()):
            marcar("outline")

        if any(_contiene_termino(nombre, norm) for nombre in doc.resolve_names().keys()):
            marcar("nombres_destino")
    finally:
        doc.close()

    return fallos


# ======================================================
# TEMPORAL Y PROMOCIÓN (mínimos y propios)
# ======================================================

def _crear_ruta_temporal(output_dir: Path) -> Path:
    """Ruta oculta con token aleatorio en el MISMO directorio de destino (mismo volumen)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"{PREFIJO_TEMPORAL}{secrets.token_hex(8)}.pdf"


def _promover(temp_path: Path, output_dir: Path, stem: str) -> Path:
    """
    Nombre final libre (resolve_conflict) + comprobación justo antes + os.replace.

    Nunca sobrescribe: si el nombre aparece ocupado en el último instante se
    busca otro. (Queda la ventana, mínima, entre la comprobación y os.replace.)
    """
    base = output_dir / f"{stem}{SUFIJO_SALIDA}.pdf"
    for _ in range(20):
        final = resolve_conflict(base, pattern=PATRON_CONFLICTO)
        if os.path.lexists(final):
            continue
        os.replace(temp_path, final)
        if not final.is_file():
            raise OSError("El archivo final no existe tras la promoción.")
        return final
    raise OSError("No se pudo reservar un nombre de salida libre.")


# ======================================================
# FUNCIÓN PRINCIPAL POR PDF
# ======================================================

def censurar_pdf(
    input_path: Path,
    output_dir: Path,
    words: Optional[Iterable[str]],
    pages: Optional[Collection[int]] = None,
    *,
    detectar_importes: bool = True,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> ResultadoCensura:
    """
    Censura un PDF (páginas 1-based en ``pages``; None = todas) con política fail-closed.

    Lanza ValueError si no hay términos y la detección de importes está desactivada,
    y CancelledByUser si se cancela (sin dejar temporales). Cualquier otro problema
    se devuelve como ResultadoCensura con estado "error" u "omitido".
    """
    if fitz is None:
        raise RuntimeError("Falta dependencia 'pymupdf'.")

    terminos_usuario = validar_terminos(words, detectar_importes)
    input_path = Path(input_path)
    output_dir = Path(output_dir)

    doc = None
    temp_path: Optional[Path] = None

    try:
        try:
            doc = fitz.open(str(input_path))
        except Exception:
            return ResultadoCensura.fallo(MotivoCensura.PDF_NO_ABRE)

        if not doc.is_pdf or doc.page_count == 0:
            return ResultadoCensura.fallo(MotivoCensura.PDF_NO_ABRE)
        if doc.needs_pass or doc.is_encrypted:
            return ResultadoCensura.fallo(MotivoCensura.PDF_CIFRADO)

        total_paginas = doc.page_count
        indices = _resolver_paginas(pages, total_paginas)
        if indices is None:
            return ResultadoCensura.fallo(MotivoCensura.RANGO_INVALIDO)

        _comprobar_cancelacion(is_cancelled)

        # a/b. Capa de texto y avisos por página (antes de tocar nada).
        analisis = _analizar_paginas(doc, indices, is_cancelled)
        avisos = dict(
            paginas_con_imagenes=analisis.con_imagenes,
            paginas_solo_vectoriales=analisis.solo_vectoriales,
            paginas_sin_capa_texto=analisis.sin_capa_texto,
        )
        if analisis.sin_capa_texto:
            return ResultadoCensura.fallo(MotivoCensura.SIN_CAPA_TEXTO, **avisos)

        # Regla opcional de importes.
        terminos = list(terminos_usuario)
        if detectar_importes:
            try:
                extra = detectar_importes_auto(_texto_documento(doc, is_cancelled))
            except ImporteNoInterpretable:
                return ResultadoCensura.fallo(MotivoCensura.IMPORTE_NO_INTERPRETABLE, **avisos)
            terminos = preparar_terminos(terminos + extra)

        # Contadores conocidos a partir de aquí (se arrastran a cualquier resultado).
        info = dict(
            avisos,
            terminos_buscados=len(terminos),
            # Términos realmente añadidos por la regla (sin duplicar los del usuario).
            importes_autodetectados=len(terminos) - len(terminos_usuario),
        )

        # b2. Formularios: si algún campo contiene un término, se aplanan los campos
        # (bake) para que su contenido pase a ser texto de página y pueda tacharse.
        # Si ningún campo lo contiene, el formulario se conserva intacto.
        if terminos and _formularios_con_termino(doc, indices, terminos):
            _aplanar_formularios(doc)
            info["formularios_aplanados"] = True

        # c. Redacción (recarga cada página con load_page: tras el bake las anteriores
        # quedan invalidadas).
        coincidencias, paginas_afectadas, sin_coincidencia = _redactar(
            doc, indices, terminos, is_cancelled
        ) if terminos else (0, 0, 0)

        if coincidencias == 0:
            # search_for puede fallar (p. ej. ligaduras) aunque el término esté en el texto:
            # eso NO es "omitido", es un riesgo de fuga.
            if _contiene_termino(_texto_paginas(doc, indices), _terminos_normalizados(terminos)):
                return ResultadoCensura.fallo(
                    MotivoCensura.VERIFICACION_FALLIDA,
                    fallos_verificacion=("coincidencia_no_localizada",),
                    **info,
                )
            return ResultadoCensura(
                estado=EstadoCensura.OMITIDO,
                motivo=MotivoCensura.SIN_COINCIDENCIAS,
                terminos_sin_coincidencias=len(terminos),
                **info,
            )

        # d/e. Saneado y scrub.
        _sanear_outline(doc, terminos)
        _sanear_anotaciones(doc, indices, terminos)
        _eliminar_adjuntos_anotacion(doc)
        _aplicar_scrub(doc)

        # f. Guardar a temporal en el destino y verificar reabriéndolo.
        _comprobar_cancelacion(is_cancelled)
        temp_path = _crear_ruta_temporal(output_dir)
        doc.save(str(temp_path), garbage=4, deflate=True)
        doc.close()
        doc = None

        try:
            fallos = verificar_salida(temp_path, terminos, indices, total_paginas)
        except Exception:
            fallos = ["error_verificacion"]

        if fallos:
            return ResultadoCensura.fallo(
                MotivoCensura.VERIFICACION_FALLIDA,
                coincidencias=coincidencias,
                paginas_afectadas=paginas_afectadas,
                fallos_verificacion=tuple(fallos),
                **info,
            )

        # g. Promoción atómica.
        _comprobar_cancelacion(is_cancelled)
        final = _promover(temp_path, output_dir, input_path.stem)

        return ResultadoCensura(
            estado=EstadoCensura.PROCESADO,
            motivo=MotivoCensura.OK,
            coincidencias=coincidencias,
            paginas_afectadas=paginas_afectadas,
            terminos_sin_coincidencias=sin_coincidencia,
            output_path=final,
            **info,
        )

    except CancelledByUser:
        raise
    except Exception as exc:
        # Solo el tipo de excepción: el mensaje podría incluir rutas o texto.
        logger.error(f"[PDF-CENSURA] Error interno ({type(exc).__name__})")
        return ResultadoCensura.fallo(MotivoCensura.ERROR_INTERNO)
    finally:
        # h. Limpieza siempre (éxito, error o cancelación).
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass
        safe_unlink(temp_path)


# ======================================================
# RESUMEN DE LOTE
# ======================================================

@dataclass
class ResumenLote:
    """Acumulador de resultados de un lote; genera el mensaje final sin datos sensibles."""

    total: int
    procesados: int = 0
    omitidos: int = 0
    errores: int = 0
    errores_por_motivo: Counter = field(default_factory=Counter)
    terminos_sin_coincidencias: int = 0
    terminos_buscados: int = 0
    paginas_con_imagenes: int = 0
    paginas_solo_vectoriales: int = 0
    # Solo de PDFs procesados:
    coincidencias: int = 0
    paginas_afectadas: int = 0
    importes_autodetectados: int = 0
    pdf_con_formularios_aplanados: int = 0
    # Categorías de fallos_verificacion de los PDFs con verificación fallida.
    fallos_verificacion: Counter = field(default_factory=Counter)
    # (nombre base, motivo): los nombres solo se usan en el mensaje visible.
    omitidos_detalle: List[Tuple[str, MotivoCensura]] = field(default_factory=list)
    errores_detalle: List[Tuple[str, MotivoCensura]] = field(default_factory=list)
    archivos: List[Path] = field(default_factory=list)
    # (nombre original, resultado) por PDF: permite recalcular en revalidar_archivos().
    _registros: list = field(default_factory=list, init=False, repr=False)

    def agregar(self, r: ResultadoCensura, nombre: Optional[str] = None) -> None:
        self._registros.append((nombre, r))
        base = _nombre_base(nombre)

        if r.estado == EstadoCensura.PROCESADO:
            self.procesados += 1
            if r.output_path is not None:
                self.archivos.append(Path(r.output_path))
            self.coincidencias += r.coincidencias
            self.paginas_afectadas += r.paginas_afectadas
            self.importes_autodetectados += r.importes_autodetectados
            if r.formularios_aplanados:
                self.pdf_con_formularios_aplanados += 1
        elif r.estado == EstadoCensura.OMITIDO:
            self.omitidos += 1
            self.omitidos_detalle.append((base, r.motivo))
        else:
            self.errores += 1
            self.errores_por_motivo[r.motivo] += 1
            self.errores_detalle.append((base, r.motivo))
            if r.motivo == MotivoCensura.VERIFICACION_FALLIDA:
                # Sin categorías = causa desconocida: se trata como comprobación interna.
                for categoria in r.fallos_verificacion or ("error_verificacion",):
                    self.fallos_verificacion[categoria] += 1
            return  # los avisos de un PDF fallido son parciales: no se suman

        self.terminos_sin_coincidencias += r.terminos_sin_coincidencias
        self.terminos_buscados += r.terminos_buscados
        self.paginas_con_imagenes += r.paginas_con_imagenes
        self.paginas_solo_vectoriales += r.paginas_solo_vectoriales

    def archivos_existentes(self) -> List[Path]:
        return [p for p in self.archivos if Path(p).is_file()]

    def revalidar_archivos(self) -> int:
        """
        Comprueba que cada PDF "procesado" tiene su archivo de salida (existe y es
        archivo). Si no, lo reclasifica como error ARCHIVO_NO_ENCONTRADO y recalcula
        todos los contadores. Devuelve cuántos reclasificó.
        """
        recalculado = ResumenLote(total=self.total)
        reclasificados = 0
        for nombre, r in self._registros:
            if r.estado == EstadoCensura.PROCESADO and not _es_archivo(r.output_path):
                r = ResultadoCensura.fallo(MotivoCensura.ARCHIVO_NO_ENCONTRADO)
                reclasificados += 1
            recalculado.agregar(r, nombre)

        if reclasificados:
            for f in dataclass_fields(self):
                setattr(self, f.name, getattr(recalculado, f.name))
        return reclasificados

    def _causas_verificacion(self) -> str:
        causas = {
            CAUSAS_VERIFICACION.get(cat, CAUSA_COMPROBACION_INTERNA)
            for cat in self.fallos_verificacion
        }
        return _unir_lista([c for c in ORDEN_CAUSAS if c in causas]) or CAUSA_COMPROBACION_INTERNA

    def mensaje(self) -> str:
        """
        Mensaje visible para el usuario: español llano y UNA sola línea.

        Es el único sitio donde aparecen nombres de archivo (solo el nombre base).
        Nunca debe enviarse a logs ni a excepciones. Sin términos ni rutas.
        """
        partes: List[str] = []

        if self.procesados:
            partes.append(
                f"Censura completada en {self.procesados} de {self.total} PDF(s): "
                f"{self.coincidencias} coincidencia(s) tachada(s) en "
                f"{self.paginas_afectadas} página(s)."
            )
        else:
            partes.append("No se ha creado ningún archivo.")

        if self.omitidos:
            nombres = _texto_nombres(n for n, _ in self.omitidos_detalle)
            partes.append(
                f"{self.omitidos} PDF(s) sin coincidencias; no se ha creado archivo{nombres}."
            )

        motivos = list(ORDEN_ERRORES) + sorted(
            (m for m in self.errores_por_motivo if m not in ORDEN_ERRORES),
            key=lambda m: m.value,
        )
        for motivo in motivos:
            n = self.errores_por_motivo.get(motivo, 0)
            if not n:
                continue
            plantilla = FRASES_ERROR.get(motivo, FRASES_ERROR[MotivoCensura.ERROR_INTERNO])
            frase = plantilla.format(n=n, causas=self._causas_verificacion())
            nombres = _texto_nombres(nom for nom, m in self.errores_detalle if m == motivo)
            partes.append(f"{frase}{nombres}.")

        if self.total == 1 and self.terminos_sin_coincidencias > 0:
            if self.terminos_buscados == 1:
                partes.append("La palabra no se encontró.")
            elif self.terminos_sin_coincidencias == 1:
                partes.append(
                    f"1 de las {self.terminos_buscados} palabras no se encontró."
                )
            else:
                partes.append(
                    f"{self.terminos_sin_coincidencias} de las {self.terminos_buscados} "
                    "palabras no se encontraron."
                )

        if self.paginas_con_imagenes:
            partes.append(
                f"Aviso: {self.paginas_con_imagenes} página(s) contienen imágenes. "
                "Si el texto está dentro de una imagen (por ejemplo, un DNI fotografiado) "
                "no se puede censurar automáticamente: revísalas."
            )

        if self.paginas_solo_vectoriales:
            partes.append(
                f"Aviso: {self.paginas_solo_vectoriales} página(s) sin texto con dibujos; "
                "si contienen texto convertido en trazados no se ha podido censurar: "
                "revísalas."
            )

        if self.importes_autodetectados:
            partes.append(
                f"Se detectaron {self.importes_autodetectados} importe(s) con la regla "
                "«Siendo … lo pagado»."
            )

        if self.pdf_con_formularios_aplanados:
            partes.append("Los campos de formulario se han convertido en contenido fijo.")

        return " ".join(partes)


# ======================================================
# AUXILIARES DEL MENSAJE
# ======================================================

def _es_archivo(path: Optional[Path]) -> bool:
    try:
        return path is not None and Path(path).is_file()
    except OSError:
        return False


def _nombre_base(nombre: Optional[str]) -> str:
    """Solo el nombre del archivo (sin carpetas) y en una línea; "" si no hay."""
    if not nombre:
        return ""
    return " ".join(Path(str(nombre)).name.split())


def _unir_lista(elementos: Sequence[str]) -> str:
    """'a', 'a y b', 'a, b y c'."""
    elementos = list(elementos)
    if len(elementos) <= 1:
        return "".join(elementos)
    return ", ".join(elementos[:-1]) + " y " + elementos[-1]


def _texto_nombres(nombres: Iterable[str]) -> str:
    """' (a.pdf, b.pdf y 3 más)': máximo MAX_NOMBRES_MENSAJE nombres; '' si no hay."""
    nombres = [n for n in nombres if n]
    if not nombres:
        return ""
    visibles = nombres[:MAX_NOMBRES_MENSAJE]
    texto = ", ".join(visibles)
    resto = len(nombres) - len(visibles)
    if resto > 0:
        texto += f" y {resto} más"
    return f" ({texto})"
