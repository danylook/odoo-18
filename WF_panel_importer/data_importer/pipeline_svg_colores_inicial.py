from pdftoOCRpasoprevio import run_and_get_paneles_datos

import os
import sys
import subprocess

PAGE_TO_PROCESS = None # Cambia según necesidad

def paso0_pdf_a_ocr(pdf_path):
    print(f"[Paso 0] Extrayendo datos OCR estructurados del PDF: {pdf_path}")
    paneles_datos = run_and_get_paneles_datos(pdf_path)
    print(f"[Paso 0] Paneles extraídos: {paneles_datos}")
    return paneles_datos

# Paso 1: PDF a SVG para la(s) página(s) seleccionada(s)
def paso1_pdf_to_svgs(pdf_path, output_dir, page_to_process=None):
    print("[Paso 1] Convirtiendo PDF a SVGs por página...")
    # Usar el script Linux del wizard (el de data_importer solo funciona en Windows)
    wizard_dir = os.path.join(os.path.dirname(__file__), '..', 'wizard')
    script_path = os.path.join(wizard_dir, "pdf_to_svg_by_page_separado_paso1_linux.py")
    if page_to_process:
        cmd = [sys.executable, script_path, pdf_path, output_dir, "--only-page", str(page_to_process)]
        pages = [page_to_process]
    else:
        cmd = [sys.executable, script_path, pdf_path, output_dir]
        pages = list(range(1, get_num_pages(pdf_path) + 1))
    subprocess.run(cmd, check=True)
    return pages


def paso2_content_colores(svg_path, output_path):
    if os.path.exists(output_path):
        os.remove(output_path)
    print(f"[Paso 2] IN: {svg_path}\n[Paso 2] OUT: {output_path}")
    # Usar el script Linux del wizard
    wizard_dir = os.path.join(os.path.dirname(__file__), '..', 'wizard')
    script_path = os.path.join(wizard_dir, "content_only_colores_elegidos_con_marco_con_oblicuos_directo_paso_2_linux.py")
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
    # generoGLPpaso6.py está en el wizard (no en data_importer)
    wizard_dir = os.path.join(os.path.dirname(__file__), '..', 'wizard')
    script_path = os.path.join(wizard_dir, "generoGLPpaso6.py")
    cmd = [sys.executable, script_path, svg_path_frontal, output_path]
    subprocess.run(cmd, check=True)

def get_num_pages(pdf_path):
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(pdf_path)
        return len(reader.pages)
    except Exception as e:
        print(f"[ERROR] No se pudo leer el PDF: {e}")
        return 0

