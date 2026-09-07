---
name: design-dna
description: Builds, redesigns, polishes, and visually reviews specific, current, non-generic websites and web UIs using only qualified measured references and approved project authority—never producer-authored visible design. Use for landing pages, multi-page sites, place/community publications, hospitality, ecommerce, portfolios, editorial sites, dashboards, product interfaces, documentation, and components; requests avoiding AI-looking, vibe-coded, templated, cookie-cutter, dated, or time-incongruent design; feedback that work feels plain, boring, under-designed, too safe, ugly, weak, or unstyled; and generic, robotic, over-explained, construction-facing, or label-heavy public copy. Apply when art direction, visual systems, content hierarchy, culturally central representation, responsiveness, rendered quality, copy voice, or typography materially matters. Pair with specialist skills for security, SEO, legal, backend, deployment, or compliance.
---

# Design DNA

A website made with this skill copies the front-end design of several
excellent websites and reads as one design. The producer contributes no
design of its own. Two programs do the looking and the measuring; the producer
does the choosing, the planning, the building and the looking-again. A
reference is studied in minutes, a build is checked in a minute or two, and
every claim traces to a record a program wrote or a screenshot a person saw.

The standard is the visitor's experience. Measurements prove provenance and
catch known failure shapes. They never substitute for looking.

## The owner's standing order: no producer design

