# PDFlight - Claude Code Handoff

Drop this in the repo root as `CLAUDE.md`. Put the build plan at `docs/BUILD-PLAN.md`.

**Precedence.** CLAUDE.md is normative for schema, ids, corpus, rules, and acceptance criteria. `docs/BUILD-PLAN.md` is normative for architecture, rationale, and phases beyond the current one. Where they conflict, CLAUDE.md wins and BUILD-PLAN.md is the one to correct.

---

## Kickoff prompt

```
Read CLAUDE.md and docs/BUILD-PLAN.md, then execute Phase 1.

Do not start Phase 2 without checking in. Do not invent FAA URLs or
legal interpretation citations. Every source URL must be verified with
a live request before it enters manifest/sources.yaml.
```

---

## 1. What this is

PDFlight builds a single hyperlinked PDF containing the FAA reference corpus a pilot needs for any certificate or rating: handbooks, ACS and PTS, the AIM, full 14 CFR text, Advisory Circulars, and selected Chief Counsel legal interpretations. Every ACS element links to the regulations, handbook sections, and guidance that support it.

Free, open source, offline, self-updating. Distributed through GitHub Releases, linked from the aviation page at iamit.org.

The FAA content is public domain and commodity. The value is the crosswalk link layer and the rebuild pipeline.

**Prior art**: the VSL ACE Guide, a $97 commercial product with the same shape. We are not copying its taxonomy, menu structure, or naming. Build the arrangement from the ACS outline independently.

---

## 2. Locked decisions

| Decision | Value |
|---|---|
| Repo | `pdflight` |
| License | MIT for code, templates, crosswalk. FAA content is US Government work, public domain |
| Certificates | Private, Instrument, Commercial, ATP, CFI, CFII |
| 14 CFR | Full text, typeset in-file, offline |
| CFR parts | Title 14: 1, 43, 45, 47, 48, 61, 67, 68, 71, 73, 91, 103, 105, 119, 135. Title 49: 830 |
| Excluded parts | 97 (TERPS), 121 (~1,800 pages, out of scope) |
| Original content | None. FAA and NTSB source material only |
| Legal interpretations | 34 selected, see section 7 |
| Branding | iamit.org aviation theme, tokens in section 6 |
| Cadence | Event-driven, two-tier release policy. Never calendared |
| Output | One linearized PDF, PDF 1.7 |
| Distribution | GitHub Releases, `releases/latest/download/pdflight.pdf` |

---

## 3. Hard rules

Violating any of these breaks the product. They are not preferences.

**Sources**

1. Never invent or guess a URL. Verify with a live request before it enters the manifest.
2. **Never invent a citation. Looking one up is not inventing one.** The prohibition is on fabricating a year, addressee, or subject to make a URL resolve. Searching the Chief Counsel index for a known addressee and reading the year off the actual document is verification, and it is required. Twelve entries in section 7 carry no year and must go through discovery (section 4.4) before they can be verified. What is forbidden: trying years until one 200s, or substituting a different interpretation that looks similar. Drop what cannot be confirmed.
2a. The same rule governs `faa_number`. Every edition letter in section 5 was written from memory and none is verified. Do not treat them as authoritative. They are derived from the fetched document, never authored by hand. The field is informational and nullable, never a key. A document whose number will not extract is not an error. See 4.2 and 4.3.
3. FAA and NTSB material only. No Garmin, no manufacturer POH, no third-party study material. If it is not a US Government work, it does not ship.
4. Add no original content. No summaries, no mnemonics, no annotations. The "source material only" property is the whole point.

**PDF construction**

5. Link targets are logical refs, never page numbers. `14cfr:91.155`, `phak:ch15:airspace-class-b`, `acs:PA.I.B.K1`.
6. Simple `/GoTo` actions with named destinations only. No JavaScript, no `GoToR`, no embedded files, no form fields, no optional content groups.
7. PDF 1.7. Not 2.0. Mobile reader support for 2.0 is inconsistent.
8. Builds are deterministic. Same inputs produce a byte-identical SHA-256. Pin `SOURCE_DATE_EPOCH`, fix the PDF `/ID`, strip or pin `CreationDate` and `ModDate`, sort every directory listing. The release job depends on this to decide whether anything changed.
9. Never commit source PDFs or the output PDF. GitHub rejects files over 100 MB in-repo. Sources live in `cache/` (gitignored) and the Actions cache. Output goes to Releases.

**Style**

10. No em-dashes anywhere, including code comments and generated PDF text. Use " - " with spaces or restructure.
11. Active voice, concise. Strunk and White.

**Toolchain**

12. Any tool not available identically on Windows and `ubuntu-latest` is a determinism risk. Prefer Python wheels over external binaries. If an external binary is unavoidable, pin its version in both environments and record it in the lock file.

