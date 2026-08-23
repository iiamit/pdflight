# FAA Reference Guide - Build and Maintenance Plan

Name: **PDFlight**. Free, open source, self-updating, hyperlinked FAA reference PDF.
Repo: `github.com/iiamit/pdflight`. Distribution: GitHub Releases, linked from the iamit.org aviation page.

**Precedence.** `CLAUDE.md` is normative for schema, ids, corpus, rules, and acceptance criteria. This file is normative for architecture, rationale, and phases beyond the current one. Where they conflict, CLAUDE.md wins and this file is the one to correct.

---

## 0. Locked scope

| Decision | Value |
|---|---|
| Distribution | Free, public repo, GitHub Releases |
| Certificates | Private, Instrument, Commercial, ATP, CFI, CFII |
| 14 CFR | Full text, typeset in-file, offline |
| Original content | None. FAA and NTSB source material only |
| Branding | iamit.org aviation theme |
| Cadence | Event-driven. Build and release when FAA sources change, not on a calendar |
| Output | Single linearized PDF |

Free distribution kills two constraints from the earlier plan:

1. **AGPL tooling is now fine.** The repo is public and the code is open source, so PyMuPDF and Ghostscript are usable. PyMuPDF is the best available library for link annotation surgery. Use it.
2. **No trademark or compilation-copyright exposure**, provided you build your own taxonomy and do not reuse VSL naming or menu structure. Still do that.

---

## 1. Repository layout

```
pdflight/
├── Makefile
├── LICENSE                     # MIT, code only
├── NOTICE                      # public-domain statement, disclaimers
├── README.md
├── manifest/
│   ├── sources.yaml            # what to fetch, hand-edited
│   ├── sources.lock.yaml       # resolved URLs, hashes, revision dates (CI-written)
│   └── cfr.yaml                # which CFR titles/parts to typeset
├── crosswalk/
│   ├── private.csv
│   ├── instrument.csv
│   ├── commercial.csv
│   ├── atp.csv
│   ├── cfi.csv
│   └── cfii.csv
├── anchors/
│   ├── patterns.yaml           # how to find each anchor in each source doc
│   └── anchors.lock.json       # last resolved anchor→page map (committed, diffable)
├── theme/
│   ├── theme.toml              # colors, type scale, spacing
│   └── fonts/                  # 7 static TTFs, OFL, fonts.lock.json. See CLAUDE.md 6
├── templates/
│   ├── cover.typ
│   ├── menu.typ                # main menu, 3 pages
│   ├── docmenu.typ             # per-document menu
│   ├── cfr.typ                 # CFR typesetting
│   └── colophon.typ            # sources, revision dates, disclaimer
├── tools/
│   ├── fetch.py
│   ├── cfr_build.py
│   ├── index.py
│   ├── resolve.py
│   ├── menus.py
│   ├── assemble.py
│   ├── link.py
│   ├── outline.py
│   ├── optimize.py
│   ├── validate.py
│   └── bootstrap_crosswalk.py
├── tests/
├── docs/
│   ├── COMPATIBILITY.md        # reader test matrix, per release
│   └── CHANGELOG.md
└── .github/workflows/
    ├── check-sources.yml
    ├── build.yml
    └── release.yml
```

**Never commit source PDFs or the output PDF.** GitHub rejects files over 100 MB in-repo. Sources live in the Actions cache and a local `cache/` directory, both gitignored. Output goes to Releases, where the per-file limit is 2 GB.

---

## 2. Source manifest

`manifest/sources.yaml`, one entry per document:

```yaml
- id: phak
  title: Pilot's Handbook of Aeronautical Knowledge
  landing_url: https://www.faa.gov/regulations_policies/handbooks_manuals/aviation/phak
  url: https://www.faa.gov/sites/faa.gov/files/pilot_handbook.pdf
  section: handbooks
  order: 1
  optional: false
  parts:                    # multi-file sources only, ordered
    - url: https://www.faa.gov/.../aim_chapter_1.pdf
  addenda:
    - url: https://www.faa.gov/.../phak_addendum_2025.pdf
      append: true
```

Fields: `id`, `title`, `landing_url`, `url`, `section`, `order`, `optional`, `parts`, `addenda`. No `faa_number` and no `menu_page`; both were removed. See CLAUDE.md 4.2.

`sources.lock.yaml` is CI-generated and holds `resolved_url`, `sha256`, `bytes`, `pages`, `content_type`, `faa_number`, `faa_number_source`, `revision_date`. `sha256` is the only load-bearing change signal; every other field is informational, nullable, and never fails a build. `fetched_at` updates only when `sha256` changes, and volatile validators live in gitignored `state/check.json`. Diffs in this file are the change signal that triggers a release. See CLAUDE.md 4.3.

### Corpus

