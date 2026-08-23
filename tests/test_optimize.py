"""Downsampling must shrink the corpus without breaking rule 8.

The compression ratio is the easy part. The properties worth testing are that
output is byte-reproducible, that sources are never touched, and that effort is
never spent for no gain.
"""

import hashlib
import io
import re
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import _manifest as M  # noqa: E402
import optimize as O  # noqa: E402


def image_pdf(width=1600, height=1200, pages=1):
    """A PDF carrying an image far denser than 150 dpi on a letter page."""
    import pymupdf

    document = pymupdf.open()
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, width, height))
    # A gradient compresses poorly enough to be worth resampling.
    for x in range(0, width, 4):
        for y in range(0, height, 4):
            pixmap.set_pixel(x, y, ((x * 7) % 256, (y * 5) % 256, (x + y) % 256))
    for _ in range(pages):
        page = document.new_page()
        page.insert_image(page.rect, pixmap=pixmap)
    data = document.tobytes()
    document.close()
    return data


@pytest.fixture(scope="module")
def sample():
    return image_pdf()


# ---------------------------------------------------------------------------
# rule 8
# ---------------------------------------------------------------------------

def test_recompression_is_byte_reproducible(sample):
    first = O.recompress(sample, "a" * 64)
    second = O.recompress(sample, "a" * 64)
    assert hashlib.sha256(first).hexdigest() == hashlib.sha256(second).hexdigest(), (
        "identical input must produce identical bytes; PyMuPDF writes a random "
        "trailer /ID unless it is pinned")


def test_pin_id_is_length_preserving(sample):
    raw = O.recompress(sample, "a" * 64)
    assert len(O.pin_id(raw, "seed")) == len(raw), (
        "changing /ID length would move every cross-reference offset")


def test_pin_id_handles_a_literal_string_id():
    """The intermittent rule 8 failure this exists to prevent.

    Per the PDF spec the second /ID element is the changing identifier, and
    MuPDF regenerates it on every write. When those random bytes happen to be
    mostly printable it emits a literal string, (...), rather than hex. About
    one save in twenty. A hex-only pattern matched nothing on exactly those
    runs, the random ID survived, and an otherwise byte-identical rebuild
    differed. Intermittent, so it passed 19 times out of 20.
    """
    trailer = (
        b"trailer\n<</Size 8/Root 1 0 R/ID[<" + b"A" * 32
        + rb'>(K\f@=MQA\250\276L,)]>>' + b"\nstartxref\n0\n%%EOF\n")
    pinned = O.pin_id(trailer, "seed")
    halves = re.search(rb"/ID\s*\[\s*<([0-9A-Fa-f]{32})>\s*<([0-9A-Fa-f]{32})>\s*\]",
                       pinned)
    assert halves, "a literal-string /ID must still be pinned: %r" % pinned[:120]
    assert halves.group(1) == halves.group(2)


def test_recompression_is_reproducible_across_many_runs(sample):
    # One run proves nothing when the failure rate is one in twenty.
    digests = {hashlib.sha256(O.recompress(sample, "a" * 64)).hexdigest()
               for _ in range(25)}
    assert len(digests) == 1, "recompression must not vary between runs"


def test_pin_id_collapses_two_differing_ids():
    trailer = (b"trailer\n<</Size 9/ID[<" + b"A" * 32 + b"><" + b"B" * 32
               + b">]>>\nstartxref\n0\n%%EOF\n")
    pinned = O.pin_id(trailer, "seed")
    import re
    halves = re.search(rb"/ID\s*\[\s*<([0-9A-Fa-f]{32})>\s*<([0-9A-Fa-f]{32})>",
                       pinned)
    assert halves.group(1) == halves.group(2)


def test_pinned_id_derives_from_the_source_hash(sample):
    raw = O.recompress(sample, "a" * 64)
    other = O.recompress(sample, "b" * 64)
    assert raw != other, "a different source hash must yield a different /ID"


def test_output_is_still_a_readable_pdf(sample):
    import pymupdf

    out = O.recompress(sample, "a" * 64)
    assert out[:5] == b"%PDF-"
    document = pymupdf.open(stream=out, filetype="pdf")
    try:
        assert document.page_count == 1
    finally:
        document.close()


# ---------------------------------------------------------------------------
# selection policy
# ---------------------------------------------------------------------------

def test_density_is_megabytes_per_page():
    assert O.density({"bytes": 10 * 1048576, "pages": 10}) == pytest.approx(1.0)
    assert O.density({"bytes": 1048576, "pages": 0}) == 0.0
    assert O.density({"bytes": 1048576}) == 0.0


