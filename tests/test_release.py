"""Phase 7: drift classification, release timing, and release notes.

The timing rules are the whole release policy, and they are the kind of logic
that looks obviously right and is not. Each rule below exists to stop a
specific bad release: three releases for one rulemaking, a weekly drip, an
empty quarterly build, or a silent year of nothing.
"""

import datetime
import io
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import check_sources as C  # noqa: E402
import release_notes as N  # noqa: E402

UTC = datetime.timezone.utc


def at(day, hour=12):
    return datetime.datetime(2026, 9, day, hour, tzinfo=UTC)


def pending(changes=None, last_release=None):
    return {"changes": changes or {}, "last_release": last_release,
            "last_build": None}


def change(tier, first_seen, detail="moved"):
    return {"kind": "source", "tier": tier, "detail": detail,
            "first_seen": first_seen, "last_seen": first_seen}


# ---------------------------------------------------------------------------
# tier classification
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("section,expected", [
    ("standards", "tier1"),     # an ACS revision changes what is tested
    ("handbooks", "tier1"),
    ("aim", "tier1"),
    ("ac", "tier2"),
    ("interps", "tier2"),
    ("guides", "tier2"),
])
def test_a_document_takes_its_tier_from_its_section(section, expected):
    assert C.tier_for_source({"section": section}) == expected


@pytest.mark.parametrize("key,expected", [
    ("title-14-part-91", "tier1"),
    ("title-14-part-61", "tier1"),
    ("title-14-part-43", "tier1"),
    ("title-49-part-830", "tier1"),   # NTSB reporting, always tier 1
    ("title-14-part-105", "tier2"),   # parachute ops, reference only
    ("title-14-part-47", "tier2"),
])
def test_cfr_parts_are_tiered_by_who_flies_under_them(key, expected):
    assert C.tier_for_cfr(key) == expected


# ---------------------------------------------------------------------------
# the timing rules
# ---------------------------------------------------------------------------

def test_a_tier_2_change_alone_never_releases():
    """An Advisory Circular revision is not worth a release on its own."""
    state = pending({"ac-61-65k": change("tier2", "2026-09-01T00:00:00Z")})
    build, reason = C.decide(state, at(20))
    assert not build
    assert "tier 2" in reason


def test_a_tier_1_change_waits_out_the_debounce():
    """Federal Register amendments cluster.

    Building on first sighting cut three releases in a week for one rulemaking.
    """
    # The last release must be recent enough not to trip the quarterly ceiling
    # and old enough not to trip the weekly floor, or neither rule under test
    # is the one that decides.
    state = pending({"title-14-part-91": change("tier1", "2026-09-10T00:00:00Z")},
                    last_release="2026-08-25T00:00:00Z")
    build, reason = C.decide(state, at(11))       # 24 hours later
    assert not build
    assert "debounce" in reason


def test_the_quarterly_ceiling_outranks_the_debounce():
    """A release 100 days stale ships, debounce or not.

    The ceiling exists to catch silent breakage. Holding it for three more days
    behind a debounce would defeat the reason it exists.
    """
    state = pending({"title-14-part-91": change("tier1", "2026-09-10T00:00:00Z")},
                    last_release="2026-06-01T00:00:00Z")
    build, reason = C.decide(state, at(11))
    assert build
    assert "ceiling" in reason


def test_a_tier_1_change_builds_once_the_debounce_elapses():
    state = pending({"title-14-part-91": change("tier1", "2026-09-10T00:00:00Z")},
                    last_release="2026-08-01T00:00:00Z")
    build, reason = C.decide(state, at(14))       # 96 hours later
    assert build
    assert "past debounce" in reason


def test_the_weekly_floor_holds_a_ready_change():
    state = pending({"aim": change("tier1", "2026-09-01T00:00:00Z")},
                    last_release="2026-09-08T00:00:00Z")
    build, reason = C.decide(state, at(10))       # 2 days after the release
    assert not build
    assert "floor" in reason


def test_the_quarterly_ceiling_builds_with_no_drift_at_all():
    """Catches silent URL rot and toolchain breakage while there is time."""
    state = pending({}, last_release="2026-01-01T00:00:00Z")
    build, reason = C.decide(state, at(30))
    assert build
    assert "ceiling" in reason


