# PDFlight

One hyperlinked PDF containing the FAA reference corpus a pilot needs for any
certificate or rating. Handbooks, ACS and PTS, the AIM, the full text of the
relevant parts of 14 CFR, Advisory Circulars, and selected Chief Counsel legal
interpretations. Every ACS element links to the regulations, handbook sections,
and guidance that support it.

Free, open source, offline, and self-updating.

**Status: the pipeline is complete and no release has been cut yet.**

Everything builds: the manifest and fetcher, the 14 CFR and 49 CFR typesetting
from eCFR, anchor resolution, the generated menus, assembly, linking, the
bookmark tree, the validation gates, the crosswalk, and the release
automation. A build currently produces roughly 6,200 pages at about 470 MB.

What is not done: the corpus covers Private and Instrument in depth, and the
remaining certificates are seeded but not verified. Reader compatibility has
not been tested on real devices, so `docs/COMPATIBILITY.md` is still empty.
See `docs/RELEASING.md` for how a release is cut and what still needs a
one-time repository setting.

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

Once the first release is cut, this URL always resolves to the current one:

```
https://github.com/iiamit/pdflight/releases/latest/download/pdflight.pdf
```

Each release also carries `SHA256SUMS`, the `sources.lock.yaml` it was built
from, and a `version.json`. Releases are event driven: they follow FAA source
changes rather than a calendar. See `docs/RELEASING.md`.

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

Private, Instrument, Commercial, ATP, CFI, CFII.

## Which reader to use

Tested on iPadOS against the current release:

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

## Reader compatibility

Some annotation apps re-render PDFs on import and strip link annotations. That
is their behavior, not a defect in this file. A per-release test matrix lives in
[docs/COMPATIBILITY.md](docs/COMPATIBILITY.md).

## Building

Requires Python 3.12 and GNU Make. Later phases also need Typst, qpdf, and
pdfcpu.

```
make setup     # install Python dependencies
make help      # list every target
make test      # run the test suite
```

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
  in real readers. Empty until a release exists to test.

Where they conflict, CLAUDE.md wins.
