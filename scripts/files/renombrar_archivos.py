"""
Renombrar archivos — DocFlow

Herramienta general para renombrado masivo de archivos de cualquier tipo.

Flujo completo (sprints futuros):
  1. Selección de archivos (cualquier tipo y extensión)
  2. Visualización y gestión de la lista (eliminar, limpiar, reordenar)
  3. Introducción de nuevos nombres (vía TXT o pegado directo)
  4. Validaciones preventivas
  5. Previsualización de cambios
  6. Elección de modo (por defecto: copiar a nueva carpeta)
  7. Confirmación
  8. Ejecución
  9. Resumen final

Restricciones de producto:
  - La extensión original siempre se conserva.
  - El modo por defecto es COPIAR_A_CARPETA (nunca modifica originales).
  - Nunca se permite sobrescribir archivos existentes.
  - La ejecución se bloquea si se detectan conflictos.

Estado actual: Sprint 2
  La pestaña "Archivos" tiene panel de selección funcional.
  Los archivos se gestionan a través de SesionRenombrado (session.py).
  La ejecución real se implementará en sprints sucesivos.
"""

import tkinter as tk
from tkinter import messagebox

from ui.ui_thread import call_ui
from scripts.common.results import build_result

# ======================================================
# METADATOS
# ======================================================

SCRIPT_META = {
    "name": "Renombrar archivos",
    "category": "ARCHIVOS",
    "description": (
        "Renombrado masivo de archivos de cualquier tipo. "
        "Los nuevos nombres pueden introducirse desde un fichero TXT "
        "o pegarse directamente. La extensión original siempre se conserva."
    ),
    "version": "0.2.0",
    "author": "DocFlow",
}


# ======================================================
# RUN
# ======================================================

def run(progress=None, is_cancelled=None):
    """
    Punto de entrada del renombrador de archivos.

    Sprint 1 — Esqueleto:
      Muestra un aviso informativo. La lógica real se implementa
      en sprints posteriores siguiendo el flujo diseñado.
    """
    parent = call_ui(lambda: tk._get_default_root())

    call_ui(lambda: messagebox.showinfo(
        "Renombrar archivos — Próximamente",
        "Esta herramienta está en desarrollo.\n\n"
        "En la próxima versión podrás:\n"
        "  • Seleccionar archivos de cualquier tipo\n"
        "  • Introducir nuevos nombres desde TXT o pegado\n"
        "  • Previsualizar los cambios antes de aplicarlos\n"
        "  • Ejecutar el renombrado de forma segura",
        parent=parent,
    ))

    return build_result(
        message="Herramienta en desarrollo — Sprint 1",
        output_dir=None,
    )
