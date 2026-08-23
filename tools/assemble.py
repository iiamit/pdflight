"""Concatenate everything into one PDF in canonical order, recording offsets.

Canonical order, from CLAUDE.md section 6 and BUILD-PLAN section 6: cover, main
menu, ACS and PTS, handbooks, AIM, 14 CFR, Advisory Circulars, legal
interpretations, guides, colophon.

Each document is preceded by its own per-document menu page, lifted out of the
Phase 4 build. Neither plan says where those pages go; putting each one
immediately before its document is what makes the `[doc]` nav stamp meaningful,
because "back to this document's menu" is then a short jump rather than a trip
to the far end of the file.

The optimized copy of a source is used when Phase 5's `optimize` produced one,
which is what keeps the assembled file inside the size budget. The original is
never modified; `cache/sources` stays exactly as the FAA served it because its
hashes are the drift signal.

Offsets are written to build/offsets.json. Every later stage needs them: the
linker rewrites anchor pages into absolute positions, the outline builder needs
document boundaries, and validation needs to know which pages belong to which
document.
"""

import argparse
import io
import json
import pathlib
import sys

import yaml

import _manifest as M

EXIT_OK = 0
EXIT_PROBLEM = 1

BUILD = M.ROOT / "build"
OUTPUT = BUILD / "pdflight.pdf"
OFFSETS = BUILD / "offsets.json"
MENUS_PDF = BUILD / "menus" / "menus.pdf"
CFR_PDF = BUILD / "cfr" / "cfr.pdf"
OPTIMIZED = M.ROOT / "cache" / "optimized"
OPTIMIZE_LOCK = M.ROOT / "manifest" / "optimize.lock.yaml"

# Section order in the finished volume.
ORDER = ["standards", "handbooks", "aim", "regs", "ac", "interps", "guides"]


def load_optimize_lock(path=OPTIMIZE_LOCK):
    if not pathlib.Path(path).is_file():
        return {}
    with io.open(path, encoding="utf-8") as handle:
        return (yaml.safe_load(handle) or {}).get("optimized", {}) or {}


def source_pdf(key, lock, optimized, cache_root=M.CACHE, out_root=OPTIMIZED):
    """The optimized copy when one exists, otherwise the untouched original."""
    record = optimized.get(key)
    if record:
        candidate = pathlib.Path(out_root) / ("%s.pdf" % record["source_sha256"])
        if candidate.is_file():
            return candidate, True
    entry = lock.get(key) or {}
    if not entry.get("sha256"):
        return None, False
    blob = M.cache_path(entry["sha256"], cache_root)
    return (blob, False) if blob.is_file() else (None, False)


def offset_key(kind, key):
    """A unique key per step.

    A document and its own menu page share an id, so keying offsets by id alone
    silently overwrote every per-document menu entry with the document that
    followed it, and the [doc] nav link had nowhere to point.
    """
    if key is None:
        return kind
    return "%s__menu" % key if kind == "docmenu" else key


def plan(entries, lock, optimized):
    """Every piece to concatenate, in order. No IO beyond stat."""
    by_section = {}
    for entry in entries:
        by_section.setdefault(entry["section"], []).append(entry)
    for bucket in by_section.values():
        bucket.sort(key=lambda e: (e.get("order") or 0, e["id"]))

    steps = [("cover", None), ("menu", None)]
    for section in ORDER:
        if section == "regs":
            steps.append(("docmenu", "cfr"))
            steps.append(("cfr", None))
            continue
        for entry in by_section.get(section, []):
            steps.append(("docmenu", entry["id"]))
            steps.append(("source", entry["id"]))
            for key in sorted(lock):
                if key.startswith(entry["id"] + ".part."):
                    steps.append(("source", key))
            for key in sorted(lock):
                if key.startswith(entry["id"] + ".addendum."):
                    steps.append(("source", key))
    steps.append(("colophon", None))
    return steps


