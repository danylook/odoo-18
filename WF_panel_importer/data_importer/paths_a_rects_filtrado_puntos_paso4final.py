# --- IMPORTS ---

import sys
import argparse
from xml.dom import minidom
import re
import io
import unicodedata
import os  # Importar os para verificar la existencia del archivo
import statistics
from collections import Counter
import json

# === VARIABLES GLOBALES Y CONFIGURACIÓN ===
PROPORCION_HORIZONTAL = 0.2969#1 #1.0494812499999852 #2.0983870967741935  # px/pulgada (largo ajustado)
PROPORCION_VERTICAL = 0.2969#1 #1.3993980842911877 #2.0983870967741935  # px/pulgada (ancho ajustado)
MARGEN_LARGO = 0.25  # 1/4 de pulgada
MARGEN_ANCHO = 0.25  # 1/4 de pulgada


INPUT_SVG = "C:\\odoo17new\\extra-addons\\others-17.0\\easyOCR\\svg_pages\\L1_E18_paso3_absoluto.svg"

#INPUT_SVG = "C:\odoo17\extra-addons\others-17.0\easyOCR\svg_pages\elevaciones de paredes_paso3_absoluto_page8.svg"
OUTPUT_SVG = "C:\\odoo17new\\extra-addons\\others-17.0\\easyOCR\\svg_pages\\elevaciones_de_paredes_rects_filtrado_puntos8.svg"

color_palette = [
    "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
    "#911eb4", "#46f0f0", "#f032e6", "#bcf60c", "#fabebe",
    "#008080", "#e6beff", "#9a6324", "#fffac8", "#800000",
    "#aaffc3", "#808000", "#ffd8b1", "#000075", "#808080",
    "#ffb300", "#803e75", "#ff6800", "#a6bdd7", "#c10020",
    "#cea262", "#817066", "#007d34", "#f6768e", "#00538a",
    "#ff7a5c", "#53377a", "#ff8e00", "#b32851", "#f4c800",
    "#7f180d", "#93aa00", "#593315", "#f13a13", "#232c16"
]


# PIEZAS y SHEATHING: se pueden cargar dinámicamente, pero aquí valores por defecto
PIEZAS = [
    ('A', 'Bottom Plate 2x4 SPF No.2', 1, '01-11-04', '00-00-00'),
    ('B', 'Top Plate 2x4 SPF No.2', 1, '01-11-04', '00-00-00'),
    ('C', 'Stud 1 1/2" x 3 1/2" 1.3E', 3, '07-08-10', '00-00-00'),
    ('D', 'Flat Stud 1 1/2" x 3 1/2" 1.3E', 1, '07-08-10', '00-00-00'),
    ('E', 'Critical Stud 1 1/2" x 3 1/2" 1.3E', 1, '07-08-10', '00-00-00'),
]
SHEATING = [
    # Ejemplo: ('F', "Sheathing 1X0 Cladmate 9'", 1, '09-00-00', '03-01-08'),
]

# Diccionario de medidas nominales a reales (en pulgadas)
MEDIDAS_NOMINALES = {
    "2x4":  {"ancho": 1.5,  "profundidad": 3.5},
    "2x6":  {"ancho": 1.5,  "profundidad": 5.5},
    "2x8":  {"ancho": 1.5,  "profundidad": 7.25},
    "2x10": {"ancho": 1.5,  "profundidad": 9.25},
    "2x12": {"ancho": 1.5,  "profundidad": 11.25},
}

# Ejemplo de uso:
# ancho_mm = MEDIDAS_NOMINALES["2x6"]["ancho"] * PULGADA_A_MM
# profundidad_mm = MEDIDAS_NOMINALES["2x6"]["profundidad"] * PULGADA_A_MM

# --- PROCESO DE PARÁMETROS Y ARGUMENTOS ---
def procesar_parametros():
    parser = argparse.ArgumentParser(description="Procesa SVG y etiqueta piezas/sheathing por argumentos JSON opcionales.")
    parser.add_argument('input_svg', nargs='?', default=None, help='Archivo SVG de entrada')
    parser.add_argument('output_svg', nargs='?', default=None, help='Archivo SVG de salida')
    parser.add_argument('--piezas', type=str, default=None, help='Lista PIEZAS en formato JSON')
    parser.add_argument('--sheathing', type=str, default=None, help='Lista SHEATHING en formato JSON')
    args, _ = parser.parse_known_args()
    piezas = None
    sheathing = None
    if args.piezas:
        try:
            piezas = json.loads(args.piezas)
            #print(f"[DEBUG] PIEZAS recibidas por argumento: {piezas}")
        except Exception as e:
            print(f"[ERROR] No se pudo parsear PIEZAS desde argumento: {e}")
    if args.sheathing:
        try:
            sheathing = json.loads(args.sheathing)
            #print(f"[DEBUG] SHEATHING recibidas por argumento: {sheathing}")
        except Exception as e:
            print(f"[ERROR] No se pudo parsear SHEATHING desde argumento: {e}")
    return piezas, sheathing, args