def test_candidates_selects_only_documents_above_the_threshold():
    lock = {
        "dense": {"bytes": int(1.0 * 1048576), "pages": 1},
        "sparse": {"bytes": int(0.01 * 1048576), "pages": 1},
        "borderline": {"bytes": int(O.DENSITY_THRESHOLD * 1048576), "pages": 1},
    }
    assert O.candidates(lock) == ["dense"]


def test_threshold_is_well_above_the_corpus_median():
    # Guards against a future edit quietly recompressing the whole corpus.
    assert O.DENSITY_THRESHOLD >= 0.2


# ---------------------------------------------------------------------------
# never pay for nothing, never touch sources
# ---------------------------------------------------------------------------

def test_a_result_that_does_not_shrink_is_discarded(tmp_path, monkeypatch):
    lock_path = tmp_path / "sources.lock.yaml"
    cache = tmp_path / "sources"
    out_root = tmp_path / "optimized"
    opt_lock = tmp_path / "optimize.lock.yaml"
    cache.mkdir()

    payload = image_pdf()
    digest = hashlib.sha256(payload).hexdigest()
    (cache / ("%s.pdf" % digest)).write_bytes(payload)
    M.dump_lock({"dense": {"sha256": digest, "bytes": 100 * 1048576,
                           "pages": 1, "resolved_url": "https://x/y.pdf"}},
                lock_path)

    # Pretend recompression achieved nothing.
    monkeypatch.setattr(O, "recompress", lambda data, sha: data + b"padding")

    out = io.StringIO()
    code = O.run([], lock_path=lock_path, cache_root=cache, out_root=out_root,
                 optimize_lock=opt_lock, out=out)
    assert code == 0
    assert "discarded" in out.getvalue()
    assert not list(out_root.glob("*.pdf")), "a useless result must not be kept"


def test_optimize_never_modifies_the_source_blob(tmp_path):
    lock_path = tmp_path / "sources.lock.yaml"
    cache = tmp_path / "sources"
    cache.mkdir()

    payload = image_pdf()
    digest = hashlib.sha256(payload).hexdigest()
    source = cache / ("%s.pdf" % digest)
    source.write_bytes(payload)
    M.dump_lock({"dense": {"sha256": digest, "bytes": 100 * 1048576,
                           "pages": 1, "resolved_url": "https://x/y.pdf"}},
                lock_path)

    O.run([], lock_path=lock_path, cache_root=cache,
          out_root=tmp_path / "optimized",
          optimize_lock=tmp_path / "optimize.lock.yaml", out=io.StringIO())

    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest, (
        "cache/sources is the drift signal and must never be rewritten")


def test_check_detects_a_corrupted_optimized_artifact(tmp_path):
    lock_path = tmp_path / "sources.lock.yaml"
    cache = tmp_path / "sources"
    out_root = tmp_path / "optimized"
    opt_lock = tmp_path / "optimize.lock.yaml"
    cache.mkdir()

    payload = image_pdf()
    digest = hashlib.sha256(payload).hexdigest()
    (cache / ("%s.pdf" % digest)).write_bytes(payload)
    M.dump_lock({"dense": {"sha256": digest, "bytes": 100 * 1048576,
                           "pages": 1, "resolved_url": "https://x/y.pdf"}},
                lock_path)

    O.run([], lock_path=lock_path, cache_root=cache, out_root=out_root,
          optimize_lock=opt_lock, out=io.StringIO())
    produced = list(out_root.glob("*.pdf"))
    assert produced, "the sample should have compressed enough to be kept"
    produced[0].write_bytes(b"%PDF-1.7 rotted")

    out = io.StringIO()
    code = O.run(["--check"], lock_path=lock_path, cache_root=cache,
                 out_root=out_root, optimize_lock=opt_lock, out=out)
    assert code == 1
    assert "lock says" in out.getvalue()


# ---------------------------------------------------------------------------
# the committed result
# ---------------------------------------------------------------------------

def test_committed_optimize_lock_stays_under_the_hard_fail():
    recorded = O.load_optimize_lock()
    if not recorded:
        pytest.skip("optimize has not been run in this checkout")
    lock = M.load_lock()
    total = sum(entry.get("bytes", 0) for entry in lock.values())
    saved = sum(r["source_bytes"] - r["output_bytes"] for r in recorded.values())
    assert (total - saved) < 500 * 1048576, "corpus must fit the hard fail"
