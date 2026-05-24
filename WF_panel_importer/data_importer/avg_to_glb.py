import trimesh
import xml.etree.ElementTree as ET
import re

def extract_rect_from_d(d):
    # Extrae coordenadas rectangulares básicas del atributo 'd' de un <path>
    matches = re.findall(r"[-+]?[0-9]*\.?[0-9]+", d)
    if len(matches) >= 8:
        try:
            x_vals = list(map(float, matches[::2]))
            y_vals = list(map(float, matches[1::2]))
            min_x, max_x = min(x_vals), max(x_vals)
            min_y, max_y = min(y_vals), max(y_vals)
            return min_x, min_y, max_x - min_x, max_y - min_y
        except Exception:
            return None
    return None

def svg_to_glb(svg_path, glb_output_path, depth=10):
    with open(svg_path, "r", encoding="utf-8") as f:
        svg_content = f.read()

    root = ET.fromstring(svg_content)
    scene = trimesh.Scene()

    for elem in root.iter():
        if elem.tag.endswith("path"):
            d = elem.attrib.get("d", "")
            style = elem.attrib.get("style", "")
            fill = elem.attrib.get("fill", "")

            # Detectar fill en estilo si es necesario
            if "fill:" in style:
                match = re.search(r"fill:([^;]+);?", style)
                if match:
                    fill = match.group(1)

            if not d or fill.lower() in {"none", "transparent", ""}:
                continue

            dims = extract_rect_from_d(d)
            if not dims:
                continue
            x, y, width, height = dims
            if width == 0 or height == 0:
                continue

            # Crear caja: X=ancho, Y=profundidad, Z=alto
            box = trimesh.creation.box(extents=(width, depth, height))
            x_center = x + width / 2
            y_center = 0
            z_center = -y - height / 2
            box.apply_translation((x_center, y_center, z_center))

            # Aplicar color
            try:
                if fill.startswith("#") and len(fill) == 7:
                    r = int(fill[1:3], 16)
                    g = int(fill[3:5], 16)
                    b = int(fill[5:7], 16)
                    box.visual.face_colors = [r, g, b, 255]
            except Exception:
                pass

            scene.add_geometry(box)

    scene.export(glb_output_path)
    print(f"✅ GLB generado en: {glb_output_path}")

# USO:
# svg_to_glb("path/a/tu_plano.svg", "salida_modelo.glb", depth=10)
