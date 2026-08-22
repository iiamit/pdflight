# Interpretation verification notes

Written by `tools/verify_interps.py`. Do not hand-edit; edits are overwritten.

Records a checked result for every dated candidate, passes included, and what
was ruled out for anything that failed. An entry that cannot be confirmed is
dropped rather than guessed at, and never replaced by a similar-looking
substitute.

The addressee, date, and subject below are read from page one of the fetched
document. They are not taken from the filename or from any search result.

**21 checked: 14 pass, 2 review, 0 mismatch, 5 fail.**

`pass` means the addressee and the filing year were both found on page one. `review` means the addressee is confirmed but the letterhead year is not legible, because those dates are scanned stamps and OCR mangles them. `mismatch` means page one names someone else, which is the only signal that a URL points at the wrong document. `fail` means the documented URL pattern did not resolve at all.

## Results

| Ref | Surname | Year | Verdict | Addressee on page 1 | FAA letter date | Request dated | Note |
|---|---|---|---|---|---|---|---|
| A1 | Gebhart | 2009 | pass | Mr. Gebhart | February 25, 2009 | - | addressee and year 2009 both on page one |
| A2 | Glenn | 2009 | pass | Mr. Glenn | DEC 1 2009 | November 11, 2007 | addressee and year 2009 both on page one |
| A3 | Hilliard | 2009 | pass | Mr. Hilliard | DEC 1 2009 | October 12, 2009 | addressee and year 2009 both on page one |
| A4 | Speranza | 2009 | pass | Mr. Speranza | May 21, 2009 | July 30, 2009 | addressee and year 2009 both on page one |
| A5 | Van Zanen | 2009 | pass | Mr. Van Zanen | November 13, 2007 | - | addressee and year 2009 both on page one |
| A6 | Crowe | 2013 | fail | - | - | - | 404 at the documented pattern |
| A7 | Murphy | 2015 | review | Mr. Murphy | October 26, 2014 | - | addressee confirmed, year 2015 not legible on page one; years seen: 2011, 2014 |
| A8 | Dick | 2016 | pass | Mr. Dick | April 13, 2012 | - | addressee and year 2016 both on page one |
| A9 | Herman | 2009 | pass | Mr. Herman | January 9, 2009 | - | addressee and year 2009 both on page one |
| A10 | Bell | 2009 | fail | - | - | - | 404 at the documented pattern |
| A11 | Metzinger | 2009 | pass | Mr. Metzinger | - | January 2, 2009 | addressee and year 2009 both on page one |
| B1 | Mangiamele | 2009 | pass | Mr. Mangiamele | February 13, 2007 | - | addressee and year 2009 both on page one |
| B2 | Haberkorn | 2011 | pass | - | June 9, 2011 | - | addressee and year 2011 both on page one |
| B4 | MacPherson | 2014 | fail | - | - | - | 404 at the documented pattern |
| B5 | Winton | 2014 | fail | - | - | - | 404 at the documented pattern |
| B6 | Levy | 2005 | fail | - | - | - | 404 at the documented pattern |
| C1 | Beard | 2015 | review | Mr. Beard | - | July 27, 2014 | addressee confirmed, year 2015 not legible on page one; years seen: 2014 |
| E1 | Murphy | 2011 | pass | Mr. Murphy | May 4, 1979 | April 27, 2010 | addressee and year 2011 both on page one |
| E2 | Letts | 2017 | pass | Mr. Letts | August 11, 2017 | - | addressee and year 2017 both on page one |
| F1 | Gossman | 2011 | pass | Mr. Gossman | - | January 5, 2011 | addressee and year 2011 both on page one |
| F2 | Krug | 2014 | pass | Mr. Krug | August 8, 2013 | - | addressee and year 2014 both on page one |

## Subjects as printed

- **Gebhart 2009** (A1): -
- **Glenn 2009** (A2): -
- **Hilliard 2009** (A3): -
- **Speranza 2009** (A4): -
- **Van Zanen 2009** (A5): -
- **Crowe 2013** (A6): -
- **Murphy 2015** (A7): Legal Interpretation on the Application of 14 CFR §§ 61.51
- **Dick 2016** (A8): Request for correct interpretation of 14 CFR 61.Sl(e)(l)(iv) - Logging time as PIC
- **Herman 2009** (A9): -
- **Bell 2009** (A10): -
- **Metzinger 2009** (A11): -
- **Mangiamele 2009** (B1): -
- **Haberkorn 2011** (B2): -
- **MacPherson 2014** (B4): -
- **Winton 2014** (B5): -
- **Levy 2005** (B6): -
- **Beard 2015** (C1): Section 6 l .31 ( d) solo endorsement requirements for additional category and/or class
- **Murphy 2011** (E1): -
- **Letts 2017** (E2): Request for Legal Interpretation Regarding the Operation of
- **Gossman 2011** (F1): -
- **Krug 2014** (F2): -

## Yearless candidates

13 candidate(s) carry no year and cannot use the documented URL
pattern. They are handled by `tools/discover_interps.py`; see
`docs/INTERPS-CANDIDATES.md`.
