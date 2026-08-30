#!/usr/bin/env python3
"""Scan supplied CAD/DXF text for explicit bridge-geometry evidence.

The goal is not to infer missing dimensions.  It records traceable text that
could support a HEC-RAS Bridge/Culvert model: deck/beam elevations, pier widths,
clearances, caps, pile caps, and related dimensions.
"""

from __future__ import annotations

import csv
import argparse
from pathlib import Path

from recover_design_bed import iter_dxf_entities

ROOT = Path(__file__).resolve().parents[1]
DXF_DIR = ROOT / "data" / "intermediate" / "dxf"
FILES = [
    (DXF_DIR / "01-赣江西支特大桥抗冲刷防护（水下不分散混凝土）.dxf", "gb18030"),
    # LibreDWG conversions in the remaining drawings are not guaranteed to
    # preserve the same text encoding.  Scan the plausible encodings; exact
    # Chinese keyword matching naturally rejects the incorrectly decoded pass.
    (DXF_DIR / "02赣江西支特大桥等值线图.dxf", "utf-8-sig"),
    (DXF_DIR / "02赣江西支特大桥等值线图.dxf", "gb18030"),
    (DXF_DIR / "西支成果.dxf", "utf-8-sig"),
    (DXF_DIR / "西支成果.dxf", "gb18030"),
    (DXF_DIR / "西支5断面100-100，0906.dxf", "utf-8-sig"),
]
OUT = ROOT / "data" / "processed" / "evidence" / "bridge_geometry_evidence.csv"

KEYWORDS = [
    "桥面",
    "梁底",
    "低弦",
    "桥梁",
    "桥墩",
    "墩柱",
    "墩身",
    "盖梁",
    "承台",
    "桩基",
    "净空",
    "净高",
    "标高",
    "高程",
    "15#",
    "16#",
    "17#",
]


def main(verbose: bool = False) -> None:
    rows: list[dict[str, str]] = []
    for path, encoding in FILES:
        for entity in iter_dxf_entities(path, encoding):
            if entity.kind not in {"TEXT", "MTEXT", "ATTRIB", "ATTDEF"}:
                continue
            text = entity.text
            matched = [keyword for keyword in KEYWORDS if keyword in text]
            if not matched:
                continue
            rows.append(
                {
                    "file": str(path.relative_to(ROOT)),
                    "encoding": encoding,
                    "section": entity.section or "",
                    "block": entity.block or "",
                    "kind": entity.kind,
                    "handle": entity.handle,
                    "layer": entity.one(8, "") or "",
                    "cad_x": entity.one(10, "") or "",
                    "cad_y": entity.one(20, "") or "",
                    "matched_keywords": "|".join(matched),
                    "text": text,
                }
            )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["file", "text"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} bridge-geometry text hits to {OUT}")
    if verbose:
        for row in rows[:80]:
            print(f"[{row['file']}] {row['matched_keywords']}: {row['text'][:220]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="print matched CAD text")
    main(parser.parse_args().verbose)
