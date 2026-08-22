"""Fetch the source corpus into cache/ and maintain manifest/sources.lock.yaml.

Phase 1 deliverable 1.3. Not implemented yet; this stub exists so the Makefile
targets resolve and so a partial build fails loudly instead of silently
appearing to succeed.

Specified in CLAUDE.md section 4.3.
"""

import sys

SPEC = """tools/fetch.py is Phase 1 deliverable 1.3 and is not implemented.

Specified in CLAUDE.md 4.3:
  - content-addressed cache at cache/sources/{sha256}.pdf, with cache/index.json
    mapping id to sha256
  - lock holds content-derived fields only; sha256 is the only load-bearing
    change signal, everything else is informational and nullable
  - fetched_at updates only when sha256 changes; volatile validators live in
    gitignored state/check.json
  - sequential, never parallel; exponential backoff on 429 and 5xx;
    browser-like User-Agent; conditional If-None-Match and If-Modified-Since
  - on 404, report every .pdf href found on landing_url as a candidate with link
    text and content length, then stop. Never substitute automatically and never
    rewrite the manifest unattended
  - pages, faa_number, and revision_date via PyMuPDF. No poppler; see rule 12
  - revision_date must not come from /ModDate, which changes on re-encoding

Modes:
  make fetch          satisfy the lock from cache, fully offline when it can be
  make fetch-check    revalidate, report drift, download nothing
  make fetch-update   pull changed sources and rewrite the lock
"""


def main(argv):
    sys.stderr.write(SPEC)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
