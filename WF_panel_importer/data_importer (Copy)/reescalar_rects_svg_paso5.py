
import sys
from xml.dom import minidom
import re
import os

# === VARIABLES GLOBALES Y CONFIGURACIÓN ===
INPUT_SVG = "C:\\odoo17new\\extra-addons\\others-17.0\\easyOCR\\svg_pages\\L1_E14_paso4_coloreado.svg"
OUTPUT_SVG = "C:\\odoo17new\\extra-addons\\others-17.0\\easyOCR\\svg_pages\\reescalado_elevaciones_de_paredes_rects8.svg"
NUEVA_PROPORCION = 10.0  # px por pulgada
PROPORCION_ORIGINAL = 8.0  # px por pulgada (ajusta este valor según corresponda)
AJUSTE = .08  # Ajuste para evitar problemas de precisión
PROPORCIONALIDAD_TOP_PLATE = None

# === FUNCIONES ===
# === GUARDAR SVG CON SALTOS DE LÍNEA ENTRE ELEMENTOS ===
def guardar_svg_con_saltos_linea(doc_final, output_svg):
    """
    Guarda el SVG con saltos de línea entre atributos para mejor legibilidad.
    """
    try:
        with open(output_svg, "w", encoding="utf-8") as f:
            svg_str = doc_final.toprettyxml()
            svg_str = svg_str.replace("><", ">\n<")  # Agregar salto de línea entre elementos
            f.write(svg_str)
        print(f"[proc] SVG final guardado en: {output_svg}")
    except Exception as e:
        print(f"[ERROR] No se pudo guardar el archivo SVG: {e}")
# === AJUSTAR X E Y DE TODOS LOS RECT AL MÚLTIPLO DE 0.25 MÁS CERCANO ===

def ajustar_xy_a_multiplo_025(svg):
    """
    Ajusta los atributos x e y de todos los <rect> al múltiplo de 0.25 más cercano.
    """
    def redondear_025_mas_cercano(valor):
        # Redondea al múltiplo de 0.25 más cercano
        return round(valor * 4) / 4
    rects = [el for el in svg.getElementsByTagName('*') if el.tagName.lower().endswith('rect')]
    for r in rects:
        try:
            x = float(r.getAttribute('x'))
            y = float(r.getAttribute('y'))
            x_ajust = redondear_025_mas_cercano(x)
            y_ajust = redondear_025_mas_cercano(y)
            #if x != x_ajust or y != y_ajust:
                #print(f"[AJUSTE 0.25 ROUND] Rect id={r.getAttribute('id')} x: {x} -> {x_ajust}, y: {y} -> {y_ajust}")
            r.setAttribute('x', str(x_ajust))
            r.setAttribute('y', str(y_ajust))
        except Exception:
            continue
        
def alinear_todos_los_superiores_por_colores(svg):
    """
    Detecta todos los colores únicos de los rects frontales (sin 'superior' en el id)
    y aplica alinear_rects_superior_y_frontal_por_color para cada uno.
    """
    rects = [el for el in svg.getElementsByTagName('*') if el.tagName.lower().endswith('rect')]
    colores = set()
    for r in rects:
        rid = (r.getAttribute('id') or '').lower()
        if 'superior' not in rid and r.getAttribute('fill'):
            colores.add(r.getAttribute('fill').lower())
    for color in colores:
        alinear_rects_superior_y_frontal_por_color(svg, color)
        
# === ALINEAR EN X TODOS LOS RECT DEL COLOR DEL SUPERIOR ===
def alinear_rects_superior_y_frontal_por_color(svg, color):
    """
    Busca el rect superior y el grupo frontal por color, alinea en x todos los rects con ese color,
    ajusta el ancho del superior y copia los campos extra del frontal al superior.
    Además, el rect superior toma width=data-ancho y height=data-largo del frontal correspondiente.
    """
    rects = [el for el in svg.getElementsByTagName('*') if el.tagName.lower().endswith('rect')]
    # Buscar el primer frontal con ese color
    rect_frontal = None
    for r in rects:
        rid = (r.getAttribute('id') or '').strip().lower()
        if 'superior' not in rid and (r.getAttribute('fill') or '').lower() == color:
            rect_frontal = r
            break
    if not rect_frontal:
        #print(f"[ERROR] No se encontró rect frontal con fill={color}")
        return
    # Buscar el rectángulo superior con ese color
    rect_superior = None
    for r in rects:
        rid = (r.getAttribute('id') or '').strip().lower()
        if 'superior' in rid and (r.getAttribute('fill') or '').lower() == color:
            rect_superior = r
            break
    if not rect_superior:
        #print(f"[ERROR] No se encontró rectángulo superior con fill={color}.")
        return
    # Grupo de todos los rects con ese color
    grupo = [r for r in rects if (r.getAttribute('fill') or '').lower() == color]
    if not grupo:
        #print(f"[ERROR] No se encontraron rects con fill={color}")
        return
    min_x = min(float(r.getAttribute('x')) for r in grupo)
    max_x = max(float(r.getAttribute('x')) + float(r.getAttribute('width')) for r in grupo)
    ancho_total = max_x - min_x
    #print(f"[INFO] Alineando {len(grupo)} rects de color {color} a x={min_x}, ancho total={ancho_total}")
    # Mover todos a min_x
    for r in grupo:
        old_x = r.getAttribute('x')
        r.setAttribute('x', str(min_x))
        #print(f"[OK] Rect id={r.getAttribute('id')} x: {old_x} -> {min_x}")
    # Ajustar ancho solo del rect 'superior'
    old_w = rect_superior.getAttribute('width')
    rect_superior.setAttribute('width', str(ancho_total))
    #print(f"[OK] Rect superior id={rect_superior.getAttribute('id')} width: {old_w} -> {ancho_total}")
    # Copiar campos extra del frontal al superior
    for campo in ['data-id', 'data-orientacion', 'data-largo', 'data-pies', 'data-ancho', 'data-profundidad', 'fill']:
        valor = rect_frontal.getAttribute(campo)
        if valor:
            rect_superior.setAttribute(campo, valor)
    # NUEVO: Setear width y height del superior a data-ancho y data-profundidad del frontal
    data_ancho = rect_frontal.getAttribute('data-ancho')
    data_largo = rect_frontal.getAttribute('data-profundidad')
    if data_ancho:
        old_width = rect_superior.getAttribute('width')
        rect_superior.setAttribute('width', data_ancho)
        #print(f"[CAMBIO] Rect superior id={rect_superior.getAttribute('id')} width: {old_width} -> {data_ancho} (data-ancho del frontal)")
    if data_largo:
        old_height = rect_superior.getAttribute('height')
        rect_superior.setAttribute('height', data_largo)
        #print(f"[CAMBIO] Rect superior id={rect_superior.getAttribute('id')} height: {old_height} -> {data_largo} (data-largo del frontal)")
    #print(f"[OK] Campos extra copiados del frontal id={rect_frontal.getAttribute('id')} al superior id={rect_superior.getAttribute('id')}")