---

## 4. Phase 1 scope

Four deliverables. **Execution order is 1.1, then 1.3, then 1.2, then 1.4.** Document order is not execution order: the manifest cannot be verified before the tool that verifies it exists, and interpretation entries cannot enter the manifest before discovery and verification run. Build the fetcher against three hand-entered sources before pointing it at the full corpus.

Stop and check in when done.

### 1.1 Repo skeleton

```
pdflight/
├── Makefile
├── LICENSE                     # MIT
├── NOTICE                      # public domain statement, disclaimers
├── README.md
├── CLAUDE.md                   # this file
├── .gitignore                  # cache/, build/, state/, *.pdf, !theme/fonts/
├── pyproject.toml              # Python 3.12, uv or pip
├── manifest/
│   ├── sources.yaml
│   ├── sources.lock.yaml       # CI-written
│   ├── optimize.lock.yaml      # tool-written, proves optimize is reproducible
│   ├── cfr.lock.yaml           # tool-written, per-part eCFR amendment dates
│   └── cfr.yaml
├── crosswalk/                  # empty in Phase 1
├── anchors/
│   ├── patterns.yaml           # empty in Phase 1
│   └── anchors.lock.json
├── theme/
│   ├── theme.toml
│   └── fonts/
│       ├── Inter-Regular.ttf           # 400
│       ├── Inter-Medium.ttf            # 500
│       ├── Inter-SemiBold.ttf          # 600
│       ├── Inter-Bold.ttf              # 700
│       ├── Inter-Italic.ttf            # 400 italic
│       ├── JetBrainsMono-Regular.ttf   # 400
│       ├── JetBrainsMono-Medium.ttf    # 500
│       ├── OFL-Inter.txt
│       ├── OFL-JetBrainsMono.txt
│       └── fonts.lock.json             # SHA-256 per TTF
├── templates/
│   ├── cfr.typ                 # CFR typesetting, Phase 2
│   └── menu.typ                # cover, menus, colophon, Phase 4
├── tools/
│   ├── _http.py                # shared client: backoff, UA, conditional GET
│   ├── _manifest.py            # manifest schema and deterministic lock IO
│   ├── _cfr.py                 # eCFR XML to intermediate tree, then Typst
│   ├── cfr_build.py            # Phase 2: regulations to a typeset PDF
│   ├── index.py                # Phase 3: outlines and page text, scored
│   ├── resolve.py              # Phase 3: refs to pages, anchors.lock.json
│   ├── menus.py                # Phase 4: cover, menus, colophon
│   ├── fetch.py
│   ├── discover_interps.py
│   ├── verify_interps.py
│   ├── optimize.py             # image downsampling, keeps the size budget
│   └── vendor_fonts.py         # one-time font vendoring, --check in the suite
├── tests/
├── docs/
│   ├── BUILD-PLAN.md
│   ├── COMPATIBILITY.md
│   ├── INTERPS-CANDIDATES.md   # written by discover_interps.py
│   └── INTERPS-NOTES.md        # written by verify_interps.py
├── .github/workflows/
├── cache/                      # gitignored: sources/{sha256}.pdf, index.json, interps-index.json
└── state/                      # gitignored: check.json
```

**Acceptance**: `make help` lists targets. `pytest` green on the font-face and hash test and the repo-hygiene tests. Repo clones clean with no large files.

The font test asserts every declared face is present and its SHA-256 matches `theme/fonts/fonts.lock.json`. Repo hygiene asserts nothing tracked exceeds 100 MB and no PDF is tracked. The three fetcher tests belong to 1.3, not here.

### 1.2 `manifest/sources.yaml`

Schema:

```yaml
- id: phak
  title: Pilot's Handbook of Aeronautical Knowledge
  landing_url: https://www.faa.gov/regulations_policies/handbooks_manuals/aviation/phak
  url: https://www.faa.gov/.../pilot_handbook.pdf   # last known direct link
  section: handbooks        # standards|handbooks|aim|regs|ac|interps|guides
  order: 1                  # sort within section
  optional: false
  parts:                    # for multi-file sources, ordered; omit when single
    - url: https://www.faa.gov/.../aim_chapter_1.pdf
  addenda:
    - url: https://www.faa.gov/.../phak_addendum.pdf
      append: true
```

Four schema decisions, all deliberate:

