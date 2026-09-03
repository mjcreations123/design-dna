---
schema_version: 1
created_with: "__DESIGN_DNA_VERSION__"
classification: "internal"
evidence_contract: "proportional-evidence-v1"
record_status: "draft"
---

# Reference dossier

Use this internal record for the required public-reference research before a
fresh Enterprise Candidate website is implemented. It is a project-specific
decision record, not customer-facing copy, a moodboard, an award score, or a
license to reproduce another brand's work.

Every reference row binds a capture you actually looked at. Save captures
under `.design-dna/references/` and bind each one as
`path plus sha256:<64 lowercase hex>`. A row without a capture is a row the
prebuild gate rejects; the capture is the evidence that the research happened.
A strong reference binds full-page wide and narrow stills, which is how
composition and rhythm are read, plus an observation session emitted by the
packaged `observe_reference.mjs` harness, which is the only evidence that
establishes what the site actually does. Run it before writing the row:

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/observe_reference.mjs" \
  --url "https://example.test/" --id strong-1 --out .design-dna/references
```

The `Observed evidence` cell then reads `motion; .design-dna/references/strong-1-observation.json plus sha256:<hex>`
for a site the session saw move, or `static; ...` for one it did not. The
session is schema 3: it carries a mechanism sheet (what held, travelled,
swapped, revealed, parallaxed, followed the pointer, and how long a hover
takes), a score, and the structure of the reference's first screen (what kind
of thing fills it, where the ink sits, what is against each edge and in each
corner, and the proportions of its type). The gate rejects a motion claim the session does not
support, and it rejects a motion row on its own numbers when the site is thin:
fewer than three distinct mechanisms, or scroll choreography on less than half
of its depth. Nobody vets the list; the harness does.

## Research frame

- Brief and priority-source rationale:
- Current active registry audit date and limitations:
- Authorized-account basis, if any; otherwise `none`:
- Public-access disposition for blocked or unavailable sources:
- Source-specific filters, sorts, categories, tags, and queries used with brief reason:
- Plausible alternate discovery paths checked alongside any status-based route:
- Ledger check (prior references reused, with reason, or `none`):

## Strong references

Record at least six references drawn from at least three active sources, with
no single source supplying more than half of the rows. The floor exists so
that no one site becomes the template; it is not a target. Add rows for every
reference that earns its place. Number ranks 1 through N without gaps.

| Rank | Reference title or visible entry | Public URL or gallery-entry URL | Discovery source | Retrieval date | Access status | Capture path and SHA-256 | Observed evidence | Signature (what a stranger would name) | Brief relevance | Design to copy | Rights boundary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 |  |  |  |  | public-live / public-gallery-entry / authorized-account |  | motion / static; path plus sha256:<hex> |  |  |  |  |
| 2 |  |  |  |  | public-live / public-gallery-entry / authorized-account |  | motion / static; path plus sha256:<hex> |  |  |  |  |
| 3 |  |  |  |  | public-live / public-gallery-entry / authorized-account |  | motion / static; path plus sha256:<hex> |  |  |  |  |
| 4 |  |  |  |  | public-live / public-gallery-entry / authorized-account |  | motion / static; path plus sha256:<hex> |  |  |  |  |
| 5 |  |  |  |  | public-live / public-gallery-entry / authorized-account |  | motion / static; path plus sha256:<hex> |  |  |  |  |
| 6 |  |  |  |  | public-live / public-gallery-entry / authorized-account |  | motion / static; path plus sha256:<hex> |  |  |  |  |

The rank reflects fit for this exact brief, not a universal quality score.
Every row's `Signature` cell answers one question first: if a stranger were
shown this site, what would they say they noticed about its design? Write it
as what the site does, with a verb: what holds, travels, swaps, reveals,
follows, transitions. The gate refuses a cell without one, because "warm
domestic object, photography led", "pure black page", "stark white, product
alone" and "one image at a time" were each recorded as a signature by this
skill's producer and each build was rejected: they name the subject, the
palette or the mood, which is the sidewalk and not the falls. A static
signature (a typographic composition, an editorial grid) is still written as
what it does to the reader as they move through it. The `Design to copy` cell then names all the good parts taken from
that reference in concrete terms, behavior first and then the rest (what the
page does as it scrolls, its interaction and transitions, its signature
moment, then media treatment, composition, how its color behaves, its type
posture and scale, shapes and surfaces), and then names the parts left behind
and why. Behavior leads the order because it is what gets forgotten, not
because the rest matters less; a row that records only motion is as
incomplete as one that records only margins. A part
that a thousand strangers would not have noticed is not the takeaway and
does not belong in the cell. The
build uses the brand's own palette and typefaces chosen for beauty; the
reference contributes behavior, composition, and scale, not its values or
family names. The `Rights boundary` cell names only what is not reused: the
reference's logo, name, copy, photographs, illustrations, and code. A gallery
entry is sufficient when it is publicly viewable; a live URL is not required.

## Negative counterexamples

| Reference title or visible entry | Public URL or gallery-entry URL | Discovery source | Retrieval date | Access status | Capture path and SHA-256 | Observed mismatch or weak relationship | What this project must avoid |
| --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  | public-live / public-gallery-entry / authorized-account |  |  |  |
|  |  |  |  | public-live / public-gallery-entry / authorized-account |  |  |  |
|  |  |  |  | public-live / public-gallery-entry / authorized-account |  |  |  |

Describe visible consequences, not a judgment of the creator or why the entry
was curated. These are counterexamples for the current brief, not permanent
style bans.

## Selected synthesis

- Selected positive ranks (at least four distinct, from at least two sources):
- Project-specific organizing synthesis:
- Behavior copied and where it is rendered:
- Negative-counterevidence result:
- Elevation beyond the references (what this build does that none of them do):
- Direction record path and status:

| Selected rank(s) | Design copied and destination | Project-specific adaptation | Boundary or verification |
| --- | --- | --- | --- |
|  |  |  |  |

This table is the design transfer map. Each row names which reference's
front-end design is copied and which route, section, or system role of this
project receives it (first screen, comparison route, product hero, type
system, palette, motion language, phone recomposition). At least three of the
selected ranks must be `motion` rows. At least one row
carries behavior, not only static composition: the `Behavior copied and where
it is rendered` line above names it and the route whose rendered scroll
sequence proves it. Different routes may
take parts from different references, but the site is one design: the
brand's palette, one type system of at most two families chosen for beauty,
one rhythm where each section flows into the next; sections from different
references that change voice at every screen fail the record. The references are the floor for this
project, not its ceiling: the elevation line names where the build goes
further than any of them.

## Component sources

Every part that ships has a source line, or it is the producer's own design,
which needs the owner's permission in the owner's words. This is where the
rejected builds came from: the references supplied one scroll effect and the
producer supplied the nav, the buttons, the list rows and the footer from
memory, and memory is the generic skeleton every time.

| Component | Source rank or owner approval | Structure taken | Recorded values reproduced | Where it is used |
| --- | --- | --- | --- | --- |
| first screen |  |  |  |  |
| layout grid |  |  |  |  |
| display typeface |  |  |  |  |
| text typeface |  |  |  |  |
| color behavior |  |  |  |  |
| section rhythm |  |  |  |  |
| navigation |  |  |  |  |
| buttons |  |  |  |  |
| rows or lists |  |  |  |  |
| footer |  |  |  |  |
| scroll behavior |  |  |  |  |
| hover behavior |  |  |  |  |

`Source rank or owner approval` is a selected rank, or
`owner-approved: "<the owner's actual words>"`. The two typeface rows may not
be owner-approved: a typeface comes from a selected reference, either the same
face where it is freely licensed or one matched to that reference's measured
proportions, because a face chosen by taste is how a build ends up sharing
nothing with any site it researched.

`Structure taken` says how the part is ARRANGED: what fills the first screen,
what sits at which edge, how the space is divided, what is beside what. The
gate rejects a cell that only carries sizes. This column exists because a
producer can reproduce every font size on a reference and still ship its own
layout, and that is exactly what happened: six references researched, and the
only thing that reached the page was one circular button.

`Recorded values reproduced` carries the numbers taken from the source's
mechanism sheet and measured styles (held distances, swap counts, durations,
easings, sizes, weights, tracking), never a paraphrase such as "big type" or
"a nice hover". Add rows for every further component the build has; the twelve
above are the floor.
