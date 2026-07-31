"""
Entrypoint mínimo de OCRmyPDF para empaquetado PyInstaller.

No contiene lógica OCR propia: delega en ocrmypdf.__main__.run.
Necesario porque el script de la venv (.venv/bin/ocrmypdf) tiene un
shebang que apunta al intérprete del entorno virtual.
"""

from __future__ import annotations

from ocrmypdf.__main__ import run


if __name__ == "__main__":
    raise SystemExit(run())
