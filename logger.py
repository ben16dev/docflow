import getpass
import logging
import os
import platform
import re
import tempfile
import threading
from pathlib import Path


# =====================================================
# CONFIGURACIÓN DE ROTACIÓN
# =====================================================

MAX_LOG_BYTES = 5 * 1024 * 1024   # 5 MB por archivo
BACKUP_COUNT = 5                   # 5 archivos rotados (.1 a .5)


# =====================================================
# UTIL: usuario + nombre de fichero seguro
# =====================================================

def _safe_filename_part(value: str, fallback: str = "unknown") -> str:
    """
    Convierte un valor a un fragmento seguro para nombres de archivo.
    Permite letras, números, guion, guion bajo y punto.
    """
    try:
        value = (value or "").strip()
    except Exception:
        value = ""

    if not value:
        return fallback

    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return safe if safe else fallback


LOG_USER = _safe_filename_part(getpass.getuser())


def _resolve_log_dir() -> Path:
    """
    Resuelve la carpeta de logs local según la plataforma.

    Preferencias:
      - macOS:   ~/Library/Logs/DocFlow
      - Windows: %LOCALAPPDATA%/DocFlow/logs
      - Linux:   $XDG_STATE_HOME/DocFlow/logs o ~/.local/state/DocFlow/logs

    Si ninguna ruta preferida es usable, usa un fallback local seguro.
    """
    home = Path.home()
    system = platform.system()

    candidates: list[Path] = []

    if system == "Darwin":
        candidates.append(home / "Library" / "Logs" / "DocFlow")
    elif system == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            candidates.append(Path(local_app_data) / "DocFlow" / "logs")
        candidates.append(home / "AppData" / "Local" / "DocFlow" / "logs")
    else:
        xdg_state = os.environ.get("XDG_STATE_HOME")
        if xdg_state:
            candidates.append(Path(xdg_state) / "DocFlow" / "logs")
        candidates.append(home / ".local" / "state" / "DocFlow" / "logs")

    candidates.append(home / ".docflow" / "logs")
    candidates.append(Path(tempfile.gettempdir()) / "DocFlow" / "logs")

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write_probe"
            probe.write_text("", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return candidate
        except Exception:
            continue

    fallback = Path(tempfile.gettempdir()) / "DocFlow" / "logs"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


LOG_DIR = _resolve_log_dir()
LOG_FILE = LOG_DIR / f"docflow_{LOG_USER}.log"


# =====================================================
# ROTACIÓN POR TAMAÑO
# =====================================================

def _rotate_if_needed(current_path: Path) -> bool:
    """
    Si current_path supera MAX_LOG_BYTES, rota archivos:
      .log.4 -> .log.5 (descarta el viejo .5)
      .log.3 -> .log.4
      ...
      .log   -> .log.1

    Devuelve True si rotó, False si no hizo falta o falló.
    """
    try:
        if not current_path.exists():
            return False

        if current_path.stat().st_size < MAX_LOG_BYTES:
            return False

        oldest = current_path.with_suffix(current_path.suffix + f".{BACKUP_COUNT}")
        if oldest.exists():
            try:
                oldest.unlink()
            except Exception:
                return False

        for i in range(BACKUP_COUNT - 1, 0, -1):
            src = current_path.with_suffix(current_path.suffix + f".{i}")
            dst = current_path.with_suffix(current_path.suffix + f".{i + 1}")
            if src.exists():
                try:
                    src.rename(dst)
                except Exception:
                    return False

        first_backup = current_path.with_suffix(current_path.suffix + ".1")
        try:
            current_path.rename(first_backup)
        except Exception:
            return False

        return True

    except Exception:
        return False


# =====================================================
# HANDLER LOCAL CON ROTACIÓN
# =====================================================

class LocalFileHandler(logging.Handler):
    """
    Escribe logs en una ruta local multiplataforma con rotación por tamaño.
    """

    def __init__(self, log_path: Path, encoding="utf-8"):
        super().__init__()
        self.encoding = encoding
        self._lock = threading.Lock()
        self._stream = None
        self._current_path = log_path
        self._stream = self._open_log_file()

    def _open_log_file(self):
        try:
            self._current_path.parent.mkdir(parents=True, exist_ok=True)
            return open(self._current_path, "a", encoding=self.encoding)
        except Exception:
            return None

    def _reopen_after_rotation(self) -> None:
        try:
            if self._stream:
                self._stream.close()
        except Exception:
            pass

        self._stream = self._open_log_file()

    def emit(self, record):
        msg = self.format(record)

        with self._lock:
            if self._stream is None:
                self._stream = self._open_log_file()

            current_path = self._current_path

            if current_path is not None and _rotate_if_needed(current_path):
                self._reopen_after_rotation()

            stream = self._stream

        if stream is None:
            return

        try:
            stream.write(msg + "\n")
            stream.flush()
        except Exception:
            with self._lock:
                self._stream = self._open_log_file()
                stream = self._stream

            if stream is not None:
                try:
                    stream.write(msg + "\n")
                    stream.flush()
                except Exception:
                    pass

    def close(self):
        with self._lock:
            try:
                if self._stream:
                    self._stream.close()
            except Exception:
                pass
            self._stream = None

        super().close()


# =====================================================
# LOGGER PÚBLICO
# =====================================================

_base_logger = logging.getLogger("DocFlow")
_base_logger.setLevel(logging.INFO)
_base_logger.propagate = False

if not _base_logger.handlers:
    handler = LocalFileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | user=%(user)s | %(message)s"
    )
    handler.setFormatter(formatter)
    _base_logger.addHandler(handler)

logger = logging.LoggerAdapter(_base_logger, {"user": LOG_USER})
