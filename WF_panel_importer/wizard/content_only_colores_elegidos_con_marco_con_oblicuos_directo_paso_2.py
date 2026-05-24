import xml.etree.ElementTree as ET
import re
import os
import sys

# Parámetros globales para el largo mínimo y máximo de oblicuos
LARGO_MINIMO = 25 # Ajusta este valor según tu necesidad
LARGO_MAXIMO = 320.0  # Ajusta este valor según tu necesidad

# Límites de ángulos permitidos para oblicuos
ANGULO_MINIMO = 6  # Valor mínimo de ángulo permitido
ANGULO_MAXIMO = 170  # Valor máximo de ángulo permitido

def es_oblicuo(x1, y1, x2, y2, largo_min=LARGO_MINIMO, largo_max=LARGO_MAXIMO, angulo_min=5, angulo_max=170):
    """
    Determina si el segmento definido por (x1, y1)-(x2, y2) es oblicuo según los parámetros dados.
    - largo_min, largo_max: límites de longitud
    - angulo_min, angulo_max: límites de ángulo en grados
    """
    import math
    def distancia(x1, y1, x2, y2):
        return ((x2 - x1)**2 + (y2 - y1)**2)**0.5
    def inclinacion(x1, y1, x2, y2):
        return math.degrees(math.atan2((y2 - y1), (x2 - x1)))
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    largo = distancia(x1, y1, x2, y2)
    angulo = abs(inclinacion(x1, y1, x2, y2))
    return (
        largo_min <= largo <= largo_max and
        angulo_min <= angulo <= angulo_max and
        dx >= 0.05 and dy >= 0.05
    )

INPUT_SVG = "C:\\odoo17\\extra-addons\\others-17.0\\easyOCR\\svg_pages\\elevaciones_de_paredes_page10.svg"
OUTPUT_SVG = "C:\\odoo17\\extra-addons\\others-17.0\\easyOCR\\svg_pages\\elevaciones_de_paredes_page3_coloreado.svg"
TARGET_COLORS = {
    '#228b22',  # verde bosque
    '#6495ed', # azul acero claro
    '#90ee90', # verde claro
    '#daa520', # oro viejo
    '#f5f5dc', # beige
    '#ff00ff', # magenta
}
COLOR_NAMES = {
    '#228b22': 'verde bosque',
    '#6495ed': 'azul acero claro',
    '#808080': 'gris',
    '#90ee90': 'verde claro',
    '#d3d3d3': 'gris claro',
    '#daa520': 'oro viejo',
    '#f5f5dc': 'beige',
    '#ff00ff': 'magenta',
}
STROKE_WIDTH = '0.005'
SCALE = 1  # Proporción para duplicar el tamaño

def normalize_color(val):
    if not val:
        return None
    val = val.strip().lower()
    if val.startswith('rgb'):
        nums = [int(x) for x in val[val.find('(')+1:val.find(')')].split(',')]
        return '#{:02x}{:02x}{:02x}'.format(*nums)
    if val.startswith('#'):
        if len(val) == 4:
            val = '#' + ''.join([c*2 for c in val[1:]])
        return val
    return val

def element_has_target_color(elem):
    for attr in ("fill", "stroke"):
        val = elem.get(attr)
        if normalize_color(val) in TARGET_COLORS:
            return True
    style = elem.get("style")
    if style:
        for part in style.split(';'):
            if ':' in part:
                k, v = part.split(':', 1)
                if k.strip() in ("fill", "stroke") and normalize_color(v) in TARGET_COLORS:
                    return True
    return False

def scale_svg_root(root):
    # Escalar viewBox si existe
    new_root = ET.Element(root.tag, root.attrib)
    viewBox = root.get('viewBox')
    if viewBox:
        parts = viewBox.strip().split()
        if len(parts) == 4:
            scaled = [str(float(x)*SCALE) if i > 1 else str(float(x)) for i, x in enumerate(parts)]
            new_root.set('viewBox', ' '.join(scaled))
    # Escalar width y height si existen
    for dim in ('width', 'height'):
        val = root.get(dim)
        if val:
            try:
                if val.endswith('px'):
                    num = float(val[:-2])
                    new_root.set(dim, f"{num*SCALE}px")
                else:
                    num = float(val)
                    new_root.set(dim, str(num*SCALE))
            except Exception:
                pass
    for child in root:
        if not isinstance(child.tag, str):
            new_root.append(child)
    return new_root

