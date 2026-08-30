#!/usr/bin/env python3
"""Convert the four local source DWGs to the canonical intermediate DXFs.

Only the declared targets are replaced, through a staging directory.  A hash
manifest is written to processed evidence so downstream data can be tied to
the exact local CAD bytes even though the large source files are not in Git.
"""

from __future__ import annotations

import csv
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/cad"
DXF = ROOT / "data/intermediate/dxf"
LOG_DIR = DXF / "logs"
MANIFEST = ROOT / "data/processed/evidence/cad_conversion_manifest.csv"

MAPPING = [
    ("01-赣江西支特大桥抗冲刷防护（水下不分散混凝土）.dwg", "01-赣江西支特大桥抗冲刷防护（水下不分散混凝土）.dxf"),
    ("02赣江西支特大桥等值线图.dwg", "02赣江西支特大桥等值线图.dxf"),
    ("西支5断面100-100，0906.dwg", "西支5断面100-100，0906.dxf"),
    ("西支成果.dwg", "西支成果.dxf"),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if not shutil.which("dwg2dxf"):
        raise RuntimeError("GNU LibreDWG dwg2dxf not found")
    DXF.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    version = subprocess.run(["dwg2dxf", "--version"], text=True, capture_output=True, check=True).stdout.splitlines()[0]
    with tempfile.TemporaryDirectory(prefix="cad-convert-", dir=DXF) as temp_dir:
        staging = Path(temp_dir)
        for source_name, target_name in MAPPING:
            source = RAW / source_name
            target = DXF / target_name
            if not source.is_file():
                raise FileNotFoundError(source)
            staged = staging / target_name
            completed = subprocess.run(
                ["dwg2dxf", "-y", "-o", str(staged), str(source)],
                text=True,
                capture_output=True,
                check=True,
            )
            messages = completed.stdout + completed.stderr
            log_path = LOG_DIR / f"{Path(target_name).stem}.log"
            log_path.write_text(messages, encoding="utf-8")
            if not staged.is_file() or staged.stat().st_size == 0:
                raise RuntimeError(f"converter returned without a usable DXF: {source}")
            staged.replace(target)
            rows.append(
                {
                    "source": source.relative_to(ROOT).as_posix(),
                    "source_sha256": sha256(source),
                    "target": target.relative_to(ROOT).as_posix(),
                    "target_sha256": sha256(target),
                    "converter": version,
                    "warning_lines": sum("warning" in line.lower() for line in messages.splitlines()),
                    "error_lines": sum("error" in line.lower() for line in messages.splitlines()),
                    "local_log_sha256": sha256(log_path),
                }
            )
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Converted {len(rows)} CAD sources; manifest: {MANIFEST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