- **`landing_url` is authoritative, `url` is a cache hint.** FAA PDF filenames carry edition letters and change without notice. The fetcher tries `url` first and on 404 reports PDF candidates scraped from `landing_url` for a human to pick. It never substitutes automatically. See 4.3.
- **`faa_number` is not in the schema.** It is a derived field, extracted from the fetched PDF's metadata or first page and written to the lock file. Never hand-authored, nullable, informational, and never a key. `id` is the identifier.
- **`menu_page` is gone.** Menu layout does not exist until Phase 4, so assigning page numbers for 77 entries now is guesswork. `section` plus `order` carries the same intent and survives a menu redesign.
- **`parts` handles multi-file sources.** The AIM is published as a chapter set and may or may not have a usable consolidated PDF. Check for one first. If it exists, use it as a single `url`. If not, enumerate chapters in `parts`, ordered. `addenda` stays separate and means supplements appended after the main body, which is a different thing.

Corpus in section 5. Every URL verified live. Anything that 404s gets flagged, not silently dropped.

**AC cancellation check.** Advisory Circulars get cancelled and superseded, and the FAA AC search page carries an explicit status field per AC. Check it for every AC in the corpus. Specifically verify whether AC 00-6 and AC 00-45 were cancelled by the Aviation Weather Handbook (FAA-H-8083-28), which is in the same corpus. Shipping a cancelled AC beside its replacement is a correctness failure, not a cosmetic one. Report status for all of them, and drop any that are cancelled unless the replacement is absent.

**Acceptance**: every `url` and every `parts` entry resolves to 200 and begins with the `%PDF-` magic bytes, every `faa_number` in the lock file was extracted rather than assumed, and every AC carries a verified status.

The gate is magic bytes, not content type. faa.gov serves real PDFs as `octet-stream` often enough that a strict type check produces false failures, and `landing_url` is HTML by definition so the gate never applies to it. Record the content type in the lock, do not enforce it.

### 1.3 `tools/fetch.py`

**Lock file holds content-derived fields only.** `resolved_url`, `sha256`, `bytes`, `pages`, `content_type`, `faa_number`, `faa_number_source`, `revision_date`. Nothing that changes when content does not.

**`sha256` is the only load-bearing change signal. Everything else in the lock is informational, nullable, and never fails a build.**

- `faa_number` is nullable and never a key. `id` is the identifier. `faa_number_source` is one of `metadata`, `firstpage`, or `null`. A document whose number will not extract is not an error.
- `revision_date` is nullable. **Do not use `/ModDate`.** It changes on re-encoding with no content change, which is the same false-drift defect described below for `fetched_at`. Prefer an extractable cover date or revision statement, null otherwise. Expect null for most documents in Phase 1: the reliable cases are ACs and ACS, where the revision letter already lives inside the document number.

`fetched_at` updates **only when `sha256` changes**. Volatile fields (`etag`, `last_modified`, last-checked timestamp) move to `state/check.json`, which is gitignored. A lock diff must mean the content changed, because BUILD-PLAN section 7 uses lock diffs as the release signal. A timestamp that ticks every run turns every check into false drift and every build into a release.

**Cache is content-addressed**: `cache/sources/{sha256}.pdf`, with `cache/index.json` mapping id to sha256. This makes the offline property trivially true and lets two sources that happen to be identical share one blob.

- Conditional requests using `If-None-Match` and `If-Modified-Since`. faa.gov may throttle datacenter egress, so this matters.
- Sequential, not parallel. Exponential backoff on 429 and 5xx. Browser-like User-Agent.
- On 404, fetch `landing_url`, extract every href ending in `.pdf`, and report them as candidates with link text and content length. Then stop. Never substitute automatically and never rewrite the manifest unattended. Auto-updating `url` from a scrape is auto-substitution, and it violates rule 1 at a different layer. A generic href scrape needs no per-template parser, and generalized URL-rot automation defers to Phase 7.
- `pages`, `faa_number`, and `revision_date` extracted via PyMuPDF, from document metadata and first-page text. See rule 12.

**Make targets**, since make does not forward flags to a recipe:

- `make fetch` - satisfy the lock from cache. **Fully offline when the cache satisfies the lock.** Zero network.
- `make fetch-check` - HEAD and conditional GET only. Revalidates, reports drift, downloads nothing.
- `make fetch-update` - pull changed sources and rewrite the lock.

**Acceptance**, as named tests:

- warm-cache `make fetch` makes zero network calls
- `make fetch-check` reports drift on a corrupted lock hash, and none when nothing changed
- two consecutive `fetch-check` runs on unchanged sources produce an empty lock diff

### 1.4 `tools/verify_interps.py`

Chief Counsel URLs follow a deterministic pattern:

```
https://www.faa.gov/about/office_org/headquarters_offices/agc/practice_areas/
  regulations/interpretations/Data/interps/{year}/{Name}_{year}_Legal_Interpretation.pdf
```

**This is two tools, not one.** Twelve entries in section 7 have no year, so their URL cannot be constructed. That is the one genuinely blocking gap in Phase 1, and it is resolved by discovery, not by guessing.

