---
name: design-dna
description: Builds, redesigns, polishes, and visually reviews specific, current, non-generic websites and web UIs using only qualified measured references and approved project authority—never producer-authored visible design. Use for landing pages, multi-page sites, place/community publications, hospitality, ecommerce, portfolios, editorial sites, dashboards, product interfaces, documentation, and components; requests avoiding AI-looking, vibe-coded, templated, cookie-cutter, dated, or time-incongruent design; feedback that work feels plain, boring, under-designed, too safe, ugly, weak, or unstyled; and generic, robotic, over-explained, construction-facing, or label-heavy public copy. Apply when art direction, visual systems, content hierarchy, culturally central representation, responsiveness, rendered quality, copy voice, or typography materially matters. Pair with specialist skills for security, SEO, legal, backend, deployment, or compliance.
---

# Design DNA

A website made with this skill copies the front-end design of several
excellent websites and reads as one design. The producer contributes no
design of its own. Two programs do the looking and the checking; the producer
does the choosing, the planning and the building. A rich reference is studied
in minutes, a site is checked in a minute, and every claim traces to a record
the programs wrote.

## The owner's standing order: no producer design

This is the publisher's own dated rule and it outranks every other aesthetic
instruction here. Motty (MJ's Studio), 2026-09-03, after a build made "as a
quick test" shipped a sticky blurred nav, a typeface pairing chosen by taste,
an approximated palette, numbered cards and a stock accordion that no selected
reference carried, and after the same thing had happened, in his count, about
twenty times before:

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

Owner directive, 2026-09-06: the research for a site takes minutes, not
hours, and nothing in this skill is allowed to make one producer's work block
another's on the same machine. There are no machine-wide slots, leases, state
contracts, or censuses in this workflow.

## The workflow

Four steps, in order. Steps 1 and 4 are programs and their output is quoted,
never paraphrased or reconstructed.

### 1. Study each reference (a few minutes each)

Select candidates QUALITY FIRST and register second, only from sources the
registry marks `award` or `curated` in
[`references/quality/public-reference-sources.json`](references/quality/public-reference-sources.json).
A listing on an open submission feed means someone sent it in, not that it is
good. Judge every candidate with your own eyes on its live page before
studying it, and drop a thin, dated or ugly site on sight. Never judge a site
from a still. Record what each selected site won or why its source's editor
chose it; a source you cannot verify is dropped, not footnoted.

Study every serious candidate:

```
node <skill>/scripts/study_reference.mjs --url <URL> --id <slug> --out .design-dna/references [--inner 3]
```

It writes `.design-dna/references/<slug>/sheet.md` and `study.json`, a
25-second real-time scroll-through video per width, an eight-frame contact
sheet per width, first screens, and up to three inner pages from the site's
own navigation. The sheet holds the site's fonts and where they load from, its
type scale, its colors weighted by painted area (the dominant ground is a
measurement), radii, shadows, controls, transitions, keyframes, animation
libraries, the layout outline, what the page does as it scrolls (pinned,
travelling, swapping, revealing, parallax, pointer-follow), what the Web
Animations API is running at six depths, and which controls respond to the
pointer.

Then LOOK: open both contact sheets and the first screens with your own eyes
and read the sheet. Answer one question per site and write it down with a
verb: if a stranger were shown this site, what would they say they noticed?
That is the signature. If it names a subject, a palette or a mood, it is not
a signature. The sheet's "signature candidates" list what the tool measured;
your sentence must name something on it, or something the frames show (a
typographic composition, a photographic treatment, a color relationship).

Floors, which are floors and not targets: at least four selected references
from at least two sources, at least one of them with real scroll or pointer
motion, and at least two inner pages observed across the set. Six candidates
studied for four selected is normal. A site the tool could not read
(`ok: false` in its summary) is not selected.

### 2. Plan (the producer's only authorship, and it is a selection)

Write `.design-dna/plan.json`:

```json
{
  "references": [
    { "id": "strong-1", "url": "https://...", "source": "awwwards; site of the day 2026-03-02",
      "signature": "the product images slide sideways under a pinned heading",
      "signature_mechanisms": ["pinned", "travel"],
      "take": ["first screen composition", "pinned heading with travelling media", "nav", "hover transition 240ms"] }
  ],
  "typefaces": [ { "family": "Fraunces", "from": "strong-1" }, { "family": "Inter", "from": "strong-2", "matched_for": "Neue Haas Grotesk" } ],
  "ground": { "color": "rgb(14, 14, 14)", "from": "strong-1" },
  "routes": [ { "url": "http://127.0.0.1:4870/", "name": "home", "dominant": "strong-1", "mechanisms": ["pinned", "travel", "reveal"] } ]
}
```

Rules for the plan, all checked by step 4:

- Every `id` is a studied reference. Every `signature_mechanisms` entry was
  detected on that site. Every mechanism a route promises exists on a
  studied reference.
- At most two typefaces, each computed by a selected reference, or declared as
  the rank-one match for a reference face that cannot be self-hosted:

  ```
  node <skill>/scripts/measure_faces.mjs --url <reference URL> --family "<Face>" --out .design-dna/references/<id>/faces.json
  node <skill>/scripts/match_typeface.mjs --target .design-dna/references/<id>/faces.json --family "<Face>" --out .design-dna/typeface-match.json
  ```

  The first measures the face as the live page renders it (and refuses a face
  the page only rendered with a fallback); the second measures the open
  candidates the same way and ranks them. `chosen` is the match; the plan
  entry carries `"matched_for"` and the record path.
- The ground is a selected reference's own dominant ground, not a minor
  citation that happens to justify the producer's taste.
- One reference is the dominant grammar of each route: its first-screen
  composition, section rhythm, control language and narrow recomposition.
  Other references contribute their signature moments where the content
  supports them. A build copies inner pages only from references whose inner
  pages were studied.
- Take the GOOD parts and design the site as one thing. A transfer that takes
  only a palette value, a font category, a background or one generic
  animation fails the standard even though it names a source.

### 3. Build

Build the routes the plan names. Content is the client's; design is the
references'. Copy the reference's mechanism, not a label for it: a "swap" that
is an ambient autoplay video on the reference is an autoplay video in the
build, not a scroll-gated slideshow. Sections fading up on scroll are not a
motion language. Decorative numbers, arrows on things that are not clickable,
eyebrows above headings, and mechanism narration in the copy are forbidden by
the owner's standing feedback.

### 4. Check the build (about a minute)

```
node <skill>/scripts/check_build.mjs --plan .design-dna/plan.json --studies .design-dna/references --out .design-dna/check
```

It reads the build with the same eyes as the references and prints one line:
`CHECK PASS ...` or `CHECK FAIL ...`. Quote that line verbatim in the report.
It fails when the build sets text in a family no selected reference computes,
paints a dominant ground no selected reference has, drops a reference's
signature mechanism, promises a mechanism a route does not carry or no
reference has, has fewer mechanisms or less scroll choreography than the
weakest selected reference, ignores the pointer where the references respond
to it, or shows a slop pattern (gradient text, an icon-card triplet near the
top, fade-up as the only motion). A failed check is fixed in the build or the
plan and re-run; it is never argued with in prose. If the check did not run,
the report says "the check did not run".

## What a report contains

- The references, each with URL, source and accolade, signature sentence, and
  the path to its sheet and contact sheets.
- The plan file.
- The check verdict line, verbatim.
- Problems the tools reported (`problems` in study.json, `problems` in
  check.json), not summarized away.

## Reference selection is by design, not by industry

Pick references from any genre for their design and never for the client's
industry. Six faithful copies of forgettable sites make a forgettable site.
When a client names another client's site, copy its structure and register,
never its copy or claims.

## Other standing rules that still apply

- Nothing fabricated: no invented reviews, numbers, credentials, clients, or
  awards. Omit an absence, never advertise it.
- No em dashes; American spelling; the studio's copy voice.
- Load every outbound link before presenting.
- Assurance boundaries (truth, rights, privacy, access, working behavior,
  evidence honesty, delivery authority) in [policy/absolutes.md](policy/absolutes.md)
  come first. The owner record at `~/.design-dna/owner-standards.md` is read
  before direction exists; it closes only the ingredients it names.

## Legacy machinery

The 12.0.0 audit machinery (observe_reference, record_reference, gate.py,
state contracts, route manifests, censuses, the source-study controller and
its machine-wide leases) remains in `scripts/` for anyone who needs its
records, documented in
[references/legacy/SKILL-12.1-machinery.md](references/legacy/SKILL-12.1-machinery.md).
It is not part of this workflow and nothing in this workflow depends on it.
