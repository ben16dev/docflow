# Compilación de DocFlow

## Recursos visuales

### Estructura estándar de assets

```
assets/
├── icon.png      ← Fuente para generación de iconos (1024×1024 recomendado)
├── icon.ico      ← Generado automáticamente para Windows (no editar)
├── icon.icns     ← Generado automáticamente para macOS  (no editar)
└── logo.png      ← Logo horizontal mostrado en la cabecera de la aplicación
```

### Logo de cabecera (`assets/logo.png`)

| Campo       | Valor                                        |
|-------------|----------------------------------------------|
| Archivo     | `assets/logo.png`                            |
| Uso         | Cabecera superior de la ventana principal    |
| Fondo       | Transparente o que armonice con `#eaf4ff`    |
| Nombre      | Debe conservarse como `logo.png`             |

> **Nota:** El icono de aplicación (barra de título, Dock, barra de tareas) sigue
> dependiendo de `icon.png`, `icon.ico` e `icon.icns`. `logo.png` es exclusivamente
> el logo horizontal mostrado dentro de la interfaz. Si el archivo no existe en el
> momento de ejecutar, la aplicación muestra el nombre textual como alternativa.

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

El mismo comando funciona en macOS, Windows y Linux:

```bash
pyinstaller DocFlow.spec --noconfirm --clean
```

El archivo `.spec` selecciona automáticamente el icono y el formato de salida
según la plataforma en la que se ejecuta el build:

| Plataforma | Salida               | Icono usado          |
|------------|----------------------|----------------------|
| macOS      | `dist/DocFlow.app`   | `assets/icon.icns`   |
| Windows    | `dist/DocFlow.exe`   | `assets/icon.ico`    |
| Linux      | `dist/DocFlow`       | `assets/icon.png`    |

> **Importante:** los builds deben generarse en el sistema operativo de destino.
> No es posible compilar `DocFlow.app` desde Windows ni `DocFlow.exe` desde macOS.

---

## macOS

```bash
source .venv/bin/activate
python -m pip install pyinstaller
rm -rf build dist
pyinstaller DocFlow.spec --noconfirm --clean
open dist/DocFlow.app
```

Resultado esperado:

```
dist/DocFlow.app
```

Si macOS muestra un icono antiguo por caché de Finder o Dock:

```bash
touch dist/DocFlow.app
killall Dock
open dist/DocFlow.app
```

---

## Windows

```powershell
.venv\Scripts\activate
python -m pip install pyinstaller
pyinstaller DocFlow.spec --noconfirm --clean
```

Resultado esperado:

```
dist\DocFlow.exe
```

---

## Archivos que NO deben editarse manualmente

- `assets/icon.ico` — generado por `generar_icono.py`
- `assets/icon.icns` — generado por `generar_icono.py` (macOS)
- `DocFlow.spec` — archivo de empaquetado; editar sólo con criterio
