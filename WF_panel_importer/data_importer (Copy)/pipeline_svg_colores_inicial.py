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
    script_path = os.path.join(os.path.dirname(__file__), "pdf_to_svg_by_page_separado-paso1.py")
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
    script_path = os.path.join(os.path.dirname(__file__), "content_only_colores_elegidos_con_marco_con_oblicuos_directo_paso_2.py")
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
        from PyPDF2 import PdfReader
        reader = PdfReader(pdf_path)
        return len(reader.pages)
    except Exception as e:
        print(f"[ERROR] No se pudo leer el PDF: {e}")
        return 0

def main():
    PDF_INPUT = "C:/odoo17new/extra-addons/others-17.0/easyOCR/elevaciones_de_paredes.pdf"
    SVG_PAGES_DIR = "C:/odoo17new/extra-addons/others-17.0/easyOCR/svg_pages/"
    os.makedirs(SVG_PAGES_DIR, exist_ok=True)
    # Borra todos los archivos del directorio de salida antes de empezar
    for f in os.listdir(SVG_PAGES_DIR):
        file_path = os.path.join(SVG_PAGES_DIR, f)
        if os.path.isfile(file_path):
            os.remove(file_path)

        # --- EJECUTA PASO 0 ---
    print(f"[DEBUG] Archivo de entrada PDF: {PDF_INPUT}")
    paneles_datos = paso0_pdf_a_ocr(PDF_INPUT)
    # Puedes usar paneles_datos aquí para lógica adicional
    
    



    # --- EJECUTA PASO 1 Y SIGUIENTES USANDO INFORMACIÓN DE PASO 0 ---
    for panel in paneles_datos:
        nombre_archivo = panel['nombre_archivo']
        page_list = panel['page_list']
        if not page_list or not isinstance(page_list, (list, tuple)):
            print(f"[ADVERTENCIA] Panel sin páginas: {nombre_archivo}")
            continue
        page_num = page_list[0]
        # Solo procesar la página solicitada si PAGE_TO_PROCESS está definido
        if PAGE_TO_PROCESS and page_num != PAGE_TO_PROCESS:
            continue
        piezas = panel.get('piezas')
        sheathing = panel.get('sheathing')
        # Paso 1: PDF a SVG solo para la página relevante
        pages = paso1_pdf_to_svgs(PDF_INPUT, SVG_PAGES_DIR, page_num)
        svg_file = os.path.join(SVG_PAGES_DIR, f"{os.path.splitext(os.path.basename(PDF_INPUT))[0]}_page{page_num}.svg")
        #print(f"[proc] Paso 1: {svg_file}")
        if not os.path.exists(svg_file):
            print(f"[ADVERTENCIA] No existe: {svg_file}")
            continue
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
