PYTHON ?= .venv/bin/python

.PHONY: geometry design-bed model results cad

geometry:
	$(PYTHON) scripts/extract_cross_sections.py

design-bed:
	$(PYTHON) scripts/recover_design_bed.py

model:
	$(PYTHON) scripts/build_hecras_project.py

results:
	$(PYTHON) scripts/extract_hecras_results.py

cad:
	$(PYTHON) scripts/export_design_bed_cad.py