def generar_datos_paneles(json_ocr):
    """
    Recibe el JSON OCR (lista de paneles) y genera para cada panel:
      - nombre_archivo: project_level
      - piezas: lista tipo PIEZAS
      - sheathing: lista tipo SHEATING
    Devuelve una lista de tuplas (nombre_archivo, piezas, sheathing, panel_name, page)
    """
    paneles = []
    for panel in json_ocr:
        nombre_archivo = f"{panel.get('project', '')}_{panel.get('level', '')}".replace(' ', '_')
        piezas = []
        sheathing = []
        for item in panel.get('cutting_list', []):
            label = item.get('label', '')
            member = item.get('member', '')
            description = item.get('description', '')
            qty = int(item.get('qty', 1)) if str(item.get('qty', 1)).isdigit() else 1
            length = item.get('length', '')
            width = item.get('width', '')
            # Detectar sheathing por el member o description
            if 'sheathing' in member.lower() or 'cladmate' in description.lower():
                sheathing.append((label, f"{member} {description}".strip(), qty, length, width))
            else:
                piezas.append((label, f"{member} {description}".strip(), qty, length, width))
        paneles.append({
            'nombre_archivo': nombre_archivo,
            'piezas': piezas,
            'sheathing': sheathing,
            'panel_name': panel.get('panel_name', ''),
            'page': panel.get('page', None)
        })
    return paneles


# PIEZAS = sorted(PIEZAS, key=lambda pieza: 'top' in pieza[1].lower(), reverse=True)

# print("[DEBUG] PIEZAS ordenadas por prioridad (top plate primero):")
# for pieza in PIEZAS:
#     print(f" - {pieza}")

def parse_medida_a_pulgadas(medida):
    partes = medida.split()
    pies, pulgadas, fraccion = 0, 0, 0
    if len(partes) > 0:
        pies = int(partes[0].split('-')[0])
        pulgadas = int(partes[0].split('-')[1])
        if len(partes[0].split('-')) > 2:
            fraccion = int(partes[0].split('-')[2])
    if len(partes) > 1:
        frac = partes[1].split('-')
        if len(frac) > 1:
            fraccion = int(frac[1])
    return pies * 12 + pulgadas + fraccion / 16.0

def get_input_output_svg():
    if len(sys.argv) > 2:
        input_svg = sys.argv[1]
        output_svg = sys.argv[2]
    else:
        input_svg = INPUT_SVG
        output_svg = OUTPUT_SVG

    return input_svg, output_svg

# --- NUEVO: Agrupador con tolerancia para comparar coordenadas flotantes ---
def agrupar_con_tolerancia(valores, tolerancia=0.01):
    """
    Agrupa valores que están dentro de una tolerancia y devuelve una lista de valores únicos representativos.
    """
    if not valores:
        return []
    valores_ordenados = sorted(valores)
    grupos = []
    grupo_actual = [valores_ordenados[0]]
    for v in valores_ordenados[1:]:
        if abs(v - grupo_actual[-1]) <= tolerancia:
            grupo_actual.append(v)
        else:
            grupos.append(grupo_actual)
            grupo_actual = [v]
    grupos.append(grupo_actual)
    # Tomar el promedio de cada grupo como valor representativo
    return [sum(g)/len(g) for g in grupos]

# --- MODIFICADO: Usar agrupador con tolerancia en la conversión de paths a rects ---
def convertir_paths_a_rects(svg, doc, guardar_intermedio=False, ruta_intermedia=None):
    paths = [el for el in svg.getElementsByTagName('*') if el.tagName.lower().endswith('path')]
    nuevos_rects = []
    rect_counter = 1
    for path in paths:
        d = path.getAttribute('d')
        coords = re.findall(r'([ML])\s*([\d\.\-]+)[,\s]+([\d\.\-]+)', d)
        if len(coords) < 4:
            continue
        xs = [float(x) for _, x, _ in coords]
        ys = [float(y) for _, _, y in coords]
        x_unique = agrupar_con_tolerancia(xs, tolerancia=0.01)
        y_unique = agrupar_con_tolerancia(ys, tolerancia=0.01)
        if len(x_unique) == 2 and len(y_unique) == 2:
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            width = max_x - min_x
            height = max_y - min_y
            x = min_x
            y = min_y
            rect = doc.createElement('rect')
            rect.setAttribute('x', str(x))
            rect.setAttribute('y', str(y))
            rect.setAttribute('width', str(width))
            rect.setAttribute('height', str(height))
            rect.setAttribute('data-path', d)
            if path.hasAttribute('id'):
                path_id = path.getAttribute('id')
                m = re.match(r'path(\d+)$', path_id)
                if m:
                    rect.setAttribute('id', f'rect{m.group(1)}')
                else:
                    rect.setAttribute('id', path_id)
            else:
                rect.setAttribute('id', f'rect{rect_counter}')
                rect_counter += 1
            if path.hasAttribute('fill'):
                rect.setAttribute('fill', path.getAttribute('fill'))
            if path.hasAttribute('style'):
                rect.setAttribute('style', path.getAttribute('style'))
            nuevos_rects.append((rect, path))
    for rect, path in nuevos_rects:
        parent = path.parentNode
        parent.replaceChild(rect, path)
    if guardar_intermedio and ruta_intermedia:
        svg_str = doc.toxml()
        svg_str = re.sub(r'<ns0:svg([^>]*)xmlns:ns0="http://www.w3.org/2000/svg"', r'<svg\1 xmlns="http://www.w3.org/2000/svg"', svg_str)
        svg_str = svg_str.replace('ns0:', '')
        with open(ruta_intermedia, 'w', encoding='utf-8') as f:
            f.write(svg_str)

