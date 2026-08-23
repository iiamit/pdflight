"""Generate the crosswalk review worklist and report progress.

The bootstrap gives every element the documents its Task cites, at
`confidence: auto`. Verification is the human half: narrow a document-level
target to a section anchor where one fits, confirm it, and mark the row
`verified`.

Two things make that tractable, and both are what this tool exists to supply.

**You can only refine to an anchor that exists.** `phak` can become
`phak:ch15` only because that anchor is in anchors.lock.json. Asking a reviewer
to invent `phak:ch15:airspace-class-b` when nothing resolves it produces a
crosswalk that fails the build. So every suggestion here is drawn from the
resolved anchor set.

**Review by Task, not by row.** A Task's elements share one References line, so
they share their targets. Deciding "for this Task, PHAK means chapter 15"
settles every element in it at once, which is the difference between 26,075
decisions and roughly 300.
"""

import argparse
import collections
import csv
import io
import json
import pathlib
import re
import sys

import _manifest as M

EXIT_OK = 0

CROSSWALK = M.ROOT / "crosswalk"
ANCHORS = M.ROOT / "anchors" / "anchors.lock.json"

TASK_OF = re.compile(r"^([A-Z]{2}\.[IVX]+\.[A-Z])\.")


def load_rows(name, root=CROSSWALK):
    path = pathlib.Path(root) / ("%s.csv" % name)
    if not path.is_file():
        return []
    with io.open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def anchors_by_document(path=ANCHORS):
    if not pathlib.Path(path).is_file():
        return {}
    with io.open(path, encoding="utf-8") as handle:
        anchors = json.load(handle).get("anchors", {})
    grouped = collections.defaultdict(list)
    for ref, entry in anchors.items():
        grouped[entry.get("doc")].append(ref)
    for bucket in grouped.values():
        bucket.sort()
    return grouped


def task_of(code):
    match = TASK_OF.match(code)
    return match.group(1) if match else code


def summarize(names, root=CROSSWALK):
    rows = []
    for name in names:
        data = load_rows(name, root)
        if not data:
            continue
        by_confidence = collections.Counter(r["confidence"] for r in data)
        tasks = {task_of(r["source_ref"]) for r in data}
        verified_tasks = {task_of(r["source_ref"]) for r in data
                          if r["confidence"] == "verified"}
        rows.append({
            "certificate": name,
            "rows": len(data),
            "elements": len({r["source_ref"] for r in data}),
            "tasks": len(tasks),
            "auto": by_confidence.get("auto", 0),
            "verified": by_confidence.get("verified", 0),
            "tasks_done": len(verified_tasks),
        })
    return rows


def worklist(name, anchors, limit, area=None, root=CROSSWALK):
    data = load_rows(name, root)
    by_task = collections.OrderedDict()
    for row in data:
        task = task_of(row["source_ref"])
        by_task.setdefault(task, {"rows": [], "targets": collections.OrderedDict()})
        by_task[task]["rows"].append(row)
        by_task[task]["targets"].setdefault(row["target_ref"], row["relation"])

    out = []
    for task, block in by_task.items():
        if area and ".%s." % area not in task:
            continue
        if all(r["confidence"] == "verified" for r in block["rows"]):
            continue
        out.append((task, block))
        if len(out) >= limit:
            break
    return out


def run(argv, out=sys.stdout, root=CROSSWALK, anchors_path=ANCHORS):
    parser = argparse.ArgumentParser(
        prog="crosswalk_review.py",
        description="Crosswalk review worklist and progress.")
    parser.add_argument("--certificate", default="private")
    parser.add_argument("--area", help="limit to one Area of Operation, e.g. I")
    parser.add_argument("--limit", type=int, default=6,
                        help="how many Tasks to print")
    parser.add_argument("--stats", action="store_true",
                        help="progress across every certificate, no worklist")
    args = parser.parse_args(argv)

    import bootstrap_crosswalk as BC

    names = [certificate for certificate, _doc, _p in BC.CERTIFICATES]

    if args.stats:
        out.write("%-12s %8s %9s %7s %8s %9s  %s\n" % (
            "certificate", "rows", "elements", "tasks", "verified",
            "tasks done", "progress"))
        out.write("-" * 82 + "\n")
        for row in summarize(names, root):
            share = (100.0 * row["tasks_done"] / row["tasks"]) if row["tasks"] else 0
            out.write("%-12s %8d %9d %7d %8d %9d  %5.1f%%\n" % (
                row["certificate"], row["rows"], row["elements"], row["tasks"],
                row["verified"], row["tasks_done"], share))
        return EXIT_OK

    anchors = anchors_by_document(anchors_path)
    tasks = worklist(args.certificate, anchors, args.limit, args.area, root)
    if not tasks:
        out.write("Nothing left to review in %s.\n" % args.certificate)
        return EXIT_OK

    out.write("Review worklist: %s%s, %d Task(s)\n\n" % (
        args.certificate,
        ", Area %s" % args.area if args.area else "", len(tasks)))

    for task, block in tasks:
        elements = sorted({r["source_ref"] for r in block["rows"]})
        out.write("=" * 78 + "\n")
        out.write("%s   %d element(s), %d target(s), %d row(s)\n" % (
            task, len(elements), len(block["targets"]), len(block["rows"])))

        sample = next((r["element_text"] for r in block["rows"]
                       if r["element_text"]), "")
        if sample:
            out.write("  first element reads: %s\n" % sample[:96])

        out.write("  targets, all confidence: auto\n")
        for target, relation in block["targets"].items():
            available = anchors.get(target, [])
            if available:
                hint = "  refine to: %s%s" % (
                    ", ".join(available[:4]),
                    " ..." if len(available) > 4 else "")
            elif target.startswith("14cfr:part-"):
                hint = "  refine to a section, e.g. 14cfr:91.155"
            else:
                hint = "  no anchors resolved for this document yet"
            out.write("    %-22s %-12s%s\n" % (target, relation, hint))
        out.write("\n")

    out.write("To verify a Task: narrow target_ref where a section fits, set\n"
              "confidence to verified, and put the reason in note. Elements in\n"
              "one Task share a References line, so they share the decision.\n")
    return EXIT_OK


def main(argv):
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
