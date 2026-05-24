"""Utilities to invoke the SVG processing pipeline."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

_logger = logging.getLogger(__name__)


class PipelineExecutionError(Exception):
    """Raised when the external SVG pipeline fails to execute."""

    def __init__(self, message: str, returncode: Optional[int] = None):
        super().__init__(message)
        self.returncode = returncode


def resolve_python_executable(root_path: str, prefer_venv: bool = True) -> str:
    """Locate the Python interpreter to execute the pipeline scripts.

    Parameters
    ----------
    root_path: str
        Absolute path to the module folder (typically the directory containing
        this wizard).
    prefer_venv: bool
        When True the function tries to use the local virtual environment at
        ``<root_path>/../../.venv``.
    """
    if prefer_venv:
        current = Path(root_path).resolve()
        for candidate_parent in (current, *current.parents):
            candidate = candidate_parent / '.venv' / 'Scripts' / 'python.exe'
            if candidate.exists():
                return str(candidate)

    return sys.executable


def run_pipeline(script_dir: str, pdf_path: str, svg_pages_dir: str, python_exec: Optional[str] = None) -> float:
    """Execute the external pipeline and return the elapsed time."""
    pipeline_script = os.path.join(script_dir, 'pipeline_svg_colores_inicial_linux.py')
    python_exec = python_exec or resolve_python_executable(script_dir)

    _logger.info("🐍 Ejecutando script: %s", pipeline_script)
    start = time.time()
    try:
        result = subprocess.run(
            [python_exec, pipeline_script, pdf_path, svg_pages_dir],
            check=True,
            capture_output=True,
            text=True,
        )
        if result.stdout:
            _logger.info("[pipeline stdout]\n%s", result.stdout)
        if result.stderr:
            _logger.warning("[pipeline stderr]\n%s", result.stderr)
    except subprocess.CalledProcessError as exc:
        stdout = (exc.stdout or "").strip()
        stderr = (exc.stderr or "").strip()
        detail = "\n".join(filter(None, [stdout, stderr]))
        _logger.error("❌ Pipeline salida:\n%s", detail)
        raise PipelineExecutionError(
            f"Pipeline falló con código {exc.returncode}.\n{detail}",
            returncode=exc.returncode,
        ) from exc
    return time.time() - start
