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


# ---------------------------------------------------------------------------
# the validator must measure the thing it claims to measure
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not FINAL.is_file(), reason="run make build")
def test_size_gate_measures_the_pdf_not_a_csv():
    """Gate 8 once reported 1.1 MB for a 475 MB file.

    A loop added for gate 3 reassigned `path`, so gate 8 stat'd the last
    crosswalk CSV instead of the build. It would have passed a 2 GB file.
    A validator that misreports is worse than no validator.
    """
    import validate as V

    out = io.StringIO()
    V.run([], out=out)
    line = next(row for row in out.getvalue().splitlines()
                if row.startswith("8 "))
    reported = float(line.split("PASS")[-1].split()[0])
    actual = FINAL.stat().st_size / 1048576
    assert abs(reported - actual) < 1.0, (
        "gate 8 reported %.1f MB, file is %.1f MB" % (reported, actual))


# ---------------------------------------------------------------------------
# section-level crosswalk targets
# ---------------------------------------------------------------------------

def test_a_section_ref_resolves_to_the_cfr_section_label():
    """`14cfr:91.119` must reach 91.119, not the top of Part 91.

    The CFR build labels sections `sec-{part}-{number}`. Nothing else in the
    pipeline performs that translation, so a missing branch here silently
    downgrades every refined element back to a part-level jump.
    """
    mapping = {"sec-91-119": 4200, "sec-61-3": 3900, "part-14-91": 4000}
    resolve = L.build_resolver(mapping, {}, [])
    assert resolve("14cfr:91.119") == 4200
    assert resolve("14cfr:61.3") == 3900
    assert resolve("14cfr:part-91") == 4000


def test_a_curated_anchor_outranks_the_generated_section_label():
    # A hand-authored anchor may point at a subsection rather than the head.
    mapping = {"14cfr:91.155": 4111, "sec-91-155": 4100}
    assert L.build_resolver(mapping, {}, [])("14cfr:91.155") == 4111


def test_an_unknown_section_resolves_to_nothing():
    assert L.build_resolver({}, {}, [])("14cfr:99.999") is None


def test_the_inline_element_pattern_finds_a_code_among_words():
    """bootstrap_crosswalk anchors its pattern to a whole line.

    Reusing that one here matched nothing, because on the page the code is
    followed by the element text.
    """
    found = L.ELEMENT_INLINE.findall(
        "PA.V.B.R3 Collision hazards, to include aircraft and terrain.")
    assert found == ["PA.V.B.R3"]
    assert L.ELEMENT_INLINE.findall("IR.VI.A.K1a and IR.VI.A.K1b") == [
        "IR.VI.A.K1a", "IR.VI.A.K1b"]


@pytest.mark.skipif(not (ROOT / "crosswalk" / "private.csv").is_file(),
                    reason="run make crosswalk")
def test_element_targets_carries_only_section_rows():
    targets = L.element_targets()
    assert targets, "no element has a section-level target"
    for code, refs in targets.items():
        for ref in refs:
            assert ref.startswith("14cfr:"), (code, ref)
            assert not ref.startswith("14cfr:part-"), (
                "%s kept a part-level row: %s" % (code, ref))


# ---------------------------------------------------------------------------
# the crosswalk pages, and the round trip through them
# ---------------------------------------------------------------------------

class FakeRect:
    def __init__(self, x0):
        self.x0 = x0

    def __or__(self, other):
        return self


class FakePyMuPDF:
    LINK_GOTO = 1

    @staticmethod
    def Rect(box):
        return FakeRect(box[0])


class FakePage:
    """Enough of a page to exercise the linkers without building a PDF."""

    def __init__(self, words):
        self._words = words
        self.links = []

    def get_text(self, _kind):
        return self._words

    def insert_link(self, spec):
        self.links.append(spec)


def _words(rows):
    # (x0, y0, x1, y1, text)
    out = []
    for y, items in rows:
        x = 40.0
        for token in items:
            out.append((x, y, x + 10.0 * len(token), y + 9.0, token))
            x += 10.0 * len(token) + 4.0
    return out