Motty (MJ's Studio), 2026-09-03, after a build made "as a quick test" shipped
a sticky blurred nav, a typeface pairing chosen by taste, an approximated
palette, numbered cards and a stock accordion that no selected reference
carried:

> "Your own designs is absolutely forbidden because you have terrible taste.
> So even if you think that your design should be on there, don't. Never put
> on your design. ... There is absolutely no using your design. You must only
> use the designs from the websites you are copying from. And this includes
> designs, layouts, fonts, and everything else. Stay out of it."

Mechanically: every part a visitor can see (layout, arrangement, typefaces,
colors, controls, spacing, motion, dividers, footers, navigation, cards, marks)
traces to a studied reference's sheet, or it is cut. Typefaces are the
references' own families, self-hosted where the license allows; otherwise the
face is measured on the live reference with `scripts/measure_faces.mjs` and
the top-ranked open-licence face from `scripts/match_typeface.mjs --target`
is declared in the plan as a match. The producer never picks a face, a
palette, or a layout for beauty, brand fit, or "reads as right".

Owner directive, 2026-09-06: research for a site takes minutes, not hours,
and nothing in this skill may make one producer's work block another's on the
same machine. There are no machine-wide slots, leases, state contracts or
censuses.

Owner directive, 2026-09-07: the tools launch the installed Google Chrome,
never automatically Edge or Playwright's bundled "Chrome for Testing", which froze his
machine; `playwright_resolver.mjs` refuses the bundled build unless the owner
sets `DESIGN_DNA_ALLOW_BUNDLED_CHROMIUM=1` himself for a run. One study or
check runs at a time on a machine. Parallel launches are not speed; they are
the freeze.

Owner directive, 2026-09-06, after the Crossing Law rejection: passing
measurements never substitute for visual quality. A build whose fonts, colors
and mechanisms all trace to references and which still looks poor is a poor
build, and the report says so first.

## The workflow

Four steps. Steps 1 and 4 are programs whose output is quoted, never
paraphrased. Step 2 is the only place the producer authors anything, and it
is a selection. Step 3 has a mandatory early look before the whole site is
built.

### 1. Find, judge, study

**Finding.** Candidates come only from sources the registry marks `award` or
`curated` in
[`references/quality/public-reference-sources.json`](references/quality/public-reference-sources.json);
a listing on an open submission feed means someone sent it in. Before
studying, resolve eligibility: load the gallery, confirm the site is listed
there today, and record the listing URL as `source_url`. If the registry is
stale (a gallery moved domain, a status is wrong), correct the registry entry
with a dated `corrections` note and the evidence, then continue. A registry
fault is never the principal problem with a build; it is the least of its
problems.

**Judging.** A gallery listing establishes where a site was found. It does not
establish that the site is good or that it suits this project. Open every
serious candidate at desktop and phone width and decide, with your own eyes:

- Desktop experience: does it read as one considered design, or a template?
- Mobile experience: does the phone layout survive, or collapse into a stack?
- Readability: type sizes, contrast, line lengths, text over photographs.
- Navigation: can a visitor find and do things without hunting?
- Reliability: does it load, at both widths, without an overlay covering it?
- Suitability: do its design relationships fit this project's content and the
  visitor's tasks? Unrelated industries are fine; a florist can be the
  dominant grammar for a care organization. A loud retail site cannot be the
  grammar for a quiet one.

Write these six judgments into the plan for every selected reference. If you
cannot write them honestly, the site is not selected. Drop thin, dated, ugly,
broken or unsuitable sites on sight and keep looking.

**Studying.**

```
node <skill>/scripts/study_reference.mjs --url <URL> --id <slug> --out .design-dna/references [--inner 3]
```

It writes `.design-dna/references/<slug>/sheet.md` and `study.json`, a
25-second real-time scroll-through video and an eight-frame contact sheet per
width, first screens, and up to three inner pages. The sheet holds the fonts
and where they load from, the type scale, the visible ground by sampling (an
`elementFromPoint` grid at ten scroll positions, so overlapping layers cannot
double count; the older stacked-rectangle figure is kept and labeled an
estimate), radii, shadows, controls, transitions, keyframes, libraries, the
layout outline, what the page does as it scrolls, and for each mechanism its
driver: `scroll` (changes with the wheel), `time` (changes on its own, an
autoplay or ambient loop) or `pointer`. An autoplay video and a scroll-gated
slideshow both say "swap"; they are different experiences, and the build
copies the one the reference has.

The study handles a consent overlay only through a permitted choice (reject,
decline, necessary-only, close). It never accepts terms for the visitor. If
only "accept" is offered, the overlay stays and the sheet says the capture is
obstructed.

**A successful capture is not an adequate study.** The sheet ends with three
sections you must read: *Studied* (which pages loaded, at which width, how
far the wheel went, how many controls were hovered), *Observation gaps*
(consent overlay not dismissed, a fixed layer covering the page, scroll frames
that repeat because the page never travelled, a horizontal scroller the
vertical pass never traversed, an inner page that failed) and *Not studied*
(menus never opened, videos not watched, forms, iframes, pages beyond the
inner three). Anything you intend to copy from a gapped region you inspect
yourself first, by an appropriate method (open the menu, traverse the strip,
read an inner page), and you say in the plan how you did (`gaps_reviewed`).
A gap you did not close is a thing you cannot copy.

**The signature.** For each selected site write one sentence with a verb
saying what a stranger would notice: what creates its impact, composition,
imagery, typography, sequence, interaction, pacing. Name the mechanism only
if the sheet measured it on that site.

### 2. Plan (a selection, written down)

Before completing the plan, read
[Signature transfer](references/quality/signature-transfer.md). Each substantial
reference now binds a measured source region and its defining static or
interactive experience to a build section. Use `study_reference.mjs --region`
for the chosen source region, then `check_build.mjs --plan-only` before building.
The JSON below shows the base fields; the linked guide supplies the required
`signature_spec`, `signature_from`, `signature_transfer`, `source_region`, `system_sections`
and review fields. Existing ingredient-only plans need an actual review and
re-study, not automatically filled declarations.

Write `.design-dna/plan.json`. Every field below is read by the check.

```json
{
  "references": [
    { "id": "strong-1", "url": "https://...", "source_id": "awwwards", "source_url": "https://www.awwwards.com/sites/...",
      "quality": { "desktop": "...", "mobile": "...", "readability": "...", "navigation": "...", "reliability": "...", "suitability": "..." },
      "contributes": "the dominant grammar: first screen, ground, type system, footer",
      "signature": "the product images slide sideways under a pinned heading",
      "signature_mechanisms": ["pinned", "travel"],
      "gaps_reviewed": "the horizontal strip was traversed by hand at both widths; nothing from the obstructed footer was copied" }
  ],
  "typefaces": [ { "family": "Fraunces", "from": "strong-1" },
                 { "family": "Instrument Serif", "from": "strong-2", "matched_for": "Cardinal Fruit", "match_record": ".design-dna/typeface-match.json" } ],
  "ground": { "color": "rgb(14, 14, 14)", "from": "strong-1" },
  "routes": [ { "url": "http://127.0.0.1:4870/", "name": "home", "dominant": "strong-1",
    "sections": [
      { "selector": ".hero", "reference": "strong-1",
        "content": "name, four nav items, one photograph, the hotline",
        "composition": "split screen: green panel left with a vertical nav, full-bleed photo right, wordmark straddling the split",
        "image_role": "the right half is a full-bleed still life; the inset is a tight portrait",
        "typography_role": "wordmark in the display serif; uppercase tracked labels in the text face",
        "behavior": "none",
        "mobile": "one column: hamburger, centered wordmark, ring button; photo below" },
      { "selector": ".stage", "reference": "strong-3", "behavior": "pinned; swap (scroll-driven)", "behavior_narrow": "pinned", "states": 4,
        "palette_from": "strong-1", "behavior_from": "strong-3",
        "content": "...", "composition": "...", "image_role": "...", "typography_role": "...", "mobile": "..." } ] } ],
  "review": { "reviewer": "independent", "file": ".design-dna/review.md" }
}
```

Rules, all checked:

- Every `id` is a studied reference, studied successfully at both widths, not
  an HTTP error page, from a registry source marked award or curated, with a
  `source_url` on that source's domain. At least four distinct references from
  at least two sources. **Four is a floor, not a quota: a weak fourth chosen
  to reach four is forbidden.** If the set does not work, keep researching.
  Every selected reference must reach at least one section as its composition
  `reference` or as `behavior_from` for a measured promised behavior. A
  `palette_from` citation alone is filler.
- `quality` carries the six judgments; `contributes` names what the site gives
  this build; `gaps_reviewed` says how any observation gap was closed.
  For each gap also supply `gap_reviews`: an array with its exact `code`,
  `page`, `viewport`, the inspection `method`, what was `observed`, and
  `artifacts: [{"file":"path/to/capture.png","sha256":"..."}]`.
  Use actual screenshots or video of that inspection. The checker verifies
  the files and hashes; the reviewer must judge what those captures show.
  Also distinguish `disposition: "inspected"` from `"excluded"`. An exclusion
  that removes the selected signature disqualifies that contribution. The
  original obstructed screenshot cannot establish a new inspection.
- At most two typefaces, each computed by a selected reference or declared
  with `matched_for` and a `match_record` that ranks it first. A typed claim
  is not a match.
- The ground is a selected reference's dominant visible ground, sampled.
- Every route lists its major sections. Each section names the reference it
  copies and explains the relationship: `content` (what goes in it),
  `composition`, `image_role`, `typography_role`, `behavior` (mechanisms and
  their driver, or `none`), `mobile` (how it recomposes), and, when it holds
  still while the visitor scrolls, `states` (how many things the visitor sees
  while it holds). `behavior_narrow` when the phone behavior differs;
  `palette_from` or `behavior_from` when a color or a behavior comes from a
  different selected reference than the composition. A font or color that
  appears somewhere in the set does not authorize its use everywhere: a
  section may use only what its own reference or the route's dominant
  reference computes.
- Adapt proportions to the content. Copy the reference's relationships, not
  its pixel heights or scroll distances. Short copy does not inherit a tall
  container; three brief topics do not earn thousands of pixels of scrolling.
  About one viewport per state is the most a held section may ask for.
- When a reference cannot carry this project's content, accessibility or
  phone behavior, take another studied pattern from the set. Never fill the
  gap with an invented design, and never reproduce a source's usability
  defect (2.9:1 text, a tiny label, a menu that hides the nav) because it is
  measurable.

### 3. Build, with an early look

Build the first route's opening and its first major transition, serve it,
and run the early look before building the rest:

```
node <skill>/scripts/check_build.mjs --plan .design-dna/plan.json --studies .design-dna/references --out .design-dna/check --early
```

It prints `EARLY LOOK: <png>`: the dominant reference's first screens beside
the build's at both widths and both scroll storyboards. Look at it. Judge
hierarchy, density, crop, legibility, pacing, and whether the reference's
impression comes through. Fix the opening before there is a whole site to
fix.

Then build the routes. Content is the client's; design is the references'.
Copy the mechanism the reference has, with its driver. Public copy carries no
design narration, no repeated demo disclaimers, no generic slogans, no filler.
Imagery matches the reference's compositional role (a full-bleed still life
where the reference has one), not merely its subject. A fictional or
illustrative disclosure appears once, quietly, where a footer note goes.
Decorative numbers, arrows on things that are not clickable, eyebrows above
headings and em dashes are forbidden by the owner's standing feedback.

