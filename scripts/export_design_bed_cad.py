#!/usr/bin/env python3
"""Export the CAD01-direct design bed as editable DXF deliverables.

Only the direct ``中地面线（建设期)`` geometry is active.  The former centre /
local / distributed constrained reconstructions are retired and are not emitted.
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data/intermediate/dxf/西支5断面100-100，0906.dxf"
CUR = ROOT / "data/processed/cross_sections/西支桥下.csv"
DB = ROOT / "data/processed/design_bed"
DESIGN = DB / "西支桥下_设计河床.csv"
CONTROL = DB / "design_bed_control_mapping.csv"
OUT = ROOT / "deliverables/cad/design_bed"
OUT.mkdir(parents=True, exist_ok=True)

DESIGN_LAYER = "DESIGN_BED_CAD01"
LAYERS = {
    "CURRENT_BED": 8,
    DESIGN_LAYER: 1,
    "PIER_CONTROL": 6,
    "WSE_22_190": 4,
    "ANNOTATION": 7,
}
WSE = 22.190

# Mapping from station/elevation metres into the original five-section drawing.
# It is independently established by the bridge-section extraction audit.
X0 = 391496.2307640212
Y0 = 3193335.313820825
SX = 10.0
SY = 10.0

STANDALONE_NAME = "赣江西支桥下_设计河床_CAD01直接提取_R2000.dxf"
OVERLAY_NAME = "西支5断面_桥下设计河床_CAD01直接叠加_R2013.dxf"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def points(path: Path) -> list[tuple[float, float]]:
    return [
        (float(row["station_m_raw_direction"]), float(row["elevation_m"]))
        for row in read_csv(path)
    ]


current = points(CUR)
design = points(DESIGN)
controls = [
    (
        int(row["pier"]),
        float(row["cad_line_station_m"]),
        float(row["cad_line_elevation_m"]),
    )
    for row in read_csv(CONTROL)
]


def pair(code: int, value: object) -> str:
    return f"{code:>3}\n{value}\n"


def header_r2000(ext: tuple[float, float, float, float]) -> str:
    xmin, ymin, xmax, ymax = ext
    text = pair(0, "SECTION") + pair(2, "HEADER")
    text += pair(9, "$ACADVER") + pair(1, "AC1015")
    text += pair(9, "$DWGCODEPAGE") + pair(3, "ANSI_936")
    text += pair(9, "$INSUNITS") + pair(70, 6)
    text += pair(9, "$MEASUREMENT") + pair(70, 1)
    text += pair(9, "$EXTMIN") + pair(10, f"{xmin:.6f}") + pair(20, f"{ymin:.6f}") + pair(30, "0.0")
    text += pair(9, "$EXTMAX") + pair(10, f"{xmax:.6f}") + pair(20, f"{ymax:.6f}") + pair(30, "0.0")
    text += pair(0, "ENDSEC")
    return text


def layer_record(name: str, color: int) -> str:
    return pair(0, "LAYER") + pair(2, name) + pair(70, 0) + pair(62, color) + pair(6, "CONTINUOUS")


def tables() -> str:
    text = pair(0, "SECTION") + pair(2, "TABLES")
    text += pair(0, "TABLE") + pair(2, "LTYPE") + pair(70, 1)
    text += pair(0, "LTYPE") + pair(2, "CONTINUOUS") + pair(70, 0) + pair(3, "Solid line") + pair(72, 65) + pair(73, 0) + pair(40, "0.0")
    text += pair(0, "ENDTAB")
    text += pair(0, "TABLE") + pair(2, "LAYER") + pair(70, len(LAYERS))
    for name, color in LAYERS.items():
        text += layer_record(name, color)
    text += pair(0, "ENDTAB") + pair(0, "ENDSEC")
    return text


def lwpoly(poly: list[tuple[float, float]], layer: str, color: int | None = None) -> str:
    text = pair(0, "LWPOLYLINE") + pair(100, "AcDbEntity") + pair(8, layer)
    if color is not None:
        text += pair(62, color)
    text += pair(100, "AcDbPolyline") + pair(90, len(poly)) + pair(70, 0)
    for x, y in poly:
        text += pair(10, f"{x:.9f}") + pair(20, f"{y:.9f}")
    return text


def line(x1: float, y1: float, x2: float, y2: float, layer: str, color: int | None = None) -> str:
    text = pair(0, "LINE") + pair(100, "AcDbEntity") + pair(8, layer)
    if color is not None:
        text += pair(62, color)
    text += pair(100, "AcDbLine")
    text += pair(10, f"{x1:.9f}") + pair(20, f"{y1:.9f}") + pair(30, "0")
    text += pair(11, f"{x2:.9f}") + pair(21, f"{y2:.9f}") + pair(31, "0")
    return text


def circle(x: float, y: float, radius: float, layer: str, color: int | None = None) -> str:
    text = pair(0, "CIRCLE") + pair(100, "AcDbEntity") + pair(8, layer)
    if color is not None:
        text += pair(62, color)
    text += pair(100, "AcDbCircle") + pair(10, f"{x:.9f}") + pair(20, f"{y:.9f}") + pair(30, "0") + pair(40, f"{radius:.6f}")
    return text


def dxf_text(x: float, y: float, height: float, value: str, layer: str = "ANNOTATION", color: int | None = None) -> str:
    text = pair(0, "TEXT") + pair(100, "AcDbEntity") + pair(8, layer)
    if color is not None:
        text += pair(62, color)
    text += pair(100, "AcDbText") + pair(10, f"{x:.9f}") + pair(20, f"{y:.9f}") + pair(30, "0")
    text += pair(40, f"{height:.6f}") + pair(1, value) + pair(100, "AcDbText")
    return text


def build_standalone() -> Path:
    xs = [point[0] for point in current]
    ys = [point[1] for point in current]
    ext = (min(xs) - 18, min(ys) - 8, max(max(xs), max(x for x, _ in design)) + 18, max(max(ys), WSE) + 18)
    text = header_r2000(ext) + tables() + pair(0, "SECTION") + pair(2, "ENTITIES")
    text += lwpoly(current, "CURRENT_BED", 8)
    text += lwpoly(design, DESIGN_LAYER, 1)
    text += line(0, WSE, max(max(xs), max(x for x, _ in design)), WSE, "WSE_22_190", 4)
    for pier, station, elevation in controls:
        text += circle(station, elevation, 2.2, "PIER_CONTROL", 6)
        text += dxf_text(station + 3, elevation + 1.2, 3.2, f"{pier}# Z={elevation:.2f}m", "ANNOTATION", 6)
    top = max(max(ys), WSE) + 10
    text += dxf_text(0, top, 5.0, "赣江西支特大桥 桥下设计河床断面", "ANNOTATION", 7)
    text += dxf_text(0, top - 5.5, 3.0, "设计线来源：CAD01 中地面线（建设期）直接提取；非人工约束重建。", "ANNOTATION", 7)
    text += dxf_text(0, top - 9.5, 3.0, "WSE=22.190m 面积核对：CAD毛面积5934.568m2；表值5980m2。", "ANNOTATION", 7)
    text += pair(0, "ENDSEC") + pair(0, "EOF")
    path = OUT / STANDALONE_NAME
    path.write_bytes(text.encode("gb18030", errors="replace"))
    return path


def entity_pairs_from_string(text: str) -> list[list[object]]:
    lines = text.splitlines()
    return [[int(lines[i].strip()), lines[i + 1]] for i in range(0, len(lines) - 1, 2)]


def world(poly: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return [(X0 + x * SX, Y0 + y * SY) for x, y in poly]


def build_overlay() -> Path:
    raw = SRC.read_text(encoding="utf-8-sig", errors="replace")
    lines = raw.splitlines()
    pairs: list[list[object]] = []
    for i in range(0, len(lines) - 1, 2):
        try:
            code = int(lines[i].strip())
        except ValueError:
            continue
        pairs.append([code, lines[i + 1]])

    existing_layers: set[str] = set()
    for i, (code, value) in enumerate(pairs):
        if code == 0 and value == "LAYER":
            for j in range(i + 1, min(i + 8, len(pairs))):
                if pairs[j][0] == 2:
                    existing_layers.add(str(pairs[j][1]))
                    break

    insert_layer_at = None
    layer_count_idx = None
    in_layer = False
    for i, (code, value) in enumerate(pairs):
        if code == 0 and value == "TABLE" and i + 1 < len(pairs) and pairs[i + 1] == [2, "LAYER"]:
            in_layer = True
            for j in range(i + 2, min(i + 8, len(pairs))):
                if pairs[j][0] == 70:
                    layer_count_idx = j
                    break
            continue
        if in_layer and code == 0 and value == "ENDTAB":
            insert_layer_at = i
            break

    new_layers = [name for name in LAYERS if name not in existing_layers]
    if insert_layer_at is not None and new_layers:
        records: list[list[object]] = []
        for name in new_layers:
            records.extend(
                [
                    [0, "LAYER"],
                    [100, "AcDbSymbolTableRecord"],
                    [100, "AcDbLayerTableRecord"],
                    [2, name],
                    [70, "0"],
                    [62, str(LAYERS[name])],
                    [6, "CONTINUOUS"],
                ]
            )
        pairs[insert_layer_at:insert_layer_at] = records
        if layer_count_idx is not None:
            pairs[layer_count_idx][1] = str(int(str(pairs[layer_count_idx][1])) + len(new_layers))

    in_entities = False
    entity_end = None
    for i, (code, value) in enumerate(pairs):
        if code == 0 and value == "SECTION" and i + 1 < len(pairs) and pairs[i + 1] == [2, "ENTITIES"]:
            in_entities = True
            continue
        if in_entities and code == 0 and value == "ENDSEC":
            entity_end = i
            break
    if entity_end is None:
        raise RuntimeError("ENTITIES end not found")

    inject = entity_pairs_from_string(lwpoly(world(design), DESIGN_LAYER, 1))
    inject += entity_pairs_from_string(
        line(X0, Y0 + WSE * SY, X0 + max(x for x, _ in design) * SX, Y0 + WSE * SY, "WSE_22_190", 4)
    )
    for pier, station, elevation in controls:
        x = X0 + station * SX
        y = Y0 + elevation * SY
        inject += entity_pairs_from_string(circle(x, y, 18, "PIER_CONTROL", 6))
        inject += entity_pairs_from_string(dxf_text(x + 25, y + 10, 22, f"{pier}# DESIGN Z={elevation:.2f}m", "ANNOTATION", 6))
    pairs[entity_end:entity_end] = inject

    overlay = OUT / OVERLAY_NAME
    with overlay.open("w", encoding="utf-8", newline="\n") as stream:
        for code, value in pairs:
            stream.write(f"{int(code):>3}\n{value}\n")
    return overlay


def retire_old_generated_dxfs() -> None:
    # Only known/generated legacy filenames in the delivery root are removed;
    # manual_review is deliberately untouched.
    legacy_tokens = ("三方案", "中心方案", "局部型", "分布型")
    for path in OUT.glob("*.dxf"):
        if path.name in {STANDALONE_NAME, OVERLAY_NAME}:
            continue
        if any(token in path.name for token in legacy_tokens):
            path.unlink()


def main() -> None:
    retire_old_generated_dxfs()
    standalone = build_standalone()
    overlay = build_overlay()
    print("DXF outputs:")
    for path in (standalone, overlay):
        print(" ", path.name, path.stat().st_size)


if __name__ == "__main__":
    main()
