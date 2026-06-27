# DocFlow

Aplicación de escritorio en **Python (Tkinter + ttk)** para automatización documental local. Todos los documentos se procesan localmente, sin enviar datos a servidores externos.

## Funcionalidades principales

- Operaciones con **PDF** (unir, extraer páginas, rotar, numerar, renombrar, etc.)
- Conversión y procesado de **EML**
- Procesado de **MBOX**
- Utilidades de renombrado y automatización de tareas documentales
- Interfaz modular por pestañas y ejecución de procesos en segundo plano

## Novedades v2.8.0

- Refactorización interna segura de scripts PDF, EML y MBOX.
- Contrato unificado de resultados:
  ```python
  {
      "message": "...",
      "output_dir": "...",
      "stats": {...}
  }
  ```

- Mejora de cancelación de procesos (sin errores de UI).
- Mayor robustez en gestión de errores.
- Introducción de utilidades comunes:
  - Sanitizado de nombres
  - Gestión de conflictos de archivos
  - Parseo de rangos PDF
- Añadidos tests automáticos básicos con `pytest`.
- Sustitución de `config.json` por `config.example.json` (sin datos sensibles).

## Estructura del proyecto

- `main.py`: punto de entrada
- `ui/`: interfaz Tkinter (pestañas, estilos, logger UI, etc.)
- `scripts/`: scripts por categoría (`pdf/`, `eml/`, `mbox/`)
- `scripts/common/`: utilidades compartidas
- `tests/`: tests automáticos básicos
- `assets/`: iconos y recursos
- `tools/`: herramientas auxiliares
- `BUILD.md`: guía de empaquetado / compilación

## Requisitos

- Python 3.x
- Dependencias definidas en `requirements.txt`

## Ejecución

Desde la carpeta raíz:

```bash
python main.py
```

## Tests

Ejecutar antes de generar builds:

```bash
python -m pytest tests
```
