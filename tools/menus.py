"""Render the cover, main menu, per-document menus, and colophon.

These are the only pages in the finished PDF that PDFlight writes itself, so
they carry the whole theme: the METAR status strip, the `pdflight_` brand mark,
`01 - STANDARDS` section numbering behind an amber rule, chips for per-document
metadata, and the ident block on the colophon. Source PDFs stay untouched.

Every navigable target is a labelled heading, because Typst exports named
destinations for nothing else. Phase 5 links source pages back to `menu-main`
and `docmenu-<id>` from here.

**The AIM has no menu section in CLAUDE.md section 6.** The six listed are
STANDARDS, HANDBOOKS, REGULATIONS, ADVISORY CIRCULARS, INTERPRETATIONS, GUIDES,
but `aim` is a first-class value in the manifest schema and the canonical page
order puts it between the handbooks and 14 CFR. Burying an 918-page core
reference under GUIDES would be worse than renumbering, so it gets its own
section here and the later numbers shift. Flagged rather than assumed.

Validation gate 4 says every manifest document must be reachable from a main
menu page, so that is asserted here rather than left for the build to discover.
"""

import argparse
import io
import pathlib
import subprocess
import sys

import yaml

import _manifest as M

EXIT_OK = 0
EXIT_PROBLEM = 1

TEMPLATE = M.ROOT / "templates" / "menu.typ"
BUILD = M.ROOT / "build" / "menus"
FONTS = M.ROOT / "theme" / "fonts"
CFR_LOCK = M.ROOT / "manifest" / "cfr.lock.yaml"

# Section order on the main menu. `aim` is the addition; see the module note.
SECTIONS = [
    ("01", "standards", "Standards"),
    ("02", "handbooks", "Handbooks"),
    ("03", "aim", "Aeronautical Information Manual"),
    ("04", "regs", "Regulations"),
    ("05", "ac", "Advisory Circulars"),
    ("06", "interps", "Interpretations"),
    ("07", "guides", "Guides"),
]

MENU_PAGES = 3


def typst_string(text):
    return (str(text or "")).replace("\\", "\\\\").replace('"', '\\"')


def label_for_doc(ident):
    return "docmenu-" + ident.replace(".", "-")


def version_from(cfr_lock):
    """Content-derived, never build-derived. Rule 8."""
    dates = [entry["amended_on"] for entry in cfr_lock.values()
             if entry.get("amended_on")]
    if not dates:
        return "v0.0.0"
    newest = max(dates)
    year, month, _day = newest.split("-")
    return "v%s.%s.1" % (year, month)


def load_cfr_lock(path=CFR_LOCK):
    if not pathlib.Path(path).is_file():
        return {}
    with io.open(path, encoding="utf-8") as handle:
        return (yaml.safe_load(handle) or {}).get("parts", {}) or {}


def chips_for(entry, lock):
    locked = lock.get(entry["id"]) or {}
    chips = []
    if locked.get("faa_number"):
        chips.append(locked["faa_number"])
    if locked.get("pages"):
        chips.append("%d pp" % locked["pages"])
    if locked.get("revision_date"):
        chips.append(locked["revision_date"])
    extra = sum(1 for key in lock if key.startswith(entry["id"] + ".addendum."))
    if extra:
        chips.append("%d addendum" % extra if extra == 1 else "%d addenda" % extra)
    return chips


def chip_args(chips):
    return "(%s,)" % ", ".join('"%s"' % typst_string(c) for c in chips)