def test_a_contents_entry_is_not_mistaken_for_an_element_definition():
    """Element codes appear twice: in the left column and in contents lists.

    Measured across both ACS documents, 1,569 sit at x0 < 110 and are
    definitions; 109 sit further right and are contents entries. Linking the
    contents entries would put the reader on the wrong page.
    """
    # 122.0 is where the ACS text column starts, which is where a contents
    # entry sits. The left-hand definition column runs 49.5 to 97.
    page = FakePage([(122.0, 200.0, 182.0, 209.0, "PA.I.A.K1")])
    assert list(L.element_code_rects(page, FakePyMuPDF())) != []
    assert list(L.element_code_rects(page, FakePyMuPDF(),
                                     left_column_only=True)) == []


def test_the_left_column_definition_is_linked():
    page = FakePage([(49.5, 200.0, 97.0, 209.0, "PA.I.A.K1")])
    found = list(L.element_code_rects(page, FakePyMuPDF(),
                                      left_column_only=True))
    assert [code for code, _rect in found] == ["PA.I.A.K1"]


def test_an_element_links_to_its_crosswalk_row():
    page = FakePage([(49.5, 200.0, 97.0, 209.0, "PA.I.A.K1")])
    added = L.link_element_to_hub(page, {"PA.I.A.K1": 42}, FakePyMuPDF())
    assert added == 1
    assert page.links[0]["page"] == 41


def test_an_element_with_no_crosswalk_row_gets_no_link():
    page = FakePage([(49.5, 200.0, 97.0, 209.0, "PA.I.A.K9")])
    assert L.link_element_to_hub(page, {"PA.I.A.K1": 42}, FakePyMuPDF()) == 0
    assert page.links == []


def test_a_crosswalk_row_links_back_and_out():
    """The round trip: code returns to the ACS, each section jumps to Title 14."""
    page = FakePage(_words([
        (200.0, ["PA.I.A.K1"]),
        (212.0, ["\u00a7", "61.3", "\u00a7", "61.51"]),
    ]))
    chips = L.chip_index({"PA.I.A.K1": ["14cfr:61.3", "14cfr:61.51"]})
    resolve = L.build_resolver({"sec-61-3": 500, "sec-61-51": 505}, {}, [])
    back, sections = L.link_hub_row(page, chips, {"PA.I.A.K1": 14},
                                    resolve, FakePyMuPDF())
    assert back == 1, "no way back to the ACS element"
    assert sections == 2, "every section must be independently reachable"
    assert {link["page"] for link in page.links} == {13, 499, 504}


def test_a_number_that_is_not_a_target_never_becomes_a_link():
    """The status strip carries `V2026.08.1`, which looks like a section.

    Only numbers an element on the page actually claims are linked, so a
    version string, a page count, or a figure number cannot become a jump.
    """
    page = FakePage(_words([
        (200.0, ["PA.I.A.K1"]),
        (212.0, ["V2026.08.1", "\u00a7", "61.3"]),
    ]))
    resolve = L.build_resolver({"sec-61-3": 500, "sec-8-1": 900}, {}, [])
    _back, sections = L.link_hub_row(
        page, L.chip_index({"PA.I.A.K1": ["14cfr:61.3"]}), {}, resolve,
        FakePyMuPDF())
    assert sections == 1
    assert page.links[0]["page"] == 499


@pytest.mark.skipif(not OFFSETS_FILE.is_file(), reason="run make assemble")
def test_each_acs_carries_its_crosswalk_pages():
    import _manifest as M

    with io.open(OFFSETS_FILE, encoding="utf-8") as handle:
        offsets = json.load(handle)["offsets"]
    for entry in M.load_sources():
        if entry["section"] != "standards":
            continue
        record = offsets.get(entry["id"] + "__menu")
        if entry["id"] in ("acs-private-airplane", "acs-instrument-airplane"):
            assert record and record["pages"] > 1, (
                "%s has no crosswalk pages" % entry["id"])


# ---------------------------------------------------------------------------
# inline target buttons
# ---------------------------------------------------------------------------

def _row(y, items):
    """(x0, y0, x1, y1, text) tuples for one visual row."""
    out = []
    for x, token in items:
        out.append((x, y, x + 5.4 * len(token), y + 9.0, token))
    return out


