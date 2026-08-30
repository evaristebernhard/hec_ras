#!/usr/bin/env python3
"""Fail-fast integrity checks for the active CAD01-direct hydraulic study."""

from __future__ import annotations

import csv
import hashlib
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILURES: list[str] = []


def require(condition: bool, message: str) -> None:
    if not condition:
        FAILURES.append(message)


def rows(relative: str) -> list[dict[str, str]]:
    path = ROOT / relative
    require(path.is_file(), f"missing {relative}")
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def truth(value: str) -> bool:
    return value.strip().lower() == "true"


def check_layout() -> None:
    for relative in [
        "docs/methodology.md",
        "docs/reproducibility.md",
        "docs/findings.md",
        "data/README.md",
        "models/main/GanjiangWestBridge.prj",
        "models/main/GanjiangWestBridge.p05",
        "report/main.pdf",
        "deliverables/cad/design_bed/README.md",
        "deliverables/cad/design_bed/赣江西支桥下_设计河床_CAD01直接提取_R2000.dxf",
        "deliverables/cad/design_bed/西支5断面_桥下设计河床_CAD01直接叠加_R2013.dxf",
    ]:
        require((ROOT / relative).is_file(), f"missing {relative}")

    # p06/p07 reconstruction plans are no longer active text inputs.
    for suffix in ("p06", "p07", "g06", "g07"):
        require(
            not (ROOT / "models/main" / f"GanjiangWestBridge.{suffix}").exists(),
            f"retired main-model input still active: {suffix}",
        )

    legacy_tokens = ("三方案", "中心方案", "局部型", "分布型")
    delivery = ROOT / "deliverables/cad/design_bed"
    for path in [*delivery.glob("*.dxf"), *(delivery / "dwg").glob("*.dwg")]:
        require(
            not any(token in path.name for token in legacy_tokens),
            f"retired reconstruction deliverable still active: {path.name}",
        )


def check_design_bed() -> None:
    audit = rows("data/processed/design_bed/design_bed_direct_audit.csv")
    require(len(audit) == 6, f"expected 6 direct design-bed audit rows, found {len(audit)}")
    allowed_status = {"PASS", "CAD_DIRECT_PRECEDENCE"}
    require(
        all(row["status"] in allowed_status for row in audit),
        "direct design-bed audit contains unexpected status",
    )
    by_check = {row["check"]: row for row in audit}
    gross = by_check.get("gross_area_at_wse_22.190_m2")
    net = by_check.get("net_area_at_wse_22.190_m2")
    if gross:
        require(math.isclose(float(gross["actual"]), 5934.568414, abs_tol=1e-6), "CAD direct gross area changed")
        require(gross["status"] == "CAD_DIRECT_PRECEDENCE", "gross area must preserve CAD precedence")
    if net:
        require(math.isclose(float(net["actual"]), 5654.568414, abs_tol=1e-6), "CAD direct net area changed")
        require(net["status"] == "CAD_DIRECT_PRECEDENCE", "net area must preserve CAD precedence")

    line_evidence = rows("data/processed/design_bed/design_bed_line_evidence.csv")
    design_rows = [row for row in line_evidence if row["role"] == "design_original"]
    require(len(design_rows) == 1, "expected exactly one CAD01 design-original line evidence row")
    if design_rows:
        row = design_rows[0]
        require(row["label_text"] == "中地面线（建设期)", "wrong semantic label for design bed")
        require(row["profile_handle"] == "450505", "unexpected CAD01 design profile handle")
        require(float(row["leader_profile_gap_cad_units"]) <= 0.05, "leader does not point to design profile")

    controls = rows("data/processed/design_bed/design_bed_control_mapping.csv")
    require(len(controls) == 3, f"expected 3 direct design-bed controls, found {len(controls)}")
    expected = {"15": 4.27, "16": 5.40, "17": 9.56}
    for row in controls:
        require(row["pier"] in expected, f"unexpected pier control {row['pier']}")
        if row["pier"] in expected:
            require(
                math.isclose(float(row["cad_line_elevation_m"]), expected[row["pier"]], abs_tol=1e-9),
                f"{row['pier']}# CAD direct elevation mismatch",
            )
        require(truth(row["match"]), f"{row['pier']}# control does not match CAD direct line")

    hdf_audit = rows("results/hecras_design_bed_cad_direct_hdf_audit.csv")
    require(len(hdf_audit) == 6, f"expected 6 p05 HDF audit rows, found {len(hdf_audit)}")
    require(all(row["status"] == "PASS" for row in hdf_audit), "p05 HDF geometry audit failed")


