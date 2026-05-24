# --- FUNCIONES PARA USO COMO MÓDULO ---
def run_ocr_pipeline(pdf_path):
    return extract_panels_from_pdf(pdf_path)

def run_and_get_paneles_datos(pdf_path):
    data = run_ocr_pipeline(pdf_path)
    # --- Agrupación y reporte unificado por (panel_name, level) ---
    from collections import defaultdict
    panel_groups = defaultdict(lambda: {
        'panel_name': None,
        'level': None,
        'page_list': set(),
        'piezas': [],
        'sheathing': [],
        'project': '',
        'site_address': '',
        'date': '',
        'designer': ''
    })
    for panel in data:
        key = (panel.get('panel_name',''), panel.get('level',''))
        group = panel_groups[key]
        group['panel_name'] = panel.get('panel_name','')
        group['level'] = panel.get('level','')
        group['project'] = panel.get('project','')
        group['site_address'] = panel.get('site_address','')
        group['date'] = panel.get('date','')
        group['designer'] = panel.get('designer','')
        # Solo usar 'page_list' estrictamente y asegurar que el valor de 'page' se incluya
        pages = panel.get('page_list')
        if isinstance(pages, (list, tuple)):
            for p in pages:
                if p:
                    group['page_list'].add(p)
        elif pages:
            group['page_list'].add(pages)
        # Asegurar que el valor de 'page' individual también se incluya
        page_val = panel.get('page')
        if page_val:
            group['page_list'].add(page_val)
        for item in panel.get('cutting_list', []):
            label = item.get('label', '')
            member = item.get('member', '')
            qty = int(item.get('qty', 1)) if str(item.get('qty', 1)).isdigit() else 1
            length = item.get('length', '')
            width = item.get('width', '')
            desc = item.get('description', '') if 'description' in item else ''
            # Unir member y description si description existe y no está vacía
            member_full = member
            if desc:
                member_full = f"{member} {desc}".strip()
            # --- Sustituir '"' por 'X0' en member_full si es sheathing ---
            if ('sheathing' in member.lower() or 'cladmate' in member.lower() or 'sheathing' in desc.lower() or 'cladmate' in desc.lower()) and '"' in member_full:
                member_full = member_full.replace('"', 'X0')
            # Normalizar width y length a formato 00-00-00
            def normalize_dim(val):
                parts = [p.zfill(2) for p in str(val).split('-') if p]
                while len(parts) < 3:
                    parts.insert(0, '00')
                #print(f"[DEBUG] Normalizando dimensión: entrada='{val}' salida='{parts}'")
                #input("Presiona ENTER para continuar...")
                return '-'.join(parts)
            length_norm = normalize_dim(length)
            width_norm = normalize_dim(width)
            if 'sheathing' in member.lower() or 'cladmate' in member.lower() or 'sheathing' in desc.lower() or 'cladmate' in desc.lower():
                group['sheathing'].append((label, member_full, qty, length_norm, width_norm))
            else:
                group['piezas'].append((label, member_full, qty, length_norm, width_norm))
    # --- Unificar paneles con el mismo nombre (ignorando "continued") y sumar piezas/sheathing y páginas ---
    import re
    def normalize_panel_name(name):
        if not name:
            return ''
        return re.sub(r'\s*continued\s*$', '', name, flags=re.IGNORECASE).strip().upper()
    def merge_items(list1, list2):
        merged = list(list1)
        for item2 in list2:
            found = False
            for idx, item1 in enumerate(merged):
                if item1[:2] == item2[:2] and item1[3] == item2[3] and item1[4] == item2[4]:
                    merged[idx] = (item1[0], item1[1], item1[2] + item2[2], item1[3], item1[4])
                    found = True
                    break
            if not found:
                merged.append(item2)
        return merged
    logical_panels = {}
    logical_panel_sources = {}
    for group in panel_groups.values():
        norm_name = normalize_panel_name(group['panel_name'])
        if norm_name not in logical_panels:
            logical_panels[norm_name] = {
                'panel_name': group['panel_name'],
                'level': group['level'],
                'page_list': set(group['page_list']),
                'piezas': list(group['piezas']),
                'sheathing': list(group['sheathing'])
            }
            logical_panel_sources[norm_name] = [group]
        else:
            logical_panels[norm_name]['page_list'].update(group['page_list'])
            logical_panels[norm_name]['piezas'] = merge_items(logical_panels[norm_name]['piezas'], group['piezas'])
            logical_panels[norm_name]['sheathing'] = merge_items(logical_panels[norm_name]['sheathing'], group['sheathing'])
            logical_panel_sources[norm_name].append(group)
    # --- Generar salida tipo lista de dicts ---
    def to_filename_part(s):
        return str(s).replace(' ', '_').replace('-', '_').upper() if s else ''
    output_panels = []
    for norm_name, group in logical_panels.items():
        levels = [g['level'] for g in logical_panel_sources[norm_name] if g['level']]
        floor_part = to_filename_part(max(set(levels), key=levels.count)) if levels else ''
        # Solo agregar al JSON si hay piezas
        if group['piezas']:
            nombre_archivo = f"{to_filename_part(group['panel_name'])}_{floor_part}" if floor_part else to_filename_part(group['panel_name'])
            output_panels.append({
                'nombre_archivo': nombre_archivo,
                'panel_name': group['panel_name'],
                'level': floor_part,
                'page_list': sorted(group['page_list']),
                'piezas': group['piezas'],
                'sheathing': group['sheathing']
            })
    return output_panels
