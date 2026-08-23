# Interpretation discovery candidates

Written by `tools/discover_interps.py`. Do not hand-edit; edits are overwritten.
Selections belong in `manifest/sources.yaml`.

**18 candidate(s) need discovery. 9 resolved, 3 deferred pending review, 6 still open.**

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
| 2009 | memorandum | - | - | Federal Aviation Administration Memor~yg, MAY 1 s 2009 Date: To: From: Prepared by: Subject: Don Bobertz, Attorney, Office of the Regional Counsel, Western Pacific ~n, A WP.-OG:{ A ~ ~~~~' Assistant Chief Counsel for Regulations, | https://www.faa.gov/media/14451 |

### C2 Theriault, Flight review scope and content

| Year | Kind | Addressee | FAA date | Subject, or excerpt for a memo | URL |
|---|---|---|---|---|---|
| ? | letter | Mr. Theriault | - | Office of the Chief Counsel 800 Independence Ave., S.W. Washington, D.C. 20591 This responds to your request for an interpretation of several 14 C.F .R. Part 61 regulations regarding certain aspects of helicopter flight training. This respo | https://www.faa.gov/about/office_org/headquarters_offices/agc/practice_areas/regulations/interpretations/data/interps/2010/Theriault_2010_Legal_Interpretation.pdf |

### C3 Kortokrax, Instrument currency, approaches, holding, tracking

| Year | Kind | Addressee | FAA date | Subject, or excerpt for a memo | URL |
|---|---|---|---|---|---|
| 2006 | letter | Mr. Kortokrax | - | 800 Independence Ave., SW. Washington, DC 20591 This is in response to your request for a legal interpretation of 14 CFR §61.57 concerning pilot in command, recent flight experience. We agree that a properly rated instructor and a student a | https://www.faa.gov/about/office_org/headquarters_offices/agc/practice_areas/regulations/interpretations/Data/interps/2006/Kortokrax_2006_Legal_Interpretation.pdf |

### D1 Collins, Procedure turn required or not

| Year | Kind | Addressee | FAA date | Subject, or excerpt for a memo | URL |
|---|---|---|---|---|---|
| 2012 | letter | Mr. Collins | August 7, 2008 | Office of the Chief Counsel 800 Independence Ave., S.W. Washington, o.c. 20591 This is in response to your request for a legal interpretation dated March 26, 2012. In your request, you asked whether a certified flight instructor (CFI) may l | https://www.faa.gov/about/office_org/headquarters_offices/agc/practice_areas/regulations/interpretations/Data/interps/2012/Collins_2012_Legal_Interpretation.pdf |
| 2013 | letter | Mr. Collins | April 7, 2013 | Office of the Chief Counsel · 800 Independence Ave., S.W. Washington, D.C. 20591 This responds to your request for a legal interpretation emailed Jvfarch 5, 2013 and amended April 7, 2013. Your letter requests reconsideration of an issue th | https://www.faa.gov/about/office_org/headquarters_offices/agc/practice_areas/regulations/interpretations/Data/interps/2013/Collins-2_2013_Legal_Interpretation.pdf |

### F3 Bell, Definition of "operate," when a flight begins

| Year | Kind | Addressee | FAA date | Subject, or excerpt for a memo | URL |
|---|---|---|---|---|---|
| 1999 | letter | Mr. Bell | January 13, 1999 | Mr. George L. Thompson has asked me to respond to your letter of January 8, 1999, in which you requested his opinion regarding a proposed flight operation. In your letter, you asked whether a pipeline patrol operation, wherein the aircraft  | https://www.faa.gov/about/office_org/headquarters_offices/agc/practice_areas/regulations/interpretations/Data/interps/1999/Bell_1999_Legal_Interpretation.pdf |

### A6 Crowe, Logging PIC toward added category or class requires sole occupancy

| Year | Kind | Addressee | FAA date | Subject, or excerpt for a memo | URL |
|---|---|---|---|---|---|
| 2012 | letter | Mr. Crowe | - | This letter responds to your request for legal interpretation dated September 26, 2012. You have indicated that you currently hold a commercial pilot certificate with an airplane category single engine land rating. You have asked several qu | https://www.faa.gov/about/office_org/headquarters_offices/agc/practice_areas/regulations/interpretations/Data/interps/2013/Crowe-PalmBeachHelicopters_2013_Legal_Interpretation.pdf |

### A10 Bell, Logging flight time

| Year | Kind | Addressee | FAA date | Subject, or excerpt for a memo | URL |
|---|---|---|---|---|---|
| 2009 | letter | Ms. Bell | November 21, 2006 | 800 Independence Ave., S.W. Washington, D.C. 20591 In a letter dated November 21, 2006 to the FAA Office of the Chief Counsel, Mr. Luis M. Gutierrez of your association requested the rescission of a letter of interpretation regarding flight | https://www.faa.gov/about/office_org/headquarters_offices/agc/practice_areas/regulations/interpretations/Data/interps/2009/Bell-AOPA_2009_Legal_Interpretation.pdf |

### B4 MacPherson, Internet flight sharing is holding out (Flytenow)

| Year | Kind | Addressee | FAA date | Subject, or excerpt for a memo | URL |
|---|---|---|---|---|---|
| 2014 | letter | Ms. MacPherson | May 19, 2014 | Office of the Chief Counsel 800 lndapendence Ave., S.W. Washington, D,C. 20591 This letter responds to your request for legal interpretation sent to my office on May 19, 2014, on behalf of your client, AirPooler, Inc. As set forth in the re | https://www.faa.gov/about/office_org/headquarters_offices/agc/practice_areas/regulations/interpretations/Data/interps/2014/MacPherson-JonesDay_2014_Legal_Interpretation.pdf |

### B5 Winton, Companion to MacPherson

| Year | Kind | Addressee | FAA date | Subject, or excerpt for a memo | URL |
|---|---|---|---|---|---|
| 2014 | letter | Mr. Winton | February 12, 2014 | Office of the Chief Counsel 800 Independence Ave., S.W. Washington, D.C. 20591 This letter responds to your request for legal interpretation sent to my office on February 12, 2014. You have asked several questions regarding expense-sharing  | https://www.faa.gov/media/12566 |


## Deferred pending review

These have a confirmed document naming the right addressee, but a subject that is not the topic CLAUDE.md section 7 claims. Rule 2 forbids adopting an interpretation that merely looks similar, so none of them ships until the conflict is resolved by hand. Either the topic column is wrong, the letter is, or a second letter to the same person has not surfaced.

| Ref | Filed as | Year | Page one actually reads as | URL |
|---|---|---|---|---|
| C4 | Night takeoff and landing currency, full sto | 2011 | This responds to your request for a legal interpretation dated August 11, 2011. Your letter requests clarification concerning the logging of pilot-in-command (PIC) time under · 14 CFR 61.Sl(e). Your letter presents a scenario in which Pilot | https://www.faa.gov/about/office_org/headquarters_offices/agc/practice_areas/regulations/interpretations/Data/interps/2011/Walker_2011_Legal_Interpretation.pdf |
| D2 | Alternate airport planning under 91.169 | 2014 | Office of the Chief Counsel 800 Independence Ave., S.W. Washington, D.C. 20591 Tius letter responds to your request for a legal interpretation of 14 C.F.R. § 61.129 dated October 10, 2013. You asked several questions concerning crediting re | https://www.faa.gov/media/12386 |
| G2 | CFI logging PIC while instructing | 2016 | Clarification of Requirements for Logging Cross-country Time to meet aeronautical | https://www.faa.gov/media/11516 |
| G2 | CFI logging PIC while instructing | 2017 | Clarification of the Exceptions in 14 CFR § 11.9. l(e) | https://www.faa.gov/about/office_org/headquarters_offices/agc/practice_areas/regulations/interpretations/Data/interps/2017/Grannis_2017_Legal_Interpretation.pdf |

## Still unresolved

- **Cazares no year** (D3, IFR in Class G airspace): page one does not name Cazares, rejected
- **Bell no year** (D4, Lost communications under 91.185): no candidate URL seeded
- **Gilberti no year** (E3, Inoperative instruments under 91.213(d)): page one does not name Gilberti, rejected; page one does not name Gilberti, rejected
- **Ludwig no year** (E4, Whether service bulletins are mandatory under Part): no candidate URL seeded
- **Mangiamele no year** (G1, Whether a CFI needs a type rating to instruct in a): no candidate URL seeded
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
