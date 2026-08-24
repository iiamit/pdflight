"""Detect source drift, classify it, and decide whether it earns a release.

BUILD-PLAN section 7. The build is event driven: the FAA does not revise on a
monthly rhythm, so a calendared release would ship stale AIMs half the time and
cut empty releases the rest.

Two tiers decide whether a change builds now or waits.

**Tier 1** releases on its own: an AIM change number, any ACS or PTS revision,
a new handbook edition, a 14 CFR amendment touching a part a certificate
applicant actually flies under, or a 49 CFR 830 amendment.

**Tier 2** batches into the next Tier 1 release or the quarterly floor:
Advisory Circular revisions, interpretation changes, crosswalk work, tooling.

Three timing rules keep the cadence honest:

- **Debounce, 72 hours.** Federal Register amendments cluster. Waiting three
  days after the first Tier 1 change avoids three releases for one rulemaking.
- **Floor, 7 days.** Never more than one release a week.
- **Ceiling, 90 days.** Build quarterly even with zero drift, so silent URL rot
  and toolchain breakage surface while there is time to fix them calmly.

    --check     compare against the locks, rewrite state/pending.json
    --decide    read pending.json and report build or wait, exit 0 either way
    --issue     print the drift issue body as markdown

`--decide` prints `build=true` or `build=false` on its last line so a workflow
can read it without parsing prose.
"""

import argparse
import datetime
import io
import json
import pathlib
import sys

import yaml

import _http
import _manifest as M

EXIT_OK = 0
EXIT_PROBLEM = 1

PENDING = M.ROOT / "state" / "pending.json"
CFR_LOCK = M.ROOT / "manifest" / "cfr.lock.yaml"
ECFR = "https://www.ecfr.gov/api/versioner/v1"

# A 14 CFR amendment to one of these parts releases on its own. They are the
# parts a certificate or rating applicant operates under; the rest of the
# corpus is reference and batches.
TIER1_CFR_PARTS = {"1", "43", "61", "67", "68", "71", "91", "135"}

# Manifest sections whose drift is Tier 1.
TIER1_SECTIONS = {"standards", "handbooks", "aim"}