def process_svg_element(elem):
    tag = elem.tag.split('}')[-1]
    color_found = None
    for attr in ("fill", "stroke"):
        val = elem.get(attr)
        norm = normalize_color(val)
        if norm in TARGET_COLORS:
            color_found = norm
    style = elem.get("style")
    if style:
        for part in style.split(';'):
            if ':' in part:
                k, v = part.split(':', 1)
                if k.strip() in ("fill", "stroke"):
                    norm = normalize_color(v)
                    if norm in TARGET_COLORS:
                        color_found = norm
    attrs = {k: v for k, v in elem.attrib.items() if k in ("id", "fill", "stroke", "style", "class", "x", "y", "width", "height", "d")}
    # print("\n# --- fed: INICIO PROCESO ELEMENTO ---")
    # print(f"<{tag} {attrs}>  --> color detectado: {color_found if color_found else 'N/A'}")
    new_elem = ET.Element(elem.tag, elem.attrib)
    # Escalar atributos geométricos
    for attr in ("x", "y", "width", "height", "cx", "cy", "r", "rx", "ry"):
        val = new_elem.get(attr)
        if val:
            try:
                new_elem.set(attr, str(float(val)*SCALE))
            except Exception:
                pass
    # Escalar path d si existe
    if 'd' in new_elem.attrib:
        d = new_elem.get('d')
        def scale_path(match):
            val = float(match.group(0)) * SCALE
            # Si el valor es muy pequeño, usa notación científica con exponente entero
            if abs(val) < 0.001 and val != 0:
                return f"{val:.6e}".replace('e+0', 'e').replace('e+','e').replace('e0','e0').replace('e-0','e-')
            else:
                return f"{val:.8f}".rstrip('0').rstrip('.')
        d_scaled = re.sub(r'(?<![a-zA-Z])-?\d*\.?\d+(?:[eE][-+]?\d+)?', scale_path, d)
        # Si no termina en Z/z, agregarlo para cerrar el path
        if not d_scaled.strip().lower().endswith('z'):
            d_scaled = d_scaled.strip() + ' Z'
        new_elem.set('d', d_scaled)
    # Forzar marco negro de STROKE_WIDTH SOLO en style (no como atributo suelto)
    # Si el path ya tiene style, lo modificamos, si no, lo creamos
    style = elem.get('style')
    style_parts = []
    found_stroke = False
    found_stroke_width = False
    if style:
        for part in style.split(';'):
            if part.strip().startswith('stroke:'):
                style_parts.append('stroke:#000000')
                found_stroke = True
            elif part.strip().startswith('stroke-width:'):
                style_parts.append(f'stroke-width:{STROKE_WIDTH}')
                found_stroke_width = True
            elif part.strip():
                style_parts.append(part)
    # Si no existía style, lo creamos con stroke y stroke-width
    if not style:
        style_parts = [f'stroke:#000000', f'stroke-width:{STROKE_WIDTH}']
    if not found_stroke:
        style_parts.append('stroke:#000000')
    if not found_stroke_width:
        style_parts.append(f'stroke-width:{STROKE_WIDTH}')
    style = ';'.join(style_parts)
    new_elem.set('style', style)
    # Eliminar atributos sueltos de stroke y stroke-width si existen
    if 'stroke' in new_elem.attrib:
        del new_elem.attrib['stroke']
    if 'stroke-width' in new_elem.attrib:
        del new_elem.attrib['stroke-width']
    # print("# --- fed: FIN PROCESO ELEMENTO ---\n")
    return new_elem

def escalar_elemento_svg(elem, scale):
    import copy
    new_elem = copy.deepcopy(elem)
    for attr in ("x", "y", "width", "height", "cx", "cy", "r", "rx", "ry"):
        val = new_elem.get(attr)
        if val:
            try:
                new_elem.set(attr, str(float(val)*scale))
            except Exception:
                pass
    if 'd' in new_elem.attrib:
        d = new_elem.get('d')
        def scale_path(match):
            val = float(match.group(0)) * scale
            if abs(val) < 0.001 and val != 0:
                return f"{val:.6e}".replace('e+0', 'e').replace('e+','e').replace('e0','e0').replace('e-0','e-')
            else:
                return f"{val:.8f}".rstrip('0').rstrip('.')
        import re
        d_scaled = re.sub(r'(?<![a-zA-Z])-?\d*\.?\d+(?:[eE][-+]?\d+)?', scale_path, d)
        new_elem.set('d', d_scaled)
    return new_elem

