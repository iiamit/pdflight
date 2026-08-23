"""Stamp persistent navigation and rewrite anchors into absolute pages.

Two jobs.

**Nav stamps.** Every content page gets two link rectangles bottom-left,
`[menu]` and `[doc]`, mono 8pt amber on a translucent slab with a hair border,
matching the `.tail-chip` treatment in CLAUDE.md section 6. Without them a
reader who lands deep in a 6,122 page file by scrolling has no way back.

Pages that *are* the navigation are exempt: the cover, the main menu, the
per-document menus, and the colophon each already carry their own controls, and
a `[menu]` link pointing at the page you are already on is noise. Validation
gate 5 says "every page carries a persistent nav stamp"; this reads that as
every page that is not itself navigation, and records the exempt set so the
gate can check the interpretation rather than guess it.

**Absolute anchors.** anchors.lock.json holds pages relative to each source
document. Once assembled, `phak:ch15` means a different page. This rewrites
each anchor to its position in the finished file and writes
build/anchors-absolute.json, which is what the crosswalk links against in
Phase 6.

Only simple `/GoTo` actions with named destinations are used. No JavaScript, no
`GoToR`, no embedded files, per section 10.
"""

import argparse
import io
import json
import pathlib
import sys

import _manifest as M

EXIT_OK = 0
EXIT_PROBLEM = 1

BUILD = M.ROOT / "build"
ASSEMBLED = BUILD / "pdflight.pdf"
OFFSETS = BUILD / "offsets.json"
LINKED = BUILD / "pdflight-linked.pdf"
ABSOLUTE = BUILD / "anchors-absolute.json"
ANCHORS_LOCK = M.ROOT / "anchors" / "anchors.lock.json"

# Generated navigation. These pages are exempt from the stamp.
NAV_KINDS = ("cover", "menu", "docmenu", "colophon")

SIGNAL = (1.0, 0.694, 0.408)      # #FFB168
SLAB = (0.039, 0.051, 0.078)      # #0A0D14
HAIR = (0.235, 0.243, 0.263)

STAMP_HEIGHT = 13.0
STAMP_PAD = 5.0
STAMP_MARGIN = 18.0


def load_offsets(path=OFFSETS):
    with io.open(path, encoding="utf-8") as handle:
        return json.load(handle)


def load_anchors(path=ANCHORS_LOCK):
    if not pathlib.Path(path).is_file():
        return {}
    with io.open(path, encoding="utf-8") as handle:
        return json.load(handle).get("anchors", {})


def absolute_page(anchor, offsets):
    """Map a document-relative anchor page onto the assembled file."""
    doc = anchor.get("doc")
    key = "cfr" if doc == "cfr" else doc
    entry = offsets.get(key)
    if not entry:
        return None
    page = anchor.get("page") or 0
    if page < 1 or page > entry["pages"]:
        return None
    return entry["start"] + page - 1


def stamp_targets(offsets):
    """Page ranges that get a stamp, with the doc menu each belongs to."""
    targets = {}
    for key, entry in offsets.items():
        if entry["kind"] in NAV_KINDS:
            continue
        doc_menu = offsets.get(key, {}).get("menu_page")
        for index in range(entry["pages"]):
            targets[entry["start"] + index] = (key, doc_menu)
    return targets


def draw_stamp(page, menu_page, doc_page, pymupdf):
    """Two tap targets bottom-left. Simple GoTo, nothing exotic."""
    rect = page.rect
    y1 = rect.height - STAMP_MARGIN
    y0 = y1 - STAMP_HEIGHT
    drawn = []
    x = STAMP_MARGIN
    for label, target in (("menu", menu_page), ("doc", doc_page)):
        if target is None:
            continue
        width = 34.0
        box = pymupdf.Rect(x, y0, x + width, y1)
        shape = page.new_shape()
        shape.draw_rect(box)
        shape.finish(fill=SLAB, color=HAIR, width=0.5, fill_opacity=0.55)
        shape.commit()
        page.insert_textbox(
            box, label, fontname="cour", fontsize=7.0, color=SIGNAL,
            align=pymupdf.TEXT_ALIGN_CENTER)
        page.insert_link({
            "kind": pymupdf.LINK_GOTO,
            "from": box,
            "page": target,
        })
        drawn.append(label)
        x += width + 4.0
    return drawn


def write_named_destinations(document, mapping, pymupdf):
    """Rebuild the /Dests name tree on the assembled document.

    `insert_pdf` does not carry named destinations. Assembly therefore
    destroyed every one of them: 42 from the generated pages and 967 from the
    CFR build, leaving zero in a file whose whole premise is that
    `14cfr:91.155` resolves by name. Page-number GoTo links still worked, which
    is why nothing looked broken until the gate was written.

    The name tree is built by hand because PyMuPDF exposes no writer for it.
    Entries must be sorted by name; a PDF reader binary-searches this array and
    an unsorted one resolves intermittently.
    """
    kids = []
    for name in sorted(mapping):
        page_number = mapping[name]
        if page_number < 1 or page_number > document.page_count:
            continue
        page = document.load_page(page_number - 1)
        xref = document.get_new_xref()
        document.update_object(
            xref, "<</D[%d 0 R /XYZ 0 %d 0]>>"
            % (document.page_xref(page_number - 1), int(page.rect.height)))
        kids.append("(%s) %d 0 R" % (name, xref))

    if not kids:
        return 0
    names_xref = document.get_new_xref()
    document.update_object(names_xref, "<</Names[%s]>>" % " ".join(kids))
    document.xref_set_key(document.pdf_catalog(), "Names",
                          "<</Dests %d 0 R>>" % names_xref)
    return len(kids)