def check_hecras_results() -> None:
    four = rows("results/hecras_steady_four_cases.csv")
    require(len(four) == 20, f"expected 20 p01-p04 section rows, found {len(four)}")
    require({row["short_id"] for row in four} == {"Current", "Protect05", "Protect10", "Protect20"}, "unexpected p01-p04 case set")

    parity = rows("results/hecras_p01_p04_parity_v2.csv")
    require(len(parity) == 20, f"expected 20 parity rows, found {len(parity)}")
    require(all(truth(row["parity_verified"]) for row in parity), "p01-p04 parity is not verified")

    design = rows("results/hecras_design_bed_cad_direct_backwater.csv")
    require(len(design) == 3, f"expected 3 CAD-direct p05 key rows, found {len(design)}")
    require(all(truth(row["hdf_geometry_match"]) for row in design), "p05 result lacks geometry match")
    rs600 = next((row for row in design if row["river_station"] == "600"), None)
    rs500 = next((row for row in design if row["river_station"] == "500"), None)
    require(rs600 is not None, "p05 RS600 result missing")
    require(rs500 is not None, "p05 RS500 result missing")
    if rs600:
        require(math.isclose(float(rs600["design_bed_wse_m"]), 22.576809, abs_tol=1e-6), "p05 RS600 WSE changed")
        require(math.isclose(float(rs600["delta_wse_mm"]), 193.6, abs_tol=0.1), "p05 RS600 delta changed")
    if rs500:
        require(math.isclose(float(rs500["velocity_mps"]), 4.691635, abs_tol=1e-6), "p05 RS500 velocity changed")

    boundary = rows("results/hecras_boundary_sensitivity.csv")
    active = [row for row in boundary if row["case_id"] in {"Current", "Protect05", "Protect10", "Protect20"}]
    require(len(active) == 24, f"expected 24 unchanged-case boundary rows, found {len(active)}")
    # Explicitly ensure retired DesignBed rows are not needed for active validation.
    for case_id, low, high in [
        ("Protect05", 2.296, 2.588),
        ("Protect10", 3.448, 4.002),
        ("Protect20", 5.762, 6.853),
    ]:
        values = [
            1000.0 * float(row["delta_wse_vs_current_same_boundary_m"])
            for row in active
            if row["case_id"] == case_id and row["river_station"] == "600"
        ]
        require(len(values) == 3, f"{case_id}: expected 3 boundary RS600 rows")
        if values:
            require(math.isclose(min(values), low, abs_tol=0.001), f"{case_id}: boundary min changed")
            require(math.isclose(max(values), high, abs_tol=0.001), f"{case_id}: boundary max changed")


def check_cad_delivery() -> None:
    validation = rows("deliverables/cad/design_bed/cad_delivery_validation.csv")
    require(len(validation) == 1, f"expected one CAD01-direct DWG validation row, found {len(validation)}")
    if validation:
        row = validation[0]
        require(row["design_layer"] == "DESIGN_BED_CAD01", "wrong active design layer")
        require(row["expected_vertices"] == row["roundtrip_vertices"], "DWG roundtrip vertex count mismatch")
        require(int(row["expected_vertices"]) == 28, "CAD01 direct delivery should contain 28 vertices")
        require(float(row["max_xy_error_m"]) < 1e-6, "DWG roundtrip geometry error too large")
        require(truth(row["cad01_direct_only"]), "DWG validation is not marked CAD01-direct only")

    source_dir = ROOT / "deliverables/cad/design_bed/source_csv"
    for stale in [
        "西支桥下_设计河床_局部型.csv",
        "西支桥下_设计河床_分布型.csv",
        "design_bed_reconstruction_audit.csv",
        "pier_station_mapping.csv",
    ]:
        require(not (source_dir / stale).exists(), f"retired reconstruction source remains in package: {stale}")

    manifest = ROOT / "deliverables/cad/design_bed/SHA256SUMS.txt"
    require(manifest.is_file(), "delivery SHA256SUMS.txt missing")
    if not manifest.is_file():
        return
    entries = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, relative = line.split("  ", 1)
        path = ROOT / "deliverables/cad/design_bed" / relative
        require(path.is_file(), f"manifest file missing: {relative}")
        if path.is_file():
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            require(actual == digest, f"manifest hash mismatch: {relative}")
        require("manual_review/" not in relative, "manual legacy review file leaked into active package")
        entries += 1
    require(entries >= 10, f"delivery manifest unexpectedly small: {entries}")


def main() -> None:
    check_layout()
    check_design_bed()
    check_hecras_results()
    check_cad_delivery()
    if FAILURES:
        for failure in FAILURES:
            print(f"[FAIL] {failure}")
        sys.exit(1)
    print("[PASS] active design bed is CAD01 direct geometry")
    print("[PASS] retired three-reconstruction logic is absent from active model/delivery")
    print("[PASS] p01-p04 frozen results + p05 geometry-audited HEC-RAS result")
    print("[PASS] active boundary evidence is restricted to unchanged current/protection cases")
    print("[PASS] CAD01-direct DXF/DWG package and manifest")


if __name__ == "__main__":
    main()
