"""Seed the crosswalk from the References line of every ACS Task.

Every Area of Operation carries a References line naming the documents that
support its Tasks. Parsing those turns most of the authoring effort into
review: each element gets document-level targets at `confidence: auto`, and a
human refines them to section level.

**The word "References" is not in the extracted text.** The ACS sets those
labels as drop caps, so PyMuPDF emits the tail first and the initial on its own
line:

    eferences:
    R
    14 CFR parts 61, 68, 91; AC 68-1; FAA-H-8083-2, FAA-H-8083-3

`Objective:` and `Note:` are mangled the same way. A parser looking for
"References:" finds nothing at all and reports zero rows without erroring,
which is the worst possible failure for a bootstrapping tool.

**Element text is stored alongside the code.** BUILD-PLAN section 11 requires
it: the FAA renumbers ACS task codes on revision, so a crosswalk keyed only by
code breaks by id rather than by page and cannot be remapped automatically.
That is a sixth column beyond the five in BUILD-PLAN section 4.
"""

import argparse
import csv
import io
import pathlib
import re
import sys

import _manifest as M
import index as IX

EXIT_OK = 0
EXIT_PROBLEM = 1

CROSSWALK = M.ROOT / "crosswalk"

FIELDS = ["source_ref", "target_ref", "relation", "confidence", "note",
          "element_text"]

# Certificates, and the ACS document each is parsed from.
CERTIFICATES = [
    ("private", "acs-private-airplane", "PA"),
    ("instrument", "acs-instrument-airplane", "IR"),
    ("commercial", "acs-commercial-airplane", "CA"),
    ("atp", "acs-atp-airplane", "AT"),
    ("cfi", "acs-cfi-airplane", "FI"),
]

AREA = re.compile(r"^Area of Operation\s+([IVX]+)\.\s+(.+?)\s*$", re.MULTILINE)
TASK = re.compile(r"^Task\s+([A-Z])\.\s+(.+?)\s*$", re.MULTILINE)

STOP = re.compile(r"^(?:bjective:|ote:|Knowledge:|Risk|Skills:|Task\s+[A-Z]\.|"
                  r"Area of Operation)", re.MULTILINE)

# The drop-cap artefact: "eferences:" then a lone "R" then the list.
#
# The list runs until the next label, not to the end of the line. A References
# line long enough to wrap put its tail on the following line, and `(.+?)$`
# under MULTILINE stopped at the first newline and dropped it. 65 of the 276
# Tasks wrap, and the citations that lived on the continuation line were
# silently missing from the crosswalk: PHAK was absent from 17 ATP Tasks and 7
# Instrument ones, and the CFI weather Task did not cite the Aviation Weather
# Handbook at all. Nothing failed, because a shorter list is still a valid
# list, which is why this survived every gate.
REFERENCES = re.compile(
    r"^eferences:\s*\n\s*R\s*\n(.+?)(?=^(?:bjective:|ote:|Knowledge:|Risk|"
    r"Skills:|Task\s+[A-Z]\.|Area of Operation)|\Z)",
    re.MULTILINE | re.DOTALL)

CFR_PARTS = re.compile(r"14 CFR (?:parts?|Part)\s+([\d,\s and]+)")
# The revision letter must be optional and outside the capture group. A closing
# \b straight after the digits refuses to match "FAA-H-8083-25C" at all, which
# silently shrank the handbook index to the one title that ships without a
# letter. Every handbook reference then read as unmet.
HANDBOOK = re.compile(r"\bFAA-H-(\d{4}-\d+)[A-Z]?\b")
AC_REF = re.compile(r"\bAC\s+(\d{1,3}[-.]\d+[A-Z]?)\b")
AIM_REF = re.compile(r"\bAIM\b")

RELATION = {"regulation": "regulation", "handbook": "explanation",
            "ac": "guidance", "aim": "guidance"}


# Any two-letter prefix, because the codes are not what the certificate name
# suggests. ATP uses AA, not AT. The CFI ACS uses two, AI for the aviation
# instructor Tasks and FI for the flight instructor ones. Hardcoding a guess
# produced zero rows for both documents while reporting success.
ELEMENT = re.compile(r"^([A-Z]{2}\.[IVX]+\.[A-Z]\.[KRS]\d+[a-z]?)\s*$",
                     re.MULTILINE)


def element_pattern(_prefix=None):
    return ELEMENT


# Routing hints for documents whose faa_number could not be extracted. This is
# not the same thing as authoring the field: rule 2a governs what goes in
# sources.lock.yaml, and that stays null. This only tells the crosswalk which
# manifest id a reference points at.
#
# Risk Management is the case. Its landing page titles it FAA-H-8083-2A but the
# document never states a number the extractor trusts, so every ACS Task citing
# FAA-H-8083-2 was reading as unmet against a handbook that is in the corpus.
REFERENCE_ALIASES = {"8083-2": "risk-management"}


def handbook_index(lock):
    """Map a base FAA-H number to a manifest id, ignoring revision letters.

    References cite `FAA-H-8083-25` while the document reports
    `FAA-H-8083-25C`, so the letter has to come off both sides.
    """
    out = {}
    for key, entry in lock.items():
        number = entry.get("faa_number") or ""
        match = HANDBOOK.search(number)
        if match and "." not in key:
            out.setdefault(match.group(1), key)
    for number, ident in REFERENCE_ALIASES.items():
        if ident in lock:
            out.setdefault(number, ident)
    return out


