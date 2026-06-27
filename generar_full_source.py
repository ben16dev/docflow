from pathlib import Path

# ==============================
# CONFIGURACIÓN
# ==============================

# Carpeta raíz del proyecto (donde está este script)
ROOT_DIR = Path(__file__).parent

# Archivo de salida
OUTPUT_FILE = ROOT_DIR / "FULL_SOURCE.txt"

# Extensiones que queremos incluir
EXTENSIONS = {".py", ".md", ".json", ".txt", ".yaml"}

# Carpetas que queremos ignorar
EXCLUDE_DIRS = {
    "__pycache__",
    ".git",
    ".idea",
    ".vscode",
    "venv",
    "env",
    "dist",
    "build"
}


# ==============================
# GENERADOR
# ==============================

def should_exclude(path: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in path.parts)


def main():
    print("Generando FULL_SOURCE.txt...")
    files_included = 0

    with OUTPUT_FILE.open("w", encoding="utf-8") as outfile:

        for file_path in sorted(ROOT_DIR.rglob("*")):

            if file_path.is_file() and file_path.suffix in EXTENSIONS:

                if should_exclude(file_path):
                    continue

                relative_path = file_path.relative_to(ROOT_DIR)

                outfile.write("\n")
                outfile.write("#" * 80 + "\n")
                outfile.write(f"# FILE: {relative_path}\n")
                outfile.write("#" * 80 + "\n\n")

                try:
                    content = file_path.read_text(encoding="utf-8")
                except Exception as e:
                    outfile.write(f"# ERROR leyendo archivo: {e}\n\n")
                    continue

                outfile.write(content)
                outfile.write("\n\n")

                files_included += 1

    print(f"OK. Archivos incluidos: {files_included}")
    print(f"Archivo generado en: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
