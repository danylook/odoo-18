import os
import subprocess
import argparse

# Buscar inkscape en rutas comunes (Windows y Linux)
import shutil
INKSCAPE_PATHS = [
    r"C:\Program Files\Inkscape\bin\inkscape.com",
    r"C:\Program Files\Inkscape\inkscape.exe",
    "/usr/bin/inkscape",
    "/usr/local/bin/inkscape",
]
INKSCAPE_PATH = shutil.which("inkscape")
# Prefer snap version (1.3+) over system version (1.2.x) for correct PDF coordinate output
_snap_inkscape = "/snap/bin/inkscape"
if os.path.isfile(_snap_inkscape):
    INKSCAPE_PATH = _snap_inkscape
elif INKSCAPE_PATH is None:
    for path in INKSCAPE_PATHS:
        if os.path.isfile(path):
            INKSCAPE_PATH = path
            break
if INKSCAPE_PATH is None:
    print("No se encontró inkscape en las rutas comunes. Ajusta la variable INKSCAPE_PATH manualmente.")
    exit(1)
else:
    print(f"Usando Inkscape en: {INKSCAPE_PATH}")

# Carpeta donde están los PDFs
PDF_DIR = r"c:/odoo17/extra-addons/others-17.0/easyOCR/"
# Carpeta de salida para los SVGs
SVG_DIR = r"c:/odoo17/extra-addons/others-17.0/easyOCR/"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('pdf_path', nargs='?', default=None)
    parser.add_argument('output_dir', nargs='?', default=None)
    parser.add_argument('--only-page', type=int, default=None, help='Exportar solo la página N (1-indexed)')
    args, unknown = parser.parse_known_args()

    if args.pdf_path:
        pdf_files = [os.path.basename(args.pdf_path)]
        PDF_DIR = os.path.dirname(args.pdf_path)
    else:
        PDF_DIR = PDF_DIR
        pdf_files = [f for f in os.listdir(PDF_DIR) if f.lower().endswith('.pdf')]
    if args.output_dir:
        SVG_DIR = args.output_dir
    else:
        SVG_DIR = SVG_DIR

    try:
        import PyPDF2
        from PyPDF2 import PdfReader
    except ImportError:
        print("PyPDF2 no está instalado. Instala con: pip install PyPDF2")
        exit(1)

    for pdf_file in pdf_files:
        pdf_path = os.path.join(PDF_DIR, pdf_file)
        base_name = os.path.splitext(pdf_file)[0]
        # Obtener el número de páginas
        try:
            reader = PdfReader(pdf_path)
            num_pages = len(reader.pages)
        except Exception as e:
            print(f"Error leyendo {pdf_file}: {e}")
            continue
        print(f"Procesando {pdf_file} ({num_pages} páginas)...")
        if args.only_page:
            pages_to_export = [args.only_page]
        else:
            pages_to_export = range(1, num_pages+1)
        for page in pages_to_export:
            svg_out = os.path.join(SVG_DIR, f"{base_name}_page{page}.svg")
            # Eliminar el archivo si existe (simula --overwrite)
            if os.path.exists(svg_out):
                os.remove(svg_out)
            # Inkscape 1.3+ usa --pages=N; 1.2.x usa --pdf-page=N
            if INKSCAPE_USE_PAGES_ARG:
                cmd = [
                    INKSCAPE_PATH,
                    f"--pages={page}",
                    f"--export-type=svg",
                    f"--export-filename={svg_out}",
                    f"{pdf_path}",
                ]
            else:
                cmd = [
                    INKSCAPE_PATH,
                    f"{pdf_path}",
                    f"--export-type=svg",
                    f"--export-filename={svg_out}",
                    f"--pdf-page={page}",
                ]
            print(f"Exportando página {page} a {svg_out} ...")
            try:
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                print(f"Error exportando página {page} de {pdf_file}:")
                print(e.stderr)
                print(e.stdout)
            except Exception as e:
                print(f"Error inesperado exportando página {page} de {pdf_file}: {e}")
    print("Listo.")

if __name__ == "__main__":
    main()
