#!/usr/bin/env python3
"""Build the smallest conventional HEC-RAS 7.0.1 steady 1D project.

This is intentionally a *format qualification* project:
- one river/reach
- five extracted cross sections
- one steady profile, Q=26000 m3/s
- one known downstream WSE
- no blocked obstruction yet

Once HEC-RAS accepts this project and generates the steady run file, the
blocked-obstruction variants are added as a separate step.  Keeping blockage
out of the first qualification run separates file-format problems from the
hydraulic scenario definition.
"""
from __future__ import annotations

import csv
import shutil
from pathlib import Path
from typing import Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
XS_DIR = ROOT / "data" / "processed" / "cross_sections"
OUT = ROOT / "hecras_validated"
NAME = "GanjiangWestBridge"

Q = 26000.0
DOWNSTREAM_WSE = 22.049342
N = 0.030

RIVER = "Ganjiang"
REACH = "WestBranch"

# HEC-RAS river station decreases downstream.  Reach lengths are distances to
# the next downstream section.
SECTIONS = [
    (1000.0, "西支上游500米.csv", 400.0),
    (600.0, "西支上游100米.csv", 100.0),
    (500.0, "西支桥下.csv", 100.0),
    (400.0, "西支下游100米.csv", 400.0),
    (0.0, "西支下游500米.csv", 0.0),
]


def read_profile(filename: str) -> List[Tuple[float, float]]:
    points: List[Tuple[float, float]] = []
    with (XS_DIR / filename).open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            points.append(
                (float(row["station_m_raw_direction"]), float(row["elevation_m"]))
            )
    points.sort()
    return points


def field8(value: float) -> str:
    """HEC-RAS legacy station/elevation fields are 8 characters wide."""
    for precision in (3, 2, 1, 0):
        s = f"{value:8.{precision}f}"
        if len(s) <= 8:
            return s
    raise ValueError(f"Cannot represent {value} in an 8-character HEC-RAS field")


def fixed8(values: Iterable[float], per_line: int = 10) -> List[str]:
    vals = list(values)
    return [
        "".join(field8(v) for v in vals[i : i + per_line])
        for i in range(0, len(vals), per_line)
    ]


def station_elevation_lines(profile: List[Tuple[float, float]]) -> List[str]:
    values: List[float] = []
    for station, elevation in profile:
        values += [station, elevation]
    return fixed8(values, 10)


def choose_banks(profile: List[Tuple[float, float]]) -> Tuple[float, float]:
    """Use exact interior station/elevation points as bank stations.

    The qualification model uses almost the full surveyed section as the main
    channel because no reliable floodplain roughness zoning has been supplied.
    """
    if len(profile) < 3:
        raise ValueError("Cross section needs at least three points")
    return profile[1][0], profile[-2][0]


def geometry_text() -> str:
    lines = [
        "Geom Title=Current Base",
        "Program Version=7.01",
        "Viewing Rectangle= 0 , 1000 , 1000 , 0 ",
        f"River Reach={RIVER:<16},{REACH:<16}",
        "Reach XY= 2",
        f"{0.0:16.3f}{0.0:16.3f}{1000.0:16.3f}{0.0:16.3f}",
        "Rch Text X Y=500,500",
        "Reverse River Text= 0",
        "",
    ]

    for rs, filename, reach_length in SECTIONS:
        profile = read_profile(filename)
        left_bank, right_bank = choose_banks(profile)

        lines.append(
            "Type RM Length L Ch R = 1 ,"
            f"{rs:g},{reach_length:g},{reach_length:g},{reach_length:g}"
        )
        lines.append("BEGIN DESCRIPTION:")
        lines.append(Path(filename).stem)
        lines.append("END DESCRIPTION:")
        lines.append(f"#Sta/Elev= {len(profile)}")
        lines.extend(station_elevation_lines(profile))

        # Standard horizontal-variation n format.  Three n blocks place breaks
        # exactly at the bank stations, even though all three n values are equal.
        lines.append("#Mann= 3 , 0 , 0")
        lines.extend(
            fixed8(
                [
                    profile[0][0], N, 0.0,
                    left_bank, N, 0.0,
                    right_bank, N, 0.0,
                ],
                9,
            )
        )
        lines.append(f"Bank Sta={left_bank:.3f},{right_bank:.3f}")
        lines.append("XS Rating Curve= 0 ,0")
        lines.append("XS HTab Horizontal Distribution= 5 , 5 , 5")
        lines.append("Exp/Cntr=0.3,0.1")
        lines.append("")

    # Conventional geometry footer copied from HEC-RAS 7.x seed structure.
    lines += [
        "LCMann Time=Dec/30/1899 00:00:00",
        "LCMann Region Time=Dec/30/1899 00:00:00",
        "LCMann Table=0",
        "Chan Stop Cuts=-1 ",
        "",
        "Use User Specified Reach Order=0",
        "GIS Ratio Cuts To Invert=-1",
        "GIS Limit At Bridges=0",
        "Composite Channel Slope=5",
        "",
    ]
    return "\n".join(lines)


