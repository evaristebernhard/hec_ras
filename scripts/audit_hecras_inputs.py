#!/usr/bin/env python3
"""Static integrity audit for generated HEC-RAS steady-flow text inputs.

This audit catches file-level problems before opening HEC-RAS: broken plan
references, overlong Short Identifiers, inconsistent boundary Flow Titles,
stale data-error artifacts, or boundary geometries that drift from the main
five-case model.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "models" / "main"
BOUNDARY = ROOT / "models" / "boundary_sensitivity"
FAILURES: list[str] = []


def require(condition: bool, message: str) -> None:
    if not condition:
        FAILURES.append(message)


def read(path: Path) -> str:
    require(path.is_file(), f"missing file: {path.relative_to(ROOT)}")
    if not path.is_file():
        return ""
    return path.read_text(encoding="ascii", errors="strict")


def field(text: str, key: str) -> str | None:
    prefix = key + "="
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return None


def check_plan(path: Path, model_dir: Path) -> None:
    text = read(path)
    if not text:
        return
    short_id = field(text, "Short Identifier")
    require(short_id is not None, f"{path.name}: missing Short Identifier")
    if short_id is not None:
        require(len(short_id) <= 16, f"{path.name}: Short Identifier exceeds 16 chars: {short_id}")

    geom = field(text, "Geom File")
    flow = field(text, "Flow File")
    require(geom is not None, f"{path.name}: missing Geom File")
    require(flow is not None, f"{path.name}: missing Flow File")
    if geom:
        require((model_dir / f"{path.stem.split('.')[0]}.{geom}").is_file(), f"{path.name}: missing referenced geometry {geom}")
    if flow:
        require((model_dir / f"{path.stem.split('.')[0]}.{flow}").is_file(), f"{path.name}: missing referenced flow {flow}")

    require("Subcritical Flow" in text, f"{path.name}: expected Subcritical Flow")
    require(field(text, "Program Version") == "7.01", f"{path.name}: unexpected Program Version")


def geometry_river_stations(text: str) -> list[float]:
    return [
        float(match.group(1))
        for match in re.finditer(r"^Type RM Length L Ch R = 1 ,([^,]+),", text, flags=re.MULTILINE)
    ]


def check_geometry(path: Path) -> None:
    text = read(path)
    if not text:
        return
    require("River Reach=Ganjiang" in text and ",WestBranch" in text, f"{path.name}: wrong river/reach")
    require(geometry_river_stations(text) == [1000.0, 600.0, 500.0, 400.0, 0.0], f"{path.name}: unexpected river-station sequence")
    require(text.count("#Block Obstruct= 1") == 1, f"{path.name}: expected exactly one blocked obstruction")
    require("  50.000" in text, f"{path.name}: obstruction top sentinel 50 m missing")


def check_flow(path: Path, expected_title: str, expected_wse: float) -> None:
    text = read(path)
    if not text:
        return
    require(field(text, "Flow Title") == expected_title, f"{path.name}: Flow Title mismatch")
    require(field(text, "Program Version") == "7.01", f"{path.name}: unexpected Program Version")
    require(field(text, "Number of Profiles") == "1", f"{path.name}: expected one profile")
    require(field(text, "Profile Names") == "Q26000", f"{path.name}: unexpected profile name")
    require("River Rch & RM=Ganjiang,WestBranch      ,1000" in text, f"{path.name}: upstream flow location mismatch")
    require(re.search(r"^\s*26000\.0\s*$", text, flags=re.MULTILINE) is not None, f"{path.name}: Q=26000 missing")
    require(field(text, "Dn Type") == "1", f"{path.name}: downstream boundary is not Known WS")
    wse = field(text, "Dn Known WS")
    require(wse is not None, f"{path.name}: missing Dn Known WS")
    if wse is not None:
        require(abs(float(wse) - expected_wse) < 5e-7, f"{path.name}: downstream WSE mismatch")


def check_boundary_map() -> None:
    path = BOUNDARY / "sensitivity_plan_map.csv"
    require(path.is_file(), "missing boundary sensitivity_plan_map.csv")
    if not path.is_file():
        return
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    require(len(rows) == 15, f"boundary map: expected 15 plans, found {len(rows)}")
    for row in rows:
        plan_path = BOUNDARY / f"GanjiangWestBridgeBoundary.{row['plan']}"
        text = read(plan_path)
        require(field(text, "Short Identifier") == row["short_id"], f"{row['plan']}: map Short ID differs from plan")
        require(len(row["short_id"]) <= 16, f"{row['plan']}: mapped Short ID exceeds 16 chars")
        require(field(text, "Geom File") == row["geometry"], f"{row['plan']}: map geometry differs from plan")
        require(field(text, "Flow File") == row["flow"], f"{row['plan']}: map flow differs from plan")


def main() -> None:
    main_prj = read(MAIN / "GanjiangWestBridge.prj")
    boundary_prj = read(BOUNDARY / "GanjiangWestBridgeBoundary.prj")
    require("SI Units" in main_prj, "main project is not SI Units")
    require("SI Units" in boundary_prj, "boundary project is not SI Units")

    for number in range(1, 6):
        check_plan(MAIN / f"GanjiangWestBridge.p{number:02d}", MAIN)
        check_geometry(MAIN / f"GanjiangWestBridge.g{number:02d}")

    check_flow(MAIN / "GanjiangWestBridge.f01", "Q26000", 22.049342)

    for number in range(1, 16):
        check_plan(BOUNDARY / f"GanjiangWestBridgeBoundary.p{number:02d}", BOUNDARY)

    for number in range(1, 6):
        main_g = MAIN / f"GanjiangWestBridge.g{number:02d}"
        boundary_g = BOUNDARY / f"GanjiangWestBridgeBoundary.g{number:02d}"
        check_geometry(boundary_g)
        if main_g.is_file() and boundary_g.is_file():
            require(main_g.read_bytes() == boundary_g.read_bytes(), f"boundary g{number:02d} differs from main geometry")

    check_flow(BOUNDARY / "GanjiangWestBridgeBoundary.f01", "Q26000_Low", 21.549342)
    check_flow(BOUNDARY / "GanjiangWestBridgeBoundary.f02", "Q26000_Base", 22.049342)
    check_flow(BOUNDARY / "GanjiangWestBridgeBoundary.f03", "Q26000_High", 22.549342)
    check_boundary_map()

    for model_dir in (MAIN, BOUNDARY):
        stale = list(model_dir.glob("*.data_errors.txt"))
        require(not stale, f"stale HEC-RAS data error artifacts in {model_dir.relative_to(ROOT)}: {[p.name for p in stale]}")

    if FAILURES:
        for failure in FAILURES:
            print(f"[FAIL] {failure}")
        sys.exit(1)

    print("[PASS] HEC-RAS project/plan/geometry/flow references are internally consistent")
    print("[PASS] all steady-flow Short Identifiers are <= 16 characters")
    print("[PASS] main and boundary geometries are identical for all five cases")
    print("[PASS] Q=26000 and Low/Base/High downstream Known WS inputs are correct")
    print("[PASS] no stale *.data_errors.txt files remain in active model directories")


if __name__ == "__main__":
    main()
