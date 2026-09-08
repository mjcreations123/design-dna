---
name: design-dna
description: Builds, redesigns, polishes, and visually reviews specific, current, non-generic websites and web UIs using only qualified measured references and approved project authority—never producer-authored visible design. Use for landing pages, multi-page sites, place/community publications, hospitality, ecommerce, portfolios, editorial sites, dashboards, product interfaces, documentation, and components; requests avoiding AI-looking, vibe-coded, templated, cookie-cutter, dated, or time-incongruent design; feedback that work feels plain, boring, under-designed, too safe, ugly, weak, or unstyled; and generic, robotic, over-explained, construction-facing, or label-heavy public copy. Apply when art direction, visual systems, content hierarchy, culturally central representation, responsiveness, rendered quality, copy voice, or typography materially matters. Pair with specialist skills for security, SEO, legal, backend, deployment, or compliance.
---

# Design DNA

A website made with this skill copies the front-end design of several
excellent websites and reads as one design. The producer contributes no
design of its own. The producer researches ten suitable websites; the user
chooses the parts to use. The producer records those choices, measures,
implements and checks them without making additional design selections. A
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
sets `DESIGN_DNA_ALLOW_BUNDLED_CHROMIUM=1` himself for a run.
Later clarification on 2026-09-07: concurrent regular-Chrome work is permitted;
open task-owned tabs and do not wait for exclusive use of the machine's browser.
Do not close or control another task's tabs or processes. The restriction is
against Chrome for Testing, not a limit on active projects or regular-Chrome tabs.

Owner directive, 2026-09-06, after the Crossing Law rejection: passing
measurements never substitute for visual quality. A build whose fonts, colors
and mechanisms all trace to references and which still looks poor is a poor
build, and the report says so first.

## The workflow

Owner-directed selection (Motty, 2026-09-08) supersedes earlier autonomous
selection, reference-count floors, source-spread quotas and motion quotas.
Research → present ten → wait for the user's part-by-part choices → measure
and plan those choices → build → check. No design or website slice is built
before the user selects the parts. A request to build, hurry or test is not
permission to skip that pause.

### 1. Research and present ten; then stop for the user

Find exactly ten distinct websites whose OVERALL designs would suit this
project's audience, content and visitor tasks. They need not share its industry:
a plumbing website may suit a doctor's office. Do not choose a weak overall
site merely because it has one attractive button or easy-to-copy effect.

Inspect the current sites, including relevant page progression and phone
layouts. Present a numbered list of ten with working direct links, names,
concise project-specific overall-fit reasons and accessible visual previews
where available. Label access or inspection limitations honestly; replace
uninspectable candidates instead of filling the ten with unverified claims.

Then STOP. The user reviews the ten and says which parts to take from each,
or asks for more websites. Supply additional candidates when requested; do not
quietly replace the original list, automatically select a subset, choose a
dominant design, combine treatments, scaffold the website or build a proof.
Numbering this research list is functional and not decorative website copy.

After the user replies, preserve their actual instructions in the existing
plan's `owner_selection` (see the signature-transfer guide). A general positive
reaction to the list is not a part-by-part selection. Ask concise questions
about uncovered visible decisions; do not invent a navigation, footer, color,
typeface, mobile treatment or transition to fill a gap. If the user chooses a
whole site's design for a named scope, that supplies authority for that scope;
do not require them to approve every pixel separately. Existing explicit choices
remain valid within their scope. New or replacement visible choices return to
the user. Selection approval is not final website or deployment approval.

### Research and study methods

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

**Studying, in two phases.** First a quick look at every serious candidate,
then the full study of the parts the USER selects. Do not perform full transfer
studies or decide what to copy before the user's selection.

```
node <skill>/scripts/study_reference.mjs --url <URL> --id <slug> --out .design-dna/references --quick
node <skill>/scripts/candidates_sheet.mjs --studies .design-dna/references --out .design-dna/candidates.png
```