def flow_text() -> str:
    # This layout follows RasSteady.write_flow_file() in ras-commander 0.99.1.
    return "\n".join(
        [
            "Flow Title=Q26000",
            "Program Version=7.01",
            "Number of Profiles= 1",
            "Profile Names=Q26000",
            f"River Rch & RM={RIVER},{REACH},1000",
            f"{Q:g}",
            f"Boundary for River Rch & Prof#={RIVER},{REACH}, 1",
            "Up Type= 0",
            "Dn Type= 1",
            f"Dn Known WS={DOWNSTREAM_WSE:.6f}",
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


def plan_text() -> str:
    # Conventional steady-flow plan keys; keep optional settings conservative.
    return "\n".join(
        [
            "Plan Title=Current Base",
            "Program Version=7.01",
            "Short Identifier=CurrentBase",
            "Geom File=g01",
            "Flow File=f01",
            "Subcritical Flow",
            "K Sum by GR= 0",
            "Std Step Tol= 0.003",
            "Critical Tol= 0.003",
            "Num of Std Step Trials= 40",
            "Max Error Tol= 0.03",
            "Flow Tol Ratio= 0.001",
            "Split Flow NTrial= 30",
            "Split Flow Tol= 0.02",
            "Split Flow Ratio= 0.02",
            "Log Output Level= 0",
            "Friction Slope Method= 1",
            "Parabolic Critical Depth",
            "Global Vel Dist= 0 , 0 , 0",
            "Global Log Level= 0",
            "CheckData=True",
            "Encroach Param=-1 ,0,0, 0",
            "Run HTab=-1",
            "Run UNet= 0",
            "Run Sediment= 0",
            "Run PostProcess= 0",
            "Run WQNet= 0",
            "Run RASMapper= 0",
            "",
        ]
    )


def project_text() -> str:
    # Mirrors authentic HEC-RAS project files: the unit selector is a bare line,
    # and component titles are read from their files rather than duplicated here.
    return "\n".join(
        [
            "Proj Title=Ganjiang West Branch Bridge 1D",
            "Current Plan=p01",
            "Default Exp/Contr=0.3,0.1",
            "SI Units",
            "Geom File=g01",
            "Flow File=f01",
            "Plan File=p01",
            "Y Axis Title=Elevation",
            "X Axis Title(PF)=Main Channel Distance",
            "X Axis Title(XS)=Station",
            "BEGIN DESCRIPTION:",
            "Five-section steady-flow format qualification model.",
            "END DESCRIPTION:",
            "DSS Start Date=",
            "DSS Start Time=",
            "DSS End Date=",
            "DSS End Time=",
            "DSS Export Filename=",
            "DSS Export Rating Curves= 0 ",
            "DSS Export Rating Curve Sorted= 0 ",
            "DSS Export Volume Flow Curves= 0 ",
            "DXF Filename=",
            "DXF OffsetX= 0 ",
            "DXF OffsetY= 0 ",
            "DXF ScaleX= 1 ",
            "DXF ScaleY= 10 ",
            "GIS Export Profiles= 0 ",
            "",
        ]
    )


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    (OUT / f"{NAME}.prj").write_text(project_text(), encoding="ascii", newline="\r\n")
    (OUT / f"{NAME}.p01").write_text(plan_text(), encoding="ascii", newline="\r\n")
    (OUT / f"{NAME}.f01").write_text(flow_text(), encoding="ascii", newline="\r\n")
    (OUT / f"{NAME}.g01").write_text(geometry_text(), encoding="utf-8", newline="\r\n")
    print(f"Built minimal current-case project: {OUT}")
    for p in sorted(OUT.iterdir()):
        print(p.name, p.stat().st_size)


if __name__ == "__main__":
    main()
