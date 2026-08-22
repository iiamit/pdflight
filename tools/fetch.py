"""Fetch the source corpus into cache/ and maintain manifest/sources.lock.yaml.

Three modes, each its own Makefile target because make does not forward flags
to a recipe.

    make fetch          Satisfy the lock from cache. Fully offline when the
                        cache already holds every locked sha256. Downloads only
                        what is missing, and only the exact bytes the lock pins.
    make fetch-check    Revalidate. Reports drift, writes nothing to the lock,
                        downloads no content. Exit 1 when drift is found.
    make fetch-update   Pull changed sources and rewrite the lock.

On a 404 this tool does not go looking for a replacement. It reports every PDF
link on the document's landing page and stops. Auto-updating `url` from a
scrape is auto-substitution, and it violates rule 1 at a different layer than
the interpretation citations do. A human picks.

Exit codes follow CLAUDE.md section 9: 0 success, 1 a check failed as designed,
2 usage error.
"""

import argparse
import hashlib
import html.parser
import pathlib
import sys
import urllib.parse

import _manifest as M
from _http import Client, FetchError, conditional_headers

EXIT_OK = 0
EXIT_DRIFT = 1

MAX_CANDIDATES = 40


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class PdfLinkParser(html.parser.HTMLParser):
    """Collect every href ending in .pdf, with its link text.

    Deliberately generic. "Find all .pdf hrefs" needs no per-template parser,
    which is what makes the candidate report cheap enough to be the 404 answer
    across every FAA page layout.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href and ".pdf" in href.lower().split("?")[0]:
            self._href = href
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            text = " ".join("".join(self._text).split())
            self.links.append((self._href, text))
            self._href = None
            self._text = []


def report_candidates(client, entry, url, out=sys.stdout):
    """Print the PDF links found on landing_url. Never picks one."""
    landing = entry.get("landing_url")
    out.write("\n%s: %s returned 404.\n" % (entry["id"], url))
    if not landing:
        out.write("  No landing_url to fall back to. Nothing reported.\n")
        return []

    out.write("  Scraping %s for candidates. Nothing is substituted"
              " automatically.\n" % landing)
    try:
        page = client.get(landing)
    except FetchError as exc:
        out.write("  landing_url unreachable: %s\n" % exc)
        return []

    if not page.ok:
        out.write("  landing_url returned %d\n" % page.status)
        return []

    parser = PdfLinkParser()
    parser.feed(page.body.decode("utf-8", "replace"))

    seen, candidates = set(), []
    for href, text in parser.links:
        absolute = urllib.parse.urljoin(page.url, href)
        if absolute in seen:
            continue
        seen.add(absolute)
        candidates.append((absolute, text))

    if not candidates:
        out.write("  No PDF links found on the landing page.\n")
        return []

    truncated = len(candidates) - MAX_CANDIDATES
    shown = candidates[:MAX_CANDIDATES]

    out.write("  %d candidate(s):\n" % len(candidates))
    for absolute, text in shown:
        try:
            head = client.head(absolute)
            size = head.content_length
            size_text = "%9d B" % size if size is not None else "  unknown"
        except FetchError:
            size_text = "unreachable"
        out.write("    %s  %s\n" % (size_text, absolute))
        if text:
            out.write("      text: %s\n" % text[:100])

    if truncated > 0:
        # No silent caps. If coverage is bounded, say so.
        out.write("  %d further candidate(s) not shown. Raise MAX_CANDIDATES"
                  " to see them.\n" % truncated)

    out.write("  Pick one by hand and update manifest/sources.yaml.\n")
    return candidates


def describe(data, response, url):
    """Build the content-derived half of a lock entry."""
    pages, number, number_source, revision = M.extract_metadata(data)
    return {
        "resolved_url": response.url if response else url,
        "sha256": sha256(data),
        "bytes": len(data),
        "pages": pages,
        "content_type": response.content_type if response else None,
        "faa_number": number,
        "faa_number_source": number_source,
        "revision_date": revision,
    }


def store(data, cache_root):
    digest = sha256(data)
    path = M.cache_path(digest, cache_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        path.write_bytes(data)
    return digest


# ---------------------------------------------------------------------------
# modes
# ---------------------------------------------------------------------------

def mode_fetch(entries, lock, client_factory, cache_root, out):
    """Satisfy the lock from cache. Zero network on a warm cache."""
    keys = [key for entry in entries for key, _ in M.targets(entry)]
    missing = []
    corrupt = []

    for key in keys:
        locked = lock.get(key)
        if not locked:
            out.write("%s: not in the lock. Run make fetch-update.\n" % key)
            missing.append(key)
            continue
        digest = locked.get("sha256")
        path = M.cache_path(digest, cache_root)
        if not path.is_file():
            missing.append(key)
        elif sha256(path.read_bytes()) != digest:
            corrupt.append(key)

    if corrupt:
        for key in corrupt:
            out.write("%s: cached blob does not match its locked sha256.\n" % key)
        return EXIT_DRIFT

    if not missing:
        out.write("%d source(s) satisfied from cache. No network.\n" % len(keys))
        return EXIT_OK

    client = client_factory()
    urls = {key: url for entry in entries for key, url in M.targets(entry)}
    failed = []
    for key in missing:
        locked = lock.get(key)
        if not locked:
            failed.append(key)
            continue
        url = locked.get("resolved_url") or urls.get(key)
        out.write("%s: fetching pinned bytes from %s\n" % (key, url))
        try:
            response = client.get(url)
        except FetchError as exc:
            out.write("  %s\n" % exc)
            failed.append(key)
            continue
        if not response.ok or sha256(response.body) != locked["sha256"]:
            out.write("  content does not match the locked sha256. "
                      "The lock is stale; run make fetch-update.\n")
            failed.append(key)
            continue
        store(response.body, cache_root)

    if failed:
        out.write("\n%d source(s) could not be satisfied.\n" % len(failed))
        return EXIT_DRIFT
    out.write("%d source(s) satisfied.\n" % len(keys))
    return EXIT_OK


def mode_check(entries, lock, state, client_factory, cache_root, out):
    """Revalidate. Never writes the lock. Exit 1 on drift."""
    drift = []
    client = None

    for entry in entries:
        for key, url in M.targets(entry):
            locked = lock.get(key)
            if not locked:
                drift.append("%s: absent from the lock" % key)
                continue

            # Local integrity first. This catches a corrupted lock hash with no
            # network at all.
            path = M.cache_path(locked.get("sha256"), cache_root)
            if path.is_file():
                actual = sha256(path.read_bytes())
                if actual != locked.get("sha256"):
                    drift.append("%s: cached blob %s, lock says %s"
                                 % (key, actual[:12], str(locked.get("sha256"))[:12]))
                    continue
            else:
                drift.append("%s: locked blob is not in the cache" % key)
                continue

            if client is None:
                client = client_factory()
            try:
                response = client.get(
                    url, **_validators(state.get(key)))
            except FetchError as exc:
                out.write("%s: %s\n" % (key, exc))
                drift.append("%s: unreachable" % key)
                continue

            if response.not_modified:
                out.write("%s: 304, unchanged\n" % key)
                continue
            if response.status == 404:
                drift.append("%s: 404" % key)
                report_candidates(client, entry, url, out)
                continue
            if not response.ok:
                drift.append("%s: HTTP %d" % (key, response.status))
                continue

            fresh = sha256(response.body)
            state[key] = {
                "etag": response.header("etag"),
                "last_modified": response.header("last-modified"),
                "checked_at": M.utcnow(),
            }
            if fresh != locked.get("sha256"):
                drift.append("%s: content changed (%s -> %s)"
                             % (key, str(locked.get("sha256"))[:12], fresh[:12]))
            else:
                out.write("%s: unchanged\n" % key)

    if drift:
        out.write("\nDrift detected:\n")
        for line in drift:
            out.write("  %s\n" % line)
        out.write("\nRun make fetch-update to adopt these changes.\n")
        return EXIT_DRIFT

    out.write("\nNo drift. The lock is current.\n")
    return EXIT_OK


def _validators(state_entry):
    headers = conditional_headers(state_entry)
    return {
        "etag": headers.get("If-None-Match"),
        "last_modified": headers.get("If-Modified-Since"),
    }


def mode_update(entries, lock, state, client_factory, cache_root, out):
    """Pull changed sources and rewrite the lock."""
    client = client_factory()
    updated = {}
    failed = []

    for entry in entries:
        for key, url in M.targets(entry):
            previous = lock.get(key)
            try:
                response = client.get(url, **_validators(state.get(key)))
            except FetchError as exc:
                out.write("%s: %s\n" % (key, exc))
                failed.append(key)
                if previous:
                    updated[key] = previous
                continue

            if response.not_modified and previous:
                out.write("%s: 304, unchanged\n" % key)
                updated[key] = previous
                continue

            if response.status == 404:
                report_candidates(client, entry, url, out)
                failed.append(key)
                if previous:
                    updated[key] = previous
                continue

            if not response.ok:
                out.write("%s: HTTP %d\n" % (key, response.status))
                failed.append(key)
                if previous:
                    updated[key] = previous
                continue

            if not M.looks_like_pdf(response.body):
                head = response.body[:16]
                out.write("%s: not a PDF. First bytes: %r, content-type %s\n"
                          % (key, head, response.content_type))
                failed.append(key)
                if previous:
                    updated[key] = previous
                continue

            fresh = describe(response.body, response, url)
            store(response.body, cache_root)
            entry_lock = M.merge_lock_entry(previous, fresh)
            updated[key] = entry_lock
            state[key] = {
                "etag": response.header("etag"),
                "last_modified": response.header("last-modified"),
                "checked_at": M.utcnow(),
            }
            changed = not previous or previous.get("sha256") != fresh["sha256"]
            out.write("%s: %s  %d pages, %d bytes%s\n" % (
                key, "CHANGED" if changed else "unchanged",
                fresh["pages"] or 0, fresh["bytes"],
                "" if fresh["faa_number"] else "  (faa_number null)"))

    if failed:
        out.write("\n%d source(s) failed: %s\n" % (len(failed), ", ".join(failed)))
    return updated, EXIT_DRIFT if failed else EXIT_OK


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def run(argv, client_factory=None, sources_path=M.SOURCES, lock_path=M.LOCK,
        state_path=M.STATE, cache_root=M.CACHE, index_path=M.CACHE_INDEX,
        out=sys.stdout):
    parser = argparse.ArgumentParser(
        prog="fetch.py",
        description="Fetch the source corpus and maintain the lock file.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true",
                       help="revalidate, report drift, write nothing")
    group.add_argument("--update", action="store_true",
                       help="pull changed sources and rewrite the lock")
    args = parser.parse_args(argv)

    client_factory = client_factory or Client
    entries = M.load_sources(sources_path)
    lock = M.load_lock(lock_path)

    if not entries:
        out.write("manifest/sources.yaml is empty. Nothing to do.\n")
        out.write("Populate it in deliverable 1.2; every URL gets a live"
                  " request first.\n")
        return EXIT_OK

    if args.check:
        state = M.load_state(state_path)
        code = mode_check(entries, lock, state, client_factory, cache_root, out)
        M.dump_state(state, state_path)
        return code

    if args.update:
        state = M.load_state(state_path)
        updated, code = mode_update(
            entries, lock, state, client_factory, cache_root, out)
        M.dump_lock(updated, lock_path)
        M.dump_state(state, state_path)
        index = {key: value["sha256"] for key, value in updated.items()
                 if value.get("sha256")}
        M.dump_cache_index(index, index_path)
        return code

    return mode_fetch(entries, lock, client_factory, cache_root, out)


def main(argv):
    try:
        return run(argv)
    except M.ManifestError as exc:
        sys.stderr.write("manifest error: %s\n" % exc)
        return EXIT_DRIFT


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
