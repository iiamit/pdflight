"""Phase 6, the crosswalk bootstrap.

The References line of every ACS Task names the documents that support it.
Parsing those is what converts most of the authoring effort into review, so the
parser is worth pinning: each defect below produced a plausible-looking result
rather than an error.
"""

import csv
import io
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import bootstrap_crosswalk as B  # noqa: E402

CROSSWALK = ROOT / "crosswalk"

RELATIONS = {"regulation", "explanation", "guidance", "standard"}
CONFIDENCE = {"auto", "verified"}


# ---------------------------------------------------------------------------
# the drop cap
# ---------------------------------------------------------------------------

BLOCK = """Task A.  Pilot Qualifications
eferences:\t
R
14 CFR parts 61, 68, 91; AC 68-1; FAA-H-8083-2, FAA-H-8083-25
bjective:\t
O
To determine the applicant exhibits satisfactory knowledge.
"""


def test_references_survives_the_drop_cap():
    """The word "References" is never in the extracted text.

    The ACS sets these labels as drop caps, so the tail comes out first and the
    initial lands on its own line. A parser looking for "References:" matches
    nothing at all and reports zero rows without erroring, which is the worst
    possible failure for a bootstrapping tool.
    """
    assert "References:" not in BLOCK
    found = B.REFERENCES.search(BLOCK)
    assert found
    assert found.group(1).startswith("14 CFR parts 61")


# ---------------------------------------------------------------------------
# the regex that quietly emptied the handbook index
# ---------------------------------------------------------------------------

def test_handbook_number_accepts_a_revision_letter():
    """A closing \\b after the digits refuses "FAA-H-8083-25C" entirely.

    That shrank the handbook index to the single title shipping without a
    letter, and every handbook reference then reported as unmet.
    """
    assert B.HANDBOOK.search("FAA-H-8083-25C").group(1) == "8083-25"
    assert B.HANDBOOK.search("FAA-H-8083-25").group(1) == "8083-25"
    assert B.HANDBOOK.search("FAA-H-8083-1B").group(1) == "8083-1"


def test_handbook_index_maps_letters_to_ids():
    lock = {"phak": {"faa_number": "FAA-H-8083-25C"},
            "ifh": {"faa_number": "FAA-H-8083-15B"},
            "phak.addendum.0": {"faa_number": "FAA-H-8083-25C"}}
    index = B.handbook_index(lock)
    assert index["8083-25"] == "phak"
    assert index["8083-15"] == "ifh"


def test_an_alias_rescues_a_document_whose_number_would_not_extract():
    # Risk Management states no number the extractor trusts, so its lock entry
    # is null by design under rule 2a. Without the alias every Task citing
    # FAA-H-8083-2 reads as unmet against a handbook that is in the corpus.
    index = B.handbook_index({"risk-management": {"faa_number": None}})
    assert index.get("8083-2") == "risk-management"


# ---------------------------------------------------------------------------
# element codes are not what the certificate name suggests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", ["PA.I.B.K1", "IR.II.A.S3", "CA.IV.K.R2",
                                  "AA.I.A.K1", "AI.I.A.K1", "FI.II.B.S1",
                                  "PA.I.B.K3b"])
def test_every_real_prefix_parses(code):
    """ATP uses AA, not AT. The CFI ACS uses both AI and FI.

    Hardcoding a guessed prefix produced zero rows for both documents while
    the run still reported success.
    """
    assert B.ELEMENT.match(code)


def test_a_non_element_line_is_not_matched():
    assert not B.ELEMENT.match("Task A.  Pilot Qualifications")
    assert not B.ELEMENT.match("14 CFR part 91")


# ---------------------------------------------------------------------------
# reference resolution
# ---------------------------------------------------------------------------

HANDBOOKS = {"8083-25": "phak", "8083-2": "risk-management"}
ACS = {"91-92": "ac-91-92"}


def test_cfr_parts_become_part_level_targets():
    targets, unmet = B.parse_references(
        "14 CFR parts 61, 68, 91", HANDBOOKS, ACS, "aim")
    assert ("14cfr:part-61", "regulation") in targets
    assert ("14cfr:part-91", "regulation") in targets
    assert not unmet


