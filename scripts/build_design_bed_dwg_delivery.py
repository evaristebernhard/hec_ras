#!/usr/bin/env python3
"""Build and round-trip validate the CAD01-direct design-bed DWG copy.

DXF/CSV remain authoritative.  Only the active ``DESIGN_BED_CAD01`` overlay is
converted; retired reconstruction DWGs are removed from the active delivery.
"""

from __future__ import annotations

import csv
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "deliverables" / "cad" / "design_bed"
DWG_DIR = BASE / "dwg"
DB = ROOT / "data" / "processed" / "design_bed"
VALIDATION = BASE / "cad_delivery_validation.csv"
LOG = BASE / "libredwg_conversion.log"

X0 = 391496.2307640212
Y0 = 3193335.313820825
SCALE = 10.0
DESIGN_LAYER = "DESIGN_BED_CAD01"
SOURCE = DB / "西支桥下_设计河床.csv"
OVERLAY = BASE / "西支5断面_桥下设计河床_CAD01直接叠加_R2013.dxf"
DWG_NAME = "西支5断面_桥下设计河床_CAD01直接叠加_R2004.dwg"


def read_expected() -> list[tuple[float, float]]:
    with SOURCE.open(encoding="utf-8-sig", newline="") as stream:
        return [
            (
                X0 + float(row["station_m_raw_direction"]) * SCALE,
                Y0 + float(row["elevation_m"]) * SCALE,
            )
            for row in csv.DictReader(stream)
        ]


def read_pairs(path: Path) -> list[tuple[int, str]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    pairs: list[tuple[int, str]] = []
    for index in range(0, len(lines) - 1, 2):
        try:
            pairs.append((int(lines[index].strip()), lines[index + 1].strip()))
        except ValueError:
            pass
    return pairs


def design_polyline(path: Path) -> list[tuple[float, float]]:
    pairs = read_pairs(path)
    in_entities = False
    entity_type: str | None = None
    fields: list[tuple[int, str]] = []
    matches: list[list[tuple[float, float]]] = []

    def flush() -> None:
        nonlocal entity_type, fields
        if entity_type == "LWPOLYLINE":
            layer = next((value for code, value in fields if code == 8), "")
            if layer == DESIGN_LAYER:
                xs = [float(value) for code, value in fields if code == 10]
                ys = [float(value) for code, value in fields if code == 20]
                matches.append(list(zip(xs, ys)))
        entity_type = None
        fields = []

    for index, (code, value) in enumerate(pairs):
        if code == 0 and value == "SECTION" and index + 1 < len(pairs) and pairs[index + 1] == (2, "ENTITIES"):
            in_entities = True
            continue
        if in_entities and code == 0 and value == "ENDSEC":
            flush()
            break
        if in_entities and code == 0:
            flush()
            entity_type = value
        elif in_entities and entity_type:
            fields.append((code, value))

    if len(matches) != 1:
        raise RuntimeError(f"expected one {DESIGN_LAYER} polyline, found {len(matches)}")
    return matches[0]


def entity_counts(path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    pairs = read_pairs(path)
    in_entities = False
    for index, (code, value) in enumerate(pairs):
        if code == 0 and value == "SECTION" and index + 1 < len(pairs) and pairs[index + 1] == (2, "ENTITIES"):
            in_entities = True
            continue
        if in_entities and code == 0 and value == "ENDSEC":
            break
        if in_entities and code == 0:
            counts[value] = counts.get(value, 0) + 1
    return counts


def retire_old_generated_dwgs() -> None:
    legacy_tokens = ("三方案", "中心方案", "局部型", "分布型")
    for path in DWG_DIR.glob("*.dwg"):
        if path.name == DWG_NAME:
            continue
        if any(token in path.name for token in legacy_tokens):
            path.unlink()


def main() -> None:
    if not shutil.which("dxf2dwg") or not shutil.which("dwg2dxf"):
        raise RuntimeError("GNU LibreDWG dxf2dwg/dwg2dxf not found")
    if not OVERLAY.is_file():
        raise FileNotFoundError(OVERLAY)

    DWG_DIR.mkdir(parents=True, exist_ok=True)
    retire_old_generated_dwgs()
    destination = DWG_DIR / DWG_NAME
    log_lines: list[str] = []

    with tempfile.TemporaryDirectory(prefix=".dwg-build-", dir=DWG_DIR) as build_tmp:
        staged = Path(build_tmp) / destination.name
        cp = subprocess.run(
            ["dxf2dwg", "-y", "--as", "r2004", "-o", str(staged), str(OVERLAY)],
            text=True,
            capture_output=True,
            check=True,
        )
        staged.replace(destination)
        log_lines.append(f"===== {OVERLAY.name} -> {destination.name} =====\n{cp.stdout}{cp.stderr}\n")

    expected = read_expected()
    with tempfile.TemporaryDirectory(prefix="design_bed_dwg_rt_") as tmp:
        tmp_path = Path(tmp)
        cp = subprocess.run(
            ["dwg2dxf", "-y", str(destination)],
            cwd=tmp_path,
            text=True,
            capture_output=True,
            check=True,
        )
        log_lines.append(f"===== roundtrip {destination.name} =====\n{cp.stdout}{cp.stderr}\n")
        roundtrip = tmp_path / f"{destination.stem}.dxf"
        if not roundtrip.exists():
            raise RuntimeError(f"roundtrip DXF missing for {destination}")

        got = design_polyline(roundtrip)
        if len(got) != len(expected):
            raise RuntimeError(
                f"{destination.name}: design vertex count {len(got)} != {len(expected)}"
            )
        max_error = max(
            math.hypot(gx - ex, gy - ey)
            for (gx, gy), (ex, ey) in zip(got, expected)
        )
        text = roundtrip.read_text(encoding="utf-8", errors="replace")
        counts = entity_counts(roundtrip)

    row = {
        "dwg": destination.name,
        "design_layer": DESIGN_LAYER,
        "expected_vertices": len(expected),
        "roundtrip_vertices": len(got),
        "max_xy_error_cad_units": f"{max_error:.12g}",
        "max_xy_error_m": f"{max_error / SCALE:.12g}",
        "entity_LINE": counts.get("LINE", 0),
        "entity_TEXT": counts.get("TEXT", 0),
        "entity_LWPOLYLINE": counts.get("LWPOLYLINE", 0),
        "entity_CIRCLE": counts.get("CIRCLE", 0),
        "chinese_bridge_label_preserved": "西支桥下" in text,
        "chinese_upstream500_label_preserved": "西支上游500米" in text,
        "cad01_direct_only": True,
    }
    with VALIDATION.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row), lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)

    LOG.write_text("".join(log_lines), encoding="utf-8")
    print(f"Wrote CAD01-direct R2004 DWG: {destination.relative_to(ROOT)}")
    print(f"Roundtrip max XY error: {max_error / SCALE:.3g} m")


if __name__ == "__main__":
    main()