def get_input_output_svg():
    if len(sys.argv) > 2:
        input_svg = sys.argv[1]
        output_svg = sys.argv[2]
    else:
        input_svg = INPUT_SVG
        output_svg = OUTPUT_SVG
    return input_svg, output_svg

def recalcular_rects(svg, nueva_proporcion):
    """
    Reescala los <rect> del SVG usando la nueva proporción, ordenando por cercanía a (0,0) usando get_rects_ordenados_por_cercania_cero.
    Al terminar, mueve la pieza más cercana al (0,0) a la posición (300, 300).
    """
    rects = [el for el in svg.getElementsByTagName('*') if el.tagName.lower().endswith('rect')]
    if not rects:
        print("[INFO] No se encontraron <rect> en el SVG.")
        return
    # Usar la función centralizada para obtener el orden por cercanía a (0,0)
    orden_cercania_cero = get_rects_ordenados_por_cercania_cero(svg)
    # Crear un diccionario de rects por id para acceso rápido
    rects_dict = {rect.getAttribute('id') or '': rect for rect in rects}
    # Leer la primera posición del orden (la pieza más cercana al cero)
    if orden_cercania_cero:
        primer_id = orden_cercania_cero[0]
        primer_rect = rects_dict.get(primer_id)
        # Ejemplo: print(f"[DEBUG] Pieza más cercana al cero: {primer_id} -> {primer_rect}")
    # Iterar sobre los rects en el orden de cercanía a (0,0)
    for rect_id in orden_cercania_cero:
        rect = rects_dict.get(rect_id)
        if rect is None:
            continue
        rect_id_lower = rect_id.lower()
        data_largo = rect.getAttribute('data-largo')
        data_ancho = rect.getAttribute('data-ancho')
        data_orientacion = rect.getAttribute('data-orientacion')
        if not data_largo or not data_ancho or not data_orientacion:
            continue
        try:
            largo = float(data_largo)
            ancho = float(data_ancho)
        except ValueError:
            continue
        # Obtener valores iniciales
        x = float(rect.getAttribute('x'))
        y = float(rect.getAttribute('y'))
        w = float(rect.getAttribute('width'))
        h = float(rect.getAttribute('height'))
        # Asignar dimensiones en pulgadas
        if data_orientacion == 'horizontal':
            new_w = largo
            new_h = ancho
            new_x = x
            new_y = y
        elif data_orientacion == 'vertical':
            new_w = ancho
            new_h = largo
            new_x = x
            new_y = y
        else:
            new_w = w
            new_h = h
            new_x = x
            new_y = y
        rect.setAttribute('width', format(new_w, '.10f').rstrip('0').rstrip('.') if '.' in format(new_w, '.10f') else str(new_w))
        rect.setAttribute('height', format(new_h, '.10f').rstrip('0').rstrip('.') if '.' in format(new_h, '.10f') else str(new_h))
    # # Mover la pieza más cercana al (0,0) a (300, 300)
    # if orden_cercania_cero:
    #     primer_id = orden_cercania_cero[0]
    #     primer_rect = rects_dict.get(primer_id)
    #     if primer_rect is not None:
    #         primer_rect.setAttribute('x', '300')
    #         primer_rect.setAttribute('y', '300')
    #         # print(f"[INFO] Pieza '{primer_id}' movida a (300, 300)")

def distancia_esquina_mas_cercana(x, y, w, h):
    esquinas = [
        (x, y),
        (x + w, y),
        (x, y + h),
        (x + w, y + h)
    ]
    return min((ex**2 + ey**2) ** 0.5 for ex, ey in esquinas)

