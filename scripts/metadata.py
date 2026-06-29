from typing import Dict, Any


REQUIRED_FIELDS = {
    "name",
    "category"
}

VALID_CATEGORIES = {"PDF", "EML", "MBOX", "ARCHIVOS"}

OPTIONAL_FIELDS = {
    "description",
    "version",
    "author"
}


def extract_metadata(module) -> Dict[str, Any]:
    """
    Extrae metadatos declarados en un script.

    Si no existen, genera un fallback seguro
    para no romper compatibilidad.
    """

    meta = getattr(module, "SCRIPT_META", None)

    if not isinstance(meta, dict):
        return _fallback_metadata(module)

    # Validación mínima de campos requeridos
    for field in REQUIRED_FIELDS:
        if field not in meta:
            return _fallback_metadata(module)

    # Validación de categoría
    if meta.get("category") not in VALID_CATEGORIES:
        return _fallback_metadata(module)

    return meta


def _fallback_metadata(module):

    name = getattr(module, "__name__", "script").split(".")[-1]

    return {
        "name": name.replace("_", " ").title(),
        "category": "unknown",
        "description": "",
        "version": "1.0",
        "author": ""
    }