def convertir_paths_oblicuos_a_rects(svg, doc, guardar_intermedio=False, ruta_intermedia=None):
    """
    Convierte paths oblicuos (definidos por dos puntos no alineados en x o y) en <rect> y los inserta al principio del SVG.
    Imprime información de cada path oblicuo encontrado y movido.
    """
    # Usar lista estática para evitar problemas al modificar el DOM durante la iteración
    paths = [el for el in svg.getElementsByTagName('*') if el.tagName.lower().endswith('path')]
    nuevos_rects = []
    rect_counter = 1000  # Para no chocar con los ids de los rects normales
    for path in paths:
        d = path.getAttribute('d')
        coords = re.findall(r'([ML])\s*([\d\.\-]+)[,\s]+([\d\.\-]+)', d)
        #print(f"[OBLICUO] Checking path id={path.getAttribute('id')} with {len(coords)} coords: {d}")
        #input("Presiona ENTER para continuar...")
        # Solo considerar paths con exactamente dos puntos (M y L)
        if len(coords) == 2:
            x1, y1 = float(coords[0][1]), float(coords[0][2])
            x2, y2 = float(coords[1][1]), float(coords[1][2])
            # Verificar que ambos puntos sean distintos en x y en y (no alineados)
            if x1 != x2 and y1 != y2:
                min_x, max_x = min(x1, x2), max(x1, x2)
                min_y, max_y = min(y1, y2), max(y1, y2)
                width = abs(max_x - min_x)
                height = abs(max_y - min_y)
                x = min_x
                y = min_y
                rect = doc.createElement('rect')
                rect.setAttribute('x', str(x))
                rect.setAttribute('y', str(y))
                rect.setAttribute('width', str(width))
                rect.setAttribute('height', str(height))
                rect.setAttribute('data-path', d)
                if path.hasAttribute('id'):
                    path_id = path.getAttribute('id')
                    m = re.match(r'path(\d+)$', path_id)
                    if m:
                        rect.setAttribute('id', f'rect{m.group(1)}Sheathing')
                        #print(f"[OBLICUO] Path id={path_id} convertido a rect id=rect{m.group(1)}Sheathing y movido al principio del SVG.")
                    else:
                        rect.setAttribute('id', path_id + 'Sheathing')
                        #print(f"[OBLICUO] Path id={path_id} convertido a rect id={path_id}Sheathing y movido al principio del SVG.")
                else:
                    rect.setAttribute('id', f'rect{rect_counter}')
                    #print(f"[OBLICUO] Path sin id convertido a rect id=rect{rect_counter} y movido al principio del SVG.")
                    rect_counter += 1
                #input("Presiona ENTER para continuar...")
                if path.hasAttribute('fill'):
                    rect.setAttribute('fill', path.getAttribute('fill'))
                if path.hasAttribute('style'):
                    rect.setAttribute('style', path.getAttribute('style'))
                nuevos_rects.append((rect, path))
    # Insertar los nuevos rects al principio del SVG y eliminar los paths originales
    for rect, path in nuevos_rects:
        parent = path.parentNode
        parent.removeChild(path)
        parent.insertBefore(rect, parent.firstChild)
    if guardar_intermedio and ruta_intermedia:
        svg_str = doc.toxml()
        svg_str = re.sub(r'<ns0:svg([^>]*)xmlns:ns0=\"http://www.w3.org/2000/svg\"', r'<svg\\1 xmlns=\"http://www.w3.org/2000/svg\"', svg_str)
        svg_str = svg_str.replace('ns0:', '')
        with open(ruta_intermedia, 'w', encoding='utf-8') as f:
            f.write(svg_str)

def separar_grupos_por_espacio(rects):
    if not rects:
        return [], []
    rects_y = []
    for rect in rects:
        y = float(rect.getAttribute('y')) if rect.hasAttribute('y') else 0.0
        w = float(rect.getAttribute('width'))
        h = float(rect.getAttribute('height'))
        if h > w:
            y_ref = y + h
            orientacion = 'vertical'
        else:
            y_ref = y
            orientacion = 'horizontal'
        rects_y.append((rect, y_ref, y, h, w, orientacion))
    rects_y.sort(key=lambda t: t[1])
    ys = [y_ref for _, y_ref, _, _, _, _ in rects_y]
    max_delta = 0
    max_idx = 0
    for i in range(1, len(ys)):
        delta = ys[i] - ys[i-1]
        if delta > max_delta:
            max_delta = delta
            max_idx = i
    if max_delta > 0 and max_idx < len(ys):
        y_limite = ys[max_idx]
        grupo_frontal = [rect for rect, y_ref, *_ in rects_y if y_ref <= y_limite]
        grupo_superior = [rect for rect, y_ref, *_ in rects_y if y_ref > y_limite]
    else:
        grupo_frontal = [rect for rect, *_ in rects_y]
        grupo_superior = []
    return grupo_frontal, grupo_superior

