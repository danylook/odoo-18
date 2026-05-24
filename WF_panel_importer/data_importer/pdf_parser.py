#!/usr/bin/env python3
"""pdf_parser.py — Split a PDF into individual pages and convert each to SVG.

This module is the entry point for Step 1 of the WF Panel importer pipeline.
It locates the Inkscape binary, counts PDF pages via PyPDF2, and calls Inkscape
once per page to produce one SVG file per page.  The list of generated SVG
absolute paths is returned so subsequent pipeline steps can consume them.

Usage (CLI):
    python pdf_parser.py <pdf_path> <output_dir> [--only-page N]

Usage (as module):
    from pdf_parser import split_pdf_to_svg
    svg_paths = split_pdf_to_svg("/path/to/file.pdf", "/path/to/output_dir/")
"""
from __future__ import annotations

import argparse
import importlib
import os
import shutil
import subprocess
import sys
import tempfile
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# Known / tested Inkscape version
# ---------------------------------------------------------------------------

# Version confirmed to work correctly with this module.
# Inkscape >= 1.3 uses --pages=N; 1.4.x is the current tested series.
INKSCAPE_KNOWN_VERSION: Tuple[int, int] = (1, 4)

# Module-level cache so version detection runs only once per process.
_inkscape_version_cache: dict = {}


# ---------------------------------------------------------------------------
# Inkscape binary resolution
# ---------------------------------------------------------------------------

def resolve_inkscape_binary() -> str:
    """Locate the Inkscape executable.

    Priority:
    1. ``INKSCAPE_BINARY`` environment variable (explicit override).
    2. /snap/bin/inkscape — Inkscape 1.4.3, preferred for correct PDF rendering.
       NOTE: the snap sandbox requires that both input and output paths are
       inside the user home directory.  ``split_pdf_to_svg`` ensures this by
       placing the ``pdfseparate`` temp files next to the output SVGs (not in
       /tmp).
    3. PATH lookup via shutil.which.
    4. /usr/bin/inkscape direct fallback (1.2.2 — works but lower quality).
    """
    env_candidate = os.environ.get("INKSCAPE_BINARY")
    if env_candidate:
        found = shutil.which(env_candidate) or (
            env_candidate if os.path.isfile(env_candidate) else None
        )
        if found:
            return found

    # Prefer snap 1.4.3 — better PDF rendering
    if os.path.isfile("/snap/bin/inkscape"):
        return "/snap/bin/inkscape"

    path_candidate = shutil.which("inkscape")
    if path_candidate:
        return path_candidate

    if os.path.isfile("/usr/bin/inkscape"):
        return "/usr/bin/inkscape"

    return ""


# ---------------------------------------------------------------------------
# Inkscape version detection
# ---------------------------------------------------------------------------

