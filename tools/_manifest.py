"""Manifest schema, lock file IO, and PDF metadata extraction.

Two rules shape everything here.

Rule 8, determinism: the lock is serialized with sorted keys, block style, and
LF endings, so identical inputs produce an identical file. `fetched_at` is
written only when `sha256` changes, because the release job treats a lock diff
as the signal that the FAA changed something. A timestamp that ticks on every
run would turn every check into false drift.

Rule 2a, derived fields: `faa_number` and `revision_date` come out of the
fetched document or they are null. They are informational, nullable, and never
keys. `id` is the identifier.
"""

import datetime
import io
import json
import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCES = ROOT / "manifest" / "sources.yaml"
LOCK = ROOT / "manifest" / "sources.lock.yaml"
STATE = ROOT / "state" / "check.json"
CACHE = ROOT / "cache" / "sources"
CACHE_INDEX = ROOT / "cache" / "index.json"

PDF_MAGIC = b"%PDF-"

SECTIONS = frozenset(
    ["standards", "handbooks", "aim", "regs", "ac", "interps", "guides"])

REQUIRED = ("id", "title", "landing_url", "section")
ALLOWED = frozenset(
    ["id", "title", "landing_url", "url", "section", "order", "optional",
     "parts", "addenda"])

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class ManifestError(Exception):
    """The manifest violates the schema."""


# ---------------------------------------------------------------------------
# sources.yaml
# ---------------------------------------------------------------------------

