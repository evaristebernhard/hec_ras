#!/usr/bin/env python3
"""Synchronize the CAD01-direct design-bed delivery and deterministic ZIP.

The package contains only the active CAD01-direct geometry plus its evidence.
``manual_review/`` is never edited by this script.
"""

from __future__ import annotations

import hashlib
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "deliverables" / "cad" / "design_bed"
SOURCE_DIR = BASE / "source_csv"
MANIFEST = BASE / "SHA256SUMS.txt"
ZIP_PATH = ROOT / "deliverables" / "ganjiang_design_bed_cad_delivery.zip"

SOURCE_FILES = [
    ROOT / "data/processed/cross_sections/西支桥下.csv",
    ROOT / "data/processed/design_bed/西支桥下_设计河床.csv",
    ROOT / "data/processed/design_bed/design_bed_cad_evidence.csv",
    ROOT / "data/processed/design_bed/design_bed_line_evidence.csv",
    ROOT / "data/processed/design_bed/design_bed_control_mapping.csv",
    ROOT / "data/processed/design_bed/design_bed_direct_audit.csv",
    ROOT / "data/processed/evidence/cad_conversion_manifest.csv",
]

RETIRED_SOURCE_NAMES = {
    "西支桥下_设计河床_局部型.csv",
    "西支桥下_设计河床_分布型.csv",
    "design_bed_reconstruction_audit.csv",
    "pier_station_mapping.csv",
}


def delivery_files() -> list[Path]:
    return [
        path
        for path in sorted(BASE.rglob("*"))
        if path.is_file()
        and path != MANIFEST
        and "manual_review" not in path.parts
        and not path.name.startswith(("#", ".#"))
        and not path.name.endswith("~")
    ]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    for name in RETIRED_SOURCE_NAMES:
        stale = SOURCE_DIR / name
        if stale.exists():
            stale.unlink()

    for source in SOURCE_FILES:
        if not source.exists():
            raise FileNotFoundError(source)
        shutil.copyfile(source, SOURCE_DIR / source.name)

    files = delivery_files()
    MANIFEST.write_text(
        "".join(f"{sha256(path)}  {path.relative_to(BASE).as_posix()}\n" for path in files),
        encoding="utf-8",
    )

    ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in [*files, MANIFEST]:
            relative = Path("design_bed") / path.relative_to(BASE)
            info = zipfile.ZipInfo(relative.as_posix(), date_time=(2026, 8, 30, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())

    print(f"Synced {len(SOURCE_FILES)} CAD01-direct source/evidence CSV files")
    print(f"Manifest: {MANIFEST.relative_to(ROOT)} ({len(files)} entries)")
    print(f"Package:  {ZIP_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
