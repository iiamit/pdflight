// Cover, main menu, per-document menus, and colophon.
//
// Preamble only; tools/menus.py appends the generated body.
//
// Every idiom here is lifted from iiamit/iamit.org assets/css/aviation.css, as
// section 6 of CLAUDE.md sets out: the METAR-style status strip, the
// `pdflight_` brand mark with an amber underscore, `01 · STANDARDS` section
// numbering behind an 18pt amber rule, headings with a trailing period, pill
// chips for per-document metadata, and the two-column mono ident block reused
// on the colophon.
//
// Amber is for actions and live signals only. Here that means the live dot,
// section rules, link targets, and the primary button. Body stays ink,
// secondary ink-2, labels ink-3. No page is tinted amber.
//
// Only labelled `heading` elements export PDF named destinations, learned the
// hard way in Phase 2. Every navigable target below is therefore a heading.

#let bg = rgb("#0A0D14")
#let bg-2 = rgb("#0F141D")
#let bg-3 = rgb("#151B26")
#let hair = rgb("#FFFFFF12")
#let hair-2 = rgb("#FFFFFF24")
#let ink = rgb("#EEF2F7")
#let ink-2 = rgb("#AAB3C0")
#let ink-3 = rgb("#6F7886")
#let ink-4 = rgb("#485061")
#let signal = rgb("#FFB168")
#let signal-2 = rgb("#FFC68F")

#let sans = "Inter"
#let mono = "JetBrains Mono"

// Rule 8: nothing time-derived in the output.
#set document(date: none, title: "PDFlight")
#set heading(numbering: none, outlined: true)

// The site's METAR-style data bar, repurposed as document status. It does the
// currency disclosure and the branding in one element.
// One inline run, not a grid. A grid of auto columns plus gutters overflowed
// the text width and wrapped the last field onto a second line, where the rule
// below then drew straight through it.
#let status-strip(fields) = {
  set text(font: mono, size: 7.5pt, fill: ink-3, tracking: 0.6pt)
  block(width: 100%, breakable: false)[
    #text(fill: signal)[●]
    #h(5pt)
    #fields.map(f => upper(f)).join(text(fill: ink-4)[ #h(3pt) | #h(3pt) ])
    #v(3pt)
    #line(length: 100%, stroke: 0.5pt + hair-2)
  ]
}

#let doc-page(fields: (), body) = {
  set page(
    width: 8.5in, height: 11in,
    margin: (top: 0.85in, bottom: 0.75in, x: 0.9in),
    fill: bg,
    header: status-strip(fields),
    footer: context {
      set text(font: mono, size: 7.5pt, fill: ink-3)
      align(center)[#counter(page).display()]
    },
  )
  set text(font: sans, size: 10.5pt, fill: ink, lang: "en")
  set par(leading: 0.62em, spacing: 0.75em)
  show link: set text(fill: signal)
  body
}

// `iamit_` on the site, static here rather than blinking. The underscore is
// escaped: bare `_` opens emphasis in Typst markup.
#let brand(size: 14pt) = text(font: mono, size: size, weight: 500, fill: ink)[
  pdflight#text(fill: signal)[\_]
]

// `01 · STANDARDS`: mono, 0.2em tracking, uppercase, ink-3, behind an 18pt
// amber rule at 0.7 opacity.
#let section-label(number, name) = block(above: 16pt, below: 7pt)[
  #line(length: 18pt, stroke: 1.2pt + signal.transparentize(30%))
  #v(4pt)
  #text(font: mono, size: 8pt, fill: ink-3, tracking: 1.8pt)[
    #number #sym.dot.c #upper(name)
  ]
]

// `.tail-chip`: 100px radius, 1px hair-2 border, mono.
#let chip(body) = box(
  inset: (x: 6pt, y: 2.5pt),
  radius: 100pt,
  stroke: 0.5pt + hair-2,
  text(font: mono, size: 7pt, fill: ink-3)[#body],
)