def listar_rects(rects):
    #print("\nListado de todos los <rect> con sus largos en x (width) e y (height):")
    for idx, rect in enumerate(rects):
        w = float(rect.getAttribute('width'))
        h = float(rect.getAttribute('height'))
        x = rect.getAttribute('x') if rect.hasAttribute('x') else ''
        y = rect.getAttribute('y') if rect.hasAttribute('y') else ''
        id_ = rect.getAttribute('id') if rect.hasAttribute('id') else ''
        style = rect.getAttribute('style') if rect.hasAttribute('style') else ''
        fill = rect.getAttribute('fill') if rect.hasAttribute('fill') else ''
        color = color_palette[idx % len(color_palette)]
        
        # Detectar orientación y aplicar proporciones correctas
        if w >= h:
            largo = w / PROPORCION_HORIZONTAL
            ancho = h / PROPORCION_VERTICAL
            orientacion = "horizontal"
            largo_formula = f"width/PROPORCION_HORIZONTAL = {w:.15f}/{PROPORCION_HORIZONTAL:.15f}"
            ancho_formula = f"height/PROPORCION_VERTICAL = {h:.15f}/{PROPORCION_VERTICAL:.15f}"
        else:
            largo = h / PROPORCION_HORIZONTAL
            ancho = w / PROPORCION_VERTICAL
            orientacion = "vertical"
            largo_formula = f"height/PROPORCION_HORIZONTAL = {h:.15f}/{PROPORCION_HORIZONTAL:.15f}"
            ancho_formula = f"width/PROPORCION_VERTICAL = {w:.15f}/{PROPORCION_VERTICAL:.15f}"
        
        #print(f"[{idx:02d}] id={id_} | x={x} y={y} | width={w:.3f} height={h:.3f} | largo={largo:.3f} in, ancho={ancho:.3f} in | orientacion={orientacion} | metodo=rect | color={color}")
        #print(f"     {largo_formula} | {ancho_formula}")

def detectar_y_etiquetar_piezas_grupo(rects, piezas, color_palette, proporcion_horizontal, proporcion_vertical, cantidad_override=None, nombre_grupo=""):
    # Para cada pieza, recorrer SIEMPRE desde el principio la lista de rects (no saltar los ya asignados a otra pieza)
    global PROPORCION_HORIZONTAL, PROPORCION_VERTICAL
    proporcion_horizontal = PROPORCION_HORIZONTAL
    proporcion_vertical = PROPORCION_VERTICAL
    color_idx = 0
    etiqueta_contadores = {}
    
    piezas = sorted(PIEZAS, key=lambda pieza: 'top' in pieza[1].lower(), reverse=True)
    print(f"[DEBUG] Procesando grupo '{nombre_grupo}' con {len(rects)} rects y {len(piezas)} piezas.")
    print("[DEBUG] PIEZAS ordenadas por prioridad (top plate primero):")
    for pieza in piezas:
        print(f" - {pieza}")
    
    # --- Revertir: procesar las piezas en el orden original de la lista ---
    for etiqueta, descripcion, cantidad, medida, *_ in piezas:
        long_real = parse_medida_a_pulgadas(medida)
        if cantidad_override is not None and cantidad_override > 0 and ("Stud" in descripcion):
            cantidad = cantidad_override
        orientacion_pieza = None
        if 'Stud' in descripcion:
            orientacion_pieza = 'vertical'
        elif 'Plate' in descripcion or 'VTP' in descripcion or 'Nailer' in descripcion:
            orientacion_pieza = 'horizontal'
        else:
            orientacion_pieza = None
        asignados = 0
        # --- Nuevo: primero los rects con 'top' en el id, luego los que tienen 'bottom', luego el resto ---
        rects_top = [rect for rect in rects if 'top' in (rect.getAttribute('id') or '').lower()]
        rects_bottom = [rect for rect in rects if 'bottom' in (rect.getAttribute('id') or '').lower()]
        rects_otros = [rect for rect in rects if rect not in rects_top and rect not in rects_bottom]
        for rect in rects_top + rects_bottom + rects_otros:
            id_ = rect.getAttribute('id') if rect.hasAttribute('id') else ''
            esperado = descripcion.replace(' ', '_')
            if not id_.startswith('rect'):
                continue
            w = float(rect.getAttribute('width'))
            h = float(rect.getAttribute('height'))
            orientacion = 'horizontal' if w >= h else 'vertical'
            if orientacion == 'horizontal':
                largo = w / proporcion_horizontal
                ancho = h / proporcion_vertical
            else:
                largo = h / proporcion_horizontal
                ancho = w / proporcion_vertical
            if abs(largo - long_real) <= MARGEN_LARGO and (orientacion_pieza is None or orientacion == orientacion_pieza):
                secuencial = etiqueta_contadores.get(descripcion, 1)
                new_id = f"{etiqueta}_{descripcion}_{secuencial}"
                print(f"[MATCH] Asignando id={new_id} a rect con largo_detectado={largo:.2f} in largo buscado={long_real:.3f} in y orientacion={orientacion}")
                new_id = normalizar_id_svg(new_id)
                rect.setAttribute('id', new_id)
                rect.setAttribute('data-id', new_id)
                rect.setAttribute('data-orientacion', orientacion)
                rect.setAttribute('data-largo', f"{long_real:.3f}")
                rect.setAttribute('data-pies', medida)
                match = re.search(r'(\d+)x(\d+)', descripcion)
                if match:
                    clave_nominal = f"{match.group(1)}x{match.group(2)}"
                    if clave_nominal in MEDIDAS_NOMINALES:
                        dim1 = MEDIDAS_NOMINALES[clave_nominal]["ancho"]
                        dim2 = MEDIDAS_NOMINALES[clave_nominal]["profundidad"]
                    ancho_real = ancho
                    if abs(ancho_real - dim1) < abs(ancho_real - dim2):
                        data_ancho = dim1
                        data_profundidad = dim2
                    else:
                        data_ancho = dim2
                        data_profundidad = dim1
                    rect.setAttribute('data-ancho', str(data_ancho))
                    rect.setAttribute('data-profundidad', str(data_profundidad))
                else:
                    rect.setAttribute('data-ancho', '')
                    rect.setAttribute('data-profundidad', '')
                color = color_palette[color_idx % len(color_palette)]
                style = rect.getAttribute('style') if rect.hasAttribute('style') else ''
                style = re.sub(r'fill\s*:[^;]+;?', '', style)
                style = re.sub(r';+', ';', style).strip('; ').strip()
                if style:
                    rect.setAttribute('style', style)
                else:
                    if rect.hasAttribute('style'):
                        rect.removeAttribute('style')
                rect.setAttribute('fill', color)
                print(f"[MATCH] {descripcion} asignado a rect id={new_id} largo_detectado={largo:.2f} in largo buscado={long_real:.3f} in in orientacion={orientacion} color={color}")
                color_idx += 1
                etiqueta_contadores[descripcion] = secuencial + 1
                asignados += 1
                if asignados >= cantidad:
                    break
    #print(f"\nResumen de ids y colores asignados en el SVG final (grupo {nombre_grupo}):")
    for rect in rects:
        id_ = rect.getAttribute('id') if rect.hasAttribute('id') else ''
        fill = rect.getAttribute('fill') if rect.hasAttribute('fill') else ''
        #print(f"  id={id_} | fill={fill}")

