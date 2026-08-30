#!/usr/bin/env python3
"""Build report plotting tables from the active CAD-direct evidence chain.

p01-p04 use the frozen/validated v2 CSV because the current workspace is missing
p01.hdf.  p05 uses the geometry-audited live HDF.  Retired constrained design-
bed reconstructions and their boundary-sensitivity rows are intentionally not
read by this script.
"""

from __future__ import annotations

import csv
from pathlib import Path

import h5py

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "report"
DATA = REPORT / "data"
DATA.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_dat(path: Path, header: list[str], rows) -> None:
    with path.open("w", encoding="utf-8") as stream:
        stream.write(" ".join(header) + "\n")
        for row in rows:
            stream.write(" ".join(str(value) for value in row) + "\n")


# 1) Bridge cross section: current surveyed bed + CAD01 direct design bed only.
profiles = [
    ("current", ROOT / "data/processed/cross_sections/西支桥下.csv"),
    ("design_cad01", ROOT / "data/processed/design_bed/西支桥下_设计河床.csv"),
]
for name, path in profiles:
    rows = read_csv(path)
    write_dat(
        DATA / f"{name}_section.dat",
        ["station_m", "elevation_m"],
        [(row["station_m_raw_direction"], row["elevation_m"]) for row in rows],
    )

controls = read_csv(ROOT / "data/processed/design_bed/design_bed_control_mapping.csv")
write_dat(
    DATA / "design_controls.dat",
    ["pier", "station_m", "design_elev_m"],
    [
        (row["pier"], row["cad_line_station_m"], row["cad_line_elevation_m"])
        for row in controls
    ],
)

# Area audit is copied into a compact report table.
direct_audit = read_csv(ROOT / "data/processed/design_bed/design_bed_direct_audit.csv")
with (DATA / "design_bed_area_audit.csv").open("w", newline="", encoding="utf-8") as stream:
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["check", "target", "actual", "difference", "status"])
    for row in direct_audit:
        if row["check"] in {
            "gross_area_at_wse_22.190_m2",
            "blocked_obstruction_m2",
            "net_area_at_wse_22.190_m2",
        }:
            writer.writerow(
                [row["check"], row["source_or_target"], row["actual"], row["difference"], row["status"]]
            )

# 2) Longitudinal WSE: p01-p04 from frozen active CSV; p05 from audited live HDF.
four = read_csv(ROOT / "results/hecras_steady_four_cases.csv")
long_rows: list[tuple[str, float, float]] = []
for row in four:
    long_rows.append((row["short_id"], float(row["river_station"]), float(row["wse_m"])))

BASE = "Results/Steady/Output/Output Blocks/Base Output/Steady Profiles/Cross Sections"
XS_ATTR = "Results/Steady/Output/Geometry Info/Cross Section Attributes"
p05_hdf = ROOT / "models/main/GanjiangWestBridge.p05.hdf"
with h5py.File(p05_hdf, "r") as hdf:
    xs = hdf[XS_ATTR][:]
    stations = [
        item["Station"].decode("utf-8", errors="replace").strip()
        if isinstance(item["Station"], bytes)
        else str(item["Station"]).strip()
        for item in xs
    ]
    wse = hdf[f"{BASE}/Water Surface"][0]
    for station, z in zip(stations, wse):
        long_rows.append(("DesignBedCAD", float(station), float(z)))

with (DATA / "wse_profiles.csv").open("w", newline="", encoding="utf-8") as stream:
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["case_id", "river_station", "wse_m"])
    writer.writerows(long_rows)

for case_id in ("Current", "Protect05", "Protect10", "Protect20", "DesignBedCAD"):
    rows = [(rs, z) for cid, rs, z in long_rows if cid == case_id]
    rows.sort(key=lambda item: item[0])
    write_dat(DATA / f"wse_{case_id}.dat", ["river_station", "wse_m"], rows)

# 3) Main-case key metrics: p01-p04 CSV plus geometry-audited p05 key stations.
p05 = read_csv(ROOT / "results/hecras_design_bed_cad_direct_backwater.csv")
for station in ("600", "500"):
    subset = [row for row in four if row["river_station"] == station]
    design = next(row for row in p05 if row["river_station"] == station)
    output = DATA / f"five_cases_rs{station}.csv"
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            ["case_id", "wse_m", "energy_grade_m", "velocity_mps", "flow_area_m2", "froude", "delta_wse_mm"]
        )
        for row in subset:
            writer.writerow(
                [
                    row["short_id"],
                    row["wse_m"],
                    row["energy_grade_m"],
                    row["velocity_mps"],
                    row["flow_area_m2"],
                    row["froude"],
                    1000.0 * float(row["delta_wse_vs_p01_m"]),
                ]
            )
        writer.writerow(
            [
                "DesignBedCAD",
                design["design_bed_wse_m"],
                design["energy_grade_m"],
                design["velocity_mps"],
                design["flow_area_m2"],
                design["froude"],
                design["delta_wse_mm"],
            ]
        )

# 4) Downstream-boundary sensitivity: only unchanged Current/Protection cases.
boundary = read_csv(ROOT / "results/hecras_boundary_sensitivity.csv")
valid_case_ids = {"Current", "Protect05", "Protect10", "Protect20"}
rows600 = [
    row for row in boundary
    if row["river_station"] == "600" and row["case_id"] in valid_case_ids
]
with (DATA / "boundary_rs600_active.csv").open("w", newline="", encoding="utf-8") as stream:
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["case_id", "downstream_wse_m", "delta_wse_mm", "absolute_wse_m"])
    for row in rows600:
        writer.writerow(
            [
                row["case_id"],
                row["downstream_wse_m"],
                1000.0 * float(row["delta_wse_vs_current_same_boundary_m"]),
                row["wse_m"],
            ]
        )

for case_id in ("Protect05", "Protect10", "Protect20"):
    subset = [row for row in rows600 if row["case_id"] == case_id]
    subset.sort(key=lambda row: float(row["downstream_wse_m"]))
    write_dat(
        DATA / f"boundary_{case_id}.dat",
        ["downstream_wse_m", "delta_wse_mm", "absolute_wse_m"],
        [
            (
                row["downstream_wse_m"],
                1000.0 * float(row["delta_wse_vs_current_same_boundary_m"]),
                row["wse_m"],
            )
            for row in subset
        ],
    )

print(f"Wrote CAD-direct report data to {DATA}")
