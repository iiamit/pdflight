"""Phase 4, the generated pages.

Cover, main menu, per-document menus, colophon. These are the only pages
PDFlight writes itself, so they carry the whole theme, and validation gate 4
says every manifest document must be reachable from a main menu page.
"""

import pathlib
import re
import sys
import tomllib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import _manifest as M  # noqa: E402
import menus  # noqa: E402

TEMPLATES = ROOT / "templates"


# ---------------------------------------------------------------------------
# theme tokens must not drift between the two templates
# ---------------------------------------------------------------------------

def theme_tokens():
    with open(ROOT / "theme" / "theme.toml", "rb") as handle:
        return tomllib.load(handle)["color"]


@pytest.mark.parametrize("template", ["cfr.typ", "menu.typ"])
def test_template_colours_match_theme_toml(template):
    """cfr.typ and menu.typ each declare their own tokens.

    Typst import paths do not survive the generated files being written to
    build/, so the tokens are duplicated on purpose. This is the guard that
    keeps them honest against theme/theme.toml, which mirrors the site CSS.
    """
    text = (TEMPLATES / template).read_text(encoding="utf-8")
    declared = dict(re.findall(r'#let ([\w-]+) = rgb\("(#[0-9A-Fa-f]{6})"\)', text))
    tokens = theme_tokens()
    for name, value in declared.items():
        key = name.replace("-", "_")
        if key in tokens:
            assert value.upper() == tokens[key][:7].upper(), (
                "%s declares %s as %s, theme.toml says %s"
                % (template, name, value, tokens[key]))


def test_amber_is_not_used_for_body_text():
    # Section 6: amber is for actions and live signals only.
    text = (TEMPLATES / "menu.typ").read_text(encoding="utf-8")
    body = re.search(r"set text\(font: sans[^)]*\)", text).group(0)
    assert "signal" not in body, "body text must be ink, never amber"


# ---------------------------------------------------------------------------
# menu structure
# ---------------------------------------------------------------------------

def test_every_manifest_section_has_a_menu_home():
    """A section with no menu entry means unreachable documents.

    CLAUDE.md section 6 lists six menu sections and omits `aim`, which is a
    first-class value in the manifest schema. That gap is why SECTIONS here
    carries seven.
    """
    covered = {key for _n, key, _name in menus.SECTIONS}
    used = {entry["section"] for entry in M.load_sources()}
    assert used <= covered, "sections with no menu home: %s" % (used - covered)


def test_aim_has_its_own_section():
    keys = [key for _n, key, _name in menus.SECTIONS]
    assert "aim" in keys


def test_section_numbers_are_unique_and_ordered():
    numbers = [n for n, _k, _name in menus.SECTIONS]
    assert numbers == sorted(numbers)
    assert len(numbers) == len(set(numbers))


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def test_version_is_derived_from_content_not_the_clock():
    # Rule 8. Two calls with the same lock must agree, and the value must come
    # from the amendment date rather than today.
    lock = {"title-14-part-91": {"amended_on": "2026-08-17"}}
    assert menus.version_from(lock) == "v2026.08.1"
    assert menus.version_from(lock) == menus.version_from(dict(lock))


def test_version_survives_an_empty_lock():
    assert menus.version_from({}) == "v0.0.0"


def test_typst_strings_are_escaped():
    assert menus.typst_string('a "quoted" \\ path') == 'a \\"quoted\\" \\\\ path'


def test_document_labels_are_typst_safe():
    # Addendum ids contain dots, which are not valid in a Typst label.
    assert menus.label_for_doc("phak.addendum.0") == "docmenu-phak-addendum-0"


def test_chips_come_from_the_lock():
    entry = {"id": "phak"}
    lock = {"phak": {"faa_number": "FAA-H-8083-25C", "pages": 522,
                     "revision_date": "May 2024"},
            "phak.addendum.0": {"pages": 5}}
    chips = menus.chips_for(entry, lock)
    assert "FAA-H-8083-25C" in chips
    assert "522 pp" in chips
    assert "1 addendum" in chips


def test_chips_tolerate_a_bare_lock_entry():
    assert menus.chips_for({"id": "x"}, {"x": {}}) == []


