"""Deliverable 1.3 acceptance, plus the paths that make the lock trustworthy.

The three named acceptance criteria from CLAUDE.md 4.3 are the tests marked
ACCEPTANCE below. Everything else guards a specific rule.
"""

import hashlib
import io
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import _manifest as M  # noqa: E402
import fetch  # noqa: E402
from conftest import make_pdf  # noqa: E402

URL = "https://www.faa.gov/sites/faa.gov/files/pilot_handbook.pdf"
LANDING = "https://www.faa.gov/regulations_policies/handbooks_manuals/phak"

ENTRY = {
    "id": "phak",
    "title": "Pilot's Handbook of Aeronautical Knowledge",
    "landing_url": LANDING,
    "url": URL,
    "section": "handbooks",
    "order": 1,
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(argv, workspace, client_factory, out=None):
    out = out or io.StringIO()
    code = fetch.run(
        argv,
        client_factory=client_factory,
        sources_path=workspace["sources"],
        lock_path=workspace["lock"],
        state_path=workspace["state"],
        cache_root=workspace["cache"],
        index_path=workspace["index"],
        out=out,
    )
    return code, out.getvalue()


@pytest.fixture
def seeded(workspace, write_sources, transport, client_factory, pdf_bytes):
    """A workspace with one source already fetched and locked."""
    write_sources([ENTRY])
    transport.add(URL, body=pdf_bytes, etag='"v1"',
                  headers={"Content-Type": "application/pdf"}, times=1)
    code, _ = run(["--update"], workspace, client_factory)
    assert code == 0
    transport.calls.clear()
    return workspace


# ---------------------------------------------------------------------------
# ACCEPTANCE
# ---------------------------------------------------------------------------

def test_acceptance_warm_cache_fetch_makes_zero_network_calls(
        seeded, transport, client_factory):
    code, output = run([], seeded, client_factory)
    assert code == 0
    assert transport.request_count == 0, (
        "warm-cache fetch must be fully offline, saw %d request(s)"
        % transport.request_count)
    assert "No network" in output


def test_acceptance_check_reports_drift_on_a_corrupted_lock_hash(
        seeded, transport, client_factory):
    lock = M.load_lock(seeded["lock"])
    lock["phak"]["sha256"] = "0" * 64
    M.dump_lock(lock, seeded["lock"])

    code, output = run(["--check"], seeded, client_factory)
    assert code == 1
    assert "Drift detected" in output
    # Assert the reason, not just the exit code. The cache path is derived from
    # the locked hash, so a corrupted lock makes the blob unfindable; that is
    # the branch this exercises. On-disk corruption is a different branch and
    # has its own test below.
    assert "locked blob is not in the cache" in output
    # Caught locally. A corrupted hash needs no network to detect.
    assert transport.request_count == 0


def test_check_detects_on_disk_cache_corruption(
        seeded, transport, client_factory):
    """The integrity branch: file named correctly, contents rotted."""
    locked = M.load_lock(seeded["lock"])["phak"]
    blob = M.cache_path(locked["sha256"], seeded["cache"])
    assert blob.is_file()
    blob.write_bytes(b"%PDF-1.7 corrupted on disk")

    code, output = run(["--check"], seeded, client_factory)
    assert code == 1
    assert "does not match its locked sha256" in output or \
           "cached blob" in output
    assert transport.request_count == 0


def test_fetch_refuses_a_corrupted_cache_rather_than_trusting_it(
        seeded, transport, client_factory):
    locked = M.load_lock(seeded["lock"])["phak"]
    M.cache_path(locked["sha256"], seeded["cache"]).write_bytes(b"rotted")

    code, output = run([], seeded, client_factory)
    assert code == 1
    assert "does not match its locked sha256" in output


def test_acceptance_check_reports_no_drift_when_nothing_changed(
        seeded, transport, client_factory):
    code, output = run(["--check"], seeded, client_factory)
    assert code == 0, output
    assert "No drift" in output


def test_acceptance_two_consecutive_checks_leave_the_lock_untouched(
        seeded, transport, client_factory):
    before = pathlib.Path(seeded["lock"]).read_bytes()
    run(["--check"], seeded, client_factory)
    after_one = pathlib.Path(seeded["lock"]).read_bytes()
    run(["--check"], seeded, client_factory)
    after_two = pathlib.Path(seeded["lock"]).read_bytes()

    assert before == after_one == after_two, (
        "fetch-check must never write the lock; a diff there is the release "
        "signal")


# ---------------------------------------------------------------------------
# the lock is only trustworthy if these hold
# ---------------------------------------------------------------------------

def test_lock_serialization_is_byte_stable(tmp_path):
    entry = {
        "resolved_url": URL, "sha256": "a" * 64, "bytes": 10, "pages": 3,
        "content_type": "application/pdf", "faa_number": "FAA-H-8083-25C",
        "faa_number_source": "firstpage", "revision_date": None,
        "fetched_at": "2026-08-22T00:00:00Z",
    }
    first, second = tmp_path / "a.yaml", tmp_path / "b.yaml"
    M.dump_lock({"phak": entry}, first)
    M.dump_lock({"phak": dict(entry)}, second)
    assert first.read_bytes() == second.read_bytes()


def test_fetched_at_survives_an_unchanged_sha256():
    previous = {"sha256": "a" * 64, "fetched_at": "2026-01-01T00:00:00Z"}
    fresh = {"sha256": "a" * 64, "fetched_at": "2026-08-22T00:00:00Z"}
    merged = M.merge_lock_entry(previous, fresh)
    assert merged["fetched_at"] == "2026-01-01T00:00:00Z", (
        "a timestamp that ticks every run turns every check into false drift")


def test_fetched_at_moves_when_sha256_changes():
    previous = {"sha256": "a" * 64, "fetched_at": "2026-01-01T00:00:00Z"}
    fresh = {"sha256": "b" * 64, "fetched_at": "2026-08-22T00:00:00Z"}
    merged = M.merge_lock_entry(previous, fresh)
    assert merged["fetched_at"] == "2026-08-22T00:00:00Z"


def test_update_is_idempotent_when_upstream_is_unchanged(
        seeded, transport, client_factory, pdf_bytes):
    before = pathlib.Path(seeded["lock"]).read_bytes()
    transport.add(URL, body=pdf_bytes, etag='"v1"',
                  headers={"Content-Type": "application/pdf"}, times=1)
    code, output = run(["--update"], seeded, client_factory)
    assert code == 0
    assert pathlib.Path(seeded["lock"]).read_bytes() == before, (
        "an unchanged source must produce an empty lock diff")


def test_a_changed_source_moves_the_locked_hash(
        seeded, transport, client_factory):
    changed = make_pdf(lines=("FAA-H-8083-25D", "Revised"))
    transport.routes.clear()
    transport.add(URL, body=changed,
                  headers={"Content-Type": "application/pdf"}, times=1)

    code, output = run(["--update"], seeded, client_factory)
    assert code == 0
    assert "CHANGED" in output
    assert M.load_lock(seeded["lock"])["phak"]["sha256"] == sha(changed)


# ---------------------------------------------------------------------------
# rule 1: never substitute a URL
# ---------------------------------------------------------------------------

LANDING_HTML = b"""
<html><body>
  <a href="/files/phak_ch01.pdf">Chapter 1, Introduction</a>
  <a href="https://www.faa.gov/files/phak_full.pdf">Full handbook</a>
  <a href="/files/notes.txt">Not a PDF</a>
  <a href="/files/phak_ch01.pdf">Duplicate link</a>
</body></html>
"""


def test_404_reports_candidates_and_never_substitutes(
        workspace, write_sources, transport, client_factory):
    write_sources([ENTRY])
    transport.add(URL, status=404, times=1)
    transport.add(LANDING, body=LANDING_HTML,
                  headers={"Content-Type": "text/html"}, times=1)
    transport.add("https://www.faa.gov/files/phak_ch01.pdf",
                  headers={"Content-Length": "1234"}, times=1)
    transport.add("https://www.faa.gov/files/phak_full.pdf",
                  headers={"Content-Length": "5678"}, times=1)

    code, output = run(["--update"], workspace, client_factory)

    assert code == 1
    assert "returned 404" in output
    assert "phak_ch01.pdf" in output and "phak_full.pdf" in output
    assert "notes.txt" not in output
    assert "Pick one by hand" in output
    # The manifest and the lock are untouched. Nothing was chosen.
    assert M.load_lock(workspace["lock"]) == {}
    assert "url: %s" % URL in pathlib.Path(workspace["sources"]).read_text(
        encoding="utf-8")


def test_candidate_links_are_deduplicated_and_absolute(
        workspace, write_sources, transport, client_factory):
    write_sources([ENTRY])
    transport.add(URL, status=404, times=1)
    transport.add(LANDING, body=LANDING_HTML, times=1)
    transport.add("https://www.faa.gov/files/phak_ch01.pdf", times=1)
    transport.add("https://www.faa.gov/files/phak_full.pdf", times=1)

    _, output = run(["--update"], workspace, client_factory)
    assert "2 candidate(s)" in output
    assert output.count("https://www.faa.gov/files/phak_ch01.pdf") == 1


# ---------------------------------------------------------------------------
# rule: magic bytes are the gate, not content type
# ---------------------------------------------------------------------------

def test_html_served_as_application_pdf_is_rejected(
        workspace, write_sources, transport, client_factory):
    write_sources([ENTRY])
    transport.add(URL, body=b"<html>Not a PDF</html>",
                  headers={"Content-Type": "application/pdf"}, times=1)

    code, output = run(["--update"], workspace, client_factory)
    assert code == 1
    assert "not a PDF" in output
    assert M.load_lock(workspace["lock"]) == {}


def test_pdf_served_as_octet_stream_is_accepted(
        workspace, write_sources, transport, client_factory, pdf_bytes):
    write_sources([ENTRY])
    transport.add(URL, body=pdf_bytes,
                  headers={"Content-Type": "binary/octet-stream"}, times=1)

    code, output = run(["--update"], workspace, client_factory)
    assert code == 0, output
    locked = M.load_lock(workspace["lock"])["phak"]
    assert locked["sha256"] == sha(pdf_bytes)
    assert locked["content_type"] == "binary/octet-stream", (
        "content type is recorded but never enforced")


# ---------------------------------------------------------------------------
# rule 2a: derived metadata is nullable and never a key
# ---------------------------------------------------------------------------

def test_faa_number_is_extracted_from_the_first_page():
    pages, number, source, _ = M.extract_metadata(
        make_pdf(lines=("FAA-H-8083-25C", "Pilot's Handbook")))
    assert pages == 1
    assert number == "FAA-H-8083-25C"
    assert source == "firstpage"


def test_an_unextractable_number_is_null_not_an_error(
        workspace, write_sources, transport, client_factory):
    blank = make_pdf(lines=("Nothing identifying here",))
    write_sources([ENTRY])
    transport.add(URL, body=blank, times=1)

    code, output = run(["--update"], workspace, client_factory)
    assert code == 0, output
    locked = M.load_lock(workspace["lock"])["phak"]
    assert locked["faa_number"] is None
    assert locked["faa_number_source"] is None
    assert "faa_number null" in output


def test_revision_date_never_comes_from_moddate():
    # A PDF whose only date is in its metadata must yield a null revision_date.
    # /ModDate changes on re-encoding with no content change, which is the same
    # false-drift defect already fixed in fetched_at.
    import fitz

    document = fitz.open()
    document.new_page().insert_text((72, 72), "No date on this page", fontsize=12)
    document.set_metadata({"modDate": "D:20260101000000Z",
                           "creationDate": "D:20260101000000Z"})
    data = document.tobytes()
    document.close()

    _, _, _, revision = M.extract_metadata(data)
    assert revision is None


def test_malformed_pdf_yields_nulls_rather_than_raising():
    assert M.extract_metadata(b"not a pdf at all") == (None, None, None, None)


# ---------------------------------------------------------------------------
# throttling manners
# ---------------------------------------------------------------------------

def test_backoff_retries_a_429_then_succeeds(transport, client_factory, pdf_bytes):
    transport.add(URL, status=429, headers={"Retry-After": "1"}, times=1)
    transport.add(URL, body=pdf_bytes, times=1)

    response = client_factory().get(URL)
    assert response.ok
    assert transport.request_count == 2


def test_retry_after_is_honored(transport, pdf_bytes):
    from _http import Client

    slept = []
    transport.add(URL, status=503, headers={"Retry-After": "7"}, times=1)
    transport.add(URL, body=pdf_bytes, times=1)

    client = Client(transport=transport, sleep=slept.append, jitter=lambda: 0.0)
    client.get(URL)
    assert slept == [7.0]


def test_retries_are_bounded(transport):
    from _http import Client

    transport.add(URL, status=503, times=99)
    client = Client(transport=transport, attempts=3,
                    sleep=lambda _s: None, jitter=lambda: 0.0)
    response = client.get(URL)
    assert response.status == 503
    assert transport.request_count == 3


def test_conditional_request_yields_304_and_no_body(
        seeded, transport, client_factory, pdf_bytes):
    transport.add(URL, body=pdf_bytes, etag='"v1"', times=1)
    code, output = run(["--check"], seeded, client_factory)
    assert code == 0
    assert "304, unchanged" in output


def test_requests_are_sequential_and_in_manifest_order(
        workspace, write_sources, transport, client_factory, pdf_bytes):
    # Sequential, not parallel, is a throttling mitigation. The observable
    # property is that targets are requested in declared order, one at a time.
    first = "https://www.faa.gov/files/aim_ch1.pdf"
    second = "https://www.faa.gov/files/aim_ch2.pdf"
    third = "https://www.faa.gov/files/aim_addendum.pdf"
    write_sources([{
        "id": "aim",
        "title": "Aeronautical Information Manual",
        "landing_url": "https://www.faa.gov/air_traffic/publications",
        "section": "aim",
        "parts": [{"url": first}, {"url": second}],
        "addenda": [{"url": third, "append": True}],
    }])
    for url in (first, second, third):
        transport.add(url, body=make_pdf(lines=(url,)), times=1)

    code, _ = run(["--update"], workspace, client_factory)
    assert code == 0

    requested = [url for _method, url, _headers in transport.calls]
    assert requested == [first, second, third], (
        "targets must be requested one at a time, in declared order")


def test_a_browser_like_user_agent_is_sent(transport, client_factory):
    transport.add(URL, body=b"%PDF-1.7", times=1)
    client_factory().get(URL)
    _, _, headers = transport.calls[0]
    assert "Mozilla/5.0" in headers["User-Agent"]


# ---------------------------------------------------------------------------
# empty manifest, which is the state until 1.2 lands
# ---------------------------------------------------------------------------

def test_empty_manifest_is_a_clean_no_op(workspace, write_sources,
                                         transport, client_factory):
    write_sources([])
    code, output = run([], workspace, client_factory)
    assert code == 0
    assert transport.request_count == 0
    assert "empty" in output
