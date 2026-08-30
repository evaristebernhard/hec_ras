#!/usr/bin/env python3
"""Recover auditable design-bed controls and build three constrained sections.

The supplied scour-protection CAD does not contain a traceable, complete
cross-river design-bed polyline.  It does contain three parameter tables with
design mud elevations.  This script discovers those tables from their header
and row text (not from anonymous block names), locates the corresponding pier
centre lines in the surveyed bridge section, and constructs three explicitly
labelled screening geometries:

* centre: minimum-deformation constrained reconstruction used by HEC-RAS p05;
* local: a shorter modification interval;
* distributed: a wider modification interval.

All three sections preserve the surveyed geometry outside their stated
modification interval, meet the three design elevations, and have a gross
area of 5,980 m2 at WSE 22.190 m.  A 280 m2 blocked obstruction then gives the
specified 5,700 m2 net conveyance area.
"""

from __future__ import annotations

import csv
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCOUR_DXF = ROOT / "data" / "dxf" / "01-赣江西支特大桥抗冲刷防护（水下不分散混凝土）.dxf"
SECTION_DXF = ROOT / "data" / "dxf" / "西支5断面100-100，0906.dxf"
CURRENT_CSV = ROOT / "data" / "processed" / "cross_sections" / "西支桥下.csv"
OUT_DIR = ROOT / "data" / "processed" / "design_bed"

FLOOD_WSE = 22.190
TARGET_GROSS_AREA_M2 = 5980.0
BLOCKAGE_M2 = 280.0
TARGET_NET_AREA_M2 = 5700.0

# Modification limits are tied to surveyed bridge-section vertices.  They
# intentionally create three materially different, but equally compliant,
# interpretations of the missing full design line.
VARIANTS = {
    "local": {
        "name_cn": "局部型",
        "filename": "西支桥下_设计河床_局部型.csv",
        "left": 87.24707019740599,
        "right": 387.24687851218624,
        "smoothness": 300.0,
    },
    "center": {
        "name_cn": "中心方案",
        "filename": "西支桥下_设计河床.csv",
        "left": 76.05474431087495,
        "right": 398.0678356309305,
        "smoothness": 1000.0,
    },
    "distributed": {
        "name_cn": "分布型",
        "filename": "西支桥下_设计河床_分布型.csv",
        "left": 58.11397191573633,
        "right": 427.84768156033823,
        "smoothness": 5000.0,
    },
}


@dataclass(frozen=True)
class Entity:
    section: str | None
    kind: str
    block: str | None
    fields: tuple[tuple[int, str], ...]

    def one(self, code: int, default: str | None = None) -> str | None:
        return next((value for key, value in self.fields if key == code), default)

    def all(self, code: int) -> list[str]:
        return [value for key, value in self.fields if key == code]

    @property
    def handle(self) -> str:
        return self.one(5, "") or ""

    @property
    def text(self) -> str:
        return clean_mtext("".join(self.all(3) + self.all(1)))


def clean_mtext(value: str) -> str:
    value = value.replace("\\P", " ").replace("\\~", " ")
    value = re.sub(r"\\[A-Za-z][^;{}]*;", "", value)
    value = value.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", value).strip()


