"""Write release notes from what actually changed, not from a template.

BUILD-PLAN section 7 says the notes come from the `sources.lock.yaml` diff:
which documents changed revision, which CFR parts were amended, the AIM change
number, and the crosswalk delta. Everything here is derived, so a release note
cannot claim a change that did not happen.

`sha256` is the only load-bearing field in the lock, so it is what decides
whether a document counts as changed. A document whose `pages` moved but whose
hash did not has not changed; that is re-extraction noise.

    --previous PATH   the lock from the last release, usually from the release
                      asset. Without it every document reads as new.
    --version TAG     the version being cut

Exits 1 when nothing changed, which is what stops the quarterly floor build
from cutting an empty release.
"""

import argparse
import csv
import io
import json
import pathlib
import sys

import yaml

import _manifest as M

EXIT_OK = 0
EXIT_NO_CHANGE = 1

CFR_LOCK = M.ROOT / "manifest" / "cfr.lock.yaml"
CROSSWALK = M.ROOT / "crosswalk"


def load_lock_file(path):
    path = pathlib.Path(path)
    if not path.is_file():
        return {}
    with io.open(path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data.get("sources", data) or {}


def load_cfr(path):
    path = pathlib.Path(path)
    if not path.is_file():
        return {}
    with io.open(path, encoding="utf-8") as handle:
        return (yaml.safe_load(handle) or {}).get("parts", {}) or {}


def crosswalk_rows(root=CROSSWALK):
    """Row count per certificate, and how many are verified."""
    out = {}
    for path in sorted(pathlib.Path(root).glob("*.csv")):
        with io.open(path, encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        out[path.stem] = (len(rows),
                          sum(1 for r in rows if r.get("confidence") == "verified"))
    return out


def diff_sources(previous, current):
    """(added, removed, changed). Changed means the sha256 moved."""
    added = sorted(set(current) - set(previous))
    removed = sorted(set(previous) - set(current))
    changed = []
    for key in sorted(set(previous) & set(current)):
        before = (previous[key] or {}).get("sha256")
        after = (current[key] or {}).get("sha256")
        if before and after and before != after:
            changed.append((key, before, after))
    return added, removed, changed


def diff_cfr(previous, current):
    moved = []
    for key in sorted(set(previous) & set(current)):
        before = (previous[key] or {}).get("amended_on")
        after = (current[key] or {}).get("amended_on")
        if before and after and before != after:
            moved.append((key, before, after))
    return moved


def describe(entry):
    """A human line for a document, from the lock's own fields."""
    bits = [entry.get("faa_number"), entry.get("revision_date")]
    pages = entry.get("pages")
    if pages:
        bits.append("%d pp" % pages)
    return ", ".join(b for b in bits if b) or "no revision stated"


def render(version, previous, current, prev_cfr, cur_cfr, crosswalk, entries,
           total_pages=None, size_bytes=None, digest=None):
    added, removed, changed = diff_sources(previous, current)
    cfr_moved = diff_cfr(prev_cfr, cur_cfr)
    titles = {e["id"]: e.get("title") or e["id"] for e in entries}

    lines = ["## PDFlight %s" % version, ""]

    facts = []
    if total_pages:
        facts.append("%d pages" % total_pages)
    if size_bytes:
        facts.append("%.0f MB" % (size_bytes / 1048576.0))
    if cur_cfr:
        current_date = max(
            (e.get("amended_on") for e in cur_cfr.values() if e.get("amended_on")),
            default=None)
        if current_date:
            facts.append("14 CFR current %s" % current_date)
    if facts:
        lines.append(" | ".join(facts))
        lines.append("")

    if not (added or removed or changed or cfr_moved):
        lines.append("No source document changed since the previous release. "
                     "This is a scheduled rebuild.")
        lines.append("")

    if changed:
        lines.append("### Documents revised")
        lines.append("")
        for key, _before, _after in changed:
            lines.append("- **%s** (`%s`): %s"
                         % (titles.get(key, key), key, describe(current[key])))
        lines.append("")

    if added:
        lines.append("### Documents added")
        lines.append("")
        for key in added:
            lines.append("- **%s** (`%s`): %s"
                         % (titles.get(key, key), key, describe(current[key])))
        lines.append("")

    if removed:
        lines.append("### Documents removed")
        lines.append("")
        for key in removed:
            lines.append("- `%s`" % key)
        lines.append("")

    if cfr_moved:
        lines.append("### Regulations amended")
        lines.append("")
        for key, before, after in cfr_moved:
            lines.append("- `%s`: %s to %s" % (key, before, after))
        lines.append("")

    if crosswalk:
        lines.append("### Crosswalk")
        lines.append("")
        lines.append("| Certificate | Rows | Verified |")
        lines.append("|---|---|---|")
        for name in sorted(crosswalk):
            rows, verified = crosswalk[name]
            lines.append("| %s | %d | %d |" % (name, rows, verified))
        lines.append("")

    if digest:
        lines.append("### Verify")
        lines.append("")
        lines.append("```")
        lines.append("%s  pdflight.pdf" % digest)
        lines.append("```")
        lines.append("")

    lines.append("Unofficial. Not an FAA product and not a substitute for the "
                 "official source documents. Verify currency before "
                 "operational use.")
    return "\n".join(lines) + "\n", bool(added or removed or changed or cfr_moved)


def run(argv, lock_path=M.LOCK, cfr_lock_path=CFR_LOCK, out=sys.stdout):
    parser = argparse.ArgumentParser(
        prog="release_notes.py",
        description="Render release notes from the lock diff.")
    parser.add_argument("--previous", help="lock file from the last release")
    parser.add_argument("--previous-cfr", help="cfr lock from the last release")
    parser.add_argument("--version", default="unreleased")
    parser.add_argument("--pdf", help="the built PDF, for page count and size")
    parser.add_argument("--digest", help="SHA-256 of the built PDF")
    parser.add_argument("--output", help="write here instead of stdout")
    args = parser.parse_args(argv)

    current = load_lock_file(lock_path)
    previous = load_lock_file(args.previous) if args.previous else {}
    cur_cfr = load_cfr(cfr_lock_path)
    prev_cfr = load_cfr(args.previous_cfr) if args.previous_cfr else {}

    total_pages = size_bytes = None
    if args.pdf and pathlib.Path(args.pdf).is_file():
        size_bytes = pathlib.Path(args.pdf).stat().st_size
        try:
            import pymupdf

            document = pymupdf.open(args.pdf)
            total_pages = document.page_count
            document.close()
        except Exception:
            total_pages = None

    body, changed = render(
        args.version, previous, current, prev_cfr, cur_cfr,
        crosswalk_rows(), M.load_sources(), total_pages, size_bytes,
        args.digest)

    if args.output:
        with io.open(args.output, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(body)
        out.write("wrote %s\n" % args.output)
    else:
        out.write(body)
    return EXIT_OK if changed else EXIT_NO_CHANGE


def main(argv):
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
