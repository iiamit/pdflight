"""Resolve interpretations that the documented URL pattern cannot reach.

Two groups need this. Thirteen candidates carry no year, so their URL cannot be
built at all. Five more carry a year but 404 at the documented pattern, because
the Chief Counsel library has used more than one filename convention over the
years. Both are handed to a human with evidence, never guessed.

**The FAA index this was designed around is gone.** CLAUDE.md 4.4 assumes a
year-browsable index listing addressee and subject. As of Phase 1.4 it does not
exist in any scriptable form:

    Data/interps/{year}/ directory listing      403
    interpretations/index.cfm search endpoint   500
    drs.faa.gov REST API                        403, even with browser headers

The interpretations moved to the Dynamic Regulatory System, which is a
JavaScript application. The PDF URL pattern itself still works, which is why
verification of dated entries is unaffected.

So candidate URLs come from outside: a DRS session or a search engine, recorded
into cache/interps-index.json. This tool never invents one. What it does is the
part that matters for rule 2: it fetches each candidate and reads the addressee,
the date, and the subject off page one, so the year is confirmed from the
document rather than from a filename or a search snippet. A candidate whose
page one names someone else is rejected outright.

Nothing is auto-selected. Ambiguity goes to docs/INTERPS-CANDIDATES.md for a
human to resolve, because picking on topic similarity would be rule 2 with
extra steps.
"""

import argparse
import io
import json
import pathlib
import sys

import _interps as I
from _http import Client, FetchError

EXIT_OK = 0
EXIT_UNRESOLVED = 1

CACHE = I.ROOT / "cache" / "interps"
CANDIDATES = I.ROOT / "docs" / "INTERPS-CANDIDATES.md"


def load_index(path=I.INDEX_CACHE):
    """Candidate URLs per table ref, seeded from outside this tool."""
    if not pathlib.Path(path).is_file():
        return {}
    with io.open(path, encoding="utf-8") as handle:
        return json.load(handle).get("candidates", {})


def save_index(candidates, path=I.INDEX_CACHE):
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({
            "comment": ("Candidate URLs per CLAUDE.md section 7 ref. Seeded "
                        "from a DRS session or a search index, because the FAA "
                        "year index no longer exists in scriptable form. "
                        "Fetched and confirmed against page one by "
                        "tools/discover_interps.py."),
            "candidates": candidates,
        }, handle, indent=2, sort_keys=True)
        handle.write("\n")


def inspect(client, entry, url, cache_root):
    """Fetch one candidate and read its page one. Never selects."""
    record = {"url": url, "status": None, "ok": False, "note": "",
              "addressee": None, "date": None, "request_date": None,
              "subject": None, "years": [], "pages": None}
    try:
        reply = client.get(url)
    except FetchError as exc:
        record["note"] = "unreachable: %s" % exc
        return record

    record["status"] = reply.status
    if not reply.ok:
        record["note"] = "HTTP %d" % reply.status
        return record
    if reply.body[:5] != b"%PDF-":
        record["note"] = "not a PDF"
        return record

    text, pages = I.read_first_page(reply.body)
    record["pages"] = pages
    record.update({k: v for k, v in I.extract(text).items()})

    if not I.surname_matches(entry["surname"], record["addressee"], text):
        record["note"] = ("page one does not name %s, rejected"
                          % entry["surname"])
        return record

    pathlib.Path(cache_root).mkdir(parents=True, exist_ok=True)
    stamp = "%s_%s" % (entry["surname"].replace(" ", "_"),
                       (record["years"] or ["unknown"])[-1])
    (pathlib.Path(cache_root) / ("%s.pdf" % stamp)).write_bytes(reply.body)

    record["ok"] = True
    record["note"] = "addressee confirmed on page one"
    return record


TEMPLATE = """\
# Interpretation discovery candidates

Written by `tools/discover_interps.py`. Do not hand-edit; edits are overwritten.
Selections belong in `manifest/sources.yaml`.

{summary}

## Why this file exists

The URL pattern in CLAUDE.md 4.4 needs a year, and thirteen candidates carry
none. Five more carry a year but 404 at that pattern, because the library has
used more than one filename convention.

CLAUDE.md 4.4 assumed a year-browsable FAA index listing addressee and subject.
That index no longer exists in scriptable form:

| Source | Result |
|---|---|
| `Data/interps/{{year}}/` directory listing | 403 |
| `interpretations/index.cfm` search endpoint | 500, retired |
| `drs.faa.gov` REST API | 403, even with browser headers |

The interpretations moved to the Dynamic Regulatory System, a JavaScript
application. The PDF pattern itself still resolves, so verification of dated
entries is unaffected; only discovery is.

Candidate URLs therefore come from a DRS session or a search index, recorded in
`cache/interps-index.json`. This tool never invents one. It fetches each
candidate and reads the addressee, date, and subject off page one, so a year is
only ever adopted from the document itself. A candidate whose page one names
someone else is rejected. Matching is on surname alone; nothing is selected on
topic similarity, which would be rule 2 with extra steps.

## Candidates

{rows}

## Still unresolved

{unresolved}

## How to resolve one

1. Find the letter in DRS: <https://drs.faa.gov/browse/LEGAL_INTERPRETATIONS/doctypeDetails>
2. Add its PDF URL to `cache/interps-index.json` under the table ref.
3. Run `make discover-interps`. The tool fetches it and prints the addressee,
   date, and subject it actually found.
4. If that is the right letter, add it to `manifest/sources.yaml` with a
   three-part id: `interp:{{surname}}-{{year}}-{{topic-slug}}`, the slug drawn
   from the subject line printed here rather than from the topic column.
"""


