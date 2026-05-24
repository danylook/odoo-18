import re
import numpy as np
import xml.etree.ElementTree as ET
from xml.dom.minidom import Document, parseString
import math
import sys

# === CONFIGURACIÓN DE ARCHIVOS ===
INPUT_SVG = "C:\\odoo17\\extra-addons\\others-17.0\\easyOCR\\svg_pages\\elevaciones de paredes_page3_coloreado.svg"
OUTPUT_SVG = "C:\\odoo17\\extra-addons\\others-17.0\\easyOCR\\svg_pages\\paths_transformados_completo_con_marcos3.svg"

# === FUNCIONES DE TRANSFORMACIÓN SVG ===
def extraer_matriz(transform):
    """Extrae la matriz y el offset de un atributo transform tipo matrix(a,b,c,d,e,f)."""
    m = list(map(float, re.findall(r"[-+]?\d*\.?\d+|\d+", transform)))
    return np.array([[m[0], m[2]], [m[1], m[3]]]), np.array([m[4], m[5]])

def convertir_a_absoluto(d_attr, transform_attr):
    """Convierte los puntos de un path a coordenadas absolutas usando la matriz de transformación."""
    if not d_attr or not transform_attr or "matrix" not in transform_attr:
        return None
    matriz, offset = extraer_matriz(transform_attr)
    # Cambiar la regex para aceptar notación científica
    comandos = re.findall(r'([MLHVZmlhvz])|([-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?)', d_attr)
    puntos = []
    i = 0
    modo = ""
    pos = np.array([0.0, 0.0])
    while i < len(comandos):
        if comandos[i][0]:
            modo = comandos[i][0]
            i += 1
        else:
            # Debug: mostrar el estado antes de intentar convertir a float
            #print(f"DEBUG: comandos={comandos}, i={i}, modo={modo}, d_attr={d_attr}, transform_attr={transform_attr}")
            if modo in "Mm":
                x, y = float(comandos[i][1]), float(comandos[i+1][1])
                if modo == "M":
                    pos = np.array([x, y])
                else:
                    pos = pos + np.array([x, y])
                puntos.append(pos.copy())
                i += 2
            elif modo in "Ll":
                x, y = float(comandos[i][1]), float(comandos[i+1][1])
                if modo == "L":
                    pos = np.array([x, y])
                else:
                    pos = pos + np.array([x, y])
                puntos.append(pos.copy())
                i += 2
            elif modo in "Hh":
                x = float(comandos[i][1])
                if modo == "H":
                    pos[0] = x
                else:
                    pos[0] = pos[0] + x
                puntos.append(pos.copy())
                i += 1
            elif modo in "Vv":
                y = float(comandos[i][1])
                if modo == "V":
                    pos[1] = y
                else:
                    pos[1] = pos[1] + y
                puntos.append(pos.copy())
                i += 1
            else:
                i += 1  # para Z u otros
    return [tuple(matriz @ p + offset) for p in puntos]

def procesar_svg_transformar_paths(input_svg, output_svg):
    """Procesa el SVG: convierte todos los paths con transform a coordenadas absolutas y guarda el resultado."""
    tree = ET.parse(input_svg)
    root = tree.getroot()
    namespace = re.match(r'\{.*\}', root.tag).group(0) if root.tag.startswith("{") else ""
    doc_final = Document()
    svg_final = doc_final.createElement("svg")
    svg_final.setAttribute("xmlns", "http://www.w3.org/2000/svg")
    svg_final.setAttribute("width", root.get("width", "1200"))
    svg_final.setAttribute("height", root.get("height", "1000"))
    if root.get("viewBox"):
        svg_final.setAttribute("viewBox", root.get("viewBox"))
    doc_final.appendChild(svg_final)
    for elem in root.iter():
        tag_clean = elem.tag.replace(namespace, "")
        if tag_clean == "path":
            path_id = elem.attrib.get("id")
            d_attr = elem.attrib.get("d", "")
            transform = elem.attrib.get("transform", "")
            puntos = convertir_a_absoluto(d_attr, transform)
            if puntos:
                d_nuevo = f"M {puntos[0][0]},{puntos[0][1]} " + " ".join(
                    f"L {x},{y}" for x, y in puntos[1:]
                ) + " Z"
                new_elem = doc_final.createElement("path")
                if path_id:
                    new_elem.setAttribute("id", path_id)
                new_elem.setAttribute("d", d_nuevo)
                for attr in elem.attrib:
                    if attr not in {"d", "transform", "id"}:
                        new_elem.setAttribute(attr, elem.attrib[attr])
                svg_final.appendChild(new_elem)
            else:
                # Path sin transform o sin matrix: copiar tal cual
                raw_xml = ET.tostring(elem, encoding="unicode")
                svg_final.appendChild(parseString(raw_xml).documentElement)
        # No else: no copiamos otros elementos
    return doc_final



