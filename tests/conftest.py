"""Shared fixtures. Nothing here touches the network.

The HTTP client takes an injectable transport precisely so the fetcher's retry,
conditional-request, 404, and drift paths can all be exercised offline.
"""

import collections
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


class FakeTransport:
    """Records every call and replays scripted responses.

    A route may hold a queue of responses so retry paths can be driven, for
    example 429 then 200.
    """

    def __init__(self):
        self.routes = collections.defaultdict(collections.deque)
        self.calls = []

    def add(self, url, status=200, body=b"", headers=None, final_url=None,
            etag=None, times=1):
        head = dict(headers or {})
        if etag:
            head["ETag"] = etag
        for _ in range(times):
            self.routes[url].append(
                {"status": status, "body": body, "headers": head,
                 "final_url": final_url or url, "etag": etag})

    def __call__(self, method, url, headers):
        self.calls.append((method, url, dict(headers)))
        queue = self.routes.get(url)
        if not queue:
            return 404, {}, b"", url

        entry = queue[0] if len(queue) == 1 else queue.popleft()

        # Honor conditional requests so the 304 path is real, not simulated.
        if entry["etag"] and headers.get("If-None-Match") == entry["etag"]:
            return 304, {"ETag": entry["etag"]}, b"", entry["final_url"]

        body = b"" if method == "HEAD" else entry["body"]
        head = dict(entry["headers"])
        head.setdefault("Content-Length", str(len(entry["body"])))
        return entry["status"], head, body, entry["final_url"]

    @property
    def request_count(self):
        return len(self.calls)


@pytest.fixture
def transport():
    return FakeTransport()


@pytest.fixture
def client_factory(transport):
    from _http import Client

    def factory():
        return Client(transport=transport, sleep=lambda _s: None,
                      jitter=lambda: 0.0)

    return factory


@pytest.fixture
def workspace(tmp_path):
    """An isolated stand-in for the repo's manifest, cache, and state paths."""
    (tmp_path / "manifest").mkdir()
    (tmp_path / "cache" / "sources").mkdir(parents=True)
    (tmp_path / "state").mkdir()
    return {
        "sources": tmp_path / "manifest" / "sources.yaml",
        "lock": tmp_path / "manifest" / "sources.lock.yaml",
        "state": tmp_path / "state" / "check.json",
        "cache": tmp_path / "cache" / "sources",
        "index": tmp_path / "cache" / "index.json",
        "root": tmp_path,
    }


def make_pdf(lines=("FAA-H-8083-25C", "Pilot's Handbook"), pages=1):
    """A real PDF, so metadata extraction is tested against a real parser."""
    import pymupdf

    document = pymupdf.open()
    for number in range(max(1, pages)):
        page = document.new_page()
        if number == 0:
            y = 72
            for line in lines:
                page.insert_text((72, y), line, fontsize=12)
                y += 18
    data = document.tobytes()
    document.close()
    return data


@pytest.fixture
def pdf_bytes():
    return make_pdf()


@pytest.fixture
def write_sources(workspace):
    import yaml

    def writer(entries):
        with open(workspace["sources"], "w", encoding="utf-8", newline="\n") as fh:
            yaml.safe_dump(entries, fh, sort_keys=False)
        return workspace["sources"]

    return writer