def extraer_oblicuos_svg_directo(input_svg, output_svg, y_max_colores=None):
    from xml.dom.minidom import parse, parseString, Document
    PROPORCION_HORIZONTAL = 164.5 / 673.53113925
    PROPORCION_VERTICAL = 104.625 / 428.4222147
    promedio_largo = 9.8180
    margen_inferior = promedio_largo * 0.90
    margen_superior = promedio_largo * 1.10
    def distancia(x1, y1, x2, y2):
        return ((x2 - x1)**2 + (y2 - y1)**2)**0.5
    def inclinacion(x1, y1, x2, y2):
        import math
        return math.degrees(math.atan2((y2 - y1), (x2 - x1)))
    svg_doc = parse(input_svg)
    paths = svg_doc.getElementsByTagName("path")
    elementos_por_id = {path.getAttribute("id"): path for path in paths if path.hasAttribute("id")}
    oblicuos_final = []
    def aplicar_matriz(x, y, matriz):
        x_new = matriz[0]*x + matriz[2]*y + matriz[4]
        y_new = matriz[1]*x + matriz[3]*y + matriz[5]
        return x_new, y_new

    def parsear_matriz(transform_str):
        m = re.search(r"matrix\(([^)]+)\)", transform_str)
        if m:
            return list(map(float, m.group(1).replace(',', ' ').split()))
        return None

    oblicuos_candidatos = []
    for path in paths:
        # Solo buscar oblicuos con stroke negro
        style = path.getAttribute("style") if path.hasAttribute("style") else ""
        stroke = path.getAttribute("stroke") if path.hasAttribute("stroke") else None
        stroke_color = None
        if stroke:
            stroke_color = stroke.strip().lower()
        elif style:
            for part in style.split(';'):
                if part.strip().startswith('stroke:'):
                    stroke_color = part.split(':',1)[1].strip().lower()
        if stroke_color != "#000000":
            continue
        if not path.hasAttribute("d"):
            continue
        d = path.getAttribute("d").strip()
        path_id = path.getAttribute("id") if path.hasAttribute("id") else ""
        # Detectar paths simples: M x1,y1 ... x2,y2 (solo dois pares de números, sin otros comandos)
        match = re.match(r'^([Mm])\s*([-+]?\d*\.?\d+),([-+]?\d*\.?\d+)\s*([-+]?\d*\.?\d+),([-+]?\d*\.?\d+)(\s*[Zz]?)$', d)
        if match:
            cmd = match.group(1)
            x1, y1 = float(match.group(2)), float(match.group(3))
            dx, dy = float(match.group(4)), float(match.group(5))
            if cmd == 'm':  # relativo
                x2, y2 = x1 + dx, y1 + dy
            else:  # absoluto
                x2, y2 = dx, dy
        else:
            continue
        # Aplicar matriz de transformación si existe
        matriz = None
        if path.hasAttribute("transform"):
            matriz = parsear_matriz(path.getAttribute("transform"))
        if matriz:
            x1t, y1t = aplicar_matriz(x1, y1, matriz)
            x2t, y2t = aplicar_matriz(x2, y2, matriz)
        else:
            x1t, y1t, x2t, y2t = x1, y1, x2, y2
        # Calcular valores reales transformados
        dx_real = abs(x2t - x1t)
        dy_real = abs(y2t - y1t)
        largo_real = ((x2t - x1t)**2 + (y2t - y1t)**2)**0.5
        import math
        angulo_real = abs(math.degrees(math.atan2((y2t - y1t), (x2t - x1t))))
        motivo = []
        # 2. Filtrar por ángulo y largo usando valores transformados
        if not (ANGULO_MINIMO <= angulo_real <= ANGULO_MAXIMO):
            motivo.append(f"ángulo fuera de rango [{angulo_real:.1f}]")
        if not (LARGO_MINIMO <= largo_real <= LARGO_MAXIMO):
            motivo.append(f"largo fuera de rango [{largo_real:.3f}]")
        incluido = False
        if not motivo:
            oblicuos_candidatos.append({
                'id': path_id,
                'd': d,
                'x1t': x1t, 'y1t': y1t, 'x2t': x2t, 'y2t': y2t,
                'largo': largo_real, 'angulo': angulo_real
            })
            incluido = True
        # Debug: imprimir siempre los valores
        print(f"[oblicuo?] id={path_id} d={d} x1={x1t:.3f} y1={y1t:.3f} x2={x2t:.3f} y2={y2t:.3f} largo={largo_real:.3f} angulo={angulo_real:.1f} {'[INCLUIDO]' if incluido else '[NO]'} {'; '.join(motivo)}")
    # --- FILTRO: solo los oblicuos con valores de y igual o mayor que el path de color más abajo (y_max_colores) ---
    if oblicuos_candidatos and y_max_colores is not None:
        print(f"[DEBUG] Umbral de comparación para oblicuos (y_max_colores): {y_max_colores}")
        oblicuos_final = [o['id'] for o in oblicuos_candidatos if max(o['y1t'], o['y2t']) <= y_max_colores]
    else:
        oblicuos_final = []
    doc_out = Document()
    svg_out = doc_out.createElement("svg")
    svg_out.setAttribute("xmlns", "http://www.w3.org/2000/svg")
    svg_out.setAttribute("width", "1000")
    svg_out.setAttribute("height", "1000")
    doc_out.appendChild(svg_out)
    for pid in oblicuos_final:
        original = elementos_por_id.get(pid)
        if original:
            path_xml = parseString(original.toxml()).documentElement
            imported_path = doc_out.importNode(path_xml, deep=True)
            svg_out.appendChild(imported_path)
    with open(output_svg, "w") as f:
        f.write(doc_out.toprettyxml())
    # print(f"Guardado: {output_svg}")

