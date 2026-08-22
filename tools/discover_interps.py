"""Resolve yearless legal interpretations against the Chief Counsel index.

Phase 1 deliverable 1.4. Not implemented yet.

Specified in CLAUDE.md section 4.4.
"""

import sys

# Exit code convention, CLAUDE.md section 9. 69 is EX_UNAVAILABLE from
# sysexits.h. Not 2, which argparse already uses for a usage error: a caller
# must be able to tell "this tool is not built yet" from "you passed a bad
# flag" without parsing stderr.
EXIT_NOT_IMPLEMENTED = 69

SPEC = """tools/discover_interps.py is Phase 1 deliverable 1.4 and is NOT IMPLEMENTED.

Twelve of the thirty-four selected interpretations carry no year, so their URL
cannot be constructed. Rule 2 forbids inventing one. Discovery resolves them
from the index instead.

Specified in CLAUDE.md 4.4:
  - locate the index root, and confirm the per-year listing shape against 2009,
    where five V-rated entries exist to cross-check
  - fetch each per-year page exactly once into cache/interps-index.json, a
    first-class reusable artifact rather than a throwaway. Cache the raw pages
    alongside it. Roughly 20 to 30 requests total, not one per candidate
  - use the same client as fetch.py: sequential, exponential backoff,
    browser-like User-Agent
  - each record carries surname, year, addressee, subject line, PDF URL, and
    source index page
  - match on surname alone, and return every match. Never auto-select on topic
    similarity, which is rule 2 with extra steps
  - a surname absent from the index is unresolved for that entry only; the run
    continues
  - emit the candidate table to docs/INTERPS-CANDIDATES.md for human selection

Once the index exists the published URL pattern is unnecessary for every entry,
not just the twelve, because the index links are authoritative.

Yearless entries: B3 Bobertz, C2 Theriault, C3 Kortokrax, C4 Walker, D1 Collins,
D2 Kuhn, D3 Cazares, D4 Bell, E3 Gilberti, E4 Ludwig, F3 Bell, G2 Grannis.
"""


def main(argv):
    sys.stderr.write(SPEC)
    return EXIT_NOT_IMPLEMENTED


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
