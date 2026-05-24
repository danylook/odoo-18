import xml.etree.ElementTree as ET
import sys
import re

# Paleta de colores para asignar a los grupos de paths
color_palette = [
    "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
    "#911eb4", "#46f0f0", "#f032e6", "#bcf60c", "#fabebe",
    "#008080", "#e6beff", "#9a6324", "#fffac8", "#800000",
    "#aaffc3", "#808000", "#ffd8b1", "#000075", "#808080",
    # Colores extra
    "#ffb300", "#803e75", "#ff6800", "#a6bdd7", "#c10020",
    "#cea262", "#817066", "#007d34", "#f6768e", "#00538a",
    "#ff7a5c", "#53377a", "#ff8e00", "#b32851", "#f4c800",
    "#7f180d", "#93aa00", "#593315", "#f13a13", "#232c16"
]

# ===================== VARIABLES =====================
# Lista de piezas: (Etiqueta, Descripción, Cantidad, Medida)
PIEZAS = [
    ("A", "Bottom Plate 2x6 SPF No.2", 1, "13-08-08 0-00"),
    ("B", "Top Plate 2x6 SPF No.2", 1, "13-08-08 0-00"),
    ("C", "VTP 2x6 SPF No.2", 1, "14-02-00 0-00"),
    ("D", "Stud 2x6 SPF No.2", 12, "8-08-10 0-00"),
    # Agrega más piezas aquí según sea necesario
]

# Proporciones reales del plano (en pulgadas por unidad SVG)
PROPORCION_HORIZONTAL = 4.094  # igual que colorear_svg_por_piezaspaso 4.py

# === CONFIGURACIÓN DE ARCHIVOS ===
INPUT_SVG = "C:\\odoo17new\\extra-addons\\others-17.0\\easyOCR\\svg_pages\\elevaciones de paredes_paso4_coloreado_page1.svg"
OUTPUT_SVG = "C:\\odoo17new\\extra-addons\\others-17.0\\easyOCR\\svg_pages\\elevaciones de paredes_piezasreales_page1.svg"

def get_input_output_svg():
    if len(sys.argv) > 2:
        input_svg = sys.argv[1]
        output_svg = sys.argv[2]
    else:
        input_svg = INPUT_SVG
        output_svg = OUTPUT_SVG
    return input_svg, output_svg

def parse_medida_a_pulgadas(medida):
    # Ejemplo: "13-08-08 0-00" => 13 pies, 8 pulgadas, 8/16 fracción
    partes = medida.split()
    pies, pulgadas, fraccion = 0, 0, 0
    if len(partes) > 0:
        pies = int(partes[0].split('-')[0])
        pulgadas = int(partes[0].split('-')[1])
        if len(partes[0].split('-')) > 2:
            fraccion = int(partes[0].split('-')[2])
    if len(partes) > 1:
        # Si hay una segunda parte, puede ser fracción
        frac = partes[1].split('-')
        if len(frac) > 1:
            fraccion = int(frac[1])
    return pies * 12 + pulgadas + fraccion / 16.0

def estimate_path_length(d_attr):
    # Solo soporta líneas rectas tipo M x y L x y ...
    coords = re.findall(r'[-+]?[0-9]*\.?[0-9]+', d_attr)
    coords = list(map(float, coords))
    if len(coords) < 4:
        return 0
    x0, y0 = coords[0], coords[1]
    total = 0
    for i in range(2, len(coords), 2):
        x1, y1 = coords[i], coords[i+1]
        total += ((x1 - x0)**2 + (y1 - y0)**2) ** 0.5
        x0, y0 = x1, y1
    return total

def estimate_rect_length(rect):
    # Usa el ancho como largo principal
    w = float(rect.get('width', '0'))
    h = float(rect.get('height', '0'))
    return max(w, h)

# ===================== FUNCIONES =====================
def get_path_center_y(path):
    d = path.get('d', '')
    coords = re.findall(r'[-+]?[0-9]*\.?[0-9]+', d)
    coords = list(map(float, coords))
    ys = coords[1::2]
    if not ys:
        return 0
    return sum(ys) / len(ys)

def get_path_center_xy(path):
    d = path.get('d', '')
    coords = re.findall(r'[-+]?[0-9]*\.?[0-9]+', d)
    coords = list(map(float, coords))
    xs = coords[0::2]
    ys = coords[1::2]
    if not xs or not ys:
        return 0, 0
    return sum(xs) / len(xs), sum(ys) / len(ys)