A held section (a pinned stage, a sticky hero) never shows the visitor an
empty frame. Copy the reference's timing, not its label: on the Surfer's
Journal the next cover is already rising while the last one leaves, and the
final cover stays put until the stage lets go. A stage whose card has left
before the hold ends, or whose next card has not arrived, is a bare colored
screen with a word in the corner (the Menucha stage did exactly this on
2026-09-07 and the owner saw it). Scrub through every held section slowly at
both widths before calling it built.

### 4. Check, review, report

```
node <skill>/scripts/check_build.mjs --plan .design-dna/plan.json --studies .design-dna/references --out .design-dna/check
```

Every run lands in `.design-dna/check/runs/<timestamp>/` with its frames,
video, review sheet and `check.json`; the latest copies sit at the root. The
failure history survives. The check prints five lines; quote all five
verbatim in the report:

- `CHECK PASS (automated)` or `CHECK FAIL (automated)`: the measurable
  comparisons. Inputs complete (route, four distinct references studied at
  both widths from two sources, quality judgments, contributions, gaps
  reviewed); typefaces from references or verified match records; the
  sampled dominant ground a reference's own, at both widths; every listed
  section present, explained, using only its own or the dominant reference's
  families and grounds, carrying the behavior the plan names *inside that
  section at that width*; no held section asking more than about a viewport
  per state; no tall, near-empty section; no mostly empty page; no photograph
  used twice (a small header/footer home-link identity pair is recorded separately);
  no em dash, eyebrow, padded number, stray arrow, repeated
  disclaimer, design narration or slogan in public copy; no scroll stop (half a
  viewport apart across the page, a twentieth inside held sections, measured
  through the stacking order) where the visitor sees almost nothing; no slop
  shape.
  Problems are listed design first and registry last. Route-level mechanism
  counts and coverage percentages are no longer floors; behavior is tested
  per section and per width, never pooled across the page.
  Its driver must also match the named behavior reference at that width.
  If an older study has no driver, re-study the intended behavior. A promised
  hover is probed inside its own section, including on narrow layouts when
  explicitly promised there; use `behavior_narrow: "none"` when appropriate.
