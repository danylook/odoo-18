#!/usr/bin/env python3
"""Export each page of one or more PDF files to individual SVGs using Inkscape.

This version is tailored for Linux/Ubuntu environments where the `inkscape`
CLI is available on the system PATH.  It mirrors the behaviour of the Windows
script, keeping the command-line interface compatible while resolving the
binary automatically for typical Linux installs.
"""
from __future__ import annotations

import argparse
import importlib
import os
import shutil
import subprocess
import sys
from typing import Iterable


def resolve_inkscape_binary() -> str:
    """Locate the Inkscape executable on Linux systems.

    Priority order:
    1. `INKSCAPE_BINARY` environment variable (path or command).
    2. Snap install at /snap/bin/inkscape (preferred: 1.3+ with correct PDF coords).
    3. `shutil.which('inkscape')` to honour PATH lookups.
    4. Common install locations for Debian/Ubuntu packages.
    """
    env_candidate = os.environ.get("INKSCAPE_BINARY")
    if env_candidate:
        found = shutil.which(env_candidate) or (
            env_candidate if os.path.isfile(env_candidate) else None
        )
        if found:
            return found

    # Prefer snap version (1.3+) over system apt version (1.2.x) for correct
    # PDF coordinate output (negative translates matching Windows Inkscape 1.3+)
    if os.path.isfile("/snap/bin/inkscape"):
        return "/snap/bin/inkscape"

    path_candidate = shutil.which("inkscape")
    if path_candidate:
        return path_candidate

    if os.path.isfile("/usr/bin/inkscape"):
        return "/usr/bin/inkscape"

    return ""


def iter_pdf_files(directory: str) -> Iterable[str]:
    """Yield PDF filenames located in `directory` (non-recursive)."""
    for entry in sorted(os.listdir(directory)):
        if entry.lower().endswith(".pdf"):
            yield entry


def _inkscape_major_minor(inkscape_binary: str) -> tuple:
    """Return (major, minor) version tuple for the given Inkscape binary."""
    import re
    try:
        out = subprocess.run(
            [inkscape_binary, "--version"],
            capture_output=True, text=True, timeout=10
        )
        m = re.search(r'Inkscape\s+(\d+)\.(\d+)', out.stdout + out.stderr)
        if m:
            return (int(m.group(1)), int(m.group(2)))
    except Exception:
        pass
    return (1, 2)


def build_cmd(
    inkscape_binary: str,
    pdf_path: str,
    svg_output: str,
    page_number: int,
    use_export_page: bool = False,
) -> list:
    """Compose the Inkscape CLI arguments for a single-page SVG export.

    Inkscape 1.2.x:  --pdf-page=N  (placed after the PDF path)
    Inkscape 1.3+:   --pages=N     (placed before the PDF path)
    """
    version = _inkscape_major_minor(inkscape_binary)
    if version >= (1, 3):
        # 1.3+ syntax: --pages selects which page to import
        # NOTE: --pdf-poppler omitido para usar el Poppler bundled del snap de Inkscape,
        # garantizando resultados consistentes independientemente de la versión del sistema.
        return [
            inkscape_binary,
            "--batch-process",
            f"--pages={page_number}",
            "--export-type=svg",
            f"--export-filename={svg_output}",
            "--export-area-page",
            "--export-dpi=96",
            "--export-text-to-path",
            pdf_path,
        ]
    else:
        # 1.2.x syntax: --pdf-page=N placed after the PDF path
        return [
            inkscape_binary,
            "--batch-process",
            "--export-type=svg",
            f"--export-filename={svg_output}",
            "--export-area-page",
            "--export-dpi=96",
            "--export-text-to-path",
            pdf_path,
            f"--pdf-page={page_number}",
        ]

def ensure_pypdf2() -> None:
    try:
        import PyPDF2  # noqa: F401
    except ImportError:  # pragma: no cover - simple dependency guard
        print("PyPDF2 no está instalado. Instálalo con: pip install PyPDF2")
        sys.exit(1)


