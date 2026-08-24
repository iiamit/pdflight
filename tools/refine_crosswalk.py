"""Validate and apply section-level refinements to the crosswalk.

The bootstrap points every element at whole CFR parts. Refinement narrows those
to the sections that actually govern the element. That work is done by reading
each element against the regulation, and this tool is the gate between a
proposal and the crosswalk.

**Nothing is trusted.** A proposal naming `61.129` is only accepted if 61.129
is one of the 849 sections this corpus actually carries. Rule 1 forbids
inventing a reference, and a section number recalled rather than looked up is
exactly that. Every rejection is reported rather than dropped.

A proposal may legitimately be empty. Plenty of ACS elements are technique or
theory with no governing regulation, and forcing a section onto them would put
a confident wrong link in front of a pilot. Those keep their part-level row.

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
CFR_BUILD = M.ROOT / "build" / "cfr"

# Which certificate each proposal file belongs to.
PROPOSALS = {
    "private": "private",
    "instrument-a": "instrument", "instrument-b": "instrument",
    "atp-a": "atp", "atp-b": "atp", "atp-c": "atp", "atp-d": "atp",
    "atp-e": "atp",
    "cfi-a": "cfi", "cfi-b": "cfi", "cfi-c": "cfi", "cfi-d": "cfi",
    "cfi-e": "cfi", "cfi-f": "cfi", "cfi-g": "cfi", "cfi-h": "cfi",
    "cfi-i": "cfi",
    "commercial-a": "commercial", "commercial-b": "commercial",
    "commercial-c": "commercial", "commercial-d": "commercial",
    "commercial-e": "commercial", "commercial-f": "commercial",
    "commercial-g": "commercial",
}


def section_inventory(build=CFR_BUILD):
    """Every CFR section the corpus carries, as {number: (part, heading)}."""
    found = {}
    for path in sorted(glob.glob(str(pathlib.Path(build) / "title-*.json"))):
        with io.open(path, encoding="utf-8") as handle:
            data = json.load(handle)

        def walk(nodes):
            for node in nodes:
                if node["kind"] == "section":
                    found[node["n"]] = (data["part"], node["heading"])
                elif node["kind"] == "subpart":
                    walk(node["children"])

        walk(data["children"])
    return found


def load_rows(certificate, root=CROSSWALK):
    path = pathlib.Path(root) / ("%s.csv" % certificate)
    with io.open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_proposals(directory):
    """Find each packet's result file.

    Proposals live under `crosswalk/proposals/`, split by which pass produced
    them, because the two passes reused the same packet names and a flat copy
    silently overwrote the CFR results for instrument-a and instrument-b with
    the handbook ones. The combined Commercial, ATP and CFI packets carry both
    `sections` and `anchors` in one file, so both tools read both directories.
    """
    root = pathlib.Path(directory)
    places = [root, root / "cfr", root / "handbook"]
    out = {}
    for name, certificate in sorted(PROPOSALS.items()):
        for place in places:
            path = place / ("%s.result.json" % name)
            if not path.is_file():
                continue
            with io.open(path, encoding="utf-8") as handle:
                try:
                    payload = json.load(handle)
                except ValueError as error:
                    payload = {"__error__": str(error)}
            if name in out:
                # A later directory only supplements; it never replaces.
                merged = dict(out[name][1])
                for code, entry in payload.items():
                    merged.setdefault(code, {}).update(entry)
                out[name] = (certificate, merged)
            else:
                out[name] = (certificate, payload)
    return out

def validate(proposals, inventory, rows_by_cert):
    """Return (accepted, report). Nothing invalid survives."""
    accepted = collections.defaultdict(dict)
    report = {"checked": 0, "elements": 0, "empty": 0, "low": 0,
              "unknown_section": [], "unknown_element": [],
              "part_changed": [], "sections": 0, "already": 0}

    for name, (certificate, mapping) in sorted(proposals.items()):
        known, settled = {}, {}
        for row in rows_by_cert[certificate]:
            ref = row["target_ref"]
            if ref.startswith("14cfr:part-"):
                known.setdefault(row["source_ref"], set()).add(
                    ref.rsplit("-", 1)[-1])
            elif ref.startswith("14cfr:"):
                settled.setdefault(row["source_ref"], set()).add(
                    ref.split(":", 1)[1])

        for code, entry in sorted(mapping.items()):
            report["checked"] += 1
            if code not in known:
                # Applying consumes the part-level row, so on a second run the
                # element looks like it was never in the crosswalk. Treat a
                # code whose sections are already present as done rather than
                # rejected, which is what makes --apply safe to repeat.
                if set(entry.get("sections") or []) <= settled.get(code, set()) \
                        and code in settled:
                    report["already"] += 1
                else:
                    report["unknown_element"].append((name, code))
                continue

            proposed = entry.get("sections") or []
            if entry.get("confidence") == "low":
                report["low"] += 1
            if not proposed:
                report["empty"] += 1
                continue

            good = []
            for number in proposed:
                if number not in inventory:
                    report["unknown_section"].append((name, code, number))
                    continue
                part = inventory[number][0]
                if part not in known[code]:
                    report["part_changed"].append((name, code, number, part))
                good.append(number)

            if good:
                report["elements"] += 1
                report["sections"] += len(good)
                accepted[certificate][code] = {
                    "sections": good,
                    "why": (entry.get("why") or "").strip()[:160],
                    "confidence": entry.get("confidence", "high"),
                }
    return accepted, report


def apply_to(rows, accepted):
    """Replace part-level CFR rows with section-level ones."""
    out, changed = [], 0
    for row in rows:
        code = row["source_ref"]
        if not row["target_ref"].startswith("14cfr:part-") or code not in accepted:
            out.append(row)
            continue
        # The part-level row is replaced, not kept alongside; leaving it would
        # mean a link to the whole part sitting beside the precise one.
        changed += 1

    for code, entry in accepted.items():
        template = next((r for r in rows if r["source_ref"] == code), None)
        if template is None:
            continue
        for number in entry["sections"]:
            out.append({
                "source_ref": code,
                "target_ref": "14cfr:%s" % number,
                "relation": "regulation",
                "confidence": "verified",
                "note": entry["why"] or "section-level refinement",
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
    return deduped, changed


def run(argv, directory=None, root=CROSSWALK, out=sys.stdout):
    parser = argparse.ArgumentParser(
        prog="refine_crosswalk.py",
        description="Validate and apply section-level crosswalk refinements.")
    parser.add_argument("--dir", default=directory,
                        help="directory holding the *.result.json proposals")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    if not args.dir:
        out.write("--dir is required\n")
        return EXIT_PROBLEM

    inventory = section_inventory()
    proposals = load_proposals(args.dir)
    if not proposals:
        out.write("no proposals found in %s\n" % args.dir)
        return EXIT_PROBLEM

    certificates = sorted({c for c, _m in proposals.values()})
    rows_by_cert = {c: load_rows(c, root) for c in certificates}
    accepted, report = validate(proposals, inventory, rows_by_cert)

    out.write("proposals checked      %d\n" % report["checked"])
    out.write("elements refined       %d\n" % report["elements"])
    out.write("sections accepted      %d\n" % report["sections"])
    out.write("left at part level     %d  (no section governs the element)\n"
              % report["empty"])
    out.write("flagged low confidence %d\n" % report["low"])
    if report["already"]:
        out.write("already applied        %d  (re-running changes nothing)\n"
                  % report["already"])

    if report["unknown_section"]:
        out.write("\nREJECTED, section is not in the corpus (%d):\n"
                  % len(report["unknown_section"]))
        for name, code, number in report["unknown_section"][:15]:
            out.write("  %-14s %-16s %s\n" % (name, code, number))
    if report["unknown_element"]:
        out.write("\nREJECTED, element has no part-level CFR row (%d):\n"
                  % len(report["unknown_element"]))
        for name, code in report["unknown_element"][:10]:
            out.write("  %-14s %s\n" % (name, code))
    if report["part_changed"]:
        out.write("\nNote, section sits in a part the element did not cite (%d):\n"
                  % len(report["part_changed"]))
        for name, code, number, part in report["part_changed"][:10]:
            out.write("  %-14s %-16s %-9s part %s\n" % (name, code, number, part))

    if not args.apply:
        out.write("\nNothing written. Re-run with --apply to update the CSVs.\n")
        return EXIT_OK

    import bootstrap_crosswalk as BC

    # Everything is computed and staged before anything is replaced. A run that
    # died between two certificates left one refined and one not, and because
    # applying consumes the part-level rows the two halves could not then be
    # brought back into step by re-running.
    staged = []
    for certificate in certificates:
        rows, replaced = apply_to(rows_by_cert[certificate],
                                  accepted.get(certificate, {}))
        final = pathlib.Path(root) / ("%s.csv" % certificate)
        pending = final.with_suffix(".csv.pending")
        BC.write_csv(pending, rows)
        staged.append((certificate, pending, final, len(rows), replaced))

    for certificate, pending, final, count, replaced in staged:
        os.replace(str(pending), str(final))
        out.write("%-12s %d row(s), %d part-level CFR row(s) replaced\n"
                  % (certificate, count, replaced))
    return EXIT_OK


def main(argv):
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
