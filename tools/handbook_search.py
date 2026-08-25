"""Search a handbook's extracted text and report which chapter holds the hits.

The refinement passes propose a chapter anchor per ACS element. Proposing one
from a remembered chapter number is how AFH-3C's inserted Energy Management
chapter silently shifts every later proposal by one. This grounds the choice:
search the text this build actually extracted, then report the anchor whose
page range contains each hit.

    python tools/handbook_search.py phak "wake turbulence"
    python tools/handbook_search.py aim "lost communication" --limit 8

An anchor is only reported if it resolved into `anchors.lock.json`, so a hit
in an unanchored stretch of a document reports as `(no anchor above)` rather
than being attached to the nearest chapter that happens to have one.
"""

import argparse
import bisect
import collections
import io
import json
import os
import re
import sys

import _manifest as M

EXIT_OK = 0
EXIT_PROBLEM = 1

ANCHORS = M.ROOT / "anchors" / "anchors.lock.json"
TITLES = M.ROOT / "anchors" / "chapter-titles.json"


def spans(doc):
    """Anchor start pages for one document, ascending, grouped by page.

    Several anchors routinely begin on one page: the Seaplane handbook starts
    EMERGENCY LANDING, GO-AROUND and POSTFLIGHT PROCEDURES on page 28. Keeping
    only one of them would credit every hit on that page to whichever sorted
    last, which reads as an anchor landing in the wrong place when it is the
    search that cannot tell them apart. Report the whole group and let the
    reader choose by title.
    """
    anchors = json.load(io.open(ANCHORS, encoding="utf-8"))["anchors"]
    titles = json.load(io.open(TITLES, encoding="utf-8"))
    pages = collections.OrderedDict()
    for ref, entry in sorted(anchors.items()):
        if entry.get("doc") != doc:
            continue
        page = entry.get("page")
        if not page:
            continue
        label = titles.get(ref) or (entry.get("evidence") or "").strip()
        pages.setdefault(page, []).append((ref, label))
    found = []
    for page in sorted(pages):
        group = pages[page]
        found.append((page,
                      " | ".join(ref for ref, _label in group),
                      " | ".join(label for _ref, label in group)))
    return found


def owner(found, page):
    """The anchor group whose range contains `page`."""
    pages = [p for p, _r, _t in found]
    position = bisect.bisect_right(pages, page) - 1
    if position < 0:
        return None
    return found[position]


def search(doc, pattern, limit, case_sensitive=False):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import index as IX

    record = IX.load_index(doc)
    if not record:
        return None, "no index record for %s. Run make index" % doc
    pages = record.get("page_text") or []
    if not pages:
        return None, "%s has no extracted text" % doc

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        matcher = re.compile(pattern, flags)
    except re.error as error:
        return None, "bad pattern: %s" % error

    found = spans(doc)
    hits = collections.OrderedDict()
    for number, text in enumerate(pages, 1):
        if not text or not matcher.search(text):
            continue
        anchor = owner(found, number)
        key = anchor[1] if anchor else "(no anchor above)"
        if anchor is not None and anchor[0] == found[-1][0]:
            # Nothing bounds the last anchor, so a document's back matter
            # lands in it. PHAK ends at Aeromedical Factors, which is why a
            # search for "circling approach" reports 8 hits there: they are
            # glossary entries. Say so rather than let the count read as
            # coverage.
            key = "%s  [unbounded, includes any back matter]" % key
        record_hit = hits.setdefault(key, {"title": anchor[2] if anchor else "",
                                           "pages": [], "count": 0})
        record_hit["count"] += len(matcher.findall(text))
        if len(record_hit["pages"]) < limit:
            record_hit["pages"].append(number)
    return hits, None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("doc", help="document id, for example phak or aim")
    parser.add_argument("pattern", help="regular expression")
    parser.add_argument("--limit", type=int, default=6,
                        help="page numbers to list per anchor")
    parser.add_argument("--case-sensitive", action="store_true")
    args = parser.parse_args(argv)

    hits, problem = search(args.doc, args.pattern, args.limit,
                           args.case_sensitive)
    if problem:
        print(problem, file=sys.stderr)
        return EXIT_PROBLEM
    if not hits:
        print("no hit for %r in %s" % (args.pattern, args.doc))
        return EXIT_OK

    ranked = sorted(hits.items(), key=lambda kv: -kv[1]["count"])
    for ref, entry in ranked:
        print("%-4d hit(s)  pages %-22s  %s"
              % (entry["count"], ",".join(str(p) for p in entry["pages"]),
                 ref))
        if entry["title"]:
            print("             %s" % entry["title"][:96])
    return EXIT_OK


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    raise SystemExit(main())
