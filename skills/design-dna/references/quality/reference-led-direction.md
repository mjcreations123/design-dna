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
- [Take the good parts into one design](#take-the-good-parts-into-one-design) |
[Approve the first screen](#approve-the-first-screen) |
[Check beauty, lineage, and flow before any gate](#check-beauty-lineage-and-flow-before-any-gate)
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

If the set cannot be filled with sites the producer honestly finds beautiful,
keep looking. Padding to reach the floor is worse than searching longer,
because a mediocre reference teaches a mediocre design. The floor exists to
stop one site becoming the template; it is not a quota to be met at any cost.

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
- color as behavior: how the ground carries the page, how a fade or a
  contrast relationship works, how much color there is and where it lands;
  the values themselves stay with the reference, because the build uses the
  brand's own palette;
- type as posture and scale: the sizes as a scale, weights, case, measure,
  the relationship between display and text; not the family names, because
  the build's families are chosen for beauty and brand fit, never because a
  reference used them;
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

Watch the site with the packaged harness before writing anything about it.
`scripts/observe_reference.mjs` opens the page, holds it still at a series of
scroll positions and screenshots each arrival twice, hovers real interactive
elements, and follows a link so the transition is seen. It compares the frames
and records whether anything actually moved. Run it once per strong reference:

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/observe_reference.mjs" \
  --url "https://example.test/" --id strong-1 --out .design-dna/references
```

Do not substitute a hand-rolled capture script. The failure this replaces is
specific and was committed by the producer who wrote this paragraph: told to
watch a site scroll, the producer jumped the scroll position with
`window.scrollTo`, screenshotted the resting state at each stop, and called a
sequence of stills a scroll sequence. A resting frame cannot show a reveal, a
parallax, a hover, or a transition, so every takeaway came back as something a
photograph can hold: a background color, a wordmark placement, a mask shape.
The gate now binds the session and refuses a motion claim the session does not
support, so this cannot be reported around.

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

- One palette, the brand's own. If the brand has colors, they are the
  palette; a reference contributes how color behaves (a fade that looks good,
  a soft ground, one accent used sparingly), never its literal values. If
  the brand has no colors yet, derive one palette from the product, the
  material, and the audience, and hold it across every route.
- One type system, chosen for beauty and brand fit: two families at most,
  each one the producer would defend on its own with no reference to justify
  it. Never a monospace, pixel, novelty, or display face as a workaround for
  a reference's licensed font; never a face because a reference used
  something like it. A reference's paid font is answered by a beautiful free
  face of the same quality, a license, or dropping the element.
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

## Approve the first screen

Build and render the first screen of the primary route before any other
route exists, at wide and narrow width, and put it in front of the owner (or,
when the owner is not in the loop, in front of the producer's own eyes beside
the reference captures) as a checkpoint. It must already carry the palette,
the type system, the media treatment, and the first motion of the whole
site. Building eight routes on an unapproved first screen was how the two
rejected builds of 2026-09-01 and 2026-09-02 lost their time.

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
