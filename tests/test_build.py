"""Phase 5: assemble, link, outline, validate.

Unit-level. The real artefact is 6,122 pages and takes about twenty minutes to
rebuild, so the logic that decides page order, offsets, and outline shape is
tested directly rather than by inspecting the output.
"""

import io
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import assemble as A  # noqa: E402
import link as L  # noqa: E402
import outline as O  # noqa: E402


ENTRIES = [
    {"id": "acs-private", "title": "Private ACS", "section": "standards",
     "order": 1},
    {"id": "phak", "title": "PHAK", "section": "handbooks", "order": 1},
    {"id": "aim", "title": "AIM", "section": "aim", "order": 1},
    {"id": "ac-61-65k", "title": "AC 61-65K", "section": "ac", "order": 1},
]
LOCK = {"acs-private": {"pages": 87, "sha256": "a" * 64},
        "phak": {"pages": 522, "sha256": "b" * 64},
        "phak.addendum.0": {"pages": 5, "sha256": "c" * 64},
        "aim": {"pages": 918, "sha256": "d" * 64},
        "ac-61-65k": {"pages": 60, "sha256": "e" * 64}}


# ---------------------------------------------------------------------------
# canonical order and offsets
# ---------------------------------------------------------------------------

def test_offset_key_separates_a_document_from_its_own_menu():
    """The bug this exists to prevent.

    A document and its per-document menu share an id. Keying offsets by id
    alone let the source silently overwrite the menu entry, so all 34 menu
    offsets vanished and the [doc] nav link had nowhere to point.
    """
    assert A.offset_key("docmenu", "phak") == "phak__menu"
    assert A.offset_key("source", "phak") == "phak"
    assert A.offset_key("cover", None) == "cover"


def test_plan_follows_the_canonical_order():
    steps = A.plan(ENTRIES, LOCK, {})
    kinds = [k for k, _ in steps]
    assert kinds[0] == "cover" and kinds[1] == "menu"
    assert kinds[-1] == "colophon"

    order = [key for kind, key in steps if kind == "source"]
    assert order.index("acs-private") < order.index("phak")
    assert order.index("phak") < order.index("aim")
    assert order.index("aim") < order.index("ac-61-65k")


def test_every_document_is_preceded_by_its_own_menu():
    steps = A.plan(ENTRIES, LOCK, {})
    for index, (kind, key) in enumerate(steps):
        if kind == "source" and "." not in (key or ""):
            assert steps[index - 1] == ("docmenu", key), (
                "%s has no menu page immediately before it" % key)


def test_the_regulations_get_a_menu_page_too():
    # 629 pages that would otherwise be the only ones with half a nav stamp.
    steps = A.plan(ENTRIES, LOCK, {})
    assert ("docmenu", "cfr") in steps
    assert steps.index(("docmenu", "cfr")) < steps.index(("cfr", None))


def test_addenda_follow_their_parent():
    steps = A.plan(ENTRIES, LOCK, {})
    keys = [key for kind, key in steps if kind == "source"]
    assert keys.index("phak") < keys.index("phak.addendum.0")


def test_the_regulations_sit_between_the_aim_and_the_circulars():
    steps = A.plan(ENTRIES, LOCK, {})
    kinds = [(k, v) for k, v in steps]
    cfr_at = kinds.index(("cfr", None))
    aim_at = kinds.index(("source", "aim"))
    ac_at = kinds.index(("source", "ac-61-65k"))
    assert aim_at < cfr_at < ac_at


# ---------------------------------------------------------------------------
# absolute anchors
# ---------------------------------------------------------------------------

OFFSETS = {"phak": {"kind": "source", "start": 469, "pages": 522},
           "cfr": {"kind": "cfr", "start": 4092, "pages": 629}}


def test_relative_pages_become_absolute():
    assert L.absolute_page({"doc": "phak", "page": 376}, OFFSETS) == 844
    assert L.absolute_page({"doc": "cfr", "page": 292}, OFFSETS) == 4383


