from pdftoOCRpasoprevio import run_and_get_paneles_datos
import base64

import os
import sys
import subprocess

PAGE_TO_PROCESS = None  # Cambia según necesidad

def paso0_pdf_a_ocr(pdf_path):
    print(f"[Paso 0] Extrayendo datos OCR estructurados del PDF: {pdf_path}")
    paneles_datos = run_and_get_paneles_datos(pdf_path)
    print(f"[Paso 0] Paneles extraídos: {paneles_datos}")
    return paneles_datos

# Paso 1: PDF a SVG para la(s) página(s) seleccionada(s)
def paso1_pdf_to_svgs(pdf_path, output_dir, page_to_process=None):
    print("[Paso 1] Convirtiendo PDF a SVGs por página (pdf_parser)…")
    script_path = os.path.join(
        os.path.dirname(__file__), "..", "data_importer", "pdf_parser.py"
    )
    if page_to_process:
        cmd = [sys.executable, script_path, pdf_path, output_dir, "--only-page", str(page_to_process)]
        pages = [page_to_process]
    else:
        cmd = [sys.executable, script_path, pdf_path, output_dir]
        pages = list(range(1, get_num_pages(pdf_path) + 1))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    if result.returncode != 0:
        raise RuntimeError(
            f"[Paso 1] pdf_parser falló (código {result.returncode}).\n"
            f"{result.stderr or result.stdout}"
        )
    return pages


def paso15_generar_metadata(svg_input_path):
    print(f"[Paso 1.5] Generando metadata desde: {svg_input_path}")
    script_path = os.path.join(os.path.dirname(__file__), "generate_panel_metadata_svg.py")
    cmd = [sys.executable, script_path, svg_input_path]
    subprocess.run(cmd, check=True)

def paso2_content_colores(svg_path, output_path):
    if os.path.exists(output_path):
        os.remove(output_path)
    print(f"[Paso 2] IN: {svg_path}\n[Paso 2] OUT: {output_path}")
    script_path = os.path.join(
        os.path.dirname(__file__),
        "content_only_colores_elegidos_con_marco_con_oblicuos_directo_paso_2_linux.py",
    )
    cmd = [sys.executable, script_path, svg_path, output_path]
    subprocess.run(cmd, check=True)

def paso3_paths_absoluto(svg_path, output_path):
    if os.path.exists(output_path):
        os.remove(output_path)
    print(f"[Paso 3] IN: {svg_path}\n[Paso 3] OUT: {output_path}")
    script_path = os.path.join(os.path.dirname(__file__), "convertir_paths_transform_a_absoluto_nuevopaso 3.py")
    cmd = [sys.executable, script_path, svg_path, output_path]
    subprocess.run(cmd, check=True)

def paso4_colorear_piezas(svg_path, output_path, piezas=None, sheathing=None):
    import json
    if os.path.exists(output_path):
        os.remove(output_path)
    print(f"[Paso 4] IN: {svg_path}\n[Paso 4] OUT: {output_path}")
    script_path = os.path.join(os.path.dirname(__file__), "paths_a_rects_filtrado_puntos_paso4final.py")
    cmd = [sys.executable, script_path, svg_path, output_path]
    if piezas is not None:
        cmd += ["--piezas", json.dumps(piezas, ensure_ascii=False)]
    if sheathing is not None:
        cmd += ["--sheathing", json.dumps(sheathing, ensure_ascii=False)]
    subprocess.run(cmd, check=True)

def paso5_reescalar_rects(svg_path, output_path):
    if os.path.exists(output_path):
        os.remove(output_path)
    print(f"[Paso 5] IN: {svg_path}\n[Paso 5] OUT: {output_path}")
    script_path = os.path.join(os.path.dirname(__file__), "reescalar_rects_svg_paso5.py")
    cmd = [sys.executable, script_path, svg_path, output_path]
    subprocess.run(cmd, check=True)

def paso6_svg_a_glb(svg_path, output_path):
    base, ext = os.path.splitext(svg_path)
    svg_path_frontal = base + '_frontal' + ext
    print(f"[Paso 6] IN: {svg_path_frontal}\n[Paso 6] OUT: {output_path}")
    script_path = os.path.join(os.path.dirname(__file__), "generoGLPpaso6.py")
    cmd = [sys.executable, script_path, svg_path_frontal, output_path]
    subprocess.run(cmd, check=True)

