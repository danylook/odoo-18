# Requisitos:
# pip install beautifulsoup4 trimesh lxml scipy

import os
import sys
from xml.dom import minidom
from bs4 import BeautifulSoup
import trimesh

# === CONFIGURACIÓN DE ARCHIVOS ===
INPUT_SVG = "C:\\odoo17\\extra-addons\\others-17.0\\easyOCR\\svg_pages\\elevaciones de paredes_paso5_reescalado_page8_frontal.svg"
OUTPUT_GLP = "C:\\odoo17\\extra-addons\\others-17.0\\easyOCR\\svg_pages\\elevaciones_de_paredes_paso6_GLP.glp"
OUTPUT_GLB = OUTPUT_GLP.replace(".glp", ".glb")


def get_input_output_svg():
    if len(sys.argv) > 2:
        input_svg = sys.argv[1]
        output_glp = sys.argv[2]
    else:
        input_svg = INPUT_SVG
        output_glp = OUTPUT_GLP
    return input_svg, output_glp

def main():
    #print("[DEBUG] Iniciando ejecución del script...")
    #print("[DEBUG] Script iniciado correctamente.")

    # 1. Obtener archivos y SVG inicial
    input_svg, output_glb = get_input_output_svg()

    #print(f"[DEBUG] Archivo SVG de entrada: {input_svg}")
    #print(f"[DEBUG] Archivo GLB de salida: {output_glb}")

    #print(f"[DEBUG] Verificando archivo de entrada: {input_svg}")
    if not os.path.exists(input_svg):
        #print(f"[ERROR] El archivo de entrada no existe: {input_svg}")
        return
    else:
        print(f"[DEBUG] El archivo de entrada existe: {input_svg}")

    # === 2. Parsear el SVG original y convertir paths rectangulares a <rect> ===
    try:
        with open(input_svg, "r", encoding="utf-8") as file:
            svg_content = file.read()
        #print("[DEBUG] Archivo SVG leído correctamente.")
    except Exception as e:
        #print(f"[ERROR] No se pudo leer el archivo SVG: {e}")
        return

    try:
        soup = BeautifulSoup(svg_content, "xml")
        #print("[DEBUG] SVG parseado con BeautifulSoup correctamente.")
    except Exception as e:
        #print(f"[ERROR] No se pudo parsear el SVG con BeautifulSoup: {e}")
        return

    rects = soup.find_all("rect")
    if not rects:
        #print("[ERROR] No se encontraron <rect> en el SVG.")
        return

    # Calcular y_max solo de piezas estructurales (profundidad > 0) para no distorsionar la inversión Y
    struct_rects = [r for r in rects if float(r.get("data-profundidad", 1)) > 0]
    y_max = max([
        float(r.get("y", 0)) + float(r.get("height", 0))
        for r in (struct_rects if struct_rects else rects) if r.get("y") and r.get("height")
    ], default=0)

    # Calcular profundidad máxima estructural para posicionar sheathing en la cara frontal
    max_struct_depth = max(
        [float(r.get("data-profundidad", 1)) for r in struct_rects if float(r.get("data-profundidad", 0)) > 0],
        default=5.5
    )

    # Crear una escena 3D
    scene = trimesh.Scene()

    for rect in rects:
        try:
            # Leer dimensiones y posición
            width = float(rect.get("width", 1))
            height = float(rect.get("height", 1))
            depth = float(rect.get("data-profundidad", 1))
            x = float(rect.get("x", 0))
            y = float(rect.get("y", 0))
            color = rect.get("fill", "#cccccc").lstrip("#")
            if len(color) == 6:
                color_rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
            else:
                color_rgb = (200, 200, 200)

            # Detectar sheathing: profundidad <= 0 indica pieza de recubrimiento exterior
            is_sheathing = depth <= 0
            if is_sheathing:
                depth = abs(depth) if abs(depth) > 0.01 else 0.75  # espesor real del sheathing

            # Crear la caja
            box = trimesh.creation.box(extents=[width, height, depth])

            # Corregir Y: SVG tiene origen arriba, 3D tiene origen abajo
            y_corrected = y_max - y - height

            # Posicionar: sheathing va en la cara frontal del panel (z = max_struct_depth)
            if is_sheathing:
                z_center = max_struct_depth + depth / 2
            else:
                z_center = depth / 2

            # Posicionar el cubo: centro de la caja es su punto medio
            box.apply_translation([x + width / 2, y_corrected + height / 2, z_center])

            # Asignar color a la caja
            box.visual.face_colors = [*color_rgb, 255]

            # Agregar a la escena
            scene.add_geometry(box)

        except Exception as e:
            #print(f"Error con rect {rect.get('id', '')}: {e}")
            continue

    # Exportar la escena como GLB
    try:
        scene.export(output_glb)
        #print(f"Archivo GLB exportado a: {output_glb}")
    except Exception as e:
        print(f"[ERROR] No se pudo exportar el GLB: {e}")

if __name__ == "__main__":
    main()