from pathlib import Path

# -------------------------------------------------
# Memoria de sesión (NO persistente)
# -------------------------------------------------
_rutas_sesion = {}


def get_ruta(tipo=None):
    """
    Devuelve la ruta guardada en sesión para 'tipo'.
    NO abre diálogos y NO persiste en disco.
    """
    return _rutas_sesion.get(tipo)


def set_ruta(tipo, ruta):
    """
    Guarda ruta en memoria de sesión (compatibilidad con scripts existentes).
    """
    if not ruta:
        return
    _rutas_sesion[tipo] = str(Path(ruta))


def reset_ruta(tipo=None):
    """
    Elimina la ruta en memoria para 'tipo' (opcional).
    """
    if tipo in _rutas_sesion:
        del _rutas_sesion[tipo]
