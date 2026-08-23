"""Phase 2, the CFR pipeline.

The regulations are generated rather than fetched, which is what lets every
section carry a native PDF named destination. These tests guard the two things
that makes possible: parsing the real eCFR DTD, and emitting Typst that
compiles.
"""

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import _cfr  # noqa: E402

CACHE = ROOT / "cache" / "cfr"

# A miniature part in the shape eCFR actually returns. Note DIV5 is the PART,
# not the subpart, and the 91.155 table sits inside an untyped <DIV>.
FIXTURE = b"""<?xml version="1.0"?>
<DIV5 N="91" TYPE="PART">
<HEAD>PART 91&#x2014;GENERAL OPERATING AND FLIGHT RULES</HEAD>
<AUTH><HED>Authority:</HED><PSPACE>49 U.S.C. 106(f).</PSPACE></AUTH>
<DIV6 N="B" TYPE="SUBPART">
<HEAD>Subpart B&#x2014;Flight Rules</HEAD>
<DIV8 N="91.155" TYPE="SECTION">
<HEAD>&#xA7; 91.155 Basic VFR weather minimums.</HEAD>
<P>(a) Except as provided in paragraph (b), no person may operate below V<I>H</I>.</P>
<DIV>
<TABLE>
<THEAD><TR><TH>Airspace</TH><TH>Flight visibility<br/>(statute miles)</TH></TR></THEAD>
<TBODY><TR><TD>Class A</TD><TD>Not Applicable</TD></TR>
<TR><TD>Class B</TD><TD>3</TD></TR></TBODY>
</TABLE>
</DIV>
<CITA>[Docket 24458, 56 FR 65660]</CITA>
</DIV8>
</DIV6>
<DIV9 N="A" TYPE="APPENDIX">
<HEAD>Appendix A to Part 91</HEAD>
<P>Category II operations.</P>
</DIV9>
</DIV5>
"""


@pytest.fixture(scope="module")
def part():
    return _cfr.parse_part(FIXTURE, 14)


# ---------------------------------------------------------------------------
# the DTD is not what the plan says it is
# ---------------------------------------------------------------------------

def test_div5_is_the_part_not_the_subpart(part):
    """CLAUDE.md 8 and BUILD-PLAN 3 both say DIV3 part, DIV5 subpart.

    A part-level eCFR request returns DIV5 TYPE=PART, DIV6 TYPE=SUBPART,
    DIV8 TYPE=SECTION. A parser written to the documented mapping finds
    nothing at all, so this is worth pinning.
    """
    assert part["part"] == "91"
    assert part["children"][0]["kind"] == "subpart"
    assert part["children"][0]["n"] == "B"


def test_a_non_part_root_is_rejected():
    with pytest.raises(ValueError, match="expected a PART root"):
        _cfr.parse_part(b'<DIV8 N="91.155" TYPE="SECTION"/>', 14)


def test_sections_carry_a_label_and_a_ref(part):
    section = _cfr.sections_of(part)[0]
    assert section["n"] == "91.155"
    assert section["label"] == "sec-91-155"
    assert section["ref"] == "14cfr:91.155"


def test_label_scheme_matches_the_documented_example():
    assert _cfr.label_for("91.155") == "sec-91-155"
    assert _cfr.label_for("830.5") == "sec-830-5"
    assert _cfr.ref_for(49, "830.5") == "49cfr:830.5"


def test_appendices_are_kept(part):
    kinds = [c["kind"] for c in part["children"]]
    assert "appendix" in kinds, "neither plan mentions appendices; they exist"


def test_part_level_authority_is_kept(part):
    assert any("49 U.S.C." in text for text in part["front"])


# ---------------------------------------------------------------------------
# the table that would have been dropped silently
# ---------------------------------------------------------------------------

