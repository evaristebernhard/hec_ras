#!/usr/bin/env python3
"""Build an isolated HEC-RAS downstream-boundary sensitivity project.

This project reuses the five main geometries from build_hecras_project.py but
runs each one at three downstream known-water-surface elevations: baseline
+/-0.50 m.  It is intentionally written to a separate directory so the
active five-plan engineering model is never overwritten.
"""

from __future__ import annotations

import csv
from pathlib import Path

import build_hecras_project as base

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "models" / "boundary_sensitivity"
PROJECT_BASENAME = "GanjiangWestBridgeBoundary"

BOUNDARIES = [
    (1, "Low", base.DOWNSTREAM_WSE_INITIAL - 0.50),
    (2, "Base", base.DOWNSTREAM_WSE_INITIAL),
    (3, "High", base.DOWNSTREAM_WSE_INITIAL + 0.50),
]

MAIN_CASES = base.CASES[:5]

# HEC-RAS steady-flow plan Short Identifiers are limited to 16 characters.
# Keep full descriptive Plan Titles, but compact only the case token used in
# Short Identifier when necessary.
SHORT_CASE_IDS = {
    "DesignBedCAD": "DBedCAD",
}


def boundary_short_id(case_id: str, boundary_id: str) -> str:
    short_case = SHORT_CASE_IDS.get(case_id, case_id)
    short_id = f"{short_case}_{boundary_id}"
    if len(short_id) > 16:
        raise ValueError(f"HEC-RAS Short Identifier exceeds 16 characters: {short_id}")
    return short_id


def plan_text(title: str, short_id: str, geom_number: int, flow_number: int) -> str:
    return "\n".join(
        [
            f"Plan Title={title}",
            "Program Version=7.01",
            f"Short Identifier={short_id}",
            f"Geom File=g{geom_number:02d}",
            f"Flow File=f{flow_number:02d}",
            "Subcritical Flow",
            "Run HTab=-1",
            "Run RAS=-1",
            "Run UNet= 0",
            "Run Sediment= 0",
            "Run PostProcess= 0",
            "Run WQNet= 0",
            "Std Step Tol= 0.003",
            "Critical Tol= 0.003",
            "Num of Std Step Trials= 40",
            "Max Error Tol= 0.03",
            "Flow Tol Ratio= 0.001",
            "Split Flow NTrial= 30",
            "Split Flow Tol= 0.02",
            "Split Flow Ratio= 0.02",
            "Log Output Level= 1",
            "Friction Slope Method= 1",
            "Parabolic Critical Depth",
            "Global Log Level= 0",
            "CheckData=True",
            "Encroach Param=-1 ,0,0, 0",
            "",
        ]
    )


def project_text(plan_rows: list[dict[str, object]]) -> str:
    lines = [
        "Proj Title=Ganjiang West Branch Bridge Boundary Sensitivity",
        "Current Plan=p01",
        f"Default Exp/Contr={base.EXPANSION:g},{base.CONTRACTION:g}",
        "SI Units",
        "Default Tol=0.003",
        "Default Max Trials=40",
        "Default Flow Tol=0.001",
        "Default HTab Params= 100,20,20",
        "Default Infiltration= 0",
        "Default Poro=0",
        "Default Short ID=Plan",
    ]
    for row in plan_rows:
        title = f"{row['case_id']}_{row['boundary_id']}"
        lines.extend([f"Plan File={row['plan']}", f"Plan Title={title}"])
    for case_number, _cn_name, short_id, _blockage, _profile in MAIN_CASES:
        lines.extend([f"Geom File=g{case_number:02d}", f"Geom Title={short_id}"])
    for flow_number, boundary_id, _wse in BOUNDARIES:
        lines.extend([f"Flow File=f{flow_number:02d}", f"Flow Title=Q26000_{boundary_id}"])
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Remove only generated text inputs.  Computed HDF/run artifacts are live
    # evidence and must never be erased implicitly by an input builder.
    input_patterns = [
        f"{PROJECT_BASENAME}.f??",
        f"{PROJECT_BASENAME}.g??",
        f"{PROJECT_BASENAME}.p??",
        f"{PROJECT_BASENAME}.prj",
    ]
    for pattern in input_patterns:
        for existing in OUT_DIR.glob(pattern):
            if existing.is_file():
                existing.unlink()

    # The five geometry files are identical to the main five-case model.
    for case_number, _cn_name, short_id, blockage, profile_path in MAIN_CASES:
        path = OUT_DIR / f"{PROJECT_BASENAME}.g{case_number:02d}"
        path.write_text(
            base.geometry_text(short_id, blockage, profile_path),
            encoding="ascii",
            newline="\r\n",
        )

    for flow_number, boundary_id, downstream_wse in BOUNDARIES:
        path = OUT_DIR / f"{PROJECT_BASENAME}.f{flow_number:02d}"
        flow_text = base.flow_text(downstream_wse).replace(
            "Flow Title=Q26000",
            f"Flow Title=Q26000_{boundary_id}",
            1,
        )
        path.write_text(flow_text, encoding="ascii", newline="\r\n")

    plan_rows: list[dict[str, object]] = []
    plan_number = 0
    for flow_number, boundary_id, downstream_wse in BOUNDARIES:
        for case_number, cn_name, case_id, blockage, _profile_path in MAIN_CASES:
            plan_number += 1
            plan = f"p{plan_number:02d}"
            short_id = boundary_short_id(case_id, boundary_id)
            title = f"{case_id}_{boundary_id}"
            (OUT_DIR / f"{PROJECT_BASENAME}.{plan}").write_text(
                plan_text(title, short_id, case_number, flow_number),
                encoding="ascii",
                newline="\r\n",
            )
            plan_rows.append(
                {
                    "plan": plan,
                    "short_id": short_id,
                    "case_number": case_number,
                    "case_id": case_id,
                    "case_cn": cn_name,
                    "blockage_m2": f"{blockage:.3f}",
                    "geometry": f"g{case_number:02d}",
                    "flow": f"f{flow_number:02d}",
                    "boundary_id": boundary_id,
                    "downstream_wse_m": f"{downstream_wse:.6f}",
                    "boundary_offset_from_base_m": f"{downstream_wse - base.DOWNSTREAM_WSE_INITIAL:.6f}",
                }
            )

    (OUT_DIR / f"{PROJECT_BASENAME}.prj").write_text(
        project_text(plan_rows), encoding="ascii", newline="\r\n"
    )

    map_path = OUT_DIR / "sensitivity_plan_map.csv"
    with map_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(plan_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(plan_rows)

    print(f"Built {len(plan_rows)} plans in {OUT_DIR}")
    for flow_number, boundary_id, downstream_wse in BOUNDARIES:
        print(f"  f{flow_number:02d} {boundary_id}: downstream WSE={downstream_wse:.6f} m")


if __name__ == "__main__":
    main()
