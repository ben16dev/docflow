import logging
import threading
import time
import getpass
import re
from pathlib import Path


# =====================================================
# CONFIGURACIÓN DE ROTACIÓN
# =====================================================

MAX_LOG_BYTES = 5 * 1024 * 1024   # 5 MB por archivo
BACKUP_COUNT = 5                   # 5 archivos rotados (.1 a .5)


# =====================================================
# UTIL: usuario Windows + nombre de fichero seguro
# =====================================================

def _safe_filename_part(value: str, fallback: str = "unknown") -> str:
    """
    Convierte el usuario a un fragmento seguro para nombres de archivo en Windows.
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


WINDOWS_USER = _safe_filename_part(getpass.getuser()) + " v2"


# =====================================================
# RUTA DE RED + FALLBACK LOCAL CONTROLADO
# =====================================================

NETWORK_DIR = Path(
    r"\\FILESTATION\Datos EDV\2.1 Clientes Archivo Asuntos\01491 CALIDAD\ORDENADO\COMUN\10_ABOGADOS\ALG\EDV_LOGS"
)
NETWORK_FILE = NETWORK_DIR / f"edv_app_{WINDOWS_USER}.log"

# Fallback local controlado y estable (no Escritorio)
LOCAL_DIR = Path.home() / "AppData" / "Local" / "EDV_AppScript" / "logs"
LOCAL_FILE = LOCAL_DIR / f"edv_app_{WINDOWS_USER}.log"
ERROR_FILE = LOCAL_DIR / "__network_log_error.txt"


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

    Tolerante a fallos: si algún rename falla (archivo en uso, red caída),
    no lanza excepción y deja el log actual tal cual.
    """
    try:
        if not current_path.exists():
            return False

        if current_path.stat().st_size < MAX_LOG_BYTES:
            return False

        # Borrar el backup más antiguo si existe
        oldest = current_path.with_suffix(current_path.suffix + f".{BACKUP_COUNT}")
        if oldest.exists():
            try:
                oldest.unlink()
            except Exception:
                # Si no se puede borrar, abortamos la rotación
                return False

        # Mover .{N-1} -> .{N}, ..., .1 -> .2
        for i in range(BACKUP_COUNT - 1, 0, -1):
            src = current_path.with_suffix(current_path.suffix + f".{i}")
            dst = current_path.with_suffix(current_path.suffix + f".{i + 1}")
            if src.exists():
                try:
                    src.rename(dst)
                except Exception:
                    # Si falla un rename intermedio, abortamos
                    return False

        # Mover .log -> .log.1
        first_backup = current_path.with_suffix(current_path.suffix + ".1")
        try:
            current_path.rename(first_backup)
        except Exception:
            return False

        return True

    except Exception:
        return False


# =====================================================
# HANDLER CONMUTABLE (local -> red) SIN BLOQUEAR UI
# =====================================================