def test_a_table_inside_an_untyped_div_is_not_dropped(part):
    """91.155 keeps its VFR weather minimums inside a bare <DIV>.

    Skipping unrecognised DIVs loses that table while the page count still
    looks plausible, which is the failure mode this exists to prevent.
    """
    section = _cfr.sections_of(part)[0]
    tables = [b for b in section["body"] if b["kind"] == "table"]
    assert len(tables) == 1
    table = tables[0]
    assert table["cols"] == 2
    assert table["header"][0] == "Airspace"
    assert ["Class A", "Not Applicable"] == table["rows"][0]


def test_ragged_rows_are_padded_to_the_column_count():
    xml = (b'<DIV5 N="1" TYPE="PART"><DIV8 N="1.1" TYPE="SECTION">'
           b"<HEAD>&#xA7; 1.1 X.</HEAD><TABLE><TR><TD>a</TD><TD>b</TD></TR>"
           b"<TR><TD>c</TD></TR></TABLE></DIV8></DIV5>")
    table = [b for b in _cfr.sections_of(_cfr.parse_part(xml, 14))[0]["body"]
             if b["kind"] == "table"][0]
    assert all(len(row) == table["cols"] for row in table["rows"])


# ---------------------------------------------------------------------------
# emitting Typst that actually compiles
# ---------------------------------------------------------------------------

def test_emphasis_uses_the_function_form(part):
    """`V<I>H</I>` must not become `V_H_`.

    Typst only reads an underscore as emphasis at a word boundary, so V_H_ is
    an unclosed delimiter and the whole document fails to compile. Regulatory
    text is full of these: V_H_, P_4_, and italicised URLs ending ",_".
    """
    rendered = _cfr.render_part(part)
    assert "#emph[H]" in rendered
    assert "V_H_" not in rendered


def test_linebreak_is_followed_by_a_space(part):
    # "#linebreak()(statute miles)" parses as calling the result of linebreak.
    rendered = _cfr.render_part(part)
    assert "#linebreak() " in rendered
    assert "#linebreak()(" not in rendered


def test_typst_special_characters_are_escaped():
    assert _cfr.escape("cost is $5 #1 [a] *b* _c_") == \
        "cost is \\$5 \\#1 \\[a\\] \\*b\\* \\_c\\_"


def test_em_dashes_never_reach_the_output(part):
    # Rule 10 applies to generated PDF text too.
    rendered = _cfr.render_part(part)
    assert "—" not in rendered
    assert "—" not in part["heading"]


def test_every_section_emits_a_label(part):
    rendered = _cfr.render_part(part)
    for section in _cfr.sections_of(part):
        assert "<%s>" % section["label"] in rendered


def test_render_is_deterministic(part):
    assert _cfr.render_part(part) == _cfr.render_part(part)


# ---------------------------------------------------------------------------
# the committed corpus
# ---------------------------------------------------------------------------

def cached_parts():
    for path in sorted(CACHE.glob("*.xml")):
        title = 49 if "title-49" in path.name else 14
        yield path, _cfr.parse_part(path.read_bytes(), title)


@pytest.mark.skipif(not list(CACHE.glob("*.xml")),
                    reason="no cached eCFR XML; run make cfr")
def test_section_labels_are_unique_across_the_whole_corpus():
    """Labels become PDF destinations, so a collision silently misroutes a ref.

    CLAUDE.md's scheme has no title component, which is safe only while no two
    titles share a section number. This is the test that catches it if that
    ever stops being true.
    """
    seen = {}
    for _path, part in cached_parts():
        for section in _cfr.sections_of(part):
            label = section["label"]
            assert label not in seen, (
                "label %s claimed by both %s and %s"
                % (label, seen.get(label), section["ref"]))
            seen[label] = section["ref"]
    assert len(seen) > 800


@pytest.mark.skipif(not (ROOT / "manifest" / "cfr.lock.yaml").is_file(),
                    reason="cfr.lock.yaml not built yet")
def test_committed_cfr_lock_covers_every_manifest_part():
    import cfr_build

    wanted = cfr_build.load_cfr_manifest()
    lock = cfr_build.load_lock()
    for title, number in wanted:
        key = "title-%s-part-%s" % (title, number)
        assert key in lock, "%s missing from cfr.lock.yaml" % key
        assert lock[key]["sections"] > 0