def listar_rects_adyacentes_structured(svg, tolerancia=0.2, rects_ordenados=None, rects_info=None, originales_rects=None, distancias_ordenadas=None):
    """
    Devuelve una lista de diccionarios con pares adyacentes de rectángulos y detalles de contacto.
    Ordena los rectángulos de referencia según dic_distancias.
    Imprime los puntos y lados usados en la búsqueda de adyacencias para depuración detallada.
    """
    if rects_ordenados is not None:
        # Convertir rects_ordenados (IDs) en elementos XML
        rects_dict = {el.getAttribute('id'): el for el in svg.getElementsByTagName('*') if el.tagName.lower().endswith('rect')}
        rects = [rects_dict[rect_id] for rect_id in rects_ordenados if rect_id in rects_dict]
    else:
        rects = [el for el in svg.getElementsByTagName('*') if el.tagName.lower().endswith('rect')]

    info_rects = []
    for rect in rects:
        rect_id = rect.getAttribute('id') or ''
        if 'superior' in rect_id.lower():
            continue  # Skip rects with 'superior' in id
        try:
            if originales_rects and rect_id in originales_rects:
                x = originales_rects[rect_id]['x']
                y = originales_rects[rect_id]['y']
                w = originales_rects[rect_id]['w']
                h = originales_rects[rect_id]['h']
            else:
                x = float(rect.getAttribute('x'))
                y = float(rect.getAttribute('y'))
                w = float(rect.getAttribute('width'))
                h = float(rect.getAttribute('height'))
            corners = [
                (x, y),
                (x + w, y),
                (x, y + h),
                (x + w, y + h)
            ]
            info_rects.append({'id': rect_id, 'x': x, 'y': y, 'w': w, 'h': h, 'corners': corners})
        except Exception:
            continue

    adyacencias = []
    # Solo buscar adyacencias para el primer rectángulo de la lista
    for i, r1 in enumerate(info_rects):
        #if i > 0:
        #    break  # Solo el primero
        x1, y1, w1, h1 = r1['x'], r1['y'], r1['w'], r1['h']
        esquinas1 = [
            (x1, y1),
            (x1 + w1, y1),
            (x1, y1 + h1),
            (x1 + w1, y1 + h1)
        ]
        #nombres = ['topleft', 'topright', 'bottomleft', 'bottomright', 'top-left', 'top-right', 'bottom-left', 'bottom-right']
        nombres = ['top-left', 'top-right', 'bottom-left', 'bottom-right']
        # print(f"[DEBUG] Buscando adyacencias para ref: {r1['id']} (x={x1}, y={y1}, w={w1}, h={h1})")
        # print(f"        Esquinas: {esquinas1}")
        for j, r2 in enumerate(info_rects):
            if i >= j:
                continue
            if 'superior' in r2['id'].lower():
                continue
            x2, y2, w2, h2 = r2['x'], r2['y'], r2['w'], r2['h']
            esquinas2 = [
                (x2, y2),
                (x2 + w2, y2),
                (x2, y2 + h2),
                (x2 + w2, y2 + h2)
            ]
            # print(f"    Candidato: {r2['id']} (x={x2}, y={y2}, w={w2}, h={h2})")
            # print(f"        Esquinas: {esquinas2}")
            # input('Presiona ENTER para continuar con este candidato...')
            def punto_sobre_segmento(px, py, xA, yA, xB, yB, tolerancia=1e-6):
                # Criterio clásico: punto sobre segmento
                if abs(xA - xB) < tolerancia:
                    # Vertical
                    if abs(px - xA) <= tolerancia and min(yA, yB) - tolerancia <= py <= max(yA, yB) + tolerancia:
                        return True
                    # Nuevo criterio: x coincide y y está dentro del rango
                    if abs(px - xA) <= tolerancia and min(yA, yB) <= py <= max(yA, yB):
                        return True
                if abs(yA - yB) < tolerancia:
                    # Horizontal
                    if abs(py - yA) <= tolerancia and min(xA, xB) - tolerancia <= px <= max(xA, xB) + tolerancia:
                        return True
                    # Nuevo criterio: y coincide y x está dentro del rango
                    if abs(py - yA) <= tolerancia and min(xA, xB) <= px <= max(xA, xB):
                        return True
                # Nuevo criterio: si x está dentro del rango y y coincide, o viceversa
                if min(xA, xB) <= px <= max(xA, xB) and abs(py - yA) <= tolerancia:
                    return True
                if min(yA, yB) <= py <= max(yA, yB) and abs(px - xA) <= tolerancia:
                    return True
                return False
            lados2 = [
                (esquinas2[0], esquinas2[1]),  # top
                (esquinas2[1], esquinas2[3]),  # right
                (esquinas2[3], esquinas2[2]),  # bottom
                (esquinas2[2], esquinas2[0])   # left
            ]
            nombres_lados = ['top', 'right', 'bottom', 'left']
            puntos_coinciden = []
            for idx, (px, py) in enumerate(esquinas1):
                nombre_esquina = nombres[idx]
                for lidx, ((xA, yA), (xB, yB)) in enumerate(lados2):
                    #print(f"        Probar esquina {nombre_esquina} {px, py} con lado {nombres_lados[lidx]} {((xA, yA), (xB, yB))}")
                    if punto_sobre_segmento(px, py, xA, yA, xB, yB, tolerancia):
                        dist_extremo = ((px - xA)**2 + (py - yA)**2) ** 0.5
                        largo_lado = ((xB - xA)**2 + (yB - yA)**2) ** 0.5
                        proporcion = dist_extremo / largo_lado if largo_lado > 0 else 0.0
                        puntos_coinciden.append({
                            'esquina': nombre_esquina,
                            'rect': r1['id'],
                            'punto': (px, py),
                            'lado': nombres_lados[lidx],
                            'adyacente': r2['id'],
                            'dist_extremo': dist_extremo,
                            'proporcion': proporcion
                        })
            lados1 = [
                (esquinas1[0], esquinas1[1]),  # top
                (esquinas1[1], esquinas1[3]),  # right
                (esquinas1[3], esquinas1[2]),  # bottom
                (esquinas1[2], esquinas1[0])   # left
            ]
            for idx, (px, py) in enumerate(esquinas2):
                nombre_esquina = nombres[idx]
                for lidx, ((xA, yA), (xB, yB)) in enumerate(lados1):
                    #print(f"        Probar esquina {nombre_esquina} {px, py} con lado {nombres_lados[lidx]} {((xA, yA), (xB, yB))}")
                    if punto_sobre_segmento(px, py, xA, yA, xB, yB, tolerancia):
                        dist_extremo = ((px - xA)**2 + (py - yA)**2) ** 0.5
                        largo_lado = ((xB - xA)**2 + (yB - yA)**2) ** 0.5
                        proporcion = dist_extremo / largo_lado if largo_lado > 0 else 0.0
                        puntos_coinciden.append({
                            'esquina': nombre_esquina,
                            'rect': r2['id'],
                            'punto': (px, py),
                            'lado': nombres_lados[lidx],
                            'adyacente': r1['id'],
                            'dist_extremo': dist_extremo,
                            'proporcion': proporcion
                        })
            if puntos_coinciden:
                #print(f"        -> Contactos encontrados: {puntos_coinciden}")
                adyacencias.append({
                    'ref': r1,
                    'ady': r2,
                    'contactos': puntos_coinciden
                })
            #else:
                #print(f"        -> Sin contactos adyacentes entre {r1['id']} y {r2['id']}")
    # Ordenar adyacencias exactamente en el mismo orden que rects_ordenados
    if rects_ordenados is not None:
        # Agrupar adyacencias por ref
        ady_por_ref = {}
        for ady in adyacencias:
            ref_id = ady['ref']['id']
            if ref_id not in ady_por_ref:
                ady_por_ref[ref_id] = []
            ady_por_ref[ref_id].append(ady)
        # Construir la lista final en el orden de rects_ordenados, asegurando correspondencia 1 a 1
        adyacencias_ordenadas = []
        for rid in rects_ordenados:
            if rid in ady_por_ref and ady_por_ref[rid]:
                adyacencias_ordenadas.append(ady_por_ref[rid][0])  # Primer adyacente por ref
            else:
                # Si no hay adyacente, se agrega None o un diccionario vacío para mantener el orden
                adyacencias_ordenadas.append(None)
        #print('[DEBUG] Orden esperado de referencias:', rects_ordenados)
        #print('[DEBUG] Orden real de referencias en adyacencias:', [a['ref']['id'] if a else None for a in adyacencias_ordenadas])
        return adyacencias_ordenadas
    elif distancias_ordenadas and isinstance(distancias_ordenadas, dict):
        adyacencias.sort(key=lambda a: distancias_ordenadas.get(a['ref']['id'], {}).get('distancia', float('inf')))
    else:
        print("[ERROR] distancias_ordenadas debe ser un diccionario o rects_ordenados debe estar definido.")
    return adyacencias


