"""Create or update panel records based on metadata SVG files."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

_logger = logging.getLogger(__name__)

LABEL_VALUE_PATTERN = re.compile(
    r'<tspan class="label">([^<:]+):\s*</tspan><tspan class="value">([^<]*)</tspan>'
)

FIELD_MAP = {
    "Job": "job",
    "Model": "model",
    "Designer": "designer",
    "Site Address": "site_address",
    "Date": "date",
    "Level": "level",
    "Bundle": "bundle",
}

DATE_FORMATS = [
    "%m-%d-%Y",
    "%m/%d/%Y",
    "%Y-%m-%d",
    "%m/%d/%Y %H:%M:%S",
    "%m-%d-%Y %H:%M:%S",
]


def sync_projects_from_metadata(env, svg_directory: str):
    """Scan metadata SVG files and create/update project records.

    Returns a mapping ``{job_name: wf.panel record}`` for downstream steps.
    """
    path = Path(svg_directory)
    if not path.exists():
        _logger.warning("🔍 Directorio de metadata inexistente: %s", svg_directory)
        return {}

    metadata_files = sorted(path.glob("Proyecto-*.svg"))
    if not metadata_files:
        _logger.info("ℹ️  No se encontraron archivos Proyecto-*.svg en %s", svg_directory)
        return {}

    records_by_job: Dict[str, object] = {}

    _logger.info("📂 Sincronizando metadata desde %d archivo(s)", len(metadata_files))
    for file_path in metadata_files:
        _logger.debug("🔎 Procesando metadata: %s", file_path.name)
        data = _extract_metadata(file_path)
        if not data:
            _logger.debug("⏭️  Sin datos interpretables en %s", file_path.name)
            continue
        record = _apply_metadata(env, data)
        if record:
            records_by_job[data["job"]] = record

    return records_by_job


def _extract_metadata(file_path: Path) -> Optional[Dict[str, str]]:
    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        _logger.warning("⚠️  No se pudo leer %s: %s", file_path, exc)
        return None

    matches = LABEL_VALUE_PATTERN.findall(content)
    if not matches:
        _logger.warning("⚠️  Archivo sin etiquetas reconocibles: %s", file_path)
        return None

    metadata: Dict[str, str] = {}
    for label, value in matches:
        key = FIELD_MAP.get(label.strip())
        if not key:
            continue
        metadata[key] = value.strip()

    if not metadata.get("job"):
        _logger.warning("⚠️  Archivo %s sin valor de Job, se ignora", file_path)
        return None

    return metadata


def _apply_metadata(env, metadata: Dict[str, str]):
    job_value = metadata.get("job")
    if not job_value:
        return None

    panel_model = env["wf.panel"]
    existing = panel_model.search([("project", "=", job_value)], limit=1)
    if not existing:
        existing = panel_model.search([("name", "=", job_value)], limit=1)

    values = _build_panel_values(metadata)
    values = _filter_known_fields(panel_model, values)
    if existing:
        existing.write(values)
        _logger.info("♻️  Proyecto actualizado a partir de metadata: %s", job_value)
        return existing
    else:
        values.setdefault("name", job_value)
        record = panel_model.create(values)
        _logger.info("✅ Proyecto creado a partir de metadata: %s", job_value)
        return record


def _build_panel_values(metadata: Dict[str, str]) -> Dict[str, object]:
    values: Dict[str, object] = {
        "project": metadata.get("job"),
        "model": metadata.get("model"),
        "designer": metadata.get("designer"),
        "site_address": metadata.get("site_address"),
        "level": metadata.get("level"),
        "bundle": metadata.get("bundle"),
    }

    date_str = metadata.get("date")
    if date_str:
        parsed = _parse_date(date_str)
        if parsed:
            values["date"] = parsed

    return values


def _parse_date(date_value: str) -> Optional[str]:
    for fmt in DATE_FORMATS:
        try:
            parsed = datetime.strptime(date_value, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue
    _logger.info("ℹ️  Fecha con formato no soportado (%s); se guarda sin convertir", date_value)
    return None


def _filter_known_fields(model, values: Dict[str, object]) -> Dict[str, object]:
    field_names = set(model.fields_get().keys())
    return {key: val for key, val in values.items() if key in field_names}