import pdfplumber
import re

def extract_panels_from_pdf(pdf_path):
    panels = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ''
            # Dividir en paneles dentro de la página
            panel_blocks = re.split(r'(?=Panel:\s*)', page_text)
            for block in panel_blocks:
                if not block.strip():
                    continue
                # Panel name
                match_panel = re.search(r'Panel:\s*(.+)', block)
                if match_panel:
                    panel_line = match_panel.group(1).replace('Elevation Report', '').strip()
                    if '  ' in panel_line:
                        panel_name = panel_line.split('  ')[0].strip()
                    else:
                        panel_name = panel_line.strip()
                else:
                    panel_name = None
                # Project data
                header_match = re.search(r'Job: (.*?)\nModel:(.*?) Page:.*?\nSite Address:(.*?) Date: (.*?)\nDesigner:(.*?)\n', block, re.DOTALL)
                project_data = {}
                if header_match:
                    project_val = header_match.group(1).replace('Elevation Report', '').strip()
                    if '  ' in project_val:
                        project_val = project_val.split('  ')[0].strip()
                    project_data['project'] = project_val
                    project_data['model'] = header_match.group(2).strip()
                    project_data['site_address'] = header_match.group(3).strip()
                    project_data['date'] = header_match.group(4).strip().split()[0]
                    project_data['designer'] = header_match.group(5).strip()
                # Level
                level_val = None
                match_level = re.search(r'Level:\s*(.+)', block, re.IGNORECASE)
                if match_level:
                    level_line = match_level.group(1).strip()
                    cut_patterns = [r'\t', r'\s{2,}', r'Bundle', r'BUNDLE', r'GAR', r'\d+/\d+']
                    min_idx = len(level_line)
                    for pat in cut_patterns:
                        m = re.search(pat, level_line)
                        if m:
                            min_idx = min(min_idx, m.start())
                    level_val = level_line[:min_idx].strip()
                project_data['level'] = level_val
                project_data['panel_name'] = panel_name or project_data.get('project')
                # Cutting List
                bom_lines = []
                # Buscar Cutting List robustamente
                idx_cutting = block.lower().find('cutting list')
                if idx_cutting != -1:
                    cutting_block = block[idx_cutting:]
                    bom_lines += parse_cutting_list(cutting_block)
                # --- Sustituir '"' por 'X0' en member si es sheathing (por robustez en el parseo base) ---
                for item in bom_lines:
                    if ('sheathing' in item.get('member','').lower() or 'cladmate' in item.get('member','').lower()) and '"' in item.get('member',''):
                        item['member'] = item['member'].replace('"', 'X0')
                # Asociar número de página (1-indexed)
                project_data['page'] = page_idx + 1
                panels.append({
                    **project_data,
                    'cutting_list': bom_lines
                })
    return panels

