#!/usr/bin/env python3
"""Reject stale boundary-sensitivity HDFs for the CAD01 design-bed case.

The boundary project reuses g05 for three downstream Known-WS values.  Old HDF
files can survive an input rebuild, so plan names alone are not evidence that
p05/p10/p15 were computed with the active CAD01-direct RS=500 geometry.
"""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np

import audit_hecras_design_bed_geometry as design_audit

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "models" / "boundary_sensitivity"
PROJECT_BASENAME = "GanjiangWestBridgeBoundary"
DESIGN_PLANS = {
    "p05": "Low",
    "p10": "Base",
    "p15": "High",
}


def audit_plan(plan: str, boundary_id: str, source: np.ndarray) -> None:
    hdf_path = MODEL_DIR / f"{PROJECT_BASENAME}.{plan}.hdf"
    if not hdf_path.is_file():
        raise FileNotFoundError(f"Missing computed DesignBedCAD boundary result: {hdf_path}")

    with h5py.File(hdf_path, "r") as hdf:
        required = [design_audit.XS_ATTR, design_audit.XS_INFO, design_audit.XS_VALUES]
        missing = [name for name in required if name not in hdf]
        if missing:
            raise RuntimeError(f"{plan}/{boundary_id}: HDF lacks geometry datasets: {missing}")

        units = design_audit.decode(hdf.attrs.get("Units System", ""))
        if units != "SI Units":
            raise RuntimeError(f"{plan}/{boundary_id}: expected SI Units, got {units!r}")

        attributes = hdf[design_audit.XS_ATTR][:]
        info = hdf[design_audit.XS_INFO][:]
        values = np.asarray(hdf[design_audit.XS_VALUES][:], dtype=float)
        stations = [design_audit.decode(row["RS"]) for row in attributes]
        try:
            index = stations.index("500")
        except ValueError as exc:
            raise RuntimeError(f"{plan}/{boundary_id}: RS=500 not found in HDF geometry") from exc

        start, count = design_audit.row_start_count(info[index])
        hdf_points = np.asarray(values[start : start + count, :2], dtype=float)
        if len(hdf_points) != len(source):
            raise RuntimeError(
                f"{plan}/{boundary_id}: RS500 has {len(hdf_points)} points; "
                f"active CAD01 source has {len(source)}"
            )

        max_station_error = float(np.max(np.abs(hdf_points[:, 0] - source[:, 0])))
        max_elevation_error = float(np.max(np.abs(hdf_points[:, 1] - source[:, 1])))
        if max_station_error > 5e-5 or max_elevation_error > 5e-6:
            raise RuntimeError(
                f"{plan}/{boundary_id}: stale DesignBedCAD HDF geometry; "
                f"station error={max_station_error:.6g} m, "
                f"elevation error={max_elevation_error:.6g} m"
            )

        obstruction_modes = {
            design_audit.decode(row["RS"]): int(row["Obstr Block Mode"]) for row in attributes
        }
        if obstruction_modes.get("500") != 1:
            raise RuntimeError(f"{plan}/{boundary_id}: RS500 blocked obstruction is not enabled")

        messages = design_audit.decode(hdf["Results/Summary/Compute Messages (text)"][0])
        lower = messages.lower()
        if "Finished Steady Flow Simulation" not in messages:
            raise RuntimeError(f"{plan}/{boundary_id}: completion marker absent")
        if "warning" in lower or "error" in lower:
            raise RuntimeError(f"{plan}/{boundary_id}: compute messages contain warning/error")

    print(
        f"[PASS] {plan} DesignBedCAD_{boundary_id}: CAD01 geometry verified; "
        f"max station error={max_station_error:.3g} m, "
        f"max elevation error={max_elevation_error:.3g} m"
    )


def main() -> None:
    source = design_audit.read_source()
    for plan, boundary_id in DESIGN_PLANS.items():
        audit_plan(plan, boundary_id, source)


if __name__ == "__main__":
    main()