def cell(value):
    if value is None or value == "":
        return "-"
    return str(value).replace("|", r"\|")


def write_candidates(entries, results, path=CANDIDATES):
    rows, unresolved = [], []
    for entry in entries:
        found = results.get(entry["ref"], [])
        confirmed = [r for r in found if r["ok"]]
        if not confirmed:
            reason = ("no candidate URL seeded" if not found
                      else "; ".join(r["note"] for r in found)[:120])
            unresolved.append("- **%s %s** (%s, %s): %s"
                              % (entry["surname"], entry["year"] or "no year",
                                 entry["ref"], entry["topic"][:50], reason))
            continue
        rows.append("### %s %s, %s\n" % (
            entry["ref"], entry["surname"], entry["topic"]))
        rows.append("| Year | Addressee | FAA date | Request dated | Subject as printed | URL |")
        rows.append("|---|---|---|---|---|---|")
        for record in confirmed:
            rows.append("| %s | %s | %s | %s | %s | %s |" % (
                cell((record["years"] or ["?"])[-1]), cell(record["addressee"]),
                cell(record["date"]), cell(record["request_date"]),
                cell(record["subject"]), record["url"]))
        rows.append("")

    summary = ("**%d candidate(s) need discovery. %d resolved, %d still open.**"
               % (len(entries), len(entries) - len(unresolved), len(unresolved)))

    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(TEMPLATE.format(
            summary=summary,
            rows="\n".join(rows) or "None resolved yet.",
            unresolved="\n".join(unresolved) or "None."))
    return len(unresolved)


def needs_discovery(entries, client=None, out=None):
    """Yearless candidates, plus dated ones the documented pattern cannot reach.

    A dated entry only needs discovery if its URL actually fails, so this asks
    rather than assumes. One HEAD per dated entry, which is cheap and keeps the
    list honest as the library shifts.
    """
    targets = list(I.yearless(entries))
    if client is None:
        return targets

    for entry in I.dated(entries):
        url = I.url_for(entry["surname"], entry["year"])
        try:
            reply = client.head(url)
        except FetchError:
            reply = None
        if reply is not None and reply.ok:
            continue
        marked = dict(entry)
        marked["pattern_404"] = True
        targets.append(marked)
        if out is not None:
            out.write("%-4s %-12s %s at the documented pattern, needs discovery\n"
                      % (entry["ref"], entry["surname"],
                         reply.status if reply is not None else "unreachable"))
    return targets


def run(argv, client_factory=None, claude_path=I.CLAUDE, index_path=I.INDEX_CACHE,
        cache_root=CACHE, candidates_path=CANDIDATES, out=sys.stdout):
    parser = argparse.ArgumentParser(
        prog="discover_interps.py",
        description="Resolve interpretations the URL pattern cannot reach.")
    parser.add_argument("--seed", nargs=2, metavar=("REF", "URL"), action="append",
                        help="record a candidate URL for a table ref")
    parser.add_argument("--only-yearless", action="store_true",
                        help="skip entries that merely 404 at the pattern")
    args = parser.parse_args(argv)

    entries = I.load(claude_path)
    index = load_index(index_path)

    if args.seed:
        for ref, url in args.seed:
            index.setdefault(ref.upper(), [])
            if url not in index[ref.upper()]:
                index[ref.upper()].append(url)
        save_index(index, index_path)
        out.write("seeded %d candidate url(s)\n" % len(args.seed))

    client = (client_factory or Client)()
    targets = (I.yearless(entries) if args.only_yearless
               else needs_discovery(entries, client, out))
    results = {}
    for entry in targets:
        urls = index.get(entry["ref"].upper(), [])
        records = [inspect(client, entry, url, cache_root) for url in urls]
        results[entry["ref"]] = records
        good = [r for r in records if r["ok"]]
        out.write("%-4s %-12s %d candidate(s), %d confirmed%s\n" % (
            entry["ref"], entry["surname"], len(records), len(good),
            "" if urls else "  (none seeded)"))

    open_count = write_candidates(targets, results, candidates_path)
    out.write("\n%d needing discovery, %d still open. Wrote %s\n" % (
        len(targets), open_count, pathlib.Path(candidates_path).name))
    return EXIT_UNRESOLVED if open_count else EXIT_OK


def main(argv):
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