def get_rects_ordenados_por_orientacion_y_distancia(svg, referencia_id, adyacencias_dict):
    referencia = next((r for r in svg.getElementsByTagName('*') if r.getAttribute('id') == referencia_id), None)
    if referencia is None:
        return []
    x_ref = float(referencia.getAttribute('x'))
    y_ref = float(referencia.getAttribute('y'))
    w_ref = float(referencia.getAttribute('width'))
    h_ref = float(referencia.getAttribute('height'))
    orientacion_ref = 'horizontal' if w_ref > h_ref else 'vertical'
    distancias = []
    for rect in svg.getElementsByTagName('*'):
        if not rect.tagName.lower().endswith('rect'):
            continue
        rect_id = rect.getAttribute('id') or ''
        if 'superior' in rect_id.lower():
            continue  # Ignorar rectángulos superiores
        try:
            x = float(rect.getAttribute('x'))
            y = float(rect.getAttribute('y'))
            w = float(rect.getAttribute('width'))
            h = float(rect.getAttribute('height'))
            dist = ((x - x_ref) ** 2 + (y - y_ref) ** 2) ** 0.5
            distancias.append((rect_id, dist))
        except Exception:
            continue
    distancias.sort(key=lambda t: t[1])
    ordenados = [tid[0] for tid in distancias]
    # Colocar el referente primero
    if referencia_id in ordenados:
        ordenados.remove(referencia_id)
        ordenados.insert(0, referencia_id)
    return ordenados


def get_rects_ordenados_por_cercania_cero(svg):
    """
    Devuelve una lista de IDs de <rect> ordenados por la distancia de su esquina más cercana al (0,0).
    """
    rects = [el for el in svg.getElementsByTagName('*') if el.tagName.lower().endswith('rect')]
    rects_info = []
    for rect in rects:
        rect_id = rect.getAttribute('id') or ''
        x = float(rect.getAttribute('x'))
        y = float(rect.getAttribute('y'))
        w = float(rect.getAttribute('width'))
        h = float(rect.getAttribute('height'))
        dist = distancia_esquina_mas_cercana(x, y, w, h)
        rects_info.append({'id': rect_id, 'dist': dist})
    rects_info.sort(key=lambda r: r['dist'])
    return [r['id'] for r in rects_info]


    return rect_ady
def obtener_distancias_rects(svg):
    """
    Devuelve un diccionario ordenado con las distancias de cada rectángulo a su esquina más cercana.
    """
    rects_ordenados = get_rects_ordenados_por_cercania_cero(svg)  # Usar la función para obtener rects ordenados
    rects = [el for el in svg.getElementsByTagName('*') if el.tagName.lower().endswith('rect')]
    rects_dict = {rect.getAttribute('id') or '': rect for rect in rects}  # Crear un diccionario para acceso rápido

    distancias = {}
    for rect_id in rects_ordenados:
        rect = rects_dict.get(rect_id)
        if rect is None:
            continue
        try:
            x = float(rect.getAttribute('x'))
            y = float(rect.getAttribute('y'))
            w = float(rect.getAttribute('width'))
            h = float(rect.getAttribute('height'))
            distancia = distancia_esquina_mas_cercana(x, y, w, h)
            distancias[rect_id] = {
                'rect': rect,
                'distancia': distancia
            }
        except ValueError:
            continue

    #print(f"[DEBUG] Distancias calculadas: {distancias}")
    return distancias

def mover_rect_a_posicion(svg, rect_id, x, y):
    """
    Mueve el rectángulo con el id dado a la posición (x, y).
    """
    rects = [el for el in svg.getElementsByTagName('*') if el.tagName.lower().endswith('rect')]
    for rect in rects:
        if (rect.getAttribute('id') or '') == rect_id:
            rect.setAttribute('x', str(x))
            rect.setAttribute('y', str(y))
            return True
    return False