# === FUNCIONES DE ANÁLISIS Y EXPORTACIÓN ===
def largo_path_recta(d):
    tokens = re.findall(r'-?\d*\.?\d+(?:[eE][-+]?\d+)?', d)
    if len(tokens) >= 4:
        x1 = float(tokens[0])
        x2 = float(tokens[2])
        largo = abs(x2 - x1)
        return largo if largo != 0 else None
    return None

def largo_path_recta_vertical(d):
    tokens = re.findall(r'-?\d*\.?\d+(?:[eE][-+]?\d+)?', d)
    if len(tokens) >= 4:
        y1 = float(tokens[1])
        y2 = float(tokens[3])
        largo = abs(y2 - y1)
        return largo if largo != 0 else None
    return None

def es_oblicuo(d):
    # Solo considera oblicuo si el path es una línea simple: M x1,y1 L x2,y2 (o m/l)
    tokens = re.findall(r'([MLml])|([-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?)', d)
    comandos = [t[0] for t in tokens if t[0]]
    numeros = [float(t[1]) for t in tokens if t[1]]
    if len(comandos) == 2 and comandos[0] in 'Mm' and comandos[1] in 'Ll' and len(numeros) == 4:
        x1, y1, x2, y2 = numeros
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        return dx > 1e-3 and dy > 1e-3
    return False

def es_rectangulo_o_oblicuo(d):
    # Detecta si el path es un rectángulo (horizontal/vertical) o un cuadrilátero oblicuo
    tokens = re.findall(r'-?\d*\.?\d+(?:[eE][-+]?\d+)?', d)
    if len(tokens) == 8:
        puntos = [(float(tokens[i]), float(tokens[i+1])) for i in range(0, 8, 2)]
        xs = [p[0] for p in puntos]
        ys = [p[1] for p in puntos]
        # Agrupa valores cercanos para tolerar errores de coma flotante
        def agrupa_cercanos(valores, tol=0.05):
            grupos = []
            for v in valores:
                for g in grupos:
                    if abs(g - v) < tol:
                        break
                else:
                    grupos.append(v)
            return grupos
        xs_agrup = agrupa_cercanos(xs)
        ys_agrup = agrupa_cercanos(ys)
        if len(xs_agrup) == 2 and len(ys_agrup) == 2:
            ancho = max(xs) - min(xs)
            alto = max(ys) - min(ys)
            #print(f"DEBUG RECT: xs={xs} ys={ys} ancho={ancho} alto={alto}")
            if ancho > alto:
                return 'horizontal', ancho, alto
            else:
                return 'vertical', ancho, alto
        # Si no es rectángulo, calculamos ángulos
        # Calcula ángulos entre lados consecutivos
        def angulo(v1, v2):
            dot = v1[0]*v2[0] + v1[1]*v2[1]
            norm1 = math.hypot(*v1)
            norm2 = math.hypot(*v2)
            if norm1 == 0 or norm2 == 0:
                return 0
            cos_theta = dot / (norm1 * norm2)
            cos_theta = max(-1, min(1, cos_theta))
            return math.degrees(math.acos(cos_theta))
        oblicuo = False
        for i in range(4):
            p0 = puntos[i]
            p1 = puntos[(i+1)%4]
            p2 = puntos[(i+2)%4]
            v1 = (p1[0]-p0[0], p1[1]-p0[1])
            v2 = (p2[0]-p1[0], p2[1]-p1[1])
            ang = angulo(v1, v2)
            if 8 < ang < 170:
                oblicuo = True
                break
        if oblicuo:
            return 'oblicuo', None, None
    return None, None, None

