"""Vendor the static font faces into theme/fonts/ and maintain fonts.lock.json.

Fonts are build inputs, so rule 8 governs them. A build-time fetch or a system
install means the binary differs between machines, subsetting yields different
bytes, and the PDF hash changes with no content change. Vendoring is a one-time
act performed by this tool, never something the build does.

    python tools/vendor_fonts.py --check    verify on-disk files against the
                                            lock. No network. This is what the
                                            test suite asserts.
    python tools/vendor_fonts.py            re-vendor from the pinned upstream
                                            releases and rewrite the lock.

The upstream release is pinned by tag and asset below. When a lock already
exists, the downloaded archive's own sha256 must match what the lock recorded,
so a re-run cannot silently pull different bytes from the same tag. Moving to a
new upstream version is a deliberate act: bump TAG here and pass
--allow-upstream-change.

Static instances only, never variable. Inter's variable font subsets
unpredictably through Typst into PDF.
"""

import argparse
import hashlib
import io
import json
import pathlib
import sys
import urllib.error
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEST = ROOT / "theme" / "fonts"
LOCK = DEST / "fonts.lock.json"
ZIP_CACHE = ROOT / "cache" / "fonts"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 pdflight/0.1"
)

EXIT_OK = 0
EXIT_MISMATCH = 1
EXIT_USAGE = 2

PLAN = [
    {
        "family": "Inter",
        "repo": "rsms/inter",
        "tag": "v4.1",
        "asset": "Inter-4.1.zip",
        "license_member": "LICENSE.txt",
        "license_file": "OFL-Inter.txt",
        "faces": [
            ("extras/ttf/Inter-Regular.ttf", "Inter-Regular.ttf", 400, "normal"),
            ("extras/ttf/Inter-Medium.ttf", "Inter-Medium.ttf", 500, "normal"),
            ("extras/ttf/Inter-SemiBold.ttf", "Inter-SemiBold.ttf", 600, "normal"),
            ("extras/ttf/Inter-Bold.ttf", "Inter-Bold.ttf", 700, "normal"),
            # Mandatory. eCFR XML uses <I> for citations and defined terms, so
            # Phase 2 needs a real italic rather than a synthesized oblique.
            ("extras/ttf/Inter-Italic.ttf", "Inter-Italic.ttf", 400, "italic"),
        ],
    },
    {
        "family": "JetBrains Mono",
        "repo": "JetBrains/JetBrainsMono",
        "tag": "v2.304",
        "asset": "JetBrainsMono-2.304.zip",
        "license_member": "OFL.txt",
        "license_file": "OFL-JetBrainsMono.txt",
        "faces": [
            ("fonts/ttf/JetBrainsMono-Regular.ttf",
             "JetBrainsMono-Regular.ttf", 400, "normal"),
            ("fonts/ttf/JetBrainsMono-Medium.ttf",
             "JetBrainsMono-Medium.ttf", 500, "normal"),
        ],
    },
]


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def asset_url(spec):
    return "https://github.com/%s/releases/download/%s/%s" % (
        spec["repo"], spec["tag"], spec["asset"],
    )


def read_lock():
    if not LOCK.is_file():
        return None
    with open(LOCK, encoding="utf-8") as handle:
        return json.load(handle)