def modificar_adyacencias(dic_adyacencias, dic_svg_inicial, dic_svg_modificado):
    """
    Modifica las adyacencias según los datos iniciales y modificados.
    """
    if "adyacencias" not in dic_adyacencias or not dic_adyacencias["adyacencias"]:
        print("[ERROR] No se encontraron adyacencias en dic_adyacencias.")
        return None

    primer_par = dic_adyacencias["adyacencias"][0]
    if primer_par is None:
        print("[ADVERTENCIA] El primer par de adyacencias es None. No hay adyacente para el primer rectángulo de referencia.")
        # Imprimir datos del primer rectángulo de referencia para depuración
        if "svg" in dic_svg_inicial:
            ref_id = None
            # Buscar el primer id de referencia en la lista de distancias si existe
            if "distancias" in dic_distancias and dic_distancias["distancias"]:
                ref_id = list(dic_distancias["distancias"].keys())[0]
            if ref_id:
                ref_rect = next((el for el in dic_svg_inicial["svg"].getElementsByTagName('*') if el.getAttribute('id') == ref_id), None)
                if ref_rect:
                    x = float(ref_rect.getAttribute('x'))
                    y = float(ref_rect.getAttribute('y'))
                    w = float(ref_rect.getAttribute('width'))
                    h = float(ref_rect.getAttribute('height'))
                    print(f"[DEPURACIÓN] Rectángulo de referencia: {ref_id}")
                    print(f"  x={x}, y={y}, w={w}, h={h}")
                    print(f"  Esquinas: {[(x, y), (x + w, y), (x, y + h), (x + w, y + h)]}")
                    print("[DEPURACIÓN] Rectángulos candidatos a adyacentes:")
                    for el in dic_svg_inicial["svg"].getElementsByTagName('*'):
                        if el.tagName.lower().endswith('rect') and el.getAttribute('id') != ref_id:
                            x2 = float(el.getAttribute('x'))
                            y2 = float(el.getAttribute('y'))
                            w2 = float(el.getAttribute('width'))
                            h2 = float(el.getAttribute('height'))
                            print(f"    id={el.getAttribute('id')}: x={x2}, y={y2}, w={w2}, h={h2}, esquinas={[(x2, y2), (x2 + w2, y2), (x2, y2 + h2), (x2 + w2, y2 + h2)]}")
            return None
    # Definir rect_ref y rect_ady correctamente si primer_par no es None
    rect_ref = primer_par["ref"]
    rect_ady = primer_par["ady"]
    
    # === Mostrar datos del SVG inicial ===

    inicial_ref = next((el for el in dic_svg_inicial["svg"].getElementsByTagName('*') if el.getAttribute('id') == rect_ref['id']), None)
    inicial_ady = next((el for el in dic_svg_inicial["svg"].getElementsByTagName('*') if el.getAttribute('id') == rect_ady['id']), None)
    

    nombres = ['top-left', 'top-right', 'bottom-left', 'bottom-right']
    x1, y1, w1, h1 = rect_ref['x'], rect_ref['y'], rect_ref['w'], rect_ref['h']
    x2, y2, w2, h2 = rect_ady['x'], rect_ady['y'], rect_ady['w'], rect_ady['h']
    esquinas1 = [
        (x1, y1), (x1 + w1, y1), (x1, y1 + h1), (x1 + w1, y1 + h1)
    ]
    esquinas2 = [
        (x2, y2), (x2 + w2, y2), (x2, y2 + h2), (x2 + w2, y2 + h2)
    ]

    dx = x1 - x2
    dy = y1 - y2
    print(f"\033[1;33m[XY] === DATOS ANTES DEL AJUSTE ===\033[0m")
    print(f"[REFERENCIA] {rect_ref['id']}: x={x1:.6f}, y={y1:.6f}, w={w1:.6f}, h={h1:.6f}")
    for n, (ex, ey) in zip(nombres, esquinas1):
        print(f"  {n}: ({ex:.6f}, {ey:.6f})")
    print(f"[ADYACENTE] {rect_ady['id']}: x={x2:.6f}, y={rect_ady['y']:.6f}, w={w2:.6f}, h={h2:.6f}")
    for n, (ex, ey) in zip(nombres, esquinas2):
        print(f"  {n}: ({ex:.6f}, {ey:.6f})")
    
    # === Mostrar datos del SVG modificado ===
    
    modificado_ref = next((el for el in dic_svg_modificado["svg"].getElementsByTagName('*') if el.getAttribute('id') == rect_ref['id']), None)
    modificado_ady = next((el for el in dic_svg_modificado["svg"].getElementsByTagName('*') if el.getAttribute('id') == rect_ady['id']), None)
    
    
    if modificado_ref is not None and modificado_ady is not None:
        mx1 = float(modificado_ref.getAttribute('x'))
        my1 = float(modificado_ref.getAttribute('y'))
        mw1 = float(modificado_ref.getAttribute('width'))
        mh1 = float(modificado_ref.getAttribute('height'))
        mx2 = float(modificado_ady.getAttribute('x'))
        my2 = float(modificado_ady.getAttribute('y'))
        mw2 = float(modificado_ady.getAttribute('width'))
        mh2 = float(modificado_ady.getAttribute('height'))
        mod_esquinas1 = [
            (mx1, my1), (mx1 + mw1, my1), (mx1, my1 + mh1), (mx1 + mw1, my1 + mh1)
        ]
        mod_esquinas2 = [
            (mx2, my2), (mx2 + mw2, my2), (mx2, my2 + mh2), (mx2 + mw2, my2 + mh2)
        ]
        print(f"\n[MODIFICADO] {rect_ref['id']}: x={mx1:.6f}, y={my1:.6f}, w={mw1:.6f}, h={mh1:.6f}")
        for n, (ex, ey) in zip(nombres, mod_esquinas1):
            print(f"  {n}: ({ex:.6f}, {ey:.6f})")
        print(f"[MODIFICADO] {rect_ady['id']}: x={mx2:.6f}, y={my2:.6f}, w={mw2:.6f}, h={mh2:.6f}")
        for n, (ex, ey) in zip(nombres, mod_esquinas2):
            print(f"  {n}: ({ex:.6f}, {ey:.6f})")
    else:
        print("[ADVERTENCIA] No se encontraron los rectángulos en el SVG modificado.")
  # === Imprimir cuál es el punto adyacente ===
        # Buscar el contacto real en la estructura de adyacencias
    if 'contactos' in primer_par and primer_par['contactos']:
        print("\n[PUNTO(S) DE CONTACTO ADYACENTE SEGÚN ANÁLISIS DE ADYACENCIA]")
        for contacto in primer_par['contactos']:
            lado_ref = contacto.get('lado', '?')
            proporcion = contacto.get('proporcion', None)
            lado_ady = contacto.get('lado', '?')
            # Guardar solo el valor en variables separadas
            proporcion_por_lado = {lado_ref: proporcion, lado_ady: proporcion}
            print(f"  [proporcion_por_lado: {proporcion_por_lado}]")
    else:
        print("[INFO] No se encontraron puntos de contacto adyacente en la estructura de adyacencias.")
    

    # === Ajuste automático usando el punto de contacto adyacente ===
    if (
        modificado_ref is not None and modificado_ady is not None
        and 'contactos' in primer_par and primer_par['contactos']
    ):
        # Tomar el primer contacto relevante
        contacto = primer_par['contactos'][0]
        esquina_ref = contacto['esquina']
        # Si el contacto es sobre el adyacente, usar ese nombre de esquina
        esquina_ady = contacto['esquina'] if contacto['rect'] == rect_ady['id'] else None
        if not esquina_ady:
            # Buscar el otro contacto si existe
            for c in primer_par['contactos']:
                if c['rect'] == rect_ady['id']:
                    esquina_ady = c['esquina']
                    break

        # Buscar la esquina específica del rectángulo adyacente en los contactos
        esquina_ady = None
        for c in primer_par['contactos']:
            if c['rect'] == rect_ady['id']:
                esquina_ady = c['esquina']
                break
        # Nombres y normalización
        nombres = ['top-left', 'top-right', 'bottom-left', 'bottom-right']
        nombres_norm = [n.replace('-', '').lower() for n in nombres]
        esquina_ref_norm = esquina_ref.replace('-', '').lower()
        idx_ref = nombres_norm.index(esquina_ref_norm)
        # Esquina de referencia en SVG inicial y modificado
        inicial_esquinas1 = [
            (x1, y1), (x1 + w1, y1), (x1, y1 + h1), (x1 + w1, y1 + h1)
        ]
        esquina_ref_inicial = inicial_esquinas1[idx_ref]
        esquina_ref_mod = mod_esquinas1[idx_ref]
        print(f"\n[AJUSTE AUTOMÁTICO] Esquina de referencia '{esquina_ref}' en inicial: {esquina_ref_inicial}")
        print(f"[AJUSTE AUTOMÁTICO] Esquina de referencia '{esquina_ref}' en modificado: {esquina_ref_mod}")
        # Calcular el delta de movimiento de la esquina de referencia
        delta_x = esquina_ref_mod[0] - esquina_ref_inicial[0]
        delta_y = esquina_ref_mod[1] - esquina_ref_inicial[1]
        print(f"[AJUSTE AUTOMÁTICO] Delta aplicado a la esquina de referencia: Δx={delta_x:.6f}, Δy={delta_y:.6f}")
        # Ahora aplicar ese delta a la esquina correspondiente del adyacente
        if esquina_ady:
            esquina_ady_norm = esquina_ady.replace('-', '').lower()
            idx_ady = nombres_norm.index(esquina_ady_norm)
            esquina_ady_mod = mod_esquinas2[idx_ady]
            print(f"[AJUSTE AUTOMÁTICO] Esquina del adyacente '{esquina_ady}' en modificado antes de mover: {esquina_ady_mod}")

            # Usar el lado correcto para la proporción
            proporcion_por_lado = {lado_ref: proporcion}
            proporcion_lado = proporcion_por_lado.get(lado_ref, 1.0)
            print(f"[AJUSTE AUTOMÁTICO] Usando proporción de lado '{lado_ref}': {proporcion_lado}")

            objetivo_x = esquina_ady_mod[0] + delta_x * 0.7145 #proporcion_lado
            objetivo_y = esquina_ady_mod[1] + delta_y
            print(f"[AJUSTE AUTOMÁTICO] Objetivo para esquina del adyacente '{esquina_ady}': ({objetivo_x:.6f}, {objetivo_y:.6f})")
            # Ajustar x/y del rectángulo para que esa esquina quede en la posición objetivo
            if esquina_ady == 'top-left':
                nuevo_x = objetivo_x
                nuevo_y = objetivo_y
                print(f"[AJUSTE AUTOMÁTICO] Moviendo adyacente '{rect_ady['id']}' a la esquina superior izquierda.")
            elif esquina_ady == 'top-right':
                nuevo_x = objetivo_x - mw2
                nuevo_y = objetivo_y
            elif esquina_ady == 'bottom-left':
                nuevo_x = objetivo_x
                nuevo_y = objetivo_y - mh2
            elif esquina_ady == 'bottom-right':
                nuevo_x = objetivo_x - mw2
                nuevo_y = objetivo_y - mh2
            else:
                nuevo_x, nuevo_y = mx2, my2  # fallback

            mover_rect_a_posicion(dic_svg_modificado["svg"], rect_ady['id'], nuevo_x, nuevo_y)
            print(f"[RESULTADO] Adyacente '{rect_ady['id']}' movido a x={nuevo_x:.6f}, y={nuevo_y:.6f}")
        else:
            print("[AJUSTE AUTOMÁTICO] No se encontró la esquina del adyacente para aplicar el delta.")
    
    return modificado_ady