// `.btn`: mono, 0.04em tracking, 4pt radius, 1pt hair-2, transparent, with a
// trailing arrow. Padding is scaled to clear a 44pt touch target.
// Chips sit inline with the title rather than on a second line. Stacked, each
// row ran about 77pt and 34 documents needed five pages; the spec calls for a
// three-page main menu. Inline, a row is about 34pt and the whole corpus fits.
// Padding still clears a 44pt touch target with the row gap included.
#let entry-button(target, title, chips: ()) = block(
  width: 100%, above: 3pt, below: 3pt,
)[
  #link(target)[
    #box(
      width: 100%, inset: (x: 9pt, y: 7pt), radius: 4pt,
      stroke: 0.5pt + hair-2, fill: bg-2,
    )[
      #grid(
        columns: (1fr, auto, auto),
        column-gutter: 8pt,
        align: (left + horizon, right + horizon, right + horizon),
        text(font: sans, size: 9.5pt, weight: 500, fill: ink)[#title],
        if chips.len() > 0 {
          stack(dir: ltr, spacing: 3pt, ..chips.map(c => chip(c)))
        } else { [] },
        text(font: mono, size: 10pt, fill: signal)[#sym.arrow.r],
      )
    ]
  ]
]

// `.btn.primary` inverts: amber fill, bg text, weight 600.
#let primary-button(target, label) = link(target)[
  #box(
    inset: (x: 12pt, y: 9pt), radius: 4pt, fill: signal,
    text(font: mono, size: 8pt, weight: 600, fill: bg, tracking: 0.5pt)[
      #upper(label)
    ],
  )
]

// `.ident`: two-column mono grid, uppercase ink-3 labels. Reused verbatim on
// the colophon source table.
#let ident(rows) = block(width: 100%, above: 8pt)[
  #grid(
    columns: (auto, 1fr),
    column-gutter: 14pt,
    row-gutter: 5pt,
    ..rows.map(r => (
      text(font: mono, size: 7.5pt, fill: ink-3, tracking: 0.8pt)[
        #upper(r.at(0))
      ],
      text(font: sans, size: 9pt, fill: ink-2)[#r.at(1)],
    )).flatten()
  )
]

// Headings carry the site's trailing period: `Handbooks.` `Regulations.`
#let page-title(body) = block(above: 0pt, below: 10pt)[
  #text(font: sans, size: 28pt, weight: 600, fill: ink, tracking: -0.7pt)[
    #body.
  ]
]

// ---------------------------------------------------------------------------
// navigable targets. headings, because nothing else exports a destination.
// ---------------------------------------------------------------------------

#let target(body) = heading(level: 1, outlined: true)[#body]
#show heading.where(level: 1): it => block(above: 0pt, below: 0pt)[#it.body]

// Target colours. CLAUDE.md section 6 reserves amber for actions, so this is
// a deliberate widening: a reader scanning the crosswalk needs to tell a
// regulation from a handbook without reading the label. Mirrors the inline
// button palette in tools/link.py; tests/test_menus.py pins them together.
#let tint-regulation = rgb("#7BD88F")
#let tint-handbook = rgb("#7FB4FF")
#let tint-manual = rgb("#C08CFF")
#let tint-circular = rgb("#FFB168")

#let tint-for(kind) = {
  if kind == "regulation" { tint-regulation }
  else if kind == "handbook" { tint-handbook }
  else if kind == "manual" { tint-manual }
  else { tint-circular }
}

#let target-chip(label, kind) = box(
  inset: (x: 5pt, y: 2pt),
  radius: 100pt,
  stroke: 0.5pt + tint-for(kind),
  text(font: mono, size: 7.5pt, fill: tint-for(kind))[#label],
)

// What the colours mean. Drawn once at the top of each crosswalk section.
#let target-legend(pairs) = block(
  width: 100%, inset: (top: 4pt, bottom: 8pt),
)[
  #for p in pairs {
    target-chip(p.at(0), p.at(1))
    h(3pt)
    text(font: sans, size: 8pt, fill: ink-3)[#p.at(2)]
    h(10pt)
  }
]

// A crosswalk row: one ACS element and everything that supports it.
//
// The labels are plain text, not Typst links. They point into pages that do
// not exist yet when this file compiles, so tools/link.py finds them
// afterwards and attaches the GoTo. The same is true of the element code,
// which links back to the ACS page it came from.
#let crosswalk-row(code, body, refs) = block(
  width: 100%,
  inset: (top: 5pt, bottom: 5pt),
  stroke: (top: 0.5pt + hair),
)[
  #grid(
    columns: (78pt, 1fr),
    column-gutter: 10pt,
    text(font: mono, size: 8pt, weight: 500, fill: signal)[#code],
    {
      text(font: sans, size: 8.5pt, fill: ink-2)[#body]
      linebreak()
      v(2pt)
      for r in refs {
        target-chip(r.at(0), r.at(1))
        h(4pt)
      }
    },
  )
]
