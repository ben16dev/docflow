# Compilación de DocFlow

## Recursos visuales

### Estructura estándar de assets

```
assets/
├── icon.png      ← Fuente para generación de iconos (1024×1024 recomendado)
├── icon.ico      ← Generado automáticamente para Windows (no editar)
└── icon.icns     ← Generado automáticamente para macOS  (no editar)
```

### Archivo fuente

| Campo               | Valor recomendado                        |
|---------------------|------------------------------------------|
| Archivo             | `assets/icon.png`                        |
| Tamaño              | 1024×1024 px (mínimo recomendado 512×512)|
| Formato             | PNG                                      |
| Proporción          | Cuadrada (1:1 estricto)                  |
| Fondo               | Transparente o sólido según diseño       |

> **Nota:** `assets/icon.ico` y `assets/icon.icns` se generan automáticamente
> a partir de `assets/icon.png`. **No los edites manualmente.**

### Diferencias entre plataformas

| Plataforma | Formato | Resoluciones                           | Herramienta    |
|------------|---------|----------------------------------------|----------------|
| Windows    | `.ico`  | 16, 24, 32, 48, 64, 128, 256 px       | Pillow         |
| macOS      | `.icns` | 16→1024 px (todas las variantes Retina)| iconutil (nativo macOS) |

### Generar iconos

Coloca primero `assets/icon.png` (PNG cuadrado, 1024×1024) y luego ejecuta:

```bash
python generar_icono.py
```

El script:
- Genera `assets/icon.ico` multirresolución (válido en cualquier SO).
- Genera `assets/icon.icns` sólo si se ejecuta en macOS con `iconutil` disponible.
- Muestra mensajes claros de éxito o error.
- No sobrescribe silenciosamente archivos incompatibles.
- Limpia archivos temporales (`.iconset`) al terminar.

Si no dispones de `assets/icon.png`, el script mostrará un error descriptivo
y el resto del proyecto seguirá funcionando (la ventana arrancará sin icono).

---

## Requisitos previos para compilar

- Python instalado
- PyInstaller instalado:

```bash
python -m pip install pyinstaller
```

- Ejecutar tests antes de compilar:

```bash
python -m pytest tests -v
```

- Generar iconos si no existen:

```bash
python generar_icono.py
```

---

## Compilar con DocFlow.spec (recomendado)

```bash
pyinstaller DocFlow.spec --noconfirm --clean
```

El archivo `.spec` selecciona automáticamente el icono según la plataforma:
- **Windows** → `assets/icon.ico`
- **macOS** → `assets/icon.icns`
- **Linux** → `assets/icon.png` (si existe)

Los assets faltantes se omiten sin romper la compilación.

---

## Compilar en Windows (línea de comandos)

```bash
pyinstaller main.py ^
  --name "DocFlow" ^
  --onefile ^
  --windowed ^
  --icon=assets/icon.ico ^
  --add-data "assets/icon.png;assets" ^
  --add-data "assets/icon.ico;assets" ^
  --add-data "ui/icons;ui/icons" ^
  --hidden-import=pypdf ^
  --hidden-import=fitz ^
  --hidden-import=reportlab ^
  --hidden-import=docx ^
  --clean
```

## Compilar en macOS (línea de comandos)

```bash
pyinstaller main.py \
  --name "DocFlow" \
  --onefile \
  --windowed \
  --icon=assets/icon.icns \
  --add-data "assets/icon.png:assets" \
  --add-data "assets/icon.ico:assets" \
  --add-data "assets/icon.icns:assets" \
  --add-data "ui/icons:ui/icons" \
  --hidden-import=pypdf \
  --hidden-import=fitz \
  --hidden-import=reportlab \
  --hidden-import=docx \
  --clean
```

> En macOS el separador de `--add-data` es `:` y en Windows es `;`.
> El `.spec` incluido gestiona esto automáticamente.

---

## Salida

El ejecutable se genera en:

```
dist/
```

---

## Archivos que NO deben editarse manualmente

- `assets/icon.ico` — generado por `generar_icono.py`
- `assets/icon.icns` — generado por `generar_icono.py` (macOS)
- `DocFlow.spec` — archivo de empaquetado; editar sólo con criterio
