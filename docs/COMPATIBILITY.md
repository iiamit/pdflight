# Reader compatibility

The single largest source of user-visible failure. Verified by hand for every
release, and published honestly.

Annotation apps re-render PDFs on import and strip link annotations. That is
their behavior, not a defect in this file. Saying so up front prevents most
support traffic.

## Test matrix

No release has been cut yet, so no results exist.

| Reader | Links | Outline | Load time | Notes |
|---|---|---|---|---|
| Apple Books (iPadOS) | | | | reference platform |
| Files / Quick Look | | | | |
| ForeFlight Documents | | | | |
| Garmin Pilot | | | | |
| GoodNotes | | | | known to break links |
| Notability | | | | known to break links |
| Adobe Acrobat iOS | | | | known poor performance |
| Acrobat / Preview desktop | | | | |

## Design constraints that maximize survival

- Simple `/GoTo` actions with named destinations only.
- No JavaScript, no embedded files, no form fields, no `GoToR`, and no `/Named`
  actions beyond `NextPage` and `PrevPage`.
- No optional content groups and no transparency groups on generated pages.
- PDF 1.7, not 2.0. Mobile reader support for 2.0 is inconsistent.
