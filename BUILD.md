\# Compilación de EDV AppScript



\## Requisitos previos



\- Python instalado

\- PyInstaller instalado:



```bash

python -m pip install pyinstaller

Ejecutar tests antes de compilar:

python -m pytest tests





\## Crear ejecutable



Se usa PyInstaller.





\## Comando

pyinstaller main.py ^

\--name "EDV AppScript" ^

\--onefile ^

\--windowed ^

\--icon=assets/icon.ico ^

\--add-data "assets/logo.png;assets" ^

\--add-data "assets/icon.ico;assets" ^

\--add-data "ui/icons;ui/icons" ^

\--hidden-import=pypdf ^

\--hidden-import=fitz ^

\--hidden-import=reportlab ^

\--hidden-import=docx ^

\--clean





\## Salida



El ejecutable se genera en:



dist/