def ac_index(entries):
    out = {}
    for entry in entries:
        if entry["section"] != "ac":
            continue
        # ac-61-65k -> 61-65
        parts = entry["id"].split("-")[1:]
        if len(parts) >= 2:
            base = "%s-%s" % (parts[0], re.sub(r"[a-z]$", "", parts[1]))
            out.setdefault(base.lower(), entry["id"])
    return out


def parse_references(text, handbooks, acs, aim_id):
    """Turn one References line into target refs, plus what could not be met."""
    targets, unmet = [], []

    for group in CFR_PARTS.findall(text):
        for number in re.findall(r"\d+", group):
            targets.append(("14cfr:part-%s" % number, "regulation"))

    for number in HANDBOOK.findall(text):
        ident = handbooks.get(number)
        if ident:
            targets.append((ident, "explanation"))
        else:
            unmet.append("FAA-H-%s" % number)

    for number in AC_REF.findall(text):
        base = re.sub(r"[A-Z]$", "", number).lower()
        ident = acs.get(base)
        if ident:
            targets.append((ident, "guidance"))
        else:
            unmet.append("AC %s" % number)

    if AIM_REF.search(text):
        if aim_id:
            targets.append((aim_id, "guidance"))
        else:
            unmet.append("AIM")

    seen, ordered = set(), []
    for ref, relation in targets:
        if ref not in seen:
            seen.add(ref)
            ordered.append((ref, relation))
    return ordered, unmet


def parse_acs(record, prefix, handbooks, acs, aim_id):
    """Walk the ACS text, returning (rows, stats)."""
    codes = element_pattern(prefix)
    # Contents pages list every Task with dot leaders, so leaving them in makes
    # each one look like a real Task that happens to have no References line.
    skip = set(record.get("toc_pages") or [])
    text = "\n".join(page for number, page in enumerate(record["page_text"], 1)
                     if number not in skip)

    # Split into Task blocks, keeping the order they appear in.
    marks = []
    for match in TASK.finditer(text):
        marks.append((match.start(), match.group(1), match.group(2)))
    marks.append((len(text), None, None))

    rows, unmet_all, tasks_without_refs = [], set(), []
    elements = 0
    for index in range(len(marks) - 1):
        start, letter, title = marks[index]
        block = text[start:marks[index + 1][0]]

        reference_line = REFERENCES.search(block)
        if not reference_line:
            tasks_without_refs.append("Task %s. %s" % (letter, title[:40]))
            continue
        # The capture may now span several lines, and a citation can be split
        # across the break, so collapse the whitespace before parsing.
        targets, unmet = parse_references(
            " ".join(reference_line.group(1).split()), handbooks, acs, aim_id)
        unmet_all.update(unmet)

        for code_match in codes.finditer(block):
            code = code_match.group(1)
            tail = block[code_match.end():]
            stop = STOP.search(tail)
            following = codes.search(tail)
            cut = min([x.start() for x in (stop, following) if x] or [len(tail)])
            element_text = " ".join(tail[:cut].split())[:300]
            elements += 1
            for ref, relation in targets:
                rows.append({
                    "source_ref": code,
                    "target_ref": ref,
                    "relation": relation,
                    "confidence": "auto",
                    "note": "from the Task %s References line" % letter,
                    "element_text": element_text,
                })

    prefixes = sorted({row["source_ref"].split(".")[0] for row in rows})
    return rows, {"elements": elements, "unmet": sorted(unmet_all),
                  "prefixes": prefixes,
                  "tasks_without_refs": tasks_without_refs}


def write_csv(path, rows):
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in sorted(rows, key=lambda r: (r["source_ref"],
                                               r["target_ref"])):
            writer.writerow(row)


def run(argv, out=sys.stdout, crosswalk_root=CROSSWALK):
    parser = argparse.ArgumentParser(
        prog="bootstrap_crosswalk.py",
        description="Seed the crosswalk from ACS References lines.")
    parser.add_argument("--certificate", action="append",
                        help="limit to specific certificates")
    args = parser.parse_args(argv)

    lock = M.load_lock()
    entries = M.load_sources()
    handbooks = handbook_index(lock)
    acs = ac_index(entries)
    aim_id = next((e["id"] for e in entries if e["section"] == "aim"), None)

    wanted = CERTIFICATES
    if args.certificate:
        keep = set(args.certificate)
        wanted = [c for c in CERTIFICATES if c[0] in keep]

    out.write("%-12s %8s %8s %8s  %s\n"
              % ("certificate", "elements", "rows", "targets", "unmet references"))
    out.write("-" * 92 + "\n")

    total_rows, problems = 0, []
    for name, document_id, prefix in wanted:
        record = IX.load_index(document_id)
        if not record:
            problems.append("%s: no index for %s" % (name, document_id))
            continue
        rows, stats = parse_acs(record, prefix, handbooks, acs, aim_id)
        if not rows:
            problems.append("%s: parsed 0 rows" % name)
        write_csv(pathlib.Path(crosswalk_root) / ("%s.csv" % name), rows)
        total_rows += len(rows)
        out.write("%-12s %8d %8d %8d  %s\n" % (
            name, stats["elements"], len(rows),
            len({r["target_ref"] for r in rows}),
            ", ".join(stats["unmet"][:5]) or "none"))
        if stats["tasks_without_refs"]:
            out.write("             %d task(s) with no References line: %s\n"
                      % (len(stats["tasks_without_refs"]),
                         "; ".join(stats["tasks_without_refs"][:3])))

    out.write("\n%d row(s) at confidence: auto across %d certificate(s)\n"
              % (total_rows, len(wanted)))
    for line in problems:
        out.write("  %s\n" % line)
    return EXIT_PROBLEM if problems else EXIT_OK


def main(argv):
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