def calcular_proporcionalidad_top_plate(svg):
    """
    Busca el <rect> cuyo id contenga 'top_plate' y calcula la proporcionalidad como data-largo / width.
    Devuelve el valor calculado o None si no se encuentra.
    """
    rects = [el for el in svg.getElementsByTagName('*') if el.tagName.lower().endswith('rect')]
    for rect in rects:
        rid = (rect.getAttribute('id') or '').lower()
        if 'top_plate' in rid:
            data_largo = rect.getAttribute('data-largo')
            width = rect.getAttribute('width')
            try:
                data_largo_f = float(data_largo)
                width_f = float(width)
                if width_f != 0:
                    proporcionalidad = data_largo_f / width_f
                    #print(f"[PROC] Proporcionalidad top_plate: data-largo={data_largo_f} / width={width_f} = {proporcionalidad}")
                    return proporcionalidad
                #else:
                    #print(f"[PROC] Warning: width=0 en top_plate id={rid}")
            except Exception as e:
                #print(f"[PROC] Error calculando proporcionalidad en top_plate id={rid}: {e}")
                continue
    #print("[PROC] No se encontró rect con id que contenga 'top_plate' para calcular proporcionalidad.")
    return None

def ajuste_proporcional(svg, factor=0.7151):
    """
    Multiplica x e y de todos los <rect> por el factor dado.
    """
    rects = [el for el in svg.getElementsByTagName('*') if el.tagName.lower().endswith('rect')]
    for rect in rects:
        try:
            x = float(rect.getAttribute('x'))
            y = float(rect.getAttribute('y'))
            rect.setAttribute('x', str(x * factor))
            rect.setAttribute('y', str(y * factor))
        except Exception:
            continue
def reescalar_sheathing_rects(svg):
    """
    Reescala los <rect> de sheathing usando data-largo como height y data-ancho como width.
    """
    rects = [el for el in svg.getElementsByTagName('*') if el.tagName.lower().endswith('rect')]
    for rect in rects:
        rect_id = rect.getAttribute('id') or ''
        if 'sheathing' not in rect_id.lower():
            continue
        data_largo = rect.getAttribute('data-largo')
        data_ancho = rect.getAttribute('data-ancho')
        if not data_largo or not data_ancho:
            continue
        try:
            largo = float(data_largo)
            ancho = float(data_ancho)
        except ValueError:
            continue
        rect.setAttribute('width', str(ancho))
        rect.setAttribute('height', str(largo))
        # Opcional: puedes imprimir para depuración
        #print(f"[SHEATHING-RESCALE] id={rect_id} width={ancho} height={largo}")

def extremos_cercanos(p1, p2, ajuste):
    """Devuelve True si ambos extremos de dos lados están a menos de ajuste de distancia (en cualquier orden)."""
    def dist(a, b):
        return ((a[0]-b[0])**2 + (a[1]-b[1])**2) ** 0.5
    return (
        dist(p1[0], p2[0]) < ajuste and dist(p1[1], p2[1]) < ajuste
    ) or (
        dist(p1[0], p2[1]) < ajuste and dist(p1[1], p2[0]) < ajuste
    )

def lados_adyacentes(lado1, lado2, ajuste):
    (x1a, y1a), (x1b, y1b) = lado1
    (x2a, y2a), (x2b, y2b) = lado2
    # Ambos horizontales
    if abs(y1a - y1b) < ajuste and abs(y2a - y2b) < ajuste:
        if abs(y1a - y2a) < ajuste:
            min1, max1 = sorted([x1a, x1b])
            min2, max2 = sorted([x2a, x2b])
            return max(min1, min2) <= min(max1, max2) + ajuste
    # Ambos verticales
    elif abs(x1a - x1b) < ajuste and abs(x2a - x2b) < ajuste:
        if abs(x1a - x2a) < ajuste:
            min1, max1 = sorted([y1a, y1b])
            min2, max2 = sorted([y2a, y2b])
            return max(min1, min2) <= min(max1, max2) + ajuste
    # Un lado horizontal y otro vertical: verificar si se tocan en un punto
    else:
        for p1 in [lado1[0], lado1[1]]:
            for p2 in [lado2[0], lado2[1]]:
                if abs(p1[0] - p2[0]) < ajuste and abs(p1[1] - p2[1]) < ajuste:
                    return True
    return False