- `FUNCTIONAL PASS` or `FUNCTIONAL FAIL`: keyboard focus visible on the first
  controls, content present with reduced motion, no fixed layer covering the
  page at rest, no sideways scroll, at both widths.
  Missing route/width coverage fails. Functional failures return a nonzero
  command exit status even when the separate design comparisons pass.
- `REVIEW INDEPENDENT`, `REVIEW SELF-REVIEW` or `REVIEW MISSING`: whether a
  review was written, by whom, what it covers and what it leaves unresolved.
  `REVIEW FAIL` means a signature is missing/unverified, its paired captures
  are absent, or a material issue remains. It fails the final command even
  when automated ingredient comparisons pass. Generic primary fonts are
  checked for source authorization too; fallback lists are not a design licence.
- `EVIDENCE`: the tool revisions that made the studies and this check, and
  which studies are older than the current study tool.
- `APPROVAL`: owner approval, recorded in the plan or not.

**The review.** Where an independent reviewer is available (a fresh agent, a
second session, a person), give it the brief, the reference sheets and
contact sheets, and `review-<n>-<route>.png`, without the builder's
explanation, and have it write `.design-dna/review.md`. Otherwise the builder
writes it and the first line says `Reviewer: self`. The file has:

```
Reviewer: independent (or: self)
- <reference id>: reference shows ... / build shows ... / difference: ...   (one line per selected reference)
## Visitor walk
menus, reading flow, horizontal interactions, keyboard navigation, focus visibility, moving content, overlays, reduced motion, mobile layouts, settled states after load
## Unresolved
- ...
```