**Handbooks** - PHAK (8083-25C), AFH (8083-3C), IFH (8083-15B), IPH (8083-16B), Risk Management (8083-2), Aviation Weather (8083-28), Weight and Balance (8083-1B), Aviation Instructor's (8083-9B), Seaplane (8083-23), Plane Sense. Basic Survival Skills was dropped: not a verified FAA publication title. A one-line add if it ever verifies.

**Standards** - Private Airplane ACS, Instrument Airplane ACS, Commercial Airplane ACS, ATP/Type Rating ACS, Flight Instructor Airplane ACS, Flight Instructor Instrument PTS.

**AIM** - current change, from the FAA ATpubs page. Revised on the 56-day cycle.

**Advisory Circulars** - 00-6, 00-45, 61-65, 61-67, 61-98, 61-107, 61-142, 90-48, 90-66, 91-67, 91-73, 91-74, 91-78, 91-92, 120-76, 20-105, 43-9, 43.13-1B/2B.

**Legal interpretations** - curated set, see section 15. The Office of Chief Counsel uses a predictable URL pattern, which makes the fetcher trivial:

```
https://www.faa.gov/about/office_org/headquarters_offices/agc/practice_areas/
  regulations/interpretations/Data/interps/{year}/{Name}_{year}_Legal_Interpretation.pdf
```

Each is 1 to 6 pages. Store as `interp:{surname}-{year}-{topic-slug}`, always all three parts, with a one-line topic summary rendered on the interpretations menu page. Two-part ids collide: Mangiamele appears twice in 2009. See CLAUDE.md 4.4.

**Regulations** - see next section.

**Excluded and why**: Garmin G1000 and GTN CFI guides are Garmin copyright, not FAA. Do not redistribute. Put an outbound web link on the menu instead. Same for any manufacturer POH material.

---

## 3. 14 CFR offline pipeline

The FAA does not publish a usable single PDF of 14 CFR. Build it from eCFR XML.

**API** (public, no auth, base `https://www.ecfr.gov`, documented at `/developers/documentation/api/v1`):

- `GET /api/versioner/v1/titles.json` - per-title `latest_amended_on`, `up_to_date_as_of`. Use for change detection.
- `GET /api/versioner/v1/versions/title-14.json` - section-level version history.
- `GET /api/versioner/v1/full/{date}/title-14.xml?part=61` - full XML for a part.

Request **at part level**, not title level. A whole-title request returns everything and will time out. One HTTP call per part, cached by `(part, date)`.

`manifest/cfr.yaml`:

```yaml
title_14:
  parts: [1, 43, 45, 47, 48, 61, 67, 68, 71, 73, 91, 103, 105, 119, 135]
  excluded: [97, 121]    # 97 is TERPS procedures; 121 is ~1,800 pages, out of scope
title_49:
  parts: [830]           # NTSB accident reporting
```

`tools/cfr_build.py`:

1. Fetch XML per part.
2. Parse the eCFR DTD structure into an intermediate JSON tree. **The mapping here was wrong**: it is `DIV5` PART, `DIV6` SUBPART, `DIV8` SECTION, `DIV9` APPENDIX, and `DIV3` never appears. Tables live inside untyped `<DIV>` wrappers. See CLAUDE.md section 8.
3. Emit Typst with a label per section: `<sec-91-155>`.
4. Compile to PDF. Typst labels become PDF named destinations, so `14cfr:91.155` resolves deterministically with zero text matching.
5. Generate a per-part index page and a Part 61/91 section-number quick jump table.

Typeset in Inter at 10.5pt, not mono. Two thousand-plus pages of monospace is unreadable on a tablet. Mono stays on headings, section numbers, and all menu chrome, which keeps the theme intact.

~~Expect roughly 2,200 to 2,800 pages and 8 to 15 MB.~~ **Measured: 629 pages and 4.6 MB**, 849 sections across 16 parts, at Inter 10.5pt. The estimate was high by about four times. Text-only PDFs do compress well, and this one is a rounding error against the 470 MB source corpus.

---

## 4. Anchors and crosswalk

This is the part that determines whether a monthly rebuild is automatic or a weekend of manual repair.

### Anchor refs

Logical, never page numbers:

```
phak:ch15:airspace-class-b
afh:ch09:stabilized-approach
14cfr:91.155
49cfr:830.5
aim:4-3-3
ac:61-65K:para-14
acs:PA.I.B.K1
interp:mangiamele-2009-expense-sharing
```

### Resolution, in priority order

1. **Native destinations** for anything you generate (CFR, menus, cover). Deterministic, zero maintenance.
2. **Source PDF outline match.** FAA handbooks and ACs ship with bookmarks. Normalize the bookmark title (case fold, strip punctuation, collapse whitespace) and match against the pattern. This covers most anchors.
3. **Text regex over extracted page text**, with an expected ordinal to disambiguate repeats. Used where bookmarks are missing or too coarse.
4. **Pinned page number** with `pinned: true`. Emits a build warning every run so it stays visible. Use sparingly.