def split_member_description(combined_parts_list):
    member_words = []
    description_words = []
    desc_started = False
    common_materials = ["SPF", "OSB", "LVL", "PINE", "FIR", "SYP", "TREATED", "CLADMATE"]
    for i, part in enumerate(combined_parts_list):
        if desc_started:
            description_words.append(part)
        else:
            is_dimension_start = False
            if part and part[0].isdigit():
                if ('x' in part and part.count('x') == 1 and part.index('x') > 0) or \
                   part.endswith('"') or part.endswith("'") or \
                   ('/' in part and part.replace('/', '').isdigit() and sum(c.isdigit() for c in part) > sum(c == '/' for c in part)):
                    is_dimension_start = True
            if is_dimension_start:
                desc_started = True
                description_words.append(part)
            elif member_words and part.upper() in common_materials:
                desc_started = True
                description_words.append(part)
            else:
                member_words.append(part)
    return " ".join(member_words), " ".join(description_words)

def parse_cutting_list(text_block):
    bom_lines = []
    lines = text_block.splitlines()
    data_lines_started = False
    # Palabras clave mínimas para la cabecera
    header_keywords = ["label", "lbl", "member", "description", "qty", "length", "width"]
    for i, line_str_full in enumerate(lines):
        line_str = line_str_full.strip()
        if not line_str:
            continue
        # Detectar cabecera de forma flexible
        lower_line = line_str.lower()
        if all(any(k in lower_line for k in ["label", "lbl"]) if kw in ["label", "lbl"] else kw in lower_line for kw in header_keywords):
            data_lines_started = True
            continue
        if not data_lines_started:
            # --- NUEVO: intentar parsear líneas tipo resumen si no hay cabecera ---
            # Ejemplo: A Bottom Plate 2x6 SPF No.2 (1) 13-08-08 0-00
            resumen_match = re.match(r'^([A-Z])\s+([\w\s\d\"\'\-\.]+?)\s*\((\d+)\)\s+([\d\-]+)\s+([\d\-]+)$', line_str)
            if resumen_match:
                label = resumen_match.group(1)
                member = resumen_match.group(2).strip()
                qty = int(resumen_match.group(3))
                length = resumen_match.group(4)
                width = resumen_match.group(5)
                # Normalizar length y width a formato XX-XX-XX
                def normalize_dim(val):
                    parts = [p.zfill(2) for p in str(val).split('-') if p]
                    # Rellenar a la izquierda con '00' hasta tener 3 partes, sin truncar si hay más
                    while len(parts) < 3:
                        parts.insert(0, '00')
                    print(f"[DEBUG] Normalizando dimensión: entrada='{val}' salida='{parts}'")
                    input("Presiona ENTER para continuar...")
                    return '-'.join(parts)
                length = normalize_dim(length)
                width = normalize_dim(width)
                # Detectar sheathing por nombre y reemplazar '"' por 'X0' en member
                if 'sheathing' in member.lower() or 'cladmate' in member.lower():
                    member = member.replace('"', 'X0')
                bom_lines.append({'label': label, 'member': member, 'description': '', 'qty': qty, 'length': length, 'width': width})
                continue
            continue
        parts = line_str.split()
        if len(parts) >=1 and parts[0].lower().startswith("total"):
            continue
        if len(parts) < 4:
            continue
        try:
            label = parts[0]
            if len(parts) >= 3:
                width_candidate = parts[-1]
                length_candidate = parts[-2]
                qty_candidate = parts[-3]
                is_qty_like = (qty_candidate.startswith('(') and qty_candidate.endswith(')') and qty_candidate[1:-1].replace('.', '', 1).isdigit()) or \
                              qty_candidate.replace('.', '', 1).isdigit()
                is_length_like = '-' in length_candidate or length_candidate.replace('.', '', 1).isdigit()
                is_width_like = '-' in width_candidate or width_candidate.replace('.', '', 1).isdigit()
                if is_qty_like and is_length_like and is_width_like and len(parts) >= 4:
                    actual_qty = qty_candidate.replace('(', '').replace(')', '')
                    actual_length = length_candidate
                    actual_width = width_candidate
                    combined_member_desc_parts = parts[1:-3]
                    if not combined_member_desc_parts:
                        continue
                    member, description = split_member_description(combined_member_desc_parts)
                    bom_lines.append({
                        'label': label, 'member': member, 'description': description,
                        'qty': actual_qty, 'length': actual_length, 'width': actual_width,
                    })
        except Exception:
            continue
    return bom_lines

