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
import csv
import io
import json
import pathlib
import re
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


# Citation forms that appear in an ACS References line.
CITE_HANDBOOK = re.compile(r"FAA-H-(\d{4}-\d+)[A-Z]?")
CITE_AC = re.compile(r"\bAC\s+(\d{1,3}[-.]\d+[A-Z]?)")
CITE_AIM = re.compile(r"\bAIM\b")
CITE_CFR = re.compile(r"14\s+CFR\s+parts?\s+([\d,\s]*\d)")
CFR_NUMBER = re.compile(r"\d+")


def page_lines(page):
    """Words grouped into lines, with a reconstructed string per line."""
    grouped = {}
    for word in page.get_text("words"):
        grouped.setdefault(round(word[1], 1), []).append(word)

    lines = []
    for key in sorted(grouped):
        words = sorted(grouped[key], key=lambda w: w[0])
        text, spans, cursor = "", [], 0
        for word in words:
            if text:
                text += " "
                cursor += 1
            spans.append((cursor, cursor + len(word[4]), word))
            text += word[4]
            cursor += len(word[4])
        lines.append((text, spans))
    return lines


def rect_for_span(spans, start, end, pymupdf):
    """Union of the word rectangles overlapping a character span."""
    boxes = [word for begin, finish, word in spans
             if begin < end and finish > start]
    if not boxes:
        return None
    rect = pymupdf.Rect(boxes[0][:4])
    for word in boxes[1:]:
        rect |= pymupdf.Rect(word[:4])
    return rect


def citations_in(text):
    """Yield (start, end, target_ref) for every citation on a line."""
    for match in CITE_HANDBOOK.finditer(text):
        yield match.start(), match.end(), "handbook:%s" % match.group(1)
    for match in CITE_AC.finditer(text):
        yield match.start(), match.end(), "ac:%s" % match.group(1).lower()
    for match in CITE_AIM.finditer(text):
        yield match.start(), match.end(), "aim"
    for match in CITE_CFR.finditer(text):
        # Each part number gets its own link, so "14 CFR parts 61, 68, 91"
        # becomes three targets rather than one vague jump.
        base = match.start(1)
        for number in CFR_NUMBER.finditer(match.group(1)):
            yield (base + number.start(), base + number.end(),
                   "14cfr:part-%s" % number.group(0))


def link_citations(page, resolver, pymupdf):
    """Turn every recognised citation on the page into a GoTo link."""
    added = 0
    for text, spans in page_lines(page):
        if not ("FAA-H-" in text or "CFR" in text or "AC " in text
                or "AIM" in text):
            continue
        for start, end, ref in citations_in(text):
            target = resolver(ref)
            if target is None:
                continue
            rect = rect_for_span(spans, start, end, pymupdf)
            if rect is None:
                continue
            page.insert_link({"kind": pymupdf.LINK_GOTO, "from": rect,
                              "page": target - 1})
            added += 1
    return added


# The element code as it sits inline on an ACS page, followed by its text.
# bootstrap_crosswalk anchors its copy to a whole line, which is right when
# parsing the outline and wrong when locating the code among words.
ELEMENT_INLINE = re.compile(r"\b([A-Z]{2}\.[IVX]+\.[A-Z]\.[KRS]\d+[a-z]?)\b")