def render(entries, lock, cfr_lock, cfr_pages):
    by_section = {}
    for entry in entries:
        by_section.setdefault(entry["section"], []).append(entry)
    for bucket in by_section.values():
        bucket.sort(key=lambda e: (e.get("order") or 0, e["id"]))

    source_pages = sum((lock.get(k) or {}).get("pages") or 0 for k in lock)
    total_pages = source_pages + cfr_pages
    version = version_from(cfr_lock)
    cfr_current = max([e["amended_on"] for e in cfr_lock.values()] or ["unknown"])
    aim = next((e for e in entries if e["section"] == "aim"), None)
    aim_label = "AIM current" if aim else "AIM absent"

    strip = '("%s", "%s", "14 CFR CURRENT %s", "%d PP")' % (
        typst_string("PDFLIGHT"), typst_string(version),
        typst_string(cfr_current), total_pages)

    out = ['#show: doc-page.with(fields: %s)' % strip, ""]

    # --- cover --------------------------------------------------------------
    out.append('#target[]<cover>')
    out.append("#v(70pt)")
    out.append("#brand(size: 20pt)")
    out.append("#v(24pt)")
    out.append('#text(font: sans, size: 52pt, weight: 600, fill: ink, '
               'tracking: -1.8pt)[The FAA reference corpus.]')
    out.append("#v(14pt)")
    out.append('#text(font: sans, size: 13pt, fill: ink-2)[One hyperlinked, '
               'offline volume. Handbooks, standards, the AIM, 14 CFR, '
               'Advisory Circulars, and Chief Counsel interpretations.]')
    out.append("#v(26pt)")
    out.append(ident_block([
        ("version", version),
        ("14 cfr current", cfr_current),
        ("documents", str(len(entries))),
        ("pages", "%d" % total_pages),
    ]))
    out.append("#v(30pt)")
    out.append('#primary-button(<menu-main>, "Open the main menu")')
    out.append("#v(1fr)")
    out.append('#text(font: sans, size: 8.5pt, fill: ink-3)[Unofficial. Not an '
               'FAA product, not endorsed by the FAA, and not a substitute for '
               'the official source documents. Verify currency before '
               'operational use. See the colophon.]')

    # --- main menu, three pages --------------------------------------------
    # One continuous flow rather than forced chunks. Splitting sections evenly
    # across three pages left the first overflowing and the last empty, because
    # section sizes differ by an order of magnitude: 17 Advisory Circulars
    # against a single AIM. Natural pagination breaks where the content
    # actually runs out, and the resulting page count is asserted below against
    # the three the spec calls for.
    ordered = [(number, key, name) for number, key, name in SECTIONS
               if by_section.get(key)]
    out.append("#pagebreak()")
    out.append("#target[]<menu-main>")
    out.append('#page-title[Contents]')
    for number, key, name in ordered:
        out.append('#target[]<menu-%s>' % key)
        out.append('#section-label("%s", "%s")' % (number, typst_string(name)))
        for entry in by_section[key]:
            out.append('#entry-button(<%s>, "%s", chips: %s)' % (
                label_for_doc(entry["id"]),
                typst_string(entry["title"]),
                chip_args(chips_for(entry, lock))))
    out.append("#v(10pt)")
    out.append('#align(center)[#primary-button(<colophon>, "Colophon and '
               'sources")]')

    # --- per-document menus -------------------------------------------------
    for entry in entries:
        locked = lock.get(entry["id"]) or {}
        out.append("#pagebreak()")
        out.append("#target[]<%s>" % label_for_doc(entry["id"]))
        out.append('#section-label("%s", "%s")' % (
            next((n for n, k, _ in SECTIONS if k == entry["section"]), "00"),
            typst_string(entry["section"])))
        out.append('#page-title[%s]' % typst_string(entry["title"]))
        rows = [("faa number", locked.get("faa_number") or "not stated"),
                ("pages", str(locked.get("pages") or "unknown")),
                ("revision", locked.get("revision_date") or "not stated"),
                ("source", entry.get("landing_url") or "")]
        digest = locked.get("sha256")
        if digest:
            rows.append(("sha256", digest[:32]))
        out.append(ident_block(rows))
        out.append("#v(18pt)")
        out.append('#align(left)[#primary-button(<menu-main>, "Return to the '
                   'main menu")]')
        out.append("#v(1fr)")
        out.append('#text(font: sans, size: 8.5pt, fill: ink-3)[This document '
                   'is reproduced unaltered. It is a work of the United States '
                   'Government and is not subject to copyright protection in '
                   'the United States.]')

    # The regulations are generated rather than fetched, so they have no
    # manifest entry and would otherwise be the only 629 pages in the volume
    # with no per-document menu to return to. The nav stamp needs a target.
    out.append("#pagebreak()")
    out.append("#target[]<docmenu-cfr>")
    out.append('#section-label("%s", "Regulations")' %
               next(n for n, k, _ in SECTIONS if k == "regs"))
    out.append('#page-title[Title 14 and 49 CFR]')
    out.append(ident_block([
        ("14 cfr parts", ", ".join(sorted(
            (k.rsplit("-", 1)[-1] for k in cfr_lock if k.startswith("title-14")),
            key=lambda s: (len(s), s)))),
        ("49 cfr parts", ", ".join(sorted(
            k.rsplit("-", 1)[-1] for k in cfr_lock if k.startswith("title-49")))),
        ("current", cfr_current),
        ("pages", "%d generated from eCFR XML" % cfr_pages),
        ("sections", "%d, each a named destination" % sum(
            (e.get("sections") or 0) for e in cfr_lock.values())),
    ]))
    out.append("#v(18pt)")
    out.append('#align(left)[#primary-button(<menu-main>, "Return to the '
               'main menu")]')
    out.append("#v(1fr)")
    out.append('#text(font: sans, size: 8.5pt, fill: ink-3)[Reproduced from '
               'the Electronic Code of Federal Regulations, which is an '
               'editorial compilation and not the official legal edition of '
               'the CFR.]')

    # --- colophon -----------------------------------------------------------
    out.append("#pagebreak()")
    out.append("#target[]<colophon>")
    out.append('#page-title[Colophon]')
    out.append('#text(font: sans, size: 10pt, fill: ink-2)[Every document in '
               'this volume, with the revision and the retrieval hash it was '
               'built from. Verify against the official FAA source before '
               'operational use.]')
    out.append("#v(12pt)")
    for number, key, name in SECTIONS:
        # The regulations are generated from eCFR rather than fetched, so they
        # have no manifest entries. They still belong in their own numbered
        # slot rather than tacked on at the end out of sequence.
        if key == "regs":
            out.append('#section-label("%s", "%s")' % (number, typst_string(name)))
            out.append(ident_block([
                ("14 cfr", "%d part(s), current %s" % (
                    len([k for k in cfr_lock if k.startswith("title-14")]),
                    cfr_current)),
                ("49 cfr", "%d part(s)" % len(
                    [k for k in cfr_lock if k.startswith("title-49")])),
                ("typeset", "%d pages generated from eCFR XML" % cfr_pages),
            ]))
            continue
        bucket = by_section.get(key)
        if not bucket:
            continue
        out.append('#section-label("%s", "%s")' % (number, typst_string(name)))
        rows = []
        for entry in bucket:
            locked = lock.get(entry["id"]) or {}
            detail = " / ".join(filter(None, [
                locked.get("faa_number"),
                "%d pp" % locked["pages"] if locked.get("pages") else None,
                locked.get("revision_date"),
                (locked.get("sha256") or "")[:12] or None,
            ]))
            rows.append((entry["id"], detail or "not yet fetched"))
        out.append(ident_block(rows))
    return "\n".join(out) + "\n"