**`tools/discover_interps.py`** - for any entry lacking a year: search the Chief Counsel interpretations index for the addressee surname. The index is browsable by year and lists addressee and subject per entry. Return every match with year, subject line, and URL. Do not pick one. Emit a candidate table to `docs/INTERPS-CANDIDATES.md` for human selection.

Reading a year off the index is verification. Trying years until one returns 200 is invention. The line is whether the year came from a source or from the tool.

**The FAA index this assumed is gone.** Checked in 1.4: the `Data/interps/{year}/` directory listing returns 403, the `interpretations/index.cfm` search endpoint returns 500 and is retired, and the `drs.faa.gov` REST API returns 403 even with browser headers. The interpretations moved to the Dynamic Regulatory System, which is a JavaScript application with no scriptable index. The PDF URL pattern above still resolves, so verification of dated entries is unaffected; only discovery is.

Candidate URLs therefore come from outside the tool, a DRS session or a search index, recorded in `cache/interps-index.json`. `discover_interps.py` never invents one. What it does is the part rule 2 actually cares about: it fetches each candidate and reads the addressee, date, and subject off page one, so a year is only ever adopted from the document. A candidate whose page one names someone else is rejected.

**Five dated entries also need discovery.** A6 Crowe 2013, A10 Bell 2009, B4 MacPherson 2014, B5 Winton 2014, and B6 Levy 2005 return 404 at the documented pattern. The library has used more than one filename convention, exactly as anticipated. Their surname and year are known; only the filename is not.

**Build the index once, then resolve locally.** Do not issue a request per candidate.

1. Locate the index root. Confirm the per-year listing shape against 2009, where five V-rated entries exist to cross-check.
2. Fetch each per-year page exactly once into `cache/interps-index.json`, a first-class reusable artifact rather than a throwaway. Cache the raw pages under `cache/` alongside it. Roughly 20 to 30 requests total.
3. Use the same client as `fetch.py`: sequential, exponential backoff, browser-like User-Agent.
4. Each record carries surname, year, addressee, subject line, PDF URL, and source index page.
5. Match on surname alone. Return every match. Never auto-select on topic similarity, which is rule 2 with extra steps.
6. A surname absent from the index is unresolved for that entry only. The run continues.

Once the index exists, the URL pattern above is unnecessary for every entry, not just the twelve. The index links are authoritative, and the library has used more than one filename convention across years.

**`tools/verify_interps.py`** - for any entry with a year: request the URL, confirm 200, extract addressee and date from page one, confirm the subject matches the stated topic. Report pass, fail, or mismatch. On a mismatch, report and stop. Never search for a different year that fits.

Yearless entries needing discovery: B3 Bobertz, C2 Theriault, C3 Kortokrax, C4 Walker, D1 Collins, D2 Kuhn, D3 Cazares, D4 Bell, E3 Gilberti, E4 Ludwig, F3 Bell, G2 Grannis. Twelve.

**Note on B3 Bobertz**: marked V in an earlier draft despite having no year. A citation cannot be confirmed and yearless at once. Treat the V as unreliable and run it through discovery like the rest.

**Note on G1 Mangiamele, and the count.** This file contradicts itself. The twelve listed above exclude G1, and the id-scheme section below asserts twice that Mangiamele appears twice in 2009, using `interp:mangiamele-2009-instructor-type-rating` as its worked example. But the section 7 table cell for G1 reads "Mangiamele, instructor letter" with no year in it. The table is the candidate list, so the tooling follows the table and **the real count of yearless entries is thirteen, not twelve**. Do not settle this by rereading the prose. Discovery settles it from the document, and the table gets the year written in once it does.

### Interpretation id scheme

`interp:{surname}-{year}` is not unique. Mangiamele appears twice in 2009 (B1 expense sharing, G1 instructor letter). Bell appears three times, Levy twice. Ids are fixed in Phase 1 and referenced by the crosswalk from Phase 6 on, so this has to be right now.

**Scheme: `interp:{surname}-{year}-{topic-slug}`.** Always all three, no conditional suffix, because a scheme that only disambiguates on collision breaks the moment a second document surfaces.

```
interp:mangiamele-2009-expense-sharing
interp:mangiamele-2009-instructor-type-rating
interp:murphy-2011-anticollision-lights
interp:murphy-2015-autopilot-sole-manipulator
```

Slug is 2 to 4 words, lowercase, hyphenated, drawn from the subject line of the actual document rather than from the topic column in section 7. Longer refs are a fair price for ids that cannot silently collide.

**Acceptance**: discovery report generated and reviewed, verified entries promoted into `sources.yaml` with three-part ids, failures documented in `docs/INTERPS-NOTES.md` with what was checked and what was ruled out.

