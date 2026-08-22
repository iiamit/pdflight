# PDFlight build orchestration. See CLAUDE.md section 4.
#
# Phase 1 covers the skeleton, the fetcher, the manifest, and interpretation
# verification. The remaining pipeline stages (cfr, index, resolve, menus,
# assemble, link, outline, optimize, validate, release) are specified in
# docs/BUILD-PLAN.md section 6 and land in later phases.
#
# make does not forward flags to a recipe, so each fetch mode is its own target.

PYTHON ?= python

.DEFAULT_GOAL := help
.PHONY: help setup fetch fetch-check fetch-update discover-interps \
        verify-interps fonts fonts-check test clean

help:
	@echo "PDFlight targets"
	@echo ""
	@echo "  setup             Install Python dependencies into the current environment"
	@echo "  fetch             Satisfy the lock from cache. Fully offline when the cache is complete"
	@echo "  fetch-check       Revalidate sources, report drift, download nothing"
	@echo "  fetch-update      Pull changed sources and rewrite manifest/sources.lock.yaml"
	@echo "  discover-interps  Resolve yearless interpretations against the cached index"
	@echo "  verify-interps    Verify dated interpretations against the Chief Counsel library"
	@echo "  fonts-check       Verify vendored fonts against theme/fonts/fonts.lock.json"
	@echo "  fonts             Re-vendor fonts from the pinned upstream releases"
	@echo "  test              Run the test suite"
	@echo "  clean             Remove build output and Python caches. Leaves cache/ intact"
	@echo ""
	@echo "Phase 1 status: skeleton only."
	@echo "fetch lands in deliverable 1.3, the interps tools in 1.4."

setup:
	$(PYTHON) -m pip install -e ".[dev]"

fetch:
	$(PYTHON) tools/fetch.py

fetch-check:
	$(PYTHON) tools/fetch.py --check

fetch-update:
	$(PYTHON) tools/fetch.py --update

discover-interps:
	$(PYTHON) tools/discover_interps.py

verify-interps:
	$(PYTHON) tools/verify_interps.py

fonts-check:
	$(PYTHON) tools/vendor_fonts.py --check

fonts:
	$(PYTHON) tools/vendor_fonts.py

test:
	$(PYTHON) -m pytest

clean:
	$(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in ('build', '.pytest_cache')]; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"