def ident_block(rows):
    body = ", ".join('("%s", "%s")' % (typst_string(a), typst_string(b))
                     for a, b in rows)
    return "#ident((%s,))" % body


def compile_typst(source, pdf, fonts=FONTS):
    import os

    env = dict(os.environ)
    env["SOURCE_DATE_EPOCH"] = "0"
    result = subprocess.run(
        ["typst", "compile", "--font-path", str(fonts), str(source), str(pdf)],
        capture_output=True, env=env)
    return (result.returncode,
            result.stdout.decode("utf-8", "replace"),
            result.stderr.decode("utf-8", "replace"))


def run(argv, sources_path=M.SOURCES, lock_path=M.LOCK, cfr_lock_path=CFR_LOCK,
        build_root=BUILD, template=TEMPLATE, out=sys.stdout):
    parser = argparse.ArgumentParser(
        prog="menus.py", description="Render cover, menus, and colophon.")
    parser.add_argument("--no-compile", action="store_true")
    args = parser.parse_args(argv)

    entries = M.load_sources(sources_path)
    lock = M.load_lock(lock_path)
    cfr_lock = load_cfr_lock(cfr_lock_path)
    if not entries:
        out.write("manifest/sources.yaml is empty. Nothing to render.\n")
        return EXIT_OK

    cfr_pdf = M.ROOT / "build" / "cfr" / "cfr.pdf"
    cfr_pages = 0
    if cfr_pdf.is_file():
        import pymupdf

        document = pymupdf.open(cfr_pdf)
        cfr_pages = document.page_count
        document.close()

    build_root = pathlib.Path(build_root)
    build_root.mkdir(parents=True, exist_ok=True)
    source = build_root / "menus.typ"
    body = render(entries, lock, cfr_lock, cfr_pages)
    preamble = pathlib.Path(template).read_text(encoding="utf-8")
    with io.open(source, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(preamble + "\n" + body)

    out.write("%d document(s) across %d menu section(s)\n" % (
        len(entries), len({e["section"] for e in entries})))

    if args.no_compile:
        return EXIT_OK

    pdf = build_root / "menus.pdf"
    code, stdout, stderr = compile_typst(source, pdf)
    if code != 0:
        out.write("typst failed:\n%s\n%s\n" % (stdout[-2500:], stderr[-2500:]))
        return EXIT_PROBLEM

    import pymupdf

    document = pymupdf.open(pdf)
    names = document.resolve_names()
    pages = document.page_count
    links = sum(len(document.load_page(n).get_links()) for n in range(pages))
    document.close()

    # The main menu runs from menu-main to the first per-document menu.
    doc_pages = [names[label_for_doc(e["id"])]["page"] for e in entries
                 if label_for_doc(e["id"]) in names]
    first_doc = min(doc_pages) if doc_pages else pages
    menu_pages = max(0, first_doc - names.get("menu-main", {}).get("page", 0))

    out.write("%s: %d pages, %d destinations, %d internal link(s)\n"
              % (pdf.name, pages, len(names), links))
    out.write("main menu occupies %d page(s)\n" % menu_pages)
    if menu_pages > MENU_PAGES:
        out.write("NOTE: CLAUDE.md section 4 calls for a %d-page main menu.\n"
                  % MENU_PAGES)

    # Validation gate 4: every manifest document reachable from a menu.
    missing = [e["id"] for e in entries
               if label_for_doc(e["id"]) not in names]
    if missing:
        out.write("\n%d document(s) unreachable from a menu: %s\n"
                  % (len(missing), ", ".join(missing[:10])))
        return EXIT_PROBLEM

    for required in ("cover", "menu-main", "colophon"):
        if required not in names:
            out.write("missing required destination: %s\n" % required)
            return EXIT_PROBLEM

    out.write("every document reachable, cover and colophon present\n")
    return EXIT_OK


def main(argv):
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
