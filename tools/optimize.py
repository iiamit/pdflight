"""Recompress oversized source PDFs into cache/optimized/.

The corpus measured 766 MB in 1.2, against a 500 MB hard fail, and three
documents carry most of it. This stage brings that back inside budget by
downsampling images that are stored at far higher resolution than any reader
will display.

Two properties matter more than the compression ratio.

Rule 8, determinism. PyMuPDF writes a random second `/ID` into the trailer on
every save, which is correct per the PDF spec and fatal for a byte-identical
rebuild. Everything else it emits is already stable: two runs of the same input
differ in exactly those 30 bytes. Both `/ID` halves are therefore pinned to a
value derived from the source hash and the profile, which is what rule 8 means
by "fix the PDF /ID". The result is reproducible across machines and runs.

Rule 12, no new external binaries. This uses PyMuPDF's own `rewrite_images`
rather than Ghostscript, so nothing new has to be installed identically on
Windows and ubuntu-latest. The PyMuPDF version is recorded in the lock, because
a different MuPDF could legitimately produce different bytes.

Sources are never modified. `cache/sources/{sha256}.pdf` stays exactly as the
FAA served it, because its hash is the drift signal that decides releases.
Optimized output is a derived artifact keyed on the source hash.
"""

import argparse
import hashlib
import io
import pathlib
import re
import sys

import yaml

import _manifest as M

EXIT_OK = 0
EXIT_DRIFT = 1

OPTIMIZED = M.ROOT / "cache" / "optimized"
OPTIMIZE_LOCK = M.ROOT / "manifest" / "optimize.lock.yaml"

# Documents denser than this are recompressed. The corpus median is 0.034
# MB/page, so this is roughly seven times the median and selects only genuine
# outliers. A threshold beats naming ids: it keeps working as the corpus grows.
DENSITY_THRESHOLD = 0.25

# Recompression that does not actually shrink a document is not worth the
# quality loss, so the result is discarded and the original used instead.
# Measured: below the density threshold, returns collapse. IFH recompresses to
# 95 percent of its original size and takes 100 seconds to do it, because its
# bulk is text and vector art rather than oversized images.
MIN_SAVING = 0.30

# Images above dpi_threshold are resampled to dpi_target and re-encoded at
# quality. 150 dpi is beyond what a tablet resolves at reading size.
PROFILE = {
    "name": "tablet-150",
    "dpi_threshold": 200,
    "dpi_target": 150,
    "quality": 80,
}

# A PDF string is written either as hex, <AB12...>, or as a literal, (...),
# and both forms are legal for either half of /ID. Matching only hex is the
# defect this pattern exists to avoid.
PDF_STRING = rb"(?:<[0-9A-Fa-f]*>|\((?:\\.|[^()\\])*\))"
TRAILER_ID = re.compile(rb"/ID\s*\[\s*" + PDF_STRING + rb"\s*" + PDF_STRING +
                        rb"\s*\]")


def digest_for(seed):
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32].upper()


def pin_id(data, seed):
    """Force both trailer /ID halves to a content-derived constant.

    Necessary even though set_id runs first. Per the PDF spec the second /ID
    element is the *changing* identifier, and MuPDF regenerates it on every
    write no matter what the document carried. When those random bytes happen
    to be mostly printable it writes them as a literal string rather than hex,
    which is about one save in twenty. An earlier hex-only pattern matched
    nothing on exactly those runs, so the random ID survived and the output
    differed from an otherwise byte-identical rebuild. That is a rule 8
    failure that only shows up intermittently, which is the worst kind.

    Rewriting is scoped to the trailer, after the last `trailer` keyword. The
    trailer is reached by parsing forward from the xref table rather than by
    an absolute offset, so changing its length moves nothing that any
    cross-reference entry points at. Outside a trailer the substitution is
    length preserving, which is safe anywhere.
    """
    pinned = digest_for(seed).encode()
    replacement = b"/ID[<" + pinned + b"><" + pinned + b">]"

    cut = data.rfind(b"trailer")
    if cut == -1:
        # No classic trailer, so /ID may live in an xref stream object whose
        # length must not change. Only touch an equal-length hex pair.
        exact = re.compile(rb"(/ID\s*\[\s*<)([0-9A-Fa-f]{32})(>\s*<)"
                           rb"([0-9A-Fa-f]{32})(>)")
        return exact.sub(
            lambda m: m.group(1) + pinned + m.group(3) + pinned + m.group(5),
            data)

    return data[:cut] + TRAILER_ID.sub(replacement, data[cut:])


def set_id(document, seed):
    """Pin the trailer /ID on the document itself, before it is written.

    xref -1 is the trailer. Setting the key here means MuPDF emits our value
    rather than generating one, so the output does not depend on which string
    form it would have chosen.
    """
    pinned = digest_for(seed)
    try:
        document.xref_set_key(-1, "ID", "[<%s><%s>]" % (pinned, pinned))
        return True
    except Exception:
        return False


def profile_seed(source_sha):
    return "%s|%s|%s|%s|%s" % (
        source_sha, PROFILE["name"], PROFILE["dpi_threshold"],
        PROFILE["dpi_target"], PROFILE["quality"])


def recompress(data, source_sha):
    import pymupdf

    document = pymupdf.open(stream=data, filetype="pdf")
    try:
        document.rewrite_images(
            dpi_threshold=PROFILE["dpi_threshold"],
            dpi_target=PROFILE["dpi_target"],
            quality=PROFILE["quality"],
        )
        # Strip dates and producer strings; they are not content.
        document.set_metadata({})
        set_id(document, profile_seed(source_sha))
        out = document.tobytes(garbage=4, deflate=True, clean=True)
    finally:
        document.close()
    # Belt and braces: if the writer regenerated an ID anyway, and it came out
    # in hex form, normalise it here too.
    return pin_id(out, profile_seed(source_sha))


