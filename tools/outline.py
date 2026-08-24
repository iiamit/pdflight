"""Build the three-level bookmark tree.

Validation gate 6 requires depth of exactly three with no orphan nodes, so the
levels are fixed:

    1  section        Standards. Handbooks. Regulations.
    2  document       PHAK, or a single CFR part
    3  anchor         a chapter, or a CFR section

The regulations do not get a "14 CFR" node of their own at level 2. If they
did, parts would sit at level 3 and the 849 sections at level 4, which breaks
the gate. Putting each part at level 2 keeps every section reachable at level 3,
which is the level a reader actually navigates by.

Bookmarks are the only navigation many readers expose for a 6,000 page file, so
this is not decoration. Annotation apps that strip link annotations usually keep
the outline.
"""

import argparse
import hashlib
import io
import json
import pathlib
import sys

import _manifest as M

EXIT_OK = 0
EXIT_PROBLEM = 1

BUILD = M.ROOT / "build"
LINKED = BUILD / "pdflight-linked.pdf"
OUTLINED = BUILD / "pdflight-outlined.pdf"
OFFSETS = BUILD / "offsets.json"
ABSOLUTE = BUILD / "anchors-absolute.json"
CFR_PDF = BUILD / "cfr" / "cfr.pdf"


def anchors_by_doc(path=ABSOLUTE):
    if not pathlib.Path(path).is_file():
        return {}
    with io.open(path, encoding="utf-8") as handle:
        anchors = json.load(handle).get("anchors", {})
    grouped = {}
    for ref, entry in anchors.items():
        grouped.setdefault(entry.get("doc"), []).append((ref, entry))
    for bucket in grouped.values():
        bucket.sort(key=lambda pair: pair[1]["page"])
    return grouped


def cfr_nodes(offsets, cfr_pdf=CFR_PDF):
    """Parts at level 2, sections at level 3, mapped to absolute pages."""
    record = offsets.get("cfr")
    path = pathlib.Path(cfr_pdf)
    if not record or not path.is_file():
        return []
    import pymupdf

    document = pymupdf.open(path)
    try:
        raw = document.get_toc()
    finally:
        document.close()

    start = record["start"]
    nodes = []
    for level, title, page in raw:
        if page is None or page < 1:
            continue
        absolute = start + page - 1
        # cfr.typ emits part=1, subpart=2, section=3, appendix=4. Subparts and
        # appendices are dropped rather than flattened, because promoting them
        # would put two different things at the same level and reading order
        # would stop matching the document.
        if level == 1:
            nodes.append((2, title, absolute))
        elif level == 3:
            nodes.append((3, title, absolute))
    return nodes


def build(offsets, entries, grouped, cfr):
    """Return a PyMuPDF-style toc: [level, title, page]."""
    import menus as menus_tool

    by_section = {}
    for entry in entries:
        by_section.setdefault(entry["section"], []).append(entry)
    for bucket in by_section.values():
        bucket.sort(key=lambda e: (e.get("order") or 0, e["id"]))

    toc = []
    for _number, key, name in menus_tool.SECTIONS:
        if key == "regs":
            if not cfr:
                continue
            record = offsets.get("cfr")
            toc.append([1, "%s." % name, record["start"]])
            toc.extend([level, title, page] for level, title, page in cfr)
            continue

        bucket = by_section.get(key)
        if not bucket:
            continue
        first = min((offsets[e["id"]]["start"] for e in bucket
                     if e["id"] in offsets), default=None)
        if first is None:
            continue
        toc.append([1, "%s." % name, first])
        for entry in bucket:
            record = offsets.get(entry["id"])
            if not record:
                continue
            toc.append([2, entry["title"], record["start"]])
            for ref, anchor in grouped.get(entry["id"], []):
                toc.append([3, ref, anchor["page"]])
    return toc


