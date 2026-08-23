"""Resolve logical anchor refs to pages, and write anchors/anchors.lock.json.

Four strategies, in the priority CLAUDE.md section 8 sets out:

    1. native   a destination the build already emitted. Deterministic, zero
                maintenance. Every 14 CFR and 49 CFR section is here.
    2. outline  match a normalised bookmark title. Works for 30 of the 40
                source documents.
    3. regex    search extracted page text with an expected ordinal. Needed
                wherever the outline is missing or is tagged-PDF noise, which
                includes PHAK and IFH, the two most important handbooks.
    4. pinned   a literal page number. Warns on every run, by design.

The lock is committed and diffable. When a rebuild moves an anchor from one
page to another the diff shows it, and when an anchor stops resolving the build
fails rather than shipping a link into the wrong page.

Table-of-contents pages are excluded from regex matching. IFH lists every
chapter title with dot leaders on page 12 long before chapter one begins, so a
regex that does not skip contents pages anchors the entire handbook to its own
table of contents.
"""

import argparse
import io
import json
import pathlib
import re
import sys

import yaml

import _manifest as M
import index as IX

EXIT_OK = 0
EXIT_UNRESOLVED = 1

PATTERNS = M.ROOT / "anchors" / "patterns.yaml"
ANCHORS_LOCK = M.ROOT / "anchors" / "anchors.lock.json"
CFR_PDF = M.ROOT / "build" / "cfr" / "cfr.pdf"

CFR_REF = re.compile(r"^(\d+)cfr:(.+)$")