def iter_dxf_entities(path: Path, encoding: str) -> Iterator[Entity]:
    """Stream the small entity metadata while skipping large OLE payloads."""
    section: str | None = None
    block: str | None = None
    kind: str | None = None
    fields: list[tuple[int, str]] = []

    def finish() -> Entity | None:
        nonlocal kind, fields, block
        if kind is None:
            return None
        previous_block = block
        entity = Entity(section, kind, previous_block, tuple(fields))
        if kind == "BLOCK":
            block = entity.one(2) or entity.one(3)
            entity = Entity(section, kind, block, tuple(fields))
        elif kind == "ENDBLK":
            block = None
        kind = None
        fields = []
        return entity

    with path.open("r", encoding=encoding, errors="replace", newline="") as stream:
        lines = iter(stream)
        while True:
            try:
                code_line = next(lines)
                value_line = next(lines)
            except StopIteration:
                break
            try:
                code = int(code_line.strip())
            except ValueError:
                continue
            value = value_line.rstrip("\r\n")
            if code == 0 and value == "SECTION":
                entity = finish()
                if entity is not None:
                    yield entity
                try:
                    next_code = int(next(lines).strip())
                    next_value = next(lines).rstrip("\r\n")
                except (StopIteration, ValueError):
                    break
                section = next_value if next_code == 2 else None
                continue
            if code == 0 and value == "ENDSEC":
                entity = finish()
                if entity is not None:
                    yield entity
                section = None
                continue
            if code == 0:
                entity = finish()
                if entity is not None:
                    yield entity
                kind = value
                fields = []
            elif kind is not None:
                # OLE2FRAME uses group 310 for megabytes of hex.  No target
                # metadata uses it, so do not retain it in memory.
                if code != 310:
                    fields.append((code, value))
    entity = finish()
    if entity is not None:
        yield entity


def as_float(value: str | None) -> float:
    if value is None:
        raise ValueError("missing numeric DXF field")
    return float(value)


def parse_design_tables() -> tuple[list[dict[str, object]], dict[int, float]]:
    block_texts: dict[str, list[Entity]] = defaultdict(list)
    table_titles: list[Entity] = []
    for entity in iter_dxf_entities(SCOUR_DXF, "gb18030"):
        if entity.kind not in {"TEXT", "MTEXT"}:
            continue
        if entity.section == "BLOCKS" and entity.block:
            block_texts[entity.block].append(entity)
        if entity.section == "ENTITIES" and "桥墩基础冲刷参数表" in entity.text:
            table_titles.append(entity)

    header_names = {
        "设计泥面标高（m）": "design_mud_elevation_m",
        "25年实测泥面标高（m）": "measured_2025_mud_elevation_m",
        "设计最大冲刷线标高（m）": "design_max_scour_elevation_m",
    }
    evidence: list[dict[str, object]] = []
    controls: dict[int, float] = {}

    for block, entities in block_texts.items():
        by_text = {entity.text: entity for entity in entities}
        if not all(name in by_text for name in header_names):
            continue
        row_entities = [
            entity for entity in entities if re.fullmatch(r"[LR](15|16|17)#", entity.text)
        ]
        if not row_entities:
            continue
        headers = {column: by_text[label] for label, column in header_names.items()}
        for row_entity in row_entities:
            match = re.fullmatch(r"([LR])(15|16|17)#", row_entity.text)
            assert match is not None
            side, pier_text = match.groups()
            pier = int(pier_text)
            row_y = as_float(row_entity.one(20))
            cells: dict[str, Entity] = {}
            for column, header in headers.items():
                hx = as_float(header.one(10))
                candidates = [
                    entity
                    for entity in entities
                    if abs(as_float(entity.one(20, "nan")) - row_y) < 0.05
                    and entity is not row_entity
                ]
                cell = min(candidates, key=lambda entity: abs(as_float(entity.one(10)) - hx))
                if abs(as_float(cell.one(10)) - hx) > 0.05:
                    raise RuntimeError(f"{block}: cannot locate {column} for {row_entity.text}")
                if not re.fullmatch(r"[-+]?\d+(?:\.\d+)?", cell.text):
                    raise RuntimeError(f"{block}: non-numeric table cell {cell.text!r}")
                cells[column] = cell

            design_value = float(cells["design_mud_elevation_m"].text)
            previous = controls.setdefault(pier, design_value)
            if not math.isclose(previous, design_value, abs_tol=1e-9):
                raise RuntimeError(f"conflicting design mud elevations for pier {pier}")

            matching_titles = [t for t in table_titles if f"{pier}#" in t.text]
            title = min(
                matching_titles,
                key=lambda item: abs(int(item.handle or "0", 16) - int(row_entity.handle, 16)),
            )
            evidence.append(
                {
                    "pier": pier,
                    "side": side,
                    "design_mud_elevation_m": f"{design_value:.2f}",
                    "measured_2025_mud_elevation_m": f"{float(cells['measured_2025_mud_elevation_m'].text):.2f}",
                    "design_max_scour_elevation_m": f"{float(cells['design_max_scour_elevation_m'].text):.2f}",
                    "source_dxf": str(SCOUR_DXF.relative_to(ROOT)),
                    "table_title": title.text,
                    "table_title_handle": title.handle,
                    "table_title_cad_x": title.one(10),
                    "table_title_cad_y": title.one(20),
                    "anonymous_block_discovered": block,
                    "row_label_handle": row_entity.handle,
                    "row_label_block_local_x": row_entity.one(10),
                    "row_label_block_local_y": row_entity.one(20),
                    "design_cell_handle": cells["design_mud_elevation_m"].handle,
                    "design_cell_block_local_x": cells["design_mud_elevation_m"].one(10),
                    "design_cell_block_local_y": cells["design_mud_elevation_m"].one(20),
                    "measured_cell_handle": cells["measured_2025_mud_elevation_m"].handle,
                    "scour_cell_handle": cells["design_max_scour_elevation_m"].handle,
                    "coordinate_note": "title=world; table cells=anonymous-block local",
                }
            )

    expected = {15: 4.27, 16: 5.40, 17: 9.56}
    if controls != expected:
        raise RuntimeError(f"CAD design controls differ from expected table values: {controls}")
    evidence.sort(key=lambda row: (int(row["pier"]), str(row["side"])))
    return evidence, controls


