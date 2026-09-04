# Reference-led direction

Use this for every fresh Enterprise Candidate public website before the first
visual candidate. It supplies a positive, project-specific direction source;
it is not a moodboard ritual, a generic gallery crawl, a popularity contest,
or permission to reproduce another brand's work.

Read the current [public reference source registry](public-reference-sources.json)
and complete the selection brief, candidate comparison, strong-reference
study, and transfer map in project-local `reference-dossier.md` before the
first visual candidate. Initialize with `--profile enterprise-candidate` so
the prebuild gate can hold the record; a standard-only state on a fresh public
build is an omission the gate will flag.

## Contents

- [No shortcuts](#2026-09-04-no-shortcuts)
- [Use only eligible public material](#use-only-eligible-public-material)
- [Retrieve the way each source allows](#retrieve-the-way-each-source-allows)
- [Check the ledger before selecting](#check-the-ledger-before-selecting)
- [Build a quality-gated, brief-fit candidate set](#build-a-quality-gated-brief-fit-candidate-set)
- [Compare candidates before selection](#compare-candidates-before-selection)
- [Study every interaction surface](#study-every-interaction-surface)
- [Judge visible quality and fit before it enters the list](#judge-visible-quality-and-fit-before-it-enters-the-list)
- [Name what the site is known for](#name-what-the-site-is-known-for)
- [Read the whole front end, behavior first](#read-the-whole-front-end-behavior-first)
- [Capture what you looked at](#capture-what-you-looked-at)
- [Take the good parts into one design](#take-the-good-parts-into-one-design)
- [Give every component a source](#give-every-component-a-source)
- [Rebuild the first screen from its mapped reference](#rebuild-the-first-screen-from-the-references-screen)
- [Never build from a picture](#never-build-from-a-picture)
- [Study the whole source](#study-the-whole-source-not-only-the-screen-you-captured)
- [Review source fidelity on the first screen](#review-source-fidelity-on-the-first-screen)
- [Measure the first screen before the second section exists](#measure-the-first-screen-before-the-second-section-exists)
- [Diff the finished build against its references](#diff-the-finished-build-against-its-references)
- [Prove each signature arrived](#prove-the-signature-arrived-one-reference-at-a-time)
- [Check beauty, lineage, and flow before any gate](#check-beauty-lineage-and-flow-before-any-gate)
- [Improve execution without adding design](#improve-execution-without-adding-design)
- [Run the one gate](#the-gate-is-one-command)
- [Continue autonomously](#continue-autonomously)

## 2026-09-04 no shortcuts

Time, tokens, cost, elapsed effort, implementation difficulty, convenience,
and words such as demo, sample, small, quick, test, or hurry may reduce only the
truthful delivered scope. They never reduce reference eligibility, quality or
exact brief-fit qualification, count/source spread, complete same-origin
traversal, the 90-second and 15-fps recording floor, wide/narrow evidence,
source-fidelity proof, component provenance, the first-screen gate, the final
gate, or whole-scope copy, functional, responsive, and access review.

Ninety seconds per viewport is a floor, not proof of completeness. The schema-4 recorder
continues past it until traversal completes and fails rather than emitting a
passing record when any page, state, target, or scroll surface remains.
Never substitute a home-made observer or recorder, hand-write a generated
record, lower a threshold, omit a route/state, defer required evidence, or
write the dossier after the build to justify what already exists. If a required
source, capability, tool, or check is unavailable, the affected website
candidate remains blocked and is not presented.

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

## Build a quality-gated, brief-fit candidate set

Before browsing, write the selection brief. It covers the actual audience and
arrival context; visitor decisions and tasks; truthful content entities,
relationships, routes, and states; brand and identity constraints; operating
model and category expectations; material/media needs; accessibility,
performance, and maintenance limits; and rights/access boundaries. These are
the selection criteria. A visual resemblance to one brief noun is not.

Use the maintained registry to discover candidates only from sources marked
`award` or `curated`. That status makes the visible work eligible for serious
study; it does not make it suitable. Quality and exact brief fit are joint
gates: a candidate that is excellent but mismatched is rejected, as is a
category match with weak design. Do not choose from gallery order, a random
result, award tier, popularity, novelty, fashion, recency, or ease of
recreation.

Industry is evidence, not a rule in either direction. A strong same-category
site may model the real content and task well. An adjacent or unrelated field
may be stronger only when the dossier records a concrete transfer rationale:
which source content model, visitor task, audience relationship, brand posture,
operational behavior, route progression, and responsive transformation map to
this website. If that mapping depends on invented content or an ornamental
analogy, reject the candidate.

When an active source has filters, sorting, categories, tags, or search, use
those controls to answer the selection brief rather than repeating the same
gallery order. Record the controls and why they fit, plus plausible alternate
paths checked. Status-based routes may help discovery but cannot be the whole
pool or substitute for studying the work itself.

Record at least six strong individual references, drawn from at least three
active sources, with no single source supplying more than half of the rows.
Among live sites, no two rows may point at the same host. The floor exists so
that no single site becomes the template; it is not a target. Gallery
homepages do not count as references. A public gallery entry can count only
for the visible design and states it actually exposes.

## Compare candidates before selection

A listing becomes a serious candidate only after the visible work has been
opened at wide and narrow widths. Study its complete legitimately accessible
experience before ranking it: entry and home; relevant inner pages; navigation;
the content/task progression to the ending; and every material hover, focus,
press, open, scroll, transition, media, reset, error, recovery, and reduced-
motion state that the source exposes. Inspect accessible page code, DOM,
route/state hooks, loaded assets, and event-capable elements as a coverage aid
for routes and controls manual browsing may miss, then reconcile every discovery
against live browser evidence. A recorder is instrumentation for this
study, not permission to stop after its sampled path.

Enter at least eight serious finalists in the dossier's candidate-comparison
table. Bind each distinct wide and narrow capture, list the pages and states
studied, compare it against the selection brief, and record `selected` or
`rejected` with the concrete reason. At least two finalists must be rejected.
Rejections must identify the actual mismatch, such as
an incompatible content model, task, audience, brand posture, operational
assumption, rights/access limit, incomplete experience, weak narrow
transformation, or grammar that cannot coexist with the intended dominant
source. “Less exciting,” “wrong industry,” or “another site looked better” is
not sufficient. A weak or mismatched candidate stays rejected even when that
means the pool or source spread remains incomplete; selection happens after a
real comparison, never a search result promoted directly into a strong row.

Treat `organization_context`, `audience`, and `visitor_task` as separate
required gates. Organization context binds the source to this organization's
exact mission, authority, offering, stakeholder relationship, operating
reality, and trust burden. Shared audience or industry language cannot make a
different institutional or commercial model fit; reject it unless generated
evidence proves a concrete transfer without invented claims, content, or
interface patterns.

## Study every interaction surface

Scrolling is not a complete study. At wide and narrow widths, enumerate every
reachable visible navigation item, menu/open-close control, role or audience
band, card, image, gallery tile, link, button, search/filter field, carousel,
accordion, tab, modal, form state, video control, cursor-sensitive surface, and
footer interaction. Hover, focus, move the pointer, and safely click or
keyboard-activate each target. Record the actual before/after/settled route,
state, visual property, behavior, and ledger-bound frame/event evidence.

Use the DOM/code inventory only to find coverage gaps. The live browser decides
what actually changed. Repeated targets can share a behavior class only when
every target ID is enumerated, each input class is tested, and the generated
census proves equivalent behavior. Same-origin links are traversed by exact GET
navigation; external side effects, login, purchase, sending, uploads, or
personal-data actions remain explicit blocked hand-offs. Do not click a broad
text match, cap targets, follow only the first link, or label a target tested
without its target-specific before/after evidence.

The completed interaction census is bound in `reference-dossier.md` for every
selected source. Final transfer verification must then prove each mapped build
component carries the same target behavior, trigger, state change, and
responsive transformation—not merely a matching component name, color, or
static detail.

Complete the generated source rendered-QA ledger at wide and narrow too. For
every visited page and authored state it records clipping, collision and fixed-
rail overlap; exact accessible-text/role identity for visible and intentionally
hidden controls; dead controls and ARIA state equivalence; keyboard and
reduced-motion behavior; direct deep-link, reload and dead-end paths; and every
open or closed overlay. An overlay clears only when its closed descendants are
actually inoperable and an open instance proves stacking, background hit/focus
blocking, initial focus, forward/back trap, Escape closure, and focus return.
`aria-hidden` alone is not inertness. Use this generated evidence to reject a
defective source; do not describe the defect away or silently copy it.

## Judge visible quality and fit before it enters the list

A source registry tells you who curated or awarded visible work and how to
reach it. It does not prove that the work is excellent for this brief. Open
every candidate, study the whole experience, and judge its execution against
the selection brief and the actual visible evidence. A thin, dated, broken, or
mismatched site is dropped however prestigious its listing and however neatly
it would fill a source-spread requirement.

The producer's eye alone has not been enough. Asked which sites a rejected
build came from, the producer named four; the owner opened them and called
three crap on sight. So the harness checks every dynamic claim: a site with
fewer than three distinct mechanisms, or with scroll choreography active on
less than half of its depth, cannot claim a rich `motion:` signature. That
floor does not reject an excellent static reference; it requires `static:` and
wide/narrow composition plus structure/style evidence instead of invented
motion.

The score is a claim check, not the selection judgment. A dynamic site can
clear it and still fail the brief; a static site can have no mechanisms and be
the strongest match. If the set cannot be filled with excellent, exact-fit
sources, keep researching. Padding to reach the floor is worse than searching
longer, because a mediocre or mismatched reference teaches the wrong design.

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

Prefix the signature `motion:` or `static:`. A motion signature names the
element, trigger, sequence, magnitude, and settled result, using verbs because
the source actually changes. A static signature names the concrete dominant
composition, typographic, photographic, object, or color relationship and its
visible hierarchy without inventing movement or adding a fake verb. A static-
dominant site may contain incidental motion; the evidence must show why the
static relationship, not that minor mechanism, is what a visitor would name.
The prefixes are evidence kinds, not style preferences or quotas.

Reject a signature that only names a subject, isolated color, or mood. “Warm
domestic object people buy for their home, photography led” was written about
a site whose actual signature was content holding in the center while the next
thing travelled into it. “Pure black page” and “stark white, product alone” are
likewise too thin unless the row describes and proves the specific dominant
relationship that makes the composition memorable.

Then test the claimed signature against the same question. If a thousand
strangers would not name it, it is not the signature takeaway. Ordinary
supporting navigation, controls, rows, and footers need not become signature
moments, but they still come from the mapped dominant reference grammar and
its measured evidence; the producer cannot supply them. A design assembled
only from forgettable fragments will be exactly as unmemorable as they are.
Someone taken to a waterfall does not come back describing a crack in the
sidewalk.

Two causes make a producer write down the sidewalk, and both are avoidable:

- Evidence. A still is the correct proof for a static relationship and cannot
  prove behavior. A producer working only from stills may miss the reason a
  dynamic site is good, while a producer forced to describe motion may erase a
  static site's real strength. Capture both viewport classes and observe the
  available behavior before classifying the signature.
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
left behind however distinctive it is. Apply quality and exact fit together:
the part must be exceptionally executed, fit this brand and audience, and
serve the route's real content and task. Failure on any axis rejects it.
Read available behavior before cataloging the static furniture because dynamic
signatures are otherwise easy to miss, not because static relationships matter
less. A site's composition, color behavior, type scale, and shapes are much of
what gets rebuilt, and a row that records only motion is as incomplete as one
that records only margins.

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
  themselves. Take a family the extractor measured on a selected reference;
  the producer does not supply or hand-match a family. When a measured family
  cannot be licensed, use only the rank-one result emitted by
  `scripts/match_typeface.mjs` for that measured source family. If a valid
  measured match cannot be produced, reject that type contribution or select
  another reference; producer or ad hoc owner taste does not choose a
  substitute;
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

Every strong row binds two distinct full-page PNGs under
`.design-dna/references/`: one wide and one narrow, each recorded in its own
table cell as `path plus sha256:<64 lowercase hex>`. Every serious finalist in
the candidate comparison binds the same pair. A negative row binds the capture
that proves its mismatch and both viewport classes when responsiveness is part
of the finding. The gate verifies that each cited file exists, decodes as a
PNG, matches its hash, and occupies the declared viewport class. One screenshot
reused in both columns is not wide/narrow research.

### Record it, then narrate every event

Before writing a `motion:` strong row, record it and look at every captured
moment where the screen changed:

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/record_reference.mjs" \
  --url "https://example.test/" --id strong-3 --out .design-dna/references \
  --state-contract .design-dna/references/strong-3-state-contract.json \
  --seconds 90 --fps 15
```

Create the state contract from
`templates/reference-state-contract-template.json` and replace its placeholder
with every relevant source state, exact URL, and exact trigger. State IDs are
authored evidence, never names guessed by the recorder. The schema-4 recorder
binds its producer and browser dependencies, records full wide and narrow
profiles, recursively traverses every discovered same-origin page, drives
every native and transform scroll surface to terminal, and exercises every
contract state and discovered hover target. Ninety seconds at 15 fps is the
minimum for each profile; if coverage remains incomplete, rerun at a greater
duration until it is complete. Any remaining page, state, target, or scroll
surface fails closed. It differences both videos frame by frame and keeps the moments that
matter as EVENTS under `strong-3-wide-events/` and
`strong-3-narrow-events/`: one sheet of four frames (before, during, after,
settled) for every hover, click or scroll step that changed the screen, one
for each run of quiet scrolling, and one for each change the page made on
its own (a video, a carousel, a card that cycles), each with the percent of
the screen that changed, where, and how long it took to settle. A hover
that changed nothing is listed as quiet and gets no sheet. Open every event
sheet in both profile directories in order and write
`strong-3-sequence-read.md`: one profile-qualified line per event, what the
cursor did, what scrolled, what changed; then a `## Behaviour
inventory` table of what the site does with magnitudes and the events that
show it (the wide and narrow event indexes are its skeleton). The dossier
binds the state contract, recording, read, and external artifact ledger. That
ledger hashes the recording JSON, both videos, both cursor paths, both
difference signals, every full frame, every event sheet, and both event
indexes. The read names profile-qualified events the
signature is on, and the validator refuses a motion read that skips an event or
has no inventory. The per-sheet read of 9.0.0 proved
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
next page arrives animated. Its schema-5 record binds producer,
structure-probe, browser-helper, Playwright, and browser-executable hashes;
exact requested/final URLs and redirect/status chains; recursive wide/narrow
page and scroll coverage; and explicit source-state structures/mechanisms. Run
it once per strong
reference:

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/observe_reference.mjs" \
  --url "https://example.test/" --id strong-1 --out .design-dna/references \
  --state-contract .design-dna/references/strong-1-state-contract.json
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

Every strong reference needs a distinct full-page wide and narrow pair. These
show composition, section rhythm, proportion, measure, color distribution, and
responsive transformation across the full page. A `motion:` row additionally
needs a wide and narrow temporal sequence: scroll from entry to ending in a
real browser, capture closely enough to expose every material change, and
exercise applicable hover, focus, press, navigation, transition, media,
ending, reset, and recovery states. Watch both sequences before writing the
row. A `static:` row binds the wide/narrow pair plus structure/style evidence;
inspect available behavior to confirm it does not displace the claimed static
dominance, but do not fabricate a temporal sequence when none is observable.

Keep every frame beside the row under the same rank name (`strong-3.png`,
`strong-3-narrow.png`, `strong-3-scroll-01.png`). The strong table binds both
full-page captures; its observation evidence and sequence/static-evidence
block bind the frames and records that prove the signature.

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
playwright-cli scroll --delta-y -100000
playwright-cli resize 375 812
playwright-cli screenshot --full-page --filename ".design-dna/references/strong-3-narrow.png"
playwright-cli screenshot --filename ".design-dna/references/strong-3-narrow-scroll-01.png"
playwright-cli scroll --delta-y 600
playwright-cli screenshot --filename ".design-dna/references/strong-3-narrow-scroll-02.png"
playwright-cli close
python -B -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" ".design-dna/references/strong-3-scroll-02.png"
```

Repeat the scroll and screenshot pair to the foot of the page at both widths,
then bind the capture that shows the signature:
`.design-dna/references/strong-3-scroll-02.png plus sha256:<the printed digest>`.
Name captures by role and rank (`strong-3.png`, `weak-1.png`) so a reviewer
can match them to rows without opening the record.

Captures are internal evidence. They stay inside `.design-dna/`, which the
deployable public root already excludes, and they are never shown to the
visitor or presented as the project's own work.

## Take the good parts into one design

The selected references are where the site's front-end design comes from, and
the site must still read as one design. Select at least four strong references
from at least two sources and map every taken relationship to a route, state,
or system role. Assign one selected reference as the dominant visual grammar
for each route. It supplies the route's hierarchy, composition, progression,
surface and control language, and responsive transformation. Other references
may contribute their strongest mapped moments only when those moments remain
compatible with that grammar. If combining them requires the producer to
invent connective design, change the combination or study a reference that
already supplies the missing relationship.

- One source-bound color system, whether the dominant reference uses one
  palette, route-specific palettes, state changes, or another recorded
  relationship. Client brand colors are the values when supplied; otherwise
  every hue and its distribution comes from measured selected-reference
  evidence. Do not simplify or expand that behavior into a producer palette.
  `check_style_provenance.mjs` refuses an unsourced loud color.
- One type system, taken rather than chosen. Every family and role comes from
  a selected reference's measured system or an explicit client brand system.
  When a measured family cannot be licensed, use only the rank-one result from
  `scripts/match_typeface.mjs`. If no valid measured match exists, reject that
  contribution or select another reference. Do not add a favorite, familiar,
  or supposedly brand-fitting face. `check_style_provenance.mjs` refuses an
  unsourced family.
- One source-bound progression. Reproduce the dominant reference's section
  rhythm, scale relationships, transitions, and intentional discontinuities;
  do not impose shared margins, steady scale, or smooth ground changes unless
  the source supplies them. Compatible contributions cannot make the route
  change into an unrelated design at every screen.
- One interaction and motion posture, copied from the dominant reference and
  compatible contributors. A static source set may yield a deliberately still
  result; do not add motion to make the site feel designed. When motion exists,
  its element, trigger, sequence, magnitude, duration, narrow behavior, and
  reduced-motion fallback come from recorded source behavior rather than a
  stock reveal.

Copying a design relationship is not pasting a page. Adapt it to the truthful
content, route job, brand authority, accessibility needs, and operating reality
of this project. Do not reuse a reference's logo, name, wordmark, copy,
photographs, illustrations, code, or distinctive whole page. If the source
cannot survive those boundaries while remaining recognizable, reject it; do
not fill the gap with producer design.

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
the site names a selected reference rank and the recorded values it
reproduces. There is no permission path for a producer source. The census and
component table cover every part the build actually renders, including
navigation, opening, controls, rows/lists, footer, type scale, and any scroll
or hover behavior that exists. A static source set must not invent motion to
fill a row. The gate refuses a values cell that paraphrases instead of
reproducing; a component with no source line does not ship.

This is not a licence to assemble a collage. The parts still have to become
one design, by the rules in the section above: one dominant source grammar per
route, source-bound color and type systems, coherent progression, and a
source-bound interaction/motion posture that may be still.

## Rebuild the first screen from the reference's screen

Keep the mapped reference's first screen open beside the build and reproduce
how it is arranged: what kind of thing fills it, where the identity sits, how
the space is divided, and what meets each edge, together with its measured
type, spacing, color, surface, and behavior. Copying only values without the
arrangement is not source fidelity.

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

## Never build from a picture

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/extract_reference_styles.mjs" \
  --url "https://example.test/" --id strong-1 \
  --observation .design-dna/references/strong-1-observation.json \
  --out .design-dna/references
```

It refuses to run without the current schema-5 observation for the same exact
URL and replays that observation's authored source states at wide and narrow.
It drives the page and reads the design system out of the live CSS: every
distinct type setting, every colour with how much it covers, every control's
padding, radius, border and transition, every section ground and division. The
dossier binds it, and the `Recorded values reproduced` column is checked
against the numbers it found. A producer given a still reports the things a
still carries, which is why the last three rejected builds came back with
caption alignment, a pill radius and a hover duration, and everything else
invented.

## Study the whole source, not only the screen you captured

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

## Review source fidelity on the first screen

Build and render the first screen of the primary route before any other route
exists, at wide and narrow width, and compare it directly beside the mapped
reference captures. When owner review is part of the brief, show this bounded
checkpoint before scaling; otherwise continue after the required source-
fidelity evidence passes. It must already carry the source-bound color, type,
media, structure, and interaction/motion posture, including deliberate
stillness. Building eight routes on an unverified first screen was how earlier
rejected builds lost their time.

## Measure the first screen before the second section exists

The full planned route set, selected-reference mapping, applicable states, and
wide/narrow viewport definitions must already exist in
`.design-dna/route-manifest.json`. As soon as the primary first screen renders,
run the packaged hard stop against its manifest key:

```text
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/gate.py" \
  --project "<PROJECT_ROOT>" \
  --build-id "<FIRST_SCREEN_BUILD_ID>" \
  --route-manifest .design-dna/route-manifest.json \
  --phase first-screen \
  --route-key <PRIMARY_KEY>
```

This phase binds the full manifest hash and proof build ID, but executes only
the named route at both manifest viewport classes. It runs the source-fidelity
checks before the generic structure can spread and writes
`.design-dna/evidence/first-screen-gate.json` without overwriting the final
gate. Bind that artifact as `First-screen gate` in the direction proof and
prebuild record. A nonzero result blocks the second section and every other
route. Fix the mapped source transfer and rerun; never clear it by changing the
citation to whichever reference happens to resemble the producer-built screen.
If the planned route, state, viewport, or reference mapping changes, rerun the
first-screen phase against the updated full manifest before broad work resumes.

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

Two things close it. The first is an objective derived check, run after the
dossier is finalized:

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/check_signature_transfer.mjs" \
  --dossier .design-dna/reference-dossier.md \
  --observation .design-dna/references/strong-1-observation.json \
  --observation .design-dna/references/strong-2-observation.json \
  --out .design-dna/evidence/signature-transfer.json
```

Do not bind `signature-transfer.json` inside the dossier it reads. Each
`Recorded proof` cell binds independent mechanism evidence for `motion:` or
wide/narrow capture plus structure/style evidence for `static:`. The final gate
binds the derived signature-transfer result separately.

For a `motion:` signature, the harness ranks mechanisms by weight and the check
requires the row to name the single highest-weight observed behavior, then
requires the mapped final route to prove that same behavior. A small true hover
cannot stand in for the source's dominant pinned or transformed sequence. For
a `static:` signature, the check uses the wide/narrow captures plus structure
and style evidence to prove the claimed dominant composition, typography,
media, or color relationship. It must not invent a mechanism, and incidental
motion must not be promoted merely to satisfy a verb rule.

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
an isolated color rather than a concrete color relationship, the build has no
signature and the direction is not finished however
clean the render is. If any answer is no, the direction is wrong; return to
the design transfer map and rebuild the affected routes. Do not proceed to the
review chain, the contrast record, or the readiness gate with a candidate
that fails this check, because those gates prove honesty and difference, not
that the site is good. Record the answers in the visual review's
reference-led closure as the `Lineage result`.

## Improve execution without adding design

Improve accuracy, content completeness, accessibility, responsive resilience,
performance, maintainability, and implementation finish while preserving the
recorded reference design. These are execution improvements, not permission to
invent a new layout, typeface, palette, component, icon, transition, or
signature interaction. When improvement requires a visible relationship the
current sources do not provide, research and measure another suitable
reference, update the comparison and transfer map, and rerun the affected
proof. Do not relabel producer invention as improvement.

## The gate is one command

After all mapped routes and states are implemented and reviewed, run:

```text
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/gate.py" \
  --project "<PROJECT_ROOT>" \
  --build-id "<IMMUTABLE_BUILD_ID>" \
  --route-manifest .design-dna/route-manifest.json \
  --phase final \
  --prebuild-authorization .design-dna/evidence/prebuild-authorizations/<GENERATED>.json \
  [--browser-executable "<BROWSER_EXECUTABLE>"]
```

The schema-2 route manifest is authoritative: every route has one unique key
and URL, one exact selected-reference rank/id/observation path/hash binding,
and typed custom states with exact triggers, substantive expectations, and
mapped source-state IDs; its viewport list includes at least one wide and one
narrow class. The manifest has an immutable `manifest_id` and no build ID. The
CLI uses a distinct final build ID and binds the exact generated first-screen
authorization predecessor. The
gate extracts that build's computed styles per route and viewport, counts the
components, runs provenance, structure, mechanisms and signature transfer,
validates the dossier, and writes `.design-dna/evidence/gate.json` with one
verdict line: `GATE PASS ...` or `GATE FAIL ...`. Quote it verbatim in the
final message. If the gate did not run, say “the gate did not run.” “Quick,”
“demo,” and “hurry” never reduce this gate; if there is no time to run it,
there is no build to present.

## Continue autonomously

Once the dossier and the design transfer map are complete, build and review
the site without waiting for a separate research approval. Pause only when a
missing fact, brand decision, rights question, cultural authority, or delivery
constraint would materially change the result.
