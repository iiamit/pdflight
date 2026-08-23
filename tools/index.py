"""Extract outlines and page text from the source corpus into an anchor index.

CLAUDE.md section 8 says "FAA handbooks ship with bookmarks. This covers most
anchors." Measured across the 40 cached documents, that is optimistic in three
specific ways, and this tool exists to record which, per document, so the
resolver can pick a strategy that will actually work.

**Presence is not usability.** PHAK carries 7,689 outline entries and almost
none of them anchor anything: the top level is filenames like
`03_phak_ch1.pdf`, the second level is "Structure Bookmarks" repeated, and a
large share resolve to page -1. They are tagged-PDF structure elements leaking
into the outline from a per-chapter assembly. An outline that exists can still
be worthless, so every entry is scored.

**Some documents have no outline at all.** IFH, 371 pages and central to the
Instrument crosswalk, has none. Neither does Plane Sense or the Seaplane
handbook.

**Some have no text either.** Plane Sense is a scan with no text layer, so
strategies 2 and 3 both fail and only a pinned page can anchor it.

The index also marks table-of-contents pages. IFH's chapter titles appear as
dot-leadered TOC lines long before the chapters themselves, so a regex that
does not skip those anchors every chapter to the contents page.
"""

import argparse
import io
import json
import pathlib
import re
import sys

import _manifest as M

EXIT_OK = 0
EXIT_PROBLEM = 1

INDEX = M.ROOT / "cache" / "index"

# Outline titles that anchor nothing. Seen in PHAK, whose outline is built from
# tagged-PDF structure rather than headings.
JUNK_TITLE = re.compile(
    r"^\s*(?:structure\s+bookmarks?|figure|table|untitled|bookmarks?)\s*$|"
    r"^\s*\d+[-_][\w-]*\.pdf\s*$|"          # 03_phak_ch1.pdf
    r"^\s*[\d]+-[\d]+\s*$|"                  # 1-1, a page number
    r"^\s*$",
    re.IGNORECASE)

# A run of dots is a table-of-contents leader.
DOT_LEADER = re.compile(r"\.{5,}")


# Density alone is the wrong discriminator, and using it rejected every
# Advisory Circular. ACs legitimately run 5 to 7 outline entries per page
# because each numbered paragraph is a bookmark, which is precisely the
# granularity `ac:61-65K:para-14` needs. PHAK runs 14.7, so the ratio only
# helps at an extreme.
STRUCTURE_NOISE_RATIO = 10.0

# What actually distinguishes PHAK is the fingerprint of a tagged-PDF outline
# assembled from per-chapter files: source filenames at the top level, literal
# "Structure Bookmarks" containers, and a large share of entries that resolve
# to no page at all.
FILENAME_TITLE = re.compile(r"^\s*[\w-]+\.pdf\s*$", re.IGNORECASE)
STRUCTURE_MARKER = re.compile(
    r"^\s*(?:structure\s+bookmarks?|document|article|sect|span)\s*$",
    re.IGNORECASE)

# A pageless-entry fraction is deliberately NOT a disqualifier. Five ACs carry
# 11 to 19 percent entries with no page, and every remaining entry in them is a
# good paragraph heading. usable_entry already drops those individually;
# condemning the whole outline for them threw away the best anchors in the
# corpus. PHAK, by contrast, is only 0.3 percent pageless and is still noise.


def usable_entry(level, title, page):
    if page is None or page < 1:
        return False
    return not JUNK_TITLE.match(title or "")


def outline_is_structural_noise(outline, pages):
    """True when the outline is tagged-PDF structure rather than headings."""
    if not outline or not pages:
        return False

    titles = [entry["title"] or "" for entry in outline]
    if any(FILENAME_TITLE.match(t) for t in titles):
        return True
    if sum(1 for t in titles if STRUCTURE_MARKER.match(t)) >= 3:
        return True

    return len(outline) / pages > STRUCTURE_NOISE_RATIO


def normalize(title):
    """Case fold, strip punctuation, collapse whitespace.

    The normalisation CLAUDE.md section 8 specifies for outline matching.
    """
    text = re.sub(r"[^\w\s]+", " ", (title or "").lower())
    return " ".join(text.split())


# Not every contents page uses dot leaders. AFH's does not, and relying on
# leaders alone left its contents pages unflagged, where a "Chapter N" regex
# matches chapters 1 through 9 within five pages of each other. The second
# signal is a run of lines ending in a page reference, "7-1" or "142".
TOC_ENTRY_LINE = re.compile(r"(?m)^.{4,90}?\s+\d{1,3}(?:-\d{1,3})?\s*$")


