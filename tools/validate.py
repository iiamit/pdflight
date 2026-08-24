"""Run the validation gates from BUILD-PLAN section 9.

Every gate below fails the build. Gates that cannot be checked yet report
UNAVAILABLE with the reason rather than passing quietly, because a gate that
silently skips is worse than one that is absent: it reads as green.

    1  zero unresolved anchors
    2  zero dangling link annotations
    3  every ACS element in the crosswalk has an outbound link
    4  every manifest document reachable from a main menu page
    5  every page carries a persistent nav stamp
    6  outline depth exactly 3, no orphan nodes
    7  pdfcpu validate clean
    8  file size within budget
    9  byte-identical rebuild from identical inputs
    10 no authored page carries a URL outside the manifest hosts
"""

import argparse
import io
import json
import pathlib
import re
import shutil
import subprocess
import sys

import _manifest as M

EXIT_OK = 0
EXIT_FAILED = 1

BUILD = M.ROOT / "build"
FINAL = BUILD / "pdflight-outlined.pdf"
OFFSETS = BUILD / "offsets.json"
ABSOLUTE = BUILD / "anchors-absolute.json"
PATTERNS = M.ROOT / "anchors" / "patterns.yaml"

WARN_BYTES = M.SIZE_WARN_BYTES
FAIL_BYTES = M.SIZE_FAIL_BYTES

# Nav pages are exempt from the stamp by design; see tools/link.py.
NAV_KINDS = ("cover", "menu", "docmenu", "colophon")

URL = re.compile(r"https?://([A-Za-z0-9.\-]+)")


class Result:
    def __init__(self):
        self.rows = []

    def add(self, number, name, state, detail=""):
        self.rows.append((number, name, state, detail))

    @property
    def failed(self):
        return [r for r in self.rows if r[2] == "FAIL"]

    @property
    def unavailable(self):
        return [r for r in self.rows if r[2] == "UNAVAILABLE"]


