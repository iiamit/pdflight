"""Build the work packets the handbook refinement passes consume.

The first sweep built its packets by hand in a scratch directory, so the
proposals under `crosswalk/proposals/` were reproducible but the questions
that produced them were not. That mattered the moment the References parser
was fixed: the wrapped-line bug had hidden documents from whole Tasks, and
rebuilding the affected packets meant reconstructing them from memory.

A packet carries, per element, the element text, the documents the ACS
References line actually names, and the chapter anchors available for each of
those documents. Nothing else. An anchor absent from `anchors.lock.json` did
not resolve to a page in this build and must never be proposed, which is the
rule `refine_handbooks.py` enforces on the way back in.

    python tools/refine_packets.py atp --split 5
    python tools/refine_packets.py instrument --split 4
"""

import argparse
import collections
import csv
import io
import json
import os
import pathlib
import sys

import _manifest as M

EXIT_OK = 0
EXIT_PROBLEM = 1

CROSSWALK = M.ROOT / "crosswalk"
PACKETS = CROSSWALK / "proposals" / "packets"
ANCHORS = M.ROOT / "anchors" / "anchors.lock.json"
TITLES = M.ROOT / "anchors" / "chapter-titles.json"

# The documents a handbook pass may narrow. The AIM is here because it is
# anchored by chapter and section like a handbook, whatever the menu calls it.
REFINABLE = (
    "phak", "afh", "ifh", "iph", "risk-management", "aviation-weather",
    "weight-balance", "aviation-instructor", "seaplane", "plane-sense",
    "aim",
)

LETTERS = "abcdefghijklmnopqrstuvwxyz"


def anchor_menu():
    """Every resolved anchor, per document, with the best title available.

    `chapter-titles.json` carries a real chapter title where one was
    recovered. Where it does not, the anchor's own `evidence` string is what
    the outline or the page text actually said, which is worse prose and
    still enough to choose by.
    """
    anchors = json.load(io.open(ANCHORS, encoding="utf-8"))["anchors"]
    titles = json.load(io.open(TITLES, encoding="utf-8"))
    menu = collections.OrderedDict()
    for ref in sorted(anchors):
        doc = ref.split(":")[0]
        if doc not in REFINABLE:
            continue
        label = titles.get(ref) or (anchors[ref].get("evidence") or "").strip()
        menu.setdefault(doc, collections.OrderedDict())[ref] = label
    return menu


def elements(certificate):
    """Element code to text, referenced documents, and current anchors.

    A refined row replaces the document-level row it came from, so reading
    only document-level rows loses every document an earlier pass already
    narrowed. The reference set is therefore the union: documents still
    unrefined, plus the document each existing chapter anchor belongs to. A
    packet that showed only the remainder would read as though the ACS never
    cited the IFH for an approach Task.
    """
    path = CROSSWALK / ("%s.csv" % certificate)
    rows = list(csv.DictReader(io.open(path, encoding="utf-8", newline="")))
    out = collections.OrderedDict()
    for row in rows:
        code = row["source_ref"]
        entry = out.setdefault(code, {"text": row.get("element_text") or "",
                                      "docs": [], "current": []})
        target = row["target_ref"]
        doc = target.split(":")[0]
        if doc in REFINABLE:
            if doc not in entry["docs"]:
                entry["docs"].append(doc)
            if ":" in target and target not in entry["current"]:
                entry["current"].append(target)
        if not entry["text"]:
            entry["text"] = row.get("element_text") or ""
    for entry in out.values():
        entry["docs"].sort()
        entry["current"].sort()
    return out


def areas(codes):
    """Group element codes by Area of Operation, keeping ACS order."""
    grouped = collections.OrderedDict()
    for code in codes:
        parts = code.split(".")
        grouped.setdefault(parts[1] if len(parts) > 1 else "?", []).append(code)
    return grouped


def split(grouped, count):
    """Cut the areas into `count` packets of roughly equal element count.

    Areas are never split across packets. An Area is one coherent subject and
    an agent that sees all of it proposes better chapters than one that sees
    half.
    """
    total = sum(len(v) for v in grouped.values())
    target = total / float(count)
    packets, current, size = [], [], 0
    for area, codes in grouped.items():
        if current and size + len(codes) > target * 1.35 and \
                len(packets) < count - 1:
            packets.append(current)
            current, size = [], 0
        current.append((area, codes))
        size += len(codes)
    if current:
        packets.append(current)
    return packets


def write(certificate, count, root=PACKETS):
    menu = anchor_menu()
    found = elements(certificate)
    grouped = areas(found)
    root = pathlib.Path(root)
    root.mkdir(parents=True, exist_ok=True)

    written = []
    for number, packet in enumerate(split(grouped, count)):
        name = "%s-%s" % (certificate, LETTERS[number])
        items = collections.OrderedDict()
        docs = set()
        for _area, codes in packet:
            for code in codes:
                entry = found[code]
                items[code] = collections.OrderedDict((
                    ("text", " ".join(entry["text"].split())),
                    ("references", entry["docs"]),
                    ("current", entry["current"]),
                ))
                docs.update(entry["docs"])
        body = collections.OrderedDict()
        body["certificate"] = certificate
        body["packet"] = name
        body["areas"] = [area for area, _codes in packet]
        body["anchor_menu"] = collections.OrderedDict(
            (doc, menu.get(doc, {})) for doc in sorted(docs))
        body["elements"] = items
        path = root / ("%s.json" % name)
        with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(body, handle, indent=1, ensure_ascii=False)
            handle.write("\n")
        written.append((name, [a for a, _c in packet], len(items),
                        sorted(docs)))
    return written


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("certificate")
    parser.add_argument("--split", type=int, default=4,
                        help="how many packets to cut the certificate into")
    args = parser.parse_args(argv)

    path = CROSSWALK / ("%s.csv" % args.certificate)
    if not path.is_file():
        print("no crosswalk for %s" % args.certificate, file=sys.stderr)
        return EXIT_PROBLEM

    for name, area_list, count, docs in write(args.certificate, args.split):
        print("%-14s areas %-22s %4d element(s)  %s"
              % (name, ",".join(area_list), count, " ".join(docs)))
    return EXIT_OK


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    raise SystemExit(main())