def combine_svgs_vertically(svg_paths, output_path):
    """Combina múltiples SVGs apilándolos verticalmente en uno solo."""
    import xml.etree.ElementTree as ET

    if not svg_paths:
        raise ValueError("No hay SVGs para combinar")

    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    tree = ET.parse(svg_paths[0])
    root = tree.getroot()

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

    for svg_path in svg_paths[1:]:
        sub_tree = ET.parse(svg_path)
        sub_root = sub_tree.getroot()
        sub_viewbox = sub_root.get('viewBox')
        if sub_viewbox:
            sub_vb_parts = sub_viewbox.split()
            sub_height = float(sub_vb_parts[3]) if len(sub_vb_parts) == 4 else float(sub_root.get('height', 1056))
        else:
            sub_height = float(sub_root.get('height', 1056))

        for elem in sub_root:
            if elem.tag.endswith(('g', 'path', 'rect', 'circle', 'line', 'polyline', 'polygon')):
                transform = elem.get('transform', '')
                elem.set('transform', f'translate(0, {current_y}) {transform}')
        for elem in list(sub_root):
            root.append(elem)
        current_y += sub_height

    root.set('viewBox', f'{x} {y} {width} {current_y}')
    root.set('height', str(current_y))
    tree.write(output_path, encoding='utf-8', xml_declaration=True)
    print(f"[COMBINE] SVGs combinados en: {output_path}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Pipeline PDF a SVG y GLB")
    parser.add_argument('pdf_input', nargs='?', default=None, help='Ruta al PDF de entrada')
    parser.add_argument('svg_pages_dir', nargs='?', default=None, help='Directorio de salida para SVGs')
    args = parser.parse_args()

    _here = os.path.dirname(os.path.abspath(__file__))
    PDF_INPUT = args.pdf_input or os.path.join(_here, "elevaciones_de_paredes.pdf")
    SVG_PAGES_DIR = args.svg_pages_dir or os.path.join(_here, "svg_pages")

    os.makedirs(SVG_PAGES_DIR, exist_ok=True)
    # Borra todos los archivos del directorio de salida antes de empezar
    for f in os.listdir(SVG_PAGES_DIR):
        file_path = os.path.join(SVG_PAGES_DIR, f)
        if os.path.isfile(file_path):
            os.remove(file_path)

    print(f"[DEBUG] Archivo de entrada PDF: {PDF_INPUT}")
    paneles_datos = paso0_pdf_a_ocr(PDF_INPUT)

    # --- EJECUTA PASO 1 Y SIGUIENTES USANDO INFORMACIÓN DE PASO 0 ---
    for panel in paneles_datos:
        nombre_archivo = panel['nombre_archivo']
        page_list = panel.get('page_list') or []
        if not page_list:
            print(f"[ADVERTENCIA] Panel sin páginas: {nombre_archivo}")
            continue

        # Normalizar y ordenar las páginas
        page_numbers = []
        for p in page_list:
            try:
                page_numbers.append(int(p))
            except (TypeError, ValueError):
                continue
        page_numbers = sorted(set(page_numbers))
        if not page_numbers:
            print(f"[ADVERTENCIA] Páginas inválidas para panel: {nombre_archivo}")
            continue

        # Solo procesar la primera página si PAGE_TO_PROCESS está definido
        if PAGE_TO_PROCESS and page_numbers[0] != PAGE_TO_PROCESS:
            continue

        # Para paneles con varias páginas consecutivas, combinar SVGs
        # (las páginas "Continued" solo tienen tablas, no dibujo, pero se incluyen por completitud)
        is_consecutive = len(page_numbers) == 1 or all(
            page_numbers[i] == page_numbers[0] + i for i in range(len(page_numbers))
        )
        if not is_consecutive:
            page_numbers = [page_numbers[0]]

        piezas = panel.get('piezas')
        sheathing = panel.get('sheathing')

        # Exportar páginas a SVG
        svg_files = []
        for page_num in page_numbers:
            paso1_pdf_to_svgs(PDF_INPUT, SVG_PAGES_DIR, page_num)
            svg_file = os.path.join(
                SVG_PAGES_DIR,
                f"{os.path.splitext(os.path.basename(PDF_INPUT))[0]}_page{page_num}.svg",
            )
            if not os.path.exists(svg_file):
                print(f"[ADVERTENCIA] No existe: {svg_file}")
                continue
            svg_files.append(svg_file)

        if not svg_files:
            print(f"[ADVERTENCIA] No se pudieron exportar SVGs para panel: {nombre_archivo}")
            continue

        # Combinar SVGs si hay múltiples páginas consecutivas
        if len(svg_files) > 1:
            combined_svg = os.path.join(SVG_PAGES_DIR, f"{nombre_archivo}_combined.svg")
            combine_svgs_vertically(svg_files, combined_svg)
            svg_file = combined_svg
        else:
            svg_file = svg_files[0]

        # Paso 2: Colores
        svg_colores = os.path.join(SVG_PAGES_DIR, f"{nombre_archivo}_paso2_colores.svg")
        print(f"[proc] Paso 2: {svg_colores}")
        paso2_content_colores(svg_file, svg_colores)
        # Paso 3: Absoluto
        svg_absoluto = os.path.join(SVG_PAGES_DIR, f"{nombre_archivo}_paso3_absoluto.svg")
        print(f"[proc] Paso 3: {svg_absoluto}")
        paso3_paths_absoluto(svg_colores, svg_absoluto)
        # Paso 4: Coloreado final
        print(f"[DEBUG] PIEZAS para {nombre_archivo}: {piezas}")
        print(f"[DEBUG] SHEATHING para {nombre_archivo}: {sheathing}")
        svg_coloreado = os.path.join(SVG_PAGES_DIR, f"{nombre_archivo}_paso4_coloreado.svg")
        print(f"[proc] Paso 4: {svg_coloreado}")
        paso4_colorear_piezas(svg_absoluto, svg_coloreado, piezas=piezas, sheathing=sheathing)
        # Paso 5: Reescalar y alinear rects
        svg_reescalado = os.path.join(SVG_PAGES_DIR, f"{nombre_archivo}_paso5_reescalado.svg")
        print(f"[proc] Paso 5: {svg_reescalado}")
        paso5_reescalar_rects(svg_coloreado, svg_reescalado)
        # Paso 6: Generar GLB 3D
        glb_output = os.path.join(SVG_PAGES_DIR, f"{nombre_archivo}.glb")
        print(f"[proc] Paso 6: {glb_output}")
        paso6_svg_a_glb(svg_reescalado, glb_output)
    print("Pipeline completo.")

if __name__ == "__main__":
    main()
