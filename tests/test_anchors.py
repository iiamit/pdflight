"""Phase 3, the anchor index and resolver.

The plan's premise was "FAA handbooks ship with bookmarks. This covers most
anchors." Measured, that holds for 30 of 40 documents and fails on the two that
matter most, so these tests pin the classification logic that decides which
strategy each document gets.
"""

import io
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import index as IX  # noqa: E402
import resolve as R  # noqa: E402

INDEX_ROOT = IX.INDEX


def entry(title, page=5, level=1):
    return {"level": level, "title": title, "norm": IX.normalize(title),
            "page": page, "usable": IX.usable_entry(level, title, page)}


# ---------------------------------------------------------------------------
# outline quality
# ---------------------------------------------------------------------------

def test_normalize_matches_the_documented_rule():
    # Case fold, strip punctuation, collapse whitespace.
    assert IX.normalize("  Class B  AIRSPACE!! ") == "class b airspace"


def test_pageless_and_junk_entries_are_not_usable():
    assert not IX.usable_entry(1, "Chapter 1", -1)
    assert not IX.usable_entry(1, "Structure Bookmarks", 5)
    assert not IX.usable_entry(1, "03_phak_ch1.pdf", 5)
    assert not IX.usable_entry(1, "1-1", 5)
    assert IX.usable_entry(1, "Class B Airspace", 5)


def test_a_tagged_pdf_outline_is_recognised_as_noise():
    """PHAK's fingerprint: source filenames and structure containers.

    Each title looks plausible alone, so title-by-title filtering misses it.
    """
    outline = ([entry("03_phak_ch1.pdf")] +
               [entry("Introduction To Flying") for _ in range(40)])
    assert IX.outline_is_structural_noise(outline, 522)

    outline = [entry(t) for t in
               ("Structure Bookmarks", "Document", "Article", "Chapter 1")]
    assert IX.outline_is_structural_noise(outline, 522)


def test_a_dense_advisory_circular_outline_is_not_noise():
    """Density alone was the wrong test and rejected every AC.

    ACs run 5 to 7 outline entries per page because each numbered paragraph is
    a bookmark, which is exactly the granularity ac:61-65K:para-14 needs.
    """
    outline = [entry("%d PURPOSE OF THIS ADVISORY CIRCULAR. It provides guidance"
                     % n) for n in range(400)]
    assert not IX.outline_is_structural_noise(outline, 60)


def test_pageless_entries_alone_do_not_condemn_an_outline():
    # Five ACs carry 11 to 19 percent pageless entries and are otherwise good.
    outline = [entry("Real Heading Here %d" % n) for n in range(80)]
    outline += [entry("Dropped %d" % n, page=-1) for n in range(19)]
    assert not IX.outline_is_structural_noise(outline, 60)


# ---------------------------------------------------------------------------
# contents pages must not satisfy a content anchor
# ---------------------------------------------------------------------------

def test_dot_leader_contents_page_is_detected():
    text = "\n".join("Chapter %d Something.................%d-1" % (n, n)
                     for n in range(1, 8))
    assert IX.is_toc_page(text)


def test_contents_page_without_dot_leaders_is_detected():
    """AFH's contents pages use no leaders.

    Missing them left "Chapter N:" matching chapters 1 through 9 within five
    pages of each other, which would anchor the whole handbook to its contents.
    """
    text = "\n".join("Chapter %d: Ground Operations   %d-1" % (n, n)
                     for n in range(1, 12))
    assert IX.is_toc_page(text)


def test_ordinary_prose_is_not_a_contents_page():
    assert not IX.is_toc_page(
        "The pilot in command is directly responsible for the operation of "
        "the aircraft. See figure 2 on page 14 for details.")


# ---------------------------------------------------------------------------
# resolution strategies
# ---------------------------------------------------------------------------

def test_native_beats_everything_for_a_cfr_ref():
    natives = {"sec-91-155": 291}
    found = R.resolve_native("14cfr:91.155", natives)
    assert found["strategy"] == "native"
    # resolve_names is zero-based; anchors are one-based.
    assert found["page"] == 292


