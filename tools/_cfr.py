"""Parse eCFR XML into an intermediate tree, and render it as Typst.

**The DTD mapping in CLAUDE.md section 8 and BUILD-PLAN section 3 is wrong.**
Both say "DIV3 part, DIV5 subpart, DIV8 section". What a part-level request
actually returns is:

    DIV5  TYPE="PART"      N="61"
    DIV6  TYPE="SUBPART"   N="A"
    DIV8  TYPE="SECTION"   N="61.1"
    DIV9  TYPE="APPENDIX"

DIV3 does not appear at all, and appendices are not mentioned in either plan.
A parser written to the documented mapping finds nothing.

Section labels become Typst labels, which become PDF named destinations, so
`14cfr:91.155` resolves without any text matching. That was verified against
Typst 0.15 before this was written, not assumed.

No network here, so the parser is testable against fixtures.
"""

import json
import re
import xml.etree.ElementTree as ET

SECTION = "SECTION"
SUBPART = "SUBPART"
PART = "PART"
APPENDIX = "APPENDIX"

# The section sign and an em dash, which eCFR uses in headings.
SECTION_SIGN = "§"
EM_DASH = "—"

HEAD_SECTION = re.compile(r"^\s*%s+\s*([\d.\-\w]+)\s*(.*)$" % SECTION_SIGN, re.S)

# Typst markup characters. Escaped so regulatory text cannot be reinterpreted
# as formatting; 14 CFR is full of #, $, *, and bracketed citations.
TYPST_ESCAPE = str.maketrans({c: "\\" + c for c in "\\#[]*_`$@<>~"})


def escape(text):
    if not text:
        return ""
    # Rule 10 applies to generated text too: no em dashes.
    text = text.replace(EM_DASH, " - ")
    return text.translate(TYPST_ESCAPE)


def label_for(section_number):
    """`61.51` -> `sec-61-51`, matching the scheme in CLAUDE.md section 8."""
    return "sec-" + re.sub(r"[^0-9a-zA-Z]+", "-", section_number).strip("-")


def ref_for(title, section_number):
    """The logical anchor ref, `14cfr:91.155`."""
    return "%dcfr:%s" % (int(title), section_number)


# ---------------------------------------------------------------------------
# inline markup
# ---------------------------------------------------------------------------

def inline(element):
    """Render mixed content to Typst, preserving italics.

    eCFR uses <I> heavily for defined terms and case citations; Part 61 alone
    has over three hundred. That is why a real italic face is vendored rather
    than synthesized.
    """
    out = [escape(element.text)]
    for child in element:
        inner = inline(child)
        tag = child.tag.upper()
        if tag in ("I", "E"):
            # Function form, not `_..._`. Typst only treats an underscore as
            # emphasis at a word boundary, and regulatory text is full of
            # places where there is none: "V<I>H</I>" renders as V_H_, which
            # Typst reads as an unclosed delimiter, and an italicised URL ends
            # ",_" which never closes. #emph[] has no such ambiguity, and the
            # brackets are safe because escape() neutralises any in the text.
            out.append("#emph[%s]" % inner if inner.strip() else inner)
        elif tag in ("SU", "SUP"):
            # eCFR writes these lowercase in practice, hence the .upper() above.
            out.append("#super[%s]" % inner)
        elif tag in ("INF", "SUB"):
            out.append("#sub[%s]" % inner)
        elif tag == "BR":
            # The trailing space matters. Typst continues an expression when a
            # call is immediately followed by "(", so "#linebreak()(statute
            # miles)" parses as calling the result. A space ends the
            # expression, and Typst trims it at the start of the new line.
            out.append("#linebreak() ")
        else:
            out.append(inner)
        out.append(escape(child.tail))
    return "".join(out)


def text_of(element):
    """Plain text, for headings and indexes."""
    return " ".join("".join(element.itertext()).split())


# ---------------------------------------------------------------------------
# parse
# ---------------------------------------------------------------------------