def normalizar_id_svg(texto):
    """
    Normaliza un id para SVG: solo letras, números, guion y guion bajo. Reemplaza espacios y caracteres especiales por '_', elimina acentos y puntos.
    """
    texto = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii')
    texto = re.sub(r'[^a-zA-Z0-9_-]', '_', texto)
    texto = re.sub(r'_+', '_', texto)
    texto = texto.strip('_')
    return texto

def comparar_grupos_por_x(grupo_frontal, grupo_superior, margen_ancho):
    """
    Compara los rectángulos del grupo frontal con los del grupo superior y asigna el mismo id
    a los rectángulos del grupo superior que coincidan en X con los del grupo frontal.

    Args:
        grupo_frontal (list): Lista de rectángulos del grupo frontal.
        grupo_superior (list): Lista de rectángulos del grupo superior.
        margen_ancho (float): Margen de tolerancia para la coincidencia en X.
    """
    for rect_frontal in grupo_frontal:
        x_frontal = float(rect_frontal.getAttribute('x')) + float(rect_frontal.getAttribute('width')) / 2
        id_frontal = rect_frontal.getAttribute('id') if rect_frontal.hasAttribute('id') else ''

        for rect_superior in grupo_superior:
            x_superior = float(rect_superior.getAttribute('x')) + float(rect_superior.getAttribute('width')) / 2

            if abs(x_frontal - x_superior) <= margen_ancho:
                rect_superior.setAttribute('id', id_frontal + '_superior')
                # Tomar el color del frontal detectado y asignarlo al superior
                rect_superior.setAttribute('fill', rect_frontal.getAttribute('fill'))
                rect_superior.setAttribute('style', rect_frontal.getAttribute('style'))
                                #rect_superior.setAttribute('style', id_frontal)               
                #print(f"[MATCH] Rectángulo superior id={id_frontal} asignado")

    # Asegurar que los cambios en los nodos del grupo superior se reflejen en el DOM
    for rect_superior in grupo_superior:
        parent = rect_superior.parentNode
        parent.replaceChild(rect_superior, rect_superior)

def determinar_orientacion_por_puntos(rect):
    # Obtener las coordenadas de los puntos extremos
    x_min = float(rect.getAttribute('x'))
    y_min = float(rect.getAttribute('y'))
    x_max = x_min + float(rect.getAttribute('width'))
    y_max = y_min + float(rect.getAttribute('height'))

    # Calcular ancho y alto
    ancho = x_max - x_min
    alto = y_max - y_min

    # Determinar orientación
    orientacion = 'horizontal' if ancho >= alto else 'vertical'
    return orientacion

def listar_rects_para_proporcion(svg):
    """
    Lista todos los <rect> que son studs verticales (h/w > 5) para ayudar a calcular proporciones.
    """
    rects_intermedios = [el for el in svg.getElementsByTagName('*') if el.tagName.lower().endswith('rect')]
    print("\n[CALCULO PROPORCION] <rect> verticales (studs) con ratio h/w > 5:")
    for rect in rects_intermedios:
        try:
            w = float(rect.getAttribute('width'))
            h = float(rect.getAttribute('height'))
        except (ValueError, AttributeError):
            continue
        # Solo considerar verticales: h mucho mayor que w (escala-independiente)
        if w > 0.01 and h > w * 5:
            id_ = rect.getAttribute('id') if rect.hasAttribute('id') else ''
            x = rect.getAttribute('x') if rect.hasAttribute('x') else ''
            y = rect.getAttribute('y') if rect.hasAttribute('y') else ''
            #print(f"id={id_} | x={x} y={y} | width={w:.3f} height={h:.3f} ratio={h/w:.1f}")

