# Downstream-boundary sensitivity model

This isolated HEC-RAS 7.0.1 project holds 15 steady plans: the five main geometries at downstream Known WS 21.549342, 22.049342, and 22.549342 m.

`sensitivity_plan_map.csv` is the authoritative plan-to-case mapping. Computed HDF/run files remain local; active extracted outputs are `results/hecras_boundary_sensitivity*.csv`.

Rebuild inputs with `scripts/build_hecras_boundary_sensitivity.py`, recompute p01–p15 in HEC-RAS, then validate with `scripts/extract_hecras_boundary_sensitivity.py`.