def split_head(head):
    """`§ 61.1 Applicability and definitions.` -> ('61.1', 'Applicability...')."""
    match = HEAD_SECTION.match(head or "")
    if not match:
        return None, " ".join((head or "").split())
    number, title = match.groups()
    return number.rstrip("."), " ".join(title.split())


def parse_part(xml_bytes, title):
    """Return one part as a plain dict tree. Raises on malformed XML."""
    root = ET.fromstring(xml_bytes)
    if root.get("TYPE") != PART:
        found = "%s TYPE=%s" % (root.tag, root.get("TYPE"))
        raise ValueError("expected a PART root, got %s" % found)

    part = {
        "title": int(title),
        "part": root.get("N"),
        "heading": "",
        "children": [],
    }

    head = root.find("HEAD")
    if head is not None:
        part["heading"] = text_of(head).replace(EM_DASH, " - ")

    # Statutory authority and Federal Register source sit at part level, before
    # the first subpart. Small, but they are the citation for the whole part.
    part["front"] = []
    for child in root:
        if child.tag in ("AUTH", "SOURCE", "EDNOTE") and child.get("TYPE") is None:
            text = text_of(child).replace(EM_DASH, " - ")
            if text:
                part["front"].append(text)

    def walk(container, bucket):
        for child in container:
            kind = child.get("TYPE")
            if kind == SUBPART:
                node = {"kind": "subpart", "n": child.get("N"),
                        "heading": "", "children": []}
                sub_head = child.find("HEAD")
                if sub_head is not None:
                    node["heading"] = text_of(sub_head).replace(EM_DASH, " - ")
                walk(child, node["children"])
                bucket.append(node)
            elif kind == SECTION:
                bucket.append(section_node(child, title))
            elif kind == APPENDIX:
                node = {"kind": "appendix", "n": child.get("N"),
                        "heading": "", "body": []}
                app_head = child.find("HEAD")
                if app_head is not None:
                    node["heading"] = text_of(app_head).replace(EM_DASH, " - ")
                node["body"] = [inline(p) for p in child.iter("P")]
                bucket.append(node)
            elif child.tag.startswith("DIV"):
                # An unexpected level: keep walking rather than drop content.
                walk(child, bucket)

    walk(root, part["children"])
    return part


def cells_of(row):
    """Return (cells, is_header) for one TR."""
    cells, header = [], False
    for cell in row:
        if cell.tag in ("TD", "TH"):
            cells.append(inline(cell))
            if cell.tag == "TH":
                header = True
    return cells, header


def table_node(element):
    """Flatten a GPO table into a header row plus body rows.

    These are not decoration. 91.155, the VFR weather minimums, is a table, and
    it is one of the most linked-to sections in the whole corpus.
    """
    header, rows = [], []
    for row in element.iter("TR"):
        cells, is_header = cells_of(row)
        if not cells:
            continue
        if is_header and not header and not rows:
            header = cells
        else:
            rows.append(cells)
    columns = max([len(header)] + [len(r) for r in rows] or [0]) if (header or rows) else 0
    if not columns:
        return None
    pad = lambda r: r + [""] * (columns - len(r))
    return {"kind": "table", "cols": columns,
            "header": pad(header) if header else [],
            "rows": [pad(r) for r in rows]}


BLOCK_TAGS = ("P", "FP", "FP-1", "FP-2", "PSPACE")
HEAD_TAGS = ("HED", "HD1", "HD2", "HD3")


