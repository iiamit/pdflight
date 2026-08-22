"""Verify dated legal interpretations against the Chief Counsel library.

Phase 1 deliverable 1.4. Not implemented yet.

Specified in CLAUDE.md section 4.4.
"""

import sys

# Exit code convention, CLAUDE.md section 9. 69 is EX_UNAVAILABLE from
# sysexits.h. Not 2, which argparse already uses for a usage error: a caller
# must be able to tell "this tool is not built yet" from "you passed a bad
# flag" without parsing stderr.
EXIT_NOT_IMPLEMENTED = 69

SPEC = """tools/verify_interps.py is Phase 1 deliverable 1.4 and is NOT IMPLEMENTED.

Specified in CLAUDE.md 4.4, for any entry that has a year:
  - request the URL and confirm 200
  - extract addressee and date from page one
  - confirm the subject matches the stated topic
  - report pass, fail, or mismatch

On a mismatch, report and stop. Never search for a different year that happens
to fit. Key on {surname}_{year}, never surname alone.

Ids are three-part: interp:{surname}-{year}-{topic-slug}. Always all three, no
conditional suffix, because a scheme that only disambiguates on collision breaks
the moment a second document surfaces. The slug is 2 to 4 words drawn from the
subject line of the actual document, not from the topic column in CLAUDE.md
section 7.

Failures are documented in docs/INTERPS-NOTES.md with what was checked and what
was ruled out. Anything that cannot be confirmed is dropped, not guessed at.

Run tools/discover_interps.py first for the twelve entries that carry no year.
"""


def main(argv):
    sys.stderr.write(SPEC)
    return EXIT_NOT_IMPLEMENTED


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