def write_lock(lock):
    DEST.mkdir(parents=True, exist_ok=True)
    with io.open(LOCK, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(lock, handle, indent=2, sort_keys=True)
        handle.write("\n")


def check():
    """Verify every vendored file against the lock. No network."""
    lock = read_lock()
    if lock is None:
        print("fonts.lock.json is missing. Run: python tools/vendor_fonts.py")
        return EXIT_MISMATCH

    problems = []
    for family, entry in sorted(lock["families"].items()):
        records = [(entry["license"]["file"], entry["license"]["sha256"], None)]
        records += [(f["file"], f["sha256"], f["bytes"]) for f in entry["faces"]]
        for name, want, size in records:
            path = DEST / name
            if not path.is_file():
                problems.append("%s: missing" % name)
                continue
            data = path.read_bytes()
            if sha256(data) != want:
                problems.append(
                    "%s: sha256 %s, lock says %s" % (name, sha256(data)[:16], want[:16])
                )
            elif size is not None and len(data) != size:
                problems.append("%s: %d bytes, lock says %d" % (name, len(data), size))
        print("%-16s %d faces, license %s" % (
            family, len(entry["faces"]), entry["license"]["file"]))

    if problems:
        for line in problems:
            print("  FAIL " + line)
        print("\n%d problem(s). Line endings are the usual cause; see "
              ".gitattributes." % len(problems))
        return EXIT_MISMATCH

    total = sum(len(e["faces"]) for e in lock["families"].values())
    print("ok, %d faces verified against the lock." % total)
    return EXIT_OK


def download(spec, allow_change, previous):
    """Return the release archive bytes, from cache when possible."""
    ZIP_CACHE.mkdir(parents=True, exist_ok=True)
    cached = ZIP_CACHE / ("%s-%s" % (spec["tag"], spec["asset"]))

    if cached.is_file():
        blob = cached.read_bytes()
    else:
        url = asset_url(spec)
        print("  downloading %s" % url)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        blob = urllib.request.urlopen(request, timeout=120).read()
        cached.write_bytes(blob)

    if previous is not None:
        recorded = previous["source"].get("asset_sha256")
        if recorded and sha256(blob) != recorded and not allow_change:
            raise SystemExit(
                "%s: archive for %s does not match the lock.\n"
                "  lock:     %s\n  download: %s\n"
                "Upstream changed an asset in place, or the tag moved. Pass "
                "--allow-upstream-change to accept it deliberately."
                % (spec["family"], spec["tag"], recorded[:16], sha256(blob)[:16])
            )
    return blob


def vendor(allow_change):
    previous = read_lock() or {"families": {}}
    DEST.mkdir(parents=True, exist_ok=True)

    lock = {
        "comment": ("Vendored build inputs. Rule 8: fonts are never fetched at "
                    "build time. Regenerate with tools/vendor_fonts.py."),
        "families": {},
    }

    for spec in PLAN:
        print("%s %s" % (spec["family"], spec["tag"]))
        blob = download(spec, allow_change, previous["families"].get(spec["family"]))
        archive = zipfile.ZipFile(io.BytesIO(blob))
        members = set(archive.namelist())

        if spec["license_member"] not in members:
            raise SystemExit("%s: license member %s is not in %s"
                             % (spec["family"], spec["license_member"], spec["asset"]))
        license_bytes = archive.read(spec["license_member"])
        (DEST / spec["license_file"]).write_bytes(license_bytes)

        faces = []
        for member, name, weight, style in spec["faces"]:
            if member not in members:
                raise SystemExit("%s: member %s is not in %s"
                                 % (spec["family"], member, spec["asset"]))
            data = archive.read(member)
            (DEST / name).write_bytes(data)
            faces.append({
                "file": name, "member": member, "weight": weight,
                "style": style, "bytes": len(data), "sha256": sha256(data),
            })
            print("  %-28s %7d bytes" % (name, len(data)))

        lock["families"][spec["family"]] = {
            "source": {
                "repo": spec["repo"], "tag": spec["tag"], "asset": spec["asset"],
                "asset_sha256": sha256(blob), "url": asset_url(spec),
            },
            "license": {
                "file": spec["license_file"], "member": spec["license_member"],
                "sha256": sha256(license_bytes),
            },
            "faces": faces,
        }
        print("  %-28s %7d bytes  (license)"
              % (spec["license_file"], len(license_bytes)))

    write_lock(lock)
    total = sum(len(e["faces"]) for e in lock["families"].values())
    print("\nfonts.lock.json written. %d faces, %d families."
          % (total, len(lock["families"])))
    return EXIT_OK


def main(argv):
    parser = argparse.ArgumentParser(
        description="Vendor static font faces and maintain fonts.lock.json.")
    parser.add_argument("--check", action="store_true",
                        help="verify vendored files against the lock, no network")
    parser.add_argument("--allow-upstream-change", action="store_true",
                        help="accept an upstream archive whose hash moved")
    args = parser.parse_args(argv)

    if args.check:
        return check()
    try:
        return vendor(args.allow_upstream_change)
    except urllib.error.URLError as exc:
        print("network error: %s" % exc, file=sys.stderr)
        return EXIT_MISMATCH


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
