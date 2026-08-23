"""Deliverable 1.4.

CLAUDE.md section 7 is the source of truth for the candidate set, so the parser
is tested against it directly rather than against a copied fixture that could
drift.
"""

import io
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import _interps as I  # noqa: E402
import discover_interps as D  # noqa: E402
import verify_interps as V  # noqa: E402


@pytest.fixture(scope="module")
def entries():
    return I.load()


# ---------------------------------------------------------------------------
# the candidate set
# ---------------------------------------------------------------------------

def test_thirty_four_candidates_are_selected(entries):
    assert len(entries) == 34


def test_every_ref_is_unique(entries):
    refs = [e["ref"] for e in entries]
    assert len(refs) == len(set(refs))


def test_surnames_survive_awkward_table_cells(entries):
    by_ref = {e["ref"]: e for e in entries}
    # "Bell/AOPA 2009": AOPA is the organisation, not the addressee.
    assert by_ref["A10"]["surname"] == "Bell"
    assert by_ref["A10"]["year"] == "2009"
    # "Van Zanen 2009": a two-word surname.
    assert by_ref["A5"]["surname"] == "Van Zanen"
    # "Mangiamele, instructor letter": a qualifier, not part of the name.
    assert by_ref["G1"]["surname"] == "Mangiamele"


def test_g1_has_no_year_in_the_table(entries):
    """CLAUDE.md contradicts itself about G1 and the count depends on it.

    Section 4.4 lists twelve yearless refs and excludes G1. The id-scheme
    section asserts twice that Mangiamele appears twice in 2009, and uses
    interp:mangiamele-2009-instructor-type-rating as its worked example. But the
    section 7 table cell for G1 carries no year at all.

    The table is the candidate list, so the parser follows it and the real
    count is thirteen. Resolving this needs the document, not a reading of the
    prose, which is what discovery is for.
    """
    by_ref = {e["ref"]: e for e in entries}
    assert by_ref["G1"]["year"] is None
    assert len(I.yearless(entries)) == 13
    assert len(I.dated(entries)) == 21


def test_url_pattern_encodes_multiword_surnames():
    url = I.url_for("Van Zanen", "2009")
    assert "Van_Zanen_2009_Legal_Interpretation.pdf" in url
    assert "/interps/2009/" in url


def test_slug_drops_filler_words():
    assert I.slug("Request for legal interpretation of the pro rata share") == \
        "pro-rata-share"


# ---------------------------------------------------------------------------
# the extraction bug that made correct documents look wrong
# ---------------------------------------------------------------------------

GLENN = (
    "U.S. Department of Transportation Federal Aviation Administration "
    "DEC 1 2009 Ted Louis Glenn Dear Mr. Glenn: Office of the Chief Counsel "
    "This responds to your request for a legal interpretation dated "
    "November 11, 2007. Your letter requests clarification concerning logging."
)

MURPHY = (
    "U.S. Department of Transportation Federal Aviation Administration JAN "
    "Dear Mr. Murphy, Office of the Chief Counsel 1 2011 800 Independence Ave. "
    "This is in response to your April 27, 2010, letter, regarding two issues."
)


def test_the_requesters_date_is_not_the_letter_date():
    """A Chief Counsel letter carries two dates and they are easy to confuse.

    Reading the first date on the page picks the incoming request's date about
    half the time, which made six correct documents look like the wrong year.
    """
    found = I.extract(GLENN)
    assert found["request_date"] == "November 11, 2007"
    assert found["date"] != "November 11, 2007"
    assert "2009" in found["years"]


def test_inline_your_date_letter_form_is_also_a_request_date():
    found = I.extract(MURPHY)
    assert found["request_date"] == "April 27, 2010"
    assert "2011" in found["years"]


def test_addressee_is_read_from_the_salutation():
    assert I.extract(GLENN)["addressee"] == "Mr. Glenn"


def test_surname_match_accepts_salutation_or_body():
    assert I.surname_matches("Glenn", "Mr. Glenn", GLENN)
    assert I.surname_matches("Glenn", None, GLENN)
    assert not I.surname_matches("Kortokrax", "Mr. Glenn", GLENN)


def test_extract_survives_empty_text():
    found = I.extract("")
    assert found["addressee"] is None and found["years"] == []


# ---------------------------------------------------------------------------
# verification verdicts
# ---------------------------------------------------------------------------

def make_letter(lines):
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    y = 72
    for line in lines:
        page.insert_text((60, y), line, fontsize=11)
        y += 16
    data = document.tobytes()
    document.close()
    return data


def run_verify(transport, client_factory, tmp_path, claude_text):
    claude = tmp_path / "CLAUDE.md"
    claude.write_text(claude_text, encoding="utf-8")
    out = io.StringIO()
    code = V.run([], client_factory=client_factory, claude_path=claude,
                 cache_root=tmp_path / "interps",
                 notes_path=tmp_path / "NOTES.md", out=out)
    return code, out.getvalue(), (tmp_path / "NOTES.md").read_text(encoding="utf-8")


SECTION = """\
## 7. Legal interpretations

| ID | Interpretation | Topic | |
|---|---|---|---|
| A1 | Gebhart 2009 | Logging PIC as safety pilot | V |

## 8. Next
"""


def test_a_wrong_addressee_is_a_mismatch(tmp_path, transport, client_factory):
    url = I.url_for("Gebhart", "2009")
    transport.add(url, body=make_letter(
        ["FEB 25 2009", "Dear Mr. Someoneelse:", "This responds to your request."]))
    code, output, notes = run_verify(transport, client_factory, tmp_path, SECTION)
    assert code == 1
    assert "mismatch" in output
    assert "does not name Gebhart" in notes


