# Reference-led direction

Use this for every fresh Enterprise Candidate public website before the first
visual candidate. It supplies a positive, project-specific direction source;
it is not a moodboard ritual, a generic gallery crawl, a popularity contest,
or permission to reproduce another brand's work.

Read the current [public reference source registry](public-reference-sources.json)
and create the project-local `reference-dossier.md` record before broad
implementation. Initialize the project with `--profile enterprise-candidate`
so the prebuild gate can hold the record; a standard-only state on a fresh
public build is an omission the gate will flag.

## Contents

- [Use only eligible public material](#use-only-eligible-public-material)
- [Retrieve the way each source allows](#retrieve-the-way-each-source-allows)
- [Check the ledger before selecting](#check-the-ledger-before-selecting)
- [Build a brief-weighted reference set](#build-a-brief-weighted-reference-set)
- [Judge the site yourself before it enters the list](#judge-the-site-yourself-before-it-enters-the-list)
- [Name what the site is known for](#name-what-the-site-is-known-for)
- [Read the whole front end, behavior first](#read-the-whole-front-end-behavior-first)
- [Capture what you looked at](#capture-what-you-looked-at)
- [Take the good parts into one design](#take-the-good-parts-into-one-design)
- [Give every component a source](#give-every-component-a-source)
- [Approve the first screen](#approve-the-first-screen)
- [Measure the first screen before the second section exists](#measure-the-first-screen-before-the-second-section-exists)
- [Diff the finished build against its references](#diff-the-finished-build-against-its-references)
- [Check beauty, lineage, and flow before any gate](#check-beauty-lineage-and-flow-before-any-gate)
- [Improve beyond the set](#improve-beyond-the-set)
- [Continue autonomously](#continue-autonomously)

## Use only eligible public material

The registry identifies sources whose public material was available when it was
audited. A source may display a sign-in or pricing link and still be useful when
the actual inspiration entry is visible publicly. Select only material you can
see legitimately during the current project:

- a public live site;
- a public gallery screenshot, case study, portfolio card, or other visible
  design entry; or
- material reachable through an account the user is authorized to use.

Do not use a login, payment, subscription, security interstitial, private
entry, or browser limitation as a reason to bypass access controls. A source
that is temporarily unavailable is skipped for this project; a source whose
useful material genuinely requires restricted access remains inactive until a
future legitimate public audit changes the registry.

## Retrieve the way each source allows

Each active registry source declares a `retrieval` mode, measured at the last
audit:

- `fetch`: a plain HTTP request exposes entry links and preview images, so a
  text fetch of a gallery page or entry page is enough to find candidates.
- `browser`: entries render only in a real browser session. A plain fetch
  returns a script shell, an empty listing, or a rate-limit response. That
  result is not evidence that the source is unavailable; it is evidence that
  the wrong tool was used.

For a `browser` source, use the interactive path described in the
[render harness](render-harness.md). With the Playwright CLI the sequence is
`open <url>`, `resize 1440 900`, then `screenshot --filename <path>`; read the
current `--help` rather than relying on remembered flags, and close the
session when done. Move at a human pace on a source that rate-limits, and
never work around a limit, a login wall, or a security interstitial.

Whatever the mode, the candidate you evaluate is the visible work itself, not
the gallery's listing text. Open the entry or the live site and look at it at
a wide and a narrow width before it earns a row.

## Check the ledger before selecting

Every project begins with fresh research. Do not begin from a prior project's
reference set, shortlist, or transfer map. Search the active sources again for
this brief, record the current discovery paths and retrieval date, and judge
the visible work again before it earns a row. A reference may appear in more
than one project when current independent research genuinely surfaces it and
the new brief gives it a fresh project role; record that reuse and its current
discovery basis. Repetition is not the failure. Carrying forward the same five
sites because they are convenient is the failure.

When an authorized cross-project [ledger](ledger.md) exists, read its
"references used" column for recent unrelated work before choosing this set.
Reaching for the same sites project after project is how a studio grows a
house style out of other people's work. Reuse of a recent reference needs a
brief-specific reason, recorded in the dossier's ledger-check line; without
one, choose differently. If no authorized ledger exists, record `none` and
continue.

## Build a brief-weighted reference set

Start with the visitor, category, content, material/media need, task, and
project risk. Weight the active sources accordingly rather than using the same
gallery order for every project. Pick references from any genre for the
design relationship, never by the client's industry: a baby-crib brand may
take its design from an art museum, a software manual, a brand-guidelines
site, or an architecture studio.

When an active source has filters, sorting, categories, tags, or search, use
those controls to test the current brief's specific experience and content
questions. Record the controls and the reason they fit the brief, including
alternative plausible discovery paths considered; the dossier's
`Source-specific filters` line is required and the prebuild gate rejects a
record that leaves it blank. A Site of the Day, award
tier, rank, chronology, or popularity route may be useful for fresh discovery,
but it is not evidence that a source will serve this project. Keep it as one
documented route alongside other brief-relevant search paths, never as a
mandatory gate, the whole candidate pool, or a substitute for source study.

Record at least six strong individual references, drawn from at least three
active sources, with no single source supplying more than half of the rows.
Among live sites, no two rows may point at the same host. The floor exists so
that no single site becomes the template; it is not a target. Gallery
homepages do not count as references. A public gallery entry counts even when
the linked site no longer works.

## Judge the site yourself before it enters the list

A source registry tells you that someone submitted a site. It does not tell
you the site is good. Open every candidate, scroll it, and decide with your
own eyes whether it is beautiful and whether you would be proud to have made
it. A thin, dated, or ugly site is dropped on sight however it was listed and
however neatly it would have filled a source-spread requirement.

The producer's eye alone has not been enough. Asked which sites a rejected
build came from, the producer named four; the owner opened them and called
three crap on sight. So the harness scores every candidate and the gate drops
a thin one without anyone having to look: a site with fewer than three
distinct mechanisms, or with scroll choreography active on less than half of
its depth, cannot hold a `motion` row. One animated hero over an otherwise
static page is the generic shape, and it scores as one.

The score is a floor, not the judgment. A site can clear it and still be ugly,
and that is the producer's call to make before the row is written. If the set
cannot be filled with sites the producer honestly finds beautiful, keep
looking. Padding to reach the floor is worse than searching longer, because a
mediocre reference teaches a mediocre design.

## Name what the site is known for

Before recording a single structural note, answer one question about each
reference: if you showed this site to a stranger and asked what they noticed
about its design, what would they say? That answer is the site's signature,
and it is the first thing the row records.

Most often the signature is something that happens rather than something
that sits there: how the page moves as you scroll, what enters and when and
how fast, a material or texture that behaves, a transition between pages, a
cursor that does something, one moment of scale or contrast or surprise.
That is why behavior is read first and captured first, and it is the part a
still image structurally cannot deliver.

It is not the only kind of signature. Some of the best sites barely move, and
what a stranger names is a typographic composition, a photographic treatment,
an editorial grid, a color relationship, or the sheer scale of one element.
Those are signatures too, they are read from stills, and a site with no motion
is a strong reference when its signature is strong. The test is never whether
a part moves. The test is whether a stranger would name it.

Write the signature as a verb. The gate refuses a `Signature` cell with no
word for what the site does, because every rejected build in this skill's
history recorded a noun. "Warm domestic object people buy for their home,
photography led" was written about a site whose actual signature was content
holding in the center of the screen while the next thing travelled into it.
"Pure black page with a large opening paragraph", "stark white, product
alone", "one image at a time with a running clock" were the others. Each is
true. Each is a subject, a palette or a mood. Each produced a rejected build.

Then test every part you plan to take against the same question. If a
thousand strangers would not name it, it is not the takeaway. A warm
background, a card with a price beneath it, a wordmark at the top of the
screen are all true observations that no visitor has ever remembered, and a
design assembled from observations like those will be exactly as
unmemorable as they are. Someone taken to a waterfall does not come back
describing a crack in the sidewalk.

Two causes make a producer write down the sidewalk, and both are avoidable:

- Evidence. A still image can only show what does not move, so a producer
  working from stills will extract the static parts every time and miss the
  reason the site is good. The capture method decides the finding before the
  finding is written, which is why the section below requires behavior to be
  captured first.
- Convenience. Layout, color, and type are the easiest things to rebuild, so
  they are what a producer reaches for. The reference sets the ambition; the
  producer's implementation comfort does not. If the honest reason a part was
  chosen is that it was easy to rebuild, it is the wrong part.

## Read the whole front end, behavior first

### Transfer what made the reference worth opening

A selected reference contributes its memorable whole, not a convenient scrap.
The producer must be able to state, before implementation, the experience that
made the page excellent: the main event a visitor would mention after
exploring it. "It has a dark background", "the type is big", "there is a
gradient", "the cards have a nice radius", and "it has a hover" are surface
observations, not a reference takeaway. They describe sidewalk cracks, not the
waterfall.

For every selected row, begin `Design to copy` with that main event and bind a
project adaptation that preserves it. Then name the supporting relationships
that make it work in the source, choosing every applicable layer rather than
cherry-picking the easiest one:

- the scroll or scene sequence and the pace that creates the experience;
- the opening and body composition, including what occupies the visitor's
  attention at each turn;
- its object, image, illustration, information, or typographic treatment;
- the color, ground, depth, shape, and scale relationships that give the
  visual world its identity;
- hover, press, cursor, navigation, or other visitor-caused behavior; and
- its narrow-screen recomposition.

The selected project must carry the reference's main event and at least the
supporting relationships necessary for that event to remain recognizable in
the new brief. A line that takes only a font posture, palette value, background
color, one generic animation, or a decorative detail fails this transfer
standard even if it technically names a source. If the main event is not
project-appropriate, drop the reference rather than taking its furniture.

Before the candidate is considered direction-ready, apply the **waterfall
test** to every selected reference: hide the design-transfer map and show the
candidate beside the source sequence. Can a viewer identify what extraordinary
experience was carried over, beyond an ingredient list? If the honest answer
is only that it borrowed a color, type, or layout detail, reopen the source reading and
the build. The goal is neither a wholesale clone nor a collage; it is an
adaptation of the strongest whole ideas from several sites into one coherent
front end.

Every reference has parts worth taking and parts to leave, and the `Design to
copy` cell records both: the good parts, named in concrete terms, and the
parts left behind, named too. A reference's most distinctive ingredient is
not automatically a good one, and an ugly, dated, or brand-foreign part is
left behind however distinctive it is. Judge, in this order: is it beautiful;
does it fit this brand and audience; does it serve the route's job. Only a
part that passes all three is taken. Read all of these things, in this order.
The order exists because the signature is what gets lost when a producer
starts with the furniture, not because the later items matter less: a site's
composition, color behavior, type scale, and shapes are most of what actually
gets rebuilt, and a row that records only motion is as incomplete as one that
records only margins.

- what the page does as it is scrolled: what enters and how, what tracks the
  scroll, what pins or sticks and for how long, what scales, masks, splits,
  or reorders itself, and the pace of the whole sequence from top to bottom;
- interaction: hover and press states, the cursor, controls that respond,
  transitions between pages or views, sound, anything the visitor causes;
- the signature moment: the one thing the site would be described by, and
  where in the page it happens;
- media treatment: image sizes, crops, bleeds, strips, staggering, overlap,
  captions, and whether media or type carries the page;
- composition: column structure, section composition, margins, how the first
  screen is built, what sits where;
- color as behavior AND as values: how the ground carries the page, how a
  fade or a contrast relationship works, how much color there is and where it
  lands, AND THE HUES THEMSELVES. Take them. Where the client has recorded
  brand colors those win; where the client has none, which is every demo and
  every spec build, the palette is the colors the extractor measured on the
  selected references. This line used to end "the values themselves stay with
  the reference, because the build uses the brand's own palette", and for a
  client with no brand that sentence meant the producer invented every hue.
  It did: one build's accent, the fill of every control and a whole full-bleed
  band, measured 122 from the nearest color any of its five references
  computes;
- type as posture and scale AND THE FAMILIES: the sizes as a scale, weights,
  case, measure, the relationship between display and text, and the families
  themselves. Take a family the extractor measured on a selected reference.
  This line used to read "not the family names, because the build's families
  are chosen for beauty and brand fit, never because a reference used them",
  which is an instruction to bring your own typeface to a copying exercise. A
  face picked by matching an x-height ratio to the reference's face is chosen
  by taste with arithmetic offered as the reason. When a measured family
  cannot be licensed, name the closest licensable cut of THAT family, or get
  the owner's permission for a substitute in the owner's quoted words;
- shapes and surfaces: radii, borders, rules, cards, pills, frames, shadows
  or their absence;
- the phone version: what the same page does at narrow width, scrolled the
  same way.

A reference that offers no good, transferable front-end part for this brief
is not a reference. Gallery membership, an award, or a large audience is not
the reason to select it; the parts on the screen are.

Also collect at least three weak or mismatched public examples. Describe the
specific observed relationship that fails this brief, such as empty spectacle,
unclear hierarchy, portable commerce scaffolding, inappropriate media, poor
reading behavior, or an unhelpful mobile transformation. Do not make claims
about the creator, rating, authorship, or why it appeared in a gallery.

## Capture what you looked at

Every strong and negative row binds a capture of the work as you saw it:
a PNG saved under `.design-dna/references/`, recorded in the row as
`path plus sha256:<64 lowercase hex>`. The gate verifies that the file exists,
decodes as a PNG, and matches its hash. A row without a capture is rejected,
because a reference nobody looked at is not research; it is a plausible name.

### Record it, then narrate every event

Before anything is written about a reference, record it and look at every
moment in the recording where the screen changed:

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/record_reference.mjs" \
  --url "https://example.test/" --id strong-3 --out .design-dna/references
```

It moves a real cursor to every interactive thing on the first screen and
dwells long enough for an expansion, a label and a caption to play; scrolls
in steps hovering what arrives; returns to the top and follows one internal
link so the transition and an inner page are on tape. Then it differences
the video frame by frame and keeps the moments that matter as EVENTS under
`strong-3-events/`: one sheet of four frames (before, during, after,
settled) for every hover, click or scroll step that changed the screen, one
for each run of quiet scrolling, and one for each change the page made on
its own (a video, a carousel, a card that cycles), each with the percent of
the screen that changed, where, and how long it took to settle. A hover
that changed nothing is listed as quiet and gets no sheet. Open every event
sheet in order and write `strong-3-sequence-read.md`: one line per event,
what the cursor did, what scrolled, what changed; then a `## Behaviour
inventory` table of what the site does with magnitudes and the events that
show it (`strong-3-events.md`, written by the recorder, is its skeleton).
The dossier binds the recording and the read, names the events the
signature is on, and the validator refuses a read that skips an event, calls
most of them static, or has no inventory. The per-sheet read of 9.0.0 proved
the method and cost an afternoon per site, nearly all of it spent on sheets
where nothing changed; the events are the same watching at the cost of the
moments alone.

This is the fourth instrument for the same job, and the reason is the same
each time. Stills called a sequence. Computed styles called a copy. Then a
harness that drove the page and wrote its mechanisms down as numbers, which
was correct, and which let the producer read the numbers, open one rest frame
of forty-one, and build a photograph inside a dotted line. The owner recorded
himself using that site for a minute. Walked at ten frames a second it held:
a sheet that loads as a miniature with a dieline around it and zooms up;
navigation photographs that grow to half the viewport under the pointer and
shove their neighbours out of the way; a label pill that trails the cursor
and decodes through random glyphs; a justified caption per cell; a showreel
with project cards drifting under the pointer; a button whose fill drains and
splits into a label block and an arrow square; a dock that rises on the first
scroll; brackets built from redacted bars; a quote whose words slide into
place; section titles drawn in hatch lines that fill with colour as you dwell;
a work index that reshuffles to promote what you hovered; and a page
transition that zooms the sheet out to a card, slides it away, and slides the
next one in. Nineteen behaviours. The build had one dashed border.

The harness is kept, as a cross-check on the reading. Run it after the read,
never instead of it. `scripts/observe_reference.mjs` drives the page with real wheel gestures,
reads every element's geometry against the viewport, finds whichever scroller
actually consumed the input, and records the site's mechanisms as numbers:
what held in the viewport and for how many pixels, what travelled through the
held frame, what swapped while it held, what revealed, what parallaxed and at
what rate, what followed the pointer, how long a hover takes, and whether the
next page arrives animated. Run it once per strong reference:

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/observe_reference.mjs" \
  --url "https://example.test/" --id strong-1 --out .design-dna/references
```

Do not substitute a hand-rolled capture script, and do not measure a site with
a script of your own. Two failures are being replaced here, both committed by
the producer who wrote this paragraph.

The first: told to watch a site scroll, it jumped the scroll position with
`window.scrollTo`, screenshotted the resting state at each stop, and called a
sequence of stills a scroll sequence. A resting frame cannot show a reveal, a
parallax, a hover or a transition, so every takeaway came back as something a
photograph can hold.

The second, after that was fixed: told to copy the design rather than
paraphrase it, it wrote a measuring script that read computed styles, font
sizes, padding, radii and colors, and built from those. Every one of those is
a property of a still. The tool could not see a pinned stage, so the producer
could not report one, and the build it produced was rejected for the same
reason as all the others. On one of those four references the document never
scrolls at all: the page is 900px tall and moves its content by transform
inside an inner scroller. Every instrument that watched `window.scrollY` saw
a site that does nothing. The harness now finds that scroller and reports the
stage held for 69,300px of scroll with the slides travelling through it.

The mechanism sheet is what a build reproduces. Not "big type" or "a nice
fade": the held distance, the swap count, the rate, the duration, the easing.

A strong reference needs both kinds of evidence, because each shows what the
other cannot. Take all of it:

- a full-page wide capture and a full-page narrow capture. These are how
  composition, section rhythm, proportion, measure, and the distribution of
  color across a whole page are read, and none of that is legible in a
  sequence of viewports. Keep taking them.
- a scroll sequence: scroll the page from top to bottom in a real browser and
  capture the viewport at each step, closely enough that what enters, moves,
  pins, or transforms is visible between consecutive frames. Watch it back
  before writing the row.
- what neither still can reach: hover and press states on the interactive
  parts, a page transition, and the phone version scrolled the same way.

Keep every frame beside the row under the same rank name (`strong-3.png`,
`strong-3-narrow.png`, `strong-3-scroll-01.png`), and bind in the row the one
capture that shows the signature, whether that is a scroll frame or the
full-page still.

What changed is the sufficiency, not the value, of the full-page still. A
single full-page screenshot no longer qualifies a strong reference on its
own, because a full-page composite is stitched from a page nobody watched
moving, and a producer holding only that artifact will describe margins and
background colors every time. It remains required, and it remains the right
evidence for everything static.

When motion genuinely cannot be observed, because the site is gone, the entry
is a gallery still, or scripting fails, say so in the row instead of
describing motion nobody watched. Such a reference is still eligible; it is
judged on what can be seen.

A minimal sequence with the Playwright CLI, run from the project root:

```text
playwright-cli open "https://example.test/entry"
playwright-cli resize 1440 900
playwright-cli screenshot --full-page --filename ".design-dna/references/strong-3.png"
playwright-cli screenshot --filename ".design-dna/references/strong-3-scroll-01.png"
playwright-cli scroll --delta-y 700
playwright-cli screenshot --filename ".design-dna/references/strong-3-scroll-02.png"
playwright-cli scroll --delta-y 700
playwright-cli screenshot --filename ".design-dna/references/strong-3-scroll-03.png"
playwright-cli resize 375 812
playwright-cli screenshot --full-page --filename ".design-dna/references/strong-3-narrow.png"
playwright-cli close
python -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" ".design-dna/references/strong-3-scroll-02.png"
```

Repeat the scroll and screenshot pair to the foot of the page, then bind the
capture that shows the signature:
`.design-dna/references/strong-3-scroll-02.png plus sha256:<the printed digest>`.
Name captures by role and rank (`strong-3.png`, `weak-1.png`) so a reviewer
can match them to rows without opening the record.

Captures are internal evidence. They stay inside `.design-dna/`, which the
deployable public root already excludes, and they are never shown to the
visitor or presented as the project's own work.

## Take the good parts into one design

The selected references are where the site's front-end design comes from,
and the site is still one design. Select a named subset of at least four
strong references, drawn from at least two sources, and record in the design
transfer map which good part of each goes where: this one's first-screen
composition, that one's way of fading a warm ground, another's image strip,
another's scroll reveal. Multiple references exist so that the result is a
clone of none of them. Then design the site as one thing before any route is
built beyond the first screen:

- One palette, and its values are MEASURED, not chosen. If the client has
  recorded brand colors, they are the palette. If the client has none, which
  is every demo and every spec build, the palette is built from the colors
  the extractor recorded on the selected references: their grounds, their
  inks, their accent. A reference contributes how color behaves AND what the
  colors are. This bullet used to say a reference contributes behavior
  "never its literal values", and that for a brand with no colors the
  producer should "derive one palette from the product, the material, and the
  audience". Read plainly, that is an instruction to invent a palette, and it
  is what a producer does with it: the accent of one build, filling every
  control and a whole band, sat 122 from the nearest color any of its five
  references computed. `check_style_provenance.mjs` now refuses a loud color
  no reference computes, so this is checked and not merely asked for.
- One type system, TAKEN: two families at most, each one a family the
  extractor measured on a selected reference. Not a family chosen for beauty,
  not a family whose x-height ratio matches the reference's, not "a
  beautiful free face of the same quality". Those are all the producer
  choosing the typeface, and the last one was written into this file as the
  approved answer. When a measured family is not licensable, use the closest
  licensable cut OF THAT FAMILY; if there is none, the substitute needs the
  owner's permission in the owner's quoted words, recorded with the family it
  replaces. Never a monospace, pixel, or novelty face as a workaround for a
  reference's licensed font. `check_style_provenance.mjs` refuses a family no
  selected reference uses.
- One rhythm. Each section leads into the next: shared margins, a consistent
  scale, transitions of ground that feel like one page turning, not a new
  site starting. A page whose sections come from different references and
  change voice at every screen has failed this step.
- One motion language, and it is designed. At least one selected reference's
  actual behavior lands in this build, rebuilt for this content, named in the
  transfer map with the route that receives it, and confirmed in the rendered
  scroll sequence. Sections that fade up as they enter are not a motion
  language: that is the default every generated site ships, and shipping it
  is the tell. Decide what moves, why it moves, what it does to the reader,
  how fast, and what happens on the phone and under reduced motion.

Copying a part is not pasting a page. Adapt each taken part to the actual
content, route job, and media of this project. The rights boundary is the
only legal limit: do not reuse a reference's logo, name, wordmark, copy,
photographs, illustrations, or code verbatim. A composition, a color
behavior, a type scale, a scroll behavior, and a shape language are not
protected, and this record exists to take them.

Ambition is set by the references, not by the seriousness of the subject. A
safety subject, a small business, or a demo does not license a quiet
information page when the selected references are not quiet. The anti-tell
rules elsewhere in this skill are a floor under the design, never the design
itself.

Keep the dossier and synthesis internal. They should guide the work, never
leak onto the customer-facing website as process labels, design rationale, or
back-end taxonomy.

## Give every component a source

The rejected builds all had the same shape underneath. The references
supplied one scroll effect, and the producer supplied the navigation, the
buttons, the list rows, the section headings and the footer from memory.
Memory produces the generic skeleton every time, so the result was the
skeleton with one borrowed effect painted on it, and the owner named exactly
that: "the call to action buttons, the shapes, the sizes, the colors, and
everything about that looks vibe coded."

The dossier's `Component sources` table closes it. Every part that ships on
the site names either a selected reference rank and the recorded values it
reproduces, or `owner-approved:` with the owner's own words permitting the
producer's design for that part. The gate requires at least navigation,
opening, buttons, rows or lists, footer, scroll behavior, hover behavior, and
type scale, and refuses a values cell that paraphrases instead of reproducing.
A component with no source line does not ship.

This is not a licence to assemble a collage. The parts still have to become
one design, by the rules in the section above: one palette, one type system,
one rhythm, one motion language.

## Rebuild the first screen from the reference's screen

Keep the reference's first screen open beside the build and reproduce how it
is arranged: what kind of thing fills it, where the wordmark sits, how the
space is divided, what is against each edge. Not its font sizes. The
difference is the whole difference.

The failure this replaces was total. A producer researched six references,
scored them, filtered them by register, measured them, and then shipped a page
whose layout, both typefaces, shapes, spacing and section rhythm it had
invented. Exactly one thing on the page came from the research: a circular
button. The owner named it in one second. Asked why, the honest answer was
that reproducing a layout means giving up authoring, and the producer took
authoring back at every decision because nothing stopped it.

Two things stop it now. The `Component sources` table demands the structure of
each part, not its properties, and refuses a cell that only carries sizes. And
`scripts/compare_structure.mjs` reads the finished first screen and compares
it with the reference's:

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/compare_structure.mjs" \
  --url "http://127.0.0.1:4920/" \
  --reference .design-dna/references/strong-1-observation.json \
  --out .design-dna/evidence/structure-diff.json
```

It compares four things and fails below three: which kind of thing is largest
on the first screen, where the ink sits over a sampled grid, what lives against
each edge and in each corner, and the proportions of the type. Run against the
build that shipped the button, it said what a person says: the largest thing on
the first screen is text where the reference's is a photograph, and the ink
agrees on 20% of the screen against a floor of 55%.

## Pick great sites, then filter by register

Quality first, register second. Reversing that order is how a build ends up
made of six faithful copies of forgettable sites, which is a forgettable site.

The rejected build pulled candidates from a submission feed's bulk tag listing,
judged each from one 1440x900 still, and kept the ones whose feeling matched
the brief. What it kept was a wedding-vendor site with a press-logo strip, a
Shopify storefront and a guesthouse template. It then copied them accurately,
and the owner's reaction to the result was a single syllable.

Take candidates only from sources the registry marks `award` or `curated`. A
submission feed is fine to browse and cannot supply a selected reference.
Record what each site won.

## Never build from a picture

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/extract_reference_styles.mjs" \
  --url "https://example.test/" --id strong-1 \
  --out .design-dna/references
```

It drives the page and reads the design system out of the live CSS: every
distinct type setting, every colour with how much it covers, every control's
padding, radius, border and transition, every section ground and division. The
dossier binds it, and the `Recorded values reproduced` column is checked
against the numbers it found. A producer given a still reports the things a
still carries, which is why the last three rejected builds came back with
caption alignment, a pill radius and a hover duration, and everything else
invented.

## Copy the whole site, not the screen you captured

A producer will copy exactly as far as its captures reach and then start
designing, without noticing the moment it crossed over. The build that forced
6.9.0 copied a first screen, a portfolio, a held statement block, a photograph
band and a listing faithfully from five references, and then invented two
entire inner pages, a form, a footer and every connective part of the home
page. Asked why, the honest answer was that going back for more evidence meant
standing the harness up again and driving four more pages, and writing a lede
block took thirty seconds. It never presented itself as a decision to stop
copying. It felt like continuing.

Worse, it wrote source lines for parts it had never looked at, because the
table demanded a source and it could produce the shape of one from memory of
what the site generally looked like. A gate whose evidence the producer
authors is not a gate.

So: observe inner pages before building inner pages. Cite the frame that shows
the part, and expect the validator to open it. And let
`scripts/scan_build_components.mjs` count the build's components rather than
listing them yourself:

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/scan_build_components.mjs" \
  --url "http://127.0.0.1:4960/" \
  --url "http://127.0.0.1:4960/owners.html" \
  --out .design-dna/evidence/component-census.json

node "<DESIGN_DNA_SKILL_ROOT>/scripts/compare_structure.mjs" \
  --census .design-dna/evidence/component-census.json \
  --reference .design-dna/references/strong-1-observation.json \
  --reference .design-dna/references/strong-1-inner-observation.json \
  --out .design-dna/evidence/structure-diff.json
```

Run against the build that invented two pages, the census named them:
`ask, band, button, doors, edge, first, folio, foot, footer, form, frame,
input, lede, nav, overture, pill, place, plate, rise, roster, scope, select,
sr, steps, textarea`. Twelve rows existed. Twenty-five components shipped.

## Approve the first screen

Build and render the first screen of the primary route before any other
route exists, at wide and narrow width, and put it in front of the owner (or,
when the owner is not in the loop, in front of the producer's own eyes beside
the reference captures) as a checkpoint. It must already carry the palette,
the type system, the media treatment, and the first motion of the whole
site. Building eight routes on an unapproved first screen was how the two
rejected builds of 2026-09-01 and 2026-09-02 lost their time.

## Measure the first screen before the second section exists

Every comparator in this file used to run when the build was finished. That
ordering is why they kept passing builds the owner rejected on sight: by the
time a gate runs at the end, the design has been made, defended and written
up, and what a failing gate produces then is a better dossier, not a better
site.

So the first screen is measured the moment it renders, and the second section
is not written until both of these pass:

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/extract_reference_styles.mjs"   --url "http://127.0.0.1:PORT/" --id build-index --out .design-dna/evidence

node "<DESIGN_DNA_SKILL_ROOT>/scripts/check_style_provenance.mjs"   --build .design-dna/evidence/build-index-styles.json   --reference .design-dna/references/strong-1-styles.json   --reference .design-dna/references/strong-2-styles.json   --out .design-dna/evidence/style-provenance.json

node "<DESIGN_DNA_SKILL_ROOT>/scripts/compare_structure.mjs"   --url "http://127.0.0.1:PORT/"   --reference .design-dna/references/strong-1-observation.json   --out .design-dna/evidence/structure-diff-first-screen.json
```

`check_style_provenance.mjs` reads the build with the same extractor that read
the references and asks of every color, typeface, size, radius and transition:
which reference did this come from? It fails on a typeface no selected
reference uses, on a LOUD color no reference computes (one filling a control,
a section ground, or a measurable share of the screen), and on a traced share
below the floor.

`compare_structure.mjs` asks whether the screen is BUILT like the screen it
cites: what kind of thing fills it, where the ink sits, what is against the
edges and corners, the proportions of the type.

This is what those two say about the build of 2026-09-03, run after it was
finished:

```text
Cormorant Garamond is not a typeface any selected reference uses.
rgb(232, 183, 29) is 122 from the nearest color any reference computes;
  it is on background, 76.2% of the screen and 18 more places.
the largest thing on the first screen is text (<h1>), the reference's is
  media (<video>); where the ink sits agrees with the reference on 3% of
  the screen (floor 55%).
```

Three percent. The producer had cited a reference whose first screen is a
full-bleed video and built a typographic layout on a flat ground, and had
written a frame citation against every component of it. Run at the first
screen, that is ten minutes lost. Run at the end, it was the whole build.

A failing first screen is rebuilt from the reference's screen. It is never
answered by re-citing it to a different reference that happens to match, and
never by editing the dossier row.

## Diff the finished build against its references

When the build runs, read it with the same harness that read the references
and compare the sheets:

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/compare_mechanisms.mjs" \
  --url "http://127.0.0.1:4880/" \
  --source .design-dna/references/strong-1-observation.json \
  --source .design-dna/references/strong-2-observation.json \
  --out .design-dna/evidence/mechanism-diff.json
```

It fails in three ways, and each one is a build this skill has already
shipped. The references carry scroll choreography and the build carries none,
which is the skeleton under the styling. The build carries fewer than half of
the mechanism types the references rely on, which is the takeaway that got
lost. Or one device appears more than twice as often in the build as in any
source, which is the fade on every section: the default every generated site
ships, and the tell the owner names first.

The visual review's reference-led closure binds this record and it must pass.
A build reviewed only by eye passes on color and type every time.

## Prove the signature arrived, one reference at a time

Every check up to here proves the producer looked at the reference, measured
it, and cited it. Not one of them asks WHICH PART of it reached the page.

That is the gap the owner named after a build that passed everything: "you
still took the crack in the sidewalk instead of the waterfall." Six references
were researched for that build. Two of them arrived as a background colour and
a set of control dimensions, and both cleared the component table, the value
cross-check, the mechanism diff and the structure diff, because a source line
records that a reference was used and never which part of it was meant. A
producer takes the part it is most comfortable rebuilding, and control
geometry is the most comfortable part there is.

Two things close it. The first is objective:

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/check_signature_transfer.mjs" \
  --dossier .design-dna/reference-dossier.md \
  --observation .design-dna/references/strong-1-observation.json \
  --observation .design-dna/references/strong-2-observation.json \
  --out .design-dna/evidence/signature-transfer.json
```

The harness already sorts a site's mechanisms by weight, so it knows which one
is the biggest thing that site does. This reads the producer's `Signature`
cell against that order and refuses one that names anything but the loudest.
A site's buttons really do fill with their own colour under the pointer; that
is a small true thing written down in place of the large one, and once it is
written down the reference contributes a small true thing. Rewrite the
signature to name what the harness ranked first, then go and take THAT.

The second is a judgment and no script can take it. The dossier's
`Signature transfer` table asks the deletion question once per selected
reference: cover its row, and what does a stranger notice is gone? The answer
has to name a component the build actually ships, because a loss nobody can
point at is not a loss, and it has to name an arrangement or a behaviour that
would go with it, because a ground, a radius, a size and a control dimension
are exactly what survive when a reference was sampled instead of copied. The
component's own name does not count as the arrangement; "the first screen
would lose its warm ground" borrows a noun from the census and still describes
a colour.

If the honest answer for a reference is that nothing anyone would name would
go, that reference was not selected. It was listed. Cut it and select another,
or go back to its recorded mechanisms and take its signature properly.

## Check beauty, lineage, and flow before any gate

Before the rendered review, the records, or any audit, scroll the candidate
in a real browser, put its wide and narrow renders beside the captures of the
selected references, and answer four questions: is this beautiful; would a
designer see that it came from that set; does each section flow into the next
as one design; and, scrolling it the way a stranger would, what would that
stranger name? If the honest answer to the last question is nothing, or only
a color, the build has no signature and the direction is not finished however
clean the render is. If any answer is no, the direction is wrong; return to
the design transfer map and rebuild the affected routes. Do not proceed to the
review chain, the contrast record, or the readiness gate with a candidate
that fails this check, because those gates prove honesty and difference, not
that the site is good. Record the answers in the visual review's
reference-led closure as the `Lineage result`.

## Improve beyond the set

The taken parts are the floor for this project, not its ceiling. The
dossier's elevation line names at least one consequential decision where the
build goes further than every reference in the set: larger and more specific
real media, a category depth the references skip, a signature interaction none
of them has, a first screen that answers the visitor's question faster, or a
mobile encounter that is designed rather than collapsed. Name the decision,
say why this brief earns it, and carry it into the direction record so the
rendered closure can confirm it is visible.

## Continue autonomously

Once the dossier and the design transfer map are complete, build and review
the site without waiting for a separate research approval. Pause only when a
missing fact, brand decision, rights question, cultural authority, or delivery
constraint would materially change the result.