def ajustar_adyacencias(AJUSTE, dic_distancias, dic_svg_modificado):
    """
    Busca pares de rectángulos cuyos lados son adyacentes (solapamiento o contacto en extremos) dentro de la tolerancia.
    Mueve la pieza más lejana para que su lado coincida con el de la más cercana.
    """
    MIN_DIFF = 1e-4  # Ajusta según la precisión que desees
    svg = dic_svg_modificado["svg"]
    rects = [el for el in svg.getElementsByTagName('*') if el.tagName.lower().endswith('rect')]
    for i, r1 in enumerate(rects):
        x1 = float(r1.getAttribute('x'))
        y1 = float(r1.getAttribute('y'))
        w1 = float(r1.getAttribute('width'))
        h1 = float(r1.getAttribute('height'))
        esquinas1 = [
            (x1, y1),
            (x1 + w1, y1),
            (x1 + w1, y1 + h1),
            (x1, y1 + h1)
        ]
        lados1 = [
            (esquinas1[0], esquinas1[1]),  # top
            (esquinas1[1], esquinas1[2]),  # right
            (esquinas1[2], esquinas1[3]),  # bottom
            (esquinas1[3], esquinas1[0])   # left
        ]
        for j, r2 in enumerate(rects):
            if i == j:
                continue
            x2 = float(r2.getAttribute('x'))
            y2 = float(r2.getAttribute('y'))
            w2 = float(r2.getAttribute('width'))
            h2 = float(r2.getAttribute('height'))
            esquinas2 = [
                (x2, y2),
                (x2 + w2, y2),
                (x2 + w2, y2 + h2),
                (x2, y2 + h2)
            ]
            lados2 = [
                (esquinas2[0], esquinas2[1]),  # top
                (esquinas2[1], esquinas2[2]),  # right
                (esquinas2[2], esquinas2[3]),  # bottom
                (esquinas2[3], esquinas2[0])   # left
            ]
            for idx1, lado1 in enumerate(lados1):
                for idx2, lado2 in enumerate(lados2):
                    if lados_adyacentes(lado1, lado2, AJUSTE):
                        # Decide which rect is fixed and which is to move
                        dist1 = dic_distancias["distancias"].get(r1.getAttribute('id'), {}).get('distancia', float('inf'))
                        dist2 = dic_distancias["distancias"].get(r2.getAttribute('id'), {}).get('distancia', float('inf'))
                        if dist1 <= dist2:
                            fijo, mover = r1, r2
                            x_m, y_m = float(mover.getAttribute('x')), float(mover.getAttribute('y'))
                            esquinas_f_print = esquinas1
                            esquinas_m_print = esquinas2
                            lado_fijo = lado1
                            lado_mover = lado2
                        else:
                            fijo, mover = r2, r1
                            x_m, y_m = float(mover.getAttribute('x')), float(mover.getAttribute('y'))
                            esquinas_f_print = esquinas2
                            esquinas_m_print = esquinas1
                            lado_fijo = lado2
                            lado_mover = lado1

                        dx = lado_fijo[0][0] - lado_mover[0][0]
                        dy = lado_fijo[0][1] - lado_mover[0][1]

                        # Solo imprimir y mover si el delta es significativo
                        if abs(dx) > MIN_DIFF or abs(dy) > MIN_DIFF:
                            print("\n[DEBUG-ADYACENCIA]")
                            print(f"  Pieza a mover: {mover.getAttribute('id')}")
                            print(f"    Esquinas: {esquinas_m_print}")
                            print(f"  Pieza fija: {fijo.getAttribute('id')}")
                            print(f"    Esquinas: {esquinas_f_print}")
                            print(f"  Lado a mover: {lado_mover}")
                            print(f"  Lado fijo: {lado_fijo}")
                            print(f"  Extremos que se tocan: {lado_mover[0]} <-> {lado_fijo[0]}, {lado_mover[1]} <-> {lado_fijo[1]}")
                            print(f"  Delta aplicado: dx={dx:.8f}, dy={dy:.8f}")
                            print(f"  Diferencia en extremos lado_mover: {lado_mover[0]} vs {lado_fijo[0]}, {lado_mover[1]} vs {lado_fijo[1]}")
                            print(f"[AJUSTE-ADYACENCIA] Movido {mover.getAttribute('id')} para alinear con {fijo.getAttribute('id')} (lado alineado por extremos)")

                            mover.setAttribute('x', str(x_m + dx))
                            mover.setAttribute('y', str(y_m + dy))
                            break
                else:
                    continue
                break

# --- NUEVO: Mover la pieza más cercana a (0,0) a (100,100) y trasladar todas las demás ---
def mover_pieza_cercana_cero_a_100_100(dic_distancias, dic_svg_modificado):
    """
    Mueve la pieza más cercana a (0,0) a (100,100) y traslada todas las demás por el mismo delta.
    """
    distancias = dic_distancias["distancias"]
    if not distancias:
        print("[ERROR] No hay distancias calculadas.")
        return
    # Buscar el único rect con 'top_plate' en el id (case-insensitive)
    top_plate_ids = [rid for rid in distancias if 'top_plate' in (rid or '').lower()]
    if not top_plate_ids:
        print("[ERROR] No se encontró ninguna pieza con 'top_plate' en el id para mover a (100,100). Se usará la más cercana a cero.")
        ref_id = next(iter(distancias.keys()))
    elif len(top_plate_ids) == 1:
        ref_id = top_plate_ids[0]
    else:
        print(f"[ADVERTENCIA] Hay más de un Top_Plate, usando el primero: {top_plate_ids}")
        ref_id = top_plate_ids[0]
    # Buscar el Top_Plate en el SVG MODIFICADO para obtener su posición real
    svg = dic_svg_modificado["svg"]
    rects = [el for el in svg.getElementsByTagName('*') if el.tagName.lower().endswith('rect')]
    rect_modificado = None
    for rect in rects:
        if (rect.getAttribute('id') or '') == ref_id:
            rect_modificado = rect
            break
    if rect_modificado is None:
        print(f"[ERROR] No se encontró el rect Top_Plate (id='{ref_id}') en el SVG modificado.")
        return
    try:
        x0 = float(rect_modificado.getAttribute('x'))
        y0 = float(rect_modificado.getAttribute('y'))
        print(f"[INFO] Posición actual del Top_Plate (id='{ref_id}') en SVG modificado: x={x0}, y={y0}")
    except Exception:
        print(f"[ERROR] No se pudo leer x/y de la pieza principal {ref_id} en SVG modificado")
        return
    dx = 100 - x0
    dy = 100 - y0
    print(f"[INFO] Trasladando TODOS los rects (incluido el Top_Plate) por el delta: dx={dx:.3f}, dy={dy:.3f} para que el Top_Plate quede en (100,100)")
    for rect in rects:
        try:
            x = float(rect.getAttribute('x'))
            y = float(rect.getAttribute('y'))
            rect.setAttribute('x', str(x + dx))
            rect.setAttribute('y', str(y + dy))
        except Exception:
            continue
    print(f"[INFO] Todas las piezas trasladadas por el delta (esquina Top_Plate a 100,100). Solo se traslada, nunca se setea directo.")

