# Interpretation discovery candidates

Written by `tools/discover_interps.py`. Do not hand-edit; edits are overwritten.
Selections belong in `manifest/sources.yaml`.

**18 candidate(s) need discovery. 1 resolved, 17 still open.**

## Why this file exists

The URL pattern in CLAUDE.md 4.4 needs a year, and thirteen candidates carry
none. Five more carry a year but 404 at that pattern, because the library has
used more than one filename convention.

CLAUDE.md 4.4 assumed a year-browsable FAA index listing addressee and subject.
That index no longer exists in scriptable form:

| Source | Result |
|---|---|
| `Data/interps/{year}/` directory listing | 403 |
| `interpretations/index.cfm` search endpoint | 500, retired |
| `drs.faa.gov` REST API | 403, even with browser headers |

The interpretations moved to the Dynamic Regulatory System, a JavaScript
application. The PDF pattern itself still resolves, so verification of dated
entries is unaffected; only discovery is.

Candidate URLs therefore come from a DRS session or a search index, recorded in
`cache/interps-index.json`. This tool never invents one. It fetches each
candidate and reads the addressee, date, and subject off page one, so a year is
only ever adopted from the document itself. A candidate whose page one names
someone else is rejected. Matching is on surname alone; nothing is selected on
topic similarity, which would be rule 2 with extra steps.

## Candidates

### C3 Kortokrax, Instrument currency, approaches, holding, tracking

| Year | Addressee | FAA date | Request dated | Subject as printed | URL |
|---|---|---|---|---|---|
| 2006 | Mr. Kortokrax | - | - | - | https://www.faa.gov/about/office_org/headquarters_offices/agc/practice_areas/regulations/interpretations/Data/interps/2006/Kortokrax_2006_Legal_Interpretation.pdf |


## Still unresolved

- **Bobertz no year** (B3, No common purpose without independent reason to tr): no candidate URL seeded
- **Theriault no year** (C2, Flight review scope and content): no candidate URL seeded
- **Walker no year** (C4, Night takeoff and landing currency, full stop): no candidate URL seeded
- **Collins no year** (D1, Procedure turn required or not): no candidate URL seeded
- **Kuhn no year** (D2, Alternate airport planning under 91.169): no candidate URL seeded
- **Cazares no year** (D3, IFR in Class G airspace): no candidate URL seeded
- **Bell no year** (D4, Lost communications under 91.185): no candidate URL seeded
- **Gilberti no year** (E3, Inoperative instruments under 91.213(d)): no candidate URL seeded
- **Ludwig no year** (E4, Whether service bulletins are mandatory under Part): no candidate URL seeded
- **Bell no year** (F3, Definition of "operate," when a flight begins): no candidate URL seeded
- **Mangiamele no year** (G1, Whether a CFI needs a type rating to instruct in a): no candidate URL seeded
- **Grannis no year** (G2, CFI logging PIC while instructing): no candidate URL seeded
- **Crowe 2013** (A6, Logging PIC toward added category or class require): no candidate URL seeded
- **Bell 2009** (A10, Logging flight time): no candidate URL seeded
- **MacPherson 2014** (B4, Internet flight sharing is holding out (Flytenow)): no candidate URL seeded
- **Winton 2014** (B5, Companion to MacPherson): no candidate URL seeded
- **Levy 2005** (B6, Early expense-sharing and common purpose analysis): no candidate URL seeded

## How to resolve one

1. Find the letter in DRS: <https://drs.faa.gov/browse/LEGAL_INTERPRETATIONS/doctypeDetails>
2. Add its PDF URL to `cache/interps-index.json` under the table ref.
3. Run `make discover-interps`. The tool fetches it and prints the addressee,
   date, and subject it actually found.
4. If that is the right letter, add it to `manifest/sources.yaml` with a
   three-part id: `interp:{surname}-{year}-{topic-slug}`, the slug drawn
   from the subject line printed here rather than from the topic column.