def destination_map(offsets, resolved, cfr_pdf, menus_pdf, pymupdf):
    """Every name the finished file should answer to, at absolute pages."""
    import menus as menus_tool

    mapping = {}

    # Generated navigation, from the offsets rather than the menus file, since
    # those pages were re-ordered during assembly.
    for key, entry in offsets.items():
        if entry["kind"] == "cover":
            mapping["cover"] = entry["start"]
        elif entry["kind"] == "menu":
            mapping["menu-main"] = entry["start"]
        elif entry["kind"] == "colophon":
            mapping["colophon"] = entry["start"]
        elif entry["kind"] == "docmenu":
            ident = key[:-len("__menu")]
            mapping[menus_tool.label_for_doc(ident)] = entry["start"]

    # Anchors, already absolute.
    for ref, anchor in resolved.items():
        mapping[ref] = anchor["page"]

    # Every CFR section label, offset into place.
    record = offsets.get("cfr")
    if record and pathlib.Path(cfr_pdf).is_file():
        document = pymupdf.open(cfr_pdf)
        try:
            for name, info in document.resolve_names().items():
                page = info.get("page")
                if page is None:
                    continue
                mapping[name] = record["start"] + page
        finally:
            document.close()
    return mapping


def run(argv, assembled=ASSEMBLED, offsets_path=OFFSETS, output=LINKED,
        anchors_path=ANCHORS_LOCK, absolute_path=ABSOLUTE, out=sys.stdout):
    parser = argparse.ArgumentParser(
        prog="link.py",
        description="Stamp navigation and rewrite anchors to absolute pages.")
    parser.add_argument("--no-stamp", action="store_true",
                        help="rewrite anchors only, leave the PDF alone")
    args = parser.parse_args(argv)

    import pymupdf
    import menus as menus_tool

    if not pathlib.Path(assembled).is_file():
        out.write("build/pdflight.pdf is missing. Run make assemble.\n")
        return EXIT_PROBLEM

    data = load_offsets(offsets_path)
    offsets = data["offsets"]
    entries = M.load_sources()

    # Each document's own menu page, so [doc] has somewhere to go. Addenda and
    # parts inherit their parent's menu, which is why the id is split on the
    # first dot.
    ordered = sorted(offsets.items(), key=lambda kv: kv[1]["start"])
    menu_page_for = {}
    for entry in entries:
        record = offsets.get(entry["id"] + "__menu")
        if record:
            menu_page_for[entry["id"]] = record["start"]

    main_menu = next((e["start"] for _k, e in ordered if e["kind"] == "menu"), 1)

    # --- absolute anchors ---------------------------------------------------
    anchors = load_anchors(anchors_path)
    resolved, dropped = {}, []
    for ref, anchor in anchors.items():
        page = absolute_page(anchor, offsets)
        if page is None:
            dropped.append(ref)
            continue
        resolved[ref] = dict(anchor, page=page, relative_page=anchor["page"])

    with io.open(absolute_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"total_pages": data["total_pages"], "anchors": resolved},
                  handle, indent=2, sort_keys=True)
        handle.write("\n")
    out.write("%d anchor(s) rewritten to absolute pages, %d dropped\n"
              % (len(resolved), len(dropped)))
    for ref in dropped[:6]:
        out.write("  dropped: %s\n" % ref)

    if args.no_stamp:
        return EXIT_PROBLEM if dropped else EXIT_OK

    # --- nav stamps ---------------------------------------------------------
    document = pymupdf.open(assembled)
    stamped, exempt = 0, 0
    for key, entry in ordered:
        if entry["kind"] in NAV_KINDS:
            exempt += entry["pages"]
            continue
        base = key.split(".")[0]
        doc_page = menu_page_for.get(base)
        for index in range(entry["pages"]):
            number = entry["start"] + index - 1
            if number >= document.page_count:
                break
            page = document.load_page(number)
            draw_stamp(page, main_menu - 1,
                       (doc_page - 1) if doc_page else None, pymupdf)
            stamped += 1

    mapping = destination_map(
        offsets, resolved, M.ROOT / "build" / "cfr" / "cfr.pdf",
        M.ROOT / "build" / "menus" / "menus.pdf", pymupdf)
    written = write_named_destinations(document, mapping, pymupdf)

    document.save(str(output), garbage=3, deflate=True)
    size = pathlib.Path(output).stat().st_size
    document.close()

    out.write("stamped %d page(s), %d navigation page(s) exempt\n"
              % (stamped, exempt))
    out.write("rebuilt %d named destination(s) destroyed by assembly\n" % written)
    out.write("%s: %.1f MB\n" % (pathlib.Path(output).name, size / 1048576))
    return EXIT_PROBLEM if dropped else EXIT_OK


def main(argv):
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