def _inkscape_major_minor(inkscape_binary: str) -> Tuple[int, int]:
    """Return (major, minor) version tuple for the given Inkscape binary.

    The result is cached per binary path so the subprocess is only spawned
    once per process.  Falls back to ``INKSCAPE_KNOWN_VERSION`` when detection
    fails, since the confirmed installed version is 1.4.3.
    """
    global _inkscape_version_cache
    if inkscape_binary in _inkscape_version_cache:
        return _inkscape_version_cache[inkscape_binary]

    import re
    detected = INKSCAPE_KNOWN_VERSION  # default: confirmed installed version
    try:
        out = subprocess.run(
            _dbus_prefix() + [inkscape_binary, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        m = re.search(r"Inkscape\s+(\d+)\.(\d+)", out.stdout + out.stderr)
        if m:
            detected = (int(m.group(1)), int(m.group(2)))
    except Exception:
        pass

    _inkscape_version_cache[inkscape_binary] = detected
    print(f"[pdf_parser] Inkscape versión detectada: {detected[0]}.{detected[1]}.x")
    return detected


# ---------------------------------------------------------------------------
# PDF splitting via pdfseparate (poppler-utils)
# ---------------------------------------------------------------------------

def _find_pdfseparate() -> str:
    """Return the path to ``pdfseparate`` (poppler-utils) or empty string."""
    return shutil.which("pdfseparate") or ""


def _split_pdf_pages(pdf_path: str, tmp_dir: str, pages: List[int]) -> dict:
    """Split *pdf_path* into individual single-page PDFs using ``pdfseparate``.

    The single-page PDFs are written to *tmp_dir*.  When using snap Inkscape
    this directory **must** be inside the user home so the sandbox can read
    the files.  ``split_pdf_to_svg`` passes a subdirectory of *output_dir*
    for this reason.

    Returns a dict mapping page_number → single-page-PDF path for every page
    that was successfully extracted.  Returns an empty dict if ``pdfseparate``
    is not available so the caller can fall back.
    """
    pdfsep = _find_pdfseparate()
    if not pdfsep:
        return {}

    pattern = os.path.join(tmp_dir, "page_%d.pdf")
    first = min(pages)
    last = max(pages)
    try:
        subprocess.run(
            [pdfsep, "-f", str(first), "-l", str(last), pdf_path, pattern],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"[pdf_parser] pdfseparate falló: {exc.stderr}")
        return {}

    result = {}
    for page in pages:
        candidate = os.path.join(tmp_dir, f"page_{page}.pdf")
        if os.path.isfile(candidate):
            result[page] = candidate
    return result


# ---------------------------------------------------------------------------
# Inkscape command builder (single-page PDF → SVG, no --pages selector)
# ---------------------------------------------------------------------------

def _dbus_prefix() -> List[str]:
    """Return ['dbus-run-session', '--'] when available, else empty list.

    Snap Inkscape requires a D-Bus session bus.  When called from a service
    (e.g. Odoo) there is no graphical session and no bus socket, so Inkscape
    throws ``Gio::DBus::Error`` and aborts.  Wrapping with ``dbus-run-session``
    creates a temporary isolated bus just for that invocation.
    """
    dbus_cmd = shutil.which("dbus-run-session")
    if dbus_cmd:
        return [dbus_cmd, "--"]
    return []


def _build_inkscape_cmd_single(
    inkscape_binary: str,
    single_page_pdf: str,
    svg_output: str,
) -> List[str]:
    """Build Inkscape command to convert a *single-page* PDF to SVG.

    Because the input already contains only one page there is no need for
    ``--pages`` / ``--pdf-page``, which eliminates the Inkscape 1.4.x bug
    where every page is exported as a copy of page 1.

    ``--batch-process`` is required for headless/server operation so that
    Inkscape does not try to open a graphical display.
    """
    return _dbus_prefix() + [
        inkscape_binary,
        "--batch-process",
        "--export-type=svg",
        f"--export-filename={svg_output}",
        "--export-area-page",
        "--export-dpi=96",
        "--export-text-to-path",
        single_page_pdf,
    ]


def _build_inkscape_cmd_fallback(
    inkscape_binary: str,
    pdf_path: str,
    svg_output: str,
    page_number: int,
    version: Optional[Tuple[int, int]] = None,
) -> List[str]:
    """Fallback command when ``pdfseparate`` is not available.

    Inkscape 1.3+  uses ``--pages=N``.
    Inkscape 1.2.x uses ``--pdf-page=N``.

    NOTE: Inkscape 1.4.x has a known bug where ``--batch-process`` +
    ``--pages=N`` in a loop always exports page 1.  The primary path
    (``pdfseparate`` + ``_build_inkscape_cmd_single``) avoids this entirely.
    """
    if version is None:
        version = _inkscape_major_minor(inkscape_binary)
    if version >= (1, 3):
        return _dbus_prefix() + [
            inkscape_binary,
            f"--pages={page_number}",
            "--export-type=svg",
            f"--export-filename={svg_output}",
            "--export-area-page",
            "--export-dpi=96",
            "--export-text-to-path",
            pdf_path,
        ]
    else:
        return _dbus_prefix() + [
            inkscape_binary,
            "--export-type=svg",
            f"--export-filename={svg_output}",
            "--export-area-page",
            "--export-dpi=96",
            "--export-text-to-path",
            pdf_path,
            f"--pdf-page={page_number}",
        ]


# ---------------------------------------------------------------------------
# PDF page counting
# ---------------------------------------------------------------------------

def count_pdf_pages(pdf_path: str) -> int:
    """Return the number of pages in *pdf_path* using PyPDF2."""
    PyPDF2 = importlib.import_module("PyPDF2")

    if hasattr(PyPDF2, "PdfReader"):
        reader = PyPDF2.PdfReader(pdf_path)
        return len(reader.pages)

    if hasattr(PyPDF2, "PdfFileReader"):
        with open(pdf_path, "rb") as fh:
            reader = PyPDF2.PdfFileReader(fh)
            return reader.getNumPages()

    raise AttributeError(
        "La instalación de PyPDF2 no expone PdfReader ni PdfFileReader. "
        "Actualiza el paquete con: pip install --upgrade PyPDF2"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def split_pdf_to_svg(
    pdf_path: str,
    output_dir: str,
    only_page: Optional[int] = None,
    inkscape_binary: Optional[str] = None,
) -> List[str]:
    """Split *pdf_path* into per-page SVG files inside *output_dir*.

    Parameters
    ----------
    pdf_path : str
        Absolute (or resolvable) path to the source PDF.
    output_dir : str
        Directory where the SVG files will be written.  Created if missing.
    only_page : int, optional
        When given, only that page number (1-indexed) is exported.
    inkscape_binary : str, optional
        Explicit path to the Inkscape binary.  Auto-detected when omitted.

    Returns
    -------
    list[str]
        Sorted list of absolute paths to the generated SVG files.

    Raises
    ------
    FileNotFoundError
        If *pdf_path* does not exist or Inkscape cannot be found.
    RuntimeError
        If no pages could be exported successfully.
    """
    pdf_path = os.path.abspath(pdf_path)
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")

    inkscape = inkscape_binary or resolve_inkscape_binary()
    if not inkscape:
        raise FileNotFoundError(
            "No se encontró Inkscape.  Instálalo con:\n"
            "  sudo snap install inkscape\n"
            "o bien define la variable de entorno INKSCAPE_BINARY."
        )

    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    num_pages = count_pdf_pages(pdf_path)
    pages = [only_page] if only_page else list(range(1, num_pages + 1))

    inkscape_version = _inkscape_major_minor(inkscape)

    print(f"[pdf_parser] {base_name}.pdf — {num_pages} página(s) detectadas.")
    print(f"[pdf_parser] Usando Inkscape: {inkscape}")

    generated: List[str] = []

    # ── Primary strategy: pdfseparate → single-page PDFs → Inkscape 1.4.3 ──
    # Snap Inkscape 1.4.3 is sandboxed: it can only read/write paths directly
    # under $HOME (not deep subdirectories like odoo18/extra-addons/...).
    # Strategy: use ~/snap_inkscape_work/ as the working dir for both the split
    # PDFs and the SVG outputs, then move the SVGs to the final output_dir.
    home_dir = os.path.expanduser("~")
    snap_work = os.path.join(home_dir, "snap_inkscape_work")
    os.makedirs(snap_work, exist_ok=True)
    try:
        try:
            page_pdfs = _split_pdf_pages(pdf_path, snap_work, pages)
        except Exception as exc:
            print(f"[pdf_parser] pdfseparate error: {exc}")
            page_pdfs = {}

        if page_pdfs:
            print(f"[pdf_parser] Usando pdfseparate + Inkscape {inkscape_version[0]}.{inkscape_version[1]} para {len(page_pdfs)} página(s).")
            for page in pages:
                single_pdf = page_pdfs.get(page)
                if not single_pdf:
                    print(f"[pdf_parser] ADVERTENCIA: pdfseparate no generó página {page}.")
                    continue

                svg_work = os.path.join(snap_work, f"{base_name}_page{page}.svg")
                svg_out  = os.path.join(output_dir, f"{base_name}_page{page}.svg")
                for f in (svg_work, svg_out):
                    if os.path.exists(f):
                        os.remove(f)

                cmd = _build_inkscape_cmd_single(inkscape, single_pdf, svg_work)
                print(f"[pdf_parser] Exportando página {page} → {os.path.basename(svg_out)} …")
                try:
                    subprocess.run(cmd, check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError as exc:
                    print(f"[pdf_parser] ERROR página {page}: {exc.stderr}")
                    continue

                if os.path.isfile(svg_work):
                    import shutil as _shutil2
                    _shutil2.move(svg_work, svg_out)
                    generated.append(svg_out)
                    print(f"[pdf_parser] ✓ {os.path.basename(svg_out)}")
                else:
                    print(f"[pdf_parser] ADVERTENCIA: Inkscape no generó {svg_work}")

        else:
            # ── Fallback: --pages=N directly (no pdfseparate available) ────
            print(
                "[pdf_parser] pdfseparate no disponible — usando --pages=N directamente.\n"
                "  NOTA: instala poppler-utils para resultados más fiables:\n"
                "  sudo apt install poppler-utils"
            )
            for page in pages:
                svg_out = os.path.join(output_dir, f"{base_name}_page{page}.svg")
                if os.path.exists(svg_out):
                    os.remove(svg_out)

                cmd = _build_inkscape_cmd_fallback(
                    inkscape, pdf_path, svg_out, page, version=inkscape_version
                )
                print(f"[pdf_parser] Exportando página {page} → {os.path.basename(svg_out)} …")
                try:
                    subprocess.run(cmd, check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError as exc:
                    print(f"[pdf_parser] ERROR página {page}: {exc.stderr}")
                    continue

                if os.path.isfile(svg_out):
                    generated.append(svg_out)
                    print(f"[pdf_parser] ✓ {os.path.basename(svg_out)}")
                else:
                    print(f"[pdf_parser] ADVERTENCIA: Inkscape no generó {svg_out}")
    finally:
        # Remove temp working directory (split PDFs + any leftover SVGs)
        import shutil as _shutil
        _shutil.rmtree(snap_work, ignore_errors=True)

    if not generated:
        raise RuntimeError(
            f"No se pudo generar ningún SVG desde '{pdf_path}'. "
            "Verifica que Inkscape y poppler-utils estén instalados y que el PDF sea válido."
        )

    return sorted(generated)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Convierte cada página de un PDF a un SVG individual."
    )
    p.add_argument("pdf_path", help="Ruta al archivo PDF de entrada.")
    p.add_argument("output_dir", help="Directorio de salida para los SVGs.")
    p.add_argument(
        "--only-page",
        type=int,
        default=None,
        metavar="N",
        help="Exportar solo la página N (1-indexed).",
    )
    p.add_argument(
        "--inkscape",
        default=None,
        metavar="PATH",
        help="Ruta explícita al binario de Inkscape.",
    )
    return p


if __name__ == "__main__":
    args = _build_arg_parser().parse_args()
    try:
        svg_files = split_pdf_to_svg(
            pdf_path=args.pdf_path,
            output_dir=args.output_dir,
            only_page=args.only_page,
            inkscape_binary=args.inkscape,
        )
        print(f"\n[pdf_parser] {len(svg_files)} SVG(s) generados:")
        for f in svg_files:
            print(f"  {f}")
    except (FileNotFoundError, RuntimeError) as err:
        print(f"[pdf_parser] FATAL: {err}", file=sys.stderr)
        sys.exit(1)
