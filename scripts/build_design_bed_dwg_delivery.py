#!/usr/bin/env python3
"""Build and round-trip validate the design-bed DWG delivery copies.

Authoritative geometry stays in DXF/CSV.  This script converts the complete
R2013 overlay DXFs (which inherit the original drawing structure) to R2004 DWG
with GNU LibreDWG, converts each DWG back to DXF, and verifies the design
polyline vertex counts/coordinates plus selected Chinese labels.
"""
from __future__ import annotations

from pathlib import Path
import csv
import math
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "deliverables" / "cad" / "design_bed"
DWG_DIR = BASE / "dwg"
DB = ROOT / "data" / "processed" / "design_bed"
VALIDATION = BASE / "cad_delivery_validation.csv"
LOG = BASE / "libredwg_conversion.log"

X0 = 391496.2307640212
Y0 = 3193335.313820825
SCALE = 10.0

SOURCE_BY_LAYER = {
    "DESIGN_CENTER": DB / "西支桥下_设计河床.csv",
    "DESIGN_LOCAL": DB / "西支桥下_设计河床_局部型.csv",
    "DESIGN_DISTRIBUTED": DB / "西支桥下_设计河床_分布型.csv",
}


def read_expected(path: Path) -> list[tuple[float, float]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [
            (
                X0 + float(row["station_m_raw_direction"]) * SCALE,
                Y0 + float(row["elevation_m"]) * SCALE,
            )
            for row in csv.DictReader(f)
        ]


def read_pairs(path: Path) -> list[tuple[int, str]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    out = []
    for i in range(0, len(lines) - 1, 2):
        try:
            out.append((int(lines[i].strip()), lines[i + 1].strip()))
        except ValueError:
            pass
    return out


def design_polylines(path: Path) -> dict[str, list[tuple[float, float]]]:
    pairs = read_pairs(path)
    result = {}
    in_entities = False
    typ = None
    fields: list[tuple[int, str]] = []

    def flush() -> None:
        nonlocal typ, fields
        if typ == "LWPOLYLINE":
            layer = next((v for c, v in fields if c == 8), "")
            if layer in SOURCE_BY_LAYER:
                xs = [float(v) for c, v in fields if c == 10]
                ys = [float(v) for c, v in fields if c == 20]
                result[layer] = list(zip(xs, ys))
        typ = None
        fields = []

    for i, (code, value) in enumerate(pairs):
        if code == 0 and value == "SECTION" and i + 1 < len(pairs) and pairs[i + 1] == (2, "ENTITIES"):
            in_entities = True
            continue
        if in_entities and code == 0 and value == "ENDSEC":
            flush()
            break
        if in_entities and code == 0:
            flush()
            typ = value
            fields = []
        elif in_entities and typ:
            fields.append((code, value))
    return result


def entity_counts(path: Path) -> dict[str, int]:
    pairs = read_pairs(path)
    counts: dict[str, int] = {}
    in_entities = False
    for i, (code, value) in enumerate(pairs):
        if code == 0 and value == "SECTION" and i + 1 < len(pairs) and pairs[i + 1] == (2, "ENTITIES"):
            in_entities = True
            continue
        if in_entities and code == 0 and value == "ENDSEC":
            break
        if in_entities and code == 0:
            counts[value] = counts.get(value, 0) + 1
    return counts


def main() -> None:
    if not shutil.which("dxf2dwg") or not shutil.which("dwg2dxf"):
        raise RuntimeError("GNU LibreDWG dxf2dwg/dwg2dxf not found")

    DWG_DIR.mkdir(parents=True, exist_ok=True)
    for old in DWG_DIR.glob("*.dwg"):
        old.unlink()

    overlays = sorted(BASE.glob("西支5断面_*_R2013.dxf"))
    if len(overlays) != 4:
        raise RuntimeError(f"expected 4 full overlay DXFs, found {len(overlays)}")

    log_lines = []
    for src in overlays:
        stem = src.name.removesuffix("_R2013.dxf")
        dst = DWG_DIR / f"{stem}_R2004.dwg"
        cp = subprocess.run(
            ["dxf2dwg", "-y", "--as", "r2004", "-o", str(dst), str(src)],
            text=True,
            capture_output=True,
            check=True,
        )
        log_lines.append(f"===== {src.name} -> {dst.name} =====\n{cp.stdout}{cp.stderr}\n")

    rows = []
    with tempfile.TemporaryDirectory(prefix="design_bed_dwg_rt_") as td:
        td_path = Path(td)
        for dwg in sorted(DWG_DIR.glob("*.dwg")):
            cp = subprocess.run(
                ["dwg2dxf", "-y", str(dwg)],
                cwd=td_path,
                text=True,
                capture_output=True,
                check=True,
            )
            log_lines.append(f"===== roundtrip {dwg.name} =====\n{cp.stdout}{cp.stderr}\n")
            rt = td_path / f"{dwg.stem}.dxf"
            if not rt.exists():
                raise RuntimeError(f"roundtrip DXF missing for {dwg}")

            text = rt.read_text(encoding="utf-8", errors="replace")
            polys = design_polylines(rt)
            counts = entity_counts(rt)
            for layer, got in polys.items():
                expected = read_expected(SOURCE_BY_LAYER[layer])
                if len(got) != len(expected):
                    raise RuntimeError(f"{dwg.name} {layer}: vertex count mismatch")
                max_err = max(
                    math.hypot(gx - ex, gy - ey)
                    for (gx, gy), (ex, ey) in zip(got, expected)
                )
                rows.append(
                    {
                        "dwg": dwg.name,
                        "design_layer": layer,
                        "expected_vertices": len(expected),
                        "roundtrip_vertices": len(got),
                        "max_xy_error_cad_units": f"{max_err:.12g}",
                        "max_xy_error_m": f"{max_err / SCALE:.12g}",
                        "entity_LINE": counts.get("LINE", 0),
                        "entity_TEXT": counts.get("TEXT", 0),
                        "entity_LWPOLYLINE": counts.get("LWPOLYLINE", 0),
                        "entity_CIRCLE": counts.get("CIRCLE", 0),
                        "chinese_bridge_label_preserved": "西支桥下" in text,
                        "chinese_upstream500_label_preserved": "西支上游500米" in text,
                    }
                )

    with VALIDATION.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = list(rows[0])
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    LOG.write_text("".join(log_lines), encoding="utf-8")
    print(f"Wrote {len(overlays)} R2004 DWGs to {DWG_DIR.relative_to(ROOT)}")
    print(f"Validation rows: {len(rows)} -> {VALIDATION.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
