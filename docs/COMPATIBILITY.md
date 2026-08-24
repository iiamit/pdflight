# Reader compatibility

The single largest source of user-visible failure. Verified by hand for every
release, and published honestly.

Annotation apps re-render PDFs on import and strip link annotations. That is
their behavior, not a defect in this file. Saying so up front prevents most
support traffic.

## Test matrix

No release has been cut yet, so no results exist.

| Reader | Links | Outline | Back | Load time | Notes |
|---|---|---|---|---|---|
| Apple Books (iPadOS) | | | | | reference platform |
| Files / Quick Look | | | | |  |
| ForeFlight Documents | | | | |  |
| Garmin Pilot | | | | |  |
| GoodNotes | | | | | known to break links |
| Notability | | | | | known to break links |
| Adobe Acrobat iOS | | | | | known poor performance |
| Acrobat / Preview desktop | | | | |  |

## Design constraints that maximize survival

- Simple `/GoTo` actions with named destinations only.
- No JavaScript, no embedded files, no form fields, no `GoToR`, and no `/Named`
  actions beyond `NextPage` and `PrevPage`.
- No optional content groups and no transparency groups on generated pages.
- PDF 1.7, not 2.0. Mobile reader support for 2.0 is inconsistent.

## The back control is load bearing

Most of this file is about links surviving. One thing depends on the reader
offering something else: a way back to the previous view.

An ACS element commonly cites three or four regulations. The crosswalk page
gives each its own link, and the element code on that row returns to the ACS.
What no static PDF can provide is the leg from a regulation back to the
crosswalk row that sent you there, because 91.175 is cited by 43 different
elements and a `/GoTo` cannot know which one you came from. Rule 6 rules out
the JavaScript that would.

So the loop is: element code, crosswalk row, section, **reader back**,
crosswalk row, next section. Every mainstream reader has that control, but it
is worth testing rather than assuming, so it has a column above.

Where a reader has no back control, the nav stamp still gets you to the
document menu and the outline still reaches every section by number. The
crosswalk row is the part that would be tedious to re-find.
