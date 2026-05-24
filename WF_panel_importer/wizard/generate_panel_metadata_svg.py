#!/usr/bin/env python3
"""Utility to generate a simple SVG summary with panel metadata.

When posible metadata values are read directly from the provided SVG page so the
output reflects the original document. Values can still be overridden via
command-line options or JSON files. The hard-coded defaults are only used as a
fallback when no metadata is detected.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import OrderedDict, defaultdict
from typing import Dict, Iterable, List, Tuple

import xml.etree.ElementTree as ET

DEFAULT_ROWS = [
    ("Job", "Emp-Dain Ph2-BLK-153-01-20T-29-END-D1"),
    ("Model", "Empire Communities"),
    ("Designer", "S.R"),
    ("Site Address", "Welland,ON Model: 20T-29 END-D1"),
    ("Date", "04-24-2025"),
    ("Level", "1st Floor"),
    ("Bundle", "1/7 1st FLR EXT"),
]

EXPECTED_LABEL_ORDER = [
    "Job",
    "Model",
    "Designer",
    "Site Address",
    "Date",
    "Level",
    "Bundle",
]
EXPECTED_LABEL_SET = set(EXPECTED_LABEL_ORDER)
PARSER_LABELS = EXPECTED_LABEL_ORDER + ["Panel"]


def parse_transform(transform: str | None) -> Tuple[float, float] | None:
    if not transform:
        return None
    transform = transform.strip()
    if transform.startswith("translate") and transform.endswith(")"):
        inner = transform[len("translate(") : -1]
        parts = [p.strip() for p in inner.replace(",", " ").split() if p.strip()]
        if len(parts) >= 2:
            try:
                return float(parts[0]), float(parts[1])
            except ValueError:
                return None
    return None


def extract_fields(row_text: str) -> List[Tuple[str, str]]:
    positions: List[Tuple[int, str]] = []
    lower = row_text.lower()
    for label in PARSER_LABELS:
        needle = f"{label}:"
        idx = lower.find(needle.lower())
        if idx != -1:
            positions.append((idx, label))
    positions.sort()

    fields: List[Tuple[str, str]] = []
    for idx, (start_pos, label) in enumerate(positions):
        value_start = start_pos + len(label) + 1
        value_end = positions[idx + 1][0] if idx + 1 < len(positions) else len(row_text)
        value = row_text[value_start:value_end].strip()
        if value:
            fields.append((label, value))
    return fields


def clean_value(label: str, value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value.strip())
    if label == "Job":
        cleaned = cleaned.replace("Elevation Report", "")
        cleaned = cleaned.replace(" - ", "-").strip()
    return cleaned


def extract_rows_from_svg(svg_path: str) -> List[Tuple[str, str]]:
    try:
        tree = ET.parse(svg_path)
    except (ET.ParseError, FileNotFoundError, OSError):
        return []

    rows_by_y: Dict[float, List[Tuple[float, str]]] = defaultdict(list)
    for element in tree.getroot().iter():
        label = element.attrib.get("aria-label")
        if not label:
            continue
        coords = parse_transform(element.attrib.get("transform"))
        if not coords:
            continue
        x, y = coords
        rows_by_y[round(y, 1)].append((x, label))

    ordered_values: "OrderedDict[str, str]" = OrderedDict()
    for y in sorted(rows_by_y):
        row_segments = sorted(rows_by_y[y], key=lambda item: item[0])
        row_text = " ".join(segment for _, segment in row_segments)
        for label, value in extract_fields(row_text):
            if label in EXPECTED_LABEL_SET and label not in ordered_values:
                ordered_values[label] = clean_value(label, value)

    return list(ordered_values.items())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera un SVG con los metadatos principales del panel."
    )
    parser.add_argument(
        "input",
        help=(
            "Ruta del archivo base (se usa su directorio para guardar el SVG de salida)."
        ),
    )
    parser.add_argument(
        "--output",
        help=(
            "Ruta completa del SVG a generar. Si se omite, se usa el nombre del Job "
            "en el mismo directorio del archivo de entrada."
        ),
    )
    parser.add_argument(
        "--width",
        type=int,
        default=900,
        help="Ancho del lienzo SVG en píxeles (default: 900).",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=360,
        help="Alto del lienzo SVG en píxeles (default: 360).",
    )
    parser.add_argument(
        "--font-size",
        type=int,
        default=22,
        help="Tamaño de fuente para las filas de texto.",
    )
    parser.add_argument(
        "--line-height",
        type=int,
        default=40,
        help="Separación vertical entre filas de texto.",
    )
    parser.add_argument(
        "--data-file",
        help="Archivo JSON con pares etiqueta/valor. Formato: {\"Job\": \"...\", ...}",
    )
    parser.add_argument(
        "--pairs",
        nargs="*",
        metavar="clave=valor",
        help="Valores inline en formato clave=valor para sobreescribir o agregar campos.",
    )
    parser.add_argument(
        "--title",
        default="Panel Metadata",
        help="Título a mostrar en la parte superior del SVG.",
    )
    return parser.parse_args()


def order_rows(rows_map: "OrderedDict[str, str]") -> List[Tuple[str, str]]:
    ordered: List[Tuple[str, str]] = []
    seen: set[str] = set()
    for label in EXPECTED_LABEL_ORDER:
        if label in rows_map:
            ordered.append((label, rows_map[label]))
            seen.add(label)
    for label, value in rows_map.items():
        if label not in seen:
            ordered.append((label, value))
    return ordered


def load_data(args: argparse.Namespace) -> List[Tuple[str, str]]:
    svg_rows = extract_rows_from_svg(args.input)
    if svg_rows:
        rows_map: "OrderedDict[str, str]" = OrderedDict(svg_rows)
    else:
        rows_map = OrderedDict(DEFAULT_ROWS)

    if args.data_file:
        try:
            with open(args.data_file, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            for key, value in loaded.items():
                rows_map[str(key)] = str(value)
        except FileNotFoundError:
            print(f"[WARN] No se encontró el archivo {args.data_file}, se ignora.")
        except json.JSONDecodeError as exc:
            print(f"[WARN] Archivo JSON inválido ({exc}); se ignora.")

    if args.pairs:
        for raw in args.pairs:
            if "=" not in raw:
                print(f"[WARN] Par ignorado (sin '='): {raw}")
                continue
            key, value = raw.split("=", 1)
            rows_map[key.strip()] = value.strip()

    return order_rows(rows_map)


_MAX_FILENAME_LEN = 150  # well under the 255-byte Linux limit


def sanitize_filename(value: str) -> str:
    base = value.strip()
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base)
    base = base.strip("._")
    return (base or "panel_metadata")[:_MAX_FILENAME_LEN]


def build_svg(
    rows: Iterable[Tuple[str, str]],
    width: int,
    height: int,
    font_size: int,
    line_height: int,
    title: str,
) -> str:
    margin_x = 40
    margin_y = 40

    y_cursor = margin_y + font_size

    header = f"""
