#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path

import h5py

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'report'
DATA = REPORT / 'data'
DATA.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path):
    with path.open(encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def write_dat(path: Path, header: list[str], rows):
    with path.open('w', encoding='utf-8') as f:
        f.write(' '.join(header) + '\n')
        for row in rows:
            f.write(' '.join(str(v) for v in row) + '\n')

# 1) Bridge cross section and design-bed variants.
profiles = [
    ('current', ROOT / 'data/processed/cross_sections/西支桥下.csv'),
    ('design_center', ROOT / 'data/processed/design_bed/西支桥下_设计河床.csv'),
    ('design_local', ROOT / 'data/processed/design_bed/西支桥下_设计河床_局部型.csv'),
    ('design_distributed', ROOT / 'data/processed/design_bed/西支桥下_设计河床_分布型.csv'),
]
for name, path in profiles:
    rows = read_csv(path)
    write_dat(
        DATA / f'{name}_section.dat',
        ['station_m', 'elevation_m'],
        [(r['station_m_raw_direction'], r['elevation_m']) for r in rows],
    )

# Pier station controls.
pier_rows = read_csv(ROOT / 'data/processed/design_bed/pier_station_mapping.csv')
write_dat(
    DATA / 'pier_controls.dat',
    ['pier', 'station_m', 'design_elev_m', 'current_elev_m'],
    [(r['pier'], r['station_m'], r['design_mud_elevation_m'], r['existing_section_elevation_m']) for r in pier_rows],
)

# 2) Longitudinal WSE profile for five main cases directly from validated HDF.
BASE = 'Results/Steady/Output/Output Blocks/Base Output/Steady Profiles/Cross Sections'
XS_ATTR = 'Results/Steady/Output/Geometry Info/Cross Section Attributes'
case_meta = [
    ('Current', 'p01'),
    ('Protect05', 'p02'),
    ('Protect10', 'p03'),
    ('Protect20', 'p04'),
    ('DesignBed', 'p05'),
]
long_rows = []
for case_id, plan in case_meta:
    path = ROOT / 'hecras_model' / f'GanjiangWestBridge.{plan}.hdf'
    with h5py.File(path, 'r') as h:
        xs = h[XS_ATTR][:]
        stations = [x['Station'].decode('utf-8', errors='replace').strip() if isinstance(x['Station'], bytes) else str(x['Station']).strip() for x in xs]
        wse = h[f'{BASE}/Water Surface'][0]
        for rs, z in zip(stations, wse):
            long_rows.append((case_id, float(rs), float(z)))
with (DATA / 'wse_profiles.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['case_id', 'river_station', 'wse_m'])
    w.writerows(long_rows)
for case_id, _plan in case_meta:
    rows = [(rs, z) for cid, rs, z in long_rows if cid == case_id]
    rows.sort(key=lambda item: item[0])
    write_dat(DATA / f'wse_{case_id}.dat', ['river_station', 'wse_m'], rows)

# 3) Main-case key metrics.
five = read_csv(ROOT / 'results/hecras_steady_five_cases.csv')
for station in ('600', '500'):
    subset = [r for r in five if r['river_station'] == station]
    with (DATA / f'five_cases_rs{station}.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['case_id', 'wse_m', 'velocity_mps', 'flow_area_m2', 'froude', 'delta_wse_mm'])
        for r in subset:
            w.writerow([
                r['short_id'], r['wse_m'], r['velocity_mps'], r['flow_area_m2'], r['froude'],
                1000.0 * float(r['delta_wse_vs_p01_m'])
            ])

# 4) Downstream-boundary sensitivity at RS=600.
bound = read_csv(ROOT / 'results/hecras_boundary_sensitivity.csv')
rows = [r for r in bound if r['river_station'] == '600']
with (DATA / 'boundary_rs600.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['case_id', 'downstream_wse_m', 'delta_wse_mm', 'absolute_wse_m'])
    for r in rows:
        w.writerow([
            r['case_id'], r['downstream_wse_m'],
            1000.0 * float(r['delta_wse_vs_current_same_boundary_m']), r['wse_m']
        ])
for case_id in ('Protect05', 'Protect10', 'Protect20', 'DesignBed'):
    sub = [r for r in rows if r['case_id'] == case_id]
    sub.sort(key=lambda r: float(r['downstream_wse_m']))
    write_dat(
        DATA / f'boundary_{case_id}.dat',
        ['downstream_wse_m', 'delta_wse_mm', 'absolute_wse_m'],
        [(r['downstream_wse_m'], 1000.0 * float(r['delta_wse_vs_current_same_boundary_m']), r['wse_m']) for r in sub],
    )

# 5) Design reconstruction sensitivity.
design = read_csv(ROOT / 'results/hecras_design_bed_sensitivity.csv')
with (DATA / 'design_sensitivity.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['case_id', 'river_station', 'wse_m', 'delta_vs_center_mm', 'range_mm'])
    for r in design:
        w.writerow([
            r['short_id'], r['river_station'], r['wse_m'],
            1000.0 * float(r['delta_wse_vs_p05_m']),
            1000.0 * float(r['reconstruction_wse_range_m'])
        ])

print(f'Wrote report data to {DATA}')