---

## 5. Corpus

**Every `FAA-H-` number below is unverified.** Edition letters were written from memory and are a starting point for lookup, not a claim. Resolve each from its FAA landing page and extract the real number from the fetched document. Rule 2a applies.

Worked example from the 1.3 seed set, which is why the rule is worth the trouble: the Weight and Balance Handbook is served at `FAA-H-8083-1.pdf`, with no edition letter in the filename, but the document's own metadata reports **FAA-H-8083-1B**. A filename is not a citation. PHAK resolved to 8083-25C from its first page and IFH to 8083-15B from metadata, both matching the guesses above, but that is luck rather than evidence.

**Handbooks**, with the numbers **as extracted in 1.2**, not as guessed: PHAK (8083-25C), AFH (8083-3C), IFH (8083-15B), IPH (8083-16B), Risk Management (**null**, see below), Aviation Weather (**8083-28B**), Weight and Balance (8083-1B), Aviation Instructor's (8083-9B), Seaplane (8083-23), Plane Sense (**8083-19A**).

Seven of ten matched the guess. Three did not, and each is a different failure mode. Aviation Weather is **8083-28B**, a revision letter the guess omitted. Plane Sense has a number at all, **FAA-H-8083-19A**, where the guess had only a name. Risk Management extracts to null: its FAA landing page titles it **FAA-H-8083-2A**, but the document itself does not state a number in a form the extractor trusts, so the lock records null rather than copying the page title. That is rule 2a behaving correctly. Do not hand-author it.

**Standards**: Private Airplane ACS, Instrument Airplane ACS, Commercial Airplane ACS, ATP and Type Rating ACS, Flight Instructor Airplane ACS, Flight Instructor Instrument PTS.

**AIM**: current change, from the FAA ATpubs page. Revises on a 56-day cycle.

**Advisory Circulars**, seventeen, each confirmed **Active** in the FAA AC index during 1.2, at the revision the index lists: 20-105C, 43-9D, 43.13-1B, 43.13-2B, 61-65K, 61-67C, 61-98E, 61-107B, 61-142, 90-48E, 90-66C, 91-67A, 91-73B, 91-74B, 91-78A, 91-92, 120-76E.

**AC 00-6 and AC 00-45 were dropped.** The suspicion in the original list was correct. AC 00-6B was cancelled 2022-12-22, with the FAA cancellation note reading "All ACs dealing with weather have been consolidated," and AC 00-45E was cancelled 2007-10-01 with no successor revision in the Active list. Their replacement, FAA-H-8083-28B, is in the corpus, so 4.2 says drop them. Nineteen became seventeen. Do not re-add either without a fresh status check.

**Regulations**: built from eCFR, not fetched as PDFs. See section 8.

**Excluded**: Garmin G1000 and GTN CFI guides. Garmin copyright, not FAA. Put an outbound web link on the menu instead.

---

## 6. Theme tokens

Lifted verbatim from `iiamit/iamit.org` → `assets/css/aviation.css`, which describes itself as an amber-on-slate theme. Write these into `theme/theme.toml` and keep token names matching the CSS custom properties so drift is visible by inspection.

```toml
[color]
bg          = "#0A0D14"   # --bg
bg_2        = "#0F141D"   # --bg-2
bg_3        = "#151B26"   # --bg-3
hair        = "#FFFFFF12" # --hair,   rgba(255,255,255,0.07)
hair_2      = "#FFFFFF24" # --hair-2, rgba(255,255,255,0.14)
ink         = "#EEF2F7"   # --ink
ink_2       = "#AAB3C0"   # --ink-2
ink_3       = "#6F7886"   # --ink-3
ink_4       = "#485061"   # --ink-4
signal      = "#FFB168"   # --signal, ACTIONS AND LIVE SIGNALS ONLY
signal_2    = "#FFC68F"   # --signal-2, hover lift
signal_dim  = "#FFB16829"
signal_glow = "#FFB1688C"

[type]
sans = "Inter"
mono = "JetBrains Mono"
base = 10.5
```

**Amber is for actions and live signals only.** The CSS says so explicitly. In print that means link targets, section rules, the live dot, and emphasis. Body is `ink`, secondary `ink_2`, labels `ink_3`. Do not tint pages amber.

Idioms to carry into the PDF, all lifted from the site:

- **Status strip** as the running header. Mono 11px, 0.08em tracking, uppercase, `ink_3`, 1px `hair_2` separators, glowing amber dot: `● PDFLIGHT | v2026.09.1 | AIM 2026-4 | 14 CFR CURRENT 2026-08-28 | 7412 PP`. Does the currency disclosure and the branding in one element.
- **Brand mark** `pdflight_` with an amber underscore, mono 14px, weight 500. Static, not blinking.
- **Section numbering** `01 · STANDARDS` style: mono 11px, 0.2em tracking, uppercase, `ink_3`, preceded by an 18px amber rule at 0.7 opacity.