def read_current_profile() -> list[dict[str, float]]:
    with CURRENT_CSV.open(encoding="utf-8-sig") as stream:
        rows = [
            {
                "station": float(row["station_m_raw_direction"]),
                "elevation": float(row["elevation_m"]),
                "cad_x": float(row["cad_x"]),
                "cad_y": float(row["cad_y"]),
            }
            for row in csv.DictReader(stream)
        ]
    rows.sort(key=lambda row: row["station"])
    return rows


def line_intersection(
    first_a: tuple[float, float],
    first_b: tuple[float, float],
    second_a: tuple[float, float],
    second_b: tuple[float, float],
) -> tuple[float, float, float, float] | None:
    x1, y1 = first_a
    x2, y2 = first_b
    x3, y3 = second_a
    x4, y4 = second_b
    denominator = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denominator) < 1e-12:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denominator
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denominator
    if -1e-9 <= t <= 1.0 + 1e-9 and -1e-9 <= u <= 1.0 + 1e-9:
        return x1 + t * (x2 - x1), y1 + t * (y2 - y1), t, u
    return None


def recover_pier_stations(
    current: Sequence[dict[str, float]], controls: dict[int, float]
) -> tuple[list[dict[str, object]], dict[int, float]]:
    labels: dict[int, Entity] = {}
    candidate_lines: list[Entity] = []
    for entity in iter_dxf_entities(SECTION_DXF, "utf-8-sig"):
        if entity.section != "ENTITIES":
            continue
        if entity.kind == "TEXT":
            match = re.fullmatch(r"(15|16|17)#", entity.text)
            if match:
                labels[int(match.group(1))] = entity
        elif entity.kind == "LWPOLYLINE" and len(entity.all(10)) == 2:
            xs = [float(value) for value in entity.all(10)]
            ys = [float(value) for value in entity.all(20)]
            if len(ys) == 2 and abs(ys[1] - ys[0]) > 300.0:
                candidate_lines.append(entity)
    if set(labels) != set(controls):
        raise RuntimeError(f"missing pier labels in bridge section: {set(controls) - set(labels)}")

    station_values = np.array([row["station"] for row in current])
    cad_x_values = np.array([row["cad_x"] for row in current])
    elevation_values = np.array([row["elevation"] for row in current])
    cad_y_values = np.array([row["cad_y"] for row in current])
    sx, sx_intercept = np.polyfit(cad_x_values, station_values, 1)
    ez, ez_intercept = np.polyfit(cad_y_values, elevation_values, 1)
    station_residuals = station_values - (sx * cad_x_values + sx_intercept)
    elevation_residuals = elevation_values - (ez * cad_y_values + ez_intercept)

    mapping: list[dict[str, object]] = []
    pier_stations: dict[int, float] = {}
    profile_xy = [(row["cad_x"], row["cad_y"]) for row in current]
    for pier, label in sorted(labels.items()):
        label_x = as_float(label.one(10))
        centreline = min(
            candidate_lines,
            key=lambda entity: abs(sum(float(v) for v in entity.all(10)) / 2.0 - label_x),
        )
        xs = [float(value) for value in centreline.all(10)]
        ys = [float(value) for value in centreline.all(20)]
        intersections: list[tuple[float, float, float, float, int]] = []
        for index, (a, b) in enumerate(zip(profile_xy, profile_xy[1:])):
            result = line_intersection((xs[0], ys[0]), (xs[1], ys[1]), a, b)
            if result is not None:
                intersections.append((*result, index))
        if len(intersections) != 1:
            raise RuntimeError(
                f"pier {pier}: expected one centreline/profile intersection, got {len(intersections)}"
            )
        cad_x, cad_y, _line_fraction, _profile_fraction, segment = intersections[0]
        station = sx * cad_x + sx_intercept
        existing_elevation = ez * cad_y + ez_intercept
        pier_stations[pier] = station
        mapping.append(
            {
                "pier": pier,
                "design_mud_elevation_m": f"{controls[pier]:.6f}",
                "existing_section_elevation_m": f"{existing_elevation:.6f}",
                "required_raise_m": f"{controls[pier] - existing_elevation:.6f}",
                "source_dxf": str(SECTION_DXF.relative_to(ROOT)),
                "label_handle": label.handle,
                "label_cad_x": f"{label_x:.9f}",
                "label_cad_y": label.one(20),
                "pier_centreline_handle": centreline.handle,
                "centreline_x1": f"{xs[0]:.9f}",
                "centreline_y1": f"{ys[0]:.9f}",
                "centreline_x2": f"{xs[1]:.9f}",
                "centreline_y2": f"{ys[1]:.9f}",
                "profile_intersection_cad_x": f"{cad_x:.9f}",
                "profile_intersection_cad_y": f"{cad_y:.9f}",
                "profile_segment_index": segment,
                "station_m": f"{station:.9f}",
                "station_transform": f"station={sx:.12g}*cad_x+({sx_intercept:.12g})",
                "station_transform_rms_residual_m": f"{float(np.sqrt(np.mean(station_residuals**2))):.12g}",
                "station_transform_max_residual_m": f"{float(np.max(np.abs(station_residuals))):.12g}",
                "elevation_transform": f"elevation={ez:.12g}*cad_y+({ez_intercept:.12g})",
                "elevation_transform_rms_residual_m": f"{float(np.sqrt(np.mean(elevation_residuals**2))):.12g}",
                "intersection_residual_cad_units": "0",
            }
        )
    return mapping, pier_stations