def is_toc_page(text):
    """A contents page, which must not satisfy a content anchor."""
    if not text:
        return False
    if len(DOT_LEADER.findall(text)) >= 4:
        return True
    return len(TOC_ENTRY_LINE.findall(text)) >= 8


def index_document(key, path, keep_text=True):
    import pymupdf

    document = pymupdf.open(path)
    try:
        outline = []
        for level, title, page in document.get_toc():
            outline.append({
                "level": level,
                "title": " ".join((title or "").split()),
                "norm": normalize(title),
                "page": page,
                "usable": usable_entry(level, title, page),
            })

        pages, toc_pages, empty = [], [], 0
        for number in range(document.page_count):
            text = document.load_page(number).get_text("text") or ""
            if len(text.strip()) < 40:
                empty += 1
            if is_toc_page(text):
                toc_pages.append(number + 1)
            pages.append(text if keep_text else "")

        noise = outline_is_structural_noise(outline, document.page_count)
        if noise:
            # Every entry is disqualified, not just the ones that look odd.
            # PHAK's individually-plausible titles are collectively worthless.
            for entry in outline:
                entry["usable"] = False
        usable = [entry for entry in outline if entry["usable"]]
        return {
            "id": key,
            "pages": document.page_count,
            "outline_total": len(outline),
            "outline_usable": len(usable),
            "outline_structural_noise": noise,
            "outline": outline,
            "toc_pages": toc_pages,
            "pages_without_text": empty,
            "has_text_layer": empty < document.page_count * 0.5,
            "page_text": pages,
        }
    finally:
        document.close()


def summarize(record):
    total = record["outline_total"]
    usable = record["outline_usable"]
    if not record["has_text_layer"]:
        return "no text layer, pin only"
    if record.get("outline_structural_noise"):
        return "outline is structure noise, regex"
    if usable >= 8:
        return "outline usable"
    if not total:
        return "no outline, regex"
    return "outline thin, regex"


def run(argv, out=sys.stdout, index_root=INDEX, lock_path=M.LOCK,
        cache_root=M.CACHE):
    parser = argparse.ArgumentParser(
        prog="index.py",
        description="Build the anchor index from cached source PDFs.")
    parser.add_argument("--id", action="append", help="limit to specific ids")
    parser.add_argument("--summary", action="store_true",
                        help="report strategy per document and write nothing")
    args = parser.parse_args(argv)

    lock = M.load_lock(lock_path)
    if not lock:
        out.write("sources.lock.yaml is empty. Run make fetch-update.\n")
        return EXIT_OK

    keys = sorted(lock)
    if args.id:
        wanted = set(args.id)
        keys = [k for k in keys if k in wanted]

    index_root = pathlib.Path(index_root)
    if not args.summary:
        index_root.mkdir(parents=True, exist_ok=True)

    out.write("%-26s %6s %8s %8s  %s\n"
              % ("id", "pages", "outline", "usable", "strategy"))
    out.write("-" * 74 + "\n")

    problems, records = [], []
    for key in keys:
        blob = M.cache_path(lock[key]["sha256"], cache_root)
        if not blob.is_file():
            problems.append("%s: not in cache" % key)
            continue
        record = index_document(key, blob, keep_text=not args.summary)
        records.append(record)
        verdict = summarize(record)
        out.write("%-26s %6d %8d %8d  %s\n" % (
            key, record["pages"], record["outline_total"],
            record["outline_usable"], verdict))

        if not args.summary:
            target = index_root / ("%s.json" % key)
            with io.open(target, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(record, handle, ensure_ascii=False)

    scanned = [r["id"] for r in records if not r["has_text_layer"]]
    junk = [r["id"] for r in records if r.get("outline_structural_noise")]
    none = [r["id"] for r in records if not r["outline_total"]]

    out.write("\n%d document(s) indexed.\n" % len(records))
    out.write("  outline usable : %d\n"
              % len([r for r in records if r["outline_usable"] >= 8]))
    out.write("  structure noise: %d  %s\n" % (len(junk), ", ".join(junk) or "-"))
    out.write("  no outline     : %d  %s\n" % (len(none), ", ".join(none) or "-"))
    out.write("  no text layer  : %d  %s\n"
              % (len(scanned), ", ".join(scanned) or "-"))

    for line in problems:
        out.write("  %s\n" % line)
    return EXIT_PROBLEM if problems else EXIT_OK


def load_index(key, index_root=INDEX):
    path = pathlib.Path(index_root) / ("%s.json" % key)
    if not path.is_file():
        return None
    with io.open(path, encoding="utf-8") as handle:
        return json.load(handle)


def main(argv):
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
