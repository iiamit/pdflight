# Interpretation discovery candidates

Written by `tools/discover_interps.py`. Do not hand-edit; edits are overwritten.
Selections belong in `manifest/sources.yaml`.

**18 candidate(s) need discovery. 2 resolved, 16 still open.**

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

### B3 Bobertz, No common purpose without independent reason to travel

| Year | Kind | Addressee | FAA date | Subject, or excerpt for a memo | URL |
|---|---|---|---|---|---|
| 2009 | memorandum | - | - | Federal Aviation Administration Memor~yg, MAY 1 s 2009 Date: To: From: Prepared by: Subject: Don Bobertz, Attorney, Office of the Regional Counsel, Western Pacific ~n, A W | https://www.faa.gov/media/14451 |

### C3 Kortokrax, Instrument currency, approaches, holding, tracking

| Year | Kind | Addressee | FAA date | Subject, or excerpt for a memo | URL |
|---|---|---|---|---|---|
| 2006 | letter | Mr. Kortokrax | - | - | https://www.faa.gov/about/office_org/headquarters_offices/agc/practice_areas/regulations/interpretations/Data/interps/2006/Kortokrax_2006_Legal_Interpretation.pdf |


## Still unresolved

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

**A DRS link will not work as a seed.** `drs.faa.gov/browse/...` URLs are
routes into a JavaScript application, not files. Every one of them returns the
same 22 KB page shell, and the DRS API refuses scripted clients outright. The
tool fetches such a seed, sees it is not a PDF, and rejects it.

A DRS record is still worth having, because its document identifier carries the
year. `FAA000000000LEGALINTPR` **`2009`** `010PDF.0001` is a 2009 document, and
a year from a source is exactly what rule 2 requires. It just is not a URL.

The seed has to be a real PDF on `www.faa.gov`, and there are two hosting
schemes in play:

| Scheme | Example |
|---|---|
| Year tree | `.../Data/interps/2006/Kortokrax_2006_Legal_Interpretation.pdf` |
| Media id | `https://www.faa.gov/media/14451` |

The second is not derivable from anything. B3 Bobertz lives there, which is why
its year-tree URL 404s even though the year was right.

So:

1. Take the year from the DRS identifier if you have it.
2. Find the actual PDF URL, by search or from the DRS viewer's own download link.
3. `python tools/discover_interps.py --seed <REF> <URL>`
4. The tool fetches it and prints what page one actually says. A candidate that
   names someone else is rejected; nothing is adopted on topic similarity.
5. If it is the right document, add it to `manifest/sources.yaml` with a
   three-part id: `interp:{surname}-{year}-{topic-slug}`, the slug drawn
   from the subject or excerpt printed above rather than from the topic column.

Memoranda print an excerpt instead of an addressee and subject. Their header
extracts as a block of labels followed by a block of values, so the fields do
not line up and any confident parse of them would be wrong. Read the excerpt.