def test_native_ignores_a_non_cfr_ref():
    assert R.resolve_native("phak:ch15", {"sec-91-155": 0}) is None


def record(outline=(), pages=None, toc=()):
    return {"outline": list(outline), "outline_structural_noise": False,
            "page_text": list(pages or []), "toc_pages": list(toc)}


def test_outline_match_is_normalised():
    spec = {"doc": "d", "match": "Class B Airspace!"}
    found = R.resolve_outline(spec, record([entry("class b airspace", page=42)]))
    assert found["page"] == 42


def test_outline_falls_back_to_a_prefix():
    # AC titles carry a whole first sentence; AFH titles a draft suffix.
    spec = {"doc": "d", "match": "02 - AFH Chapter 1"}
    found = R.resolve_outline(
        spec, record([entry("02 - AFH Chapter 1 (Draft 4)", page=22)]))
    assert found["page"] == 22


def test_outline_respects_an_ordinal():
    rows = [entry("Introduction", page=10), entry("Introduction", page=99)]
    spec = {"doc": "d", "match": "Introduction", "ordinal": 2}
    assert R.resolve_outline(spec, record(rows))["page"] == 99


def test_outline_is_skipped_when_the_outline_is_noise():
    rec = record([entry("Chapter 1", page=16)])
    rec["outline_structural_noise"] = True
    assert R.resolve_outline({"doc": "d", "match": "Chapter 1"}, rec) is None


def test_regex_skips_contents_pages():
    pages = ["Chapter 1 ....... 1-1\nChapter 2 ....... 2-1", "", "Chapter 1"]
    spec = {"doc": "d", "pattern": r"^\s*Chapter\s+1\s*$"}
    found = R.resolve_regex(spec, record(pages=pages, toc=[1]))
    assert found["page"] == 3, "must not anchor to the table of contents"


def test_regex_respects_an_ordinal():
    pages = ["Chapter 1", "filler", "Chapter 1"]
    spec = {"doc": "d", "pattern": r"^\s*Chapter\s+1\s*$", "ordinal": 2}
    assert R.resolve_regex(spec, record(pages=pages))["page"] == 3


def test_pinned_requires_the_explicit_flag():
    assert R.resolve_pinned({"doc": "d", "page": 7}) is None
    found = R.resolve_pinned({"doc": "d", "page": 7, "pinned": True})
    assert found["strategy"] == "pinned" and found["page"] == 7


def test_priority_order_prefers_outline_then_regex():
    rec = record([entry("Chapter 1", page=16)], pages=["", "Chapter 1"])
    spec = {"doc": "d", "strategy": "outline", "match": "Chapter 1",
            "pattern": r"^Chapter 1$"}
    assert R.resolve_one("phak:ch01", spec, {}, {"d": rec})["strategy"] == "outline"


def test_an_unresolvable_anchor_returns_nothing():
    rec = record([], pages=["nothing here"])
    spec = {"doc": "d", "strategy": "regex", "pattern": r"^Chapter 9$"}
    assert R.resolve_one("phak:ch09", spec, {}, {"d": rec}) is None


# ---------------------------------------------------------------------------
# the committed lock
# ---------------------------------------------------------------------------

def test_lock_serialisation_is_stable(tmp_path):
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    payload = {"phak:ch01": {"doc": "phak", "page": 16, "strategy": "regex",
                             "evidence": "Chapter 1"}}
    R.dump_lock(payload, first)
    R.dump_lock(dict(payload), second)
    assert first.read_bytes() == second.read_bytes()


@pytest.mark.skipif(not (ROOT / "anchors" / "anchors.lock.json").is_file(),
                    reason="anchors.lock.json not built yet")
def test_committed_lock_covers_every_pattern():
    specs = R.load_patterns()
    with io.open(ROOT / "anchors" / "anchors.lock.json", encoding="utf-8") as fh:
        anchors = json.load(fh)["anchors"]
    missing = sorted(set(specs) - set(anchors))
    assert not missing, "unresolved anchors: %s" % missing[:10]


