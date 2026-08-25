# Brief: propose handbook chapter anchors for one packet

## What you are doing

An ACS element currently points at whole handbooks. Your job is to narrow
each one to the chapter that actually covers the element, so a button reading
`PHAK` becomes a button reading `PHAK c15`.

Read your packet at `crosswalk/proposals/packets/<packet>.json`. It holds:

- `anchor_menu`: every chapter anchor that resolved to a real page in this
  build, per document, with its title. **This is the only source of anchors.**
- `elements`: per element code, the `text` from the ACS, the `references`
  (the documents that element's Task cites) and `current` (chapter anchors an
  earlier pass already assigned).

## Rules, in order of importance

1. **Never propose an anchor that is not in this packet's `anchor_menu`.** An
   anchor recalled rather than looked up is an invented citation. AFH-3C
   inserted Energy Management as chapter 4 and moved every later chapter, so a
   remembered chapter number is wrong more often than it looks.
2. **Never propose a chapter of a document not in that element's
   `references`.** The crosswalk may not assert a link the ACS never made.
3. **Ground the choice in the text.** Run
   `python tools/handbook_search.py <doc> "<regex>"` from the repo root. It
   searches the text this build extracted and reports which chapter holds the
   hits. Use it whenever the right chapter is not obvious from the title, and
   always before proposing a chapter you are inferring rather than reading.
4. **Empty is a correct answer.** Plenty of elements are covered by a handbook
   as a whole and by no chapter in particular. Say so and move on. Do not
   force a chapter to fill a row.
5. `current` is what an earlier pass assigned. Repeat an entry you agree with,
   drop one you think is wrong, add ones that are missing. Repeating a settled
   anchor is free: the validator reports it as already applied.
6. No em-dashes anywhere, in prose or in JSON. Use " - " with spaces.

## Output

Write `crosswalk/proposals/rerun/<packet>.result.json`, one entry per element
code in your packet, JSON with `indent=1` and sorted keys:

```json
{
 "IR.VI.A.K1": {
  "anchors": ["ifh:ch10", "iph:ch04"],
  "why": "IFH ch10 IFR Flight covers approach procedures and IPH ch04 Approaches covers LP and LNAV minima directly",
  "confidence": "high"
 },
 "IR.VI.A.K2": {
  "anchors": [],
  "why": "No chapter treats RNAV annunciations as its subject. The document-level rows stay",
  "confidence": "high"
 }
}
```

`why` is truncated to 160 characters when it becomes the CSV note, so keep it
under that and make the first clause the load-bearing one. `confidence` is
`high` or `low`; use `low` when you are proposing a plausible chapter you
could not confirm in the text.

Do not touch any CSV. Do not run `refine_handbooks.py --apply`. Write your one
result file and report how many elements you gave anchors to, how many you
deliberately left empty, and anything the packet made impossible to answer.