`anchors/patterns.yaml`:

```yaml
phak:ch15:airspace-class-b:
  strategy: outline
  match: "Class B Airspace"
  fallback:
    strategy: regex
    pattern: '^Class B Airspace'
    ordinal: 1
```

`anchors.lock.json` is committed. When a rebuild moves an anchor from page 15-7 to 15-9, the PR diff shows it. When an anchor stops resolving, the build fails.

### Crosswalk

One CSV per certificate. ~~Roughly 3,000 to 5,000 rows total.~~ **Measured: 26,075 rows at `confidence: auto`** across five certificates, from 5,493 ACS elements. The estimate was five to eight times low, because it counted refined section-level links rather than the document-level cross product the bootstrap produces: every element inherits every document its Task's References line names, which averages four to five targets each.

The schema carries a sixth column beyond the five below. Section 11 requires the element's full text stored alongside its code, because the FAA renumbers ACS codes on revision and a crosswalk keyed only by code breaks by id rather than by page.

```csv
source_ref,target_ref,relation,confidence,note
PA.I.B.K1,14cfr:61.3,regulation,verified,
PA.I.B.K1,phak:ch01:certificates,explanation,verified,
PA.I.B.K1,ac:61-65K:para-2,guidance,auto,
```

`relation` drives link ordering and the icon on the ACS page: `regulation`, `explanation`, `guidance`, `standard`.

### Bootstrapping

Every ACS Area of Operation carries a **References** line listing supporting documents. `tools/bootstrap_crosswalk.py` parses those lines, expands each cited document into a document-level target, and writes rows with `confidence: auto`. You then refine to section level by hand. This converts most of the authoring effort into review.

Order of work: Private, then Instrument, then Commercial, then CFI, then CFII, then ATP. Private and Instrument alone cover the majority of real use.

---

## 5. Branding

Tokens lifted verbatim from `iiamit/iamit.org` → `assets/css/aviation.css`. The CSS calls itself "amber-on-slate adjacent theme," bridging the main site's terminal vocabulary with an instrument-panel amber accent. `theme/theme.toml` mirrors it token for token:

```toml
[color]
bg         = "#0A0D14"   # --bg
bg_2       = "#0F141D"   # --bg-2
bg_3       = "#151B26"   # --bg-3
hair       = "#FFFFFF12" # --hair,   rgba(255,255,255,0.07)
hair_2     = "#FFFFFF24" # --hair-2, rgba(255,255,255,0.14)
ink        = "#EEF2F7"   # --ink
ink_2      = "#AAB3C0"   # --ink-2
ink_3      = "#6F7886"   # --ink-3
ink_4      = "#485061"   # --ink-4
signal     = "#FFB168"   # --signal,   actions and live indicators ONLY
signal_2   = "#FFC68F"   # --signal-2, hover lift
signal_dim = "#FFB16829" # --signal-dim
signal_glow= "#FFB1688C" # --signal-glow

[type]
sans = "Inter"            # --font-sans
mono = "JetBrains Mono"   # --font-mono
```

The CSS comment is explicit that amber is for **actions and live signals only**. Honor that in print. Amber goes on link targets, the live dot, section rules, and `<em>` emphasis. Body text is `ink`, secondary is `ink_2`, labels are `ink_3`. Do not tint whole pages amber.

### Page idioms, lifted from the site

**Status strip.** The aviation page opens with a METAR-style data bar: `● KCDW | N9363V | CFI / CFII | 800+ hrs | 550+ in type`, mono 11px, 0.08em tracking, uppercase, `ink_3`, separated by 1px `hair_2` rules, with a glowing amber dot. Reuse it as the running header on every generated page, repurposed as document status:

```
● PDFLIGHT  |  v2026.09  |  AIM 2026-4  |  14 CFR CURRENT 2026-08-28  |  7412 PP
```

That single element does the currency-disclosure job and carries the brand at the same time.

**Brand mark.** `iamit_` with the underscore in amber and blinking. Static in print: `pdflight_` with an amber underscore, mono 14px, weight 500.

**Section numbering.** `01 · About` style: mono 11px, 0.2em tracking, uppercase, `ink_3`, preceded by an 18px amber rule at 0.7 opacity. Map directly onto menu sections: `01 · STANDARDS`, `02 · HANDBOOKS`, `03 · REGULATIONS`, `04 · ADVISORY CIRCULARS`, `05 · INTERPRETATIONS`, `06 · GUIDES`.

**Headings.** Inter 600, tight tracking (-0.025em), with the site's signature trailing period: `Handbooks.` `Regulations.` H1 on the cover at 66px / -0.035em, section heads at 40px.

**Buttons become tap targets.** `.btn` is 12px mono, 0.04em tracking, 4px radius, 1px `hair_2` border, transparent fill, with a `→` arrow. `.btn.primary` inverts: amber fill, `#0A0D14` text, weight 600. Use plain buttons for menu entries and primary style for the "return to main menu" control. Scale padding up to hit 44pt minimum touch height.