DEBOUNCE_HOURS = 72
FLOOR_DAYS = 7
CEILING_DAYS = 90


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def stamp(moment=None):
    return (moment or now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_stamp(text):
    if not text:
        return None
    try:
        return datetime.datetime.strptime(
            text, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=datetime.timezone.utc)
    except ValueError:
        return None


def load_pending(path=PENDING):
    path = pathlib.Path(path)
    if not path.is_file():
        return {"changes": {}, "last_release": None, "last_build": None}
    with io.open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    data.setdefault("changes", {})
    data.setdefault("last_release", None)
    data.setdefault("last_build", None)
    return data


def write_pending(data, path=PENDING):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")


def load_cfr_lock(path=CFR_LOCK):
    path = pathlib.Path(path)
    if not path.is_file():
        return {}
    with io.open(path, encoding="utf-8") as handle:
        return (yaml.safe_load(handle) or {}).get("parts", {}) or {}


def tier_for_source(entry):
    """Tier of a manifest document, from the section it sits in."""
    return "tier1" if entry.get("section") in TIER1_SECTIONS else "tier2"


def tier_for_cfr(key):
    """Tier of a CFR part key such as `title-14-part-91`."""
    if key.startswith("title-49"):
        return "tier1"
    return "tier1" if key.rsplit("-", 1)[-1] in TIER1_CFR_PARTS else "tier2"


def check_sources(entries, lock, state, client, out):
    """Which manifest documents look changed upstream.

    Conditional requests only. A 304 is the common answer and costs nothing,
    which is what makes a daily check affordable against faa.gov.
    """
    found = {}
    for entry in entries:
        key = entry["id"]
        locked = lock.get(key) or {}
        url = locked.get("resolved_url") or entry.get("url")
        if not url:
            continue
        prior = state.get(key) or {}
        try:
            response = client.head(url, headers=_conditional(prior))
        except Exception as error:                      # network, not content
            out.write("  %s unreachable: %s\n" % (key, error))
            continue

        if response.status == 304:
            continue
        if response.status >= 400:
            found[key] = {"kind": "source", "tier": tier_for_source(entry),
                          "detail": "HTTP %d" % response.status,
                          "id": key, "title": entry.get("title") or key}
            continue

        etag = response.header("etag")
        modified = response.header("last-modified")
        length = response.header("content-length")
        moved = []
        if etag and prior.get("etag") and etag != prior["etag"]:
            moved.append("etag")
        if modified and prior.get("last_modified") \
                and modified != prior["last_modified"]:
            moved.append("last-modified")
        if length and locked.get("bytes") and str(locked["bytes"]) != length:
            moved.append("length %s -> %s" % (locked["bytes"], length))
        if moved:
            found[key] = {"kind": "source", "tier": tier_for_source(entry),
                          "detail": ", ".join(moved),
                          "id": key, "title": entry.get("title") or key}
    return found


def _conditional(prior):
    headers = {}
    if prior.get("etag"):
        headers["If-None-Match"] = prior["etag"]
    if prior.get("last_modified"):
        headers["If-Modified-Since"] = prior["last_modified"]
    return headers


def check_cfr(cfr_lock, client, out):
    """Which CFR parts eCFR reports amended since the lock was written."""
    found = {}
    try:
        response = client.get("%s/titles.json" % ECFR)
        titles = json.loads(response.body.decode("utf-8", "replace"))
    except Exception as error:
        out.write("  eCFR titles unreachable: %s\n" % error)
        return found

    latest = {}
    for record in titles.get("titles") or []:
        number = str(record.get("number"))
        if number in ("14", "49"):
            latest[number] = record.get("latest_amended_on")

    # A title-level date moving does not say which part moved, so ask for the
    # part list only when it has.
    for key, entry in sorted(cfr_lock.items()):
        title = "14" if key.startswith("title-14") else "49"
        recorded = entry.get("amended_on")
        upstream = latest.get(title)
        if not upstream or not recorded or upstream <= recorded:
            continue
        found[key] = {"kind": "cfr", "tier": tier_for_cfr(key),
                      "detail": "title %s amended %s, lock %s"
                                % (title, upstream, recorded),
                      "id": key, "title": key}
    return found


def merge(pending, detected, moment=None):
    """Fold newly detected changes into the pending queue.

    `first_seen` is the debounce clock and must not restart when the same
    change is seen again the next day, so an existing entry keeps its stamp.
    """
    when = stamp(moment)
    changes = pending.setdefault("changes", {})
    for key, record in detected.items():
        if key in changes:
            changes[key].update(
                {"tier": record["tier"], "detail": record["detail"],
                 "last_seen": when})
        else:
            changes[key] = dict(record, first_seen=when, last_seen=when)
    return pending


def decide(pending, moment=None):
    """Build or wait. Returns (bool, reason)."""
    moment = moment or now()
    changes = pending.get("changes") or {}
    last_release = parse_stamp(pending.get("last_release"))

    if last_release:
        since_release = (moment - last_release).total_seconds() / 86400.0
        if since_release >= CEILING_DAYS:
            return True, ("ceiling: %.0f days since the last release, quarterly "
                          "floor build" % since_release)
    elif not changes:
        return True, "no release has been cut yet"

    if not changes:
        return False, "no pending changes"

    tier1 = {k: v for k, v in changes.items() if v.get("tier") == "tier1"}
    if not tier1:
        return False, ("%d tier 2 change(s) waiting for a tier 1 trigger or the "
                       "quarterly floor" % len(changes))

    oldest = min((parse_stamp(v.get("first_seen")) or moment)
                 for v in tier1.values())
    held = (moment - oldest).total_seconds() / 3600.0
    if held < DEBOUNCE_HOURS:
        return False, ("debounce: oldest tier 1 change is %.0fh old, waiting "
                       "for %dh" % (held, DEBOUNCE_HOURS))

    if last_release:
        since_release = (moment - last_release).total_seconds() / 86400.0
        if since_release < FLOOR_DAYS:
            return False, ("floor: last release was %.1f days ago, minimum is "
                           "%d" % (since_release, FLOOR_DAYS))

    return True, ("%d tier 1 change(s) held %.0fh, past debounce"
                  % (len(tier1), held))


def issue_body(pending, moment=None):
    """The drift issue, rewritten in place rather than reopened each time."""
    build, reason = decide(pending, moment)
    changes = pending.get("changes") or {}
    lines = ["<!-- pdflight:drift -->",
             "Updated %s by `tools/check_sources.py`." % stamp(moment), "",
             "**Decision:** %s. %s" % ("build" if build else "hold", reason),
             ""]
    if not changes:
        lines.append("No pending changes. The lock is current.")
        return "\n".join(lines) + "\n"

    for tier, title in (("tier1", "Tier 1, releases on its own"),
                        ("tier2", "Tier 2, batches")):
        rows = {k: v for k, v in changes.items() if v.get("tier") == tier}
        if not rows:
            continue
        lines.append("### %s" % title)
        lines.append("")
        lines.append("| Source | Detected | What moved |")
        lines.append("|---|---|---|")
        for key in sorted(rows):
            record = rows[key]
            lines.append("| `%s` | %s | %s |"
                         % (key, record.get("first_seen") or "?",
                            record.get("detail") or ""))
        lines.append("")

    lines.append("Adopt these with `make fetch-update`, or let the scheduled "
                 "build pick them up.")
    return "\n".join(lines) + "\n"


def run(argv, client_factory=None, sources_path=M.SOURCES, lock_path=M.LOCK,
        state_path=M.STATE, pending_path=PENDING, cfr_lock_path=CFR_LOCK,
        moment=None, out=sys.stdout):
    parser = argparse.ArgumentParser(
        prog="check_sources.py",
        description="Detect source drift and decide whether it earns a release.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true",
                       help="probe upstream and rewrite state/pending.json")
    group.add_argument("--decide", action="store_true",
                       help="report build or wait from the pending queue")
    group.add_argument("--issue", action="store_true",
                       help="print the drift issue body as markdown")
    parser.add_argument("--released", metavar="STAMP",
                        help="record a release at this UTC stamp and clear the "
                             "queue")
    args = parser.parse_args(argv)

    pending = load_pending(pending_path)

    if args.released:
        pending["changes"] = {}
        pending["last_release"] = args.released
        write_pending(pending, pending_path)
        out.write("release recorded at %s, pending queue cleared\n"
                  % args.released)
        return EXIT_OK

    if args.issue:
        out.write(issue_body(pending, moment))
        return EXIT_OK

    if args.decide:
        build, reason = decide(pending, moment)
        out.write("%s\n" % reason)
        out.write("build=%s\n" % ("true" if build else "false"))
        return EXIT_OK

    if not args.check:
        parser.error("one of --check, --decide, --issue, --released is required")

    entries = M.load_sources(sources_path)
    lock = M.load_lock(lock_path)
    state = {}
    if pathlib.Path(state_path).is_file():
        with io.open(state_path, encoding="utf-8") as handle:
            state = json.load(handle)

    client = (client_factory or _http.Client)()
    out.write("probing %d source(s) and the eCFR title index\n" % len(entries))
    detected = check_sources(entries, lock, state, client, out)
    detected.update(check_cfr(load_cfr_lock(cfr_lock_path), client, out))

    merge(pending, detected, moment)
    write_pending(pending, pending_path)

    build, reason = decide(pending, moment)
    tier1 = sum(1 for v in pending["changes"].values()
                if v.get("tier") == "tier1")
    out.write("%d request(s), %d change(s) detected, %d pending (%d tier 1)\n"
              % (client.request_count, len(detected),
                 len(pending["changes"]), tier1))
    out.write("%s\n" % reason)
    out.write("build=%s\n" % ("true" if build else "false"))
    return EXIT_OK


def main(argv):
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