A quick look takes about a minute: the home page at both widths, its fonts
and where they load from, the visible ground by sampling, the layout outline,
the scroll mechanisms with their drivers, and an eight-second storyboard. The
candidates sheet tiles every look into one image, desktop beside phone beside
storyboard with a measured caption; use it to help the user review the ten.
A quick look supports candidate presentation, not implementation evidence;
the check refuses one as a fully studied implementation reference.

```
node <skill>/scripts/study_reference.mjs --url <URL> --id <slug> --out .design-dna/references --region SEL [--region SEL2] [--inner 1] [--inner-widths both]
```

The full study of a selected reference takes two to four minutes: everything
above plus the hover probe, Web Animations at six depths, a 25-second
recording per width, the source regions you intend to transfer (name their
selectors from the quick look's layout outline), and one inner page at
desktop width (`--inner 0` for a one-page build; `--inner 3 --inner-widths
both` only for the dominant reference of a multi-page build).

The first presentation contains ten candidates, but the number of sources
actually used is determined by the user's choices. Do not force four sources,
two galleries, or animation into those choices. Fully study each selected
transfer at both widths and relevant inner pages. A failed study is not evidence;
explain the obstacle and ask before substituting a different design or source.

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

**The selected part.** For each user-selected contribution write one sentence with a verb
saying what a stranger would notice: what creates its impact, composition,
imagery, typography, sequence, interaction, pacing. Name the mechanism only
if the sheet measured it on that site. Its signature_spec describes the part
the user chose, not an unrelated grand feature the producer wants to add.

### 2. Plan (the user's selections, written down)

Before completing the plan, read
[Signature transfer](references/quality/signature-transfer.md). Each substantial
reference now binds a measured source region and its defining static or
interactive experience to a build section. Use `study_reference.mjs --region`
for the chosen source region, then `check_build.mjs --plan-only` before building.
The JSON below shows the base fields; the linked guide supplies the required
`signature_spec`, `signature_from`, `signature_transfer`, `source_region`, `system_sections`
and review fields. Existing ingredient-only plans need an actual review and
re-study, not automatically filled declarations.

Only after user selection, optionally scaffold the measurable half, then
replace suggestions with the actual user-authorized choices:

```
node <skill>/scripts/plan_scaffold.mjs --studies .design-dna/references --select a,b,c,d --dominant a --route http://127.0.0.1:4870/ --out .design-dna/plan.json
```

It fills ids, urls, detected mechanisms, the two most-set families with
their sources (a commercial face comes back as a `matched_for` stub), the
dominant reference's sampled ground, the gaps to acknowledge, a
`signature_spec` per reference built from the regions the study captured,
and one section stub per captured region. These are mechanical suggestions,
not permission to choose fonts, source parts or layouts. Remove unselected
suggestions and ask about uncovered choices. Every field you must write says
TODO, and the check refuses a plan that still says TODO anywhere.

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
  `source_url` on that source's domain. Use only the user's selected sources
  and parts; there is no minimum number of sources used beyond one.
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
- Typefaces follow the user's selected treatments, each computed by a selected reference or declared
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
  phone behavior, explain the conflict and ask the user which alternative to
  use, even if another studied pattern is available. Never fill the
  gap with an invented design, and never reproduce a source's usability
  defect (2.9:1 text, a tiny label, a menu that hides the nav) because it is
  measurable.

### 3. Build, with an early look

After the user has selected the relevant parts, build the first route's opening
and its first major transition, serve it,
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
  comparisons. Inputs complete (route, recorded user selections, selected references studied at
  both widths, none of them a quick look, quality judgments,
  contributions, gaps reviewed, no TODO left in the plan); typefaces from references or verified match records; the
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

## The clock

Keep research proportionate and give useful progress updates. Present the ten
before full transfer studies. Waiting for the user's selection is intentional,
not a blocker to bypass. Elapsed time never authorizes choosing for the user.
Additional candidates are researched when the user requests them.

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