def test_no_pending_changes_and_a_recent_release_does_nothing():
    state = pending({}, last_release="2026-09-01T00:00:00Z")
    build, reason = C.decide(state, at(10))
    assert not build
    assert "no pending" in reason


def test_the_first_ever_run_builds():
    build, reason = C.decide(pending(), at(1))
    assert build


# ---------------------------------------------------------------------------
# the debounce clock
# ---------------------------------------------------------------------------

def test_seeing_the_same_change_again_does_not_restart_the_clock():
    """The check runs daily.

    Refreshing first_seen on every sighting would hold a tier 1 change forever,
    because it would never be more than 24 hours old.
    """
    state = pending()
    detected = {"aim": {"kind": "source", "tier": "tier1", "detail": "etag"}}
    C.merge(state, detected, at(10))
    C.merge(state, detected, at(11))
    C.merge(state, detected, at(12))
    assert state["changes"]["aim"]["first_seen"] == "2026-09-10T12:00:00Z"
    assert state["changes"]["aim"]["last_seen"] == "2026-09-12T12:00:00Z"
    build, _reason = C.decide(state, at(13, 13))
    assert build, "a change seen daily for three days must clear the debounce"


def test_recording_a_release_clears_the_queue(tmp_path):
    path = tmp_path / "pending.json"
    C.write_pending(pending({"aim": change("tier1", "2026-09-01T00:00:00Z")}),
                    path)
    out = io.StringIO()
    assert C.run(["--released", "2026-09-14T00:00:00Z"],
                 pending_path=path, out=out) == 0
    after = C.load_pending(path)
    assert after["changes"] == {}
    assert after["last_release"] == "2026-09-14T00:00:00Z"


# ---------------------------------------------------------------------------
# drift detection, offline
# ---------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, status, headers=None):
        self.status = status
        self._headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.body = b""

    def header(self, name):
        return self._headers.get(name.lower())


class FakeClient:
    def __init__(self, replies):
        self.replies = replies
        self.request_count = 0
        self.sent = []

    def head(self, url, headers=None):
        self.request_count += 1
        self.sent.append((url, headers or {}))
        return self.replies.get(url, FakeResponse(304))

    def get(self, url, **kwargs):
        self.request_count += 1
        raise RuntimeError("no eCFR in this test")


ENTRIES = [{"id": "aim", "section": "aim", "title": "AIM",
            "url": "https://example.test/aim.pdf"},
           {"id": "ac-61-65k", "section": "ac", "title": "AC 61-65K",
            "url": "https://example.test/ac.pdf"}]
LOCK = {"aim": {"resolved_url": "https://example.test/aim.pdf",
                "sha256": "a" * 64, "bytes": 100},
        "ac-61-65k": {"resolved_url": "https://example.test/ac.pdf",
                      "sha256": "b" * 64, "bytes": 200}}
STATE = {"aim": {"etag": "old-aim"}, "ac-61-65k": {"etag": "old-ac"}}


def test_a_304_is_not_drift():
    client = FakeClient({})
    found = C.check_sources(ENTRIES, LOCK, STATE, client, io.StringIO())
    assert found == {}
    assert client.request_count == 2


def test_a_changed_etag_is_drift_and_carries_its_tier():
    client = FakeClient({
        "https://example.test/aim.pdf": FakeResponse(200, {"ETag": "new"}),
    })
    found = C.check_sources(ENTRIES, LOCK, STATE, client, io.StringIO())
    assert set(found) == {"aim"}
    assert found["aim"]["tier"] == "tier1"


def test_a_conditional_header_is_sent_when_one_is_known():
    client = FakeClient({})
    C.check_sources(ENTRIES, LOCK, STATE, client, io.StringIO())
    _url, headers = client.sent[0]
    assert headers.get("If-None-Match") == "old-aim"


def test_a_404_is_reported_rather_than_ignored():
    """URL rot is the highest-frequency failure this project has."""
    client = FakeClient({
        "https://example.test/ac.pdf": FakeResponse(404),
    })
    found = C.check_sources(ENTRIES, LOCK, STATE, client, io.StringIO())
    assert found["ac-61-65k"]["detail"] == "HTTP 404"


def test_an_unreachable_host_is_not_mistaken_for_a_change():
    """A network failure must not enqueue a release."""

    class Broken(FakeClient):
        def head(self, url, headers=None):
            raise RuntimeError("connection reset")

    found = C.check_sources(ENTRIES, LOCK, STATE, Broken({}), io.StringIO())
    assert found == {}