def test_the_first_page_of_a_document_maps_to_its_start():
    assert L.absolute_page({"doc": "phak", "page": 1}, OFFSETS) == 469


def test_an_out_of_range_page_is_refused():
    assert L.absolute_page({"doc": "phak", "page": 523}, OFFSETS) is None
    assert L.absolute_page({"doc": "phak", "page": 0}, OFFSETS) is None


def test_an_unknown_document_is_refused():
    assert L.absolute_page({"doc": "nope", "page": 1}, OFFSETS) is None


def test_navigation_pages_are_exempt_from_stamping():
    # Gate 5 says every page. A [menu] link on the menu itself is noise, so the
    # exemption is explicit and recorded rather than incidental.
    assert set(L.NAV_KINDS) == {"cover", "menu", "docmenu", "colophon"}


# ---------------------------------------------------------------------------
# outline shape, gate 6
# ---------------------------------------------------------------------------

def test_outline_is_three_levels_with_no_orphans():
    offsets = {"acs-private": {"kind": "source", "start": 10, "pages": 87},
               "phak": {"kind": "source", "start": 100, "pages": 522},
               "cfr": {"kind": "cfr", "start": 700, "pages": 629}}
    grouped = {"phak": [("phak:ch15", {"page": 476})]}
    cfr = [(2, "Part 61", 705), (3, "61.51", 712)]
    toc = O.build(offsets, ENTRIES[:2], grouped, cfr)
    assert not O.problems(toc, 2000)
    assert max(row[0] for row in toc) == 3


def test_cfr_parts_sit_at_level_two_so_sections_fit_at_three():
    """Giving the regulations their own level-2 node would push sections to 4.

    That breaks gate 6, and level 3 is the level a reader navigates by.
    """
    offsets = {"cfr": {"kind": "cfr", "start": 700, "pages": 629}}
    toc = O.build(offsets, [], {}, [(2, "Part 61", 705), (3, "61.51", 712)])
    levels = {title: level for level, title, _page in toc}
    assert levels["Part 61"] == 2
    assert levels["61.51"] == 3


def test_a_depth_of_two_is_reported():
    assert any("depth is 2" in p for p in
               O.problems([[1, "A.", 1], [2, "B", 2]], 10))


def test_an_orphan_level_is_reported():
    problems = O.problems([[1, "A.", 1], [3, "C", 2]], 10)
    assert any("orphan" in p for p in problems)


def test_a_page_beyond_the_document_is_reported():
    problems = O.problems([[1, "A.", 1], [2, "B", 999]], 10)
    assert any("points at page" in p for p in problems)


# ---------------------------------------------------------------------------
# the built artefact
# ---------------------------------------------------------------------------

FINAL = ROOT / "build" / "pdflight-outlined.pdf"
OFFSETS_FILE = ROOT / "build" / "offsets.json"


@pytest.mark.skipif(not OFFSETS_FILE.is_file(), reason="run make assemble")
def test_committed_offsets_are_contiguous():
    with io.open(OFFSETS_FILE, encoding="utf-8") as handle:
        data = json.load(handle)
    ordered = sorted(data["offsets"].values(), key=lambda e: e["start"])
    cursor = 1
    for entry in ordered:
        assert entry["start"] == cursor, "gap or overlap at page %d" % cursor
        cursor += entry["pages"]
    assert cursor - 1 == data["total_pages"]


@pytest.mark.skipif(not OFFSETS_FILE.is_file(), reason="run make assemble")
def test_every_manifest_document_has_a_menu_offset():
    import _manifest as M

    with io.open(OFFSETS_FILE, encoding="utf-8") as handle:
        offsets = json.load(handle)["offsets"]
    missing = [e["id"] for e in M.load_sources()
               if (e["id"] + "__menu") not in offsets]
    assert not missing, "no menu page recorded for: %s" % missing
