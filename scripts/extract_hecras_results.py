#!/usr/bin/env python3
"""Read the five active HEC-RAS HDF results and write two simple CSV files."""

from __future__ import annotations

import csv
import math
from pathlib import Path

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "models" / "main"
RESULTS_DIR = ROOT / "results"
DESIGN_BED = ROOT / "data" / "processed" / "design_bed" / "西支桥下_设计河床.csv"

CASES = [
    ("p01", "Current", "现状河床线", 360.0),
    ("p02", "Protect05", "0.5m防冲刷", 380.0),
    ("p03", "Protect10", "1.0m防冲刷", 390.0),
    ("p04", "Protect20", "2.0m防冲刷", 410.0),
    ("p05", "DesignBedCAD", "设计河床线-CAD01直接提取", 280.0),
]

OUTPUT_BASE = (
    "Results/Steady/Output/Output Blocks/Base Output/"
    "Steady Profiles/Cross Sections"
)
OUTPUT_XS = "Results/Steady/Output/Geometry Info/Cross Section Attributes"
GEOM_XS = "Geometry/Cross Sections/Attributes"
GEOM_INFO = "Geometry/Cross Sections/Station Elevation Info"
GEOM_VALUES = "Geometry/Cross Sections/Station Elevation Values"


def decode(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    return str(value).strip()


def row_start_count(row: object) -> tuple[int, int]:
    dtype = getattr(row, "dtype", None)
    if dtype is not None and dtype.names:
        names = list(dtype.names)
        start = next((name for name in names if "start" in name.lower()), names[0])
        count = next(
            (name for name in names if "count" in name.lower() or "length" in name.lower()),
            names[1],
        )
        return int(row[start]), int(row[count])
    values = np.asarray(row).reshape(-1)
    return int(values[0]), int(values[1])


def validate_design_bed_geometry(hdf: h5py.File) -> None:
    """Make sure p05 HDF really contains the active CAD01 design bed."""
    with DESIGN_BED.open(encoding="utf-8-sig", newline="") as stream:
        expected = np.asarray(
            [
                (float(row["station_m_raw_direction"]), float(row["elevation_m"]))
                for row in csv.DictReader(stream)
            ],
            dtype=float,
        )
    expected = np.round(expected[np.argsort(expected[:, 0])], 3)

    attrs = hdf[GEOM_XS][:]
    stations = [decode(row["RS"]) for row in attrs]
    if "500" not in stations:
        raise RuntimeError("p05: RS500 not found in HDF geometry")
    index = stations.index("500")

    start, count = row_start_count(hdf[GEOM_INFO][index])
    actual = np.asarray(hdf[GEOM_VALUES][start : start + count, :2], dtype=float)

    if actual.shape != expected.shape:
        raise RuntimeError(
            f"p05: RS500 geometry point count differs: HDF={len(actual)}, CAD01={len(expected)}"
        )

    station_error = float(np.max(np.abs(actual[:, 0] - expected[:, 0])))
    elevation_error = float(np.max(np.abs(actual[:, 1] - expected[:, 1])))
    if station_error > 5e-5 or elevation_error > 5e-6:
        raise RuntimeError(
            "p05 HDF is not the current CAD01 design bed: "
            f"station error={station_error:.6g} m, elevation error={elevation_error:.6g} m"
        )


def read_plan(plan: str) -> list[dict[str, float | str]]:
    path = MODEL_DIR / f"GanjiangWestBridge.{plan}.hdf"
    if not path.exists():
        raise FileNotFoundError(f"Missing HEC-RAS result: {path}")

    with h5py.File(path, "r") as hdf:
        units = decode(hdf.attrs.get("Units System", ""))
        if units != "SI Units":
            raise RuntimeError(f"{plan}: expected SI Units, got {units!r}")

        geom = hdf[GEOM_XS][:]
        obstruction_modes = {decode(row["RS"]): int(row["Obstr Block Mode"]) for row in geom}
        if obstruction_modes.get("500") != 1:
            raise RuntimeError(f"{plan}: RS500 blocked obstruction is not enabled")

        if plan == "p05":
            validate_design_bed_geometry(hdf)

        messages = decode(hdf["Results/Summary/Compute Messages (text)"][0])
        if "Finished Steady Flow Simulation" not in messages:
            raise RuntimeError(f"{plan}: HEC-RAS simulation did not finish")
        lower = messages.lower()
        if "error" in lower or "warning" in lower:
            raise RuntimeError(f"{plan}: HEC-RAS compute messages contain warning/error")

        xs = hdf[OUTPUT_XS][:]
        stations = [decode(row["Station"]) for row in xs]
        wse = hdf[f"{OUTPUT_BASE}/Water Surface"][0]
        energy = hdf[f"{OUTPUT_BASE}/Energy Grade"][0]
        flow = hdf[f"{OUTPUT_BASE}/Flow"][0]
        extra = f"{OUTPUT_BASE}/Additional Variables"
        velocity = hdf[f"{extra}/Velocity Total"][0]
        area = hdf[f"{extra}/Area Flow Total"][0]
        depth = hdf[f"{extra}/Hydraulic Depth Total"][0]

        return [
            {
                "river_station": station,
                "wse_m": float(z),
                "energy_grade_m": float(e),
                "flow_m3s": float(q),
                "velocity_mps": float(v),
                "flow_area_m2": float(a),
                "hydraulic_depth_m": float(d),
                "froude": float(v) / math.sqrt(9.80665 * float(d)),
            }
            for station, z, e, q, v, a, d in zip(
                stations, wse, energy, flow, velocity, area, depth
            )
        ]


def by_station(rows: list[dict[str, float | str]], station: str) -> dict[str, float | str]:
    return next(row for row in rows if str(row["river_station"]) == station)


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    data: dict[str, list[dict[str, float | str]]] = {}
    for plan, _short_id, _case, _blockage in CASES:
        data[plan] = read_plan(plan)

    current = {str(row["river_station"]): row for row in data["p01"]}

    detail_rows: list[dict[str, object]] = []
    for plan, short_id, case, blockage in CASES:
        for row in data[plan]:
            station = str(row["river_station"])
            baseline = current[station]
            detail_rows.append(
                {
                    "plan": plan,
                    "short_id": short_id,
                    "case": case,
                    "blockage_m2": f"{blockage:.3f}",
                    "river_station": station,
                    "wse_m": f"{float(row['wse_m']):.6f}",
                    "energy_grade_m": f"{float(row['energy_grade_m']):.6f}",
                    "flow_m3s": f"{float(row['flow_m3s']):.3f}",
                    "velocity_mps": f"{float(row['velocity_mps']):.6f}",
                    "flow_area_m2": f"{float(row['flow_area_m2']):.3f}",
                    "froude": f"{float(row['froude']):.6f}",
                    "delta_wse_vs_current_m": f"{float(row['wse_m']) - float(baseline['wse_m']):.6f}",
                }
            )

    detail_path = RESULTS_DIR / "hecras_five_cases.csv"
    with detail_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(detail_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(detail_rows)

    summary_rows: list[dict[str, object]] = []
    current_600 = by_station(data["p01"], "600")
    for plan, short_id, case, blockage in CASES:
        rs600 = by_station(data[plan], "600")
        rs500 = by_station(data[plan], "500")
        summary_rows.append(
            {
                "plan": plan,
                "short_id": short_id,
                "case": case,
                "blockage_m2": f"{blockage:.3f}",
                "rs600_wse_m": f"{float(rs600['wse_m']):.6f}",
                "rs600_delta_wse_vs_current_mm": f"{1000.0 * (float(rs600['wse_m']) - float(current_600['wse_m'])):.3f}",
                "rs500_wse_m": f"{float(rs500['wse_m']):.6f}",
                "rs500_velocity_mps": f"{float(rs500['velocity_mps']):.6f}",
                "rs500_flow_area_m2": f"{float(rs500['flow_area_m2']):.3f}",
                "rs500_froude": f"{float(rs500['froude']):.6f}",
            }
        )

    summary_path = RESULTS_DIR / "hecras_five_cases_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"Wrote {detail_path}")
    print(f"Wrote {summary_path}")
    for row in summary_rows:
        print(
            f"{row['plan']} {row['short_id']}: "
            f"RS600 ΔWSE={row['rs600_delta_wse_vs_current_mm']} mm, "
            f"RS500 V={row['rs500_velocity_mps']} m/s"
        )


if __name__ == "__main__":
    main()
