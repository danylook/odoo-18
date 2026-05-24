#!/usr/bin/env python3
"""Export PDF pages to SVG using a Windows-like Inkscape CLI on Linux.

This variant mimics the minimal command used on the Windows workflow so the
resulting SVG keeps the same richness (paths, clipPaths, groups, etc.).  It
first tries the modern ``--export-page`` flag used by Inkscape 1.2+, and if the
binary rejects it it falls back to the legacy ``--pages`` syntax still valid on
older builds.  No extra export modifiers are added so Inkscape keeps its
defaults, matching the Windows output as closely as possible.
"""
from __future__ import annotations

import argparse
import importlib
import os
import shutil
import subprocess
import sys
from typing import Iterable, List


def resolve_inkscape_binary() -> str:
    env_candidate = os.environ.get("INKSCAPE_BINARY")
    if env_candidate:
        found = shutil.which(env_candidate) or (
            env_candidate if os.path.isfile(env_candidate) else None
        )
        if found:
            return found

    path_candidate = shutil.which("inkscape")
    if path_candidate:
        return path_candidate

    for candidate in ("/usr/bin/inkscape", "/snap/bin/inkscape"):
        if os.path.isfile(candidate):
            return candidate

    return ""


def iter_pdf_files(directory: str) -> Iterable[str]:
    for entry in sorted(os.listdir(directory)):
        if entry.lower().endswith(".pdf"):
            yield entry


def ensure_pypdf2() -> None:
    try:
        import PyPDF2  # noqa: F401
    except ImportError:
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


def build_cmd(
    inkscape_binary: str,
    pdf_path: str,
    svg_output: str,
    page_number: int,
    use_legacy: bool = False,
) -> List[str]:
    cmd = [
        inkscape_binary,
        pdf_path,
        "--export-type=svg",
        f"--export-filename={svg_output}",
    ]
    if use_legacy:
        cmd.append(f"--pages={page_number}")
    else:
        cmd.append(f"--export-page={page_number}")
    return cmd


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
    except Exception as exc:
        print(f"Error leyendo {pdf_name}: {exc}")
        return

    print(f"Procesando {pdf_name} ({num_pages} páginas)...")
    pages = [only_page] if only_page else range(1, num_pages + 1)

    os.makedirs(svg_dir, exist_ok=True)
    for page in pages:
        svg_out = os.path.join(svg_dir, f"{base_name}_page{page}.svg")
        if os.path.exists(svg_out):
            os.remove(svg_out)

        primary_cmd = build_cmd(inkscape_binary, pdf_path, svg_out, page)
        print(f"Exportando página {page} a {svg_out} …")
        try:
            subprocess.run(primary_cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as primary_error:
            combined = (primary_error.stderr or "") + (primary_error.stdout or "")
            if "Unknown option --export-page" in combined:
                legacy_cmd = build_cmd(
                    inkscape_binary,
                    pdf_path,
                    svg_out,
                    page,
                    use_legacy=True,
                )
                print("[AVISO] Inkscape no reconoce --export-page; probando --pages …")
                try:
                    subprocess.run(legacy_cmd, check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError as legacy_error:
                    print(f"Error exportando página {page} de {pdf_name}:")
                    if legacy_error.stderr:
                        print(legacy_error.stderr)
                    if legacy_error.stdout:
                        print(legacy_error.stdout)
                except Exception as fallback_exc:
                    print(
                        f"Error inesperado exportando página {page} de {pdf_name}: {fallback_exc}"
                    )
            else:
                print(f"Error exportando página {page} de {pdf_name}:")
                if primary_error.stderr:
                    print(primary_error.stderr)
                if primary_error.stdout:
                    print(primary_error.stdout)
        except Exception as generic_exc:
            print(f"Error inesperado exportando página {page} de {pdf_name}: {generic_exc}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convierte páginas de PDF en SVG usando Inkscape (Linux, modo completo)."
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
