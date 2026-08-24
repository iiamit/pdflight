"""Build the regulations from eCFR XML into a typeset PDF.

The FAA does not publish a usable single PDF of 14 CFR, so this generates one.
Because it is generated, every section carries a native PDF named destination
and `14cfr:91.155` resolves deterministically, with none of the text matching
that source PDFs need. That is resolution strategy 1 in CLAUDE.md section 8,
and it is the reason the regulations are the cheapest part of the anchor layer
to maintain.

    make cfr-check    compare eCFR amendment dates against the lock, no build
    make cfr          fetch, parse, typeset, compile

Requests are made per part. A whole-title request returns everything and times
out, which the plan warns about and which is still true.

Exit codes per CLAUDE.md section 9: 0 success, 1 a check failed, 2 usage.
"""

import argparse
import hashlib
import io
import json
import pathlib
import subprocess
import sys

import yaml

import _cfr
import _manifest as M
from _http import Client, FetchError

# Retry budget for eCFR, which is flakier than faa.gov on large parts.
CFR_ATTEMPTS = 8
CFR_BASE_DELAY = 4.0

EXIT_OK = 0
EXIT_DRIFT = 1

API = "https://www.ecfr.gov/api/versioner/v1"
CFR_MANIFEST = M.ROOT / "manifest" / "cfr.yaml"
CFR_LOCK = M.ROOT / "manifest" / "cfr.lock.yaml"
CACHE = M.ROOT / "cache" / "cfr"
BUILD = M.ROOT / "build" / "cfr"
TEMPLATE = M.ROOT / "templates" / "cfr.typ"
FONTS = M.ROOT / "theme" / "fonts"


