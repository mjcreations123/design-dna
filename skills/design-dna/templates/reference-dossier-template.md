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

| Rank | Reference title or visible entry | Public URL or gallery-entry URL | Discovery source and accolade | Retrieval date | Access status | Capture path and SHA-256 | Observed evidence | Measured styles | Signature (what a stranger would name) | Brief relevance | Design to copy | Rights boundary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 |  |  |  |  | public-live / public-gallery-entry / authorized-account |  | motion / static; path plus sha256:<hex> |  |  |  |  |  |
| 2 |  |  |  |  | public-live / public-gallery-entry / authorized-account |  | motion / static; path plus sha256:<hex> |  |  |  |  |  |
| 3 |  |  |  |  | public-live / public-gallery-entry / authorized-account |  | motion / static; path plus sha256:<hex> |  |  |  |  |  |
| 4 |  |  |  |  | public-live / public-gallery-entry / authorized-account |  | motion / static; path plus sha256:<hex> |  |  |  |  |  |
| 5 |  |  |  |  | public-live / public-gallery-entry / authorized-account |  | motion / static; path plus sha256:<hex> |  |  |  |  |  |
| 6 |  |  |  |  | public-live / public-gallery-entry / authorized-account |  | motion / static; path plus sha256:<hex> |  |  |  |  |  |

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

| Reference title or visible entry | Public URL or gallery-entry URL | Discovery source and accolade | Retrieval date | Access status | Capture path and SHA-256 | Observed mismatch or weak relationship | What this project must avoid |
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
- Combination of references (which reference supplies which part, and why no
  single one of them is this build):
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

## Sequence reads

One block per selected reference. The reference was RECORDED, the recording
was reduced to the moments where the screen changed, and every one of those
events was narrated before the strong row was written. The validator counts:
a line per event, an inventory of what the site does, and a signature located
on events that exist.

### strong-1
- Recording: .design-dna/references/strong-1-recording.json plus sha256:<hex>
- Read: .design-dna/references/strong-1-sequence-read.md plus sha256:<hex>
- Signature events: e004, e005

Produce the recording with the packaged recorder, which drives a real cursor
over every interactive thing on the first screen, scrolls in steps hovering
what arrives, follows one internal link so the page transition and an inner
page are on tape, then differences the video and keeps one four-frame sheet
per event (a hover, click or scroll step that changed something, a run of
quiet travel, a change the page made on its own):

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/record_reference.mjs" \
  --url "https://example.test/" --id strong-1 --out .design-dna/references
```

Then open `strong-1-events/` and write `strong-1-sequence-read.md` by hand:
one line per event, `- e001 (0.3s, load): ...`, saying what the cursor did,
what scrolled and what changed, followed by a `## Behaviour inventory` table
(trigger, element, effect, magnitude, events) of at least eight rows; the
recorder's `strong-1-events.md` is its skeleton. The inventory is what the
build reproduces.

This step is here because three instruments in a row let the producer say it
had watched a site without looking. The last one recorded a reference's
mechanisms as numbers; the producer read the numbers, opened one rest frame of
forty-one, and built a photograph inside a dotted line. The owner recorded
himself using the site for a minute and the producer, walking that recording
at ten frames a second, found nineteen behaviours it had never seen. A script
cannot make you understand what you see. It can make sure you saw it.

## Signature transfer

One row per selected reference. This is the last gate and the only one that
asks WHICH PART of each reference arrived.

| Rank | Signature, copied from the strong row | The build part that carries it | Recorded proof | What a stranger would lose if this reference were cut |
| --- | --- | --- | --- | --- |
|  |  |  | path plus sha256:<hex> |  |

Every gate before this one proves the producer looked at the reference,
measured it, and cited it. None of them asks which part of it reached the
page. Six references were researched for one build, every gate passed, and two
of them arrived as a background colour and a set of control dimensions,
because those are the parts a producer is most comfortable rebuilding and a
source line does not record which part it meant. The owner's words:
"you still took the crack in the sidewalk instead of the waterfall."

`Signature, copied from the strong row` is copied, not summarised. The
validator checks it against the strong row, because a signature that changes
on its way down the record is a signature being refitted to whatever got
built.