def get_num_pages(pdf_path):
    try:
        import importlib

        PyPDF2 = importlib.import_module("PyPDF2")
        if hasattr(PyPDF2, "PdfReader"):
            reader = PyPDF2.PdfReader(pdf_path)
            return len(reader.pages)
        if hasattr(PyPDF2, "PdfFileReader"):
            with open(pdf_path, "rb") as pdf_file:
                reader = PyPDF2.PdfFileReader(pdf_file)
                return reader.getNumPages()
        raise AttributeError("PyPDF2 no expone PdfReader ni PdfFileReader")
    except Exception as e:
        print(f"[ERROR] No se pudo leer el PDF: {e}")
        return 0

def combine_svgs_vertically(svg_paths, output_path):
    """Combina múltiples SVGs apilándolos verticalmente en uno solo."""
    import xml.etree.ElementTree as ET

    if not svg_paths:
        raise ValueError("No hay SVGs para combinar")

    # Parsear el primer SVG para obtener la estructura base
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    tree = ET.parse(svg_paths[0])
    root = tree.getroot()

    # Obtener viewBox y height del primer SVG
    viewbox = root.get('viewBox')
    if viewbox:
        vb_parts = viewbox.split()
        if len(vb_parts) == 4:
            x, y, width, height = map(float, vb_parts)
        else:
            width = float(root.get('width', 816))
            height = float(root.get('height', 1056))
            x, y = 0, 0
    else:
        width = float(root.get('width', 816))
        height = float(root.get('height', 1056))
        x, y = 0, 0

    current_y = height

    # Para cada SVG adicional, extraer el contenido y apilarlo
    for svg_path in svg_paths[1:]:
        sub_tree = ET.parse(svg_path)
        sub_root = sub_tree.getroot()

        # Obtener height del sub SVG
        sub_viewbox = sub_root.get('viewBox')
        if sub_viewbox:
            sub_vb_parts = sub_viewbox.split()
            if len(sub_vb_parts) == 4:
                sub_height = float(sub_vb_parts[3])
            else:
                sub_height = float(sub_root.get('height', 1056))
        else:
            sub_height = float(sub_root.get('height', 1056))

        # Mover el contenido del sub SVG hacia abajo
        for elem in sub_root:
            if elem.tag.endswith('g') or elem.tag.endswith('path') or elem.tag.endswith('rect') or elem.tag.endswith('circle') or elem.tag.endswith('line') or elem.tag.endswith('polyline') or elem.tag.endswith('polygon'):
                transform = elem.get('transform', '')
                elem.set('transform', f'translate(0, {current_y}) {transform}')

        # Agregar los elementos al root principal
        for elem in list(sub_root):
            root.append(elem)

        current_y += sub_height

    # Actualizar el viewBox y height del SVG combinado
    new_height = current_y
    root.set('viewBox', f'{x} {y} {width} {new_height}')
    root.set('height', str(new_height))

    # Escribir el SVG combinado
    tree.write(output_path, encoding='utf-8', xml_declaration=True)
    print(f"[COMBINE] SVGs combinados en: {output_path}")


def _normalize_pages(page_list) -> list:
    """Convert a raw page_list from OCR data to a sorted list of ints."""
    result = []
    for p in (page_list or []):
        try:
            result.append(int(p))
        except (TypeError, ValueError):
            pass
    return sorted(set(result))


