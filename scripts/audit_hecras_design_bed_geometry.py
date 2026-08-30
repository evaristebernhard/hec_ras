#!/usr/bin/env python3
"""Audit that computed HEC-RAS p05 actually contains the CAD-direct design bed.

The active design-bed source is ``data/processed/design_bed/西支桥下_设计河床.csv``,
recovered directly from CAD 01.  This script prevents a stale p05 HDF from being
mistaken for current evidence after model inputs have changed.

It compares the RS=500 station/elevation values embedded in the computed HDF
against the active source rounded to the 0.001 m precision written to the legacy
HEC-RAS geometry text.  When the geometry matches and the HDF compute messages
pass the standard checks, it also exports the p05 hydraulic state and the
backwater relative to the frozen validated p01 baseline.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import h5py
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "models" / "main"
RESULTS_DIR = ROOT / "results"
SOURCE = ROOT / "data" / "processed" / "design_bed" / "西支桥下_设计河床.csv"
HDF_PATH = MODEL_DIR / "GanjiangWestBridge.p05.hdf"
BASELINE = RESULTS_DIR / "hecras_steady_four_cases_baseline_v2_20260830.csv"
AUDIT_OUT = RESULTS_DIR / "hecras_design_bed_cad_direct_hdf_audit.csv"
BACKWATER_OUT = RESULTS_DIR / "hecras_design_bed_cad_direct_backwater.csv"

XS_ATTR = "Geometry/Cross Sections/Attributes"
XS_INFO = "Geometry/Cross Sections/Station Elevation Info"
XS_VALUES = "Geometry/Cross Sections/Station Elevation Values"
OUTPUT_XS_ATTR = "Results/Steady/Output/Geometry Info/Cross Section Attributes"
OUTPUT_BASE = (
    "Results/Steady/Output/Output Blocks/Base Output/"
    "Steady Profiles/Cross Sections"
)


def decode(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    return str(value).strip()


def read_source() -> np.ndarray:
    with SOURCE.open(encoding="utf-8-sig") as stream:
        points = [
            (float(row["station_m_raw_direction"]), float(row["elevation_m"]))
            for row in csv.DictReader(stream)
        ]
    points.sort()
    # build_hecras_project.py writes these values with three decimals.
    return np.round(np.asarray(points, dtype=float), 3)


def read_p01_baseline() -> dict[str, float]:
    with BASELINE.open(encoding="utf-8-sig") as stream:
        return {
            row["river_station"]: float(row["wse_m"])
            for row in csv.DictReader(stream)
            if row["plan"] == "p01"
        }


def row_start_count(row: np.void | np.ndarray) -> tuple[int, int]:
    if getattr(row, "dtype", None) is not None and row.dtype.names:
        names = list(row.dtype.names)
        lowered = {name.lower(): name for name in names}
        start_name = next((lowered[k] for k in lowered if "start" in k), names[0])
        count_name = next((lowered[k] for k in lowered if "count" in k or "length" in k), names[1])
        return int(row[start_name]), int(row[count_name])
    values = np.asarray(row).reshape(-1)
    if len(values) < 2:
        raise RuntimeError("Station Elevation Info row has fewer than two values")
    return int(values[0]), int(values[1])


def write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty {path}")
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    source = read_source()
    baseline = read_p01_baseline()

    with h5py.File(HDF_PATH, "r") as hdf:
        required = [XS_ATTR, XS_INFO, XS_VALUES, OUTPUT_XS_ATTR]
        missing = [name for name in required if name not in hdf]
        if missing:
            raise RuntimeError(f"p05 HDF lacks required geometry datasets: {missing}")

        units = decode(hdf.attrs.get("Units System", ""))
        if units != "SI Units":
            raise RuntimeError(f"p05 expected SI Units, got {units!r}")

        attributes = hdf[XS_ATTR][:]
        info = hdf[XS_INFO][:]
        values = np.asarray(hdf[XS_VALUES][:], dtype=float)
        stations = [decode(row["RS"]) for row in attributes]
        try:
            index = stations.index("500")
        except ValueError as exc:
            raise RuntimeError("RS=500 not found in p05 HDF geometry") from exc
        start, count = row_start_count(info[index])
        hdf_points = np.asarray(values[start : start + count, :2], dtype=float)

        if len(hdf_points) != len(source):
            raise RuntimeError(
                f"p05 RS500 has {len(hdf_points)} points; active CAD-direct source has {len(source)}"
            )
        max_station_error = float(np.max(np.abs(hdf_points[:, 0] - source[:, 0])))
        max_elevation_error = float(np.max(np.abs(hdf_points[:, 1] - source[:, 1])))
        # The legacy geometry text is written to 0.001 m and HEC-RAS stores the
        # parsed values as finite-precision floats.  Tens of micrometres in the
        # station coordinate are therefore expected and are far below source
        # precision; centimetre- or millimetre-scale drift would not be.
        station_tolerance = 5e-5
        elevation_tolerance = 5e-6
        geometry_match = (
            max_station_error <= station_tolerance
            and max_elevation_error <= elevation_tolerance
        )
        if not geometry_match:
            raise RuntimeError(
                "p05 HDF geometry is stale or differs from CAD-direct source: "
                f"max station error={max_station_error:.6g} m, "
                f"max elevation error={max_elevation_error:.6g} m"
            )

        obstruction_modes = {
            decode(row["RS"]): int(row["Obstr Block Mode"]) for row in attributes
        }
        if obstruction_modes.get("500") != 1:
            raise RuntimeError("p05 HDF RS500 obstruction block mode is not enabled")

        messages = decode(hdf["Results/Summary/Compute Messages (text)"][0])
        completed = "Finished Steady Flow Simulation" in messages
        clean_messages = "warning" not in messages.lower() and "error" not in messages.lower()
        if not completed or not clean_messages:
            raise RuntimeError("p05 HDF compute-message validation failed")

        out_xs = hdf[OUTPUT_XS_ATTR][:]
        out_stations = [decode(row["Station"]) for row in out_xs]
        wse = hdf[f"{OUTPUT_BASE}/Water Surface"][0]
        energy = hdf[f"{OUTPUT_BASE}/Energy Grade"][0]
        additional = f"{OUTPUT_BASE}/Additional Variables"
        velocity = hdf[f"{additional}/Velocity Total"][0]
        area = hdf[f"{additional}/Area Flow Total"][0]
        depth = hdf[f"{additional}/Hydraulic Depth Total"][0]

        state = {
            station: {
                "wse": float(z),
                "energy": float(e),
                "velocity": float(v),
                "area": float(a),
                "depth": float(d),
            }
            for station, z, e, v, a, d in zip(out_stations, wse, energy, velocity, area, depth)
        }

    audit_rows = [
        {
            "check": "p05_geometry_source",
            "expected": "CAD 01 direct construction-period ground line",
            "actual": str(SOURCE.relative_to(ROOT)),
            "difference": "0",
            "status": "PASS",
        },
        {
            "check": "rs500_point_count",
            "expected": len(source),
            "actual": len(hdf_points),
            "difference": len(hdf_points) - len(source),
            "status": "PASS",
        },
        {
            "check": "rs500_station_max_abs_error_m",
            "expected": "<=5e-5",
            "actual": f"{max_station_error:.9g}",
            "difference": f"{max_station_error:.9g}",
            "status": "PASS",
        },
        {
            "check": "rs500_elevation_max_abs_error_m",
            "expected": "<=5e-6",
            "actual": f"{max_elevation_error:.9g}",
            "difference": f"{max_elevation_error:.9g}",
            "status": "PASS",
        },
        {
            "check": "rs500_obstruction_mode",
            "expected": 1,
            "actual": 1,
            "difference": 0,
            "status": "PASS",
        },
        {
            "check": "steady_compute_messages",
            "expected": "finished; no warning/error",
            "actual": "finished; no warning/error",
            "difference": "0",
            "status": "PASS",
        },
    ]
    write_rows(AUDIT_OUT, audit_rows)

    backwater_rows: list[dict[str, object]] = []
    for station, role in (("600", "upstream_100m_backwater"), ("500", "bridge_local_state"), ("1000", "upstream_500m_backwater")):
        if station not in state or station not in baseline:
            continue
        p05 = state[station]
        delta = p05["wse"] - baseline[station]
        froude = p05["velocity"] / math.sqrt(9.80665 * p05["depth"])
        backwater_rows.append(
            {
                "solver": "HEC-RAS 7.0.1",
                "design_plan": "p05",
                "geometry_source": "CAD01_direct",
                "river_station": station,
                "role": role,
                "current_baseline_wse_m": f"{baseline[station]:.6f}",
                "design_bed_wse_m": f"{p05['wse']:.6f}",
                "delta_wse_design_minus_current_m": f"{delta:.6f}",
                "delta_wse_mm": f"{delta*1000.0:.1f}",
                "energy_grade_m": f"{p05['energy']:.6f}",
                "velocity_mps": f"{p05['velocity']:.6f}",
                "flow_area_m2": f"{p05['area']:.3f}",
                "froude": f"{froude:.6f}",
                "hdf_geometry_match": True,
            }
        )
    write_rows(BACKWATER_OUT, backwater_rows)

    rs600 = next(row for row in backwater_rows if row["river_station"] == "600")
    print(
        "[PASS] p05 HDF matches CAD-direct design bed; "
        f"RS600 delta={float(rs600['delta_wse_design_minus_current_m']):+.6f} m "
        f"({float(rs600['delta_wse_mm']):+.1f} mm)"
    )


if __name__ == "__main__":
    main()
