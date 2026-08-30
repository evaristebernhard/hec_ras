#!/usr/bin/env python3
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "deliverables" / "cad" / "design_bed"
SRC = BASE / "赣江西支桥下_设计河床_三方案对比_R2000.dxf"
DST = BASE / "西支桥下_设计河床_三方案_审阅版_R2000.dxf"

shutil.copy2(SRC, DST)
print(DST.relative_to(ROOT))