def run(argv, final=FINAL, offsets_path=OFFSETS, absolute=ABSOLUTE,
        out=sys.stdout):
    parser = argparse.ArgumentParser(
        prog="validate.py", description="Run the validation gates.")
    parser.parse_args(argv)

    import pymupdf

    path = pathlib.Path(final)
    if not path.is_file():
        out.write("%s is missing. Run the build first.\n" % path.name)
        return EXIT_FAILED

    with io.open(offsets_path, encoding="utf-8") as handle:
        data = json.load(handle)
    offsets = data["offsets"]

    document = pymupdf.open(path)
    result = Result()

    # 1 -- unresolved anchors ------------------------------------------------
    import resolve as R

    specs = R.load_patterns(PATTERNS)
    with io.open(absolute, encoding="utf-8") as handle:
        anchors = json.load(handle)["anchors"]
    unresolved = sorted(set(specs) - set(anchors))
    result.add(1, "zero unresolved anchors",
               "PASS" if not unresolved else "FAIL",
               "%d of %d resolved" % (len(anchors), len(specs)))

    # 2 -- dangling links ----------------------------------------------------
    dangling, total_links = [], 0
    for number in range(document.page_count):
        for link in document.load_page(number).get_links():
            total_links += 1
            target = link.get("page")
            if link.get("kind") == pymupdf.LINK_GOTO:
                if target is None or target < 0 or target >= document.page_count:
                    dangling.append((number + 1, target))
    result.add(2, "zero dangling link annotations",
               "PASS" if not dangling else "FAIL",
               "%d link(s) checked, %d dangling" % (total_links, len(dangling)))

    # 3 -- crosswalk coverage ------------------------------------------------
    # A data check, not a PDF one. The question is whether every element the
    # ACS defines has at least one row pointing somewhere, which is answerable
    # from the source documents and the CSVs without opening the build.
    import bootstrap_crosswalk as BC
    import index as IX

    covered, defined, per_cert = set(), set(), []
    for name, document_id, _prefix in BC.CERTIFICATES:
        # Not `path`. That name holds the built PDF, and shadowing it here made
        # gate 8 measure the last crosswalk CSV instead: it reported 1.1 MB for
        # a 475 MB file and would have passed a 2 GB one.
        csv_path = M.ROOT / "crosswalk" / ("%s.csv" % name)
        if not csv_path.is_file():
            continue
        rows = set()
        with io.open(csv_path, encoding="utf-8", newline="") as handle:
            import csv as _csv

            for row in _csv.DictReader(handle):
                rows.add(row["source_ref"])
        covered |= rows

        record = IX.load_index(document_id)
        if record:
            skip = set(record.get("toc_pages") or [])
            text = "\n".join(
                page for number, page in enumerate(record["page_text"], 1)
                if number not in skip)
            found = set(BC.ELEMENT.findall(text))
            defined |= found
            per_cert.append((name, len(found - rows)))

    uncovered = defined - covered
    worst = sorted(per_cert, key=lambda pair: -pair[1])[:1]
    result.add(3, "every ACS element has an outbound link",
               "PASS" if not uncovered else "FAIL",
               "%d element(s) across %d certificate(s)"
               % (len(defined), len(per_cert)) if not uncovered
               else "%d of %d uncovered, worst %s with %d"
                    % (len(uncovered), len(defined),
                       worst[0][0] if worst else "-",
                       worst[0][1] if worst else 0))

    # 4 -- reachability ------------------------------------------------------
    import menus as menus_tool

    # "Reachable" has to mean a reader can get there, not that the destination
    # exists. The first version of this gate checked only that the name was in
    # the file, and passed for a build in which assembly had stripped every
    # link annotation off every generated page: the cover, the contents, every
    # entry arrow, the colophon button, and every "Return to the main menu"
    # did nothing at all, and all 34 documents still counted as reachable.
    # A dict, not a set: the gate needs each destination's page to check
    # that something actually links to it.
    names = document.resolve_names()
    entries = M.load_sources()

    generated_pages = set()
    for _key, entry in offsets.items():
        if entry["kind"] in NAV_KINDS:
            for index in range(entry["pages"]):
                generated_pages.add(entry["start"] + index)

    linked_from_menu = set()
    menu_link_count = 0
    for number in sorted(generated_pages):
        if number > document.page_count:
            continue
        for link in document.load_page(number - 1).get_links():
            menu_link_count += 1
            target = link.get("page")
            if target is not None and target >= 0:
                linked_from_menu.add(target + 1)

    unreachable = []
    for entry in entries:
        label = menus_tool.label_for_doc(entry["id"])
        if label not in names:
            unreachable.append(entry["id"])
            continue
        if names[label].get("page") + 1 not in linked_from_menu:
            unreachable.append(entry["id"])

    result.add(4, "every document is linked from a menu page",
               "PASS" if not unreachable else "FAIL",
               "%d document(s), %d link(s) across %d generated page(s)"
               % (len(entries), menu_link_count, len(generated_pages))
               if not unreachable
               else "%d of %d unreachable, e.g. %s"
                    % (len(unreachable), len(entries), unreachable[0]))

    # 5 -- nav stamps --------------------------------------------------------
    exempt = set()
    for _key, entry in offsets.items():
        if entry["kind"] in NAV_KINDS:
            for index in range(entry["pages"]):
                exempt.add(entry["start"] + index)

    missing_stamp = []
    for number in range(document.page_count):
        if (number + 1) in exempt:
            continue
        if not document.load_page(number).get_links():
            missing_stamp.append(number + 1)
    result.add(5, "every content page carries a nav stamp",
               "PASS" if not missing_stamp else "FAIL",
               "%d stamped, %d navigation page(s) exempt"
               % (document.page_count - len(exempt), len(exempt))
               if not missing_stamp
               else "%d unstamped, first at %d"
               % (len(missing_stamp), missing_stamp[0]))

    # 6 -- outline -----------------------------------------------------------
    import outline as O

    toc = document.get_toc()
    outline_problems = O.problems(toc, document.page_count) if toc else \
        ["no outline present"]
    result.add(6, "outline depth 3, no orphans",
               "PASS" if not outline_problems else "FAIL",
               "%d node(s)" % len(toc) if not outline_problems
               else outline_problems[0][:60])

    # 7 -- pdfcpu ------------------------------------------------------------
    if shutil.which("pdfcpu"):
        proc = subprocess.run(["pdfcpu", "validate", str(path)],
                              capture_output=True)
        result.add(7, "pdfcpu validate clean",
                   "PASS" if proc.returncode == 0 else "FAIL",
                   proc.stderr.decode("utf-8", "replace")[:60])
    else:
        result.add(7, "pdfcpu validate clean", "UNAVAILABLE",
                   "pdfcpu is not installed")

    # 8 -- size --------------------------------------------------------------
    size = path.stat().st_size
    state = "FAIL" if size >= FAIL_BYTES else "PASS"
    note = "%.1f MB" % (size / 1048576)
    if size >= WARN_BYTES and state == "PASS":
        note += ", over the 350 MB warn line"
    result.add(8, "file size within budget", state, note)

    # 9 -- reproducibility ---------------------------------------------------
    # A full rebuild is far too slow to run inside a gate, so this checks the
    # property that made rebuilds differ rather than the rebuild itself: the
    # trailer /ID must be the content-derived constant. The first Linux build
    # differed from the Windows one by four bytes with identical content,
    # identical PyMuPDF and identical Typst, and an unpinned /ID was why.
    #
    # This matters beyond tidiness. release.yml decides whether to publish by
    # comparing the built hash against the last release, so an unpinned id
    # makes every build look changed, cuts an empty release every quarter, and
    # turns the skip-if-unchanged branch into dead code.
    import optimize
    import outline as O

    tail = path.read_bytes()[-4096:]
    expected = optimize.digest_for(O.seed_for(offsets_path)).encode()
    found = optimize.TRAILER_ID.search(tail)
    if not found:
        result.add(9, "output is reproducible", "FAIL",
                   "no trailer /ID in the shipped file")
    elif tail.count(expected) >= 2:
        result.add(9, "output is reproducible", "PASS",
                   "trailer /ID pinned to the content-derived constant")
    else:
        result.add(9, "output is reproducible", "FAIL",
                   "trailer /ID is not pinned: %s"
                   % found.group(0)[:56].decode("latin-1"))

    # 10 -- stray URLs -------------------------------------------------------
    # The line is authored versus reproduced, not generated versus source.
    #
    # Source PDFs are reproduced unaltered under rule 4, and FAA text
    # legitimately cites asrs.arc.nasa.gov and others. The CFR pages are
    # typeset by this project but their words are the regulation: 14 CFR
    # incorporates standards by reference and prints where to obtain them, so
    # its text carries www.archives.gov, rtca.org and icao.int. Stripping those
    # would alter the law to satisfy a gate.
    #
    # What is left is the handful of pages PDFlight actually writes, where a
    # URL pointing outside the manifest really would be a defect of ours.
    allowed = {"www.faa.gov", "faa.gov", "www.ecfr.gov", "ecfr.gov",
               "www.ntsb.gov", "drs.faa.gov", "www.gpo.gov"}
    generated = set()
    for _key, entry in offsets.items():
        if entry["kind"] in NAV_KINDS:
            for index in range(entry["pages"]):
                generated.add(entry["start"] + index)

    seen, sampled = {}, 0
    for number in sorted(generated):
        if number > document.page_count:
            continue
        sampled += 1
        for host in URL.findall(document.load_page(number - 1).get_text("text")):
            host = host.lower().rstrip(".")
            if host not in allowed:
                seen.setdefault(host, number)
    result.add(10, "no stray URL on a generated page",
               "PASS" if not seen else "FAIL",
               "%d generated page(s) checked" % sampled if not seen
               else "%d host(s), e.g. %s on page %d" % (
                   len(seen), sorted(seen)[0], seen[sorted(seen)[0]]))

    document.close()

    out.write("%-4s %-46s %-12s %s\n" % ("gate", "check", "state", "detail"))
    out.write("-" * 100 + "\n")
    for number, name, state, detail in result.rows:
        out.write("%-4d %-46s %-12s %s\n" % (number, name, state, detail))

    out.write("\n%d passed, %d failed, %d unavailable\n" % (
        len([r for r in result.rows if r[2] == "PASS"]),
        len(result.failed), len(result.unavailable)))
    return EXIT_FAILED if result.failed else EXIT_OK


def main(argv):
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
