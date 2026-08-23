# Crosswalk verification

The bootstrap gave every ACS element the documents its Task cites, at
`confidence: auto`. This is the guide to the other half: narrowing those to
sections, confirming them, and marking them `verified`.

BUILD-PLAN budgets 50 to 80 hours for Private and Instrument. Most of that is
judgment, not typing.

## The unit of work is the Task, not the row

There are 26,075 rows, which is not the number of decisions.

Every element inside a Task shares one References line, so it shares the same
targets. Deciding "for this Task, PHAK means chapter 15" settles every element
in it at once.

| Certificate | Rows | Elements | **Tasks** |
|---|---|---|---|
| private | 5,143 | 1,192 | **61** |
| instrument | 1,975 | 338 | **22** |
| commercial | 5,116 | 1,192 | 60 |
| atp | 5,128 | 1,027 | 48 |
| cfi | 8,713 | 1,744 | 85 |

**Private and Instrument together are 83 Tasks.** That is the v1.0 scope, and
BUILD-PLAN is explicit that it ships before anything else is touched.

## Start here

```
python tools/crosswalk_review.py --stats
python tools/crosswalk_review.py --certificate private --area I --limit 6
```

The worklist prints each Task with its elements, the first element's text, its
current targets, and which anchors are available to refine each one to. Work
an Area at a time; Areas are how the ACS itself is organised and how a
checkride is run.

To verify a Task, edit `crosswalk/private.csv`:

1. Narrow `target_ref` where a section genuinely fits. `phak` becomes
   `phak:ch15`. Leave it at the document where no section is more right than
   the whole thing.
2. Set `confidence` from `auto` to `verified`.
3. Put the reason in `note`, replacing the bootstrap text.

Leave `element_text` alone. It exists so the crosswalk survives an ACS
renumbering; see below.

## You can only point at an anchor that exists

This is the constraint that shapes the work. `phak:ch15` resolves because it is
in `anchors.lock.json`. Inventing `phak:ch15:airspace-class-b` produces a row
that fails the build, because `make resolve` refuses unresolved anchors.

Today 73 anchors resolve: PHAK and IFH chapters, AFH chapters, Aviation Weather
chapters, AC 61-65K paragraphs, the Private ACS Areas, and every one of the 849
CFR sections.

**The regulations are the easy half.** Every CFR section is already a native
destination, so `14cfr:part-61` can be narrowed to `14cfr:61.51` immediately,
with no new anchor work.

**The handbooks are chapter-level only.** Narrowing below a chapter means
adding a pattern to `anchors/patterns.yaml` first and re-running
`make index resolve`. Worth doing where a Task points at one specific passage,
not worth doing wholesale.

**Risk Management has no anchors at all**, and it is the single most cited
document in the crosswalk at 5,410 rows. It is a short handbook and adding
chapter anchors for it is probably the highest-leverage hour available.

Most-cited targets, which is where anchor work pays back fastest:

| Target | Rows |
|---|---|
| risk-management | 5,410 |
| afh | 4,994 |
| phak | 4,909 |
| aim | 2,791 |
| aviation-instructor | 1,729 |

## Two decisions to make before refining

**Part 39 is cited but not carried.** 433 of 1,983 CFR rows point at a part
outside `manifest/cfr.yaml`. Most are deliberate: Part 97 is TERPS and Part 121
is out of scope, together 249 rows. But **Part 39, Airworthiness Directives, is
49 rows and was never deliberately excluded**. The Private ACS cites it under
Airworthiness Requirements, and it is a short part. Adding it to `cfr.yaml`
would resolve those rows and cost very little.

The remainder are Parts 117, 63, 93, 25, 23 and 111, mostly ATP and transport
category, and mostly reasonable to leave out for a v1.0 aimed at Private and
Instrument.

**Some references have no home at all.** `AC 68-1`, `AC 120-71`, `AC 60-28` and
several 90-series circulars are cited by Tasks but are not in the corpus. They
are reported by `make crosswalk` under "unmet references". Each is a decision:
add it, or accept the element points only at its other targets.

## Why element_text is in the schema

The FAA renumbers ACS task codes on revision, roughly annually. A crosswalk
keyed only by code breaks by id rather than by page, and there is no way to
tell which new code corresponds to which old one.

`element_text` is the recovery path: fuzzy-match the stored text against the
new ACS to propose a remap, then review the proposal instead of re-authoring
the crosswalk. That is why the column exists and why it should not be edited to
say something tidier than what the ACS actually says.

## What "verified" is claiming

That a human read the element and the target and judged the target to actually
support that element. Not that the bootstrap looked plausible.

The bootstrap is deliberately generous: it gives an element every document its
Task cites, whether or not each one is relevant to that particular element.
Narrowing is as often about **removing** a target as retargeting it. A row that
should not exist should be deleted, not marked verified.

## Checking the work

```
make crosswalk-stats     progress by certificate
make resolve             fails if a row points at an anchor that does not resolve
make validate            gate 3, every element still has at least one target
```

Gate 3 is the floor: an element must keep at least one outbound target. Delete
the last row for an element and the build fails, which is the intended
behaviour.
