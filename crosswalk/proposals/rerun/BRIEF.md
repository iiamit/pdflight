# Brief: close the handbook gaps for one packet

## What you are doing

An ACS element points at the documents its Task cites. An earlier pass
narrowed some of those to a chapter, so a button reads `PHAK c15`. The rest
still point at a whole book, and a button reading `PHAK` sends a reader to a
522 page handbook.

**Your job is those remaining documents.** For each one, decide whether a
chapter covers the element well enough to point at, and say so or say no.

Read your packet at `crosswalk/proposals/packets/<packet>.json`. Per element
it holds:

- `text`: the element as the ACS words it.
- `references`: every document that element's Task cites.
- `current`: chapter anchors an earlier pass already assigned.
- `gaps`: **the documents in `references` with no chapter yet. This is the
  work.** An element with an empty `gaps` list is already done; repeat its
  `current` anchors and move on.

It also holds `anchor_menu`: every chapter anchor that resolved to a real page
in this build, per document, with its title. That is the only supply of
anchors you may draw from.

The first attempt at this rerun reaffirmed `current` and proposed nothing for
any gap. It gave zero PHAK chapters to the 232 ATP elements that lacked one.
Do not repeat that. Working through `gaps` is the point of the pass.

## Rules, in order of importance

1. **Never propose an anchor that is not in this packet's `anchor_menu`.** An
   anchor recalled rather than looked up is an invented citation. AFH-3C
   inserted Energy Management as chapter 4 and moved every later chapter, so a
   remembered chapter number is wrong more often than it looks.
2. **Never propose a chapter of a document not in that element's
   `references`.** The crosswalk may not assert a link the ACS never made. If
   the obvious chapter lives in a document the Task does not cite, the answer
   is no chapter, not the next best book.
3. **Ground every gap decision in the text.** Run
   `python tools/handbook_search.py <doc> "<regex>"` from the repo root. It
   searches the text this build extracted and reports which chapter holds the
   hits. Search before you decide, not after.
4. **"No chapter fits" is a real answer and often the right one.** Plenty of
   elements are covered by a handbook as a whole and by no chapter in
   particular, and the Risk Management Handbook and the Seaplane handbook are
   frequently like this. Say so in `why` and leave that document alone. Do not
   force a chapter to fill a row. A wrong chapter is worse than a whole book,
   because it looks answered.
5. Repeat every `current` anchor you still agree with. Drop one only when the
   text shows it is wrong, and say what you searched. Repeating a settled
   anchor costs nothing: the validator reports it as already applied.
6. No em-dashes anywhere, in prose or in JSON. Use " - " with spaces.

## If your result file already exists

An earlier run may have left `crosswalk/proposals/rerun/<packet>.result.json`.
Read it and extend it. Keep the entries it has, add anchors for the gaps it
did not address, and rewrite `why` where you changed the anchors.

## Output

Write `crosswalk/proposals/rerun/<packet>.result.json`, one entry per element
code in your packet, JSON with `indent=1` and sorted keys:

```json
{
 "IR.VI.A.K1": {
  "anchors": ["ifh:ch10", "iph:ch04", "phak:ch16"],
  "why": "IPH ch04 Approaches covers LP and LNAV minima directly, IFH ch10 covers approach procedures, PHAK ch16 covers navigation systems",
  "confidence": "high"
 },
 "IR.VI.A.K2": {
  "anchors": ["iph:ch04"],
  "why": "IPH ch04 covers RNAV annunciations. No AFH or risk management chapter treats them, so those stay at document level",
  "confidence": "high"
 }
}
```

`why` is truncated to 160 characters when it becomes the CSV note, so keep it
under that and put the load-bearing clause first. `confidence` is `high` or
`low`; use `low` for a plausible chapter you could not confirm in the text.

Do not touch any CSV. Do not run `refine_handbooks.py --apply`.

## Report back

How many gaps you closed, how many you judged had no fitting chapter, any
anchor in the menu that looked misplaced when you searched for it, and
anything the packet made impossible to answer.
