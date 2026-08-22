"""Fonts are build inputs, so rule 8 governs them.

A build-time fetch or a system install means the binary differs between
machines, subsetting yields different bytes, and the PDF hash changes with no
content change. These tests are the gate on that.

See CLAUDE.md section 6.
"""

import hashlib
import json
import pathlib
import re
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[1]
FONTS = ROOT / "theme" / "fonts"

EXPECTED_FACE_COUNT = 7


def theme():
    with open(ROOT / "theme" / "theme.toml", "rb") as fh:
        return tomllib.load(fh)


def lock():
    with open(FONTS / "fonts.lock.json", encoding="utf-8") as fh:
        return json.load(fh)


def declared_faces():
    return theme()["font"]["face"]


def locked_faces_by_file():
    out = {}
    for family in lock()["families"].values():
        for face in family["faces"]:
            out[face["file"]] = face
    return out


def test_theme_declares_the_expected_faces():
    assert len(declared_faces()) == EXPECTED_FACE_COUNT


def test_every_declared_face_is_present_and_hashes_match():
    locked = locked_faces_by_file()
    for face in declared_faces():
        name = face["file"]
        path = FONTS / name
        assert path.is_file(), f"declared face is not vendored: {name}"
        assert name in locked, f"{name} is not recorded in fonts.lock.json"

        record = locked[name]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == record["sha256"], f"sha256 mismatch for {name}"
        assert path.stat().st_size == record["bytes"], f"size mismatch for {name}"
        assert face["weight"] == record["weight"], f"weight mismatch for {name}"
        assert face["style"] == record["style"], f"style mismatch for {name}"


def test_lock_records_nothing_that_is_not_declared():
    declared = {face["file"] for face in declared_faces()}
    assert set(locked_faces_by_file()) == declared


def test_a_real_italic_is_vendored():
    # eCFR XML uses <I> for citations and defined terms. Phase 2 needs a real
    # italic rather than a synthesized oblique.
    assert any(face["style"] == "italic" for face in declared_faces())


def test_no_variable_font_is_vendored():
    # Inter's variable font subsets unpredictably through Typst into PDF.
    found = [p.name for p in FONTS.glob("*.ttf") if "variable" in p.name.lower()]
    assert not found, f"variable fonts must not be vendored: {found}"


def test_every_family_vendors_its_license():
    for name, family in lock()["families"].items():
        path = FONTS / family["license"]["file"]
        assert path.is_file(), f"missing OFL text for {name}"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == family["license"]["sha256"], f"OFL changed for {name}"


def test_lock_records_provenance_for_every_family():
    # Enough to re-derive each file without guessing a URL.
    for name, family in lock()["families"].items():
        source = family["source"]
        for key in ("repo", "tag", "asset", "asset_sha256", "url"):
            assert source.get(key), f"{name} source is missing {key}"
        for face in family["faces"]:
            assert face.get("member"), f"{face['file']} is missing its member path"


FONT_FETCH = re.compile(
    r"fonts\.googleapis\.com"
    r"|fonts\.gstatic\.com"
    r"|https?://\S+\.(?:ttf|otf|woff2?)\b",
    re.IGNORECASE,
)


def test_vendor_tool_check_mode_agrees():
    # The tool that produced the lock must also validate it, offline.
    import subprocess
    import sys as _sys

    result = subprocess.run(
        [_sys.executable, "tools/vendor_fonts.py", "--check"],
        cwd=ROOT, capture_output=True,
    )
    assert result.returncode == 0, result.stdout.decode("utf-8", "replace")


# tools/vendor_fonts.py is the one place allowed to reach upstream. It is a
# one-time vendoring tool, deliberately not part of any build target.
VENDORING_TOOL = "vendor_fonts.py"


def test_no_font_is_fetched_at_build_time():
    offenders = []
    for directory in ("templates", "tools"):
        base = ROOT / directory
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in (".typ", ".py"):
                continue
            if path.name == VENDORING_TOOL:
                continue
            if FONT_FETCH.search(path.read_text(encoding="utf-8")):
                offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"fonts must never be fetched at build time: {offenders}"


def test_vendoring_tool_is_not_wired_into_any_build_target():
    # make fonts is a manual escape hatch. Nothing in the build may depend on it.
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    recipes = [line for line in makefile.splitlines() if line.startswith("\t")]
    wired = [r for r in recipes if VENDORING_TOOL in r and "--check" not in r]
    assert len(wired) == 1, (
        "vendor_fonts.py without --check should appear in exactly one recipe, "
        f"the manual `fonts` target. Found: {wired}"
    )
