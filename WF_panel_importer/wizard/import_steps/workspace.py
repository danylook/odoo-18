"""Workspace preparation utilities for the WF panel import wizard."""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Optional, Tuple

_logger = logging.getLogger(__name__)


def prepare_workspace(env) -> Tuple[str, bool]:
    """Return the directory where SVG pages should be produced.

    The method fetches the custom configuration parameter when available and
    falls back to the system temporary directory. The folder is created if
    needed and cleared so each run starts from a clean state.

    Returns
    -------
    tuple
        ``(svg_pages_dir, used_default_dir)`` where ``used_default_dir`` is
        ``True`` when the configuration parameter was not defined.
    """
    svg_temp_dir = env['ir.config_parameter'].sudo().get_param('wf_panel_importer.svg_temp_dir')
    used_default_dir = False
    if not svg_temp_dir:
        module_path = Path(__file__).resolve().parents[2]
        svg_temp_dir = str(module_path / 'data_importer')
        used_default_dir = True
        _logger.warning(
            "No se definió el parámetro 'wf_panel_importer.svg_temp_dir'. Se utiliza directorio del módulo: %s",
            svg_temp_dir,
        )

    svg_pages_dir = os.path.join(svg_temp_dir, 'svg_pages')
    os.makedirs(svg_pages_dir, exist_ok=True)
    _logger.info("📁 Directorio temporal preparado: %s", svg_pages_dir)

    _clean_directory(svg_pages_dir)
    return svg_pages_dir, used_default_dir


def save_pdf(pdf_binary: bytes, svg_pages_dir: str, base_filename: Optional[str], fallback_id: int) -> str:
    """Persist the uploaded PDF next to the generated SVGs and return its path."""
    _logger.info("💾 Guardando archivo PDF...")
    filename = base_filename or f"panel_import_{fallback_id}.pdf"
    safe_filename = filename.replace(' ', '_')
    pdf_path = os.path.join(svg_pages_dir, safe_filename)

    with open(pdf_path, 'wb') as buffer:
        buffer.write(base64.b64decode(pdf_binary))

    return pdf_path


def _clean_directory(directory: str) -> None:
    _logger.info("🧹 Limpiando archivos anteriores...")
    for entry in os.listdir(directory):
        absolute_path = os.path.join(directory, entry)
        if os.path.isfile(absolute_path):
            os.remove(absolute_path)
