#!/usr/bin/env python3
"""Build the auditable HEC-RAS 7.x 1D steady-flow project.

The purpose of this script is to create a small, auditable HEC-RAS project that
can be executed headlessly with Ras.exe -c or the Linux RasSteady engine after
HEC-RAS itself has generated the .r## run file.

Four directly comparable scenarios are represented with the same surveyed
cross-section geometry and different equivalent blocked-obstruction areas at
the bridge section:

    current riverbed      360 m2
    +0.5 m protection     380 m2
    +1.0 m protection     390 m2
    +2.0 m protection     410 m2

The blocked obstruction is centered on the deepest point of the bridge section.
Its lateral limits are solved so that, at the CAD-labelled flood level of
22.190 m, the integral of (WSE-ground) across the obstruction equals the target
blocked area.  The obstruction top is kept numerically above all modeled water
levels so the equivalent pier blockage cannot be artificially overtopped.

The fifth main plan replaces only RS 500 with the centre constrained
design-bed reconstruction and uses a 280 m2 obstruction.  Two additional
plans carry the local and distributed reconstruction sensitivity geometries;
they are not part of the main five-case numbering convention.

This is an equivalent 1D blockage representation, not a detailed bridge-pier
model.  It is deliberately kept simple so that the first HEC-RAS calculation
can be validated against the independent Python standard-step model.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
XS_DIR = ROOT / "data" / "processed" / "cross_sections"
DESIGN_BED_DIR = ROOT / "data" / "processed" / "design_bed"
OUT_DIR = ROOT / "hecras_model"
PROJECT_BASENAME = "GanjiangWestBridge"

Q = 26000.0
FLOOD_WSE = 22.190
# The lateral obstruction width is calibrated so its submerged area equals the
# tabulated blockage at FLOOD_WSE.  Its top must remain above every modeled
# water level; otherwise HEC-RAS would allow artificial over-obstruction flow as
# soon as WSE exceeds 22.190 m.  This is a numerical sentinel, not a claimed
# bridge-deck elevation.
EQUIVALENT_OBSTRUCTION_TOP = 50.0
DOWNSTREAM_WSE_INITIAL = 22.049342
MANNING_N = 0.030
EXPANSION = 0.30
CONTRACTION = 0.10

# The no-obstruction parser smoke test was completed against HEC-RAS 7.0.1 on
# 2026-08-30.  Generate the four intended engineering cases by default; each
# geometry now carries its case-specific equivalent blocked obstruction.
INCLUDE_BLOCKAGE = True

RIVER = "Ganjiang"
REACH = "WestBranch"

# HEC-RAS river station decreases downstream.  Reach lengths belong to each
# cross section and are distances from that section to the next downstream XS.
SECTIONS = [
    (1000.0, "西支上游500米.csv", 400.0),
    (600.0, "西支上游100米.csv", 100.0),
    (500.0, "西支桥下.csv", 100.0),
    (400.0, "西支下游100米.csv", 400.0),
    (0.0, "西支下游500米.csv", 0.0),
]

CASES = [
    # plan/geometry number, Chinese name, short id, blockage, RS 500 profile,
    # sensitivity flag
    (1, "现状河床线", "Current", 360.0, XS_DIR / "西支桥下.csv", False),
    (2, "0.5m防冲刷", "Protect05", 380.0, XS_DIR / "西支桥下.csv", False),
    (3, "1.0m防冲刷", "Protect10", 390.0, XS_DIR / "西支桥下.csv", False),
    (4, "2.0m防冲刷", "Protect20", 410.0, XS_DIR / "西支桥下.csv", False),
    (5, "设计河床线", "DesignBed", 280.0, DESIGN_BED_DIR / "西支桥下_设计河床.csv", False),
    (6, "设计河床线-局部型敏感性", "DesignLocal", 280.0, DESIGN_BED_DIR / "西支桥下_设计河床_局部型.csv", True),
    (7, "设计河床线-分布型敏感性", "DesignDistrib", 280.0, DESIGN_BED_DIR / "西支桥下_设计河床_分布型.csv", True),
]

Point = Tuple[float, float]


def read_profile(filename: str | Path) -> List[Point]:
    pts: List[Point] = []
    path = Path(filename)
    if not path.is_absolute():
        path = XS_DIR / path
    with path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            pts.append(
                (
                    float(row["station_m_raw_direction"]),
                    float(row["elevation_m"]),
                )
            )
    pts.sort(key=lambda p: p[0])
    return pts


def z_at(profile: Sequence[Point], x: float) -> float:
    if x <= profile[0][0]:
        return profile[0][1]
    if x >= profile[-1][0]:
        return profile[-1][1]
    for (x1, z1), (x2, z2) in zip(profile, profile[1:]):
        if x1 <= x <= x2:
            if x2 == x1:
                return min(z1, z2)
            t = (x - x1) / (x2 - x1)
            return z1 + t * (z2 - z1)
    raise RuntimeError("station interpolation failed")


def blocked_area(profile: Sequence[Point], left: float, right: float, top: float) -> float:
    """Exact piecewise-linear area between ground and obstruction top."""
    if right <= left:
        return 0.0
    cuts = [left, right]
    cuts.extend(x for x, _ in profile if left < x < right)
    cuts = sorted(set(cuts))
    area = 0.0
    for xa, xb in zip(cuts, cuts[1:]):
        za = z_at(profile, xa)
        zb = z_at(profile, xb)
        da = top - za
        db = top - zb
        dx = xb - xa
        if da <= 0 and db <= 0:
            continue
        if da >= 0 and db >= 0:
            area += dx * (da + db) / 2.0
            continue
        # Linear crossing where depth becomes zero.
        t = da / (da - db)
        xc = xa + t * dx
        if da > 0:
            area += (xc - xa) * da / 2.0
        else:
            area += (xb - xc) * db / 2.0
    return area


def obstruction_limits(profile: Sequence[Point], target_area: float, top: float) -> Tuple[float, float]:
    center = min(profile, key=lambda p: p[1])[0]
    max_half = min(center - profile[0][0], profile[-1][0] - center)
    lo, hi = 0.0, max_half
    if blocked_area(profile, center - hi, center + hi, top) < target_area:
        raise ValueError(f"Cannot fit blocked area {target_area} m2 around deepest point")
    for _ in range(80):
        half = 0.5 * (lo + hi)
        area = blocked_area(profile, center - half, center + half, top)
        if area < target_area:
            lo = half
        else:
            hi = half
    half = 0.5 * (lo + hi)
    return center - half, center + half


def fmt8(value: float) -> str:
    """HEC-RAS legacy geometry fields are nominally 8 chars wide."""
    # Prefer compact decimal representation while preserving sub-centimetre
    # geometry where possible.  Scientific notation is avoided for readability.
    candidates = [
        f"{value:8.3f}",
        f"{value:8.2f}",
        f"{value:8.1f}",
        f"{value:8.0f}",
    ]
    for s in candidates:
        if len(s) <= 8:
            return s
    raise ValueError(f"Value does not fit 8-character HEC-RAS field: {value}")


def fixed_values(values: Iterable[float], values_per_line: int) -> str:
    values = list(values)
    lines = []
    for i in range(0, len(values), values_per_line):
        lines.append("".join(fmt8(v) for v in values[i : i + values_per_line]))
    return "\n".join(lines)


def station_elevation_block(profile: Sequence[Point]) -> str:
    vals: List[float] = []
    for x, z in profile:
        vals.extend((x, z))
    # Five station/elevation pairs = 10 numeric fields per line.
    return fixed_values(vals, 10)


def geometry_text(title: str, blockage_m2: float, bridge_profile_path: Path | None = None) -> str:
    if bridge_profile_path is None:
        bridge_profile_path = XS_DIR / "西支桥下.csv"
    bridge_profile = read_profile(bridge_profile_path)
    obs_left, obs_right = obstruction_limits(bridge_profile, blockage_m2, FLOOD_WSE)

    lines = [
        f"Geom Title={title}",
        "Program Version=7.01",
        "Viewing Rectangle= 0 , 1000 , 1000 , 0",
        f"River Reach={RIVER:<16},{REACH:<16}",
        "Reach XY= 2",
        f"{0.0:16.3f}{0.0:16.3f}{1000.0:16.3f}{0.0:16.3f}",
        "Rch Text X Y=500,500",
        "Reverse River Text= 0",
        "",
    ]

    for rs, filename, reach_len in SECTIONS:
        profile = bridge_profile if math.isclose(rs, 500.0) else read_profile(filename)
        # HEC-RAS requires LOB / channel / ROB roughness regions for a normal
        # cross section.  Use actual profile stations for the bank locations so
        # no GUI-side interpolation is needed.  All three start with the same n
        # so this remains equivalent to a single composite roughness assumption.
        bank_left = profile[1][0]
        bank_right = profile[-2][0]
        mann_values = (
            profile[0][0], MANNING_N, 0.0,
            bank_left, MANNING_N, 0.0,
            bank_right, MANNING_N, 0.0,
        )

        lines.extend(
            [
                f"Type RM Length L Ch R = 1 ,{rs:g},{reach_len:g},{reach_len:g},{reach_len:g}",
                f"#Sta/Elev= {len(profile)}",
                station_elevation_block(profile),
                "#Mann= 3 , 0 , 0",
                fixed_values(mann_values, 9),
                f"Bank Sta={bank_left:.3f},{bank_right:.3f}",
                "XS Rating Curve= 0 ,0",
            ]
        )

        if INCLUDE_BLOCKAGE and math.isclose(rs, 500.0):
            lines.extend(
                [
                    "#Block Obstruct= 1",
                    fixed_values((obs_left, obs_right, EQUIVALENT_OBSTRUCTION_TOP), 9),
                ]
            )

        lines.extend(
            [
                f"Exp/Cntr={EXPANSION:g},{CONTRACTION:g}",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def flow_text(downstream_wse: float) -> str:
    return "\n".join(
        [
            "Flow Title=Q26000",
            "Program Version=7.01",
            "Number of Profiles= 1",
            "Profile Names=Q26000",
            f"River Rch & RM={RIVER},{REACH:<16},{SECTIONS[0][0]:g}",
            f"{Q:8.1f}",
            f"Boundary for River Rch & Prof#={RIVER},{REACH:<16}, 1",
            "Up Type= 0",
            "Dn Type= 1",
            f"Dn Known WS={downstream_wse:.6f}",
            "DSS Import StartDate=",
            "DSS Import StartTime=",
            "DSS Import EndDate=",
            "DSS Import EndTime=",
            "DSS Import GetInterval= 0",
            "DSS Import Interval=",
            "DSS Import GetPeak= 0",
            "DSS Import FillOption= 0",
            "",
        ]
    )


def plan_text(title: str, short_id: str, geom_number: int) -> str:
    return "\n".join(
        [
            f"Plan Title={title}",
            "Program Version=7.01",
            f"Short Identifier={short_id}",
            f"Geom File=g{geom_number:02d}",
            "Flow File=f01",
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


def project_text() -> str:
    lines = [
        "Proj Title=Ganjiang West Branch Bridge 1D",
        "Current Plan=p01",
        f"Default Exp/Contr={EXPANSION:g},{CONTRACTION:g}",
        "SI Units",
        "Default Tol=0.003",
        "Default Max Trials=40",
        "Default Flow Tol=0.001",
        "Default HTab Params= 100,20,20",
        "Default Infiltration= 0",
        "Default Poro=0",
        "Default Short ID=Plan",
    ]
    for number, _cn_name, short_id, _blockage, _profile, _sensitivity in CASES:
        lines.extend([f"Plan File=p{number:02d}", f"Plan Title={short_id}"])
    for number, _cn_name, short_id, _blockage, _profile, _sensitivity in CASES:
        lines.extend([f"Geom File=g{number:02d}", f"Geom Title={short_id}"])
    lines.extend(["Flow File=f01", "Flow Title=Q26000", ""])
    return "\n".join(lines)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    (OUT_DIR / f"{PROJECT_BASENAME}.prj").write_text(
        project_text(), encoding="ascii", newline="\r\n"
    )
    (OUT_DIR / f"{PROJECT_BASENAME}.f01").write_text(
        flow_text(DOWNSTREAM_WSE_INITIAL), encoding="ascii", newline="\r\n"
    )

    audit_rows = []
    for number, cn_name, short_id, blockage, bridge_profile_path, sensitivity in CASES:
        title = short_id
        gpath = OUT_DIR / f"{PROJECT_BASENAME}.g{number:02d}"
        ppath = OUT_DIR / f"{PROJECT_BASENAME}.p{number:02d}"
        gpath.write_text(
            geometry_text(title, blockage, bridge_profile_path), encoding="ascii", newline="\r\n"
        )
        ppath.write_text(
            plan_text(title, short_id, number), encoding="ascii", newline="\r\n"
        )
        bridge_profile = read_profile(bridge_profile_path)
        left, right = obstruction_limits(bridge_profile, blockage, FLOOD_WSE)
        gross_area = blocked_area(
            bridge_profile, bridge_profile[0][0], bridge_profile[-1][0], FLOOD_WSE
        )
        audit_rows.append(
            (
                number,
                cn_name,
                short_id,
                sensitivity,
                bridge_profile_path.relative_to(ROOT),
                gross_area,
                blockage,
                gross_area - blockage,
                left,
                right,
                blocked_area(bridge_profile, left, right, FLOOD_WSE),
            )
        )

    with (OUT_DIR / "blockage_audit.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "plan",
                "case",
                "short_id",
                "sensitivity_plan",
                "bridge_profile",
                "gross_area_at_wse_22.190_m2",
                "target_blockage_m2",
                "net_area_at_wse_22.190_m2",
                "left_station_m",
                "right_station_m",
                "recomputed_blockage_m2",
            ]
        )
        for row in audit_rows:
            w.writerow(
                [
                    f"p{row[0]:02d}",
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                    f"{row[5]:.6f}",
                    f"{row[6]:.3f}",
                    f"{row[7]:.6f}",
                    f"{row[8]:.6f}",
                    f"{row[9]:.6f}",
                    f"{row[10]:.6f}",
                ]
            )

    print(f"Built HEC-RAS project in {OUT_DIR}")
    for row in audit_rows:
        print(
            f"p{row[0]:02d} {row[1]:18s}: gross={row[5]:.3f}, "
            f"blockage={row[10]:.3f}, net={row[7]:.3f} m2"
        )


if __name__ == "__main__":
    main()