**The menu sections listed in this file omit the AIM.** The six named are STANDARDS, HANDBOOKS, REGULATIONS, ADVISORY CIRCULARS, INTERPRETATIONS, GUIDES, but `aim` is a first-class value in the 4.2 schema and the canonical page order puts it between the handbooks and 14 CFR. Filing an 918-page core reference under GUIDES would be worse than renumbering, so Phase 4 gives it `03 · AERONAUTICAL INFORMATION MANUAL` and shifts REGULATIONS to 04, ADVISORY CIRCULARS to 05, INTERPRETATIONS to 06, GUIDES to 07. Seven sections, not six. Say so if you would rather it went elsewhere.
- **Headings** Inter 600, -0.025em tracking, trailing period: `Handbooks.` `Regulations.`
- **Chips** 100px radius, 1px `hair_2`, mono 11px, for per-document revision and page count. `revision_date` is nullable and usually empty, so the chip must render without it.
- **Ident block** two-column mono grid with uppercase `ink_3` labels, reused for the colophon source table.

**Fonts are build inputs, so rule 8 governs them.** A build-time fetch or a system install means the binary differs between machines, subsetting yields different bytes, and the PDF hash changes with no content change.

- Seven static faces: Inter 400, 500, 600, 700, Italic 400; JetBrains Mono 400, 500.
- Static instances, never variable. Inter's variable font subsets unpredictably through Typst into PDF.
- Italic 400 is mandatory, not decorative. eCFR XML uses `<I>` for citations and defined terms, so Phase 2 needs a real italic rather than a synthesized oblique.
- Configure Typst to fail on a missing face. Never synthesize a weight or a slant.
- Vendor `OFL.txt` per family. Both are SIL OFL.
- `theme/fonts/fonts.lock.json` records a SHA-256 per TTF. Never fetch a font at build time, in any phase.
- Subset at optimize.

**One deliberate deviation**: 14 CFR body text in Inter at 10.5pt, not mono. Twenty-five hundred pages of monospace is unreadable on a tablet. Mono stays on section numbers, headers, menu chrome, and ident blocks.

Theme applies to generated pages only. Source FAA PDFs stay untouched on white. Do not invert them.

---

## 7. Legal interpretations

Thirty-four selected. **V** means name, year, and topic confirmed. **C** means unverified, must pass `verify_interps.py` before entering the manifest.

**Thirteen entries carry no year** and must go through `discover_interps.py` first: B3, C2, C3, C4, D1, D2, D3, D4, E3, E4, F3, **G1**, G2. An earlier draft said twelve and omitted G1; see the note in 4.4. B3 Bobertz is marked V below but has no year, which is contradictory. Treat it as C.

The topic column is a working description, not the document's subject line. Ids and slugs come from the fetched document.

**A. Logging flight time**

| ID | Interpretation | Topic | |
|---|---|---|---|
| A1 | Gebhart 2009 | Logging PIC and cross-country as safety pilot | V |
| A2 | Glenn 2009 | Logging cross-country and SIC as safety pilot | V |
| A3 | Hilliard 2009 | Splitting cross-country when two pilots alternate as PIC | V |
| A4 | Speranza 2009 | Logging PIC as sole manipulator on IFR flight plan without instrument rating | V |
| A5 | Van Zanen 2009 | Whether a pilot may define "a flight" to optimize cross-country time | V |
| A6 | Crowe 2013 | Logging PIC toward added category or class requires sole occupancy | V |
| A7 | Murphy 2015 | Autopilot use still counts as sole manipulator | V |
| A8 | Dick 2016 | Logging PIC under 61.51(e)(1)(iv) | V |
| A9 | Herman 2009 | Logging flight time | C |
| A10 | Bell/AOPA 2009 | Logging flight time | C |
| A11 | Metzinger 2009 | Logging flight time | C |

**B. Compensation, expense sharing, holding out**

| ID | Interpretation | Topic | |
|---|---|---|---|
| B1 | Mangiamele 2009 | 61.113(c) pro rata sharing, no third-party reimbursement | V |
| B2 | Haberkorn 2011 | Common purpose, publicly posting flight information | V |
| B3 | Bobertz | No common purpose without independent reason to travel | C |
| B4 | MacPherson 2014 | Internet flight sharing is holding out (Flytenow) | V |
| B5 | Winton 2014 | Companion to MacPherson | V |
| B6 | Levy 2005 | Early expense-sharing and common purpose analysis | C |

**C. Currency, proficiency, endorsements**