def get_rect_center_xy(rect):
    x = float(rect.get('x', '0'))
    y = float(rect.get('y', '0'))
    w = float(rect.get('width', '0'))
    h = float(rect.get('height', '0'))
    return x + w/2, y + h/2

def renombrar_piezas_svg(svg_in, svg_out, piezas=PIEZAS):
    tree = ET.parse(svg_in)
    root = tree.getroot()
    ns = {'svg': 'http://www.w3.org/2000/svg'}
    # Procesar tanto paths como rects
    paths = list(root.findall('.//svg:path', ns))
    rects = list(root.findall('.//svg:rect', ns))
    # Ordenar por y (de arriba a abajo)
    paths_sorted = sorted(paths, key=get_path_center_y)
    rects_sorted = sorted(rects, key=lambda r: get_rect_center_xy(r)[1])
    # Calcular longitudes reales de las piezas
    piezas_con_long = []
    for p in piezas:
        etiqueta, descripcion, cantidad, medida = p
        long_real = parse_medida_a_pulgadas(medida)
        piezas_con_long.append((etiqueta, descripcion, cantidad, medida, long_real))
    # Calcular longitudes de paths y rects
    paths_con_long = []
    for path in paths_sorted:
        d = path.get('d', '')
        long_svg = estimate_path_length(d)
        long_pulgadas = long_svg / PROPORCION_HORIZONTAL if PROPORCION_HORIZONTAL else 0
        paths_con_long.append((path, long_pulgadas, 'path'))
    rects_con_long = []
    for rect in rects_sorted:
        long_svg = estimate_rect_length(rect)
        long_pulgadas = long_svg / PROPORCION_HORIZONTAL if PROPORCION_HORIZONTAL else 0
        rects_con_long.append((rect, long_pulgadas, 'rect'))
    # Unir ambos
    elementos_con_long = paths_con_long + rects_con_long
    usados = set()
    color_idx = 0
    piezas_detectadas = []
    etiqueta_contadores = {}
    text_elements = []
    for etiqueta, descripcion, cantidad, medida, long_real in piezas_con_long:
        candidatos = [(idx, el, abs(long_pulgadas - long_real), tipo)
                      for idx, (el, long_pulgadas, tipo) in enumerate(elementos_con_long) if idx not in usados]
        candidatos.sort(key=lambda t: t[2])
        if etiqueta not in etiqueta_contadores:
            etiqueta_contadores[etiqueta] = 1
        for i in range(cantidad):
            if i >= len(candidatos):
                break
            idx, el, _, tipo = candidatos[i]
            id_clean = descripcion.replace(' ', '_').replace('.', '').replace(',', '').replace('/', '_')
            secuencial = etiqueta_contadores[etiqueta]
            new_id = f"{id_clean}{secuencial}"
            el.set('id', new_id)
            el.set('data-pieza', etiqueta)
            el.set('data-descripcion', descripcion)
            el.set('data-cantidad', str(cantidad))
            el.set('data-medida', medida)
            color = color_palette[color_idx % len(color_palette)]
            if tipo == 'path':
                style = el.get('style', '')
                style = re.sub(r'fill\s*:[^;]+;?', '', style)
                style = f'fill:{color};' + style
                el.set('style', style)
                el.set('fill', color)
                x, y = get_path_center_xy(el)
            else:
                style = el.get('style', '')
                style = re.sub(r'fill\s*:[^;]+;?', '', style)
                style = f'fill:{color};' + style
                el.set('style', style)
                el.set('fill', color)
                x, y = get_rect_center_xy(el)
            usados.add(idx)
            piezas_detectadas.append((new_id, descripcion, color))
            # Crear <text> SVG para la etiqueta
            text_el = ET.Element('text', {
                'x': str(x),
                'y': str(y),
                'fill': '#000',
                'font-size': '14',
                'text-anchor': 'middle',
                'alignment-baseline': 'middle',
                'font-family': 'Arial',
                'id': f'label_{new_id}'
            })
            text_el.text = new_id
            text_elements.append(text_el)
            color_idx += 1
            etiqueta_contadores[etiqueta] += 1
    # Agregar los <text> al SVG
    for text_el in text_elements:
        root.append(text_el)
    tree.write(svg_out, encoding='utf-8', xml_declaration=True)
    #print(f"SVG renombrado guardado en: {svg_out}")
    #print("Piezas detectadas y color asignado:")
    for idp, desc, color in piezas_detectadas:
        #print(f"  {idp}: {desc} - color {color}")

# ===================== MAIN =====================
if __name__ == "__main__":
    input_svg, output_svg = get_input_output_svg()
    renombrar_piezas_svg(input_svg, output_svg)