def agregar_oblicuos_al_svg(svg_path_colores, svg_path_oblicuos):
    import xml.etree.ElementTree as ET
    tree_final = ET.parse(svg_path_colores)
    root_final = tree_final.getroot()
    tree_oblicuos = ET.parse(svg_path_oblicuos)
    root_oblicuos = tree_oblicuos.getroot()
    for elem in root_oblicuos.findall('.//{http://www.w3.org/2000/svg}path') + root_oblicuos.findall('.//path'):
        elem_escalado = escalar_elemento_svg(elem, SCALE)
        root_final.append(elem_escalado)
    tree_final.write(svg_path_colores, encoding='utf-8', xml_declaration=True)
    # print(f"Oblicuos agregados al SVG final (escalados): {svg_path_colores}")

def convertir_svg_colores_con_marco(input_svg, output_svg):
    import xml.etree.ElementTree as ET
    def aplicar_matriz(x, y, matriz):
        x_new = matriz[0]*x + matriz[2]*y + matriz[4]
        y_new = matriz[1]*x + matriz[3]*y + matriz[5]
        return x_new, y_new
    def parsear_matriz(transform_str):
        m = re.search(r"matrix\(([^)]+)\)", transform_str)
        if m:
            return list(map(float, m.group(1).replace(',', ' ').split()))
        return None
    tree = ET.parse(input_svg)
    root = tree.getroot()
    detected_colors = set()
    new_root = scale_svg_root(root)
    y_max_colores = None  # Acumular el valor máximo de y de los paths de colores
    id_max_colores = None  # Guardar el id del path que determina el y_max_colores
    for elem in root.iter():
        if element_has_target_color(elem):
            new_elem = process_svg_element(elem)
            new_root.append(new_elem)
            # Calcular y_max_colores para cada path de color
            if 'd' in elem.attrib:
                d = elem.get('d').strip()
                # Analizar todos los comandos y puntos del path, simple o complejo
                puntos = []
                x, y = 0, 0
                start_x, start_y = 0, 0
                tokens = re.findall(r'[MmLlHhVvZz]|-?\d*\.?\d+(?:[eE][-+]?\d+)?', d)
                i = 0
                modo = None
                while i < len(tokens):
                    token = tokens[i]
                    if token in 'MmLlHhVvZz':
                        modo = token
                        i += 1
                        if modo in 'Zz':
                            x, y = start_x, start_y
                            puntos.append((x, y))
                        continue
                    if modo in 'Mm':
                        dx = float(tokens[i])
                        dy = float(tokens[i+1])
                        if modo == 'm':
                            x += dx
                            y += dy
                        else:
                            x, y = dx, dy
                        start_x, start_y = x, y
                        puntos.append((x, y))
                        i += 2
                    elif modo in 'Ll':
                        dx = float(tokens[i])
                        dy = float(tokens[i+1])
                        if modo == 'l':
                            x += dx
                            y += dy
                        else:
                            x, y = dx, dy
                        puntos.append((x, y))
                        i += 2
                    elif modo in 'Hh':
                        dx = float(tokens[i])
                        if modo == 'h':
                            x += dx
                        else:
                            x = dx
                        puntos.append((x, y))
                        i += 1
                    elif modo in 'Vv':
                        dy = float(tokens[i])
                        if modo == 'v':
                            y += dy
                        else:
                            y = dy
                        puntos.append((x, y))
                        i += 1
                    else:
                        i += 1
                # Aplicar matriz de transformación si existe
                matriz = None
                if 'transform' in elem.attrib:
                    matriz = parsear_matriz(elem.get('transform'))
                puntos_transformados = []
                for px, py in puntos:
                    if matriz:
                        px, py = aplicar_matriz(px, py, matriz)
                    puntos_transformados.append((px, py))
                if puntos_transformados:
                    y_max_local = max(py for px, py in puntos_transformados)
                    if y_max_colores is None or y_max_local > y_max_colores:
                        y_max_colores = y_max_local
                        id_max_colores = elem.get('id','')
                    #print(f"[DEBUG] Path color detectado: id={elem.get('id','')} d={d} puntos={puntos_transformados}")
                    #print(f"[DEBUG] y_max_local={y_max_local:.3f} y_max_colores acumulado={y_max_colores:.3f} (id_max_colores={id_max_colores})")
                #else:
                    #print(f"[DEBUG] Path color detectado: id={elem.get('id','')} d={d} (no se encontraron puntos)")
                    #print(f"[DEBUG] y_max_colores acumulado={y_max_colores if y_max_colores is not None else 'None'} (id_max_colores={id_max_colores})")
            #else:
                #print(f"[DEBUG] Path color detectado: id={elem.get('id','')} (sin atributo d)")
                #print(f"[DEBUG] y_max_colores acumulado={y_max_colores if y_max_colores is not None else 'None'} (id_max_colores={id_max_colores})")
    # Eliminar el archivo de salida si existe antes de escribir
    if os.path.exists(output_svg):
        os.remove(output_svg)
    tree2 = ET.ElementTree(new_root)
    tree2.write(output_svg, encoding='utf-8', xml_declaration=True)
    #print(f"[DEBUG] Valor máximo de y (más abajo) de paths de colores FINAL: {y_max_colores} (id_max_colores={id_max_colores})")
    return y_max_colores

