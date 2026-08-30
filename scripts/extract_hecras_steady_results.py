#!/usr/bin/env python3
"""Validate and export the five main and two design-bed sensitivity plans.

The checks here are intentionally tied to the two silent failures encountered
while creating the project: the project must be SI, and the bridge cross
section (RS 500) must have blocked-obstruction mode enabled in the computed
HDF geometry.  A successful Ras.exe exit code alone is not sufficient.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import h5py


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "hecras_model"
RESULTS_DIR = ROOT / "results"

LEGACY_PLANS = [
    ("p01", "Current", "现状河床线", 360.0),
    ("p02", "Protect05", "0.5m防冲刷", 380.0),
    ("p03", "Protect10", "1.0m防冲刷", 390.0),
    ("p04", "Protect20", "2.0m防冲刷", 410.0),
]

DESIGN_PLANS = [
    ("p05", "DesignBed", "设计河床线-中心方案", 280.0),
    ("p06", "DesignLocal", "设计河床线-局部型敏感性", 280.0),
    ("p07", "DesignDistrib", "设计河床线-分布型敏感性", 280.0),
]

PLANS = LEGACY_PLANS + DESIGN_PLANS
MAIN_PLANS = LEGACY_PLANS + DESIGN_PLANS[:1]
KEY_STATIONS = {"500", "600"}

BASE = (
    "Results/Steady/Output/Output Blocks/Base Output/"
    "Steady Profiles/Cross Sections"
)
XS_ATTRIBUTES = "Results/Steady/Output/Geometry Info/Cross Section Attributes"
GEOMETRY_ATTRIBUTES = "Geometry/Cross Sections/Attributes"


def decode(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    return str(value).strip()


def read_plan(plan: str) -> tuple[list[dict[str, object]], dict[str, object]]:
    hdf_path = MODEL_DIR / f"GanjiangWestBridge.{plan}.hdf"
    if not hdf_path.exists():
        raise FileNotFoundError(f"Missing computed HEC-RAS result: {hdf_path}")

    with h5py.File(hdf_path, "r") as hdf:
        units = decode(hdf.attrs.get("Units System", ""))
        if units != "SI Units":
            raise RuntimeError(f"{plan}: expected SI Units, HDF reports {units!r}")

        geometry = hdf[GEOMETRY_ATTRIBUTES][:]
        obstruction_modes = {
            decode(row["RS"]): int(row["Obstr Block Mode"]) for row in geometry
        }
        if obstruction_modes.get("500") != 1:
            raise RuntimeError(
                f"{plan}: blocked obstruction did not propagate to RS 500 HDF geometry"
            )

        xs = hdf[XS_ATTRIBUTES][:]
        stations = [decode(row["Station"]) for row in xs]
        water_surface = hdf[f"{BASE}/Water Surface"][0]
        energy_grade = hdf[f"{BASE}/Energy Grade"][0]
        flow = hdf[f"{BASE}/Flow"][0]
        additional = f"{BASE}/Additional Variables"
        velocity = hdf[f"{additional}/Velocity Total"][0]
        flow_area = hdf[f"{additional}/Area Flow Total"][0]
        hydraulic_depth = hdf[f"{additional}/Hydraulic Depth Total"][0]
        arrays = (
            water_surface,
            energy_grade,
            flow,
            velocity,
            flow_area,
            hydraulic_depth,
        )
        if any(len(stations) != len(values) for values in arrays):
            raise RuntimeError(f"{plan}: HDF result arrays have inconsistent lengths")

        messages = decode(hdf["Results/Summary/Compute Messages (text)"][0])
        if "Finished Steady Flow Simulation" not in messages:
            raise RuntimeError(f"{plan}: HEC-RAS completion marker is absent")
        lower_messages = messages.lower()
        if "error" in lower_messages or "warning" in lower_messages:
            raise RuntimeError(f"{plan}: HEC-RAS compute messages contain error/warning")

        rows = [
            {
                "river_station": station,
                "wse_m": float(wse),
                "energy_grade_m": float(energy),
                "flow_m3s": float(q),
                "velocity_mps": float(v),
                "flow_area_m2": float(area),
                "hydraulic_depth_m": float(depth),
                "froude": float(v) / math.sqrt(9.80665 * float(depth)),
            }
            for station, wse, energy, q, v, area, depth in zip(
                stations,
                water_surface,
                energy_grade,
                flow,
                velocity,
                flow_area,
                hydraulic_depth,
            )
        ]
        validation = {
            "plan": plan,
            "units": units,
            "rs500_obstr_block_mode": obstruction_modes["500"],
            "steady_completion_marker": True,
            "error_warning_absent": True,
            "hdf_file": hdf_path.name,
        }
        return rows, validation


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    plan_rows: dict[str, list[dict[str, object]]] = {}
    validations: list[dict[str, object]] = []
    for plan, _short_id, _case, _blockage in PLANS:
        rows, validation = read_plan(plan)
        plan_rows[plan] = rows
        validations.append(validation)

    baseline = {
        str(row["river_station"]): float(row["wse_m"])
        for row in plan_rows["p01"]
    }

    # The original 2026-08-30 baseline used an obstruction top equal to the
    # 22.190 m calibration WSE.  That representation can be artificially
    # overtopped when modeled WSE rises above 22.190 m, so it is preserved as a
    # historical pre-fix artifact but is no longer the active parity target.
    frozen_path = RESULTS_DIR / "hecras_steady_four_cases_baseline_v2_20260830.csv"
    parity_rows = []
    baseline_created = False
    if frozen_path.exists():
        with frozen_path.open(encoding="utf-8-sig") as stream:
            frozen_wse = {
                (row["plan"], row["river_station"]): float(row["wse_m"])
                for row in csv.DictReader(stream)
            }
        for plan, _short_id, _case, _blockage in LEGACY_PLANS:
            for row in plan_rows[plan]:
                station = str(row["river_station"])
                previous = frozen_wse[(plan, station)]
                rerun = float(row["wse_m"])
                difference = rerun - previous
                parity_rows.append(
                    {
                        "plan": plan,
                        "river_station": station,
                        "baseline_wse_m": f"{previous:.6f}",
                        "rerun_wse_m": f"{rerun:.6f}",
                        "difference_m": f"{difference:.9f}",
                        "tolerance_m": "0.000001000",
                        "parity_verified": abs(difference) <= 1e-6,
                        "reference": "v2_frozen_baseline",
                    }
                )
    else:
        # Bootstrap the corrected baseline only after matching the independently
        # executed Base branch of the downstream-boundary sensitivity project.
        sensitivity_path = RESULTS_DIR / "hecras_boundary_sensitivity.csv"
        if not sensitivity_path.exists():
            raise FileNotFoundError(
                "Corrected v2 baseline absent and boundary sensitivity reference missing"
            )
        case_to_plan = {
            "Current": "p01",
            "Protect05": "p02",
            "Protect10": "p03",
            "Protect20": "p04",
        }
        with sensitivity_path.open(encoding="utf-8-sig") as stream:
            sensitivity_wse = {
                (case_to_plan[row["case_id"]], row["river_station"]): float(row["wse_m"])
                for row in csv.DictReader(stream)
                if row["boundary_id"] == "Base" and row["case_id"] in case_to_plan
            }
        for plan, _short_id, _case, _blockage in LEGACY_PLANS:
            for row in plan_rows[plan]:
                station = str(row["river_station"])
                key = (plan, station)
                if key not in sensitivity_wse:
                    continue
                previous = sensitivity_wse[key]
                rerun = float(row["wse_m"])
                difference = rerun - previous
                parity_rows.append(
                    {
                        "plan": plan,
                        "river_station": station,
                        "baseline_wse_m": f"{previous:.6f}",
                        "rerun_wse_m": f"{rerun:.6f}",
                        "difference_m": f"{difference:.9f}",
                        "tolerance_m": "0.000001000",
                        "parity_verified": abs(difference) <= 1e-6,
                        "reference": "boundary_sensitivity_base",
                    }
                )
        if not parity_rows:
            raise RuntimeError("No Base-boundary parity rows were available for v2 bootstrap")
        baseline_created = True

    if not all(bool(row["parity_verified"]) for row in parity_rows):
        raise RuntimeError("p01-p04 corrected WSE parity exceeds 1e-6 m")

    if baseline_created:
        with frozen_path.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=["plan", "river_station", "wse_m"])
            writer.writeheader()
            for plan, _short_id, _case, _blockage in LEGACY_PLANS:
                for row in plan_rows[plan]:
                    writer.writerow(
                        {
                            "plan": plan,
                            "river_station": str(row["river_station"]),
                            "wse_m": f"{float(row['wse_m']):.6f}",
                        }
                    )

    parity_path = RESULTS_DIR / "hecras_p01_p04_parity_v2.csv"
    with parity_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(parity_rows[0]))
        writer.writeheader()
        writer.writerows(parity_rows)

    detail_path = RESULTS_DIR / "hecras_steady_four_cases.csv"
    with detail_path.open("w", newline="", encoding="utf-8-sig") as stream:
        fieldnames = [
            "plan",
            "short_id",
            "case",
            "blockage_m2",
            "river_station",
            "wse_m",
            "energy_grade_m",
            "flow_m3s",
            "velocity_mps",
            "flow_area_m2",
            "hydraulic_depth_m",
            "froude",
            "delta_wse_vs_p01_m",
        ]
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for plan, short_id, case, blockage in LEGACY_PLANS:
            for row in plan_rows[plan]:
                station = str(row["river_station"])
                wse = float(row["wse_m"])
                writer.writerow(
                    {
                        "plan": plan,
                        "short_id": short_id,
                        "case": case,
                        "blockage_m2": f"{blockage:.3f}",
                        "river_station": station,
                        "wse_m": f"{wse:.6f}",
                        "energy_grade_m": f"{float(row['energy_grade_m']):.6f}",
                        "flow_m3s": f"{float(row['flow_m3s']):.6f}",
                        "velocity_mps": f"{float(row['velocity_mps']):.6f}",
                        "flow_area_m2": f"{float(row['flow_area_m2']):.3f}",
                        "hydraulic_depth_m": f"{float(row['hydraulic_depth_m']):.6f}",
                        "froude": f"{float(row['froude']):.6f}",
                        "delta_wse_vs_p01_m": f"{wse - baseline[station]:.6f}",
                    }
                )

    # Keep the legacy validation filename limited to the original four plans.
    validation_path = RESULTS_DIR / "hecras_steady_validation.csv"
    with validation_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(validations[0]))
        writer.writeheader()
        writer.writerows(validations[:4])

    validation_all_path = RESULTS_DIR / "hecras_steady_validation_all_plans.csv"
    with validation_all_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(validations[0]))
        writer.writeheader()
        writer.writerows(validations)

    metric_fields = [
        "plan",
        "short_id",
        "case",
        "blockage_m2",
        "river_station",
        "wse_m",
        "energy_grade_m",
        "velocity_mps",
        "flow_area_m2",
        "froude",
        "delta_wse_vs_p01_m",
        "delta_energy_grade_vs_p01_m",
        "delta_velocity_vs_p01_mps",
        "delta_flow_area_vs_p01_m2",
        "delta_froude_vs_p01",
    ]

    def comparison_row(
        plan: str, short_id: str, case: str, blockage: float, row: dict[str, object]
    ) -> dict[str, object]:
        station = str(row["river_station"])
        current = next(
            item for item in plan_rows["p01"] if str(item["river_station"]) == station
        )
        return {
            "plan": plan,
            "short_id": short_id,
            "case": case,
            "blockage_m2": f"{blockage:.3f}",
            "river_station": station,
            "wse_m": f"{float(row['wse_m']):.6f}",
            "energy_grade_m": f"{float(row['energy_grade_m']):.6f}",
            "velocity_mps": f"{float(row['velocity_mps']):.6f}",
            "flow_area_m2": f"{float(row['flow_area_m2']):.3f}",
            "froude": f"{float(row['froude']):.6f}",
            "delta_wse_vs_p01_m": f"{float(row['wse_m']) - float(current['wse_m']):.6f}",
            "delta_energy_grade_vs_p01_m": f"{float(row['energy_grade_m']) - float(current['energy_grade_m']):.6f}",
            "delta_velocity_vs_p01_mps": f"{float(row['velocity_mps']) - float(current['velocity_mps']):.6f}",
            "delta_flow_area_vs_p01_m2": f"{float(row['flow_area_m2']) - float(current['flow_area_m2']):.3f}",
            "delta_froude_vs_p01": f"{float(row['froude']) - float(current['froude']):.6f}",
        }

    five_path = RESULTS_DIR / "hecras_steady_five_cases.csv"
    with five_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=metric_fields)
        writer.writeheader()
        for plan, short_id, case, blockage in MAIN_PLANS:
            for row in plan_rows[plan]:
                if str(row["river_station"]) in KEY_STATIONS:
                    writer.writerow(comparison_row(plan, short_id, case, blockage, row))

    design_values: dict[str, dict[str, float]] = {}
    for station in KEY_STATIONS:
        values = {
            plan: float(
                next(row for row in plan_rows[plan] if str(row["river_station"]) == station)[
                    "wse_m"
                ]
            )
            for plan, _short_id, _case, _blockage in DESIGN_PLANS
        }
        center_effect = abs(values["p05"] - baseline[station])
        spread = max(values.values()) - min(values.values())
        design_values[station] = {
            "spread": spread,
            "center_effect": center_effect,
            "ratio": spread / center_effect if center_effect else math.inf,
        }

    sensitivity_fields = metric_fields + [
        "delta_wse_vs_p05_m",
        "reconstruction_wse_range_m",
        "center_effect_vs_current_m",
        "range_to_center_effect_ratio",
        "stable_screening_value_under_20pct_rule",
    ]
    sensitivity_path = RESULTS_DIR / "hecras_design_bed_sensitivity.csv"
    with sensitivity_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=sensitivity_fields)
        writer.writeheader()
        for plan, short_id, case, blockage in DESIGN_PLANS:
            for row in plan_rows[plan]:
                station = str(row["river_station"])
                if station not in KEY_STATIONS:
                    continue
                output = comparison_row(plan, short_id, case, blockage, row)
                center = next(
                    item for item in plan_rows["p05"] if str(item["river_station"]) == station
                )
                stats = design_values[station]
                output.update(
                    {
                        "delta_wse_vs_p05_m": f"{float(row['wse_m']) - float(center['wse_m']):.6f}",
                        "reconstruction_wse_range_m": f"{stats['spread']:.6f}",
                        "center_effect_vs_current_m": f"{stats['center_effect']:.6f}",
                        "range_to_center_effect_ratio": f"{stats['ratio']:.6f}",
                        "stable_screening_value_under_20pct_rule": stats["ratio"] < 0.20,
                    }
                )
                writer.writerow(output)

    print(f"Validated {len(PLANS)} HEC-RAS plans")
    print(f"Wrote {detail_path}")
    print(f"Wrote {validation_path}")
    print(f"Wrote {five_path}")
    print(f"Wrote {sensitivity_path}")
    if baseline_created:
        print("[V2 BASELINE CREATED] corrected p01-p04 matched boundary-sensitivity Base runs")
    else:
        print("[PARITY VERIFIED] corrected p01-p04 WSE <= 1e-6 m from v2 frozen baseline")


if __name__ == "__main__":
    main()