def sample():
    entries = [
        {"id": "phak", "title": "Pilot's Handbook", "section": "handbooks",
         "order": 1, "landing_url": "https://www.faa.gov/phak"},
        {"id": "aim", "title": "Aeronautical Information Manual",
         "section": "aim", "order": 1, "landing_url": "https://www.faa.gov/aim"},
    ]
    lock = {"phak": {"pages": 522, "sha256": "a" * 64,
                     "faa_number": "FAA-H-8083-25C"},
            "aim": {"pages": 918, "sha256": "b" * 64}}
    cfr = {"title-14-part-91": {"amended_on": "2026-08-17"}}
    return entries, lock, cfr


def test_render_reaches_every_document():
    entries, lock, cfr = sample()
    body = menus.render(entries, lock, cfr, 629)
    for entry in entries:
        assert "<%s>" % menus.label_for_doc(entry["id"]) in body


def test_render_emits_the_required_destinations():
    entries, lock, cfr = sample()
    body = menus.render(entries, lock, cfr, 629)
    for required in ("<cover>", "<menu-main>", "<colophon>"):
        assert required in body


def test_render_is_deterministic():
    entries, lock, cfr = sample()
    assert menus.render(entries, lock, cfr, 629) == \
        menus.render(entries, lock, cfr, 629)


def test_regulations_appear_in_their_numbered_slot():
    """The regulations have no manifest entries, being generated from eCFR.

    They were previously appended after everything else as a hardcoded "08",
    which put Regulations after Advisory Circulars and out of sequence.
    """
    entries, lock, cfr = sample()
    body = menus.render(entries, lock, cfr, 629)
    regs = next(n for n, k, _ in menus.SECTIONS if k == "regs")
    assert '#section-label("%s", "Regulations")' % regs in body
    assert '"08"' not in body


# ---------------------------------------------------------------------------
# the built artefact
# ---------------------------------------------------------------------------

BUILT = ROOT / "build" / "menus" / "menus.pdf"


@pytest.mark.skipif(not BUILT.is_file(), reason="run make menus")
def test_built_pdf_reaches_every_manifest_document():
    import pymupdf

    document = pymupdf.open(BUILT)
    names = set(document.resolve_names())
    document.close()
    missing = [e["id"] for e in M.load_sources()
               if menus.label_for_doc(e["id"]) not in names]
    assert not missing, "unreachable from a menu: %s" % missing


@pytest.mark.skipif(not BUILT.is_file(), reason="run make menus")
def test_main_menu_fits_the_page_budget():
    import pymupdf

    document = pymupdf.open(BUILT)
    names = document.resolve_names()
    first_doc = min(names[menus.label_for_doc(e["id"])]["page"]
                    for e in M.load_sources()
                    if menus.label_for_doc(e["id"]) in names)
    document.close()
    used = first_doc - names["menu-main"]["page"]
    assert used <= menus.MENU_PAGES, (
        "main menu takes %d pages, spec allows %d" % (used, menus.MENU_PAGES))


# ---------------------------------------------------------------------------
# the target palette lives in two places and must not drift
# ---------------------------------------------------------------------------

def test_the_typst_palette_matches_the_button_palette():
    """Buttons are drawn by PyMuPDF, chips by Typst, from separate constants.

    A reader sees both on the same lookup: an amber chip on the crosswalk page
    beside a green button on the ACS page would read as two different kinds of
    link. CLAUDE.md section 6 reserves amber for actions, so this palette is a
    deliberate widening and is pinned here rather than left to drift.
    """
    import re

    import link as L

    source = (ROOT / "templates" / "menu.typ").read_text(encoding="utf-8")
    declared = dict(re.findall(r'#let tint-(\w+) = rgb\("(#[0-9A-Fa-f]{6})"\)',
                               source))
    assert declared, "no tint- tokens found in menu.typ"

    for kind, rgb in L.TARGET_KIND:
        assert kind in declared, "menu.typ has no colour for %s" % kind
        hexed = "#%02X%02X%02X" % tuple(int(round(c * 255)) for c in rgb)
        assert declared[kind].upper() == hexed, (
            "%s is %s in menu.typ and %s in link.py"
            % (kind, declared[kind], hexed))


def test_every_target_kind_has_a_colour():
    import link as L

    kinds = {kind for kind, _rgb in L.TARGET_KIND}
    for ref in ("14cfr:91.119", "49cfr:830.5", "phak:ch15", "aim:ch03-s02",
                "ac-91-92", "risk-management:ch02"):
        assert L.target_kind(ref) in kinds
        assert L.color_for_ref(ref) is not None
