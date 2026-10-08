# Registro de decisiones (ADR)

Formato por entrada:

## ADR-NNN — Título (AAAA-MM-DD)

- Contexto:
- Decisión:
- Alternativas descartadas:
- Consecuencias:

## ADR-001 — Censura de PDF fail-closed (2026-10-08)

- Contexto: la censura por palabras fallaba en silencio (PDFs sin capa de texto, cero coincidencias contadas como procesado, metadatos y formularios intactos, sin verificación).
- Decisión: política fail-closed. Un PDF solo se escribe si el resultado, reabierto desde un temporal, supera la verificación; cualquier duda produce error sin archivo. Estados procesado/omitido/error. Lógica en `censura_core` sin UI. Formularios con término: aplanado y redacción. Revalidación de archivos al final del lote. Importes automáticos como opción visible y estricta. Los nombres de archivo solo aparecen en el mensaje visible, nunca en logs.
- Alternativas descartadas: censura sin verificación (fuga silenciosa); OCR automático antes de censurar (diferido: requiere diseño de cadena); umbral de tamaño para imágenes (un DNI pegado es pequeño); vaciar valores de campos (no fiable en PyMuPDF 1.25.1) o resetear todos los campos (pierde datos no sensibles); modificar `ocr_io` para reutilizar helpers (riesgo sobre código validado).
- Consecuencias: más PDFs terminan en error o aviso en lugar de salir «censurados»; el usuario debe aplicar OCR a los escaneados; quedan límites documentados (texto en imágenes, vectores, texto oculto, enlaces eliminados, formularios aplanados); la verificación añade coste de CPU; dependencia de PyMuPDF 1.25.1 con tres bugs sorteados (`scrub` `reset_responses`, `scrub` `attached_files`, `delete_annot`) que deben revisarse al actualizar la librería.