def test_the_changelog_page_gets_no_buttons():
    """The ACS front matter lists element codes in four columns.

    With no element prose on the row, the neighbouring column reads as this
    element's text. The first build stamped 86 buttons across that page.
    """
    words = (_row(200.0, [(49.5, "PA.I.B.K1e"), (200.0, "PA.II.A.S4"),
                          (310.0, "PA.VI.D.S5"), (430.0, "PA.VIII.E.R8")])
             + _row(212.0, [(49.5, "PA.I.B.K4"), (200.0, "PA.II.B.K4")]))
    assert L.element_blocks(FakePage(words), FakePyMuPDF()) == []


def test_a_real_element_row_is_found():
    words = _row(200.0, [(49.5, "PA.I.A.K1"),
                         (122.0, "Certification requirements.")])
    blocks = L.element_blocks(FakePage(words), FakePyMuPDF())
    assert [b[0] for b in blocks] == ["PA.I.A.K1"]


def test_an_element_does_not_swallow_the_next_section_header():
    """Buttons were landing after `Skills:` instead of after the element.

    An element's continuation lines carry nothing in the left column. A row
    that does is the next thing starting, so the block stops there.
    """
    words = (_row(200.0, [(49.5, "PA.I.A.K5"), (122.0, "Part 68 BasicMed.")])
             + _row(224.0, [(40.5, "Skills:"),
                            (122.0, "The applicant exhibits the skill to:")]))
    blocks = L.element_blocks(FakePage(words), FakePyMuPDF())
    assert len(blocks) == 1
    code, tail, _y0, _y1 = blocks[0]
    assert code == "PA.I.A.K5"
    # the tail is the element's own text, not the header that follows it
    assert tail < 122.0 + 5.4 * len("The applicant exhibits the skill to:")


def test_a_wrapped_element_keeps_its_continuation_line():
    words = (_row(200.0, [(49.5, "PA.I.A.S1"), (122.0, "Apply requirements")])
             + _row(212.0, [(122.0, "given by the evaluator.")]))
    blocks = L.element_blocks(FakePage(words), FakePyMuPDF())
    assert len(blocks) == 1
    assert blocks[0][2] >= 212.0, "button must sit on the last line"


def test_only_specific_targets_earn_a_button(tmp_path):
    """A button means "here is the rule".

    `phak` means "here is a 522 page handbook", which the References line
    above the element already links to.
    """
    import csv as _csv

    path = tmp_path / "private.csv"
    with io.open(str(path), "w", encoding="utf-8", newline="") as handle:
        writer = _csv.DictWriter(handle, fieldnames=[
            "source_ref", "target_ref", "relation", "confidence", "note",
            "element_text"])
        writer.writeheader()
        for ref in ("14cfr:91.119", "phak", "afh", "14cfr:part-91"):
            writer.writerow({"source_ref": "PA.V.B.R3", "target_ref": ref,
                             "relation": "r", "confidence": "auto",
                             "note": "", "element_text": "t"})
    assert L.specific_targets(str(tmp_path)) == {
        "PA.V.B.R3": ["14cfr:91.119"]}


def test_button_labels_name_the_target():
    """Short forms the FAA itself uses, because a button is millimetres wide.

    `FAA-H-8083-23 chapter 5` is 44pt of label on a page that has 38pt to
    spare, so handbooks without a common abbreviation use their bare number.
    """
    assert L.button_label("14cfr:91.119") == "91.119"
    assert L.button_label("phak:ch15") == "PHAK c15"
    assert L.button_label("ac:61-65k") == "AC 61-65K"
    assert L.button_label("phak") == "PHAK"
    assert L.button_label("risk-management:ch02") == "8083-2 c2"
    # the AIM cites itself as chapter-section
    assert L.button_label("aim:ch03-s02") == "AIM 3-2"
    assert L.button_label("something-unknown") is None


def test_no_button_label_is_wider_than_the_margin_allows():
    widest = max((L.button_label(r) for r in
                  ("14cfr:91.119", "phak:ch15", "aim:ch03-s02",
                   "risk-management:ch02", "aviation-weather:ch05")), key=len)
    assert L.button_width(widest) < 45.0, (
        "%r is %.1fpt, too wide to sit inline" % (widest, L.button_width(widest)))