**Chip idiom.** The `.tail-chip` and `.session-chip` pill (100px radius, 1px `hair_2`, mono 11px) is the right shape for per-document metadata: revision number, page count, currency date.

**Ident block.** `.ident` uses a two-column mono grid with uppercase `ink_3` labels. Reuse it verbatim on the colophon for the source revision table.

### Fonts

The site loads Inter and JetBrains Mono from Google Fonts, weights 400/500/600/700 and 400/500. Both are SIL OFL, so both embed and redistribute freely. Vendor the TTFs into `theme/fonts/` rather than relying on a network fetch at build time, and subset at optimize.

**One deliberate deviation.** 14 CFR body text goes in Inter at 10.5pt, not mono. Twenty-five hundred pages of monospace is unreadable on a tablet. Mono stays on section numbers, running headers, menu chrome, and the ident blocks, which is what actually carries the theme.

### Constraints

- Theme applies to generated pages only. Source FAA PDFs stay untouched on white. Do not invert them, it looks broken and inflates file size.
- Persistent nav stamped on every page of every source document: two link rectangles bottom-left, `[menu]` and `[doc]`, mono 8pt amber on `rgba(10,13,20,0.55)` with a `hair_2` border, matching the `.tail-chip` treatment.
- Minimum 44pt tap targets throughout.
- Amber `#FFB168` on `#0A0D14` clears WCAG AA comfortably and stays readable in direct sun.

## 6. Build pipeline

`make guide` from a clean checkout. Every stage is idempotent and cacheable.

| Target | Does |
|---|---|
| `fetch` | Pull per manifest, verify or record SHA-256, write `sources.lock.yaml` |
| `cfr` | eCFR XML to typeset PDF with native destinations |
| `index` | Extract per-page text and outlines, build anchor index |
| `resolve` | Join crosswalk against anchor index, write `anchors.lock.json`, fail on unresolved |
| `menus` | Render cover, 3 main menu pages, per-document menus, colophon |
| `assemble` | Concatenate in canonical order, record page offsets |
| `link` | Inject named destinations, crosswalk links, persistent nav stamps |
| `outline` | Build the 3-level bookmark tree |
| `optimize` | Subset fonts, downsample images above 200 dpi, deflate, linearize |
| `validate` | All gates below |
| `release` | Write SHA-256, page count, changelog entry, version metadata |

**Toolchain**: Python 3.12, PyMuPDF (assembly, links, page counts, all text extraction), qpdf (linearize, object repair), pdfcpu (validation), Typst (generated pages), Ghostscript (image downsampling, only if the size budget is breached). No poppler: one text extractor everywhere, per CLAUDE.md rule 12.

**Canonical page order**: cover, main menu p1-3, ACS and PTS documents, handbooks, AIM, 14 CFR, Advisory Circulars, legal interpretations, guides and pamphlets, colophon.

**Determinism**: set `SOURCE_DATE_EPOCH`, fix the PDF `/ID`, strip or pin `CreationDate` and `ModDate`, sort every directory listing. Identical inputs must produce an identical SHA-256. That is how the release job knows whether anything actually changed.

**Size budget**: hard fail above 500 MB, warn above 350 MB. Realistic estimate is 250 to 400 MB, dominated by the image-heavy handbooks.

**Measured, Phase 1.2, whole corpus in the lock. The budget is blown.**

Forty targets: 6 standards, 10 handbooks, the AIM, 17 Advisory Circulars, all addenda. **766 MB and 5,455 pages**, before the 34 interpretations, before the typeset CFR, before a single generated page.

That is 1.5x the 500 MB hard fail and 2.2x the 350 MB warn line. The "250 to 400 MB realistic estimate" above is wrong by roughly a factor of two.

Two documents dominate:

| Document | Size | Pages | MB per page |
|---|---|---|---|
| Airplane Flying Handbook | 273.2 MB | 406 | 0.67 |
| Aviation Instructor's Handbook | 145.1 MB | 228 | 0.64 |
| Pilot's Handbook | 77.6 MB | 522 | 0.15 |
| Everything else, 37 targets | 270 MB | 4,299 | 0.06 |

AFH and AIH together are 418 MB, 55 percent of the corpus for 12 percent of the pages. At roughly 0.65 MB per page against a 0.06 MB per page corpus median, both are carrying images at far higher resolution than a tablet can display. They are the entire problem, and they are also the two most important documents for the Private and Commercial crosswalks, so dropping them is not attractive.

**Resolved in 1.2 by `tools/optimize.py`.** Downsampling images above 200 dpi to 150 dpi at quality 80, applied only to documents denser than 0.25 MB/page:

