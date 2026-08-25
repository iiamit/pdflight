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
        verify-interps check drift notes guide crosswalk crosswalk-stats review packets refine refine-apply build assemble link         outline validate menus         index         resolve resolve-check cfr cfr-check         optimize         optimize-check fonts         fonts-check test clean

help:
	@echo "PDFlight targets"
	@echo ""
	@echo "  setup             Install Python dependencies into the current environment"
	@echo "  fetch             Satisfy the lock from cache. Fully offline when the cache is complete"
	@echo "  fetch-check       Revalidate sources, report drift, download nothing"
	@echo "  fetch-update      Pull changed sources and rewrite manifest/sources.lock.yaml"
	@echo "  discover-interps  Resolve yearless interpretations against the cached index"
	@echo "  verify-interps    Verify dated interpretations against the Chief Counsel library"
	@echo "  crosswalk         Seed the crosswalk from ACS References lines"
	@echo "  crosswalk-stats   Crosswalk verification progress by certificate"
	@echo "  review            Print the next Tasks to verify (CERT=private AREA=I)"
	@echo "  packets           Build refinement packets (CERT=atp SPLIT=5)"
	@echo "  refine            Validate proposals, write nothing"
	@echo "  refine-apply      Apply validated proposals to the CSVs"
	@echo "  guide             Everything from cold: fetch through validate"
	@echo "  build             Re-run the assembly stages only. Assumes cfr,"
	@echo "                    index, resolve and optimize have already run"
	@echo "  assemble          Concatenate the corpus in canonical order"
	@echo "  link              Stamp navigation and rewrite anchors to absolute pages"
	@echo "  outline           Build the three-level bookmark tree"
	@echo "  validate          Run the validation gates"
	@echo "  menus             Render cover, main menu, per-document menus, colophon"
	@echo "  index             Extract outlines and page text into the anchor index"
	@echo "  resolve           Resolve anchor refs to pages, write anchors.lock.json"
	@echo "  resolve-check     Resolve and report moved or unresolved anchors"
	@echo "  cfr               Build 14 CFR and 49 CFR from eCFR into a typeset PDF"
	@echo "  cfr-check         Compare eCFR amendment dates against manifest/cfr.lock.yaml"
	@echo "  optimize          Recompress oversized sources into cache/optimized/"
	@echo "  optimize-check    Verify optimized artifacts against optimize.lock.yaml"
	@echo "  fonts-check       Verify vendored fonts against theme/fonts/fonts.lock.json"
	@echo "  fonts             Re-vendor fonts from the pinned upstream releases"
	@echo "  check             Probe sources and eCFR, classify drift, decide on a build"
	@echo "  drift             Print the drift issue body"
	@echo "  notes             Render release notes from the lock diff"
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

crosswalk:
	$(PYTHON) tools/bootstrap_crosswalk.py

crosswalk-stats:
	$(PYTHON) tools/crosswalk_review.py --stats

# The refinement loop. `packets` writes the questions, an agent or a
# reviewer writes the answers under crosswalk/proposals/, and `refine`
# validates them before anything reaches a CSV. SPLIT is how many packets
# to cut the certificate into. An Area of Operation is never split across
# two: an agent that sees all of one proposes better chapters than one
# that sees half.
SPLIT ?= 4

packets:
	$(PYTHON) tools/refine_packets.py $(CERT) --split $(SPLIT)

refine:
	$(PYTHON) tools/refine_crosswalk.py --dir crosswalk/proposals
	$(PYTHON) tools/refine_handbooks.py --dir crosswalk/proposals

refine-apply:
	$(PYTHON) tools/refine_crosswalk.py --dir crosswalk/proposals --apply
	$(PYTHON) tools/refine_handbooks.py --dir crosswalk/proposals --apply

CERT ?= private
AREA ?=
LIMIT ?= 6

review:
	$(PYTHON) tools/crosswalk_review.py --certificate $(CERT)         $(if $(AREA),--area $(AREA),) --limit $(LIMIT)

# Make runs prerequisites left to right only when it is not parallel, and
# every stage here consumes the previous one's output.
.NOTPARALLEL:

# The whole pipeline from an empty build directory, which is what CI runs.
# `build` alone assumes cfr, index, resolve and optimize have already run: on a
# cold runner it fails at assemble with no regulations PDF, and if it got past
# that it would breach the size budget by using unoptimized sources.
guide: fetch optimize cfr index resolve menus assemble link outline validate

build: menus assemble link outline validate

assemble:
	$(PYTHON) tools/assemble.py

link:
	$(PYTHON) tools/link.py

outline:
	$(PYTHON) tools/outline.py

validate:
	$(PYTHON) tools/validate.py

menus:
	$(PYTHON) tools/menus.py

index:
	$(PYTHON) tools/index.py

resolve:
	$(PYTHON) tools/resolve.py

resolve-check:
	$(PYTHON) tools/resolve.py --check

cfr:
	$(PYTHON) tools/cfr_build.py

cfr-check:
	$(PYTHON) tools/cfr_build.py --check

optimize:
	$(PYTHON) tools/optimize.py

optimize-check:
	$(PYTHON) tools/optimize.py --check

fonts-check:
	$(PYTHON) tools/vendor_fonts.py --check

fonts:
	$(PYTHON) tools/vendor_fonts.py

test:
	$(PYTHON) -m pytest

clean:
	$(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in ('build', '.pytest_cache')]; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"

check:
	$(PYTHON) tools/check_sources.py --check

drift:
	$(PYTHON) tools/check_sources.py --issue

notes:
	$(PYTHON) tools/release_notes.py --pdf build/pdflight-outlined.pdf