def problems(toc, total_pages):
    """Gate 6: depth exactly three, no orphans."""
    found = []
    depth = max((row[0] for row in toc), default=0)
    if depth != 3:
        found.append("outline depth is %d, gate 6 requires exactly 3" % depth)

    previous = 0
    for level, title, page in toc:
        if level > previous + 1:
            found.append("orphan: %r jumps from level %d to %d"
                         % (title[:40], previous, level))
        if page < 1 or page > total_pages:
            found.append("%r points at page %s of %d" % (title[:40], page,
                                                         total_pages))
        previous = level
    return found


def seed_for(offsets_path):
    """A content-derived seed for the trailer /ID.

    Rule 8 wants the id fixed, and section 6 wants everything version-like
    derived from content rather than from the build. The locks are exactly
    that: they change when a source changes and not otherwise.
    """
    parts = []
    for name in ("manifest/sources.lock.yaml", "manifest/cfr.lock.yaml"):
        path = M.ROOT / name
        if path.is_file():
            parts.append(path.read_bytes())
    path = pathlib.Path(offsets_path)
    if path.is_file():
        parts.append(path.read_bytes())
    return hashlib.sha256(b"".join(parts)).hexdigest()


def pin_output_id(path, seed):
    """Force the shipped file's trailer /ID to a content-derived constant.

    Reuses optimize.pin_id rather than reimplementing it, because that
    function already carries the hard-won detail: MuPDF regenerates the second
    /ID on every write and serialises it as a literal string when the random
    bytes happen to be printable, so a hex-only pattern misses about one save
    in twenty.
    """
    import optimize

    data = path.read_bytes()
    pinned = optimize.pin_id(data, seed)
    if pinned == data:
        return False
    path.write_bytes(pinned)
    return True


def run(argv, linked=LINKED, output=OUTLINED, offsets_path=OFFSETS,
        absolute=ABSOLUTE, cfr_pdf=CFR_PDF, out=sys.stdout):
    parser = argparse.ArgumentParser(
        prog="outline.py", description="Build the three-level bookmark tree.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    import pymupdf

    if not pathlib.Path(linked).is_file():
        out.write("build/pdflight-linked.pdf is missing. Run make link.\n")
        return EXIT_PROBLEM

    with io.open(offsets_path, encoding="utf-8") as handle:
        data = json.load(handle)
    offsets = data["offsets"]
    total = data["total_pages"]

    toc = build(offsets, M.load_sources(), anchors_by_doc(absolute),
                cfr_nodes(offsets, cfr_pdf))
    counts = {1: 0, 2: 0, 3: 0}
    for level, _t, _p in toc:
        counts[level] = counts.get(level, 0) + 1
    out.write("outline: %d node(s), %d section(s), %d document(s), %d anchor(s)\n"
              % (len(toc), counts.get(1, 0), counts.get(2, 0), counts.get(3, 0)))

    found = problems(toc, total)
    for line in found[:10]:
        out.write("  %s\n" % line)
    if found:
        out.write("%d outline problem(s)\n" % len(found))
        return EXIT_PROBLEM

    if args.dry_run:
        return EXIT_OK

    document = pymupdf.open(linked)
    document.set_toc(toc)

    # Rule 8 says fix the /ID and strip or pin the dates. Until now that only
    # happened in optimize.py, on the intermediate source copies, and never on
    # the artefact that actually ships. The first Linux build proved the cost:
    # same inputs, same PyMuPDF, same Typst, and a hash that differed from the
    # Windows build. Determinism is what lets the release job tell "nothing
    # changed" from "changed", so an unpinned output would eventually cut an
    # empty release or skip a real one.
    document.set_metadata({"producer": "PDFlight", "creator": "PDFlight",
                           "creationDate": "", "modDate": ""})
    document.save(str(output), garbage=3, deflate=True)
    document.close()

    stamped = pin_output_id(pathlib.Path(output), seed_for(offsets_path))
    size = pathlib.Path(output).stat().st_size
    out.write("%s: %.1f MB, depth 3, no orphans\n"
              % (pathlib.Path(output).name, size / 1048576))
    out.write("trailer /ID pinned to %s\n" % ("yes" if stamped else "NO, "
                                              "the pattern did not match"))
    return EXIT_OK


def main(argv):
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