| Document | Before | After | Ratio |
|---|---|---|---|
| Airplane Flying Handbook | 260.6 MB | 90.5 MB | 35% |
| Aviation Instructor's Handbook | 138.4 MB | 43.1 MB | 31% |
| Seaplane Handbook | 37.7 MB | 6.9 MB | 18% |

**Corpus 766 MB to 470 MB, saving 296 MB.** The hard fail passes. The 350 MB warn line does not, and headroom is thin with the CFR, interpretations, and generated pages still to come.

The threshold is empirically placed, not guessed. Below it returns collapse: IFH recompresses to 95 percent of its size and takes 100 seconds to do it, because its bulk is text and vector art rather than oversized images. A 30 percent minimum-saving floor discards any result that does not earn its quality loss.

Ghostscript was not needed. PyMuPDF's `rewrite_images` did the work, so no second imaging binary has to exist identically on both platforms. Output is byte-reproducible: PyMuPDF writes a random second trailer `/ID` on every save, which is correct per the PDF spec and fatal for rule 8, so both halves are pinned to a value derived from the source hash. Two runs from a cold cache produced an identical `manifest/optimize.lock.yaml`.

If more headroom is needed later, dropping `dpi_target` to 120 roughly halves these three again.

---

## 7. GitHub Actions

Public repos get unlimited Actions minutes. `ubuntu-latest` gives 4 vCPU, 16 GB RAM, and roughly 14 GB free disk. Disk is the binding constraint, so free space first.

**The build is event-driven, not calendared.** Source changes drive releases. The FAA does not revise on a monthly rhythm and neither should this. The AIM runs a 56-day cycle. eCFR updates daily and Title 14 amendments land whenever they land. ACS revisions arrive once or twice a year. A monthly cron would ship stale AIMs half the time and cut empty releases the rest.

### Release policy

Two tiers decide whether a change cuts a release or waits.

**Tier 1, releases on its own:**

- AIM change number increments
- Any ACS or PTS revision
- New handbook edition or addendum
- 14 CFR amendment touching Parts 1, 43, 61, 67, 68, 71, 91, 135
- 49 CFR Part 830 amendment

**Tier 2, batches into the next Tier 1 release or the quarterly floor:**

- Advisory Circular revision
- New or removed legal interpretation
- Crosswalk additions and corrections
- Theme, template, or tooling changes
- 14 CFR amendment to a part outside the Tier 1 list

**Timing rules:**

- **Debounce, 72 hours.** After a Tier 1 change is detected, wait three days before building. Federal Register amendments cluster, and this avoids cutting three releases in a week for one rulemaking.
- **Floor, 7 days.** Never more than one release per week. Anything arriving inside the window rides along with the next one.
- **Ceiling, 90 days.** Force a full build every quarter even with zero drift. Catches silent URL rot, expired certificates, and toolchain breakage while there is still time to fix it calmly.

**Versioning**: `vYYYY.MM.N`, sequence within the month. `v2026.09.1`, `v2026.09.2`. Date-legible, and it does not pretend to a monthly cadence it does not have.

### `check-sources.yml`

```yaml
on:
  schedule: [{ cron: "0 11 * * *" }]   # daily, 11:00 UTC
  workflow_dispatch:
```

Daily, not weekly. The check is cheap, a few dozen HEAD requests and two JSON calls, and detection latency is the whole product promise.

Steps:

1. `HEAD` every manifest URL. Capture `ETag`, `Last-Modified`, `Content-Length`.
2. `GET /api/versioner/v1/titles.json`. Compare `latest_amended_on` for Titles 14 and 49.
3. `GET /api/versioner/v1/versions/title-14.json`. Identify which parts changed, so the tier can be assigned correctly.
4. Scrape the FAA ATpubs page for the current AIM change number.
5. Scrape the ACS page for revision dates.
6. Classify every detected change as Tier 1 or Tier 2 and write `state/pending.json`.
7. Maintain a single open issue, `Source drift`, updated in place rather than reopened. It shows the pending queue, tier, and scheduled build date.
8. If a Tier 1 change is older than 72 hours and the last release is older than 7 days, fire `repository_dispatch: build-and-release`.

### `build.yml`

```yaml
on:
  repository_dispatch: { types: [build-and-release] }
  schedule: [{ cron: "0 9 1 */3 *" }]   # quarterly floor
  pull_request:
  workflow_dispatch:
concurrency:
  group: build
  cancel-in-progress: true
```

Steps:

1. `jlumbroso/free-disk-space` to reclaim roughly 25 GB.
2. `actions/cache` on `cache/sources`, key `sources-${{ hashFiles('manifest/sources.lock.yaml') }}`, restore-keys `sources-`.
3. Install Typst, qpdf, pdfcpu, Python deps.
4. `make guide`.
5. Upload the PDF as a workflow artifact, 14-day retention.
6. On pull requests, comment with page count, file size, anchor resolution rate, unresolved anchors, and the SHA-256 delta against the last release.

