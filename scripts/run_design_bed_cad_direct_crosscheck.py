#!/usr/bin/env python3
"""Compute a transparent standard-step cross-check for CAD-direct design bed.

This does not impersonate a HEC-RAS result.  It uses the same discharge,
roughness, reach lengths, downstream Known WS and equivalent obstruction
areas as the HEC-RAS project, while swapping only the RS 500 profile.
"""

from __future__ import annotations

import csv
from pathlib import Path

import run_steady_1d_cases as steady


ROOT = Path(__file__).resolve().parents[1]
DESIGN_PROFILE = ROOT / "data" / "processed" / "design_bed" / "西支桥下_设计河床.csv"
OUT_DIR = ROOT / "results" / "cross_checks"
CASES = (
    ("Current", "现状河床线", 360.0, False),
    ("DesignBedCAD", "设计河床线-CAD直接提取", 280.0, True),
)


def sections(use_design_bed: bool):
    values = steady.load_sections()
    if use_design_bed:
        river_m, _name, _profile = values[2]
        values[2] = (
            river_m,
            "西支桥下_设计河床_CAD直接提取",
            steady.read_profile(DESIGN_PROFILE),
        )
    return values


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    current_sections = sections(False)
    downstream_wse = steady.calibrate_downstream_wse(current_sections, steady.DEFAULT_N)
    runs = {
        case_id: steady.run_profile(
            sections(use_design), downstream_wse, steady.DEFAULT_N, blockage
        )
        for case_id, _case_cn, blockage, use_design in CASES
    }
    current_by_river_m = {state.river_m: state for state in runs["Current"]}

    detail_fields = [
        "solver",
        "case_id",
        "case",
        "river_m",
        "section",
        "wse_m",
        "delta_wse_vs_current_m",
        "energy_m",
        "velocity_mps",
        "effective_area_m2",
        "froude",
        "blockage_m2",
        "downstream_known_ws_m",
    ]
    detail_rows = []
    for case_id, case_cn, blockage, _use_design in CASES:
        for state in runs[case_id]:
            reference = current_by_river_m[state.river_m]
            detail_rows.append(
                {
                    "solver": "python_standard_step_crosscheck",
                    "case_id": case_id,
                    "case": case_cn,
                    "river_m": f"{state.river_m:.1f}",
                    "section": state.name,
                    "wse_m": f"{state.wse:.6f}",
                    "delta_wse_vs_current_m": f"{state.wse-reference.wse:.6f}",
                    "energy_m": f"{state.energy:.6f}",
                    "velocity_mps": f"{state.velocity:.6f}",
                    "effective_area_m2": f"{state.area_eff:.3f}",
                    "froude": f"{state.froude:.6f}",
                    "blockage_m2": f"{blockage:.3f}",
                    "downstream_known_ws_m": f"{downstream_wse:.6f}",
                }
            )

    detail_path = OUT_DIR / "design_bed_cad_direct_standard_step.csv"
    with detail_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=detail_fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(detail_rows)

    # HEC-RAS RS 600 / 500 / 1000 correspond to river_m -100 / 0 / -500.
    summary_rows = []
    design_by_river_m = {state.river_m: state for state in runs["DesignBedCAD"]}
    for hec_rs, river_m, role in ((600, -100.0, "upstream_100m_backwater"),
                                  (500, 0.0, "bridge_local_state"),
                                  (1000, -500.0, "upstream_500m_backwater")):
        current = current_by_river_m[river_m]
        design = design_by_river_m[river_m]
        summary_rows.append(
            {
                "solver": "python_standard_step_crosscheck",
                "river_station": hec_rs,
                "role": role,
                "current_wse_m": f"{current.wse:.6f}",
                "design_bed_cad_wse_m": f"{design.wse:.6f}",
                "backwater_height_delta_wse_m": f"{design.wse-current.wse:.6f}",
                "backwater_height_mm": f"{(design.wse-current.wse)*1000.0:.1f}",
                "status": "CROSSCHECK_NOT_HECRAS",
            }
        )
    summary_path = OUT_DIR / "design_bed_cad_direct_backwater_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(summary_rows)

    rs600 = summary_rows[0]
    print(
        "CAD-direct standard-step RS 600 backwater: "
        f"{float(rs600['backwater_height_delta_wse_m']):+.6f} m "
        f"({float(rs600['backwater_height_mm']):+.1f} mm)"
    )
    print(f"Downstream Known WS: {downstream_wse:.6f} m")


if __name__ == "__main__":
    main()