def count_pdf_pages(pdf_path: str) -> int:
    PyPDF2 = importlib.import_module("PyPDF2")

    if hasattr(PyPDF2, "PdfReader"):
        reader = PyPDF2.PdfReader(pdf_path)
        return len(reader.pages)

    if hasattr(PyPDF2, "PdfFileReader"):
        with open(pdf_path, "rb") as pdf_file:
            reader = PyPDF2.PdfFileReader(pdf_file)
            return reader.getNumPages()

    raise AttributeError(
        "La instalación de PyPDF2 no expone PdfReader ni PdfFileReader. Actualiza el paquete."
    )


def export_pdf(
    inkscape_binary: str,
    pdf_dir: str,
    svg_dir: str,
    pdf_name: str,
    only_page: int | None,
) -> None:
    pdf_path = os.path.join(pdf_dir, pdf_name)
    base_name = os.path.splitext(pdf_name)[0]
    
    try:
        num_pages = count_pdf_pages(pdf_path)
    except Exception as exc:  # pragma: no cover - CLI feedback
        print(f"Error leyendo {pdf_name}: {exc}")
        return

    print(f"Procesando {pdf_name} ({num_pages} páginas)...")
    if only_page:
        pages = [only_page]
    else:
        pages = range(1, num_pages + 1)

    os.makedirs(svg_dir, exist_ok=True)
    for page in pages:
        svg_out = os.path.join(svg_dir, f"{base_name}_page{page}.svg")
        if os.path.exists(svg_out):
            os.remove(svg_out)
        cmd = build_cmd(inkscape_binary, pdf_path, svg_out, page)
        print(f"Exportando página {page} a {svg_out} …")
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:  # pragma: no cover
            print(f"Error exportando página {page} de {pdf_name}:")
            if exc.stderr:
                print(exc.stderr)
            if exc.stdout:
                print(exc.stdout)
        except Exception as exc:  # pragma: no cover
            print(f"Error inesperado exportando página {page} de {pdf_name}: {exc}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convierte páginas de PDF en SVG usando Inkscape (Linux)."
    )
    parser.add_argument(
        "pdf_path",
        nargs="?",
        default=None,
        help="Ruta a un PDF específico a procesar.",
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        default=None,
        help="Directorio donde guardar los SVG (por defecto, el del PDF).",
    )
    parser.add_argument(
        "--pdf-dir",
        default=os.getcwd(),
        help="Directorio con PDFs cuando no se indica un archivo concreto.",
    )
    parser.add_argument(
        "--svg-dir",
        default=None,
        help="Directorio base para los SVG cuando se procesan varios PDFs.",
    )
    parser.add_argument(
        "--only-page",
        type=int,
        default=None,
        help="Exportar solo la página N (1-indexada).",
    )
    return parser.parse_args()


def main() -> None:
    inkscape_binary = resolve_inkscape_binary()
    if not inkscape_binary:
        print(
            "No se encontró el ejecutable de Inkscape. Asegúrate de tenerlo instalado "
            "y disponible en PATH, o define INKSCAPE_BINARY con la ruta completa."
        )
        sys.exit(1)
    print(f"Usando Inkscape en: {inkscape_binary}")

    args = parse_args()
    ensure_pypdf2()

    if args.pdf_path:
        pdf_dir = os.path.dirname(os.path.abspath(args.pdf_path)) or os.getcwd()
        pdf_files = [os.path.basename(args.pdf_path)]
    else:
        pdf_dir = os.path.abspath(args.pdf_dir)
        pdf_files = list(iter_pdf_files(pdf_dir))

    if not pdf_files:
        print("No se encontraron archivos PDF para procesar.")
        return

    if args.output_dir:
        svg_dir = os.path.abspath(args.output_dir)
    elif args.svg_dir:
        svg_dir = os.path.abspath(args.svg_dir)
    else:
        svg_dir = pdf_dir

    for pdf_name in pdf_files:
        export_pdf(inkscape_binary, pdf_dir, svg_dir, pdf_name, args.only_page)

    print("Listo.")


if __name__ == "__main__":
    main()
