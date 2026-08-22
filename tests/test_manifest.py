"""Manifest schema validation.

The schema is the first line of defense for rules 1 and 2a. A bad entry should
fail here, loudly, before anything reaches the network.
"""

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import _manifest as M  # noqa: E402

GOOD = {
    "id": "phak",
    "title": "Pilot's Handbook of Aeronautical Knowledge",
    "landing_url": "https://www.faa.gov/handbooks/phak",
    "url": "https://www.faa.gov/files/phak.pdf",
    "section": "handbooks",
    "order": 1,
}


def variant(**overrides):
    entry = dict(GOOD)
    entry.update(overrides)
    return entry


def test_a_well_formed_entry_validates():
    assert M.validate([GOOD])


def test_the_committed_manifest_parses_and_validates():
    # load_sources validates on the way in, so this failing means the committed
    # manifest is malformed. Asserts shape, never a fixed entry count.
    entries = M.load_sources()
    assert isinstance(entries, list)
    for entry in entries:
        assert entry["landing_url"].startswith("https://")
        assert entry["section"] in M.SECTIONS
        assert "faa_number" not in entry, "rule 2a: derived, never authored"


def test_committed_manifest_has_unique_target_keys():
    keys = [key for entry in M.load_sources() for key, _ in M.targets(entry)]
    assert len(keys) == len(set(keys)), "target keys must be unique"


def test_committed_manifest_urls_are_all_faa_gov():
    # Rule 3: FAA and NTSB material only. Nothing else gets fetched.
    allowed = ("www.faa.gov", "www.ntsb.gov", "www.ecfr.gov")
    import urllib.parse

    for entry in M.load_sources():
        urls = [entry.get("landing_url")]
        urls += [url for _key, url in M.targets(entry)]
        for url in filter(None, urls):
            host = urllib.parse.urlparse(url).netloc
            assert host in allowed, f"{entry['id']}: unexpected host {host}"


def test_duplicate_ids_are_rejected():
    with pytest.raises(M.ManifestError, match="duplicate id"):
        M.validate([GOOD, variant(title="Copy")])


def test_unknown_section_is_rejected():
    with pytest.raises(M.ManifestError, match="section must be"):
        M.validate([variant(section="miscellaneous")])


def test_http_urls_are_rejected():
    with pytest.raises(M.ManifestError, match="must be https"):
        M.validate([variant(url="http://www.faa.gov/files/phak.pdf")])


def test_faa_number_in_the_manifest_is_rejected():
    # Rule 2a. It is derived at fetch time, never hand-authored.
    with pytest.raises(M.ManifestError, match="unknown fields: faa_number"):
        M.validate([variant(faa_number="FAA-H-8083-25C")])


def test_menu_page_in_the_manifest_is_rejected():
    # Removed in favor of section plus order, which survives a menu redesign.
    with pytest.raises(M.ManifestError, match="unknown fields: menu_page"):
        M.validate([variant(menu_page=1)])


def test_landing_url_is_required():
    entry = dict(GOOD)
    del entry["landing_url"]
    with pytest.raises(M.ManifestError, match="missing landing_url"):
        M.validate([entry])


def test_an_entry_needs_url_or_parts():
    entry = dict(GOOD)
    del entry["url"]
    with pytest.raises(M.ManifestError, match="needs url or parts"):
        M.validate([entry])


def test_parts_only_entry_is_valid():
    entry = dict(GOOD)
    del entry["url"]
    entry["parts"] = [{"url": "https://www.faa.gov/files/aim_ch1.pdf"}]
    assert M.validate([entry])


def test_ids_must_be_slugs():
    with pytest.raises(M.ManifestError, match="lowercase slug"):
        M.validate([variant(id="PHAK Handbook")])


def test_targets_key_parts_and_addenda_stably():
    entry = dict(GOOD)
    entry["parts"] = [{"url": "https://www.faa.gov/a.pdf"},
                      {"url": "https://www.faa.gov/b.pdf"}]
    entry["addenda"] = [{"url": "https://www.faa.gov/c.pdf", "append": True}]

    keys = [key for key, _ in M.targets(entry)]
    assert keys == ["phak", "phak.part.0", "phak.part.1", "phak.addendum.0"]


def test_magic_bytes_gate():
    assert M.looks_like_pdf(b"%PDF-1.7\nrest")
    assert not M.looks_like_pdf(b"<html>")
    assert not M.looks_like_pdf(b"")


def test_committed_cfr_manifest_is_valid():
    import yaml

    with open(ROOT / "manifest" / "cfr.yaml", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    assert data["title_14"]["parts"][0] == 1
    assert 61 in data["title_14"]["parts"] and 91 in data["title_14"]["parts"]
    assert 121 in data["title_14"]["excluded"]
    assert data["title_49"]["parts"] == [830]