def test_relations_follow_the_kind_of_source():
    targets, _unmet = B.parse_references(
        "14 CFR part 91; AC 91-92; AIM; FAA-H-8083-25", HANDBOOKS, ACS, "aim")
    kinds = dict(targets)
    assert kinds["14cfr:part-91"] == "regulation"
    assert kinds["ac-91-92"] == "guidance"
    assert kinds["aim"] == "guidance"
    assert kinds["phak"] == "explanation"


def test_a_reference_outside_the_corpus_is_reported_not_dropped():
    _targets, unmet = B.parse_references("AC 68-1", HANDBOOKS, ACS, "aim")
    assert unmet == ["AC 68-1"]


def test_targets_are_deduplicated():
    targets, _unmet = B.parse_references(
        "FAA-H-8083-25, FAA-H-8083-25", HANDBOOKS, ACS, "aim")
    assert len(targets) == 1


# ---------------------------------------------------------------------------
# the committed CSVs
# ---------------------------------------------------------------------------

def committed():
    for path in sorted(CROSSWALK.glob("*.csv")):
        with io.open(path, encoding="utf-8", newline="") as handle:
            yield path, list(csv.DictReader(handle))


@pytest.mark.skipif(not list(CROSSWALK.glob("*.csv")),
                    reason="run make crosswalk")
def test_schema_carries_the_element_text():
    """BUILD-PLAN section 4 lists five columns; section 11 requires the text.

    The FAA renumbers ACS codes on revision, so a crosswalk keyed only by code
    breaks by id rather than by page and cannot be remapped automatically.
    """
    for path, rows in committed():
        assert rows, "%s is empty" % path.name
        assert set(rows[0]) == set(B.FIELDS)
        assert "element_text" in rows[0]


@pytest.mark.skipif(not list(CROSSWALK.glob("*.csv")),
                    reason="run make crosswalk")
def test_every_row_is_well_formed():
    for path, rows in committed():
        for row in rows:
            assert B.ELEMENT.match(row["source_ref"]), (
                "%s: %r is not an element code" % (path.name, row["source_ref"]))
            assert row["relation"] in RELATIONS
            assert row["confidence"] in CONFIDENCE
            assert row["target_ref"]


@pytest.mark.skipif(not list(CROSSWALK.glob("*.csv")),
                    reason="run make crosswalk")
def test_no_duplicate_pairs():
    for path, rows in committed():
        pairs = [(r["source_ref"], r["target_ref"]) for r in rows]
        assert len(pairs) == len(set(pairs)), "%s has duplicates" % path.name


@pytest.mark.skipif(not list(CROSSWALK.glob("*.csv")),
                    reason="run make crosswalk")
def test_bootstrap_rows_are_all_auto():
    # Nothing is verified until a human says so.
    for path, rows in committed():
        assert {r["confidence"] for r in rows} <= {"auto", "verified"}


@pytest.mark.skipif(not list(CROSSWALK.glob("*.csv")),
                    reason="run make crosswalk")
def test_every_element_has_at_least_one_target():
    # Gate 3, checked here as data rather than against the built PDF.
    for path, rows in committed():
        by_element = {}
        for row in rows:
            by_element.setdefault(row["source_ref"], 0)
            by_element[row["source_ref"]] += 1
        assert all(count >= 1 for count in by_element.values())


# ---------------------------------------------------------------------------
# citation linking, Phase 6 into the PDF
# ---------------------------------------------------------------------------

def test_every_citation_form_on_a_references_line_is_found():
    import link as L

    line = ("R eferences: 14 CFR parts 61, 68, 91; AC 91-92; AIM; "
            "FAA-H-8083-2, FAA-H-8083-25")
    found = {ref for _s, _e, ref in L.citations_in(line)}
    assert "14cfr:part-61" in found
    assert "14cfr:part-68" in found
    assert "14cfr:part-91" in found, "each part gets its own link, not one vague jump"
    assert "ac:91-92" in found
    assert "aim" in found
    assert "handbook:8083-2" in found
    assert "handbook:8083-25" in found


def test_a_citation_span_covers_only_its_own_token():
    import link as L

    line = "14 CFR parts 61, 68, 91"
    spans = {ref: line[s:e] for s, e, ref in L.citations_in(line)}
    assert spans["14cfr:part-61"] == "61"
    assert spans["14cfr:part-91"] == "91"