def element_targets(root=None, every_kind=False):
    """Element code -> its targets, from the crosswalk.

    By default only CFR section rows, which is what the crosswalk pages list.
    With `every_kind` the handbook and Advisory Circular rows come too, in
    specificity order, which is what the inline buttons draw.

    A part-level CFR row is never returned. It already has a surface: the
    References line names the part in so many words, and link_citations turns
    that text into the link.
    """
    import bootstrap_crosswalk as BC

    base = pathlib.Path(root) if root else (M.ROOT / "crosswalk")
    found = {}
    for name, _document_id, _prefix in BC.CERTIFICATES:
        path = base / ("%s.csv" % name)
        if not path.is_file():
            continue
        with io.open(path, encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                ref = row["target_ref"]
                if ref.startswith("14cfr:part-"):
                    continue
                if not every_kind and not ref.startswith("14cfr:"):
                    continue
                found.setdefault(row["source_ref"], []).append(ref)

    if every_kind:
        for code in found:
            found[code] = sorted(set(found[code]), key=target_rank)
    return found


def specific_targets(root=None):
    """Targets precise enough to deserve a button on the ACS page.

    A button means "here is the rule". A document-level row such as `phak`
    means "here is a 522 page handbook", which the References line above the
    element already links to, so drawing it inline adds clutter and no reach.
    Refine a handbook row to `phak:ch15` and it earns a button automatically.
    """
    return {code: [ref for ref in refs if ":" in ref]
            for code, refs in element_targets(root, every_kind=True).items()
            if any(":" in ref for ref in refs)}


def target_rank(ref):
    """Sort key putting the most specific target first.

    Width on an ACS line is finite, so when not every target fits the ones
    that survive should be the ones that land on a paragraph rather than on
    the front of a 522 page handbook.
    """
    if ref.startswith("14cfr:") or ref.startswith("49cfr:"):
        return (0, ref)
    if ":" in ref:                      # phak:ch15, ac:61-65k:para-14
        return (1, ref)
    if ref.startswith("ac-"):
        return (2, ref)
    return (3, ref)


# What a button says. These are the names the corpus already uses for these
# documents, not abbreviations invented here.
# A button is a few millimetres wide, so the label is the shortest form the
# FAA itself uses: the common abbreviation where there is one, otherwise the
# handbook number without its FAA-H- prefix. Nothing here is coined.
SHORT_LABEL = {
    "phak": "PHAK", "afh": "AFH", "ifh": "IFH", "iph": "IPH", "aim": "AIM",
    "risk-management": "8083-2", "seaplane": "8083-23",
    "aviation-weather": "8083-28", "awh": "8083-28",
    "weight-balance": "8083-1", "aviation-instructor": "8083-9",
    "plane-sense": "8083-19",
}

# The AIM cites itself as chapter-section, so `aim:ch03-s02` reads "AIM 3-2".
AIM_ANCHOR = re.compile(r"^ch(\d+)-s(\d+)$")
LEADING_NUMBER = re.compile(r"^(\d+)-")


# Button colour by what the target is.
#
# CLAUDE.md section 6 reserves amber for actions and live signals, so this is a
# deliberate widening of the palette rather than drift: a reader scanning an
# ACS page needs to tell a regulation from a handbook without reading the
# label. Every colour below is chosen to sit on the near-black button slab, and
# the slab is what keeps them legible on a white FAA page.
REG = (0.482, 0.847, 0.561)        # #7BD88F  regulations, 14 and 49 CFR
BOOK = (0.498, 0.706, 1.0)         # #7FB4FF  handbooks
MANUAL = (0.753, 0.549, 1.0)       # #C08CFF  the AIM
CIRCULAR = (1.0, 0.694, 0.408)     # #FFB168  Advisory Circulars, the signal amber

TARGET_KIND = (
    ("regulation", REG),
    ("handbook", BOOK),
    ("manual", MANUAL),
    ("circular", CIRCULAR),
)


def target_kind(ref):
    """Which family a target belongs to, for colour and for the legend."""
    head = ref.split(":", 1)[0]
    if head in ("14cfr", "49cfr"):
        return "regulation"
    if head == "aim":
        return "manual"
    if head.startswith("ac-") or head == "ac":
        return "circular"
    return "handbook"


def color_for_ref(ref):
    kind = target_kind(ref)
    return dict(TARGET_KIND)[kind]


def button_label(ref):
    """The text on a target button, or None when it cannot be named."""
    if ref.startswith("14cfr:"):
        return ref.split(":", 1)[1]
    if ref.startswith("49cfr:"):
        return ref.split(":", 1)[1]
    if ref.startswith("ac-"):
        return "AC " + ref[3:].upper()
    if ref.startswith("ac:"):
        parts = ref.split(":")
        # An AC anchored at paragraph or appendix granularity needs the
        # paragraph in the label. AC 61-65K carries 60 endorsements in
        # Appendix A, and without this every one of them is a chip reading
        # "AC 61-65K" whose destination is arbitrary.
        if len(parts) > 2 and parts[2]:
            return "AC %s %s" % (parts[1].upper(), parts[2].upper())
        return "AC " + parts[1].upper()
    head = ref.split(":")[0]
    base = SHORT_LABEL.get(head)
    if not base:
        return None
    if ":" not in ref:
        return base
    tail = ref.split(":", 1)[1]
    section = AIM_ANCHOR.match(tail)
    if section:
        return "%s %d-%d" % (base, int(section.group(1)), int(section.group(2)))
    if tail.startswith("ch"):
        return "%s c%s" % (base, tail[2:].lstrip("0") or "0")
    # The older Aviation Weather anchors are named `2-aviation-weather-...`
    # rather than `ch02`. Without this they all label as the bare handbook
    # number, and five different chapters share one chip.
    lead = LEADING_NUMBER.match(tail)
    if lead:
        return "%s c%s" % (base, lead.group(1).lstrip("0") or "0")

    # A topic anchor, which is how the seaplane handbook is anchored because
    # it has no outline. Falling through to the bare handbook number gave all
    # 33 of its anchors the same chip, so that chip's destination was
    # arbitrary. The topic is the FAA's own section heading, so naming the
    # chip after it invents nothing. These run wider than a chapter label and
    # will often overflow the inline buttons, which is what the crosswalk page
    # is for.
    words = [w for w in tail.replace("_", "-").split("-") if w]
    if words:
        return " ".join(w.capitalize() for w in words)
    return base


# A section chip on a crosswalk page, rendered by templates/menu.typ as
# `#sym.section 91.119`. Some builds of PyMuPDF hand back the section sign as
# its own word and some glue it to the number, so the sign is optional here and
# the number carries the match.
SECTION_CHIP = re.compile(r"(?:§\s*)?\b(\d{1,3}\.\d{1,4}[a-z]?)\b")

# An element code sitting in the ACS left-hand column rather than mentioned in
# a contents list. Measured across both ACS documents: 1,569 codes sit at
# x0 < 110 and are definitions, 109 sit further right and are contents entries.
CODE_COLUMN_X = 110.0


def element_code_rects(page, pymupdf, left_column_only=False):
    """Yield (code, rect) for every element code on the page."""
    for text, spans in page_lines(page):
        for match in ELEMENT_INLINE.finditer(text):
            rect = rect_for_span(spans, match.start(1), match.end(1), pymupdf)
            if rect is None:
                continue
            if left_column_only and rect.x0 >= CODE_COLUMN_X:
                continue
            yield match.group(1), rect


# Inline target buttons, the affordance the ACE Guide uses. Sized so a four
# button set fits the median element; see element_blocks for the measurement.
BUTTON_FONT = 5.2
BUTTON_CHAR = 3.15          # JetBrains Mono advance at BUTTON_FONT
BUTTON_PAD = 3.4
BUTTON_GAP = 2.6
BUTTON_LEAD = 5.0           # clear of the last word
BUTTON_HEIGHT = 8.2
RIGHT_EDGE = 576.0          # page width 612 less the 36pt margin
TEXT_COLUMN_X = 110.0
# Element prose begins at x=122 on every ACS page measured. A row whose
# first text word starts further right is a column of something else.
TEXT_COLUMN_START_MAX = 135.0


def button_width(label):
    return len(label) * BUTTON_CHAR + 2 * BUTTON_PAD


def element_blocks(page, pymupdf):
    """Per element on the page: its code, and where its text stops.

    A button goes after the *last* line of the element, not the first. An
    earlier version measured the line carrying the code, which for wrapped
    text is always full width, and concluded there was no room anywhere. The
    last line leaves a median of 225pt.
    """
    words = page.get_text("words")
    if not words:
        return []

    rows = {}
    for word in words:
        rows.setdefault(round(word[1] / 3.0), []).append(word)
    buckets = sorted(rows)

    codes = []
    for bucket in buckets:
        for word in sorted(rows[bucket], key=lambda a: a[0]):
            if ELEMENT_INLINE.fullmatch(word[4]) and word[0] < CODE_COLUMN_X:
                codes.append((bucket, word[4]))

    blocks = []
    for index, (bucket, code) in enumerate(codes):
        stop = codes[index + 1][0] if index + 1 < len(codes) else 10 ** 9

        # The code's own row must carry element text, starting where the ACS
        # text column starts. Without this the changelog page in the front
        # matter, which lists codes in four columns and no prose, reads as
        # 100 elements whose neighbouring column is their text, and gets
        # buttons stamped across it.
        own = [w for w in rows[bucket] if w[0] >= TEXT_COLUMN_X]
        if not own or min(w[0] for w in own) > TEXT_COLUMN_START_MAX:
            continue
        if all(ELEMENT_INLINE.fullmatch(w[4]) for w in own):
            continue

        tail = None
        for other in buckets:
            if other < bucket or other >= stop:
                continue
            # An element's continuation lines carry nothing in the left-hand
            # column. A row that does is the next thing starting: `Skills:`,
            # `References:`, `Objective:`. Without this the element's buttons
            # were drawn after the following section header instead of after
            # its own text.
            if other > bucket and any(w[0] < TEXT_COLUMN_X for w in rows[other]):
                break
            body = [w for w in rows[other] if w[0] >= TEXT_COLUMN_X]
            if body and min(w[0] for w in body) <= TEXT_COLUMN_START_MAX:
                tail = (max(w[2] for w in body),
                        min(w[1] for w in body), max(w[3] for w in body))
        if tail:
            blocks.append((code, tail[0], tail[1], tail[2]))
    return blocks


def draw_target_buttons(page, blocks, targets, resolver, pymupdf):
    """Draw a link button per target, inline after the element text.

    Returns (drawn, elements_touched, dropped). Buttons that will not fit
    before the right margin are dropped rather than overprinted, and the
    element code still links to the crosswalk row that lists every target.
    """
    drawn, touched, dropped = 0, 0, 0
    for code, tail, y0, y1 in blocks:
        refs = targets.get(code)
        if not refs:
            continue

        placed = 0
        x = tail + BUTTON_LEAD
        for ref in refs:
            label = button_label(ref)
            if not label:
                continue
            target = resolver(ref)
            if target is None:
                continue
            width = button_width(label)
            if x + width > RIGHT_EDGE:
                dropped += 1
                continue

            top = min(y0, y1 - BUTTON_HEIGHT)
            box = pymupdf.Rect(x, top, x + width, top + BUTTON_HEIGHT)
            shape = page.new_shape()
            shape.draw_rect(box)
            tint = color_for_ref(ref)
            shape.finish(fill=SLAB, color=tint, width=0.4, fill_opacity=0.92)
            shape.commit()
            page.insert_textbox(
                box, label, fontname="cour", fontsize=BUTTON_FONT,
                color=tint, align=pymupdf.TEXT_ALIGN_CENTER)
            page.insert_link({"kind": pymupdf.LINK_GOTO, "from": box,
                              "page": target - 1})
            x += width + BUTTON_GAP
            placed += 1
            drawn += 1
        if placed:
            touched += 1
    return drawn, touched, dropped


def link_element_to_hub(page, hub_page_of, pymupdf):
    """Point each ACS element code at its row on the crosswalk page.

    An element is commonly governed by three or four sections, and there is
    nowhere on the ACS page to put three or four links. Measured: 30 percent of
    element rows leave under 9pt between the end of the FAA text and the right
    margin, so a strip of chips would overprint the regulation it is citing.

    So the code carries one link, to a row that carries the rest. That row is
    also what the reader comes back to between targets.
    """
    added = 0
    for code, rect in element_code_rects(page, pymupdf, left_column_only=True):
        target = hub_page_of.get(code)
        if target is None:
            continue
        page.insert_link({"kind": pymupdf.LINK_GOTO, "from": rect,
                          "page": target - 1})
        added += 1
    return added


# `ACS VIII` on an area index row. The Crosswalk chip beside it is a Typst
# link, because both ends are generated pages; this one points into the ACS
# document, which does not exist when the menus compile.
AREA_CHIP = re.compile(r"\bACS\s+([IVX]{1,4})\b")


def link_area_index(page, prefix, resolver, pymupdf):
    """Point each area row at that Area of Operation in the ACS itself."""
    if not prefix:
        return 0
    added = 0
    for text, spans in page_lines(page):
        for match in AREA_CHIP.finditer(text):
            ref = "acs:%s:area-%s" % (prefix, match.group(1).lower())
            target = resolver(ref)
            if target is None:
                continue
            rect = rect_for_span(spans, match.start(), match.end(), pymupdf)
            if rect is None:
                continue
            page.insert_link({"kind": pymupdf.LINK_GOTO, "from": rect,
                              "page": target - 1})
            added += 1
    return added


def chip_index(targets):
    """Chip label -> target ref, for every target the crosswalk carries.

    Matching chips by a number pattern only ever found the CFR ones, so the
    handbook and AIM chips rendered on the crosswalk pages and went nowhere.
    That mattered most for the targets that overflow the inline buttons,
    because the crosswalk page is the only place they appear at all.

    A label is unambiguous by construction: `PHAK c15` names one anchor, so
    every occurrence of it on a crosswalk page resolves the same way.
    """
    index = {}
    for refs in targets.values():
        for ref in refs:
            label = button_label(ref)
            if label:
                index.setdefault(label, ref)
    return index


def link_hub_row(page, chips, acs_page_of, resolver, pymupdf):
    """Wire up one crosswalk page.

    Two kinds of link. The element code returns to the ACS page it was read
    from, which is the leg that lets a reader work through four sources and
    still find their place. Each chip jumps to what it names.
    """
    codes, linked = 0, 0
    for code, rect in element_code_rects(page, pymupdf):
        target = acs_page_of.get(code)
        if target is None:
            continue
        page.insert_link({"kind": pymupdf.LINK_GOTO, "from": rect,
                          "page": target - 1})
        codes += 1

    # Only text that is somebody's chip label becomes a link, so the version
    # string in the status strip cannot turn into a false jump. The index spans
    # every target rather than this page's, because an element whose row
    # straddles a page break leaves its chips on the page after its code.
    for text, spans in page_lines(page):
        taken = []
        # Longest first, because `AFH c1` is a prefix of `AFH c11` and `61.3`
        # of `61.31`. Matching the short one first would link the wrong
        # chapter and leave the real chip unlinked.
        for label in sorted(chips, key=len, reverse=True):
            ref = chips[label]
            start = 0
            while True:
                at = text.find(label, start)
                if at < 0:
                    break
                end = at + len(label)
                start = end
                if not _standalone(text, at, end):
                    continue
                if any(a < end and b > at for a, b in taken):
                    continue
                target = resolver(ref)
                if target is None:
                    continue
                rect = rect_for_span(spans, at, end, pymupdf)
                if rect is None:
                    continue
                page.insert_link({"kind": pymupdf.LINK_GOTO, "from": rect,
                                  "page": target - 1})
                taken.append((at, end))
                linked += 1
    return codes, linked


def _standalone(text, start, end):
    """True when the span is not sitting inside a longer token."""
    before = text[start - 1] if start else " "
    after = text[end] if end < len(text) else " "
    return not (before.isalnum() or before in ".-"
                or after.isalnum() or after in ".-")


def build_resolver(mapping, lock, entries):
    """Map a citation token onto an absolute page.

    Handbook numbers are matched without their revision letter, because an ACS
    cites FAA-H-8083-25 while the document reports FAA-H-8083-25C.
    """
    import bootstrap_crosswalk as BC
    import menus as menus_tool

    handbooks = BC.handbook_index(lock)
    circulars = BC.ac_index(entries)

    def resolve(ref):
        if ref.startswith("handbook:"):
            ident = handbooks.get(ref.split(":", 1)[1])
            return mapping.get(menus_tool.label_for_doc(ident)) if ident else None
        if ref.startswith("ac:"):
            base = re.sub(r"[a-z]$", "", ref.split(":", 1)[1])
            ident = circulars.get(base)
            return mapping.get(menus_tool.label_for_doc(ident)) if ident else None
        if ref == "aim":
            ident = next((e["id"] for e in entries if e["section"] == "aim"), None)
            return mapping.get(menus_tool.label_for_doc(ident)) if ident else None
        if ref.startswith("14cfr:part-"):
            return mapping.get("part-14-%s" % ref.rsplit("-", 1)[-1])

        direct = mapping.get(ref)
        if direct is not None:
            return direct

        # A section target such as `14cfr:91.119`. The CFR build labels every
        # section `sec-{part}-{number}`, so the jump resolves by name with no
        # text matching. Hand-authored anchors are consulted first, above,
        # because a curated anchor may point at a subsection rather than the
        # section head.
        if ref.startswith("14cfr:"):
            number = ref.split(":", 1)[1]
            if "." in number:
                part, tail = number.split(".", 1)
                return mapping.get("sec-%s-%s" % (part, tail.replace(".", "-")))

        # A bare document id from the crosswalk, such as `phak` or `ac-91-92`.
        # It resolves to that document's own menu page, which is its front
        # door and the only target the crosswalk has for it until the handbook
        # rows are refined to chapters.
        if ":" not in ref:
            return mapping.get(menus_tool.label_for_doc(ref))
        return None

    return resolve


def relink_generated(document, offsets, menus_pdf, pymupdf):
    """Redraw the links Typst put on the generated pages.

    `insert_pdf` does not carry a link whose target is a named destination.
    Not a page-range problem: copying the whole of menus.pdf still leaves the
    page with no annotations at all. Every menu link is a `/Named` link,
    because that is the only kind Typst emits, so assembly silently stripped
    all 73 of them. The cover, the contents, every entry arrow, the colophon
    button, and every "Return to the main menu" did nothing.

    Nothing caught it. Gate 2 only inspects `GOTO` links, and zero links means
    nothing dangles. Gate 5 exempts navigation pages from the stamp check by
    design. Gate 4 asked whether the destination *name* existed, which it did.

    The fix is to read the links back off menus.pdf and redraw them as plain
    page GoTo, which is what everything else in this file already uses.
    """
    menus = pathlib.Path(menus_pdf)
    if not menus.is_file():
        return 0

    # Source page index in menus.pdf -> page in the assembled file.
    source_to_page = {}
    for _key, entry in offsets.items():
        first = entry.get("source_start")
        if entry["kind"] not in NAV_KINDS or first is None:
            continue
        for index in range(entry["pages"]):
            source_to_page[first + index] = entry["start"] + index

    document_menus = pymupdf.open(menus)
    added = 0
    try:
        for source_index, target_page in sorted(source_to_page.items()):
            if source_index >= document_menus.page_count:
                continue
            if target_page > document.page_count:
                continue
            source_page = document_menus.load_page(source_index)
            links = source_page.get_links()
            if not links:
                continue
            page = document.load_page(target_page - 1)
            for link in links:
                landing = source_to_page.get(link.get("page"))
                if landing is None or link.get("from") is None:
                    continue
                page.insert_link({"kind": pymupdf.LINK_GOTO,
                                  "from": link["from"],
                                  "page": landing - 1})
                added += 1
    finally:
        document_menus.close()
    return added


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

    # --- crosswalk links ----------------------------------------------------
    # Two surfaces, because the ACS carries two different things.
    #
    # The References line cites whole parts, so link_citations turns that text
    # into part-level jumps. That is not a shortcoming: the line says "14 CFR
    # part 91" and a link under those words should land on Part 91.
    #
    # The section that actually governs an element lives in the crosswalk, not
    # in the page text, so link_elements attaches it to the element code. That
    # is what makes PA.V.B.R3 reach 91.119 rather than the top of a 300-page
    # part.
    lock_for_links = M.load_lock()
    resolver = build_resolver(mapping, lock_for_links, entries)
    targets = element_targets()

    # Pass one locates things; pass two links them. The two directions depend
    # on each other, so neither can be drawn until both ends are known.
    acs_page_of, hub_page_of, hub_pages = {}, {}, []
    hub_prefix = {}
    for entry in entries:
        if entry["section"] != "standards":
            continue
        record = offsets.get(entry["id"])
        if record:
            for index in range(record["pages"]):
                number = record["start"] + index - 1
                if number >= document.page_count:
                    break
                for code, _rect in element_code_rects(
                        document.load_page(number), pymupdf,
                        left_column_only=True):
                    acs_page_of.setdefault(code, number + 1)

        # The crosswalk sits in the pages after this document's menu page.
        menu = offsets.get(entry["id"] + "__menu")
        if menu and menu["pages"] > 1:
            prefix = menus_tool.ACS_PREFIX.get(entry["id"])
            for index in range(1, menu["pages"]):
                number = menu["start"] + index - 1
                if number >= document.page_count:
                    break
                hub_pages.append(number)
                hub_prefix[number] = prefix
                for code, _rect in element_code_rects(
                        document.load_page(number), pymupdf):
                    hub_page_of.setdefault(code, number + 1)

    every_target = specific_targets()
    element_links, hub_back, hub_sections = 0, 0, 0
    buttons, buttoned, overflowed = 0, 0, 0
    citation_links, citation_pages = 0, 0
    for entry in entries:
        if entry["section"] != "standards":
            continue
        record = offsets.get(entry["id"])
        if not record:
            continue
        for index in range(record["pages"]):
            number = record["start"] + index - 1
            if number >= document.page_count:
                break
            page = document.load_page(number)
            added = link_citations(page, resolver, pymupdf)
            element_links += link_element_to_hub(page, hub_page_of, pymupdf)
            drew, touched, lost = draw_target_buttons(
                page, element_blocks(page, pymupdf), every_target, resolver,
                pymupdf)
            buttons += drew
            buttoned += touched
            overflowed += lost
            if added:
                citation_pages += 1
                citation_links += added

    chips = chip_index(every_target)
    area_links = 0
    for number in hub_pages:
        page = document.load_page(number)
        back, sections = link_hub_row(
            page, chips, acs_page_of, resolver, pymupdf)
        area_links += link_area_index(
            page, hub_prefix.get(number), resolver, pymupdf)
        hub_back += back
        hub_sections += sections

    menu_links = relink_generated(
        document, offsets, M.ROOT / "build" / "menus" / "menus.pdf", pymupdf)
    written = write_named_destinations(document, mapping, pymupdf)

    document.save(str(output), garbage=3, deflate=True)
    size = pathlib.Path(output).stat().st_size
    document.close()

    out.write("stamped %d page(s), %d navigation page(s) exempt\n"
              % (stamped, exempt))
    out.write("rebuilt %d named destination(s) destroyed by assembly\n" % written)
    out.write("redrew %d generated menu link(s) dropped by assembly\n"
              % menu_links)
    out.write("%d crosswalk citation link(s) across %d ACS page(s)\n"
              % (citation_links, citation_pages))
    out.write("%d element code(s) linked to their crosswalk row\n"
              % element_links)
    out.write("%d crosswalk page(s): %d return link(s), %d section link(s)\n"
              % (len(hub_pages), hub_back, hub_sections))
    out.write("%d area index link(s) into the ACS itself\n" % area_links)
    out.write("%d inline target button(s) across %d element(s), %d overflowed "
              "to the crosswalk page\n" % (buttons, buttoned, overflowed))
    out.write("%s: %.1f MB\n" % (pathlib.Path(output).name, size / 1048576))
    return EXIT_PROBLEM if dropped else EXIT_OK


def main(argv):
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
