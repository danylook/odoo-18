"""Create panel sections and components from SVG output files."""

from __future__ import annotations

import base64
import logging
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, Optional

from . import project_creation

_logger = logging.getLogger(__name__)

SVG_NAMESPACE = "{http://www.w3.org/2000/svg}"
PANEL_SUFFIX = "_paso5_reescalado_frontal.svg"
COUNT_SUFFIX_RE = re.compile(r"\s*\(\d+\s+panels?\)\s*$", re.IGNORECASE)


def sync_panels_from_svg(env, svg_directory: str, projects_by_job: Optional[Dict[str, object]] = None) -> None:
    """Generate or refresh panel structures using the paso5 SVG output."""
    path = Path(svg_directory)
    if not path.exists():
        _logger.warning("Directorio de paneles inexistente: %s", svg_directory)
        return

    panel_files = sorted(path.glob(f"*{PANEL_SUFFIX}"))
    if not panel_files:
        _logger.info("No se encontraron archivos *_paso5_reescalado_frontal.svg en %s", svg_directory)
        return

    project_map = _resolve_projects(env, path, projects_by_job)
    if not project_map:
        _logger.warning("No se encontraron proyectos asociados para los paneles generados")
        return

    default_project = next(iter(project_map.values()))
    panel_model = env["wf.panel.section"]
    component_model = env["wf.panel.component"]

    _logger.info("Sincronizando %d panel(es) desde SVG", len(panel_files))
    panels_per_project = defaultdict(int)
    for file_path in panel_files:
        panel_name = file_path.name.replace(PANEL_SUFFIX, "")
        project = _select_project_for_panel(panel_name, project_map, default_project)
        if not project:
            _logger.warning("Se ignora el panel %s al no encontrar proyecto destino", panel_name)
            continue

        section = panel_model.search([
            ("project_id", "=", project.id),
            ("name", "=", panel_name),
        ], limit=1)

        if section:
            # Limpiar componentes previos para evitar duplicados.
            section.component_ids.unlink()
            section.write({"source_file": file_path.name})
            _logger.info("Panel actualizado: %s -> %s", panel_name, project.display_name)
        else:
            section = panel_model.create({
                "project_id": project.id,
                "name": panel_name,
                "source_file": file_path.name,
            })
            _logger.info("Panel creado: %s -> %s", panel_name, project.display_name)

        components = list(_extract_components(file_path))
        if components:
            for sequence, component_vals in enumerate(components, start=1):
                component_vals.update({
                    "section_id": section.id,
                    "sequence": sequence * 10,
                })
            component_model.create(components)
        else:
            _logger.info("Panel %s sin rectangulos reconocibles", panel_name)

        _attach_section_glb(section, file_path)
        panels_per_project[project.id] += 1

    if panels_per_project:
        _label_projects_with_counts(env, panels_per_project)


def _resolve_projects(env, svg_path: Path, precomputed: Optional[Dict[str, object]]) -> Dict[str, object]:
    mapping: Dict[str, object] = {}
    if precomputed:
        mapping.update(precomputed)

    metadata_files = sorted(svg_path.glob("Proyecto-*.svg"))
    if not metadata_files and mapping:
        return mapping

    for metadata_file in metadata_files:
        metadata = project_creation._extract_metadata(metadata_file)  # pylint: disable=protected-access
        if not metadata:
            continue
        job_name = metadata.get("job")
        if not job_name or job_name in mapping:
            continue
        project = env["wf.panel"].search([
            ("project", "=", job_name)
        ], limit=1)
        if not project:
            project = env["wf.panel"].search([
                ("name", "=", job_name)
            ], limit=1)
        if project:
            mapping[job_name] = project

    return mapping


def _select_project_for_panel(panel_name: str, _mapping: Dict[str, object], default_project):
    _ = panel_name  # reservado para reglas futuras
    return default_project


