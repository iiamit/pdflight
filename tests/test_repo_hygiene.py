"""Rule 9: never commit source PDFs or the output PDF.

GitHub rejects files over 100 MB in-repo. Sources live in cache/ and the Actions
cache; output goes to Releases.

These read the git index, so a file is covered as soon as it is staged.
"""

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
GITHUB_FILE_LIMIT = 100 * 1024 * 1024


def tracked():
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT, capture_output=True, check=True,
    )
    return [p for p in result.stdout.decode("utf-8").split("\0") if p]


def test_no_pdf_is_tracked():
    pdfs = [p for p in tracked() if p.lower().endswith(".pdf")]
    assert not pdfs, f"PDFs must never be committed: {pdfs}"


def test_no_tracked_file_exceeds_the_github_limit():
    oversized = []
    for rel in tracked():
        path = ROOT / rel
        if path.is_file() and path.stat().st_size > GITHUB_FILE_LIMIT:
            oversized.append((rel, path.stat().st_size))
    assert not oversized, f"over the 100 MB limit: {oversized}"


def test_generated_and_fetched_directories_are_ignored():
    for directory in ("cache", "state", "build"):
        result = subprocess.run(
            ["git", "check-ignore", "-q", f"{directory}/probe"], cwd=ROOT,
        )
        assert result.returncode == 0, f"{directory}/ must be gitignored"


def test_vendored_fonts_are_not_ignored():
    # The *.pdf rule must never grow into something that drops build inputs.
    for name in ("Inter-Regular.ttf", "OFL-Inter.txt", "fonts.lock.json"):
        result = subprocess.run(
            ["git", "check-ignore", "-q", f"theme/fonts/{name}"], cwd=ROOT,
        )
        assert result.returncode == 1, f"theme/fonts/{name} must stay tracked"


def test_hashed_build_inputs_are_exempt_from_eol_conversion():
    """Guards the defect a fresh clone caught.

    core.autocrlf rewrites LF to CRLF at checkout on Windows. That changes the
    bytes of the vendored OFL texts, so their sha256 no longer matches
    fonts.lock.json, and the font test fails on Windows while passing on
    ubuntu-latest. theme/fonts/** must be marked -text so git leaves it alone.
    """
    for name in ("OFL-Inter.txt", "OFL-JetBrainsMono.txt", "Inter-Regular.ttf"):
        result = subprocess.run(
            ["git", "check-attr", "text", "--", f"theme/fonts/{name}"],
            cwd=ROOT, capture_output=True, check=True,
        )
        value = result.stdout.decode("utf-8").strip().rsplit(":", 1)[-1].strip()
        assert value == "unset", (
            f"theme/fonts/{name} has text={value}, expected unset. "
            "Hashed build inputs must never be line-ending converted."
        )
