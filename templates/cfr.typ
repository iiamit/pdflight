// 14 CFR and 49 CFR typesetting. Preamble only; tools/cfr_build.py appends the
// generated body to this file.
//
// Theme tokens mirror theme/theme.toml, which mirrors iiamit/iamit.org
// assets/css/aviation.css. Keep the names aligned so drift is visible.
//
// Amber is for actions and live signals only. Here that means section numbers,
// part rules, and the running-header dot. Never body text.
//
// The deliberate deviation from CLAUDE.md section 6: body text is Inter at
// 10.5pt, not mono. Two thousand-plus pages of monospace is unreadable on a
// tablet. Mono stays on section numbers, the running header, and part chrome.
//
// **Every structural level must be a `heading` element.** Typst exports PDF
// named destinations only for labelled headings. A labelled block, a labelled
// helper that returns a sequence, a labelled figure, and labelled content all
// produce nothing, verified against Typst 0.15. Since `14cfr:91.155` resolving
// without text matching is the entire reason the regulations are generated
// rather than fetched, each helper below returns exactly one heading and all
// visual styling lives in a `show` rule.

#let bg = rgb("#0A0D14")
#let hair-2 = rgb("#FFFFFF24")
#let ink = rgb("#EEF2F7")
#let ink-2 = rgb("#AAB3C0")
#let ink-3 = rgb("#6F7886")
#let signal = rgb("#FFB168")

#let sans = "Inter"
#let mono = "JetBrains Mono"

// Rule 8: no build date in the output. A timestamp would change the hash on
// every run and turn every rebuild into a release.
#set document(date: none, title: "14 CFR")

#set heading(numbering: none, outlined: true)

#let status-strip(title: "", currency: "") = {
  set text(font: mono, size: 7.5pt, fill: ink-3, tracking: 0.6pt)
  grid(
    columns: (auto, 1fr, auto),
    [#text(fill: signal)[●] #upper(title)],
    [],
    [#upper(currency)],
  )
  v(-7pt)
  line(length: 100%, stroke: 0.5pt + hair-2)
}

#let cfr-doc(title: "", currency: "", body) = {
  set page(
    width: 8.5in,
    height: 11in,
    margin: (top: 0.85in, bottom: 0.75in, x: 0.9in),
    fill: bg,
    header: status-strip(title: title, currency: currency),
    footer: context {
      set text(font: mono, size: 7.5pt, fill: ink-3)
      align(center)[#counter(page).display()]
    },
  )
  set text(font: sans, size: 10.5pt, fill: ink, lang: "en")
  set par(justify: false, leading: 0.62em, spacing: 0.72em)
  show link: set text(fill: signal)
  body
}

// ---------------------------------------------------------------------------
// structure. one heading each, styling in the show rules below.
// ---------------------------------------------------------------------------

#let cfr-part(number, title) = heading(level: 1)[
  #line(length: 18pt, stroke: 1.2pt + signal.transparentize(30%))
  #v(4pt)
  #text(font: mono, size: 8pt, fill: ink-3, tracking: 2pt)[#upper("Part " + number)]
  #v(3pt)
  #text(font: sans, size: 19pt, weight: 600, fill: ink, tracking: -0.4pt)[#title.]
]

#let cfr-subpart(number, title) = heading(level: 2)[
  #text(font: mono, size: 8pt, fill: ink-3, tracking: 1.4pt)[#upper("Subpart " + number)]
  #v(1pt)
  #text(font: sans, size: 13pt, weight: 600, fill: ink-2)[#title]
]

// The section number is mono and amber so it reads as an identifier rather
// than prose. Its label becomes the PDF named destination.
#let cfr-section(number, title) = heading(level: 3)[
  #text(font: mono, size: 10pt, fill: signal, weight: 500)[§ #number]
  #h(6pt)
  #text(font: sans, size: 11.5pt, weight: 600, fill: ink)[#title]
]

#let cfr-appendix(number, title) = heading(level: 4)[
  #text(font: mono, size: 8pt, fill: ink-3, tracking: 1.4pt)[#upper("Appendix " + number)]
  #v(1pt)
  #text(font: sans, size: 12pt, weight: 600, fill: ink-2)[#title]
]

// Show rules carry spacing only. Styling lives in the helpers above, because
// a heading body is a sequence and cannot be reliably taken apart here.
#show heading.where(level: 1): it => {
  pagebreak(weak: true)
  block(breakable: false, above: 0pt, below: 8pt)[#it.body]
}
#show heading.where(level: 2): it => block(
  breakable: false, above: 13pt, below: 5pt)[#it.body]
#show heading.where(level: 3): it => block(
  breakable: false, width: 100%, above: 11pt, below: 3pt)[#it.body]
#show heading.where(level: 4): it => block(
  breakable: false, above: 12pt, below: 4pt)[#it.body]

// ---------------------------------------------------------------------------
// body
// ---------------------------------------------------------------------------

#let cfr-p(body) = block(width: 100%)[#body]

// Statutory authority and source notes: smaller, dimmer, not body copy.
#let cfr-cita(body) = block(width: 100%)[
  #text(size: 8.5pt, fill: ink-3, style: "italic")[#body]
]

#let cfr-note(body) = block(
  width: 100%, inset: (left: 10pt), stroke: (left: 1pt + hair-2),
)[
  #text(size: 9.5pt, fill: ink-2)[#body]
]

// A flush paragraph: eCFR's FP, indented relative to the enclosing paragraph.
#let cfr-fp(body) = block(width: 100%, inset: (left: 14pt))[#body]

// An unnumbered subheading inside a section. Not a `heading`, deliberately:
// it carries no label and must not enter the outline or the destination set.
#let cfr-subhead(body) = block(width: 100%, above: 8pt, below: 3pt)[
  #text(font: sans, size: 10pt, weight: 600, fill: ink-2)[#body]
]

// Regulatory tables. 91.155 basic VFR weather minimums is one of these, so
// they carry real normative content and cannot be dropped.
#let cfr-table(cols, header, cells) = block(width: 100%, above: 8pt, below: 8pt)[
  #set text(size: 9pt)
  #table(
    columns: cols,
    stroke: 0.5pt + hair-2,
    inset: 5pt,
    fill: (_, row) => if row == 0 and header.len() > 0 { rgb("#0F141D") },
    ..header.map(cell => text(weight: 600, fill: ink-2)[#cell]),
    ..cells,
  )
]