def test_a_button_that_would_cross_the_margin_is_dropped_not_overprinted():
    blocks = [("PA.V.B.R3", L.RIGHT_EDGE - 12.0, 200.0, 209.0)]
    page = FakePage([])
    drawn, _touched, dropped = L.draw_target_buttons(
        page, blocks, {"PA.V.B.R3": ["14cfr:91.119"]},
        lambda _ref: 4200, FakePyMuPDF())
    assert (drawn, dropped) == (0, 1)
    assert page.links == []


# ---------------------------------------------------------------------------
# crosswalk chips of every kind, not just the numeric ones
# ---------------------------------------------------------------------------

def test_a_handbook_chip_is_linked_not_just_a_cfr_one():
    """The first version matched chips with a number pattern.

    That found `61.3` and missed `PHAK c15`, so every handbook chip rendered
    on the crosswalk page and went nowhere. It mattered most for targets that
    overflow the inline buttons, because the crosswalk page is the only place
    they appear at all.
    """
    chips = L.chip_index({"PA.V.B.R3": ["14cfr:91.119", "phak:ch15"]})
    assert chips == {"91.119": "14cfr:91.119", "PHAK c15": "phak:ch15"}

    page = FakePage(_words([
        (200.0, ["PA.V.B.R3"]),
        (212.0, ["91.119", "PHAK", "c15"]),
    ]))
    resolve = L.build_resolver(
        {"sec-91-119": 500, "phak:ch15": 900}, {}, [])
    _back, linked = L.link_hub_row(page, chips, {}, resolve, FakePyMuPDF())
    assert linked == 2
    assert {link["page"] for link in page.links} == {499, 899}


def test_a_short_label_does_not_match_inside_a_longer_one():
    """`AFH c1` is a prefix of `AFH c11`, and `61.3` of `61.31`.

    Matching the short one first linked the wrong chapter and left the real
    chip unlinked.
    """
    assert not L._standalone("AFH c11", 0, len("AFH c1"))
    assert L._standalone("AFH c1 x", 0, len("AFH c1"))
    assert not L._standalone("61.31", 0, len("61.3"))
    assert L._standalone("61.3 ", 0, len("61.3"))


def test_the_longer_chip_wins_when_both_could_match():
    chips = {"AFH c1": "afh:ch01", "AFH c11": "afh:ch11"}
    page = FakePage(_words([(200.0, ["AFH", "c11"])]))
    resolve = L.build_resolver({"afh:ch01": 100, "afh:ch11": 800}, {}, [])
    _back, linked = L.link_hub_row(page, chips, {}, resolve, FakePyMuPDF())
    assert linked == 1
    assert page.links[0]["page"] == 799, "linked the wrong chapter"


def test_a_chip_label_is_never_ambiguous():
    """Two anchors sharing a label would make the chip link unpredictable."""
    targets = L.specific_targets()
    if not targets:
        pytest.skip("run make crosswalk")
    seen = {}
    for refs in targets.values():
        for ref in refs:
            label = L.button_label(ref)
            if label:
                assert seen.setdefault(label, ref) == ref, (
                    "label %r means both %s and %s"
                    % (label, seen[label], ref))


# ---------------------------------------------------------------------------
# the generated menu links, which assembly strips
# ---------------------------------------------------------------------------

def test_a_named_link_is_redrawn_as_a_page_goto():
    """insert_pdf carries no link whose target is a named destination.

    Typst emits only that kind, so assembly stripped all 73 menu links and
    the cover, contents, entry arrows, colophon button and every "Return to
    the main menu" did nothing. Three gates looked at the file and none
    noticed, because zero links dangle and navigation pages are stamp-exempt.
    """
    class SourcePage:
        def __init__(self, links):
            self._links = links

        def get_links(self):
            return self._links

    class SourceDoc:
        page_count = 2

        def __init__(self, pages):
            self._pages = pages

        def load_page(self, number):
            return self._pages[number]

        def close(self):
            pass

    # cover (source page 0) links to the main menu (source page 1)
    source = SourceDoc([SourcePage([{"kind": 4, "page": 1,
                                     "from": FakeRect(10.0)}]),
                        SourcePage([])])
    target = FakePage([])

    class Assembled:
        page_count = 20

        def load_page(self, _number):
            return target

    offsets = {"cover": {"kind": "cover", "start": 1, "pages": 1,
                         "source_start": 0},
               "menu": {"kind": "menu", "start": 2, "pages": 1,
                        "source_start": 1}}

    class Fake(FakePyMuPDF):
        @staticmethod
        def open(_path):
            return source

    added = L.relink_generated(Assembled(), offsets, __file__, Fake())
    assert added == 1
    # source page 1 is assembled page 2, so the GoTo is 0-based page 1
    assert target.links[0]["page"] == 1
    assert target.links[0]["kind"] == FakePyMuPDF.LINK_GOTO