def list_svg_colors_with_names(input_svg):
    tree = ET.parse(input_svg)
    root = tree.getroot()
    colors = set()
    for elem in root.iter():
        for attr in ("fill", "stroke"):
            val = elem.get(attr)
            norm = normalize_color(val)
            if norm:
                colors.add(norm)
        style = elem.get("style")
        if style:
            for part in style.split(';'):
                if ':' in part:
                    k, v = part.split(':', 1)
                    if k.strip() in ("fill", "stroke"):
                        norm = normalize_color(v)
                        if norm:
                            colors.add(norm)
    # print("Colores únicos encontrados en el SVG:")
    # for color in sorted(colors):
    #     if color in TARGET_COLORS:
    #         nombre = COLOR_NAMES.get(color, "(sin nombre conocido)")
    #         print(f"{color} -> {nombre}")

def main():
    import sys
    import os
    # Si se pasan argumentos, usarlos; si no, usar los valores por defecto INPUT_SVG y OUTPUT_SVG
    if len(sys.argv) >= 3:
        input_svg = sys.argv[1]
        output_svg = sys.argv[2]
    else:
        input_svg = INPUT_SVG
        output_svg = OUTPUT_SVG
    #print(f"[content_only_colores] IN: {input_svg}\n[content_only_colores] OUT: {output_svg}")
    y_max_colores = convertir_svg_colores_con_marco(input_svg, output_svg)
    #print(f"[OK] Procesado: {os.path.basename(input_svg)} -> {os.path.basename(output_svg)}")
    # list_svg_colors_with_names(input_svg)
    # --- Extraer oblicuos y agregarlos al SVG final ---
    TEMP_OBLICUOS = os.path.join(os.path.dirname(output_svg), "_temp_oblicuos.svg")
    extraer_oblicuos_svg_directo(input_svg, TEMP_OBLICUOS, y_max_colores)
    agregar_oblicuos_al_svg(output_svg, TEMP_OBLICUOS)
    try:
        os.remove(TEMP_OBLICUOS)
    except Exception as e:
        pass

if __name__ == "__main__":
    main()