def _resolve_frame_pages(page_numbers: list) -> tuple:
    """Decide which SVG pages to use for a panel/frame.

    Returns (pages_to_use, frame_type) where frame_type is one of:
      '1-page'      — single page
      '2-page'      — two consecutive pages (frame spans two pages)
      'multi/non-consecutive' — more than 2 or non-consecutive; first page only
    """
    if len(page_numbers) == 1:
        return page_numbers, '1-page'
    if len(page_numbers) == 2 and page_numbers[1] == page_numbers[0] + 1:
        return page_numbers, '2-page'
    # Non-consecutive or >2 pages: use only the first page
    return [page_numbers[0]], 'multi/non-consecutive'


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Pipeline PDF a SVG y GLB (Linux)")
    parser.add_argument('pdf_input', nargs='?', default=None, help='Ruta al archivo PDF de entrada')
    parser.add_argument('svg_pages_dir', nargs='?', default=None, help='Directorio de salida para los SVGs')
    args = parser.parse_args()

    PDF_INPUT = args.pdf_input or "/home/eco/odoo18/extra-addons/others-18.0/WF_panel_importer/data_importer/elevaciones_de_paredes.pdf"
    SVG_PAGES_DIR = args.svg_pages_dir or "/home/eco/odoo18/extra-addons/others-18.0/WF_panel_importer/data_importer/svg_pages/"

    pdf_basename = os.path.basename(PDF_INPUT)
    pdf_dest_path = os.path.join(SVG_PAGES_DIR, pdf_basename)
    if not os.path.exists(pdf_dest_path):
        raise FileNotFoundError(
            f"El PDF de entrada no se encuentra en el directorio de salida: {pdf_dest_path}\n"
            "Asegúrate de que Odoo lo haya copiado correctamente antes de ejecutar el pipeline."
        )
    print(f"[DEBUG] Archivo de entrada PDF: {pdf_dest_path}")

    # ── Paso 0: OCR → datos de paneles ─────────────────────────────────────
    paneles_datos = paso0_pdf_a_ocr(pdf_dest_path)

    # ── Paso 1: Convertir TODAS las páginas del PDF a SVG (una sola vez) ───
    # pdf_parser exports every page upfront so the per-frame loop only needs
    # to read the already-generated files — no redundant Inkscape calls.
    print("[Paso 1] Exportando todas las páginas del PDF a SVG (pdf_parser)…")
    paso1_pdf_to_svgs(pdf_dest_path, SVG_PAGES_DIR)
    pdf_stem = os.path.splitext(pdf_basename)[0]

    # ── Procesar cada frame / panel ─────────────────────────────────────────
    for panel in paneles_datos:
        nombre_archivo = panel['nombre_archivo']

        # Normalizar páginas del panel
        page_numbers = _normalize_pages(panel.get('page_list'))
        if not page_numbers:
            print(f"[ADVERTENCIA] Panel '{nombre_archivo}' sin páginas válidas — omitido.")
            continue

        # Determinar si el frame ocupa 1 o 2 páginas
        pages_to_use, frame_type = _resolve_frame_pages(page_numbers)
        print(f"\n[Frame] '{nombre_archivo}' → tipo: {frame_type} | páginas: {pages_to_use}")

        # Referenciar los SVGs ya generados en el Paso 1
        svg_files = []
        for page_num in pages_to_use:
            svg_path = os.path.join(SVG_PAGES_DIR, f"{pdf_stem}_page{page_num}.svg")
            if os.path.exists(svg_path):
                svg_files.append(svg_path)
            else:
                print(f"  [ADVERTENCIA] SVG no encontrado para página {page_num}: {svg_path}")

        if not svg_files:
            print(f"  [ADVERTENCIA] No hay SVGs disponibles para '{nombre_archivo}' — omitido.")
            continue

        # Filtro opcional PAGE_TO_PROCESS
        if PAGE_TO_PROCESS:
            svg_files = [f for f in svg_files if f"_page{PAGE_TO_PROCESS}.svg" in f]
            if not svg_files:
                continue

        # Paso 1.5: Metadata desde la primera página del frame
        paso15_generar_metadata(svg_files[0])

        # Combinar las dos páginas si el frame las necesita
        if len(svg_files) == 2:
            combined_svg = os.path.join(SVG_PAGES_DIR, f"{nombre_archivo}_combined.svg")
            print(f"  [Frame] Combinando 2 páginas → {os.path.basename(combined_svg)}")
            combine_svgs_vertically(svg_files, combined_svg)
            svg_input = combined_svg
        else:
            svg_input = svg_files[0]

        piezas = panel.get('piezas')
        sheathing = panel.get('sheathing')
        print(f"  [DEBUG] PIEZAS: {piezas}")
        print(f"  [DEBUG] SHEATHING: {sheathing}")

        svg_colores = os.path.join(SVG_PAGES_DIR, f"{nombre_archivo}_paso2_colores.svg")
        print(f"  [Paso 2] → {os.path.basename(svg_colores)}")
        paso2_content_colores(svg_input, svg_colores)

        svg_absoluto = os.path.join(SVG_PAGES_DIR, f"{nombre_archivo}_paso3_absoluto.svg")
        print(f"  [Paso 3] → {os.path.basename(svg_absoluto)}")
        paso3_paths_absoluto(svg_colores, svg_absoluto)

        svg_coloreado = os.path.join(SVG_PAGES_DIR, f"{nombre_archivo}_paso4_coloreado.svg")
        print(f"  [Paso 4] → {os.path.basename(svg_coloreado)}")
        paso4_colorear_piezas(svg_absoluto, svg_coloreado, piezas=piezas, sheathing=sheathing)

        svg_reescalado = os.path.join(SVG_PAGES_DIR, f"{nombre_archivo}_paso5_reescalado.svg")
        print(f"  [Paso 5] → {os.path.basename(svg_reescalado)}")
        paso5_reescalar_rects(svg_coloreado, svg_reescalado)

        glb_output = os.path.join(SVG_PAGES_DIR, f"{nombre_archivo}.glb")
        print(f"  [Paso 6] → {os.path.basename(glb_output)}")
        paso6_svg_a_glb(svg_reescalado, glb_output)

    print("\nPipeline completo (Linux).")


if __name__ == "__main__":
    main()