| ID | Interpretation | Topic | |
|---|---|---|---|
| C1 | Beard 2015 | 61.31(d) category and class endorsement does not expire | V |
| C2 | Theriault | Flight review scope and content | C |
| C3 | Kortokrax | Instrument currency, approaches, holding, tracking | C |
| C4 | Walker | Night takeoff and landing currency, full stop | C |

**D. Instrument operations** (all unverified)

| ID | Interpretation | Topic | |
|---|---|---|---|
| D1 | Collins | Procedure turn required or not | C |
| D2 | Kuhn | Alternate airport planning under 91.169 | C |
| D3 | Cazares | IFR in Class G airspace | C |
| D4 | Bell | Lost communications under 91.185 | C |

**E. Equipment and airworthiness**

| ID | Interpretation | Topic | |
|---|---|---|---|
| E1 | Murphy 2011 | Beacon plus strobes is one anti-collision system under 91.209(b) | V |
| E2 | Letts 2017 | Affirms Murphy 2011 | V |
| E3 | Gilberti | Inoperative instruments under 91.213(d) | C |
| E4 | Ludwig | Whether service bulletins are mandatory under Part 91 | C |

**F. Airspace and operations**

| ID | Interpretation | Topic | |
|---|---|---|---|
| F1 | Gossman 2011 | Left-hand traffic patterns under 91.126 | V |
| F2 | Krug 2014 | Affirms Gossman | V |
| F3 | Bell | Definition of "operate," when a flight begins | C |

**G. Instructor privileges** (both unverified)

| ID | Interpretation | Topic | |
|---|---|---|---|
| G1 | Mangiamele, instructor letter | Whether a CFI needs a type rating to instruct in a type-rated aircraft | C |
| G2 | Grannis | CFI logging PIC while instructing | C |

**Deferred**, carried in the manifest with `optional: true` so enabling one is a flag flip: C5 Pratte, D5 Levy, E5 Coleal, F4 Weiss, F5 Duncan, G3 Fickbohm, G4 Hicks.

### Deferred pending review

A different thing from the backfill above. These refs have a **confirmed
document whose page one names the right addressee, but whose subject is not the
topic this table claims**. Rule 2 forbids adopting an interpretation that merely
looks similar, so none of them ships until a human resolves the conflict. Either
the topic column is wrong, or the letter is, or there is a second letter to the
same person that has not surfaced.

Tools read this list. A ref named here is reported separately by
`discover_interps.py` rather than counted as open, so it stays visible without
blocking the run.

| Ref | Filed as | Page one actually reads as |
|---|---|---|
| C4 | Night takeoff and landing currency, full stop | logging pilot-in-command time |
| D2 | Alternate airport planning under 91.169 | crediting flight time under 61.129(a)(4) |
| G2 | CFI logging PIC while instructing | logging cross-country time (2016); the exceptions in 11.91(e) (2017) |

`DEFERRED-REVIEW: C4, D2, G2`

---

## 8. Phase 2 preview, for context only

Do not start these without checking in.

**CFR pipeline**. eCFR API, no auth, base `https://www.ecfr.gov`:

- `GET /api/versioner/v1/titles.json` for `latest_amended_on`, used for change detection
- `GET /api/versioner/v1/versions/title-14.json` for section-level history
- `GET /api/versioner/v1/full/{date}/title-14.xml?part=61` for content

Request at **part level**. A whole-title request returns everything and times out.

**The DTD mapping below was wrong and is corrected here.** Both this file and BUILD-PLAN said "`DIV3` part, `DIV5` subpart, `DIV8` section". A part-level request actually returns:

| Element | Meaning |
|---|---|
| `DIV5 TYPE="PART"` | the part |
| `DIV6 TYPE="SUBPART"` | the subpart |
| `DIV8 TYPE="SECTION"` | the section |
| `DIV9 TYPE="APPENDIX"` | an appendix, which neither plan mentioned |

`DIV3` never appears. A parser written to the documented mapping finds nothing.

Two more things the plan did not anticipate. Sections keep tables inside an **untyped `<DIV>`**, and 91.155, the basic VFR weather minimums, is one of them; skipping unrecognised DIVs drops that table while the page count still looks plausible. And `sup`/`sub` are lowercase in the real XML.

Emit Typst with a label per section, then compile. **Only labelled `heading` elements export PDF named destinations.** A labelled block, a labelled helper returning a sequence, a labelled figure, and labelled content all silently produce nothing, verified against Typst 0.15. Since that export is the whole reason the regulations are generated rather than fetched, every structural level is a `heading` and styling lives in `show` rules.

