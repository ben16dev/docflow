# Compilación de DocFlow

## Requisitos previos

- Python instalado
- PyInstaller instalado:

```bash
python -m pip install pyinstaller
```

Ejecutar tests antes de compilar:

```bash
python -m pytest tests
```

## Crear ejecutable

Se usa PyInstaller con el archivo `DocFlow.spec` incluido en el repositorio.

## Comando (Windows)

```bash
pyinstaller main.py ^
  --name "DocFlow" ^
  --onefile ^
  --windowed ^
  --icon=assets/icon.ico ^
  --add-data "assets/logo.png;assets" ^
  --add-data "assets/icon.ico;assets" ^
  --add-data "ui/icons;ui/icons" ^
  --hidden-import=pypdf ^
  --hidden-import=fitz ^
  --hidden-import=reportlab ^
  --hidden-import=docx ^
  --clean
```

## Salida

El ejecutable se genera en:

```
dist/
```