def _extract_components(file_path: Path) -> Iterable[Dict[str, object]]:
    try:
        tree = ET.parse(file_path)
    except ET.ParseError as exc:
        _logger.warning("No se pudo parsear %s: %s", file_path.name, exc)
        return []
    except OSError as exc:
        _logger.warning("No se pudo leer %s: %s", file_path.name, exc)
        return []

    root = tree.getroot()
    rects = list(root.iter(f"{SVG_NAMESPACE}rect"))
    components_map = {}
    for rect in rects:
        attributes = rect.attrib
        component_vals = {
            # "svg_id": attributes.get("id"),
            "data_id": attributes.get("data-id"),
            "data_path": attributes.get("data-path"),
            "x": _float_or_none(attributes.get("x")),
            "y": _float_or_none(attributes.get("y")),
            # "svg_width": _float_or_none(attributes.get("width")),
            # "svg_height": _float_or_none(attributes.get("height")),
            "data_length": _float_or_none(attributes.get("data-largo")),
            "data_width": _float_or_none(attributes.get("data-ancho")),
            "data_depth": _float_or_none(attributes.get("data-profundidad")),
            "data_orientation": _normalize_orientation(attributes.get("data-orientacion")),
        }
        key = component_vals["data_id"] or attributes.get("id")
        if not key:
            continue
        if not _has_meaningful_data(component_vals):
            continue
        existing = components_map.get(key)
        if existing:
            if _is_better_component(component_vals, existing):
                components_map[key] = component_vals
        else:
            components_map[key] = component_vals
    return list(components_map.values())


def _float_or_none(value: Optional[str]) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        try:
            normalized = value.replace(",", ".")
            return float(normalized)
        except (AttributeError, ValueError):
            return None


def _has_meaningful_data(component_vals: Dict[str, object]) -> bool:
    float_fields = (
        component_vals.get("x"),
        component_vals.get("y"),
        component_vals.get("svg_width"),
        component_vals.get("svg_height"),
        component_vals.get("data_length"),
        component_vals.get("data_width"),
        component_vals.get("data_depth"),
    )
    if any(value is not None for value in float_fields):
        return True
    return bool(
        component_vals.get("svg_id")
        or component_vals.get("data_id")
        or component_vals.get("data_path")
    )


def _is_better_component(candidate: Dict[str, object], current: Dict[str, object]) -> bool:
    return _component_quality_key(candidate) > _component_quality_key(current)


def _component_quality_key(component: Dict[str, object]):
    length = _positive(component.get("data_length"))
    width = _positive(component.get("data_width"))
    depth = _positive(component.get("data_depth"))
    area = length * width
    volume = length * width * depth
    return (length, area, width, depth, volume)


def _positive(value):
    try:
        if value and value > 0:
            return float(value)
    except TypeError:
        pass
    return 0.0


def _normalize_orientation(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    candidate = value.strip().lower()
    if candidate in {"horizontal", "vertical"}:
        return candidate
    return None


def _label_projects_with_counts(env, panels_per_project):
    Project = env["wf.panel"].sudo()
    for project_id, count in panels_per_project.items():
        project = Project.browse(project_id)
        if not project.exists():
            continue
        base_label = project.project or COUNT_SUFFIX_RE.sub("", project.name or "") or project.name
        if not base_label:
            base_label = project.name
        total_panels = len(project.section_ids)
        if not total_panels:
            continue
        new_name = f"{base_label} ({total_panels} panels)"
        if project.name != new_name:
            project.write({"name": new_name})


def _attach_section_glb(section, svg_file: Path) -> None:
    panel_name = svg_file.name.replace(PANEL_SUFFIX, "")
    glb_path = svg_file.with_name(f"{panel_name}.glb")
    if not glb_path.exists():
        return
    try:
        glb_bytes = glb_path.read_bytes()
    except OSError as exc:  # pragma: no cover - I/O defensive path
        _logger.warning("No se pudo leer el GLB %s: %s", glb_path.name, exc)
        return
    if not glb_bytes:
        _logger.info("Se omite GLB vacío para el panel %s", panel_name)
        return
    project = section.project_id
    if not project:
        _logger.info("Se omite GLB para %s por falta de proyecto", panel_name)
        return
    ensure_product = getattr(project, "_ensure_manufactured_product", None)
    if not ensure_product:
        _logger.debug("El proyecto no soporta productos fabricados; se omite GLB para %s", panel_name)
        return
    product = ensure_product(section)
    if not product:
        _logger.info("No se pudo asegurar producto fabricado para %s", panel_name)
        return
    template = product.product_tmpl_id.sudo()
    encoded = base64.b64encode(glb_bytes)
    if "model_3d" in template.fields_get():
        template.write({"model_3d": encoded})
        _logger.info("Modelo 3D actualizado para el panel %s (%s)", panel_name, glb_path.name)