`Recorded proof` binds the `scripts/check_signature_transfer.mjs` record, or
the mechanism or structure diff that shows this signature arriving. Run the
transfer check before writing these rows:

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/check_signature_transfer.mjs"   --dossier .design-dna/reference-dossier.md   --observation .design-dna/references/strong-1-observation.json   --out .design-dna/evidence/signature-transfer.json
```

It reads each reference's mechanisms in the order the harness ranked them and
refuses a signature that names something other than the loudest thing that
site does. A site's buttons really do change colour under the pointer; that is
a small true thing written down in place of the large one, and a reference
described by a small true thing contributes a small true thing.

`What a stranger would lose if this reference were cut` is the deletion test,
and it is the one cell no script can fill. Cover the reference's row and ask
what visibly goes. The answer must name a component the build actually ships,
because a loss nobody can point at is not a loss, and it must name an
arrangement or a behaviour: a ground, a radius, a size or a control dimension
is what survives when a reference was sampled rather than copied. If the
honest answer is "nothing anyone would name", that reference was not selected,
it was listed. Cut it or take its signature properly.

## Component sources

Every part that ships has a source line, or it is the producer's own design,
which needs the owner's permission in the owner's words. This is where the
rejected builds came from: the references supplied one scroll effect and the
producer supplied the nav, the buttons, the list rows and the footer from
memory, and memory is the generic skeleton every time.

- Component census: __REPLACE_WITH_DESIGN_DNA_EVIDENCE_COMPONENT_CENSUS_JSON_PLUS_SHA256__

| Component | Source rank or owner approval | Frame that shows it | Structure taken | Recorded values reproduced | Where it is used |
| --- | --- | --- | --- | --- | --- |
| first screen |  | strong-N-events/eNNN-kind.png |  |  |  |
| layout grid |  |  |  |  |  |
| display typeface |  |  |  |  |  |
| text typeface |  |  |  |  |  |
| color behavior |  |  |  |  |  |
| section rhythm |  |  |  |  |  |
| navigation |  |  |  |  |  |
| buttons |  |  |  |  |  |
| rows or lists |  |  |  |  |  |
| footer |  |  |  |  |  |
| scroll behavior |  |  |  |  |  |
| hover behavior |  |  |  |  |  |

`Component census` binds the `scripts/scan_build_components.mjs` record for
the finished build. It counts every component the build actually renders, and
the gate requires a row for each one. The twelve rows below are a floor, not
the list: a build that satisfied all twelve and also shipped a lede block, a
photo plate, a numbered list, a form and a footer with no rows between them is
exactly the failure this closes.

`Recorded values reproduced` is checked against the reference's measured
styles. Every number in the cell has to be a number that reference actually
computes, and a cell with fewer than three numbers in it is refused. This is
what a build made from a screenshot cannot survive: a still carries a caption
alignment, a radius and a colour impression, and the producer fills in the
rest from memory while believing it is copying.

`Recorded values reproduced` is checked against the reference's measured
styles. Every number in the cell has to be a number that reference actually
computes, and a cell with fewer than three numbers in it is refused. This is
what a build made from a screenshot cannot survive: a still carries a caption
alignment, a radius and a colour impression, and the producer fills in the
rest from memory while believing it is copying.

`Recorded values reproduced` is checked against the reference's measured
styles. Every number in the cell has to be a number that reference actually
computes, and a cell with fewer than three numbers in it is refused. This is
what a build made from a screenshot cannot survive: a still carries a caption
alignment, a radius and a colour impression, and the producer fills in the
rest from memory while believing it is copying.

`Frame that shows it` names the capture that shows this part, relative to the
reference captures directory, for example
`strong-4-frames/strong-4-006-scroll-settle.png`. The validator opens it. A
source line nobody can follow is not a source line: a producer once wrote
`footer <- index-space.org: a plain block, no rules` for a footer it had never
opened, because the table asked for a source and prose is free. If the frame
does not exist, go and observe the page that shows the part, or cut the
component.

`Source rank or owner approval` is a selected rank, or
`owner-approved: "<the owner's actual words>"`. An owner-approved row writes
`owner-approved` in the frame column, because the producer's own design has no
reference frame to cite. The two typeface rows may not
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