def test_relinking_is_skipped_when_menus_pdf_is_absent():
    offsets = {"cover": {"kind": "cover", "start": 1, "pages": 1,
                         "source_start": 0}}
    assert L.relink_generated(None, offsets, "no/such/menus.pdf",
                              FakePyMuPDF()) == 0


@pytest.mark.skipif(not OFFSETS_FILE.is_file(), reason="run make assemble")
def test_assembly_records_where_each_generated_run_came_from():
    """Without source_start the linker cannot find the links to redraw."""
    with io.open(OFFSETS_FILE, encoding="utf-8") as handle:
        offsets = json.load(handle)["offsets"]
    generated = [(k, e) for k, e in offsets.items() if e["kind"] in L.NAV_KINDS]
    assert generated, "no generated pages in the offsets"
    for key, entry in generated:
        assert entry.get("source_start") is not None, (
            "%s has no source_start" % key)


@pytest.mark.skipif(not FINAL.is_file(), reason="run make build")
def test_the_built_menu_pages_actually_carry_links():
    """The defect this whole section exists for, checked on the real file."""
    import pymupdf

    with io.open(OFFSETS_FILE, encoding="utf-8") as handle:
        offsets = json.load(handle)["offsets"]
    document = pymupdf.open(FINAL)
    try:
        for key, entry in offsets.items():
            if entry["kind"] not in ("cover", "menu"):
                continue
            page = document.load_page(entry["start"] - 1)
            assert page.get_links(), "%s page %d has no links" % (
                key, entry["start"])
    finally:
        document.close()


# ---------------------------------------------------------------------------
# rule 8, on the artefact that actually ships
# ---------------------------------------------------------------------------

def test_the_seed_is_content_derived_not_build_derived():
    """Rule 8 and section 6 both require it.

    A seed that moved with the build would give a different /ID every run,
    which is the thing being fixed.
    """
    import outline as O

    first = O.seed_for(OFFSETS_FILE)
    second = O.seed_for(OFFSETS_FILE)
    assert first == second and len(first) == 64


@pytest.mark.skipif(not FINAL.is_file(), reason="run make build")
def test_the_shipped_file_has_a_pinned_trailer_id():
    """The first Linux build differed from the Windows one by four bytes.

    Same inputs, same PyMuPDF, same Typst. The cause was the trailer /ID:
    optimize.py pinned it on the intermediate source copies and nothing
    pinned it on the file that ships. Without this, the release job cannot
    tell "nothing changed" from "changed", which is what stops the quarterly
    floor build cutting an empty release.
    """
    import optimize
    import outline as O

    data = FINAL.read_bytes()
    match = optimize.TRAILER_ID.search(data[-4096:])
    assert match, "no trailer /ID found in the shipped file"

    expected = optimize.digest_for(O.seed_for(OFFSETS_FILE)).encode()
    assert data[-4096:].count(expected) >= 2, (
        "trailer /ID is not the content-derived constant: %r"
        % match.group(0)[:80])


@pytest.mark.skipif(not FINAL.is_file(), reason="run make build")
def test_the_shipped_file_carries_no_build_timestamp():
    """A creation date makes every rebuild differ for no content reason."""
    import pymupdf

    document = pymupdf.open(FINAL)
    try:
        meta = document.metadata or {}
    finally:
        document.close()
    assert not (meta.get("creationDate") or "").strip(), meta.get("creationDate")
    assert not (meta.get("modDate") or "").strip(), meta.get("modDate")