Budget 25 to 45 minutes. The 6-hour job limit is not a concern.

**FAA rate limiting is a real risk.** faa.gov may throttle or block datacenter egress, and a daily check raises the exposure. Mitigate with conditional requests (`If-None-Match`, `If-Modified-Since`), exponential backoff, a browser-like User-Agent, sequential rather than parallel fetches, and the Actions cache so a cold pull is rare. If blocking persists, mirror to a Cloudflare R2 bucket refreshed from a residential connection.

### `release.yml`

```yaml
on:
  workflow_run:
    workflows: [build]
    types: [completed]
    branches: [main]
```

- Skip if the built SHA-256 matches the previous release. Determinism makes this reliable, and it is what stops the quarterly floor build from cutting an empty release.
- Tag `vYYYY.MM.N`.
- Attach `pdflight.pdf`, `SHA256SUMS`, `sources.lock.yaml`, `version.json`.
- Generate release notes from the `sources.lock.yaml` diff: which documents changed revision, which CFR parts were amended, the AIM change number, and the crosswalk row delta.
- Clear `state/pending.json` and close the drift issue.
- `repository_dispatch` to the iamit.org repo with the version payload.

Expected cadence in practice: 8 to 12 releases a year, clustered around AIM changes.

## 8. Distribution and site integration

**Stable download URL**, always current, no CDN needed:

```
https://github.com/iiamit/pdflight/releases/latest/download/pdflight.pdf
```

That path resolves server-side to the newest release asset. Link it directly from the aviation page. No client-side JavaScript, no manual updates.

**Version display on the site**: the release job fires `repository_dispatch` at the iamit.org repo. A small workflow there writes `_data/pdflight.yml`:

```yaml
version: "2026.09"
released: 2026-09-01
pages: 7412
size_mb: 318
aim_change: "2026-4"
cfr_current_as_of: 2026-08-28
sha256: "…"
```

The aviation page Jekyll template renders version, currency date, and size next to the download button, then rebuilds Pages. Fully hands-off.

**Also publish**: a `docs/` GitHub Pages page in the guide repo with the changelog, the reader compatibility matrix, and an issue link. Point the aviation page at it for anyone who wants detail.

---

## 9. Validation gates

Every one of these fails the build.

1. Zero unresolved anchors.
2. Zero dangling link annotations. Every destination exists in the assembled document.
3. Every ACS element in every crosswalk has at least one outbound link.
4. Every manifest document is reachable from a main menu page.
5. Every page carries a persistent nav stamp.
6. Outline depth of exactly 3, no orphan nodes.
7. `pdfcpu validate` clean.
8. File size within budget.
9. Byte-identical rebuild from identical inputs.
10. No text layer contains a URL to a source that is not in the manifest.

Warnings, non-fatal but reported in the PR comment: any pinned anchor, any crosswalk row still at `confidence: auto`, any source older than 24 months.

### What the first full build changed about these gates

**Gate 2 nearly passed for the wrong reason.** `insert_pdf` does not carry named destinations, so assembly destroyed all 1,009 of them: 42 from the generated pages, 967 from the CFR build. Nothing looked broken, because every link is a page-number `/GoTo` and 16,648 of them resolved cleanly. Only gate 4, which asks whether a document is reachable *by name*, caught it. `tools/link.py` now rebuilds the `/Dests` name tree by hand, sorted, since readers binary-search it.

**Gate 5 needs an exemption to mean anything.** "Every page carries a persistent nav stamp" cannot include the cover, the menus, and the colophon: a `[menu]` link on the menu is noise. The 39 navigation pages are exempt by design, the exemption is recorded in the offsets, and the gate checks that set rather than guessing.

**Gate 10 is about authored pages, not generated ones.** The distinction is authored versus reproduced. Source PDFs are unaltered under rule 4 and FAA text cites `asrs.arc.nasa.gov`. The CFR pages are typeset here but their words are the regulation, and 14 CFR incorporates standards by reference, printing `www.archives.gov`, `rtca.org` and `icao.int`. Stripping those would alter the law to satisfy a gate. The gate now covers only the 39 pages PDFlight writes.

**Gates 7 and 9 report UNAVAILABLE.** pdfcpu is not installed, and a byte-identical rebuild cannot be checked inside a single run at roughly 17 minutes per build. Both state the reason rather than passing quietly, because a gate that silently skips reads as green.

---

## 10. Reader compatibility

The single largest source of user-visible failure. Do not skip it.

Test matrix, manually verified per release, tracked in `docs/COMPATIBILITY.md`:

| Reader | Links | Outline | Load time | Notes |
|---|---|---|---|---|
| Apple Books (iPadOS) | | | | reference platform |
| Files / Quick Look | | | | |
| ForeFlight Documents | | | | |
| Garmin Pilot | | | | |
| GoodNotes | | | | known to break links |
| Notability | | | | known to break links |
| Adobe Acrobat iOS | | | | known poor performance |
| Acrobat / Preview desktop | | | | |