def density(entry):
    pages = entry.get("pages") or 0
    if not pages:
        return 0.0
    return entry.get("bytes", 0) / pages / 1048576


def candidates(lock):
    return sorted(key for key, entry in lock.items()
                  if density(entry) > DENSITY_THRESHOLD)


def load_optimize_lock(path=OPTIMIZE_LOCK):
    if not pathlib.Path(path).is_file():
        return {}
    with io.open(path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return (data or {}).get("optimized", {}) or {}


HEADER = """\
# Written by tools/optimize.py. Do not hand-edit.
#
# Derived artifacts, not sources. cache/sources/ is never modified; its hashes
# are the drift signal that decides releases.
#
# output_sha256 is committed so a rebuild on another machine can be proven
# byte-identical. If it moves without a profile or source change, determinism
# has regressed. The PyMuPDF version is recorded because a different MuPDF may
# legitimately encode differently; see rule 12.
"""


def dump_optimize_lock(entries, pymupdf_version, path=OPTIMIZE_LOCK):
    ordered = {key: entries[key] for key in sorted(entries)}
    body = yaml.safe_dump(
        {"profile": dict(PROFILE),
         "density_threshold_mb_per_page": DENSITY_THRESHOLD,
         "pymupdf": pymupdf_version,
         "optimized": ordered},
        default_flow_style=False, sort_keys=True, width=100)
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(HEADER)
        handle.write("\n")
        handle.write(body)


def run(argv, lock_path=M.LOCK, cache_root=M.CACHE, out_root=OPTIMIZED,
        optimize_lock=OPTIMIZE_LOCK, out=sys.stdout):
    parser = argparse.ArgumentParser(
        prog="optimize.py",
        description="Recompress oversized sources into cache/optimized/.")
    parser.add_argument("--check", action="store_true",
                        help="verify existing output against the lock, no work")
    args = parser.parse_args(argv)

    import pymupdf
    version = pymupdf.version[0]

    lock = M.load_lock(lock_path)
    if not lock:
        out.write("sources.lock.yaml is empty. Run make fetch-update first.\n")
        return EXIT_OK

    chosen = candidates(lock)
    total_before = sum(entry.get("bytes", 0) for entry in lock.values())

    if args.check:
        recorded = load_optimize_lock(optimize_lock)
        problems = []
        for key in chosen:
            record = recorded.get(key)
            if not record:
                problems.append("%s: not in optimize.lock.yaml" % key)
                continue
            path = pathlib.Path(out_root) / ("%s.pdf" % record["source_sha256"])
            if not path.is_file():
                problems.append("%s: optimized blob missing from cache" % key)
                continue
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != record["output_sha256"]:
                problems.append("%s: output %s, lock says %s"
                                % (key, actual[:12], record["output_sha256"][:12]))
        for line in problems:
            out.write("  %s\n" % line)
        if problems:
            out.write("\n%d problem(s). Run make optimize.\n" % len(problems))
            return EXIT_DRIFT
        out.write("%d optimized artifact(s) match the lock.\n" % len(chosen))
        return EXIT_OK

    out.write("threshold %.2f MB/page selects %d of %d target(s)\n\n"
              % (DENSITY_THRESHOLD, len(chosen), len(lock)))

    pathlib.Path(out_root).mkdir(parents=True, exist_ok=True)
    entries, saved = {}, 0
    for key in chosen:
        entry = lock[key]
        source = M.cache_path(entry["sha256"], cache_root)
        if not source.is_file():
            out.write("%s: source blob missing from cache, skipped\n" % key)
            continue
        data = source.read_bytes()
        result = recompress(data, entry["sha256"])

        if len(result) > len(data) * (1.0 - MIN_SAVING):
            out.write("%-22s %8.1f MB -> %7.1f MB  (%2.0f%%)  discarded, under "
                      "the %.0f%% floor\n" % (
                          key, len(data) / 1048576, len(result) / 1048576,
                          100 * len(result) / max(1, len(data)), MIN_SAVING * 100))
            continue

        target = pathlib.Path(out_root) / ("%s.pdf" % entry["sha256"])
        target.write_bytes(result)

        saved += len(data) - len(result)
        entries[key] = {
            "source_sha256": entry["sha256"],
            "output_sha256": hashlib.sha256(result).hexdigest(),
            "source_bytes": len(data),
            "output_bytes": len(result),
            "pages": entry.get("pages"),
        }
        out.write("%-22s %8.1f MB -> %7.1f MB  (%2.0f%%)  %d pages\n" % (
            key, len(data) / 1048576, len(result) / 1048576,
            100 * len(result) / max(1, len(data)), entry.get("pages") or 0))

    dump_optimize_lock(entries, version, optimize_lock)

    after = total_before - saved
    out.write("\ncorpus %.1f MB -> %.1f MB, saved %.1f MB\n"
              % (total_before / 1048576, after / 1048576, saved / 1048576))
    out.write("hard fail 500 MB: %s\n"
              % ("PASS" if after < 500 * 1048576 else "STILL OVER"))
    out.write("warn 350 MB: %s\n"
              % ("pass" if after < 350 * 1048576 else "over"))
    return EXIT_OK


def main(argv):
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