# ---------------------------------------------------------------------------
# release notes
# ---------------------------------------------------------------------------

def test_notes_report_a_revised_document():
    previous = {"phak": {"sha256": "a" * 64, "faa_number": "FAA-H-8083-25C"}}
    current = {"phak": {"sha256": "c" * 64, "faa_number": "FAA-H-8083-25D",
                        "pages": 522}}
    body, changed = N.render(
        "v2026.09.1", previous, current, {}, {}, {}, [
            {"id": "phak", "title": "Pilot's Handbook"}])
    assert changed
    assert "Documents revised" in body
    assert "FAA-H-8083-25D" in body


def test_a_page_count_change_alone_is_not_a_revision():
    """Only sha256 is load bearing.

    `pages` moves on re-extraction with no content change, and treating that as
    a revision would cut a release announcing nothing.
    """
    previous = {"phak": {"sha256": "a" * 64, "pages": 521}}
    current = {"phak": {"sha256": "a" * 64, "pages": 522}}
    _body, changed = N.render("v1", previous, current, {}, {}, {}, [])
    assert not changed


def test_an_unchanged_corpus_says_so_plainly():
    body, changed = N.render("v1", {"phak": {"sha256": "a" * 64}},
                             {"phak": {"sha256": "a" * 64}}, {}, {}, {}, [])
    assert not changed
    assert "scheduled rebuild" in body


def test_notes_report_an_amended_cfr_part():
    body, changed = N.render(
        "v1", {}, {}, {"title-14-part-91": {"amended_on": "2026-01-01"}},
        {"title-14-part-91": {"amended_on": "2026-08-19"}}, {}, [])
    assert changed
    assert "Regulations amended" in body
    assert "2026-08-19" in body


def test_notes_always_carry_the_unofficial_disclaimer():
    body, _changed = N.render("v1", {}, {}, {}, {}, {}, [])
    assert "Unofficial" in body
    assert "not a substitute" in body


def test_notes_exit_nonzero_when_nothing_changed(tmp_path):
    """This is what stops the quarterly floor build cutting an empty release."""
    lock = tmp_path / "sources.lock.yaml"
    lock.write_text("sources:\n  phak:\n    sha256: '%s'\n" % ("a" * 64),
                    encoding="utf-8")
    out = io.StringIO()
    code = N.run(["--previous", str(lock)], lock_path=lock,
                 cfr_lock_path=tmp_path / "absent.yaml", out=out)
    assert code == N.EXIT_NO_CHANGE


# ---------------------------------------------------------------------------
# the workflows must stay consistent with the tools they call
# ---------------------------------------------------------------------------

WORKFLOWS = ROOT / ".github" / "workflows"


def test_every_workflow_parses():
    import yaml

    for path in sorted(WORKFLOWS.glob("*.yml")):
        with io.open(path, encoding="utf-8") as handle:
            assert yaml.safe_load(handle), path.name


def test_release_never_publishes_a_pull_request_build():
    """A PR build must not reach the releases page."""
    text = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")
    assert "workflow_run.event != 'pull_request'" in text
    assert "workflow_run.conclusion == 'success'" in text


def test_the_build_pins_every_external_tool():
    """Rule 12: an unpinned tool is a determinism risk.

    An unpinned Typst changes the generated bytes. An action tracking @main
    lets a third party change what runs here without a commit in this repo.
    A version written from memory is worse still: pdfcpu 0.8.0 does not exist
    and would have failed the build twenty minutes in.
    """
    text = (WORKFLOWS / "build.yml").read_text(encoding="utf-8")
    assert "version=0.15.1" in text, "typst is not pinned"
    assert "version=0.15.0" in text, "pdfcpu is not pinned to a real release"
    assert "@main" not in text, "an action is tracking a moving branch"


def test_the_dispatch_limitation_is_handled_out_loud():
    """The default GITHUB_TOKEN cannot start a workflow.

    Left unhandled, check-sources would decide to build and nothing would
    happen, with nothing in the log saying why.
    """
    text = (WORKFLOWS / "check-sources.yml").read_text(encoding="utf-8")
    assert "DISPATCH_TOKEN" in text
    assert "::warning::" in text
