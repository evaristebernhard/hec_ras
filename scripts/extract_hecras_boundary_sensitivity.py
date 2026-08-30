#!/usr/bin/env python3
"""Validate and summarize the downstream-boundary HEC-RAS sensitivity runs."""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path

import h5py

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "hecras_boundary_sensitivity"
RESULTS_DIR = ROOT / "results"
PROJECT_BASENAME = "GanjiangWestBridgeBoundary"
KEY_STATIONS = {"600", "500"}

BASE = (
    "Results/Steady/Output/Output Blocks/Base Output/"
    "Steady Profiles/Cross Sections"
)
XS_ATTRIBUTES = "Results/Steady/Output/Geometry Info/Cross Section Attributes"
GEOMETRY_ATTRIBUTES = "Geometry/Cross Sections/Attributes"


def decode(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    return str(value).strip()


def read_plan_map() -> list[dict[str, str]]:
    path = MODEL_DIR / "sensitivity_plan_map.csv"
    with path.open(encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def read_plan(plan: str) -> tuple[list[dict[str, float | str]], dict[str, object]]:
    hdf_path = MODEL_DIR / f"{PROJECT_BASENAME}.{plan}.hdf"
    if not hdf_path.exists():
        raise FileNotFoundError(f"Missing computed HEC-RAS result: {hdf_path}")

    with h5py.File(hdf_path, "r") as hdf:
        units = decode(hdf.attrs.get("Units System", ""))
        if units != "SI Units":
            raise RuntimeError(f"{plan}: expected SI Units, HDF reports {units!r}")

        geometry = hdf[GEOMETRY_ATTRIBUTES][:]
        obstruction_modes = {
            decode(row["RS"]): int(row["Obstr Block Mode"]) for row in geometry
        }
        if obstruction_modes.get("500") != 1:
            raise RuntimeError(f"{plan}: blocked obstruction absent at RS 500")

        xs = hdf[XS_ATTRIBUTES][:]
        stations = [decode(row["Station"]) for row in xs]
        water_surface = hdf[f"{BASE}/Water Surface"][0]
        energy_grade = hdf[f"{BASE}/Energy Grade"][0]
        additional = f"{BASE}/Additional Variables"
        velocity = hdf[f"{additional}/Velocity Total"][0]
        flow_area = hdf[f"{additional}/Area Flow Total"][0]
        hydraulic_depth = hdf[f"{additional}/Hydraulic Depth Total"][0]

        messages = decode(hdf["Results/Summary/Compute Messages (text)"][0])
        if "Finished Steady Flow Simulation" not in messages:
            raise RuntimeError(f"{plan}: completion marker absent")
        lower_messages = messages.lower()
        if "error" in lower_messages or "warning" in lower_messages:
            raise RuntimeError(f"{plan}: HEC-RAS compute messages contain error/warning")

        rows: list[dict[str, float | str]] = []
        for station, wse, energy, v, area, depth in zip(
            stations, water_surface, energy_grade, velocity, flow_area, hydraulic_depth
        ):
            if station not in KEY_STATIONS:
                continue
            rows.append(
                {
                    "river_station": station,
                    "wse_m": float(wse),
                    "energy_grade_m": float(energy),
                    "velocity_mps": float(v),
                    "flow_area_m2": float(area),
                    "hydraulic_depth_m": float(depth),
                    "froude": float(v) / math.sqrt(9.80665 * float(depth)),
                }
            )

        validation = {
            "plan": plan,
            "units": units,
            "rs500_obstr_block_mode": obstruction_modes["500"],
            "steady_completion_marker": True,
            "error_warning_absent": True,
            "hdf_file": hdf_path.name,
        }
        return rows, validation


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    plan_map = read_plan_map()

    by_plan: dict[str, list[dict[str, float | str]]] = {}
    validations: list[dict[str, object]] = []
    for meta in plan_map:
        rows, validation = read_plan(meta["plan"])
        by_plan[meta["plan"]] = rows
        validations.append(validation)

    # Current-riverbed reference within each downstream boundary.
    current_refs: dict[tuple[str, str], dict[str, float | str]] = {}
    for meta in plan_map:
        if meta["case_id"] != "Current":
            continue
        for row in by_plan[meta["plan"]]:
            current_refs[(meta["boundary_id"], str(row["river_station"]))] = row

    detail_rows: list[dict[str, object]] = []
    for meta in plan_map:
        for row in by_plan[meta["plan"]]:
            station = str(row["river_station"])
            current = current_refs[(meta["boundary_id"], station)]
            detail_rows.append(
                {
                    **meta,
                    "river_station": station,
                    "wse_m": f"{float(row['wse_m']):.6f}",
                    "energy_grade_m": f"{float(row['energy_grade_m']):.6f}",
                    "velocity_mps": f"{float(row['velocity_mps']):.6f}",
                    "flow_area_m2": f"{float(row['flow_area_m2']):.3f}",
                    "froude": f"{float(row['froude']):.6f}",
                    "delta_wse_vs_current_same_boundary_m": f"{float(row['wse_m']) - float(current['wse_m']):.6f}",
                    "delta_energy_vs_current_same_boundary_m": f"{float(row['energy_grade_m']) - float(current['energy_grade_m']):.6f}",
                    "delta_velocity_vs_current_same_boundary_mps": f"{float(row['velocity_mps']) - float(current['velocity_mps']):.6f}",
                }
            )

    detail_path = RESULTS_DIR / "hecras_boundary_sensitivity.csv"
    with detail_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(detail_rows[0]))
        writer.writeheader()
        writer.writerows(detail_rows)

    validation_path = RESULTS_DIR / "hecras_boundary_sensitivity_validation.csv"
    with validation_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(validations[0]))
        writer.writeheader()
        writer.writerows(validations)

    grouped: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in detail_rows:
        grouped[(str(row["case_id"]), str(row["case_cn"]), str(row["river_station"]))].append(row)

    summary_rows: list[dict[str, object]] = []
    for (case_id, case_cn, station), rows in sorted(grouped.items()):
        rows.sort(key=lambda r: float(r["downstream_wse_m"]))
        wses = [float(row["wse_m"]) for row in rows]
        deltas = [float(row["delta_wse_vs_current_same_boundary_m"]) for row in rows]
        summary_rows.append(
            {
                "case_id": case_id,
                "case_cn": case_cn,
                "river_station": station,
                "downstream_wse_min_m": f"{min(float(row['downstream_wse_m']) for row in rows):.6f}",
                "downstream_wse_max_m": f"{max(float(row['downstream_wse_m']) for row in rows):.6f}",
                "absolute_wse_min_m": f"{min(wses):.6f}",
                "absolute_wse_max_m": f"{max(wses):.6f}",
                "absolute_wse_range_m": f"{max(wses) - min(wses):.6f}",
                "relative_effect_min_m": f"{min(deltas):.6f}",
                "relative_effect_max_m": f"{max(deltas):.6f}",
                "relative_effect_range_m": f"{max(deltas) - min(deltas):.6f}",
                "relative_effect_range_mm": f"{1000.0 * (max(deltas) - min(deltas)):.3f}",
            }
        )

    summary_path = RESULTS_DIR / "hecras_boundary_sensitivity_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary_rows[0]))
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"Validated {len(plan_map)} HEC-RAS boundary-sensitivity plans")
    print(f"Wrote {detail_path}")
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()
