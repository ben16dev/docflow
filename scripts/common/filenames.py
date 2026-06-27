import re
import unicodedata
from pathlib import Path


INVALID_WINDOWS_CHARS = r'[\\/*?:"<>|]'


def sanitize_filename(name: str, max_len: int = 120, fallback: str = "salida") -> str:
    """
    Limpia un nombre de archivo/carpeta manteniendo compatibilidad Windows.
    """

    name = (name or "").strip()
    name = re.sub(INVALID_WINDOWS_CHARS, "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = name.rstrip(". ")

    if not name:
        name = fallback

    return name[:max_len]


def sanitize_filename_ascii(name: str, max_len: int = 120, fallback: str = "salida") -> str:
    """
    Limpia un nombre y elimina acentos.
    Útil para casos donde interesa máxima compatibilidad.
    """

    name = unicodedata.normalize("NFD", name or "")
    name = "".join(c for c in name if not unicodedata.combining(c))

    return sanitize_filename(name, max_len=max_len, fallback=fallback)


def resolve_conflict(path: Path, pattern: str = "_v{i}") -> Path:
    """
    Devuelve una ruta libre si ya existe el archivo.

    Ejemplo:
    archivo.pdf
    archivo_v2.pdf
    archivo_v3.pdf
    """

    path = Path(path)

    if not path.exists():
        return path

    folder = path.parent
    stem = path.stem
    suffix = path.suffix

    i = 2
    while True:
        candidate = folder / f"{stem}{pattern.format(i=i)}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1