def process_pdf(path):
    return extract_panels_from_pdf(path)

# Uso:
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        print(f"[INFO] Usando archivo enviado por argumento: {pdf_path}")
    else:
        pdf_path = "C:\\odoo17\\extra-addons\\others-17.0\\easyOCR\\Blk_153_L1.pdf"
        print(f"[INFO] Usando archivo predefinido: {pdf_path}")
    data = process_pdf(pdf_path)
    # Unificación de nombre de archivo (solo una vez, reutilizable)
    def sugerir_nombre_archivo(panel):
        def to_filename_part(s):
            return str(s).replace(' ', '_').replace('-', '_').upper() if s else ''
        project = panel.get('project', '')
        level = panel.get('level', '')
        panel_name = panel.get('panel_name', '')
        # Si panel_name ya está incluido en project o level, no lo repitas
        parts = [to_filename_part(project), to_filename_part(level)]
        if panel_name and to_filename_part(panel_name) not in parts:
            parts.append(to_filename_part(panel_name))
        nombre = '_'.join([p for p in parts if p])
        return nombre.strip('_')

    # --- Agrupación y reporte unificado por (panel_name, level) ---
    from collections import defaultdict

    panel_groups = defaultdict(lambda: {
        'panel_name': None,
        'level': None,
        'page_list': set(),
        'piezas': [],
        'sheathing': [],
        'project': '',
        'site_address': '',
        'date': '',
        'designer': ''
    })

    for panel in data:
        key = (panel.get('panel_name',''), panel.get('level',''))
        group = panel_groups[key]
        group['panel_name'] = panel.get('panel_name','')
        group['level'] = panel.get('level','')
        group['project'] = panel.get('project','')
        group['site_address'] = panel.get('site_address','')
        group['date'] = panel.get('date','')
        group['designer'] = panel.get('designer','')
        # Solo usar 'page_list' estrictamente y asegurar que el valor de 'page' se incluya
        pages = panel.get('page_list')
        if isinstance(pages, (list, tuple)):
            for p in pages:
                if p:
                    group['page_list'].add(p)
        elif pages:
            group['page_list'].add(pages)
        # Asegurar que el valor de 'page' individual también se incluya
        page_val = panel.get('page')
        if page_val:
            group['page_list'].add(page_val)
        for item in panel.get('cutting_list', []):
            label = item.get('label', '')
            member = item.get('member', '')
            qty = int(item.get('qty', 1)) if str(item.get('qty', 1)).isdigit() else 1
            length = item.get('length', '')
            width = item.get('width', '')
            desc = item.get('description', '') if 'description' in item else ''
            # Unir member y description si description existe y no está vacía
            member_full = member
            if desc:
                member_full = f"{member} {desc}".strip()
            # Normalizar width y length a formato 00-00-00
            def normalize_dim(val):
                parts = str(val).split('-')
                return '-'.join([p.zfill(2) for p in parts] + ['00'] * (3 - len(parts)))
            length_norm = normalize_dim(length)
            width_norm = normalize_dim(width)
            if 'sheathing' in member.lower() or 'cladmate' in member.lower() or 'sheathing' in desc.lower() or 'cladmate' in desc.lower():
                group['sheathing'].append((label, member_full, qty, length_norm, width_norm))
            else:
                group['piezas'].append((label, member_full, qty, length_norm, width_norm))

    # Mostrar resultados agrupados


    # --- Unificar paneles con el mismo nombre (ignorando "continued") y sumar piezas/sheathing y páginas ---
    import json
    import re
    def normalize_panel_name(name):
        if not name:
            return ''
        return re.sub(r'\s*continued\s*$', '', name, flags=re.IGNORECASE).strip().upper()

    def merge_items(list1, list2):
        merged = list(list1)
        for item2 in list2:
            found = False
            for idx, item1 in enumerate(merged):
                if item1[:2] == item2[:2] and item1[3] == item2[3] and item1[4] == item2[4]:
                    merged[idx] = (item1[0], item1[1], item1[2] + item2[2], item1[3], item1[4])
                    found = True
                    break
            if not found:
                merged.append(item2)
        return merged

    # Agrupar paneles lógicos
    logical_panels = {}
    logical_panel_sources = {}
    for group in panel_groups.values():
        norm_name = normalize_panel_name(group['panel_name'])
        if norm_name not in logical_panels:
            logical_panels[norm_name] = {
                'panel_name': group['panel_name'],
                'level': group['level'],
                'page_list': set(group['page_list']),
                'piezas': list(group['piezas']),
                'sheathing': list(group['sheathing'])
            }
            logical_panel_sources[norm_name] = [group]
        else:
            logical_panels[norm_name]['page_list'].update(group['page_list'])
            logical_panels[norm_name]['piezas'] = merge_items(logical_panels[norm_name]['piezas'], group['piezas'])
            logical_panels[norm_name]['sheathing'] = merge_items(logical_panels[norm_name]['sheathing'], group['sheathing'])
            logical_panel_sources[norm_name].append(group)

    # Mostrar resultados unificados por panel lógico
    for norm_name, group in logical_panels.items():
        def to_filename_part(s):
            return str(s).replace(' ', '_').replace('-', '_').upper() if s else ''
        # Buscar el floor/level más frecuente entre los grupos fuente
        levels = [g['level'] for g in logical_panel_sources[norm_name] if g['level']]
        floor_part = to_filename_part(max(set(levels), key=levels.count)) if levels else ''
        # Solo imprimir si hay piezas
        if group['piezas']:
            nombre_archivo = f"{to_filename_part(group['panel_name'])}_{floor_part}" if floor_part else to_filename_part(group['panel_name'])
            print(f"\n--- Panel: {group['panel_name']} | Niveles: {sorted(set(levels))} | Páginas: {sorted(group['page_list'])} ---")
            print(f"Archivo sugerido: {nombre_archivo}")
            print("PIEZAS =", group['piezas'])
            print("SHEATHING =", group['sheathing'])

    # --- Imprimir archivo de salida final (JSON) ---
    output_panels = []
    for norm_name, group in logical_panels.items():
        def to_filename_part(s):
            return str(s).replace(' ', '_').replace('-', '_').upper() if s else ''
        levels = [g['level'] for g in logical_panel_sources[norm_name] if g['level']]
        floor_part = to_filename_part(max(set(levels), key=levels.count)) if levels else ''
        # Solo agregar al JSON si hay piezas y si hay páginas
        if group['piezas'] and group['page_list']:
            nombre_archivo = f"{to_filename_part(group['panel_name'])}_{floor_part}" if floor_part else to_filename_part(group['panel_name'])
            output_panels.append({
                'nombre_archivo': nombre_archivo,
                'panel_name': group['panel_name'],
                'level': floor_part,
                'page_list': sorted(group['page_list']),
                'piezas': group['piezas'],
                'sheathing': group['sheathing']
            })
    print("\n--- Archivo de salida (JSON) ---")
    #print(json.dumps(output_panels, indent=2, ensure_ascii=False))
