# Releasing

Event driven, never calendared. Source changes drive releases. The FAA does not
revise on a monthly rhythm, so a monthly cron would ship stale AIMs half the
time and cut empty releases the rest.

Expected cadence in practice: 8 to 12 releases a year, clustered around AIM
changes.

## Setup, once

`check-sources.yml` decides when a build is due, then asks `build.yml` to run
by firing a `repository_dispatch`. **The default `GITHUB_TOKEN` cannot do
that.** GitHub refuses to start a workflow from an event raised by its own
token, which is a deliberate guard against a run triggering itself forever.

So the automated path needs a token that is not `GITHUB_TOKEN`:

1. Create a fine-grained personal access token with **Contents: read and
   write** on this repository only.
2. Add it as a repository secret named `DISPATCH_TOKEN`.

Without it nothing breaks and nothing lies: `check-sources` still detects
drift, still classifies it, and still maintains the drift issue. It just
annotates the run with a warning saying a build is due and cannot be started
automatically. Run `build.yml` by hand in that case.

The `drift` label must exist for the issue step to work:

```
gh label create drift --description "Upstream source changed" --color FFB168
```

## The three workflows

| Workflow | Trigger | Does |
|---|---|---|
| `check-sources` | daily 11:00 UTC, manual | probes every source and eCFR, classifies drift, updates the drift issue, asks for a build when one is due |
| `build` | dispatch, quarterly cron, every PR, manual | builds the PDF and uploads it as an artifact |
| `release` | a successful `build` on `main` | publishes a tagged release, unless the build is byte-identical to the last one |

`release` runs on `workflow_run` rather than as a step inside `build`, so a
pull request build can never publish. That is also why it needs no extra token:
unlike `repository_dispatch`, `workflow_run` is meant to be chained.

## What earns a release

**Tier 1 releases on its own.** An AIM change number, any ACS or PTS revision,
a new handbook edition, a 14 CFR amendment to Parts 1, 43, 61, 67, 68, 71, 91
or 135, or a 49 CFR 830 amendment. These are the parts a certificate applicant
actually operates under.

**Tier 2 waits** for the next Tier 1 release or the quarterly floor. Advisory
Circular revisions, interpretation changes, crosswalk work, theme and tooling
changes, and 14 CFR amendments to parts outside the Tier 1 list.

## The three timing rules

Each exists to stop a specific bad release.

- **Debounce, 72 hours.** Federal Register amendments cluster, so a Tier 1
  change waits three days before it builds. Without this one rulemaking cuts
  three releases in a week.
- **Floor, 7 days.** Never more than one release a week. Anything arriving
  inside the window rides along with the next one.
- **Ceiling, 90 days.** Build quarterly even with zero drift, which catches
  silent URL rot and toolchain breakage while there is still time to fix it
  calmly. The ceiling outranks the debounce: a release 100 days stale ships.

The debounce clock is `first_seen` in `state/pending.json`, and it does not
restart when the same change is seen again. The check runs daily, so refreshing
it on every sighting would hold a Tier 1 change forever.

`state/` is gitignored, so the queue lives in the Actions cache between runs.
Losing it is not harmful: the next check re-detects the same drift and restarts
the debounce, which delays a release by three days rather than skipping it.

## Versioning

`vYYYY.MM.N`, sequence within the month. Date-legible, and it does not pretend
to a monthly cadence it does not have.

## Why an unchanged build does not release

Rule 8: identical inputs produce a byte-identical SHA-256. `release` compares
the built hash against the previous release's `SHA256SUMS` and stops when they
match. That is what keeps the quarterly floor build from cutting an empty
release, and it only works because the build is deterministic.

## Doing it by hand

```
make check      probe sources and eCFR, classify drift, decide
make drift      print the drift issue body
make build      full build
make notes      release notes from the lock diff
```

`make check` prints `build=true` or `build=false` as its last line, which is
what the workflow reads.

## Distribution

The release asset is named `pdflight.pdf` so this URL is always the current
release and needs no CDN, no JavaScript, and no manual updating:

```
https://github.com/iiamit/pdflight/releases/latest/download/pdflight.pdf
```
