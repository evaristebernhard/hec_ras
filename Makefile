PYTHON ?= .venv/bin/python
LATEXMK ?= latexmk
MPLCONFIGDIR ?= /tmp/hec_ras_matplotlib

.PHONY: cad-intermediate processed evidence model-inputs audit-design-bed-hdf extract-results report-data report cad-dxf cad-dwg cad-package verify all

cad-intermediate:
	$(PYTHON) scripts/convert_cad_sources.py

processed:
	$(PYTHON) scripts/extract_cross_sections.py
	$(PYTHON) scripts/recover_design_bed.py

evidence:
	$(PYTHON) scripts/audit_bridge_geometry_evidence.py
	$(PYTHON) scripts/inspect_dxf.py

# This target changes HEC-RAS inputs. Recompute affected plans externally before
# treating their existing HDF files as current evidence.
model-inputs: processed
	$(PYTHON) scripts/build_hecras_project.py
	$(PYTHON) scripts/build_hecras_boundary_sensitivity.py

# p05 can be independently verified even while p01.hdf is absent.
audit-design-bed-hdf:
	$(PYTHON) scripts/audit_hecras_design_bed_geometry.py

# Full live-HDF extraction requires p01-p05 HDF files to be present.
extract-results:
	$(PYTHON) scripts/extract_hecras_steady_results.py
	$(PYTHON) scripts/extract_hecras_boundary_sensitivity.py

# Report data deliberately uses frozen p01-p04 results plus geometry-audited p05.
report-data: audit-design-bed-hdf
	$(PYTHON) scripts/build_report_data.py
	MPLCONFIGDIR=$(MPLCONFIGDIR) $(PYTHON) scripts/render_design_bed_figure.py
	MPLCONFIGDIR=$(MPLCONFIGDIR) $(PYTHON) scripts/render_dxf_cad_views.py

report: report-data
	cd report && $(LATEXMK) -xelatex -interaction=nonstopmode -halt-on-error main.tex

cad-dxf: processed
	$(PYTHON) scripts/export_design_bed_cad.py

cad-dwg: cad-dxf
	$(PYTHON) scripts/build_design_bed_dwg_delivery.py

cad-package: cad-dwg
	$(PYTHON) scripts/package_design_bed_delivery.py

# Current verification does not pretend the missing p01.hdf is available. It
# verifies the frozen p01-p04 parity chain, the live CAD-direct p05 HDF, and the
# direct-only CAD package.
verify: audit-design-bed-hdf cad-package
	$(PYTHON) -m compileall -q scripts
	$(PYTHON) scripts/verify_repository.py

all: verify report