def collect_body(element, body):
    """Walk a section's children, including untyped DIV wrappers.

    91.155 keeps its table inside a bare <DIV>. Skipping unrecognised DIVs drops
    that table silently, which is exactly the kind of loss that looks fine in a
    page count and is wrong in the document.
    """
    for child in element:
        tag = child.tag.upper()
        if tag == "HEAD":
            continue
        if tag == "TABLE":
            table = table_node(child)
            if table:
                body.append(table)
        elif tag in BLOCK_TAGS:
            text = inline(child)
            if text.strip():
                body.append({"kind": "fp" if tag.startswith("FP") else "p",
                             "text": text})
        elif tag in HEAD_TAGS:
            text = inline(child)
            if text.strip():
                body.append({"kind": "subhead", "text": text})
        elif tag in ("CITA", "SOURCE", "AUTH"):
            body.append({"kind": "cita", "text": text_of(child)})
        elif tag in ("EXTRACT", "NOTE", "EDNOTE"):
            for paragraph in child.iter("P"):
                body.append({"kind": "note", "text": inline(paragraph)})
        elif tag.startswith("DIV"):
            collect_body(child, body)


def section_node(element, title):
    head = element.find("HEAD")
    raw = text_of(head) if head is not None else ""
    number, heading = split_head(raw)
    number = number or element.get("N") or ""
    body = []
    collect_body(element, body)
    return {
        "kind": "section",
        "n": number,
        "heading": heading,
        "label": label_for(number),
        "ref": ref_for(title, number),
        "body": body,
    }


def sections_of(part):
    """Every section in document order, flattened across subparts."""
    found = []

    def walk(nodes):
        for node in nodes:
            if node["kind"] == "section":
                found.append(node)
            elif node["kind"] == "subpart":
                walk(node["children"])

    walk(part["children"])
    return found


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------

def render_part(part):
    """Emit Typst for one part. Helpers come from templates/cfr.typ."""
    lines = ['#cfr-part("%s", "%s") <%s>' % (
        escape_string(part["part"]), escape_string(part["heading"]),
        "part-%s-%s" % (part["title"], label_for(part["part"])[4:]))]

    for text in part.get("front", []):
        lines.append("#cfr-cita[%s]" % escape(text))

    def emit(nodes):
        for node in nodes:
            if node["kind"] == "subpart":
                lines.append('#cfr-subpart("%s", "%s") <%s>' % (
                    escape_string(node["n"]), escape_string(node["heading"]),
                    "subpart-%s-%s-%s" % (part["title"], part["part"],
                                          node["n"])))
                emit(node["children"])
            elif node["kind"] == "section":
                lines.append('#cfr-section("%s", "%s") <%s>' % (
                    escape_string(node["n"]), escape_string(node["heading"]),
                    node["label"]))
                for block in node["body"]:
                    lines.append(render_block(block))
            elif node["kind"] == "appendix":
                lines.append('#cfr-appendix("%s", "%s") <%s>' % (
                    escape_string(node["n"]), escape_string(node["heading"]),
                    "appendix-%s-%s-%s" % (part["title"], part["part"],
                                           label_for(node["n"])[4:])))
                for text in node["body"]:
                    lines.append("#cfr-p[%s]" % text)

    emit(part["children"])
    return "\n".join(lines) + "\n"


def render_block(block):
    kind = block["kind"]
    if kind == "table":
        return render_table(block)
    if kind == "cita":
        return "#cfr-cita[%s]" % escape(block["text"])
    if kind == "fp":
        return "#cfr-fp[%s]" % block["text"]
    if kind == "subhead":
        return "#cfr-subhead[%s]" % block["text"]
    if kind == "note":
        return "#cfr-note[%s]" % block["text"]
    return "#cfr-p[%s]" % block["text"]


def render_table(block):
    def row(cells):
        return ", ".join("[%s]" % c for c in cells)

    header = "(%s,)" % row(block["header"]) if block["header"] else "()"
    flat = [c for r in block["rows"] for c in r]
    cells = "(%s,)" % row(flat) if flat else "()"
    return "#cfr-table(%d, %s, %s)" % (block["cols"], header, cells)


def escape_string(text):
    """Escape for a Typst double-quoted string argument."""
    return (text or "").replace("\\", "\\\\").replace('"', '\\"')


def dump_json(part):
    return json.dumps(part, indent=2, sort_keys=True, ensure_ascii=False)
