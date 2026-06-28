"""Mensajes de error comprensibles para la interfaz de usuario."""


def format_user_error(exc: BaseException) -> str:
    """
    Convierte una excepción en un mensaje breve y accionable para el usuario.
    El traceback completo debe registrarse por separado en el log.
    """
    if isinstance(exc, RuntimeError):
        message = str(exc).strip()
        if message:
            return message

    if isinstance(exc, PermissionError):
        return (
            "No tienes permisos suficientes para acceder al archivo o carpeta indicados."
        )

    if isinstance(exc, FileNotFoundError):
        return "No se encontró el archivo o carpeta indicados."

    if isinstance(exc, OSError):
        message = str(exc).strip()
        if message:
            return f"Error de acceso al sistema de archivos: {message}"
        return "Error de acceso al sistema de archivos."

    return (
        "Se ha producido un error inesperado durante la ejecución. "
        "Revisa el log para más detalles."
    )
