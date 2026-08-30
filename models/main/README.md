# GanjiangWestBridge HEC-RAS 7.0.1 model

## Model scope

This is the active **1D steady-flow equivalent-blockage screening model** for the Ganjiang West Branch bridge reach. It is not an explicit HEC-RAS Bridge/Culvert model and must not be used to infer local pier vortices or scour depth.

## Active inputs

- `GanjiangWestBridge.prj`
- `GanjiangWestBridge.f01`: Q = 26,000 m³/s, downstream Known WS = 22.049342 m
- `GanjiangWestBridge.g01` / `p01`: current surveyed bed, 360 m² equivalent blockage
- `GanjiangWestBridge.g02` / `p02`: 0.5 m protection, 380 m² equivalent blockage
- `GanjiangWestBridge.g03` / `p03`: 1.0 m protection, 390 m² equivalent blockage
- `GanjiangWestBridge.g04` / `p04`: 2.0 m protection, 410 m² equivalent blockage
- `GanjiangWestBridge.g05` / `p05`: **CAD 01 direct construction-period/design bed**, 280 m² equivalent blockage

The former centre/local/distributed constrained design-bed reconstructions are retired. They are retained only under `archive/legacy_constrained_reconstruction/` and are not active plans.

## CAD-direct design-bed provenance

The active RS 500 design profile comes from `data/processed/design_bed/西支桥下_设计河床.csv`. It is recovered from CAD 01 by selecting the semantically labelled `中地面线（建设期)` profile through its leader, then transforming CAD coordinates with the matching `上游地面线（现状)` profile.

The 15#/16#/17# design mud elevations (4.27/5.40/9.56 m) are independent cross-checks and match the recovered CAD line exactly. They are no longer used to construct an artificial riverbed.

At WSE 22.190 m the direct CAD profile has a gross area of 5934.568 m² and a net area of 5654.568 m² after the 280 m² blockage. The older tabulated 5980/5700 m² values differ by 45.432 m² (~0.76%). The active model gives precedence to the complete CAD geometry rather than modifying it to force the table area.

## Equivalent-blockage v2 convention

The obstruction lateral width is solved so that its submerged area at WSE 22.190 m equals the target blockage area. The obstruction top elevation is a numerical sentinel of 50 m so HEC-RAS cannot artificially pass flow over the equivalent blockage in the studied range. The 50 m value is not a physical bridge-deck or pier elevation.

## HDF geometry audit

Run:

```bash
.venv/bin/python scripts/audit_hecras_design_bed_geometry.py
```

The audit reads RS 500 station/elevation values from `GanjiangWestBridge.p05.hdf` and compares them point-by-point with the active CAD-direct CSV. The current p05 HDF passes this check and produces:

- RS 600 WSE = 22.576809 m, +193.558 mm relative to the frozen current-bed baseline;
- RS 500 WSE = 21.962107 m;
- RS 500 mean velocity = 4.691635 m/s;
- RS 500 Froude = 0.447357.

Outputs:

- `results/hecras_design_bed_cad_direct_hdf_audit.csv`
- `results/hecras_design_bed_cad_direct_backwater.csv`

## Current HDF availability

The workspace currently contains computed p02–p05 HDFs but is missing `GanjiangWestBridge.p01.hdf`. Therefore `scripts/extract_hecras_steady_results.py` cannot presently perform a single live-HDF extraction of all five plans. The frozen p01–p04 v2 CSV remains the reference for those four unchanged cases; restore/recompute p01 HDF before final solver archive.

## Rebuild caution

`make model-inputs` rewrites the text geometry/project inputs. Any existing HDF must then be treated as potentially stale until recomputed or explicitly geometry-audited. Do not infer freshness from the plan filename alone.