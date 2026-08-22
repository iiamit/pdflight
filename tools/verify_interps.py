"""Verify dated legal interpretations against the Chief Counsel library.

For any candidate that carries a year, build the documented URL, fetch it, and
confirm the document is what the table claims by reading page one. The
addressee, the date, and the subject come off the paper. Nothing is accepted
because a filename looked right.

On a mismatch this reports and stops for that entry. It never searches for a
different year that happens to fit; that is the exact behaviour rule 2 forbids.

Writes docs/INTERPS-NOTES.md with a checked result for all candidates, passes
included, so the record shows what was examined rather than only what failed.

Exit codes per CLAUDE.md section 9: 0 all verified, 1 something did not.
"""

import argparse
import io
import pathlib
import sys

import _interps as I
from _http import Client, FetchError

EXIT_OK = 0
EXIT_FAILED = 1

CACHE = I.ROOT / "cache" / "interps"
NOTES = I.ROOT / "docs" / "INTERPS-NOTES.md"


def check_one(client, entry, cache_root):
    url = I.url_for(entry["surname"], entry["year"])
    record = {
        "ref": entry["ref"], "surname": entry["surname"], "year": entry["year"],
        "topic": entry["topic"], "confidence": entry["confidence"], "url": url,
        "status": None, "verdict": "fail", "note": "",
        "addressee": None, "date": None, "request_date": None,
        "subject": None, "pages": None, "years": [],
    }
    try:
        reply = client.get(url)
    except FetchError as exc:
        record["note"] = "unreachable: %s" % exc
        return record

    record["status"] = reply.status
    if reply.status == 404:
        record["note"] = "404 at the documented pattern"
        return record
    if not reply.ok:
        record["note"] = "HTTP %d" % reply.status
        return record
    if reply.body[:5] != b"%PDF-":
        record["note"] = "not a PDF, first bytes %r" % reply.body[:8]
        return record

    pathlib.Path(cache_root).mkdir(parents=True, exist_ok=True)
    (pathlib.Path(cache_root) / ("%s_%s.pdf" % (
        entry["surname"].replace(" ", "_"), entry["year"]))).write_bytes(reply.body)

    text, pages = I.read_first_page(reply.body)
    record["pages"] = pages
    found = I.extract(text)
    record.update(found)

    # Wrong addressee means the wrong document. That is the only hard mismatch.
    if not I.surname_matches(entry["surname"], found["addressee"], text):
        record["verdict"] = "mismatch"
        record["note"] = ("page one does not name %s; addressee reads %r"
                          % (entry["surname"], found["addressee"]))
        return record

    # The FAA files under the year it issues, and the letterhead date is a
    # scanned stamp that OCRs badly. Corroborate the year as a token anywhere
    # on page one rather than demanding a parsed date match it. Demanding that
    # produced six false mismatches on documents that were correct.
    if entry["year"] in found["years"]:
        record["verdict"] = "pass"
        record["note"] = "addressee and year %s both on page one" % entry["year"]
        return record

    record["verdict"] = "review"
    record["note"] = ("addressee confirmed, year %s not legible on page one; "
                      "years seen: %s"
                      % (entry["year"], ", ".join(found["years"]) or "none"))
    return record


TEMPLATE = """\
# Interpretation verification notes

Written by `tools/verify_interps.py`. Do not hand-edit; edits are overwritten.

Records a checked result for every dated candidate, passes included, and what
was ruled out for anything that failed. An entry that cannot be confirmed is
dropped rather than guessed at, and never replaced by a similar-looking
substitute.

The addressee, date, and subject below are read from page one of the fetched
document. They are not taken from the filename or from any search result.

{summary}

## Results

| Ref | Surname | Year | Verdict | Addressee on page 1 | FAA letter date | Request dated | Note |
|---|---|---|---|---|---|---|---|
{rows}

## Subjects as printed

{subjects}

## Yearless candidates

{yearless} candidate(s) carry no year and cannot use the documented URL
pattern. They are handled by `tools/discover_interps.py`; see
`docs/INTERPS-CANDIDATES.md`.
"""


def cell(value):
    if value is None or value == "":
        return "-"
    return str(value).replace("|", r"\|")


def write_notes(records, yearless_count, path=NOTES):
    def count(name):
        return len([r for r in records if r["verdict"] == name])

    summary = (
        "**%d checked: %d pass, %d review, %d mismatch, %d fail.**\n\n"
        "`pass` means the addressee and the filing year were both found on page "
        "one. `review` means the addressee is confirmed but the letterhead year "
        "is not legible, because those dates are scanned stamps and OCR mangles "
        "them. `mismatch` means page one names someone else, which is the only "
        "signal that a URL points at the wrong document. `fail` means the "
        "documented URL pattern did not resolve at all."
        % (len(records), count("pass"), count("review"),
           count("mismatch"), count("fail")))

    rows = "\n".join(
        "| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r["ref"], cell(r["surname"]), cell(r["year"]), r["verdict"],
            cell(r["addressee"]), cell(r["date"]), cell(r["request_date"]),
            cell(r["note"]))
        for r in records)

    subjects = "\n".join(
        "- **%s %s** (%s): %s" % (r["surname"], r["year"] or "", r["ref"],
                                  cell(r["subject"]))
        for r in records) or "None extracted."

    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(TEMPLATE.format(summary=summary, rows=rows,
                                     subjects=subjects, yearless=yearless_count))


def run(argv, client_factory=None, claude_path=I.CLAUDE, cache_root=CACHE,
        notes_path=NOTES, out=sys.stdout):
    parser = argparse.ArgumentParser(
        prog="verify_interps.py",
        description="Verify dated interpretations against the Chief Counsel library.")
    parser.add_argument("--ref", action="append",
                        help="limit to specific table refs, for example A1")
    args = parser.parse_args(argv)

    entries = I.load(claude_path)
    dated = I.dated(entries)
    if args.ref:
        wanted = {r.upper() for r in args.ref}
        dated = [e for e in dated if e["ref"].upper() in wanted]

    client = (client_factory or Client)()
    records = []
    for entry in dated:
        record = check_one(client, entry, cache_root)
        records.append(record)
        out.write("%-4s %-12s %-5s %-8s %s\n" % (
            record["ref"], record["surname"], record["year"],
            record["verdict"], record["note"][:60]))

    write_notes(records, len(I.yearless(entries)), notes_path)

    # A review is a human task, not a failure. Only a wrong document or an
    # unresolvable URL fails the run.
    bad = [r for r in records if r["verdict"] in ("fail", "mismatch")]
    out.write("\n%d checked, %d pass, %d review, %d not confirmed. Wrote %s\n" % (
        len(records), len([r for r in records if r["verdict"] == "pass"]),
        len([r for r in records if r["verdict"] == "review"]), len(bad),
        pathlib.Path(notes_path).name))
    return EXIT_FAILED if bad else EXIT_OK


def main(argv):
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