def test_year_on_page_one_passes(tmp_path, transport, client_factory):
    url = I.url_for("Gebhart", "2009")
    transport.add(url, body=make_letter(
        ["FEB 25 2009", "Dear Mr. Gebhart:", "This responds to your request."]))
    code, output, notes = run_verify(transport, client_factory, tmp_path, SECTION)
    assert code == 0
    assert "pass" in output


def test_illegible_year_is_review_not_failure(tmp_path, transport, client_factory):
    # Letterhead dates are scanned stamps; OCR mangles them. That is a human
    # task, not a broken build.
    url = I.url_for("Gebhart", "2009")
    transport.add(url, body=make_letter(
        ["JMl 9 201'.3", "Dear Mr. Gebhart:", "This responds to your request."]))
    code, output, notes = run_verify(transport, client_factory, tmp_path, SECTION)
    assert code == 0, "review must not fail the run"
    assert "review" in output


def test_a_404_is_a_failure(tmp_path, transport, client_factory):
    transport.add(I.url_for("Gebhart", "2009"), status=404)
    code, output, _ = run_verify(transport, client_factory, tmp_path, SECTION)
    assert code == 1
    assert "404" in output


# ---------------------------------------------------------------------------
# discovery never selects
# ---------------------------------------------------------------------------

def test_discovery_rejects_a_candidate_naming_someone_else(transport,
                                                           client_factory):
    url = "https://www.faa.gov/x/Someone_2011_Legal_Interpretation.pdf"
    transport.add(url, body=make_letter(
        ["JAN 1 2011", "Dear Mr. Different:", "Body."]))
    record = D.inspect(client_factory(), {"surname": "Kortokrax"}, url,
                       pathlib.Path(".") / "cache" / "interps")
    assert record["ok"] is False
    assert "does not name Kortokrax" in record["note"]


def test_discovery_confirms_a_matching_candidate(tmp_path, transport,
                                                 client_factory):
    url = "https://www.faa.gov/x/Kortokrax_2006_Legal_Interpretation.pdf"
    transport.add(url, body=make_letter(
        ["AUG 22 2006", "Dear Mr. Kortokrax:", "Body."]))
    record = D.inspect(client_factory(), {"surname": "Kortokrax"}, url,
                       tmp_path / "interps")
    assert record["ok"] is True
    assert "2006" in record["years"]


def test_yearless_entries_all_need_discovery(entries):
    targets = D.needs_discovery(entries)
    assert len(targets) == 13, "with no client, only the yearless are returned"
    assert all(t["year"] is None for t in targets)


def test_committed_candidate_doc_lists_the_dead_index():
    text = (ROOT / "docs" / "INTERPS-CANDIDATES.md").read_text(encoding="utf-8")
    assert "drs.faa.gov" in text
    assert "403" in text and "500" in text

MEMO = (
    "Federal Aviation Administration Memor~yg, MAY 1 s 2009 "
    "Date: To: From: Prepared by: Subject: "
    "Don Bobertz, Attorney, Office of the Regional Counsel, Western Pacific"
)


def test_a_memorandum_is_not_given_a_fabricated_addressee():
    """B3 Bobertz is an internal memo, not a letter to a requester.

    Its header extracts as a block of labels then a block of values, so the
    labels do not sit next to their values. An earlier version read "Prepared
    by: Subject:" positionally and reported the addressee as "Subject". A
    verbatim excerpt is worth more than a confident wrong field.
    """
    found = I.extract(MEMO)
    assert found["kind"] == "memorandum"
    assert found["addressee"] is None
    assert found["subject"] is None
    assert "Don Bobertz" in found["excerpt"]
    assert "2009" in found["years"]


def test_a_memo_still_gates_on_the_surname():
    assert I.surname_matches("Bobertz", None, MEMO)
    assert not I.surname_matches("Kortokrax", None, MEMO)


def test_a_letter_is_not_misread_as_a_memorandum():
    assert I.extract(GLENN)["kind"] == "letter"
    assert I.extract(GLENN)["excerpt"] is None


# ---------------------------------------------------------------------------
# deferred pending review
# ---------------------------------------------------------------------------

def test_deferred_refs_are_declared_in_claude_md():
    """Refs whose confirmed document contradicts the topic column.

    Right addressee, wrong subject. Rule 2 forbids adopting an interpretation
    that merely looks similar, so these wait for a human rather than shipping
    or being silently dropped.
    """
    assert I.deferred() == {"C4", "D2", "G2"}


def test_every_deferred_ref_exists_in_the_table(entries):
    refs = {e["ref"] for e in entries}
    assert I.deferred() <= refs, "a deferred ref must name a real candidate"


def test_deferred_refs_are_not_counted_as_open():
    text = (ROOT / "docs" / "INTERPS-CANDIDATES.md").read_text(encoding="utf-8")
    unresolved = text.split("## Still unresolved")[1].split("## How to")[0]
    for ref in I.deferred():
        assert "(%s," % ref not in unresolved, (
            "%s is deferred, not open; it needs a decision, not a URL" % ref)


def test_the_deferred_section_shows_the_conflict():
    text = (ROOT / "docs" / "INTERPS-CANDIDATES.md").read_text(encoding="utf-8")
    block = text.split("## Deferred pending review")[1].split("## Still")[0]
    # Each deferred ref must show what the document actually says, so the
    # conflict is reviewable without refetching anything.
    for ref in I.deferred():
        assert "| %s |" % ref in block
    assert "forbids adopting an interpretation that merely looks similar" in block