def load_patterns(path=PATTERNS):
    with io.open(path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data or {}


def native_destinations(pdf=CFR_PDF):
    """Named destinations already present in a generated PDF."""
    path = pathlib.Path(pdf)
    if not path.is_file():
        return {}
    import pymupdf

    document = pymupdf.open(path)
    try:
        return {name: info.get("page") for name, info in
                document.resolve_names().items()}
    finally:
        document.close()


def resolve_native(ref, natives):
    match = CFR_REF.match(ref)
    if not match:
        return None
    import _cfr

    label = _cfr.label_for(match.group(2))
    if label in natives:
        # resolve_names is zero-based; anchors are one-based like every other
        # page number in this project.
        return {"strategy": "native", "page": natives[label] + 1,
                "doc": "cfr", "evidence": label}
    return None


def resolve_outline(spec, record):
    if not record or record.get("outline_structural_noise"):
        return None
    wanted = IX.normalize(spec.get("match", ""))
    if not wanted:
        return None
    hits = [entry for entry in record["outline"]
            if entry["usable"] and entry["norm"] == wanted]
    if not hits:
        hits = [entry for entry in record["outline"]
                if entry["usable"] and entry["norm"].startswith(wanted)]
    if not hits:
        return None
    ordinal = int(spec.get("ordinal", 1))
    if ordinal > len(hits):
        return None
    entry = hits[ordinal - 1]
    return {"strategy": "outline", "page": entry["page"],
            "doc": spec["doc"], "evidence": entry["title"][:120]}


def resolve_regex(spec, record):
    if not record:
        return None
    pattern = spec.get("pattern")
    if not pattern:
        return None
    compiled = re.compile(pattern, re.MULTILINE)
    skip = set(record.get("toc_pages") or [])
    ordinal = int(spec.get("ordinal", 1))

    found = 0
    for number, text in enumerate(record["page_text"], start=1):
        if number in skip or not text:
            continue
        match = compiled.search(text)
        if not match:
            continue
        found += 1
        if found == ordinal:
            excerpt = " ".join(match.group(0).split())[:120]
            return {"strategy": "regex", "page": number,
                    "doc": spec["doc"], "evidence": excerpt}
    return None


def resolve_pinned(spec):
    page = spec.get("page")
    if not spec.get("pinned") or not page:
        return None
    return {"strategy": "pinned", "page": int(page), "doc": spec["doc"],
            "evidence": "pinned by hand"}


def resolve_one(ref, spec, natives, indexes):
    """Try each strategy in priority order and report which one answered."""
    native = resolve_native(ref, natives)
    if native:
        return native

    record = indexes.get(spec.get("doc"))
    order = spec.get("strategy")
    attempts = []
    if order == "outline":
        attempts = [resolve_outline, resolve_regex]
    elif order == "regex":
        attempts = [resolve_regex, resolve_outline]
    else:
        attempts = [resolve_outline, resolve_regex]

    for attempt in attempts:
        found = attempt(spec, record)
        if found:
            return found

    fallback = spec.get("fallback")
    if fallback:
        merged = dict(spec)
        merged.update(fallback)
        for attempt in (resolve_outline, resolve_regex):
            found = attempt(merged, record)
            if found:
                found["strategy"] += " (fallback)"
                return found

    return resolve_pinned(spec)


HEADER_NOTE = ("Written by tools/resolve.py. Committed so a page move shows up "
               "as a diff. Do not hand-edit.")


def dump_lock(resolved, path=ANCHORS_LOCK):
    payload = {"_note": HEADER_NOTE,
               "anchors": {ref: resolved[ref] for ref in sorted(resolved)}}
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")


def run(argv, patterns_path=PATTERNS, lock_path=ANCHORS_LOCK, cfr_pdf=CFR_PDF,
        index_root=IX.INDEX, out=sys.stdout):
    parser = argparse.ArgumentParser(
        prog="resolve.py",
        description="Resolve anchor refs to pages and write anchors.lock.json.")
    parser.add_argument("--check", action="store_true",
                        help="resolve and compare against the lock, write nothing")
    args = parser.parse_args(argv)

    specs = load_patterns(patterns_path)
    if not specs:
        out.write("anchors/patterns.yaml is empty. Nothing to resolve.\n")
        return EXIT_OK

    natives = native_destinations(cfr_pdf)
    out.write("%d native destination(s) available from the CFR build\n\n"
              % len(natives))

    indexes, resolved, unresolved, pinned = {}, {}, [], []
    for ref in sorted(specs):
        spec = specs[ref] or {}
        doc = spec.get("doc")
        if doc and doc not in indexes:
            indexes[doc] = IX.load_index(doc, index_root)

        found = resolve_one(ref, spec, natives, indexes)
        if not found:
            unresolved.append(ref)
            continue
        resolved[ref] = found
        if found["strategy"] == "pinned":
            pinned.append(ref)

    by_strategy = {}
    for entry in resolved.values():
        by_strategy[entry["strategy"]] = by_strategy.get(entry["strategy"], 0) + 1
    for name in sorted(by_strategy):
        out.write("  %-20s %d\n" % (name, by_strategy[name]))

    if pinned:
        out.write("\n%d pinned anchor(s), which will not survive a repagination:\n"
                  % len(pinned))
        for ref in pinned:
            out.write("  %s -> page %d\n" % (ref, resolved[ref]["page"]))

    if unresolved:
        out.write("\n%d unresolved:\n" % len(unresolved))
        for ref in unresolved:
            out.write("  %s\n" % ref)

    if args.check:
        previous = {}
        if pathlib.Path(lock_path).is_file():
            with io.open(lock_path, encoding="utf-8") as handle:
                previous = json.load(handle).get("anchors", {})
        moved = [ref for ref in resolved
                 if ref in previous and previous[ref]["page"] != resolved[ref]["page"]]
        for ref in moved:
            out.write("  moved: %s page %s -> %s\n"
                      % (ref, previous[ref]["page"], resolved[ref]["page"]))
        out.write("\n%d resolved, %d moved, %d unresolved\n"
                  % (len(resolved), len(moved), len(unresolved)))
        return EXIT_UNRESOLVED if (unresolved or moved) else EXIT_OK

    dump_lock(resolved, lock_path)
    out.write("\n%d anchor(s) resolved. Wrote %s\n"
              % (len(resolved), pathlib.Path(lock_path).name))
    return EXIT_UNRESOLVED if unresolved else EXIT_OK


def main(argv):
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