<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{width}\" height=\"{height}\">
    <style>
        .title {{ font-family: 'Segoe UI', Arial, sans-serif; font-weight: 600; font-size: {font_size + 6}px; }}
        .label {{ font-family: 'Segoe UI', Arial, sans-serif; font-weight: 600; font-size: {font_size}px; }}
        .value {{ font-family: 'Segoe UI', Arial, sans-serif; font-weight: 400; font-size: {font_size}px; }}
        .row {{ fill: #222; }}
        .bg {{ fill: #f9f9f9; stroke: #444; stroke-width: 1; }}
    </style>
    <rect class=\"bg\" x=\"10\" y=\"10\" width=\"{width - 20}\" height=\"{height - 20}\" rx=\"12\" ry=\"12\" />
    <text class=\"title\" x=\"{margin_x}\" y=\"{margin_y}\">{title}</text>
""".strip()

    body_lines = [header]

    for label, value in rows:
        y_cursor += line_height
        row = (
            f"    <text class=\"row\" x=\"{margin_x}\" y=\"{y_cursor}\">"
            f"<tspan class=\"label\">{label}: </tspan>"
            f"<tspan class=\"value\">{value}</tspan>"
            "</text>"
        )
        body_lines.append(row)

    body_lines.append("</svg>")
    return "\n".join(body_lines)


def write_file(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def main() -> int:
    args = parse_args()
    rows = load_data(args)
    data_map = dict(rows)

    base_dir = os.path.dirname(os.path.abspath(args.input)) or os.getcwd()

    if args.output:
        output_path = args.output
    else:
        job_name = data_map.get("Job", "panel_metadata")
        base_name = sanitize_filename(job_name)
        output_path = os.path.join(base_dir, f"Proyecto-{base_name}.svg")
    if not output_path.lower().endswith(".svg"):
        output_path = f"{output_path}.svg"

    svg_content = build_svg(
        rows=rows,
        width=args.width,
        height=args.height,
        font_size=args.font_size,
        line_height=args.line_height,
        title=args.title,
    )
    write_file(output_path, svg_content)
    print(f"SVG generado en {os.path.abspath(output_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
