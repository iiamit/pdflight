# Interpretation discovery candidates

Written by `tools/discover_interps.py`. Do not hand-edit; edits are overwritten
on the next run. Selections are recorded in `manifest/sources.yaml`.

Twelve of the thirty-four selected interpretations carry no year, so their URL
cannot be constructed. Discovery resolves them against the cached Chief Counsel
index rather than by guessing a year.

- B3 Bobertz, C2 Theriault, C3 Kortokrax, C4 Walker, D1 Collins, D2 Kuhn,
  D3 Cazares, D4 Bell, E3 Gilberti, E4 Ludwig, F3 Bell, G2 Grannis.

Matching is on surname alone. Every match is listed with its year, addressee,
and subject line. The tool never picks one; a human does. Auto-selecting on
topic similarity would be rule 2 with extra steps.

Reading a year off the index is verification. Trying years until one returns 200
is invention. The line is whether the year came from a source or from the tool.

Recurring surnames also produce multiple candidates for entries that already
have a year. Bell appears three times, Levy twice, Murphy twice, and Mangiamele
collides with itself on both surname and year in 2009.

## Candidates

Not yet generated. Phase 1 deliverable 1.4.