def calcular_proporcion_por_moda_rects(svg, piezas):
    """
    Calcula la proporción px/pulgada usando la moda de las alturas de studs verticales.
    Usa un filtro escala-independiente basado en ratio h/w > 5 (funciona a cualquier DPI).
    Si la proporción es válida, actualiza PROPORCION_HORIZONTAL y PROPORCION_VERTICAL.
    """
    global PROPORCION_HORIZONTAL, PROPORCION_VERTICAL
    rects_intermedios = [el for el in svg.getElementsByTagName('*') if el.tagName.lower().endswith('rect')]
    lados = []
    for rect in rects_intermedios:
        try:
            w = float(rect.getAttribute('width'))
            h = float(rect.getAttribute('height'))
        except (ValueError, AttributeError):
            continue
        # Filtro escala-independiente: h/w > 5 identifica studs verticales sin importar la escala
        if w > 0.01 and h > w * 5:
            lados.append(round(h, 6))
    if not lados:
        print("[PROPORCION] No se encontraron <rect> verticales (studs) con ratio h/w > 5.")
        return
    # Calcular la moda
    moda_px, count = Counter(lados).most_common(1)[0]
    print(f"[PROPORCION] Moda de los lados (en px): {moda_px} (aparece {count} veces)")
    # Tomar la pieza con mayor cantidad
    pieza_ref = max(piezas, key=lambda p: p[2])
    etiqueta, descripcion, cantidad, medida, width = pieza_ref
    largo_real = parse_medida_a_pulgadas(medida)
    print(f"[PROPORCION] Pieza de referencia: {descripcion} (cantidad={cantidad}) = {largo_real:.6f} pulgadas (de '{medida}')")
    proporcion = moda_px / largo_real
    print(f"[PROPORCION] Proporción calculada: {moda_px:.6f} px / {largo_real:.6f} in = {proporcion:.15f} px/pulgada")
    # Actualizar variables globales
    PROPORCION_HORIZONTAL = proporcion
    PROPORCION_VERTICAL = proporcion
    print(f"[PROPORCION] PROPORCION_HORIZONTAL y PROPORCION_VERTICAL actualizadas a: {proporcion:.15f}")
    return proporcion

def detectar_y_etiquetar_sheathing(rects, sheathing_list, color_palette, proporcion_horizontal, proporcion_vertical, nombre_grupo=""):
    """
    Etiqueta los rectángulos de sheathing usando el width como ancho y medida como largo.
    Compara tanto el ancho como el largo del rect con los valores de SHEATING.
    Evita asignar dos veces el mismo rect.
    """
    color_idx = len(color_palette) - 1  # Comienza desde el último color
    rects_asignados = set()
    for etiqueta, descripcion, cantidad, medida, width_str in sheathing_list:
        largo_real = parse_medida_a_pulgadas(medida)
        ancho_real = parse_medida_a_pulgadas(width_str)
        asignados = 0
        for rect in rects:
            # Saltar si ya fue asignado como sheathing en este proceso
            rect_id = id(rect)
            if rect_id in rects_asignados:
                continue
            id_ = rect.getAttribute('id') if rect.hasAttribute('id') else ''
            # Procesar rects que: (a) tienen 'sheathing' en el id (pre-etiquetados como oblicuos)
            # o (b) id empieza con 'rect' (sin etiquetar aún, Inkscape 1.4+ genera <rect> directamente)
            if 'sheathing' not in id_.lower() and not id_.lower().startswith('rect'):
                continue
            w = float(rect.getAttribute('width')) / proporcion_horizontal
            h = float(rect.getAttribute('height')) / proporcion_vertical
            if abs(w - ancho_real) <= MARGEN_ANCHO and abs(h - largo_real) <= MARGEN_LARGO:
                label_normalizado = normalizar_id_svg(descripcion)
                new_id = f"{etiqueta}_{label_normalizado}"
                rect.setAttribute('id', new_id)
                #rect.setAttribute('label', descripcion)
                rect.setAttribute('data-id', new_id)
                rect.setAttribute('data-largo', f"{largo_real:.3f}")
                rect.setAttribute('data-ancho', f"{ancho_real:.3f}")
                rect.setAttribute('data-pies', medida)
                rect.setAttribute('data-profundidad', "-1")
                color = color_palette[color_idx % len(color_palette)]
                style = rect.getAttribute('style') if rect.hasAttribute('style') else ''
                style = re.sub(r'fill\s*:[^;]+;?', '', style)
                style = re.sub(r';+', ';', style).strip('; ').strip()
                if style:
                    rect.setAttribute('style', style)
                else:
                    if rect.hasAttribute('style'):
                        rect.removeAttribute('style')
                rect.setAttribute('fill', color)
                # print(f"[MATCH-SHEATHING] {descripcion} asignado a rect id={new_id} ancho_detectado={w:.2f} in ancho buscado={ancho_real:.3f} in | largo_detectado={h:.2f} in largo buscado={largo_real:.3f} in | color={color}")
                # print("[DEBUG] Rect detectado y etiquetado como sheathing:")
                # print(f"    id={new_id}")
                # #
                # 
                # print(f"    label={descripcion}")
                # print(f"    x={rect.getAttribute('x')}, y={rect.getAttribute('y')}")
                # print(f"    width={rect.getAttribute('width')}, height={rect.getAttribute('height')}")
                # print(f"    data-largo={rect.getAttribute('data-largo')}, data-ancho={rect.getAttribute('data-ancho')}")
                # print(f"    fill={color}")
                # #input("Presiona ENTER para continuar...")
                color_idx -= 1
                asignados += 1
                rects_asignados.add(rect_id)

