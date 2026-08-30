#!/usr/bin/env python3
"""Minimal reproducible 1D steady-flow comparison for the bridge reach.

This is a transparent Python standard-step model intended to produce a first
engineering comparison before a formal HEC-RAS project is available.

Assumptions in this first-pass model:
- Steady Q = 26,000 m3/s.
- Five surveyed/extracted cross-sections are ordered by their names at
  -500 m, -100 m, 0 m (bridge), +100 m, +500 m relative to the bridge.
- Subcritical standard-step solution from downstream to upstream.
- One composite Manning n for the whole wetted section.
- Bridge blockage is represented by an equivalent reduction of flow area at
  the bridge section only. Effective hydraulic radius is A_eff/P.
- No explicit pier drag coefficient / bridge deck / pressure-flow model is
  included in this first-pass comparison.
- The downstream water level is calibrated so the CURRENT-RIVERBED case
  (360 m2 blockage) reproduces the CAD-labelled bridge flood level 22.190 m.

The model is deliberately simple: it makes every assumption visible and gives
us a reproducible screening result plus sensitivity checks. It is not a
replacement for a fully configured HEC-RAS bridge model.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from scipy.optimize import brentq

G = 9.80665
Q = 26_000.0
TARGET_BRIDGE_WSE = 22.190
DEFAULT_N = 0.030
# First-pass bridge energy-loss coefficients, consistent with a mild approach
# contraction and a more pronounced downstream expansion. These are modeling
# assumptions and are sensitivity-tested below.
CONTRACTION_C = 0.10
EXPANSION_C = 0.30
PIER_DRAG_CD = 1.00

ROOT = Path("data/processed/cross_sections")
OUT = Path("results")

# River coordinate increases downstream.
SECTION_FILES = [
    (-500.0, "西支上游500米.csv"),
    (-100.0, "西支上游100米.csv"),
    (0.0, "西支桥下.csv"),
    (100.0, "西支下游100米.csv"),
    (500.0, "西支下游500米.csv"),
]

# The four directly comparable scenarios share the same current surveyed
# cross-sections. The separate "设计河床线" row in the source table has a
# different flood-flow area (5700 vs 6800 m2), so it requires a different
# riverbed geometry and must not be mimicked by changing blockage alone.
CASES = {
    "现状河床线": 360.0,
    "0.5m防冲刷": 380.0,
    "1.0m防冲刷": 390.0,
    "2.0m防冲刷": 410.0,
}

REFERENCE_CASE = "现状河床线"


@dataclass
class Geometry:
    area: float
    wetted_perimeter: float
    top_width: float
    hydraulic_radius: float
    hydraulic_depth: float


@dataclass
class State:
    river_m: float
    name: str
    wse: float
    area_raw: float
    area_eff: float
    wetted_perimeter: float
    hydraulic_radius_eff: float
    velocity: float
    velocity_head: float
    energy: float
    friction_slope: float
    froude: float
    blockage: float


def read_profile(path: Path) -> List[Tuple[float, float]]:
    pts: List[Tuple[float, float]] = []
    with path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            pts.append((float(row["station_m_raw_direction"]), float(row["elevation_m"])))
    pts.sort(key=lambda p: p[0])
    return pts


def _submerged_piece(x1: float, z1: float, x2: float, z2: float, wse: float):
    """Return submerged endpoints on one linear terrain segment, or None."""
    d1 = wse - z1
    d2 = wse - z2
    if d1 <= 0.0 and d2 <= 0.0:
        return None
    if d1 >= 0.0 and d2 >= 0.0:
        return x1, z1, x2, z2

    # Crossing with WSE.
    t = (wse - z1) / (z2 - z1)
    xc = x1 + t * (x2 - x1)
    if d1 > 0.0:
        return x1, z1, xc, wse
    return xc, wse, x2, z2


def geometry(profile: List[Tuple[float, float]], wse: float) -> Geometry:
    area = 0.0
    perim = 0.0
    top_width = 0.0

    for (x1, z1), (x2, z2) in zip(profile, profile[1:]):
        piece = _submerged_piece(x1, z1, x2, z2, wse)
        if piece is None:
            continue
        xa, za, xb, zb = piece
        dx = xb - xa
        if dx <= 0.0:
            continue
        da = max(0.0, wse - za)
        db = max(0.0, wse - zb)
        area += dx * (da + db) / 2.0
        perim += math.hypot(dx, zb - za)
        top_width += dx

    if area <= 0.0 or perim <= 0.0 or top_width <= 0.0:
        raise ValueError(f"No valid wetted geometry at WSE={wse:.3f}")

    r = area / perim
    d = area / top_width
    return Geometry(area, perim, top_width, r, d)


def make_state(
    river_m: float,
    name: str,
    profile: List[Tuple[float, float]],
    wse: float,
    n: float,
    blockage: float,
) -> State:
    geo = geometry(profile, wse)
    area_eff = geo.area - blockage
    if area_eff <= 1.0:
        raise ValueError(
            f"Effective area <= 1 m2 at {name}, WSE={wse:.3f}, blockage={blockage:.1f}"
        )
    r_eff = area_eff / geo.wetted_perimeter
    velocity = Q / area_eff
    vh = velocity * velocity / (2.0 * G)
    sf = (Q * n / (area_eff * (r_eff ** (2.0 / 3.0)))) ** 2
    hyd_depth_eff = area_eff / geo.top_width
    froude = velocity / math.sqrt(G * hyd_depth_eff)
    return State(
        river_m=river_m,
        name=name,
        wse=wse,
        area_raw=geo.area,
        area_eff=area_eff,
        wetted_perimeter=geo.wetted_perimeter,
        hydraulic_radius_eff=r_eff,
        velocity=velocity,
        velocity_head=vh,
        energy=wse + vh,
        friction_slope=sf,
        froude=froude,
        blockage=blockage,
    )


def solve_upstream_state(
    upstream_info,
    downstream_state: State,
    downstream_profile,
    n: float,
    bridge_blockage: float,
) -> State:
    river_u, name_u, profile_u = upstream_info
    river_d = downstream_state.river_m
    length = river_d - river_u
    if length <= 0:
        raise ValueError("Sections are not ordered upstream -> downstream")

    blockage_u = bridge_blockage if abs(river_u) < 1e-9 else 0.0

    def residual(wse_u: float) -> float:
        su = make_state(river_u, name_u, profile_u, wse_u, n, blockage_u)
        # Standard-step friction loss using average friction slope.
        hf = length * 0.5 * (su.friction_slope + downstream_state.friction_slope)

        # Local bridge losses. Flow direction is upstream -> downstream.
        # 0 -> +100 m is the expansion out of the contracted bridge section.
        # -100 -> 0 m is the contraction into the bridge plus a simple pier
        # drag head-loss estimate F/(rho*g*A) = Cd*(Ablock/Aflow)*V^2/(2g).
        hminor = 0.0
        if abs(river_u) < 1e-9 and abs(downstream_state.river_m - 100.0) < 1e-9:
            hminor += EXPANSION_C * abs(su.velocity_head - downstream_state.velocity_head)
        elif abs(river_u + 100.0) < 1e-9 and abs(downstream_state.river_m) < 1e-9:
            hminor += CONTRACTION_C * abs(downstream_state.velocity_head - su.velocity_head)
            if downstream_state.blockage > 0.0:
                blockage_ratio = downstream_state.blockage / downstream_state.area_raw
                hminor += PIER_DRAG_CD * blockage_ratio * downstream_state.velocity_head

        return su.energy - downstream_state.energy - hf - hminor

    min_elev = min(z for _, z in profile_u)
    lo = max(min_elev + 0.05, downstream_state.wse - 5.0)
    hi = max(downstream_state.wse + 10.0, TARGET_BRIDGE_WSE + 8.0)

    # The specific-energy relation may have both a low-stage supercritical
    # root and a high-stage subcritical root. Scan all valid sign changes and
    # choose the highest root with Fr < 1.
    nscan = 320
    xs = [lo + (hi - lo) * i / nscan for i in range(nscan + 1)]
    samples = []
    for x in xs:
        try:
            samples.append((x, residual(x)))
        except ValueError:
            continue

    brackets = []
    for (x1, f1), (x2, f2) in zip(samples, samples[1:]):
        if f1 == 0.0:
            brackets.append((x1, x1))
        elif f2 == 0.0 or (f1 < 0.0 < f2) or (f1 > 0.0 > f2):
            brackets.append((x1, x2))

    candidates = []
    for a, b in brackets:
        wse = a if a == b else brentq(residual, a, b, xtol=1e-10, rtol=1e-12, maxiter=200)
        state = make_state(river_u, name_u, profile_u, wse, n, blockage_u)
        if state.froude < 1.0:
            candidates.append(state)

    if not candidates:
        raise RuntimeError(f"Could not find a subcritical upstream root at {name_u}")

    return max(candidates, key=lambda s: s.wse)


def load_sections():
    sections = []
    for river_m, filename in SECTION_FILES:
        path = ROOT / filename
        sections.append((river_m, path.stem, read_profile(path)))
    return sections


def run_profile(sections, downstream_wse: float, n: float, bridge_blockage: float) -> List[State]:
    river_d, name_d, profile_d = sections[-1]
    sd = make_state(river_d, name_d, profile_d, downstream_wse, n, 0.0)
    states_down_to_up = [sd]
    current = sd
    # Walk from downstream toward upstream.
    for idx in range(len(sections) - 2, -1, -1):
        su = solve_upstream_state(sections[idx], current, sections[idx + 1][2], n, bridge_blockage)
        states_down_to_up.append(su)
        current = su
    return list(reversed(states_down_to_up))


def bridge_state(states: Iterable[State]) -> State:
    return next(s for s in states if abs(s.river_m) < 1e-9)


def calibrate_downstream_wse(sections, n: float) -> float:
    blockage = CASES[REFERENCE_CASE]

    def objective(ds_wse: float) -> float:
        states = run_profile(sections, ds_wse, n, blockage)
        return bridge_state(states).wse - TARGET_BRIDGE_WSE

    # Flood stage is expected to be near 22 m; the broad bracket makes this
    # robust to the first-pass Manning assumption.
    lo, hi = 10.0, 26.0
    f_lo, f_hi = objective(lo), objective(hi)
    if f_lo * f_hi > 0:
        raise RuntimeError(
            f"Could not calibrate downstream WSE: objective({lo})={f_lo:.3f}, objective({hi})={f_hi:.3f}"
        )
    return brentq(objective, lo, hi, xtol=1e-9, rtol=1e-11, maxiter=100)


def write_case_results(all_cases: Dict[str, List[State]], downstream_wse: float, n: float) -> None:
    OUT.mkdir(exist_ok=True)
    detail_path = OUT / "steady_1d_cases.csv"
    with detail_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([
            "case", "river_m", "section", "wse_m", "raw_area_m2", "effective_area_m2",
            "blockage_m2", "velocity_m_s", "velocity_head_m", "energy_m", "friction_slope",
            "hydraulic_radius_m", "froude"
        ])
        for case, states in all_cases.items():
            for s in states:
                w.writerow([
                    case, f"{s.river_m:.1f}", s.name, f"{s.wse:.6f}", f"{s.area_raw:.3f}",
                    f"{s.area_eff:.3f}", f"{s.blockage:.3f}", f"{s.velocity:.6f}",
                    f"{s.velocity_head:.6f}", f"{s.energy:.6f}", f"{s.friction_slope:.8f}",
                    f"{s.hydraulic_radius_eff:.6f}", f"{s.froude:.6f}"
                ])

    ref_bridge = bridge_state(all_cases[REFERENCE_CASE])
    ref_up100 = next(s for s in all_cases[REFERENCE_CASE] if s.river_m == -100.0)
    summary_path = OUT / "steady_1d_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([
            "case", "blockage_m2", "bridge_wse_m", "delta_bridge_wse_vs_current_m",
            "up100_wse_m", "delta_up100_wse_vs_current_m", "bridge_velocity_m_s",
            "bridge_effective_area_m2", "bridge_froude", "up500_wse_m"
        ])
        for case, states in all_cases.items():
            b = bridge_state(states)
            u100 = next(s for s in states if s.river_m == -100.0)
            u500 = next(s for s in states if s.river_m == -500.0)
            w.writerow([
                case, f"{CASES[case]:.1f}", f"{b.wse:.6f}", f"{b.wse-ref_bridge.wse:.6f}",
                f"{u100.wse:.6f}", f"{u100.wse-ref_up100.wse:.6f}", f"{b.velocity:.6f}",
                f"{b.area_eff:.3f}", f"{b.froude:.6f}", f"{u500.wse:.6f}"
            ])

    md_path = OUT / "steady_1d_notes.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("# 1D steady-flow first-pass results\n\n")
        f.write(f"- Q = {Q:,.0f} m³/s\n")
        f.write(f"- Manning n = {n:.3f}\n")
        f.write(f"- CAD-labelled flood level used for calibration = {TARGET_BRIDGE_WSE:.3f} m\n")
        f.write(f"- Calibrated downstream (+500 m) WSE = {downstream_wse:.3f} m\n")
        f.write(f"- Calibration reference = {REFERENCE_CASE}, blockage {CASES[REFERENCE_CASE]:.0f} m²\n\n")
        f.write("Bridge blockage is represented as equivalent flow-area reduction only. "
                "This is a screening model, not an explicit HEC-RAS bridge/pier model.\n")


def run_sensitivity(sections, calibrated_downstream_wse: float) -> None:
    OUT.mkdir(exist_ok=True)
    path = OUT / "steady_1d_sensitivity.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([
            "manning_n", "case", "downstream_wse_fixed_m", "bridge_wse_m",
            "delta_bridge_wse_vs_same_n_current_m", "up100_wse_m",
            "delta_up100_wse_vs_same_n_current_m", "bridge_velocity_m_s", "bridge_froude"
        ])
        for n in (0.025, 0.030, 0.035):
            cases = {
                case: run_profile(sections, calibrated_downstream_wse, n, blockage)
                for case, blockage in CASES.items()
            }
            ref_b = bridge_state(cases[REFERENCE_CASE])
            ref_u = next(s for s in cases[REFERENCE_CASE] if s.river_m == -100.0)
            for case, states in cases.items():
                b = bridge_state(states)
                u = next(s for s in states if s.river_m == -100.0)
                w.writerow([
                    f"{n:.3f}", case, f"{calibrated_downstream_wse:.6f}", f"{b.wse:.6f}",
                    f"{b.wse-ref_b.wse:.6f}", f"{u.wse:.6f}", f"{u.wse-ref_u.wse:.6f}",
                    f"{b.velocity:.6f}", f"{b.froude:.6f}"
                ])


def main() -> None:
    sections = load_sections()
    downstream_wse = calibrate_downstream_wse(sections, DEFAULT_N)
    all_cases = {
        case: run_profile(sections, downstream_wse, DEFAULT_N, blockage)
        for case, blockage in CASES.items()
    }
    write_case_results(all_cases, downstream_wse, DEFAULT_N)
    run_sensitivity(sections, downstream_wse)

    print(f"Calibrated downstream WSE (+500 m): {downstream_wse:.4f} m")
    print(f"Reference bridge WSE target: {TARGET_BRIDGE_WSE:.3f} m")
    ref = bridge_state(all_cases[REFERENCE_CASE])
    for case, states in all_cases.items():
        b = bridge_state(states)
        u100 = next(s for s in states if s.river_m == -100.0)
        print(
            f"{case:12s} blockage={CASES[case]:6.1f} m2  "
            f"bridge WSE={b.wse:8.4f} m  dWSE={b.wse-ref.wse:+.4f} m  "
            f"Vbridge={b.velocity:5.3f} m/s  Fr={b.froude:5.3f}  "
            f"up100 WSE={u100.wse:8.4f} m"
        )


if __name__ == "__main__":
    main()