@pytest.mark.skipif(not (ROOT / "anchors" / "anchors.lock.json").is_file(),
                    reason="anchors.lock.json not built yet")
def test_every_locked_page_is_positive():
    with io.open(ROOT / "anchors" / "anchors.lock.json", encoding="utf-8") as fh:
        anchors = json.load(fh)["anchors"]
    bad = {ref: e["page"] for ref, e in anchors.items() if e["page"] < 1}
    assert not bad, "anchors resolving to no page: %s" % bad


@pytest.mark.skipif(not (ROOT / "anchors" / "anchors.lock.json").is_file(),
                    reason="anchors.lock.json not built yet")
def test_pinned_anchors_stay_rare():
    # Rule: pinned anchors warn every run and do not survive repagination.
    with io.open(ROOT / "anchors" / "anchors.lock.json", encoding="utf-8") as fh:
        anchors = json.load(fh)["anchors"]
    pinned = [r for r, e in anchors.items() if e["strategy"] == "pinned"]
    assert len(pinned) <= max(2, len(anchors) // 20), \
        "too many pinned anchors: %s" % pinned


# ---------------------------------------------------------------------------
# the handbook search helper
# ---------------------------------------------------------------------------

import handbook_search as HS  # noqa: E402


def test_owner_picks_the_anchor_whose_range_contains_the_page():
    """A hit belongs to the last anchor at or before it, never the nearest.

    Rounding to the nearest anchor would attribute the first page of a chapter
    to the chapter before it, which is exactly the off-by-one that makes a
    proposal look right and land a page early.
    """
    found = [(10, "phak:ch01", "One"), (40, "phak:ch02", "Two"),
             (90, "phak:ch03", "Three")]
    assert HS.owner(found, 10)[1] == "phak:ch01"
    assert HS.owner(found, 39)[1] == "phak:ch01"
    assert HS.owner(found, 40)[1] == "phak:ch02"
    assert HS.owner(found, 89)[1] == "phak:ch02"
    assert HS.owner(found, 400)[1] == "phak:ch03"


def test_owner_reports_nothing_above_the_first_anchor():
    """Front matter is not chapter one.

    A hit in an unanchored stretch has to report as unanchored. Attaching it
    to the nearest chapter that happens to have an anchor is how a table of
    contents entry becomes a citation.
    """
    found = [(10, "phak:ch01", "One")]
    assert HS.owner(found, 9) is None


def test_anchors_sharing_a_page_are_reported_together():
    """Three seaplane sections start on page 28. None of them wins.

    Crediting the page to whichever anchor sorted last makes a correct anchor
    look like it landed in the wrong place, which is how a real anchor gets
    rebuilt to fix a defect it does not have.
    """
    found = HS.spans("seaplane")
    page_28 = [entry for entry in found if entry[0] == 28]
    assert len(page_28) == 1, "page 28 should be one group, not several rows"
    refs = page_28[0][1]
    for ref in ("seaplane:emergency-landing", "seaplane:go-around",
                "seaplane:postflight-procedures"):
        assert ref in refs, "%s missing from the page 28 group" % ref


def test_the_last_anchor_is_marked_unbounded():
    """Nothing bounds a document's final chapter, so back matter lands in it.

    PHAK ends at Aeromedical Factors, and a search for "circling approach"
    reports hits there because the glossary carries the term. Unmarked, that
    count reads as coverage and invites anchoring an approach element to the
    aeromedical chapter.
    """
    hits, problem = HS.search("phak", r"circling approach", 6)
    assert problem is None
    assert hits
    for key in hits:
        assert "unbounded" in key, "expected the tail to be marked: %s" % key


def test_a_bounded_anchor_carries_no_warning():
    """The marker is for the tail alone, not for every result."""
    hits, problem = HS.search("phak", r"wake turbulence", 6)
    assert problem is None
    bounded = [k for k in hits if "unbounded" not in k
               and "no anchor above" not in k]
    assert bounded, "expected at least one bounded chapter hit"
