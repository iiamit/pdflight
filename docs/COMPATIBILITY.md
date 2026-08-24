# Reader compatibility

The single largest source of user-visible failure. Verified by hand for every
release, and published honestly.

Annotation apps re-render PDFs on import and strip link annotations. That is
their behavior, not a defect in this file. Saying so up front prevents most
support traffic.

## Test matrix

Tested against v2026.08.3 on 2026-08-24.

| Reader | Links | Outline | Back | Load time | Notes |
|---|---|---|---|---|---|
| Apple Books (iPadOS) | yes |  | **no** |  | tested: links work, no back control |
| Preview (iPadOS) | yes |  | **no** |  | tested: links work, no back control |
| ForeFlight Documents | yes |  | yes |  | tested: links and back both work |
| Garmin Pilot (iOS) | **none** |  | **no** |  | tested: strips every link, internal and external |
| Files / Quick Look |  |  |  |  |  |
| GoodNotes |  |  |  |  | known to break links |
| Notability |  |  |  |  | known to break links |
| Adobe Acrobat iOS |  |  |  |  | known poor performance |
| Acrobat / Preview desktop |  |  |  |  |  |

## Design constraints that maximize survival

- Simple `/GoTo` actions with named destinations only.
- No JavaScript, no embedded files, no form fields, no `GoToR`, and no `/Named`
  actions beyond `NextPage` and `PrevPage`.
- No optional content groups and no transparency groups on generated pages.
- PDF 1.7, not 2.0. Mobile reader support for 2.0 is inconsistent.

## Read it in Preview, Apple Books, or ForeFlight

**Garmin Pilot strips every link**, internal and external, so the crosswalk,
the menus and the nav stamps all do nothing there. The outline still works and
the text is intact, but the link layer that this project exists to add is
absent. If you want the crosswalk, save the file locally and open it in
Preview, Apple Books, or ForeFlight Documents.

**ForeFlight Documents keeps the links and has a back control**, which is the
full experience: element, crosswalk row, source, back, next source.

**Preview and Apple Books keep the links but have no back control.** Neither
does Garmin Pilot. On iPadOS there is no back control at all, so the crosswalk
round trip cannot rely on one and the forward path has to be complete on its
own.

That is what the nav stamp is for. Every content page carries two returns,
`[menu]` to the contents and `[doc]` to the front of the document being read,
so no jump is a dead end even with no back control. The first round of testing
found the forward path broken one step earlier: an ACS document menu had a
single link, back to the contents, and the crosswalk two pages later was
reachable only by scrolling. Every document menu now offers its crosswalk
explicitly.

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