def load_cfr_manifest(path=CFR_MANIFEST):
    with io.open(path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    wanted = []
    for key, spec in sorted(data.items()):
        if not key.startswith("title_"):
            continue
        title = int(key.split("_", 1)[1])
        for part in (spec or {}).get("parts", []):
            wanted.append((title, str(part)))
    return wanted


def latest_amended(client):
    """Per-title amendment dates. This is the change signal for regulations."""
    reply = client.get("%s/titles.json" % API)
    if not reply.ok:
        raise FetchError("titles.json returned %d" % reply.status)
    out = {}
    for entry in json.loads(reply.body).get("titles", []):
        if entry.get("number") is not None:
            out[int(entry["number"])] = {
                "latest_amended_on": entry.get("latest_amended_on"),
                "up_to_date_as_of": entry.get("up_to_date_as_of"),
            }
    return out


def part_xml(client, title, part, date, cache_root=CACHE):
    """Fetch one part, cached by (title, part, date) so a rebuild is offline."""
    cache_root = pathlib.Path(cache_root)
    cache_root.mkdir(parents=True, exist_ok=True)
    cached = cache_root / ("title-%s-part-%s-%s.xml" % (title, part, date))
    if cached.is_file():
        return cached.read_bytes(), True

    url = "%s/full/%s/title-%s.xml?part=%s" % (API, date, title, part)
    reply = client.get(url)
    if not reply.ok:
        raise FetchError(
            "title %s part %s returned %d after %d attempts. A 503 here is "
            "usually eCFR timing out while generating the part; re-running "
            "the build normally clears it."
            % (title, part, reply.status, CFR_ATTEMPTS))
    cached.write_bytes(reply.body)
    return reply.body, False


def load_lock(path=CFR_LOCK):
    if not pathlib.Path(path).is_file():
        return {}
    with io.open(path, encoding="utf-8") as handle:
        return (yaml.safe_load(handle) or {}).get("parts", {}) or {}


LOCK_HEADER = """\
# Written by tools/cfr_build.py. Do not hand-edit.
#
# One entry per CFR part, keyed title-part. `amended_on` is the eCFR amendment
# date the XML was pulled for, and `sha256` is of that XML. A diff here means
# the regulations changed, which is a release signal exactly like a diff in
# sources.lock.yaml.
#
# `sections` is the count of named destinations that part contributes. If it
# drops without an amendment, the parser broke.
"""


def dump_lock(parts, path=CFR_LOCK):
    ordered = {key: parts[key] for key in sorted(parts)}
    body = yaml.safe_dump({"parts": ordered} if ordered else {},
                          default_flow_style=False, sort_keys=True, width=100)
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(LOCK_HEADER)
        handle.write("\n")
        handle.write(body if ordered else "{}\n")


def build_typst(parsed_parts, currency, template=TEMPLATE):
    """Preamble plus generated body, concatenated into one deterministic file."""
    preamble = pathlib.Path(template).read_text(encoding="utf-8")
    body = ["", "#show: cfr-doc.with(title: \"PDFLIGHT | 14 CFR\", currency: \"%s\")"
            % _cfr.escape_string(currency), ""]
    for part in parsed_parts:
        body.append(_cfr.render_part(part))
    return preamble + "\n".join(body)


def compile_typst(source_path, pdf_path, fonts=FONTS):
    """Compile with Typst. SOURCE_DATE_EPOCH pins anything time-derived."""
    import os

    env = dict(os.environ)
    env["SOURCE_DATE_EPOCH"] = "0"
    result = subprocess.run(
        ["typst", "compile", "--font-path", str(fonts),
         str(source_path), str(pdf_path)],
        capture_output=True, env=env,
    )
    return result.returncode, result.stdout.decode("utf-8", "replace"), \
        result.stderr.decode("utf-8", "replace")


def run(argv, client_factory=None, manifest_path=CFR_MANIFEST,
        lock_path=CFR_LOCK, cache_root=CACHE, build_root=BUILD,
        template=TEMPLATE, out=sys.stdout):
    parser = argparse.ArgumentParser(
        prog="cfr_build.py",
        description="Build 14 CFR and 49 CFR from eCFR XML.")
    parser.add_argument("--check", action="store_true",
                        help="compare amendment dates against the lock, no build")
    parser.add_argument("--part", action="append",
                        help="limit to specific parts, for example 91")
    parser.add_argument("--no-compile", action="store_true",
                        help="emit Typst but do not run the compiler")
    args = parser.parse_args(argv)

    wanted = load_cfr_manifest(manifest_path)
    if args.part:
        keep = {str(p) for p in args.part}
        wanted = [(t, p) for t, p in wanted if p in keep]
    if not wanted:
        out.write("manifest/cfr.yaml selects no parts.\n")
        return EXIT_OK

    # eCFR generates a part's XML on demand and answers 503 when that times
    # out server side, which happens on the large parts. The default budget of
    # five attempts at a 1 second base is about 31 seconds, and a CI build died
    # on a single 503 for Part 71 after fetching the whole corpus. This waits
    # roughly four minutes instead. A part that stays down is still fatal:
    # shipping 14 CFR with a part quietly missing would be worse than failing.
    client = client_factory() if client_factory else Client(
        attempts=CFR_ATTEMPTS, base_delay=CFR_BASE_DELAY)
    lock = load_lock(lock_path)
    dates = latest_amended(client)

    if args.check:
        drift = []
        for title, part in wanted:
            key = "title-%s-part-%s" % (title, part)
            amended = (dates.get(title) or {}).get("latest_amended_on")
            recorded = (lock.get(key) or {}).get("amended_on")
            if recorded != amended:
                drift.append("%s: eCFR %s, lock %s" % (key, amended, recorded))
        for line in drift:
            out.write("  %s\n" % line)
        if drift:
            out.write("\n%d part(s) drifted. Run make cfr.\n" % len(drift))
            return EXIT_DRIFT
        out.write("No drift. %d part(s) current.\n" % len(wanted))
        return EXIT_OK

    build_root = pathlib.Path(build_root)
    build_root.mkdir(parents=True, exist_ok=True)

    parsed, entries, total_sections = [], {}, 0
    for title, part in wanted:
        amended = (dates.get(title) or {}).get("latest_amended_on")
        if not amended:
            out.write("title %s: no amendment date from eCFR, skipped\n" % title)
            continue
        raw, cached = part_xml(client, title, part, amended, cache_root)
        try:
            tree = _cfr.parse_part(raw, title)
        except Exception as exc:
            out.write("title %s part %s: parse failed: %s\n" % (title, part, exc))
            return EXIT_DRIFT

        sections = _cfr.sections_of(tree)
        total_sections += len(sections)
        parsed.append(tree)
        entries["title-%s-part-%s" % (title, part)] = {
            "amended_on": amended,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "sections": len(sections),
        }
        out.write("title %-2s part %-4s %5d sections  %7d bytes%s\n" % (
            title, part, len(sections), len(raw), "  (cached)" if cached else ""))

    # Intermediate JSON, per the plan. Useful on its own for the crosswalk.
    for tree in parsed:
        target = build_root / ("title-%s-part-%s.json" % (tree["title"], tree["part"]))
        with io.open(target, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(_cfr.dump_json(tree))
            handle.write("\n")

    currency = " | ".join(
        "TITLE %s CURRENT %s" % (t, (dates.get(t) or {}).get("latest_amended_on"))
        for t in sorted({t for t, _ in wanted}))
    source = build_root / "cfr.typ"
    with io.open(source, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(build_typst(parsed, currency, template))

    dump_lock(entries, lock_path)
    out.write("\n%d part(s), %d sections. Wrote %s\n"
              % (len(parsed), total_sections, source.name))

    if args.no_compile:
        return EXIT_OK

    pdf = build_root / "cfr.pdf"
    code, stdout, stderr = compile_typst(source, pdf)
    if code != 0:
        out.write("typst failed:\n%s\n%s\n" % (stdout[-3000:], stderr[-3000:]))
        return EXIT_DRIFT

    try:
        import pymupdf

        document = pymupdf.open(pdf)
        names = document.resolve_names()
        pages = document.page_count
        document.close()
    except Exception as exc:
        out.write("could not inspect the built PDF: %s\n" % exc)
        return EXIT_DRIFT

    out.write("%s: %d pages, %.1f MB, %d named destinations\n" % (
        pdf.name, pages, pdf.stat().st_size / 1048576, len(names)))

    # Count is not the test. Every section label must actually resolve, because
    # a missing one silently breaks 14cfr:x.y for that section alone.
    missing = []
    for tree in parsed:
        for section in _cfr.sections_of(tree):
            if section["label"] not in names:
                missing.append("%s (%s)" % (section["ref"], section["label"]))

    if missing:
        out.write("\n%d section(s) produced no destination:\n" % len(missing))
        for line in missing[:20]:
            out.write("  %s\n" % line)
        if len(missing) > 20:
            out.write("  ... and %d more\n" % (len(missing) - 20))
        return EXIT_DRIFT

    out.write("all %d section refs resolve\n" % total_sections)
    return EXIT_OK


def main(argv):
    try:
        return run(argv)
    except FetchError as exc:
        sys.stderr.write("eCFR: %s\n" % exc)
        return EXIT_DRIFT


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