Design constraints that maximize survival:

- Simple `/GoTo` actions with named destinations only.
- No JavaScript, no embedded files, no form fields, no `/Named` actions beyond `NextPage` and `PrevPage`, no `GoToR`.
- No optional content groups, no transparency groups on generated pages.
- PDF 1.7, not 2.0. Mobile reader support for 2.0 is inconsistent.

Publish the matrix honestly. Annotation apps re-render PDFs on import and strip link annotations. That is their behavior, not your bug, and saying so up front prevents most support traffic.

---

## 11. Maintenance runbook

**Steady state, automatic**: the daily check detects drift, classifies it, waits out the debounce, builds, releases if the hash changed, and updates the site. Expected human time: zero. Most AIM cycles and CFR amendments need no intervention at all.

**When the drift issue shows an unresolvable change** (a moved URL, a renamed document, a broken anchor):

1. Read the diff table in the issue.
2. If a URL moved, update `manifest/sources.yaml`.
3. Push to a branch. The PR build reports anchor resolution.
4. If anchors broke, adjust `anchors/patterns.yaml`. Bookmark titles are the usual culprit.
5. Merge. Release fires automatically.

Expected: 15 to 40 minutes.

**When the FAA revises an ACS** (once or twice a year, painful):

Task codes get renumbered. The crosswalk keys break by ID, not by page. Mitigation, built in from day one: store the ACS element's full text in the crosswalk row alongside its code. `tools/remap_acs.py` fuzzy-matches old element text against the new ACS to propose a code remap, and you review the proposal rather than re-authoring.

Expected: 2 to 4 hours per affected certificate.

**When a handbook gets a new edition** (every 2 to 4 years per handbook): pagination changes wholesale. Outline-based anchors mostly survive. Regex anchors need review. Expect 1 to 3 hours.

---

## 12. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| FAA blocks CI egress | Medium | Backoff, UA header, cache, R2 mirror fallback |
| FAA URL restructure | High, recurring | Daily check workflow, drift issue |
| ACS renumbering | Certain, annual | Text-keyed crosswalk, remap tool |
| Reader strips links | Certain, some apps | Published compatibility matrix |
| File size hurts load time | Medium | Budget gate, image downsampling, older-iPad test |
| Runner disk exhaustion | Medium | Free-disk step, streaming fetch, prune intermediates |
| eCFR API change | Low | Pin API version, contract test in CI |
| Someone treats it as authoritative | Medium | Prominent currency date, colophon disclaimer, "verify against official FAA sources" |

---

## 13. Milestones

| Phase | Deliverable | Effort |
|---|---|---|
| 1 | Manifest, fetcher, lock file, cache. `make fetch` works | 8-12 h |
| 2 | CFR pipeline. Standalone 14 CFR PDF with working destinations | 15-25 h |
| 3 | Anchor index and resolver. `anchors.lock.json` for all sources | 15-20 h |
| 4 | Theme, menus, cover, colophon, nav stamps | 15-25 h |
| 5 | Assemble, link, outline, optimize, validate. First full build | 15-20 h |
| 6 | Crosswalk: Private + Instrument, bootstrapped then verified | 50-80 h |
| 7 | Actions workflows, release automation, site integration | 10-15 h |
| 8 | **v1.0 release** (Private + Instrument + full regs) | - |
| 9 | Crosswalk: Commercial, CFI, CFII, ATP | 90-140 h |
| 10 | Reader compatibility pass, compatibility doc | 10-15 h |
| 11 | **v2.0 release** (all certificates) | - |

Ship v1.0 before touching phase 9. Private and Instrument cover most demand, and shipping early surfaces the reader-compatibility problems while the crosswalk is still small enough to fix cheaply.

---

## 14. Licensing and notices

- `LICENSE`: MIT. Covers the build code, templates, and crosswalk only.
- `NOTICE`: FAA and NTSB publications are works of the United States Government, not subject to copyright in the US. This compilation is unofficial. It is not an FAA product, is not endorsed by the FAA, and is not a substitute for the official source documents. Verify currency before operational use.
- Cover page: version, build date, and a per-document currency table on the colophon.
- Do not use "ACE," "VSL," or any confusingly similar naming.
- No manufacturer avionics documentation.

---

## 15. Legal interpretation candidates

Fetcher URL pattern is predictable (section 2), so adding or removing one is a single manifest line. Recommended target is 28 to 34. Pick from the list below.

Confidence column: **V** = name, year, and topic confirmed against FAA or citing sources during research. **C** = candidate, exists but citation needs verification at fetch time before it goes in the manifest.

### A. Logging flight time

