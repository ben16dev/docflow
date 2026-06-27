"""
Wrapper de compatibilidad para logger central.

Este archivo existe solo para mantener compatibilidad
con imports antiguos:

    from ui.logger import logger

El logger real está en:

    logger.py
"""

from logger import logger

__all__ = ["logger"]



