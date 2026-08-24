"""Validate and apply handbook chapter refinements to the crosswalk.

The bootstrap points every element at whole handbooks. This narrows those to
the chapters that actually cover the element, which is what turns a button
reading PHAK into a button reading PHAK c15.

**Nothing is trusted.** A proposal naming `phak:ch15` is only accepted if that
anchor is in `anchors/anchors.lock.json`, which means it resolved to a real
page in this build. An anchor recalled rather than looked up is exactly the
invention rule 1 forbids, and a chapter number that shifted between editions
is the most likely way to get one wrong: AFH-3C inserted Energy Management as
chapter 4, moving every chapter after it.

A proposal may legitimately be empty. Plenty of ACS elements are covered by a
handbook as a whole and by no chapter in particular. Those keep their
document-level row.

    --check   validate proposals and report, write nothing
    --apply   rewrite the CSVs
"""

import argparse
import collections
import csv
import glob
import io
import json
import os
import pathlib
import sys

import _manifest as M

EXIT_OK = 0
EXIT_PROBLEM = 1

CROSSWALK = M.ROOT / "crosswalk"
ANCHORS = M.ROOT / "anchors" / "anchors.lock.json"

# Which certificate each proposal file belongs to.
PROPOSALS = {
    "private-a": "private", "private-b": "private", "private-b2": "private",
    "private-b3": "private", "private-c": "private", "private-d": "private",
    "private-e": "private",
    "instrument-a": "instrument", "instrument-b": "instrument",
    "instrument-c": "instrument", "instrument-d": "instrument",
}


def anchor_inventory(path=ANCHORS):
    """Every anchor that resolved, as {ref: doc}."""
    with io.open(path, encoding="utf-8") as handle:
        anchors = json.load(handle)["anchors"]
    return {ref: entry.get("doc") for ref, entry in anchors.items()}


def load_rows(certificate, root=CROSSWALK):
    path = pathlib.Path(root) / ("%s.csv" % certificate)
    with io.open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_proposals(directory):
    out = {}
    for name, certificate in sorted(PROPOSALS.items()):
        path = pathlib.Path(directory) / ("%s.result.json" % name)
        if not path.is_file():
            continue
        with io.open(path, encoding="utf-8") as handle:
            try:
                out[name] = (certificate, json.load(handle))
            except ValueError as error:
                out[name] = (certificate, {"__error__": str(error)})
    return out


def validate(proposals, inventory, rows_by_cert):
    """Return (accepted, report). Nothing invalid survives."""
    accepted = collections.defaultdict(dict)
    report = {"checked": 0, "elements": 0, "empty": 0, "low": 0, "anchors": 0,
              "unknown_anchor": [], "unknown_element": [], "wrong_doc": [],
              "already": 0, "broken": []}

    for name, (certificate, mapping) in sorted(proposals.items()):
        if "__error__" in mapping:
            report["broken"].append((name, mapping["__error__"][:70]))
            continue

        # Which whole-handbook rows each element currently has, and which
        # chapter rows it already carries.
        cited, settled = {}, {}
        for row in rows_by_cert[certificate]:
            ref = row["target_ref"]
            if ref.startswith(("14cfr", "49cfr")):
                continue
            if ":" in ref:
                settled.setdefault(row["source_ref"], set()).add(ref)
            else:
                cited.setdefault(row["source_ref"], set()).add(ref)

        for code, entry in sorted(mapping.items()):
            report["checked"] += 1
            proposed = entry.get("anchors") or []

            if code not in cited:
                if proposed and set(proposed) <= settled.get(code, set()):
                    report["already"] += 1
                else:
                    report["unknown_element"].append((name, code))
                continue

            if entry.get("confidence") == "low":
                report["low"] += 1
            if not proposed:
                report["empty"] += 1
                continue

            good, settled_here = [], settled.get(code, set())
            for ref in proposed:
                doc = inventory.get(ref)
                if doc is None:
                    report["unknown_anchor"].append((name, code, ref))
                    continue
                # Applying replaces the element's document-level row with the
                # chapter rows, so on a re-run the handbook is no longer among
                # the things its Task appears to cite. Without this an already
                # applied refinement reads as 2,089 rejections and buries the
                # handful that are genuinely new.
                if ref in settled_here:
                    report["already"] += 1
                    continue
                # The chapter must belong to a handbook this element's Task
                # actually cites, or the crosswalk starts asserting a link the
                # ACS never made.
                if doc not in cited[code]:
                    report["wrong_doc"].append((name, code, ref, doc))
                    continue
                good.append(ref)

            if good:
                report["elements"] += 1
                report["anchors"] += len(good)
                accepted[certificate][code] = {
                    "anchors": good,
                    "why": (entry.get("why") or "").strip()[:160],
                    "confidence": entry.get("confidence", "high"),
                }
    return accepted, report