def parse_args():
    parser = argparse.ArgumentParser(description="Procesa SVG y etiqueta piezas/sheathing por argumentos JSON opcionales.")
    parser.add_argument('input_svg', nargs='?', default=None, help='Archivo SVG de entrada')
    parser.add_argument('output_svg', nargs='?', default=None, help='Archivo SVG de salida')
    parser.add_argument('--piezas', type=str, default=None, help='Lista PIEZAS en formato JSON')
    parser.add_argument('--sheathing', type=str, default=None, help='Lista SHEATHING en formato JSON')
    return parser.parse_args()
    args = parse_args()
    # Si se pasan argumentos, usarlos; si no, usar los valores por defecto

def main():    
    # Procesar argumentos y sobreescribir PIEZAS/SHEATHING si se pasan por línea de comandos
    piezas, sheathing, args = procesar_parametros()
    global PIEZAS, SHEATING, INPUT_SVG, OUTPUT_SVG

    if piezas is not None:
        PIEZAS = piezas
    if sheathing is not None:
        SHEATING = sheathing
    if args.input_svg:
        INPUT_SVG = args.input_svg
    if args.output_svg:
        OUTPUT_SVG = args.output_svg
  
    # Determinar input/output SVG
    if args.input_svg and args.output_svg:
        input_svg = args.input_svg
        output_svg = args.output_svg
    else:
        input_svg, output_svg = get_input_output_svg()

    #print(f"[DEBUG] Archivo SVG de entrada: {input_svg}")
    #print(f"[DEBUG] Archivo SVG de salida: {output_svg}")

    # Verificar existencia del archivo de entrada
    #print(f"[DEBUG] Verificando archivo de entrada: {input_svg}")
    if not os.path.exists(input_svg):
        print(f"[ERROR] El archivo de entrada no existe: {input_svg}")
        return
    else:
        print(f"[DEBUG] El archivo de entrada existe: {input_svg}")

    # === 2. Parsear el SVG original y convertir paths rectangulares a <rect> ===
    try:
        doc = minidom.parse(input_svg)
        print("[DEBUG] Archivo SVG parseado correctamente.")
    except Exception as e:
        print(f"[ERROR] No se pudo parsear el archivo SVG: {e}")
        return

    svg_tags = [el for el in doc.getElementsByTagName('*') if el.tagName.lower().endswith('svg')]
    if not svg_tags:
        print("[ERROR] No se encontró la etiqueta <svg> en el archivo.")
        return

    svg = svg_tags[0]
    print("[DEBUG] Etiqueta <svg> encontrada.")

    # Guardar SVG intermedio tras conversión de <path> a <rect>
    ruta_intermedia = input_svg.replace('.svg', '_rects_intermedios.svg')
    convertir_paths_a_rects(svg, doc, guardar_intermedio=True, ruta_intermedia=ruta_intermedia)
    convertir_paths_oblicuos_a_rects(svg, doc, guardar_intermedio=True, ruta_intermedia=ruta_intermedia)
    
    print(f"[DEBUG] SVG intermedio guardado en: {ruta_intermedia}")

    # Llamar al procedimiento modular para listar rects útiles para proporción
    listar_rects_para_proporcion(svg)

    # Calcular proporción por moda de rects
    calcular_proporcion_por_moda_rects(svg, PIEZAS)

    # === 3. Obtener todos los <rect> del SVG ya convertido ===
    rects = [el for el in svg.getElementsByTagName('*') if el.tagName.lower().endswith('rect')]

    # EXCLUIR los sheathing de los grupos
    rects_sin_sheathing = [r for r in rects if 'sheathing' not in (r.getAttribute('id') or '').lower()]

    # === 4. Separar los <rect> en dos grupos (frontal/superior) según salto vertical ===
    grupo_frontal, grupo_superior = separar_grupos_por_espacio(rects_sin_sheathing)
    #print(f"[DEBUG] Total de <rect> en grupo frontal: {len(grupo_frontal)}")
    #print(f"[DEBUG] Total de <rect> en grupo superior: {len(grupo_superior)}")

    # === 5. Listar y mostrar información de ambos grupos (solo imprime, no modifica ids) ===
    print("\n--- GRUPO FRONTAL ---")
    #listar_rects(grupo_frontal)

    # === 6. Etiquetar y asignar ids/colores a todas las piezas del grupo frontal ===
    print("\nBuscando y emparejando las siguientes piezas en el grupo frontal:")
    detectar_y_etiquetar_piezas_grupo(
        grupo_frontal,
        PIEZAS,
        color_palette,
        PROPORCION_HORIZONTAL,
        PROPORCION_VERTICAL,
        cantidad_override=None,  # Usar la cantidad de cada pieza según PIEZAS
        nombre_grupo="frontal"
    )

    # === 6b. Etiquetar y asignar ids/colores a los sheathing ===
    print("\nBuscando y emparejando los sheathing:")
    detectar_y_etiquetar_sheathing(
        rects,
        SHEATING,
        color_palette,
        PROPORCION_HORIZONTAL,
        PROPORCION_VERTICAL,
        nombre_grupo="frontal"
    )

    # === 6c. Crear rects sintéticos para sheathing no encontrado en el SVG ===
    # El PDF de framing no incluye geometría de sheathing; se inyectan rects
    # desde los datos OCR para que aparezcan en Odoo y en el GLB.
    sheathing_etiquetados = set()
    for rect in svg.getElementsByTagName('*'):
        if not rect.tagName.lower().endswith('rect'):
            continue
        id_ = rect.getAttribute('id') if rect.hasAttribute('id') else ''
        if 'sheathing' in id_.lower():
            etiqueta = id_.split('_')[0]
            sheathing_etiquetados.add(etiqueta)

    # Calcular bounding box del panel (rects etiquetados con data-id) para posicionar sheathing sobre el panel
    panel_x_min = float('inf')
    panel_y_min = float('inf')
    for rect in svg.getElementsByTagName('*'):
        if not rect.tagName.lower().endswith('rect'):
            continue
        did = rect.getAttribute('data-id') if rect.hasAttribute('data-id') else ''
        if not did:
            continue
        try:
            rx = float(rect.getAttribute('x') or 0)
            ry = float(rect.getAttribute('y') or 0)
            if rx < panel_x_min:
                panel_x_min = rx
            if ry < panel_y_min:
                panel_y_min = ry
        except ValueError:
            pass
    if panel_x_min == float('inf'):
        panel_x_min = 0.0
    if panel_y_min == float('inf'):
        panel_y_min = 0.0
    MARGEN_SHEATHING = 0.0
    cursor_x = panel_x_min

    color_sheathing_idx = len(color_palette) - 1
    for etiqueta, descripcion, cantidad, medida, width_str in SHEATING:
        if etiqueta in sheathing_etiquetados:
            continue  # Ya tiene rect etiquetado desde el SVG
        largo_real = parse_medida_a_pulgadas(medida)
        ancho_real = parse_medida_a_pulgadas(width_str)
        label_normalizado = normalizar_id_svg(descripcion)
        new_id = f"{etiqueta}_{label_normalizado}"
        # En SVG: width=ancho (horizontal), height=largo (vertical)
        # El paso5 reescala a pulgadas reales usando data-largo y data-ancho
        rect_w = ancho_real * PROPORCION_HORIZONTAL
        rect_h = largo_real * PROPORCION_VERTICAL
        rect_s = doc.createElement('rect')
        rect_s.setAttribute('id', new_id)
        rect_s.setAttribute('data-id', new_id)
        rect_s.setAttribute('x', str(round(cursor_x, 4)))
        rect_s.setAttribute('y', str(round(panel_y_min, 4)))
        rect_s.setAttribute('width', str(round(rect_w, 4)))
        rect_s.setAttribute('height', str(round(rect_h, 4)))
        rect_s.setAttribute('data-largo', f"{largo_real:.3f}")
        rect_s.setAttribute('data-ancho', f"{ancho_real:.3f}")
        rect_s.setAttribute('data-pies', medida)
        rect_s.setAttribute('data-profundidad', "-0.75")
        color_sheathing = color_palette[color_sheathing_idx % len(color_palette)]
        rect_s.setAttribute('fill', color_sheathing)
        color_sheathing_idx -= 1
        cursor_x += rect_w + MARGEN_SHEATHING
        svg.appendChild(rect_s)
        rects.append(rect_s)
        print(f"[SHEATHING-SINTETICO] {descripcion} -> {new_id} x={cursor_x - rect_w - MARGEN_SHEATHING:.1f} y={panel_y_min:.1f} w={rect_w:.1f} h={rect_h:.1f} largo={largo_real:.3f}\" ancho={ancho_real:.3f}\"")

    # # === 7. Comparar piezas del grupo frontal con el grupo superior ===
    print("\nComparando piezas del grupo frontal con el grupo superior...")
    comparar_grupos_por_x(grupo_frontal, grupo_superior, MARGEN_ANCHO)

    # === 8. Guardar el SVG final con los ids y colores asignados ===
    try:
        svg_str = doc.toxml()
        svg_str = re.sub(r'<ns0:svg([^>]*)xmlns:ns0="http://www.w3.org/2000/svg"', r'<svg\1 xmlns="http://www.w3.org/2000/svg"', svg_str)
        svg_str = svg_str.replace('ns0:', '')
        try:
            with open(output_svg, 'w', encoding='utf-8') as f:
                svg_str = svg_str.replace('><', '>\n<')  # Agregar salto de línea entre elementos
                f.write(svg_str)
            print(f"[DEBUG] SVG final guardado en: {output_svg}")
        except Exception as e:
            print(f"[ERROR] No se pudo guardar el archivo SVG: {e}")
    except Exception as e:
        print(f"[ERROR] No se pudo guardar el archivo SVG final: {e}")
    # ...existing code...

if __name__ == "__main__":
    main()
