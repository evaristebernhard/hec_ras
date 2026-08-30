# 1D steady-flow current status (2026-08-30)

- Q = 26,000 m³/s
- Manning n = 0.030
- CAD-labelled flood level used for calibration = 22.190 m
- Calibrated downstream (+500 m) WSE = 22.049 m
- Calibration reference = 现状河床线, blockage 360 m²

The current/protection four-case comparison is complete in three implementations:

- Python standard-step screening model;
- STREAM-1D independent check;
- HEC-RAS 7.0.1 steady plans `p01`-`p04`.

HEC-RAS result validation: `SI Units`, RS 500 `Obstr Block Mode=1`, and
`Finished Steady Flow Simulation` in all four plan HDF files.

At RS 600, HEC-RAS incremental WSE relative to current is +2.64 / +3.97 /
+6.41 mm for the 0.5 / 1.0 / 2.0 m protection cases. Bridge velocity changes
from 3.847 to 3.878 m/s; Froude remains subcritical at about 0.332-0.336.

Bridge blockage is represented as equivalent blocked obstruction only. This is
a screening model, not an explicit HEC-RAS bridge/pier model. The separate
design-riverbed case and HEC-RAS downstream-boundary sensitivity remain open.