def run(argv, sources_path=M.SOURCES, lock_path=M.LOCK, menus_pdf=MENUS_PDF,
        cfr_pdf=CFR_PDF, output=OUTPUT, offsets_path=OFFSETS,
        cache_root=M.CACHE, out=sys.stdout):
    parser = argparse.ArgumentParser(
        prog="assemble.py",
        description="Concatenate the corpus into one PDF in canonical order.")
    parser.add_argument("--dry-run", action="store_true",
                        help="report the plan and the page budget, build nothing")
    args = parser.parse_args(argv)

    import pymupdf

    entries = M.load_sources(sources_path)
    lock = M.load_lock(lock_path)
    optimized = load_optimize_lock()
    steps = plan(entries, lock, optimized)

    menus_path = pathlib.Path(menus_pdf)
    if not menus_path.is_file():
        out.write("build/menus/menus.pdf is missing. Run make menus.\n")
        return EXIT_PROBLEM
    menus = pymupdf.open(menus_path)
    menu_names = menus.resolve_names()

    import menus as menus_tool

    # Where each generated page lives inside menus.pdf.
    cover_page = menu_names["cover"]["page"]
    menu_start = menu_names["menu-main"]["page"]
    colophon_page = menu_names["colophon"]["page"]
    doc_menu_page = {}
    for ident in [e["id"] for e in entries] + ["cfr"]:
        label = menus_tool.label_for_doc(ident)
        if label in menu_names:
            doc_menu_page[ident] = menu_names[label]["page"]
    menu_end = min([p for p in doc_menu_page.values()] or [colophon_page])

    missing, total, offsets = [], 0, {}
    sizes = {}
    for kind, key in steps:
        if kind == "cover":
            count = menu_start - cover_page
        elif kind == "menu":
            count = menu_end - menu_start
        elif kind == "colophon":
            count = menus.page_count - colophon_page
        elif kind == "docmenu":
            if key not in doc_menu_page:
                missing.append("%s (menu page)" % key)
                continue
            count = 1
        elif kind == "cfr":
            cfr = pathlib.Path(cfr_pdf)
            if not cfr.is_file():
                missing.append("cfr")
                continue
            document = pymupdf.open(cfr)
            count = document.page_count
            document.close()
            sizes["cfr"] = cfr.stat().st_size
        else:
            path, was_optimized = source_pdf(key, lock, optimized, cache_root)
            if path is None:
                missing.append(key)
                continue
            count = (lock.get(key) or {}).get("pages") or 0
            sizes[key] = path.stat().st_size
            if not count:
                document = pymupdf.open(path)
                count = document.page_count
                document.close()
        offsets[offset_key(kind, key)] = {"kind": kind, "start": total + 1,
                                          "pages": count}
        total += count

    menus.close()

    out.write("%d step(s), %d page(s), %.0f MB of input\n"
              % (len(steps), total, sum(sizes.values()) / 1048576))
    if missing:
        out.write("%d piece(s) unavailable: %s\n"
                  % (len(missing), ", ".join(missing[:8])))
        return EXIT_PROBLEM

    if args.dry_run:
        for section in ORDER:
            members = [e["id"] for e in entries if e["section"] == section]
            if members:
                out.write("  %-10s %d document(s)\n" % (section, len(members)))
        return EXIT_OK

    # --- build -------------------------------------------------------------
    output = pathlib.Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    result = pymupdf.open()
    menus = pymupdf.open(menus_path)
    placed = {}
    cursor = 0

    for kind, key in steps:
        before = cursor
        if kind == "cover":
            result.insert_pdf(menus, from_page=cover_page,
                              to_page=menu_start - 1)
        elif kind == "menu":
            result.insert_pdf(menus, from_page=menu_start, to_page=menu_end - 1)
        elif kind == "colophon":
            result.insert_pdf(menus, from_page=colophon_page,
                              to_page=menus.page_count - 1)
        elif kind == "docmenu":
            page = doc_menu_page[key]
            result.insert_pdf(menus, from_page=page, to_page=page)
        elif kind == "cfr":
            document = pymupdf.open(cfr_pdf)
            result.insert_pdf(document)
            document.close()
        else:
            path, _was = source_pdf(key, lock, optimized, cache_root)
            document = pymupdf.open(path)
            result.insert_pdf(document)
            document.close()
        cursor = result.page_count
        placed[offset_key(kind, key)] = {"kind": kind, "start": before + 1,
                                         "pages": cursor - before}
        out.write("  %-10s %-26s p%-6d %d page(s)\n"
                  % (kind, key or "", before + 1, cursor - before))

    menus.close()
    result.save(str(output), garbage=3, deflate=True)
    size = output.stat().st_size
    result.close()

    with io.open(offsets_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"total_pages": cursor, "offsets": placed}, handle,
                  indent=2, sort_keys=True)
        handle.write("\n")

    out.write("\n%s: %d pages, %.1f MB\n"
              % (output.name, cursor, size / 1048576))
    out.write("size budget: %s\n" % (
        "PASS" if size < 500 * 1048576 else "OVER THE 500 MB HARD FAIL"))
    return EXIT_OK


def main(argv):
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
