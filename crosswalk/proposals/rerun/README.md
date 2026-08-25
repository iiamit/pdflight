# Handbook refinement rerun

The first sweep ran while `bootstrap_crosswalk.py` was dropping wrapped
References lines, so some packets never saw documents their Task cites. The
PHAK was absent from 396 ATP elements and 146 Instrument ones. These files
redo the handbook chapter proposals for those two certificates against the
corrected reference lists.

A file here supplements the matching file under `handbook/`: `anchors` and
`why` are replaced, `sections` and `section_why` are left alone.

Packets are built by `tools/refine_packets.py` and validated back in by
`tools/refine_handbooks.py`. Nothing here is trusted: an anchor absent from
`anchors/anchors.lock.json` is rejected, and so is a chapter belonging to a
document the element's Task does not cite.
