"""The interpretation candidate set, parsed from CLAUDE.md section 7.

CLAUDE.md is normative for ids and corpus, so the tables there are the source
of truth rather than a duplicate data file that could drift out of step.

Also holds the Chief Counsel URL pattern and the page-one extraction used to
confirm an addressee, a date, and a subject against the document itself. The
whole point of rule 2 is that those three come off the paper, never off a
search result or a filename.
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
CLAUDE = ROOT / "CLAUDE.md"
INDEX_CACHE = ROOT / "cache" / "interps-index.json"

PATTERN = ("https://www.faa.gov/about/office_org/headquarters_offices/agc"
           "/practice_areas/regulations/interpretations/Data/interps"
           "/%(year)s/%(name)s_%(year)s_Legal_Interpretation.pdf")

ROW = re.compile(r"^\|\s*([A-G]\d{1,2})\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*([VC])\s*\|\s*$")
YEAR = re.compile(r"\b(19\d{2}|20\d{2})\b")

# Organisation names that appear beside an addressee and are not the surname.
NOT_A_SURNAME = {"aopa", "instructor", "letter"}


def _surname(cell):
    """Pull the addressee surname out of a table cell.

    Cells look like "Gebhart 2009", "Bell/AOPA 2009", "Van Zanen 2009",
    "Mangiamele, instructor letter", or bare "Bobertz".
    """
    text = YEAR.sub("", cell)
    text = text.split(",")[0]
    text = text.split("/")[0]
    words = [w for w in re.split(r"\s+", text.strip()) if w]
    words = [w for w in words if w.lower().strip(".") not in NOT_A_SURNAME]
    return " ".join(words).strip() or cell.strip()


def load(path=CLAUDE):
    """Return the 34 selected interpretations, in table order."""
    entries = []
    in_section = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## 7."):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section:
            continue
        match = ROW.match(line)
        if not match:
            continue
        ident, cell, topic, confidence = match.groups()
        year = YEAR.search(cell)
        entries.append({
            "ref": ident,
            "cell": cell,
            "surname": _surname(cell),
            "year": year.group(1) if year else None,
            "topic": topic.strip(),
            "confidence": confidence,
        })
    return entries


def dated(entries):
    return [e for e in entries if e["year"]]


def yearless(entries):
    return [e for e in entries if not e["year"]]


def url_for(surname, year):
    """Build the documented URL. Only ever called with a year from a source."""
    return PATTERN % {"year": year, "name": surname.replace(" ", "_")}


def slug(text, words=4):
    parts = re.findall(r"[a-z0-9]+", (text or "").lower())
    skip = {"the", "a", "an", "of", "to", "for", "and", "or", "in", "on",
            "under", "whether", "request", "legal", "interpretation"}
    keep = [p for p in parts if p not in skip][:words]
    return "-".join(keep) or "unslugged"


# ---------------------------------------------------------------------------
# page-one extraction
# ---------------------------------------------------------------------------

DATE_PATTERNS = (
    re.compile(r"\b((?:January|February|March|April|May|June|July|August"
               r"|September|October|November|December)\s+\d{1,2},\s*\d{4})\b"),
    re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b"),
    re.compile(r"\b((?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)"
               r"[A-Z]*\s+\d{1,2},?\s*\d{4})\b", re.I),
)

DEAR = re.compile(r"\bDear\s+((?:Mr\.|Ms\.|Mrs\.|Dr\.|Captain|Capt\.)?\s*"
                  r"[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){0,2})\s*[:,]")

SUBJECT = re.compile(r"(?:Re|RE|Subject|SUBJECT)\s*[:.]\s*(.{5,200})")


def read_first_page(data):
    """Return (text, page_count) or (None, None) if it will not parse."""
    try:
        import pymupdf
    except ImportError:  # pragma: no cover
        return None, None
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception:
        return None, None
    try:
        if not document.page_count:
            return "", 0
        return document.load_page(0).get_text("text") or "", document.page_count
    except Exception:
        return None, None
    finally:
        document.close()


# A Chief Counsel letter carries two dates, and confusing them is the easy
# mistake. The letterhead date is the FAA's, usually a scanned stamp that OCRs
# badly ("DEC 1 2009", "JMl 9 201'.3"). The other is the incoming request's,
# introduced by "responds to your request ... dated X". Reading the first date
# on the page picks the request date about half the time, which makes a correct
# document look like the wrong year.
REQUEST_DATE = re.compile(
    r"(?:respond(?:s|ing)?\s+to|in\s+response\s+to|this\s+letter\s+responds\s+to)"
    r"[^.]{0,120}?\b(?:dated|of)\s+((?:January|February|March|April|May|June|July"
    r"|August|September|October|November|December)\s+\d{1,2},\s*\d{4})",
    re.IGNORECASE | re.DOTALL)

# Also catches "your April 27, 2010, letter".
REQUEST_DATE_INLINE = re.compile(
    r"\byour\s+((?:January|February|March|April|May|June|July|August|September"
    r"|October|November|December)\s+\d{1,2},\s*\d{4})[,\s]+letter",
    re.IGNORECASE)

YEAR_TOKEN = re.compile(r"\b(19\d{2}|20\d{2})\b")


def extract(text):
    """Pull addressee, both dates, subject, and every year seen on page one."""
    if not text:
        return {"addressee": None, "date": None, "request_date": None,
                "subject": None, "years": []}
    head = text[:6000]

    request = REQUEST_DATE.search(head) or REQUEST_DATE_INLINE.search(head)
    request_date = " ".join(request.group(1).split()) if request else None

    letter_date = None
    for pattern in DATE_PATTERNS:
        for found in pattern.finditer(head):
            candidate = " ".join(found.group(1).split())
            if request_date and candidate == request_date:
                continue
            letter_date = candidate
            break
        if letter_date:
            break

    dear = DEAR.search(head)
    subject = SUBJECT.search(head)
    return {
        "addressee": " ".join(dear.group(1).split()) if dear else None,
        "date": letter_date,
        "request_date": request_date,
        "subject": " ".join(subject.group(1).split())[:200] if subject else None,
        "years": sorted(set(YEAR_TOKEN.findall(head))),
    }


def surname_matches(surname, extracted_addressee, text):
    """Does this document actually belong to the named addressee?

    Checked against the salutation first, then anywhere on page one, because
    some letters address a company officer by full name.
    """
    last = surname.split()[-1].lower()
    if extracted_addressee and last in extracted_addressee.lower():
        return True
    return bool(text) and last in text[:6000].lower()