def relation_for(ref, doc):
    """A refinement keeps the relation its document already had.

    The vocabulary is fixed in bootstrap_crosswalk: regulations explain
    nothing, handbooks explain, the AIM and Advisory Circulars guide. Inventing
    a fifth value here put 2,089 rows outside the schema.
    """
    if ref.startswith(("14cfr", "49cfr")):
        return "regulation"
    if doc == "aim" or doc.startswith("ac-") or ref.startswith("ac:"):
        return "guidance"
    return "explanation"


def apply_to(rows, accepted, inventory):
    """Replace a document-level row with the chapter rows that refine it."""
    replaced = 0
    drop = set()
    for code, entry in accepted.items():
        for ref in entry["anchors"]:
            drop.add((code, inventory[ref]))

    out = []
    for row in rows:
        key = (row["source_ref"], row["target_ref"])
        if ":" not in row["target_ref"] and key in drop:
            replaced += 1
            continue
        out.append(row)

    for code, entry in accepted.items():
        template = next((r for r in rows if r["source_ref"] == code), None)
        if template is None:
            continue
        for ref in entry["anchors"]:
            out.append({
                "source_ref": code,
                "target_ref": ref,
                "relation": relation_for(ref, inventory.get(ref) or ""),
                "confidence": "verified",
                "note": entry["why"] or "chapter-level refinement",
                "element_text": template["element_text"],
            })

    seen, deduped = set(), []
    for row in out:
        key = (row["source_ref"], row["target_ref"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    deduped.sort(key=lambda r: (r["source_ref"], r["target_ref"]))
    return deduped, replaced


def run(argv, directory=None, root=CROSSWALK, out=sys.stdout):
    parser = argparse.ArgumentParser(
        prog="refine_handbooks.py",
        description="Validate and apply handbook chapter refinements.")
    parser.add_argument("--dir", default=directory,
                        help="directory holding the *.result.json proposals")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    if not args.dir:
        out.write("--dir is required\n")
        return EXIT_PROBLEM

    inventory = anchor_inventory()
    proposals = load_proposals(args.dir)
    if not proposals:
        out.write("no proposals found in %s\n" % args.dir)
        return EXIT_PROBLEM

    certificates = sorted({c for c, _m in proposals.values()})
    rows_by_cert = {c: load_rows(c, root) for c in certificates}
    accepted, report = validate(proposals, inventory, rows_by_cert)

    out.write("packets read           %d of %d\n"
              % (len(proposals), len(PROPOSALS)))
    out.write("proposals checked      %d\n" % report["checked"])
    out.write("elements refined       %d\n" % report["elements"])
    out.write("chapter anchors        %d\n" % report["anchors"])
    out.write("left at document level %d  (no chapter beats the whole book)\n"
              % report["empty"])
    out.write("flagged low confidence %d\n" % report["low"])
    if report["already"]:
        out.write("already applied        %d\n" % report["already"])

    for key, title in (("broken", "UNREADABLE proposal file"),
                       ("unknown_anchor", "REJECTED, anchor does not resolve"),
                       ("wrong_doc", "REJECTED, handbook not cited by the Task"),
                       ("unknown_element", "REJECTED, element has no such row")):
        rows = report[key]
        if not rows:
            continue
        out.write("\n%s (%d):\n" % (title, len(rows)))
        for row in rows[:12]:
            out.write("  %s\n" % "  ".join(str(part) for part in row))

    if not args.apply:
        out.write("\nNothing written. Re-run with --apply to update the CSVs.\n")
        return EXIT_OK

    import bootstrap_crosswalk as BC

    staged = []
    for certificate in certificates:
        rows, replaced = apply_to(rows_by_cert[certificate],
                                  accepted.get(certificate, {}), inventory)
        final = pathlib.Path(root) / ("%s.csv" % certificate)
        pending = final.with_suffix(".csv.pending")
        BC.write_csv(pending, rows)
        staged.append((certificate, pending, final, len(rows), replaced))

    for certificate, pending, final, count, replaced in staged:
        os.replace(str(pending), str(final))
        out.write("%-12s %d row(s), %d document-level row(s) replaced\n"
                  % (certificate, count, replaced))
    return EXIT_OK


def main(argv):
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