# === MAIN: FLUJO PRINCIPAL ===
def main():
    input_svg, output_svg = get_input_output_svg()
    doc_final = procesar_svg_transformar_paths(input_svg, output_svg)

    # Guardar el SVG con saltos de línea solo una vez
    guardar_svg_con_saltos_linea(doc_final, output_svg)
    print(f"SVG procesado y guardado con saltos de línea en: {output_svg}")

def get_input_output_svg():
    # Usa argumentos si se pasan, si no usa variables por defecto
    if len(sys.argv) > 2:
        input_svg = sys.argv[1]
        output_svg = sys.argv[2]
    else:
        input_svg = INPUT_SVG
        output_svg = OUTPUT_SVG
    return input_svg, output_svg

def guardar_svg_con_saltos_linea(doc_final, output_svg):
    """
    Guarda el SVG con saltos de línea entre atributos para mejor legibilidad.
    """
    try:
        with open(output_svg, "w", encoding="utf-8") as f:
            svg_str = doc_final.toprettyxml()
            svg_str = svg_str.replace("><", ">\n<")  # Agregar salto de línea entre elementos
            f.write(svg_str)
        print(f"✔️ SVG guardado con saltos de línea en: {output_svg}")
    except Exception as e:
        print(f"[ERROR] No se pudo guardar el archivo SVG: {e}")

def procesar_y_guardar_svg_coloreado(output_svg, root):
    """
    Procesa el SVG transformado, clasifica, asigna color y guarda el resultado en un archivo.
    """
    new_root = ET.Element(root.tag, root.attrib)
    if 'viewBox' in root.attrib:
        new_root.set('viewBox', root.attrib['viewBox'])
    if 'width' in root.attrib:
        new_root.set('width', root.attrib['width'])
    if 'height' in root.attrib:
        new_root.set('height', root.attrib['height'])
    for elem in root.iter():
        if elem.tag.split('}')[-1] == 'path':
            id_ = elem.attrib.get('id', '(sin id)')
            d = elem.attrib.get('d')
            color = None
            motivo = ''
            if d:
                orientacion, ancho, alto = es_rectangulo_o_oblicuo(d)
                if orientacion == 'horizontal':
                    color = '#e6194b'
                    motivo = 'horizontal (rectángulo)'
                elif orientacion == 'vertical':
                    color = '#4363d8'
                    motivo = 'vertical (rectángulo)'
                elif orientacion == 'oblicuo':
                    color = '#00cc00'
                    motivo = 'oblicuo'
                elif largo_path_recta(d):
                    color = '#e6194b'
                    motivo = 'horizontal'
                elif largo_path_recta_vertical(d):
                    color = '#4363d8'
                    motivo = 'vertical'
            if color:
                new_elem = ET.Element(elem.tag, elem.attrib)
                new_elem.attrib['fill'] = color
                style = new_elem.attrib.get('style', '')
                if 'fill:' in style:
                    style = re.sub(r'fill\s*:[^;]+', f'fill:{color}', style)
                else:
                    if style and not style.strip().endswith(';'):
                        style += ';'
                    style += f'fill:{color};'
                new_elem.attrib['style'] = style
                new_elem.attrib['stroke'] = '#222222'
                new_elem.attrib['stroke-width'] = '1'
                new_root.append(new_elem)
                print(f"[COLOR] path id={id_} d={d} => {motivo} color={color}")
    tree2 = ET.ElementTree(new_root)
    tree2.write(output_svg, encoding='utf-8', xml_declaration=True)
    print(f"SVG coloreado exportado: {output_svg}")

if __name__ == "__main__":
    main()