**Measured, not estimated: 629 pages and 4.6 MB for 849 sections across 16 parts.** The 2,200 to 2,800 page and 8 to 15 MB estimate was high by roughly four times, because it assumed looser typesetting than Inter at 10.5pt gives. The build is byte-reproducible: two runs from a warm cache produce an identical `.typ` and an identical PDF.

**Anchor resolution**, priority order:

1. Native destinations for anything generated. Deterministic.
2. Source PDF outline match. Normalize the title (case fold, strip punctuation, collapse whitespace) and match.
3. Regex over extracted page text with an expected ordinal.
4. Pinned page number with `pinned: true`, which emits a warning every run.

**"FAA handbooks ship with bookmarks. This covers most anchors" is measured, and it holds for 30 of 40 documents but fails on the two that matter most.**

| Document | Reality |
|---|---|
| PHAK | 7,689 bookmarks, all worthless. Top level is source filenames like `03_phak_ch1.pdf`, then "Structure Bookmarks", "Document", "Article". Tagged-PDF structure leaking in from a per-chapter assembly. |
| IFH | No outline at all, 371 pages, and central to the Instrument crosswalk. |
| AFH | Outline titles are production filenames with a draft number, `02 - AFH Chapter 1 (Draft 4)`. They resolve today and break on re-issue, so match on the prefix. |
| Advisory Circulars | Excellent. 5 to 7 entries per page, one per numbered paragraph, exactly the granularity `ac:61-65K:para-14` wants. |
| Plane Sense, Seaplane | No outline. Both do have a text layer, so regex works. |

Two consequences. **Presence is not usability**, so `tools/index.py` scores every outline and marks the structural-noise case; density alone is the wrong test and rejects every AC. And **strategy 3 carries far more weight than the plan assumed**, so contents pages must be excluded: IFH lists every chapter title on page 12, and AFH's contents pages use no dot leaders, so both need detecting or the whole handbook anchors to its own table of contents.

**Crosswalk bootstrap**. Every ACS Area of Operation carries a References line listing supporting documents. Parse it to seed document-level targets at `confidence: auto`, then refine to section level by hand. Order: Private, Instrument, Commercial, CFI, CFII, ATP.

Full detail in `docs/BUILD-PLAN.md` sections 3, 4, 6, 7.

---

## 9. Toolchain

Python 3.12. PyMuPDF for assembly, links, page counts, all text extraction, and image downsampling (AGPL is fine, this repo is open source). Typst for generated pages, pinned at 0.15. qpdf for linearize and object repair. pdfcpu for validation.

**No Ghostscript.** The size budget was breached in 1.2, at 766 MB against a 500 MB hard fail, which is the condition that was supposed to bring Ghostscript in. PyMuPDF's own `rewrite_images` closed the gap instead, taking the corpus to 470 MB, so no second imaging binary has to be installed identically on Windows and `ubuntu-latest`. See rule 12 and `tools/optimize.py`.

**No poppler.** PyMuPDF `get_text()` covers Phase 3 extraction, so `pdftotext` is never needed, and `pdfinfo` was poppler's only remaining job. Two extractors disagree on whitespace and column reading order, FAA handbooks are heavily multi-column, and Phase 3 resolves anchors by regex over extracted text. Two extractors means anchors resolve differently on Windows than on `ubuntu-latest`. One extractor, everywhere. See rule 12.

Size budget: warn above 350 MB, hard fail above 500 MB.

**Exit codes.** Every tool in `tools/` uses the same convention, so CI and the
Makefile can tell outcomes apart without parsing stderr.

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | A check failed as designed. Drift detected, hash mismatch, verification mismatch. Expected and actionable, not a crash |
| 2 | Usage error. Reserved, because `argparse` already exits 2 on a bad flag |
| 69 | Not implemented yet. `EX_UNAVAILABLE` from `sysexits.h` |

A tool that is not built yet must exit 69, never 0. Silent success in a partial
pipeline is worse than a loud failure.

---

## 10. Definition of done, Phase 1

- `make fetch-update` pulls the full corpus and writes a complete `sources.lock.yaml`. `make fetch` on a warm cache makes zero network calls. Two consecutive `fetch-check` runs on unchanged sources produce an empty lock diff.
- Every manifest URL verified live. Every `faa_number` extracted, none assumed. Null is an acceptable value.
- Every AC status checked. Cancelled ACs dropped or justified.
- Discovery report exists for the twelve yearless interpretations. Verification report exists for the rest. Passing entries are in the manifest with three-part ids. Failures documented with what was checked and what was ruled out.
- `pytest` green.
- Nothing over 100 MB committed.
- README states what this is, what it is not, and that it is unofficial.

Then stop and report: corpus page count, total bytes, interpretation discovery and pass rates, any AC found cancelled, any `faa_number` that differed from section 5, and any URL that would not resolve.