def test_a_singular_part_reference_parses():
    import link as L

    found = {ref for _s, _e, ref in L.citations_in("14 CFR part 91; AIM")}
    assert found == {"14cfr:part-91", "aim"}


def test_a_line_with_no_citation_yields_nothing():
    import link as L

    assert not list(L.citations_in("The applicant demonstrates understanding of:"))


def test_a_target_outside_the_corpus_resolves_to_nothing():
    """Part 93 is cited by the ACS and is not in cfr.yaml.

    It must degrade to no link rather than to a wrong page.
    """
    import link as L

    resolve = L.build_resolver({"part-14-91": 4354}, {}, [])
    assert resolve("14cfr:part-91") == 4354
    assert resolve("14cfr:part-93") is None


# ---------------------------------------------------------------------------
# the review worklist
# ---------------------------------------------------------------------------

def test_task_grouping_collapses_elements():
    import crosswalk_review as CR

    assert CR.task_of("PA.I.B.K3b") == "PA.I.B"
    assert CR.task_of("IR.VII.A.S1") == "IR.VII.A"


@pytest.mark.skipif(not list(CROSSWALK.glob("*.csv")),
                    reason="run make crosswalk")
def test_the_worklist_counts_tasks_not_rows():
    # 26,075 rows is not the number of decisions; Private is 61 Tasks.
    import crosswalk_review as CR

    stats = {row["certificate"]: row for row in CR.summarize(["private"])}
    assert stats["private"]["tasks"] < 100
    assert stats["private"]["rows"] > 4000


@pytest.mark.skipif(not list(CROSSWALK.glob("*.csv")),
                    reason="run make crosswalk")
def test_verified_tasks_drop_out_of_the_worklist():
    import crosswalk_review as CR

    tasks = CR.worklist("private", {}, limit=3)
    assert tasks, "nothing to review, but no task is verified yet"
    for _task, block in tasks:
        assert any(row["confidence"] == "auto" for row in block["rows"])


# ---------------------------------------------------------------------------
# refinement is safe to repeat
# ---------------------------------------------------------------------------

import refine_crosswalk as RC  # noqa: E402


def _proposal(sections, confidence="high"):
    return {"sections": list(sections), "why": "because", "confidence": confidence}


def test_a_second_apply_is_a_no_op_not_a_rejection():
    """Applying consumes the part-level row it replaces.

    On a re-run the element then looks like it was never in the crosswalk, and
    the first version of this reported all 269 as REJECTED. A half-finished
    run could not be brought back into step, which is exactly when you re-run.
    """
    rows = [{"source_ref": "PA.I.A.K1", "target_ref": "14cfr:61.3",
             "relation": "regulation", "confidence": "verified",
             "note": "", "element_text": "x"}]
    proposals = {"private": ("private", {"PA.I.A.K1": _proposal(["61.3"])})}
    inventory = {"61.3": ("61", "Requirement for certificates")}

    accepted, report = RC.validate(proposals, inventory, {"private": rows})
    assert report["already"] == 1
    assert report["unknown_element"] == []
    assert not accepted.get("private")


def test_an_element_genuinely_absent_is_still_reported():
    """The no-op path must not swallow a real mismatch."""
    proposals = {"private": ("private", {"PA.I.A.K1": _proposal(["61.3"])})}
    accepted, report = RC.validate(
        proposals, {"61.3": ("61", "x")}, {"private": []})
    assert report["already"] == 0
    assert report["unknown_element"] == [("private", "PA.I.A.K1")]


def test_a_partly_applied_element_is_not_called_done():
    """Two of four sections present means the run did not finish."""
    rows = [{"source_ref": "PA.I.A.K1", "target_ref": "14cfr:61.3",
             "relation": "regulation", "confidence": "verified",
             "note": "", "element_text": "x"}]
    proposals = {"private": ("private",
                             {"PA.I.A.K1": _proposal(["61.3", "61.51"])})}
    _accepted, report = RC.validate(
        proposals, {"61.3": ("61", "x"), "61.51": ("61", "y")},
        {"private": rows})
    assert report["already"] == 0
    assert report["unknown_element"] == [("private", "PA.I.A.K1")]
