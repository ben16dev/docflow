# TESTING.md — Checklist de regresión DocFlow

## 1. Propósito

Usar esta checklist para validar estabilidad sin inventar pasos ad hoc.

| Nivel | Cuándo |
|-------|--------|
| Rápida | Antes de un commit importante |
| Regresión funcional | Antes de generar un build |
| Release | Validación de plataforma + artefacto empaquetado |

No sustituye los tests automatizados (`pytest`); los complementa.

---

## 2. Comprobación rápida antes de un commit importante

- [ ] `git status`
- [ ] `git diff --stat`
- [ ] Suite completa: `.venv/bin/python -m pytest tests -v`
- [ ] Importación: `.venv/bin/python -c "from ui.app import App; print('Imports OK')"`
- [ ] Arranque manual: `python main.py` (o equivalente del venv)
- [ ] Navegación básica entre pestañas
- [ ] Sin errores visibles en consola ni diálogos inesperados

---

## 3. Regresión funcional antes de build

- [ ] MBOX: flujo principal de una herramienta
- [ ] EML: flujo principal de una herramienta
- [ ] PDF: flujo principal de una herramienta
- [ ] Archivos: herramienta de la pestaña Archivos
- [ ] Conversión: flujo principal
- [ ] Progreso visible durante una ejecución
- [ ] Cancelación: botón Cancelar → estado «Cancelado», UI recuperada (sin diálogo de error)
- [ ] Error real: provoca un fallo controlado
- [ ] Abrir log desde el diálogo de error
- [ ] Copiar mensaje desde el diálogo de error
- [ ] Recuperación: tras cerrar el diálogo se puede ejecutar otra herramienta

---

## 4. Validación macOS

- [ ] Apertura del log desde el diálogo (ubicación local de usuario)
- [ ] Detección / apertura de navegadores usada por herramientas
- [ ] Artefacto `.app` arranca
- [ ] Icono y recursos visibles en la app empaquetada
- [ ] Ejecución fuera del repositorio (copiar/mover el `.app` y abrir)

---

## 5. Validación Windows

- [ ] Apertura del log desde el diálogo (ubicación local de usuario)
- [ ] Chrome y Edge detectables / usables según la herramienta
- [ ] Artefacto `.exe` arranca
- [ ] Icono y recursos visibles en el ejecutable
- [ ] Ejecución fuera del repositorio

---

## 6. Empaquetado

```bash
.venv/bin/python -m PyInstaller DocFlow.spec --noconfirm --clean
```

Comprobaciones mínimas del artefacto:

- [ ] Build termina sin error
- [ ] Existe `dist/DocFlow.app` (macOS) o `dist/DocFlow.exe` (Windows) o `dist/DocFlow` (Linux)
- [ ] Arranque del artefacto
- [ ] Una herramienta de humo (éxito breve)
- [ ] Un error controlado: diálogo, abrir log, copiar mensaje, recuperación

Detalles de iconos y plataformas: ver `BUILD.md`.

---

## 7. Registro de resultado

| Campo | Valor |
|-------|--------|
| Fecha | |
| Plataforma | |
| Versión | |
| Resultado | OK / FAIL |
| Incidencias | |
| Pendiente | |
