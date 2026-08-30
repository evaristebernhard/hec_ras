#!/usr/bin/env python3
"""Independent four-case cross-check using the open-source STREAM-1D solver.

The four directly comparable scenarios all use the current surveyed riverbed:
- current riverbed / existing piers: 360 m2 blocked area
- +0.5 m protection: 380 m2
- +1.0 m protection: 390 m2
- +2.0 m protection: 410 m2

Because the source table supplies blocked *area* rather than exact pier polygons,
we represent the obstruction as an equivalent horizontal-topped blocked strip
centered on the deepest part of the bridge cross section. To expose that
modeling uncertainty, the script repeats the calculation with 50, 100, and
200 m equivalent strip widths. For each width and case, the strip top is
calibrated with STREAM-1D itself so that the flow area removed at WSE=22.190 m
matches the tabulated blocked area.

The downstream stage is then calibrated separately for each strip width so the
current-riverbed case reproduces the CAD-labelled bridge flood level 22.190 m.
The quantity of interest is the incremental upstream backwater relative to the
current-riverbed case under the same calibrated downstream boundary.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Tuple

import stream1d as st

Q = 26_000.0
MANNING_N = 0.030
TARGET_BRIDGE_WSE = 22.190
CONTRACTION_C = 0.10
EXPANSION_C = 0.30

ROOT = Path("data/processed/cross_sections")
OUT = Path("results")

# STREAM-1D expects larger river station upstream and smaller downstream.
SECTION_FILES = [
    (1000.0, "西支上游500米.csv"),
    (600.0, "西支上游100米.csv"),
    (500.0, "西支桥下.csv"),
    (400.0, "西支下游100米.csv"),
    (0.0, "西支下游500米.csv"),
]

CASES: Dict[str, float] = {
    "现状河床线": 360.0,
    "0.5m防冲刷": 380.0,
    "1.0m防冲刷": 390.0,
    "2.0m防冲刷": 410.0,
}
REFERENCE_CASE = "现状河床线"
STRIP_WIDTHS = (50.0, 100.0, 200.0)


def read_profile(path: Path) -> Tuple[List[float], List[float]]:
    pts = []
    with path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            pts.append((float(row["station_m_raw_direction"]), float(row["elevation_m"])))
    pts.sort(key=lambda p: p[0])
    return [p[0] for p in pts], [p[1] for p in pts]


def xs_obj(river_station: float, filename: str, obstruction=None) -> st.CrossSection:
    x, y = read_profile(ROOT / filename)
    return st.CrossSection(
        station=river_station,
        x=x,
        y=y,
        n_stations=[x[0]],
        n_values=[MANNING_N],
        unit_system="Metric",
        blocked_obstructions=obstruction,
    )


def deepest_station() -> float:
    x, y = read_profile(ROOT / "西支桥下.csv")
    return x[min(range(len(y)), key=y.__getitem__)]


def obstruction_dict(width: float, top_elev: float):
    center = deepest_station()
    x, _ = read_profile(ROOT / "西支桥下.csv")
    left = max(x[0] + 1e-6, center - width / 2.0)
    right = min(x[-1] - 1e-6, center + width / 2.0)
    return [{"stations": [left, right], "elevations": [top_elev, top_elev]}]


def bridge_area_at_target(width: float, top_elev: float) -> float:
    """Ask STREAM-1D for effective bridge area at essentially fixed 22.190 m."""
    bridge = xs_obj(1.0, "西支桥下.csv", obstruction_dict(width, top_elev))
    downstream = xs_obj(0.0, "西支桥下.csv", None)
    result = st.solve_steady(
        st.SteadyInputs(
            cross_sections=[bridge, downstream],
            flow_rate=1.0,
            downstream_wsel=TARGET_BRIDGE_WSE,
            regime=0,
            coeff_contraction=CONTRACTION_C,
            coeff_expansion=EXPANSION_C,
        )
    )
    return float(result["area"][0])


def raw_bridge_area_at_target() -> float:
    bridge = xs_obj(1.0, "西支桥下.csv", None)
    downstream = xs_obj(0.0, "西支桥下.csv", None)
    result = st.solve_steady(
        st.SteadyInputs(
            cross_sections=[bridge, downstream],
            flow_rate=1.0,
            downstream_wsel=TARGET_BRIDGE_WSE,
            regime=0,
            coeff_contraction=CONTRACTION_C,
            coeff_expansion=EXPANSION_C,
        )
    )
    return float(result["area"][0])


def calibrate_obstruction_top(width: float, target_blocked_area: float, raw_area: float) -> float:
    target_effective = raw_area - target_blocked_area
    _, y = read_profile(ROOT / "西支桥下.csv")
    lo = min(y)
    hi = TARGET_BRIDGE_WSE

    def f(top: float) -> float:
        return bridge_area_at_target(width, top) - target_effective

    flo, fhi = f(lo), f(hi)
    if flo * fhi > 0:
        raise RuntimeError(
            f"Width {width} m cannot represent {target_blocked_area} m2: "
            f"area residuals {flo:.3f}, {fhi:.3f}"
        )
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if flo * fm <= 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return 0.5 * (lo + hi)


def make_reach(width: float, top_elev: float):
    sections = []
    for station, filename in SECTION_FILES:
        obs = obstruction_dict(width, top_elev) if station == 500.0 else None
        sections.append(xs_obj(station, filename, obs))
    return sections


def run_case(width: float, top_elev: float, downstream_wse: float):
    return st.solve_steady(
        st.SteadyInputs(
            cross_sections=make_reach(width, top_elev),
            flow_rate=Q,
            downstream_wsel=downstream_wse,
            regime=0,
            coeff_contraction=CONTRACTION_C,
            coeff_expansion=EXPANSION_C,
        )
    )


def calibrate_downstream(width: float, current_top: float) -> float:
    def f(wse: float) -> float:
        return float(run_case(width, current_top, wse)["wsel"][2]) - TARGET_BRIDGE_WSE

    lo, hi = 18.0, 25.0
    flo, fhi = f(lo), f(hi)
    if flo * fhi > 0:
        raise RuntimeError(
            f"Cannot calibrate downstream stage for width={width}: {flo:.3f}, {fhi:.3f}"
        )
    for _ in range(45):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if flo * fm <= 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return 0.5 * (lo + hi)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    raw_area = raw_bridge_area_at_target()
    print(f"STREAM-1D raw bridge area at WSE={TARGET_BRIDGE_WSE:.3f}: {raw_area:.3f} m2")

    rows = []
    tops_rows = []

    for width in STRIP_WIDTHS:
        tops = {
            case: calibrate_obstruction_top(width, blocked_area, raw_area)
            for case, blocked_area in CASES.items()
        }
        ds_wse = calibrate_downstream(width, tops[REFERENCE_CASE])
        runs = {case: run_case(width, tops[case], ds_wse) for case in CASES}

        ref = runs[REFERENCE_CASE]
        ref_up100 = float(ref["wsel"][1])
        ref_up500 = float(ref["wsel"][0])

        print(f"\nEquivalent blocked strip width = {width:.0f} m; calibrated downstream WSE={ds_wse:.4f} m")
        for case, blocked_area in CASES.items():
            r = runs[case]
            bridge_wse = float(r["wsel"][2])
            up100 = float(r["wsel"][1])
            up500 = float(r["wsel"][0])
            vel = float(r["velocity"][2])
            eff_area = float(r["area"][2])
            froude = float(r["froude"][2])
            d100 = up100 - ref_up100
            d500 = up500 - ref_up500
            print(
                f"{case:12s} top={tops[case]:7.3f} m  bridge={bridge_wse:8.4f} m  "
                f"up100 dWSE={d100*1000:+7.2f} mm  up500 dWSE={d500*1000:+7.2f} mm  "
                f"Vbridge={vel:5.3f} m/s"
            )
            rows.append([
                width, case, blocked_area, tops[case], ds_wse, bridge_wse,
                up100, d100, up500, d500, vel, eff_area, froude,
            ])
            tops_rows.append([width, case, blocked_area, tops[case]])

    with (OUT / "stream1d_four_cases.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([
            "equivalent_strip_width_m", "case", "target_blocked_area_m2", "obstruction_top_m",
            "calibrated_downstream_wse_m", "bridge_wse_m", "up100_wse_m",
            "delta_up100_vs_current_m", "up500_wse_m", "delta_up500_vs_current_m",
            "bridge_velocity_m_s", "bridge_effective_area_m2", "bridge_froude",
        ])
        w.writerows(rows)

    with (OUT / "stream1d_obstruction_calibration.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([
            "equivalent_strip_width_m", "case", "target_blocked_area_m2", "obstruction_top_m",
        ])
        w.writerows(tops_rows)


if __name__ == "__main__":
    main()