| # | Interpretation | Topic | Conf |
|---|---|---|---|
| A1 | Gebhart (2009) | Logging PIC and cross-country as a safety pilot | V |
| A2 | Glenn (2009) | Logging cross-country and SIC time as a safety pilot | V |
| A3 | Hilliard (2009) | Splitting cross-country time when two pilots alternate as PIC | V |
| A4 | Speranza (2009) | Logging PIC as sole manipulator on an IFR flight plan without an instrument rating | V |
| A5 | Van Zanen (2009) | Whether a pilot may define "a flight" to optimize cross-country time | V |
| A6 | Crowe (2013) | Logging PIC toward an added category or class requires sole occupancy | V |
| A7 | Murphy (2015) | Autopilot use still counts as sole manipulator of the controls | V |
| A8 | Dick (2016) | Logging PIC under 61.51(e)(1)(iv) | V |
| A9 | Herman (2009) | Logging flight time, general | C |
| A10 | Bell / AOPA (2009) | Logging flight time, general | C |
| A11 | Metzinger (2009) | Logging flight time, general | C |

### B. Compensation, expense sharing, holding out

| # | Interpretation | Topic | Conf |
|---|---|---|---|
| B1 | Mangiamele (2009) | 61.113(c) pro rata sharing; no reimbursement from a third party such as an employer | V |
| B2 | Haberkorn (2011) | Common purpose; publicly posting flight information | V |
| B3 | Bobertz | No common purpose when the pilot has no independent reason to be at the destination | V |
| B4 | MacPherson (2014) | Internet flight sharing constitutes holding out; the Flytenow interpretation | V |
| B5 | Winton (2014) | Companion to MacPherson, same subject | V |
| B6 | Levy (2005) | Early expense-sharing and common purpose analysis | C |

Note AC 61-142 already covers 61.113(c) in the corpus. B1 through B5 add the enforcement posture the AC does not state plainly.

### C. Currency, proficiency, endorsements

| # | Interpretation | Topic | Conf |
|---|---|---|---|
| C1 | Beard (2015) | The 61.31(d) category and class endorsement does not expire | V |
| C2 | Theriault | Flight review scope and content | C |
| C3 | Kortokrax | Instrument currency, six approaches, holding, tracking | C |
| C4 | Walker | Night takeoff and landing currency, full stop | C |
| C5 | Pratte | IPC administration and who may give it | C |

### D. Instrument operations

| # | Interpretation | Topic | Conf |
|---|---|---|---|
| D1 | Collins | Procedure turn required or not; the shortening question | C |
| D2 | Kuhn | Alternate airport planning under 91.169 | C |
| D3 | Cazares | IFR in Class G, uncontrolled airspace | C |
| D4 | Bell | Lost communications procedures under 91.185 | C |
| D5 | Levy | Descent below MDA or DA under 91.175 | C |

### E. Equipment and airworthiness

| # | Interpretation | Topic | Conf |
|---|---|---|---|
| E1 | Murphy (2011) | Beacon plus strobes is one anti-collision light system under 91.209(b) | V |
| E2 | Letts (2017) | Affirms Murphy (2011), same subject | V |
| E3 | Gilberti | Inoperative instruments under 91.213(d) | C |
| E4 | Ludwig | Whether manufacturer service bulletins are mandatory under Part 91 | C |
| E5 | Coleal | 91.205 required equipment | C |

### F. Airspace and operations

| # | Interpretation | Topic | Conf |
|---|---|---|---|
| F1 | Gossman (2011) | Left-hand traffic patterns under 91.126 | V |
| F2 | Krug (2014) | Affirms Gossman on traffic pattern direction | V |
| F3 | Bell | Definition of "operate" and when a flight begins | C |
| F4 | Weiss | 91.119 minimum safe altitudes | C |
| F5 | Duncan | Careless and reckless under 91.13 as a standalone charge | C |

### G. Instructor privileges

| # | Interpretation | Topic | Conf |
|---|---|---|---|
| G1 | Mangiamele (2009), instructor letter | Whether a CFI must hold a type rating to instruct in a type-rated aircraft | C |
| G2 | Grannis | CFI logging PIC while giving instruction | C |
| G3 | Fickbohm | Instructor endorsement responsibility and record retention | C |
| G4 | Hicks | Ground instructor privileges and logging | C |

### Recommendation

**Superseded. See `CLAUDE.md` section 7 for the locked set.** The selection is A1-A11, B1-B6, C1-C4, D1-D4, E1-E4, F1-F3, G1-G2, which is **34**, not 33. An earlier draft of this paragraph said 33. It was an arithmetic error.

Every C-rated entry gets verified against the Chief Counsel index before it enters `manifest/sources.yaml`. Any that fails verification is dropped rather than guessed at.

---

## Open items

1. **Sixteen interpretation citations** need verification (section 15). Twelve of them carry no year and go through `discover_interps.py` first. Mechanical, and it belongs in phase 1 rather than at first build.

Everything else is decided. Phase 1.1 is complete. Next concrete step is deliverable 1.3, the fetcher, then 1.2, the manifest.
