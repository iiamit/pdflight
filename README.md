# PDFlight

One hyperlinked PDF containing the FAA reference corpus a pilot needs for any
certificate or rating. Handbooks, ACS and PTS, the AIM, the full text of the
relevant parts of 14 CFR and 49 CFR, and Advisory Circulars. Every ACS element
links to the regulations, handbook chapters, and guidance that support it.

Free, open source, offline, and self-updating.

**Status: shipping. The current release is v2026.08.5.**

6,527 pages, 484 MB. Forty source documents, plus 629 pages of 14 CFR and
49 CFR typeset from eCFR covering 16 parts and 849 sections. The crosswalk
covers all five certificates: 28,001 rows across 5,493 ACS elements, and 96
percent of those elements point at a specific chapter or section rather than a
whole handbook or a whole part.

Two things are not done. The Chief Counsel legal interpretations are verified
but not yet in the file, described below. And reader compatibility is tested on
iPadOS only.

## What this is

- A single linearized PDF, PDF 1.7, built from public domain FAA and NTSB
  source material.
- A crosswalk link layer connecting ACS elements to their supporting sources.
  This is where the value is. The FAA content itself is a commodity.
- A rebuild pipeline that detects when the FAA changes something and cuts a new
  release. Event driven, never on a calendar.
- Offline. No network access is needed to read it, and no link leaves the file
  except a small number of deliberate outbound references.

## Download

This URL always resolves to the current release:

```
https://github.com/iiamit/pdflight/releases/latest/download/pdflight.pdf
```

Each release also carries `SHA256SUMS`, the `sources.lock.yaml` it was built
from, and a `version.json`. Releases follow FAA source changes rather than a
calendar, and an unchanged build does not release at all. See
`docs/RELEASING.md`.

## What is in it

Seven sections, in page order:

| | Section | Contents |
|---|---|---|
| 01 | Standards | Five ACS and the CFII PTS |
| 02 | Handbooks | Ten, PHAK through Plane Sense |
| 03 | Aeronautical Information Manual | current change |
| 04 | Regulations | 14 CFR parts 1, 43, 45, 47, 48, 61, 67, 68, 71, 73, 91, 103, 105, 119, 135 and 49 CFR 830, typeset from eCFR |
| 05 | Advisory Circulars | Seventeen, each confirmed active |
| 06 | Interpretations | empty, see below |
| 07 | Guides | outbound links only |

Every content page carries a nav stamp with `[menu]` and `[doc]` returns, and
the bookmark tree reaches three levels deep.

## What this is not

- **Not an FAA product.** Unofficial, not endorsed, not reviewed by any agency.
- **Not authoritative.** Verify against the official sources before you rely on
  anything here. Every document carries its revision and currency date, and the
  colophon lists the source and retrieval date for each one.
- **Not a study guide.** No original content of any kind. No summaries, no
  mnemonics, no annotations. Source material only.
- **Not a substitute for current charts, NOTAMs, or a POH.**

See NOTICE for the full disclaimer.

## Certificates covered

Private, Instrument, Commercial, ATP, CFI, CFII. All 276 ACS Tasks have been
worked, and every element carries at least one target.

| Certificate | Rows | Elements | Elements with a specific target |
|---|---|---|---|
| Private | 5,309 | 1,192 | 89% |
| Instrument | 2,400 | 338 | 99% |
| Commercial | 5,285 | 1,192 | 97% |
| ATP | 5,951 | 1,027 | 98% |
| CFI | 9,056 | 1,744 | 98% |

"Specific" means a CFR section or a handbook chapter rather than a whole part
or a whole book. The remainder is deliberate: the Risk Management Handbook has
no chapter-sized topics, the AFH carries no IFR content, and ACS tolerances are
not regulated anywhere. A wrong chapter is worse than a whole book, because it
looks answered. See [docs/CROSSWALK-REVIEW.md](docs/CROSSWALK-REVIEW.md).

## Legal interpretations are not in the file yet

Section 06 is empty. The verification work is done and the tooling exists:
`tools/verify_interps.py` checked 21 dated candidates and passed 14 against
page one of the actual document, and `tools/discover_interps.py` resolved 9 of
18 that needed a filename or a year found first. What has not happened is
promoting those into `manifest/sources.yaml`, so no interpretation ships today
and no crosswalk row points at one.

Six candidates remain open and three are deferred pending review, where page
one names the right addressee but the subject is not the topic the selection
claimed. Those do not ship until a human resolves the conflict. See
[docs/INTERPS-NOTES.md](docs/INTERPS-NOTES.md) and
[docs/INTERPS-CANDIDATES.md](docs/INTERPS-CANDIDATES.md).

## Which reader to use

Tested by hand on iPadOS against v2026.08.3:

| Reader | Links | Back |
|---|---|---|
| ForeFlight Documents | yes | yes |
| Apple Books | yes | no |
| Preview | yes | no |
| Garmin Pilot | **no** | no |

**Garmin Pilot strips every link**, so the crosswalk does nothing there. Save
the file locally and open it in ForeFlight, Apple Books, or Preview instead.

ForeFlight is the fullest experience because it has a back control, which is
what makes working through several regulations for one ACS element quick. The
others work too: every page carries `[menu]` and `[doc]` returns, so no jump
is a dead end.

Desktop readers and the annotation apps are untested. Some annotation apps
re-render PDFs on import and strip link annotations, which is their behavior
and not a defect in this file. The per-release matrix lives in
[docs/COMPATIBILITY.md](docs/COMPATIBILITY.md).

## Building

Requires Python 3.12, GNU Make, Typst 0.15, qpdf, and pdfcpu.

```
make setup     # install Python dependencies
make help      # list every target
make guide     # everything from cold: fetch through validate
make build     # re-run the assembly stages only
make test      # run the test suite, 294 tests
```

A full build from a cold cache downloads roughly 470 MB of source PDFs and
takes a while. `make build` assumes `cfr`, `index`, `resolve` and `optimize`
have already run.

Builds are deterministic: the same inputs produce a byte-identical SHA-256.
The release automation depends on that to decide whether anything changed.

Source PDFs are never committed. They are fetched into `cache/`, which is
gitignored, and the output goes to GitHub Releases.

## Licensing

Build code, templates, and crosswalk are MIT. See LICENSE.

FAA and NTSB publications are works of the United States Government and are not
subject to copyright protection in the United States.

Inter and JetBrains Mono are vendored under the SIL Open Font License 1.1.

## Documentation

- [CLAUDE.md](CLAUDE.md) is normative for schema, ids, corpus, rules, and
  acceptance criteria.
- [docs/BUILD-PLAN.md](docs/BUILD-PLAN.md) is normative for architecture,
  rationale, and later phases.
- [docs/RELEASING.md](docs/RELEASING.md) covers the release policy, the timing
  rules, and the one repository secret the automation needs.
- [docs/CROSSWALK-REVIEW.md](docs/CROSSWALK-REVIEW.md) covers how the crosswalk
  is verified and what "verified" claims.
- [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) records how the file behaves
  in real readers.

Where they conflict, CLAUDE.md wins.