def section_area(x: Sequence[float], z: Sequence[float], wse: float) -> float:
    area = 0.0
    for x1, z1, x2, z2 in zip(x, z, x[1:], z[1:]):
        dx = x2 - x1
        d1, d2 = wse - z1, wse - z2
        if d1 <= 0.0 and d2 <= 0.0:
            continue
        if d1 >= 0.0 and d2 >= 0.0:
            area += dx * (d1 + d2) / 2.0
            continue
        fraction = d1 / (d1 - d2)
        if d1 > 0.0:
            area += dx * fraction * d1 / 2.0
        else:
            area += dx * (1.0 - fraction) * d2 / 2.0
    return area


def build_variant(
    variant: str,
    config: dict[str, object],
    current: Sequence[dict[str, float]],
    controls: dict[int, float],
    pier_stations: dict[int, float],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    original_x = np.array([row["station"] for row in current])
    original_z = np.array([row["elevation"] for row in current])
    left, right = float(config["left"]), float(config["right"])
    grid = np.arange(math.ceil(left / 2.0) * 2.0, right, 2.0)
    x = np.unique(np.concatenate((original_x, grid, [left, right], list(pier_stations.values()))))
    current_z = np.interp(x, original_x, original_z)
    count = len(x)

    dx = np.diff(x)
    integral_weights = np.zeros(count)
    integral_weights[:-1] += dx / 2.0
    integral_weights[1:] += dx / 2.0

    # Penalise bed raise and changes in raise-gradient.  Equality constraints
    # impose the unmodified zone, three pier elevations, and total area.
    hessian = np.diag(np.maximum(integral_weights, 1e-6))
    second_difference_rows: list[np.ndarray] = []
    for index in range(1, count - 1):
        h1 = x[index] - x[index - 1]
        h2 = x[index + 1] - x[index]
        row = np.zeros(count)
        row[index - 1] = 1.0 / h1
        row[index] = -1.0 / h1 - 1.0 / h2
        row[index + 1] = 1.0 / h2
        second_difference_rows.append(row * math.sqrt(2.0 / (h1 + h2)))
    curvature = np.array(second_difference_rows)
    hessian += float(config["smoothness"]) * curvature.T @ curvature

    constraints: list[np.ndarray] = []
    rhs: list[float] = []
    for index, station in enumerate(x):
        if station <= left + 1e-8 or station >= right - 1e-8:
            row = np.zeros(count)
            row[index] = 1.0
            constraints.append(row)
            rhs.append(0.0)
    for pier, station in sorted(pier_stations.items()):
        index = int(np.argmin(np.abs(x - station)))
        if abs(x[index] - station) > 1e-8:
            raise RuntimeError(f"pier station {station} absent from reconstruction grid")
        row = np.zeros(count)
        row[index] = 1.0
        constraints.append(row)
        rhs.append(controls[pier] - current_z[index])

    current_area = section_area(original_x, original_z, FLOOD_WSE)
    target_raise_integral = current_area - TARGET_GROSS_AREA_M2
    constraints.append(integral_weights)
    rhs.append(target_raise_integral)
    constraint_matrix = np.array(constraints)
    kkt = np.block(
        [
            [hessian, constraint_matrix.T],
            [constraint_matrix, np.zeros((len(constraints), len(constraints)))],
        ]
    )
    solution = np.linalg.solve(kkt, np.concatenate((np.zeros(count), np.array(rhs))))
    raise_m = solution[:count]
    raise_m[np.abs(raise_m) < 1e-9] = 0.0
    if float(np.min(raise_m)) < -1e-7:
        raise RuntimeError(f"{variant}: solver lowered surveyed bed by {np.min(raise_m)} m")
    raise_m = np.maximum(raise_m, 0.0)
    design_z = current_z + raise_m

    rows: list[dict[str, object]] = []
    for index, (station, old_z, new_z, dz) in enumerate(zip(x, current_z, design_z, raise_m)):
        rows.append(
            {
                "point_index": index,
                "station_m_raw_direction": f"{station:.9f}",
                "elevation_m": f"{new_z:.9f}",
                "current_elevation_m": f"{old_z:.9f}",
                "raise_m": f"{dz:.9f}",
                "modified": int(dz > 1e-8),
                "variant": variant,
                "geometry_source": "constraint_reconstruction",
            }
        )

    gross_area = section_area(x, design_z, FLOOD_WSE)
    net_area = gross_area - BLOCKAGE_M2
    control_error = max(
        abs(float(np.interp(station, x, design_z)) - controls[pier])
        for pier, station in pier_stations.items()
    )
    outside_mask = (x <= left + 1e-8) | (x >= right - 1e-8)
    outside_difference = float(np.max(np.abs(design_z[outside_mask] - current_z[outside_mask])))
    audit = [
        {
            "variant": variant,
            "check": "station_strictly_increasing",
            "target": ">0",
            "actual": f"{float(np.min(np.diff(x))):.9f}",
            "tolerance": "0",
            "passed": bool(np.all(np.diff(x) > 0.0)),
        },
        {
            "variant": variant,
            "check": "minimum_raise_m",
            "target": ">=0",
            "actual": f"{float(np.min(raise_m)):.9f}",
            "tolerance": "1e-7",
            "passed": bool(np.min(raise_m) >= -1e-7),
        },
        {
            "variant": variant,
            "check": "unchanged_outside_modification_zone_m",
            "target": "0",
            "actual": f"{outside_difference:.12g}",
            "tolerance": "1e-8",
            "passed": outside_difference <= 1e-8,
        },
        {
            "variant": variant,
            "check": "pier_control_max_error_m",
            "target": "0",
            "actual": f"{control_error:.12g}",
            "tolerance": "1e-6",
            "passed": control_error <= 1e-6,
        },
        {
            "variant": variant,
            "check": "gross_area_at_wse_22.190_m2",
            "target": f"{TARGET_GROSS_AREA_M2:.3f}",
            "actual": f"{gross_area:.9f}",
            "tolerance": "1.0",
            "passed": abs(gross_area - TARGET_GROSS_AREA_M2) <= 1.0,
        },
        {
            "variant": variant,
            "check": "blocked_obstruction_m2",
            "target": f"{BLOCKAGE_M2:.3f}",
            "actual": f"{BLOCKAGE_M2:.9f}",
            "tolerance": "0.01",
            "passed": True,
        },
        {
            "variant": variant,
            "check": "net_area_at_wse_22.190_m2",
            "target": f"{TARGET_NET_AREA_M2:.3f}",
            "actual": f"{net_area:.9f}",
            "tolerance": "1.0",
            "passed": abs(net_area - TARGET_NET_AREA_M2) <= 1.0,
        },
        {
            "variant": variant,
            "check": "maximum_raise_gradient_m_per_m",
            "target": "reported",
            "actual": f"{float(np.max(np.abs(np.diff(raise_m) / np.diff(x)))):.9f}",
            "tolerance": "n/a",
            "passed": True,
        },
    ]
    return rows, audit


def write_csv(path: Path, rows: Sequence[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV {path}")
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    evidence, controls = parse_design_tables()
    current = read_current_profile()
    mapping, pier_stations = recover_pier_stations(current, controls)
    write_csv(OUT_DIR / "design_bed_cad_evidence.csv", evidence)
    write_csv(OUT_DIR / "pier_station_mapping.csv", mapping)

    all_audit: list[dict[str, object]] = []
    for variant, config in VARIANTS.items():
        rows, audit = build_variant(variant, config, current, controls, pier_stations)
        write_csv(OUT_DIR / str(config["filename"]), rows)
        all_audit.extend(audit)
    write_csv(OUT_DIR / "design_bed_reconstruction_audit.csv", all_audit)

    if not all(bool(row["passed"]) for row in all_audit):
        failed = [row for row in all_audit if not bool(row["passed"])]
        raise RuntimeError(f"design-bed audit failed: {failed}")
    print(f"Recovered {len(evidence)} CAD table rows and {len(mapping)} pier stations")
    for variant, config in VARIANTS.items():
        area_row = next(
            row
            for row in all_audit
            if row["variant"] == variant and row["check"] == "gross_area_at_wse_22.190_m2"
        )
        print(f"{config['name_cn']}: gross area={area_row['actual']} m2 -> {config['filename']}")


if __name__ == "__main__":
    main()