class SwitchingFileHandler(logging.Handler):
    """
    Arranca escribiendo en LOCAL para no bloquear la app.
    Intenta promocionar a RED en segundo plano.
    Si RED falla, sigue en LOCAL sin romper ejecución.

    Rota archivos por tamaño (MAX_LOG_BYTES) con BACKUP_COUNT backups.
    """

    def __init__(self, encoding="utf-8", retry_seconds=10):
        super().__init__()
        self.encoding = encoding
        self.retry_seconds = retry_seconds

        self._lock = threading.Lock()
        self._stream = None
        self._using_network = False
        self._current_path = None
        self._last_retry = 0.0
        self._retry_in_progress = False

        # Arranque SIEMPRE local, sin tocar red
        self._stream = self._open_local_safely()
        self._current_path = LOCAL_FILE if self._stream is not None else None

    def _write_error_hint(self, exc: Exception) -> None:
        try:
            LOCAL_DIR.mkdir(parents=True, exist_ok=True)
            with open(ERROR_FILE, "a", encoding="utf-8") as f:
                f.write(
                    f"{time.strftime('%Y-%m-%d %H:%M:%S')} | ERROR RED LOG: {exc}\n"
                )
        except Exception:
            pass

    def _open_network(self):
        NETWORK_DIR.mkdir(parents=True, exist_ok=True)
        return open(NETWORK_FILE, "a", encoding=self.encoding)

    def _open_local_safely(self):
        try:
            LOCAL_DIR.mkdir(parents=True, exist_ok=True)
            return open(LOCAL_FILE, "a", encoding=self.encoding)
        except Exception:
            return None

    def _swap_stream(self, new_stream, new_path: Path, using_network: bool) -> None:
        old_stream = self._stream
        self._stream = new_stream
        self._current_path = new_path
        self._using_network = using_network

        if old_stream and old_stream is not new_stream:
            try:
                old_stream.close()
            except Exception:
                pass

    def _reopen_after_rotation(self) -> None:
        """
        Cierra el stream actual y reabre el archivo (que ahora estará vacío
        porque se ha renombrado a .1). Debe llamarse con el lock tomado.
        """
        try:
            if self._stream:
                self._stream.close()
        except Exception:
            pass

        try:
            if self._using_network:
                self._stream = self._open_network()
                self._current_path = NETWORK_FILE
            else:
                self._stream = self._open_local_safely()
                self._current_path = LOCAL_FILE
        except Exception as e:
            self._write_error_hint(e)
            # Fallback duro a local si la reapertura falla
            self._stream = self._open_local_safely()
            self._current_path = LOCAL_FILE
            self._using_network = False

    def _should_retry_network(self) -> bool:
        now = time.time()
        return (now - self._last_retry) >= self.retry_seconds

    def _schedule_network_retry(self) -> None:
        with self._lock:
            if self._using_network:
                return
            if self._retry_in_progress:
                return
            if not self._should_retry_network():
                return

            self._retry_in_progress = True
            self._last_retry = time.time()

        t = threading.Thread(target=self._background_promote_to_network, daemon=True)
        t.start()

    def _background_promote_to_network(self) -> None:
        new_stream = None
        try:
            new_stream = self._open_network()
        except Exception as e:
            self._write_error_hint(e)
        finally:
            with self._lock:
                if new_stream:
                    self._swap_stream(new_stream, NETWORK_FILE, using_network=True)
                self._retry_in_progress = False

    def emit(self, record):
        msg = self.format(record)

        # 1) Comprobar rotación + escribir en el stream actual
        with self._lock:
            stream = self._stream
            using_network = self._using_network
            current_path = self._current_path

            if stream is None:
                self._stream = self._open_local_safely()
                stream = self._stream
                self._current_path = LOCAL_FILE
                current_path = LOCAL_FILE
                using_network = False

            # Rotar si toca (antes de escribir)
            if current_path is not None and _rotate_if_needed(current_path):
                self._reopen_after_rotation()
                stream = self._stream

        if stream is not None:
            try:
                stream.write(msg + "\n")
                stream.flush()
            except Exception as e:
                self._write_error_hint(e)

                with self._lock:
                    # Si falla el stream actual, volvemos a local
                    new_stream = self._open_local_safely()
                    self._swap_stream(new_stream, LOCAL_FILE, using_network=False)
                    stream = self._stream

                if stream is not None:
                    try:
                        stream.write(msg + "\n")
                        stream.flush()
                    except Exception:
                        pass

        # 2) Si seguimos en local, intentar promocionar a red en segundo plano
        if not using_network:
            self._schedule_network_retry()

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

_base_logger = logging.getLogger("EDV_AppScript")
_base_logger.setLevel(logging.INFO)
_base_logger.propagate = False

if not _base_logger.handlers:
    handler = SwitchingFileHandler(encoding="utf-8", retry_seconds=10)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | user=%(user)s | %(message)s"
    )
    handler.setFormatter(formatter)
    _base_logger.addHandler(handler)

logger = logging.LoggerAdapter(_base_logger, {"user": WINDOWS_USER})