def load_sources(path=SOURCES):
    with io.open(path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if data is None:
        data = []
    if not isinstance(data, list):
        raise ManifestError("sources.yaml must be a list, got %s"
                            % type(data).__name__)
    validate(data)
    return data


def validate(entries):
    seen = set()
    for index, entry in enumerate(entries):
        where = "entry %d" % index
        if not isinstance(entry, dict):
            raise ManifestError("%s is not a mapping" % where)

        for field in REQUIRED:
            if not entry.get(field):
                raise ManifestError("%s is missing %s" % (where, field))

        extra = set(entry) - ALLOWED
        if extra:
            raise ManifestError("%s has unknown fields: %s"
                                % (where, ", ".join(sorted(extra))))

        ident = entry["id"]
        where = "%s (%s)" % (where, ident)
        if not ID_PATTERN.match(ident):
            raise ManifestError("%s: id must be lowercase slug" % where)
        if ident in seen:
            raise ManifestError("duplicate id: %s" % ident)
        seen.add(ident)

        if entry["section"] not in SECTIONS:
            raise ManifestError("%s: section must be one of %s"
                                % (where, ", ".join(sorted(SECTIONS))))

        for field in ("landing_url", "url"):
            value = entry.get(field)
            if value and not str(value).startswith("https://"):
                raise ManifestError("%s: %s must be https" % (where, field))

        if not entry.get("url") and not entry.get("parts"):
            raise ManifestError("%s: needs url or parts" % where)

        for field in ("parts", "addenda"):
            items = entry.get(field) or []
            if not isinstance(items, list):
                raise ManifestError("%s: %s must be a list" % (where, field))
            for item in items:
                if not isinstance(item, dict) or not item.get("url"):
                    raise ManifestError("%s: every %s item needs a url"
                                        % (where, field))
                if not str(item["url"]).startswith("https://"):
                    raise ManifestError("%s: %s url must be https"
                                        % (where, field))
    return entries


def targets(entry):
    """Yield (key, url) for the entry and each of its parts and addenda.

    Keys are stable and derived from `id`, never from a hash or a filename, so
    a lock diff stays readable when a document changes.
    """
    if entry.get("url"):
        yield entry["id"], entry["url"]
    for index, part in enumerate(entry.get("parts") or []):
        yield "%s.part.%d" % (entry["id"], index), part["url"]
    for index, addendum in enumerate(entry.get("addenda") or []):
        yield "%s.addendum.%d" % (entry["id"], index), addendum["url"]


# ---------------------------------------------------------------------------
# sources.lock.yaml
# ---------------------------------------------------------------------------

LOCK_FIELDS = ("resolved_url", "sha256", "bytes", "pages", "content_type",
               "faa_number", "faa_number_source", "revision_date", "fetched_at")


def load_lock(path=LOCK):
    if not pathlib.Path(path).is_file():
        return {}
    with io.open(path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not data:
        return {}
    return data.get("sources", {}) or {}


LOCK_HEADER = """\
# Written by tools/fetch.py. Do not hand-edit.
#
# Holds content-derived fields only. sha256 is the only load-bearing change
# signal; every other field is informational, nullable, and never fails a build.
#
# fetched_at updates only when sha256 changes. Volatile validators (etag,
# last_modified, last-checked timestamp) live in state/check.json, which is
# gitignored. A diff in this file must mean the content changed, because the
# release job uses that diff to decide whether to cut a release.
"""


def dump_lock(sources, path=LOCK):
    """Serialize deterministically. Identical input, identical bytes."""
    ordered = {}
    for key in sorted(sources):
        entry = sources[key]
        ordered[key] = {f: entry.get(f) for f in LOCK_FIELDS if f in entry}

    body = yaml.safe_dump(
        {"sources": ordered} if ordered else {},
        default_flow_style=False,
        sort_keys=True,
        allow_unicode=True,
        width=100,
    )
    if not ordered:
        body = "{}\n"

    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(LOCK_HEADER)
        handle.write("\n")
        handle.write(body)


def merge_lock_entry(previous, fresh):
    """Carry fetched_at forward unless sha256 actually moved.

    This is the whole reason a lock diff can be trusted as a release signal.
    """
    entry = dict(fresh)
    if previous and previous.get("sha256") == fresh.get("sha256"):
        entry["fetched_at"] = previous.get("fetched_at")
    else:
        entry["fetched_at"] = fresh.get("fetched_at") or utcnow()
    return entry


def utcnow():
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# state/check.json, gitignored, never a release signal
# ---------------------------------------------------------------------------

def load_state(path=STATE):
    if not pathlib.Path(path).is_file():
        return {}
    with io.open(path, encoding="utf-8") as handle:
        return json.load(handle)


def dump_state(state, path=STATE):
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")


# ---------------------------------------------------------------------------
# content-addressed cache
# ---------------------------------------------------------------------------

def cache_path(digest, root=CACHE):
    return pathlib.Path(root) / ("%s.pdf" % digest)


def load_cache_index(path=CACHE_INDEX):
    if not pathlib.Path(path).is_file():
        return {}
    with io.open(path, encoding="utf-8") as handle:
        return json.load(handle)


def dump_cache_index(index, path=CACHE_INDEX):
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(index, handle, indent=2, sort_keys=True)
        handle.write("\n")


# ---------------------------------------------------------------------------
# derived metadata, rule 2a
# ---------------------------------------------------------------------------

FAA_NUMBER_PATTERNS = (
    re.compile(r"\bFAA-H-\d{4}-\d+[A-Z]?\b"),
    re.compile(r"\bFAA-S-ACS-\d+[A-Z]?\b"),
    re.compile(r"\bFAA-S-\d{4}-\d+[A-Z]?\b"),
    re.compile(r"\bAC\s?No[.:]?\s?(\d{1,3}[-.]\d+[A-Z]?)\b", re.IGNORECASE),
    re.compile(r"\bAC\s(\d{1,3}[-.]\d+[A-Z]?)\b"),
)

# Deliberately narrow. A wrong revision_date is worse than a null one, and the
# field is informational. Most Phase 1 documents will resolve to null; the
# reliable cases are ACs and ACS where the letter is inside the number already.
REVISION_DATE_PATTERNS = (
    re.compile(r"\bDate[d]?[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})\b", re.IGNORECASE),
    re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b"),
    re.compile(
        r"\b((?:January|February|March|April|May|June|July|August|September"
        r"|October|November|December)\s+\d{4})\b"),
)


def extract_metadata(data):
    """Return (pages, faa_number, faa_number_source, revision_date).

    Never raises on a malformed PDF; a document we cannot parse yields nulls
    and a page count of None rather than failing the run.
    """
    try:
        import fitz
    except ImportError:
        return None, None, None, None

    try:
        document = fitz.open(stream=data, filetype="pdf")
    except Exception:
        return None, None, None, None

    try:
        pages = document.page_count

        meta_blob = " ".join(
            str(v) for v in (document.metadata or {}).values() if v)
        number = _first_number(meta_blob)
        source = "metadata" if number else None

        first_page_text = ""
        if pages:
            try:
                first_page_text = document.load_page(0).get_text("text") or ""
            except Exception:
                first_page_text = ""

        if not number:
            number = _first_number(first_page_text)
            source = "firstpage" if number else None

        revision = _first_revision_date(first_page_text)
        return pages, number, source, revision
    finally:
        document.close()


def _first_number(text):
    if not text:
        return None
    for pattern in FAA_NUMBER_PATTERNS:
        match = pattern.search(text)
        if match:
            if match.groups():
                return ("AC " + match.group(1)).strip()
            return match.group(0).strip()
    return None


def _first_revision_date(text):
    if not text:
        return None
    head = text[:4000]
    for pattern in REVISION_DATE_PATTERNS:
        match = pattern.search(head)
        if match:
            return match.group(1).strip()
    return None


def looks_like_pdf(data):
    """The real gate. Content type is recorded but never enforced."""
    return bool(data) and data[:len(PDF_MAGIC)] == PDF_MAGIC