The visitor walk is done, not imagined: open the menus at both widths,
traverse anything horizontal, tab through the page, load it with reduced
motion, look at it settled four seconds after load, and say what you saw. A
correctly formatted review proves that a review was written; it does not
prove the design is good.

**The report** separates four things and never blends them: the automated
lines, the review's findings including unresolved differences, the functional
line, and owner approval. Material problems are stated first and plainly.
"Fonts and colors passed" never becomes "the site is ready". A known weak or
rejected result is never described favorably because a metric improved.

## What a report contains

- The references, each with URL, source and listing URL, the six quality
  judgments, its signature, what it contributes, its observation gaps and how
  they were closed, and the paths to its sheet and contact sheets.
- The plan file and the review file, with the review sheet path.
- The five check lines, verbatim.
- Problems the tools reported (`problems` and `observation_gaps` in
  study.json; `problems` and `functional_problems` in check.json), not
  summarized away.
- What was not verified, in one plain sentence.

## Reference selection is by design, not by industry

Pick references from any genre for their design relationships and never for
the client's industry. Six faithful copies of forgettable sites make a
forgettable site. When a client names another client's site, copy its
structure and register, never its copy or claims.

## Other standing rules that still apply

- Nothing fabricated: no invented reviews, numbers, credentials, clients, or
  awards. Omit an absence, never advertise it.
- No em dashes; American spelling; the studio's copy voice.
- Load every outbound link before presenting.
- Assurance boundaries (truth, rights, privacy, access, working behavior,
  evidence honesty, delivery authority) in [policy/absolutes.md](policy/absolutes.md)
  come first. The owner record at `~/.design-dna/owner-standards.md` is read
  before direction exists; it closes only the ingredients it names.

## What the tools prove, and what they cannot

The study proves what a site's DOM computed and how its elements moved under
a wheel, a pointer and time, at two widths, on the day it ran. The check
proves that a build's visible ingredients trace to those records, that the
behaviors named for each section exist in that section, that known failure
shapes are absent, and that a keyboard and a reduced-motion visitor are not
locked out. Neither proves that the composition is right, that the crop is
good, that the pacing feels earned, or that the reference's impression comes
through. Those are seen or they are not, and the report says which.

## Legacy machinery

The 12.0.0 audit machinery (observe_reference, record_reference, gate.py,
state contracts, route manifests, censuses, the source-study controller and
its machine-wide leases) remains in `scripts/` for anyone who needs its
records, documented in
[references/legacy/SKILL-12.1-machinery.md](references/legacy/SKILL-12.1-machinery.md).
It is not part of this workflow and nothing in this workflow depends on it.