def proc_calcular_y_aplicar_proporcionalidad(svg):
    """
    Calcula la proporcionalidad del top_plate y la aplica como factor de ajuste global.
    Guarda el valor en la variable global PROPORCIONALIDAD_TOP_PLATE.
    """
    global PROPORCIONALIDAD_TOP_PLATE
    proporcionalidad = calcular_proporcionalidad_top_plate(svg)
    if proporcionalidad is not None:
        PROPORCIONALIDAD_TOP_PLATE = proporcionalidad
        print(f"[proc] Proporcionalidad calculada sobre svg_modificado: {proporcionalidad}")
        ajuste_proporcional(svg, factor=proporcionalidad)
    else:
        PROPORCIONALIDAD_TOP_PLATE = 0.71465
        print("[proc] No se pudo calcular proporcionalidad, usando valor por defecto 0.71465")
        ajuste_proporcional(svg, factor=0.71465)


def generar_svg_solo_frontales(svg_path, output_path=None):
    """
    Genera un SVG solo con las piezas frontales (montantes verticales).
    Para <rect>: incluye las que NO tienen 'rect' ni 'superior' en el id.
    Para <path>: incluye las que son verticales (height > width), determinado
    geometricamente a partir del atributo 'd'.
    El archivo de salida tendrá '_frontal' agregado al nombre.
    """
    from xml.dom import minidom
    import os
    import re

    def _bbox_from_path_d(d):
        """Devuelve (width, height) del bounding box de un path rectangular."""
        nums = list(map(float, re.findall(r'[-+]?[0-9]*\.?[0-9]+', d)))
        if len(nums) < 4:
            return 0, 0
        xs = nums[0::2]
        ys = nums[1::2]
        return max(xs) - min(xs), max(ys) - min(ys)

    # Leer SVG original
    doc = minidom.parse(svg_path)
    svg = doc.getElementsByTagName('svg')[0]

    frontales = []

    # Elementos <rect>: filtrar por id (lógica original)
    for r in svg.getElementsByTagName('rect'):
        rid = (r.getAttribute('id') or '').lower()
        if 'rect' not in rid and 'superior' not in rid:
            frontales.append(r)

    # Elementos <path>: filtrar geométricamente (frontal = pieza vertical, height > width)
    for p in svg.getElementsByTagName('path'):
        d = p.getAttribute('d') or ''
        w, h = _bbox_from_path_d(d)
        if h > w:  # pieza vertical = montante frontal
            frontales.append(p)

    # Crear nuevo documento SVG
    new_doc = minidom.Document()
    new_svg = svg.cloneNode(False)
    new_doc.appendChild(new_svg)

    # Agregar solo los elementos frontales
    for r in frontales:
        new_svg.appendChild(r.cloneNode(True))

    # Definir nombre de salida
    if not output_path:
        base, ext = os.path.splitext(svg_path)
        output_path = f"{base}_frontal{ext}"

    # Guardar el nuevo SVG
    with open(output_path, 'w', encoding='utf-8') as f:
        new_doc.writexml(f)
    print(f"[PASO 9] SVG frontal generado en: {output_path} ({len(frontales)} piezas)")
    
if __name__ == "__main__":
    global dic_svg_inicial, dic_svg_modificado, dic_distancias, dic_adyacencias, dic_ajuste
    # 1. Obtener archivos y SVG inicial
    input_svg, output_svg = get_input_output_svg()

    # Cargar dos DOM independientes: uno para análisis (original), otro para modificar
    svg_original = minidom.parse(input_svg)
    svg_modificado = minidom.parse(input_svg)
    dic_svg_inicial = {"svg": svg_original}
    dic_svg_modificado = {"svg": svg_modificado}

    # 2. Listar distancias de esquina más cercana (sobre el original)
    dic_distancias = {"distancias": obtener_distancias_rects(svg_original)}

    # 3. Analizar adyacencias sobre el original
    adyacencias_original = listar_rects_adyacentes_structured(
        svg_original, tolerancia=0.2, rects_ordenados=list(dic_distancias["distancias"].keys()), distancias_ordenadas=dic_distancias["distancias"]
    )
    dic_adyacencias = {"adyacencias": adyacencias_original}

    # 4. Modificar el SVG modificado (reescalar, mover, etc.)
    
    proc_calcular_y_aplicar_proporcionalidad(svg_modificado)
    recalcular_rects(svg_modificado, PROPORCIONALIDAD_TOP_PLATE)
    reescalar_sheathing_rects(svg_modificado)

    # 5. Mover la pieza más cercana a (0,0) a (100,100) y trasladar todas las demás

    mover_pieza_cercana_cero_a_100_100(dic_distancias, dic_svg_modificado)

    # 6. Alinear en x todos los rects del color del superior/frontal automáticamente
    #alinear_rects_superior_y_frontal_por_color(svg_modificado)
    alinear_todos_los_superiores_por_colores(svg_modificado)
    # 7. Ajustar x e y de todos los rects al múltiplo superior de 0.25
    ajustar_xy_a_multiplo_025(svg_modificado)

    #ajustar_adyacencias_por_distancias(dic_adyacencias, dic_distancias)

    # 8. Guardar el SVG modificado con saltos de línea
    guardar_svg_con_saltos_linea(svg_modificado, output_svg)
    print(f"[INFO] SVG reescalado y alineado guardado en: {output_svg}")

    # Paso 9: Generar SVG solo con piezas frontales
    generar_svg_solo_frontales(output_svg)
    #guardar_svg_con_saltos_linea(svg_modificado, output_svg)
    print()  # Agrega un salto de línea después de guardar el SVG final


