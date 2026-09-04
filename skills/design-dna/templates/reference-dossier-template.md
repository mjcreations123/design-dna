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

## Contents

- [Research frame](#research-frame)
- [Candidate comparison](#candidate-comparison)
- [Strong references](#strong-references)
- [Interaction census](#interaction-census)
- [Negative counterexamples](#negative-counterexamples)
- [Selected synthesis](#selected-synthesis)
- [Route manifest](#route-manifest)
- [Preimplementation visible decisions](#preimplementation-visible-decisions)
- [Sequence reads](#sequence-reads)
- [Signature transfer](#signature-transfer)
- [Component sources](#component-sources)

Time, tokens, cost, convenience, or a demo/small/quick/hurry label may reduce
delivered scope only. They cannot reduce any reference count, qualification,
traversal, 90-second/15-fps recording floor, wide/narrow evidence, proof, or
gate below. An unavailable required capability blocks the affected candidate;
do not hand-write a generated-record substitute or justify an existing build
after the fact.

Every serious candidate and strong reference binds distinct full-page wide and
narrow captures you actually inspected. Save them under
`.design-dna/references/` and bind each as `path plus sha256:<64 lowercase
hex>`. One file reused for both viewport classes is invalid. The pair is how
composition, rhythm, responsive transformation, and static signatures are
read. For accessible live sources, also bind an observation session emitted by
the packaged `observe_reference.mjs` harness. Give it the same authored
source-state contract used by the recorder; it recursively studies every
discovered same-origin page and scroll surface at wide and narrow before a
selected row is written:

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/observe_reference.mjs" \
  --url "https://example.test/" --id strong-1 --out .design-dna/references \
  --state-contract .design-dna/references/strong-1-state-contract.json
```

The `Observed evidence` cell then reads `motion; .design-dna/references/strong-1-observation.json plus sha256:<hex>`
for a site with a supported dynamic signature, or `static; ...` when the
dominant claim is static. The
session is schema 5: it carries exact navigation/status chains, recursive wide
and narrow structure/mechanism/state evidence, producer/dependency identity,
and a mechanism sheet (what held, travelled,
swapped, revealed, parallaxed, followed the pointer, and how long a hover
takes), a score, and the structure of the reference's first screen (what kind
of thing fills it, where the ink sits, what is against each edge and in each
corner, and the proportions of its type). The gate rejects a motion claim the
session does not support, and it rejects a motion row on its own numbers when the site is thin:
fewer than three distinct mechanisms, or scroll choreography on less than half
of its depth. That motion floor does not disqualify a strong static reference;
the wide/narrow captures plus structure/style evidence must prove its static
signature without invented motion.

## Research frame

- Reference-selection brief (audience and arrival; visitor tasks; truthful
  content model, routes, and states; brand; operating reality; material/media;
  accessibility/performance/maintenance; rights/access):
- Brief and priority-source rationale:
- Current active registry audit date and limitations:
- Authorized-account basis, if any; otherwise `none`:
- Public-access disposition for blocked or unavailable sources:
- Source-specific filters, sorts, categories, tags, and queries used with brief reason:
- Plausible alternate discovery paths checked alongside any status-based route:
- Ledger check (prior references reused, with reason, or `none`):
- Planned route/state coverage for `.design-dna/route-manifest.json`:

## Candidate comparison

Record at least eight serious finalists after opening and studying each
legitimately accessible experience at wide and narrow widths. At least two
finalists must be concretely rejected. Raw gallery listings are not candidates.
A selected reference must be both excellent and an exact fit for the selection
brief; an award or curated listing establishes eligibility, not suitability. A
weak or mismatched finalist remains rejected even if that leaves a floor
incomplete; keep researching rather than padding the pool.

| Candidate title and URL | Registry source, exact discovery path/filter, retrieval date, and fresh/reuse basis | Wide capture path and SHA-256 | Narrow capture path and SHA-256 | Complete live pages, progression, and states studied | Brief-fit gate: organization/audience/task criteria passed/failed and bound evidence | Quality/execution gate: criteria passed/failed and bound capture/sequence evidence | Conjunctive disposition and concrete rejection reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
|  | source=; discovery_path=https://; filter=; retrieval=browser / fetch; retrieved=YYYY-MM-DD; reuse_basis=fresh / revalidated-reuse; prior_evidence=path plus sha256:<hex> when reused |  |  | evidence=path plus sha256:<hex>; wide_pages=; narrow_pages=; states=; progression= | content_model=pass / fail; organization_context=pass / fail; visitor_task=pass / fail; audience=pass / fail; brand_authority=pass / fail; operating_reality=pass / fail; route_responsive=pass / fail; rights_access=pass / fail; evidence=path plus sha256:<hex> | composition=pass / fail; typography=pass / fail; media=pass / fail; responsive=pass / fail; interaction=pass / fail; finish=pass / fail; defects=none / concrete generated defect categories; evidence=path plus sha256:<hex> | brief_fit=pass / fail; quality_execution=pass / fail; disposition=selected / rejected; reason=concrete evidence-bound reason |

Selection is conjunctive and mechanical. A candidate is `selected` only when
every brief-fit criterion and every quality/execution criterion is `pass`, the
packaged observer reports no defects, its wide/narrow captures match this row,
and its discovered pages and authored states were completely visited at both
widths. A category or style tag is not a filter, generic praise is not a
criterion, and an award is only source eligibility. A reused candidate binds
its prior artifact and is observed again now; otherwise mark it `fresh`.
Anything that fails either gate is rejected with the concrete failed criterion
or generated defect, even when a quota remains unfinished.

`organization_context` is not another name for audience or visual tone. It
tests the exact organization type, mission, authority, service or product
reality, stakeholder relationship, and trust burden in this brief. A source
for a different institution or commercial model passes only when the bound
evidence proves those operating relationships transfer without invented
content, claims, or interface patterns.

For every serious candidate, reconcile the live study with an accessible
code/DOM coverage inventory. Use DOM, route/configuration hints, loaded assets,
state hooks, and event-capable elements to discover potentially missed routes,
controls, media, and interactions; then exercise every safe discovered item in
the live browser at wide and narrow widths. Code inventory is discovery aid
only. It never replaces rendered progression, target-specific before/after
evidence, or real browser verification.

## Strong references

Record at least six references drawn from at least three active sources, with
no single source supplying more than half of the rows. The floor exists so
that no one site becomes the template; it is not a target. Add rows for every
reference that earns its place. Number ranks 1 through N without gaps.

| Rank | Reference title or visible entry | Public URL or gallery-entry URL | Discovery source and accolade | Retrieval date | Access status | Wide capture path and SHA-256 | Narrow capture path and SHA-256 | Pages, progression, and states studied | Observed evidence | Measured styles | Signature (motion or static; what a stranger would name) | Brief relevance | Design to copy | Rights boundary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 |  |  |  |  | public-live / public-gallery-entry / authorized-account |  |  |  | motion / static; path plus sha256:<hex> |  | motion: / static: |  |  |  |
| 2 |  |  |  |  | public-live / public-gallery-entry / authorized-account |  |  |  | motion / static; path plus sha256:<hex> |  | motion: / static: |  |  |  |
| 3 |  |  |  |  | public-live / public-gallery-entry / authorized-account |  |  |  | motion / static; path plus sha256:<hex> |  | motion: / static: |  |  |  |
| 4 |  |  |  |  | public-live / public-gallery-entry / authorized-account |  |  |  | motion / static; path plus sha256:<hex> |  | motion: / static: |  |  |  |
| 5 |  |  |  |  | public-live / public-gallery-entry / authorized-account |  |  |  | motion / static; path plus sha256:<hex> |  | motion: / static: |  |  |  |
| 6 |  |  |  |  | public-live / public-gallery-entry / authorized-account |  |  |  | motion / static; path plus sha256:<hex> |  | motion: / static: |  |  |  |

The rank reflects fit for this exact brief, not a universal quality score.
Every row's `Signature` cell answers one question first: if a stranger were
shown this site, what would they say they noticed about its design? Begin with
`motion:` when the evidence supports a dynamic signature, then name the
element, trigger, sequence, magnitude, and settled result. Begin with `static:`
when the dominant signature is a composition, typographic system, photographic
or object treatment, or color relationship, then name that exact visible
relationship without inventing movement or forcing a verb. A subject, isolated
color, or mood is too thin for either kind.

## Interaction census

For every selected strong reference, bind the generated schema-5 observer and
schema-4 recorder interaction census at both widths. The live site, not a
gallery still or hand-written claim, supplies the inventory. Every safe
reachable target and every declared or DOM/code-discovered state must have a
target-specific before/after/settled artifact binding. Repeated instances may
share an equivalence class only when the generated census lists every target ID,
the exact enumeration rule, the tested input classes, and identical observed
behavior. External side effects, login, purchase, messaging, uploads, and
personal-data actions are recorded as blocked hand-offs; never activate them to
fill coverage.

### strong-1 interaction census

- Observation: .design-dna/references/strong-1-observation.json plus sha256:<hex>
- Recording: .design-dna/references/strong-1-recording.json plus sha256:<hex>
- Recording artifact ledger: .design-dna/references/strong-1-artifacts.json plus sha256:<hex>

| Target ID and page/route | Target kind and repeat/equivalence class | Input tested | Before state | After/settled state and changed property or behavior | Wide/narrow evidence frames or event artifacts with SHA-256 | Disposition |
| --- | --- | --- | --- | --- | --- | --- |
| target_id=; profile=wide / narrow; page=https://; occurrence=1 | kind=; repeat_class_sha256=; repeat_index=; repeat_count= | input=; source_state_id=none / state-id | observer_sha256=; recorder_sha256= | observer_after_sha256=; observer_settled_sha256=; recorder_after_sha256=; recorder_settled_sha256=; observer_behavior=; recorder_behavior= | observer_before=path plus sha256:<hex>; observer_after=path plus sha256:<hex>; observer_settled=path plus sha256:<hex>; recorder_before=path plus sha256:<hex>; recorder_after=path plus sha256:<hex>; recorder_settled=path plus sha256:<hex>; ledger=.design-dna/references/strong-1-artifacts.json plus sha256:<hex> | exercised / quiet / blocked hand-off |

The row values must reconcile exactly to the generated observer/recorder
interaction census, its target IDs, and the immutable artifact ledger. A
selected reference with a missing target census, one incidental detail, a
hand-written “tested” claim, or an unbound interaction frame is incomplete and
cannot transfer behavior.

Both bound records must also contain generated `rendered_qa_by_viewport` for
all visited pages and source states. It reconciles exact role plus accessible-
text semantic keys across wide/narrow; clipping, collisions, fixed rails,
hidden/dead controls and ARIA state; keyboard/reduced-motion/deep-link/reload/
dead-end paths; and closed/open overlay inertness, stacking, initial focus,
focus trap, Escape closure and focus return. `aria-hidden` without actual
inert/disabled/removed-tab-order behavior fails. Copy no selected-source
behavior while its generated defect evidence remains unresolved.

The `Brief relevance` cell must address the source's fit to this website's
content model, visitor task, audience, brand authority, operating reality,
route progression, and responsive needs. Same-industry status is not enough;
an adjacent or unrelated field needs a concrete transfer rationale for these
relationships and is rejected when the mapping requires invented content.

The `Design to copy` cell then names all the good parts taken from
that reference in concrete terms, behavior first and then the rest (what the
page does as it scrolls, its interaction and transitions, its signature
moment, then media treatment, composition, how its color behaves, its type
posture and scale, shapes and surfaces), and then names the parts left behind
and why. Behavior leads the order because it is what gets forgotten, not
because the rest matters less; a row that records only motion is as incomplete
as one that records only margins. A part that a thousand strangers would not
have noticed is not the takeaway and does not belong in the cell. Every palette
value, typeface family, composition, component, and behavior used by the build
comes from a recorded client brand system or a measured selected reference. An
unavailable reference family uses only the matcher's rank-one result. The
`Rights boundary` cell names what is not reused: the reference's logo, name,
copy, photographs, illustrations, and code. A gallery entry is sufficient only
for the visible design and states it actually exposes; a live URL is not
required.

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
- Dominant visual grammar by route (one selected rank per route):
- Interaction or motion copied and where it is rendered, or static posture with evidence:
- Negative-counterevidence result:
- Combination of references (which reference supplies which part, and why no
  single one of them is this build):
- Execution improvements only (content, access, responsive resilience,
  performance, maintainability, or finish; no unsourced design):
- Direction record path and status:

| Selected rank(s) | Design copied and destination | Project-specific adaptation | Boundary or verification |
| --- | --- | --- | --- |
|  |  |  |  |

This table is the design transfer map. Each row names which reference's
front-end design is copied and which route, section, or system role of this
project receives it (first screen, comparison route, product hero, type
system, palette, interaction/motion posture, phone recomposition). Assign one
selected rank as the dominant grammar for each route. Other mapped parts must
be compatible with its hierarchy, composition, progression, surface/control
language, and responsive transformation; a row cannot rely on producer-made
connective design. A static source set may remain static. When a selected row
claims motion, the interaction/motion line names it and the route/state whose
rendered sequence proves it. Every palette value and typeface family comes from
the recorded brand or measured selected references, with only a matcher-ranked
substitute when needed. The site keeps one coherent rhythm rather than changing
voice at every screen.

## Route manifest

- Route manifest ID and binding: manifest_id=__REPLACE_WITH_IMMUTABLE_MANIFEST_ID__; path=.design-dna/route-manifest.json; sha256:__REPLACE_WITH_SHA256__
- First-screen gate: __REPLACE_WITH_DESIGN_DNA_EVIDENCE_FIRST_SCREEN_GATE_JSON_PLUS_SHA256__
- First-screen proof build ID and primary route key: build_id=__REPLACE_WITH_DISTINCT_PROOF_BUILD_ID__; route_key=__REPLACE_WITH_PRIMARY_ROUTE_KEY__
- Final build ID used for the final gate: __REPLACE_WITH_DISTINCT_FINAL_BUILD_ID__

Create `.design-dna/route-manifest.json` from the packaged
`templates/route-manifest-template.json`. It is the only route mapping contract:
every route appears once with a unique key and normalized URL, one mapped
selected-reference rank/id/observation path/exact observation hash. Every
applicable state is a typed object with a unique ID, kind, exact trigger,
substantive expectation, and `mapped_reference_state_id` that exists in the
bound observation's wide and narrow `states_by_viewport`; the canonical `rest`
state is mandatory. Its viewport list includes
at least one wide and one narrow profile. Before a second section or another
route is implemented, run `gate.py --phase first-screen --route-key
<PRIMARY_KEY>` and bind its passing record above. A later route/state/viewport/
reference-mapping change invalidates that checkpoint and requires a rerun
before broad work resumes. The manifest has an immutable `manifest_id`, never a
build ID. Use a distinct proof build ID for the first-screen phase and a
distinct final build ID for the final phase; the final command must pass the
exact generated `--prebuild-authorization` JSON. Do not
maintain a second route list in this dossier or replace the manifest with a
hand-picked URL subset.

## Preimplementation visible decisions

- Visible decision source manifest: .design-dna/visible-decision-sources.json plus sha256:<hex>

Create this manifest before broad implementation and bind the exact proof
build ID, immutable route-manifest ID/hash, current selected observation
hashes, and every planned visible decision. Its `planned_decision_ids` must
equal its decision rows. Cover `layout`, `typeface`, `color`, `control`,
`transition`, `content-pattern`, and `effect`; every row binds exact routes,
states, a selected source, and immutable evidence. Set all three escape flags
(`placeholders_allowed`, `generic_scaffold_allowed`, and
`fallback_design_allowed`) to false and keep `unsourced_decisions` empty. A
generic scaffold, fallback styling, placeholder copy, or visible decision
added after the proof without a new sourced manifest invalidates the proof.
The evidence path/hash must be a generated PNG in the cited current observer's
canonical `frames` inventory, such as a capture or a before/after/settled state
or interaction frame. The observer JSON envelope, a local note, a hand-written
screenshot manifest, or another file merely placed under `.design-dna/` is not
source evidence.

## Sequence reads

One block per selected `motion:` reference. Its recording is reduced to the
moments where the screen changed, and every event is narrated before the strong
row is written. The validator counts a line per event, an inventory of what the
site does, and a signature located on events that exist. For a `static:`
reference, add a `### strong-N static evidence` block that binds the distinct
wide/narrow captures plus structure/style evidence and explains why the static
relationship dominates; do not fabricate events or motion.

### strong-1
- State contract: .design-dna/references/strong-1-state-contract.json plus sha256:<hex>
- Recording: .design-dna/references/strong-1-recording.json plus sha256:<hex>
- Recording artifact ledger: .design-dna/references/strong-1-artifacts.json plus sha256:<hex>
- Read: .design-dna/references/strong-1-sequence-read.md plus sha256:<hex>
- Signature events: wide/e0004, narrow/e0005

Create the source-state contract from
`templates/reference-state-contract-template.json`, retaining the primary
`rest` entry and adding every relevant state with an exact URL and trigger.
Produce the schema-4 recording with the packaged recorder. It records at least
90 seconds at 15 fps separately at wide and narrow. If either profile remains
incomplete, rerun it with a greater duration until every recursively discovered
same-origin page, declared state, native or transform scroll surface, and
discovered hover target is complete; it fails closed on any remainder. It writes an external artifact ledger binding the
recording JSON, both videos, both cursor paths, both difference signals, every
frame, every event sheet, and both event indexes:

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/record_reference.mjs" \
  --url "https://example.test/" --id strong-1 --out .design-dna/references \
  --state-contract .design-dna/references/strong-1-state-contract.json \
  --seconds 90 --fps 15
```

Then open `strong-1-wide-events/` and `strong-1-narrow-events/` and write
`strong-1-sequence-read.md` by hand: one profile-qualified line per event,
`- wide/e0001 (0.3s, load): ...`, saying what the cursor did, what scrolled
and what changed, followed by a `## Behaviour inventory` table
(trigger, element, effect, magnitude, events) of at least eight rows; the
recorder's `strong-1-wide-events.md` and `strong-1-narrow-events.md` are its
skeletons. The inventory is what the
build reproduces.

This step is here because three instruments in a row let the producer say it
had watched a site without looking. The last one recorded a reference's
mechanisms as numbers; the producer read the numbers, opened one rest frame of
forty-one, and built a photograph inside a dotted line. The owner recorded
himself using the site for a minute and the producer, walking that recording
at ten frames a second, found nineteen behaviours it had never seen. A script
cannot make you understand what you see. It can make sure you saw it.

### strong-N static evidence
- Wide capture: .design-dna/references/strong-N.png plus sha256:<hex>
- Narrow capture: .design-dna/references/strong-N-narrow.png plus sha256:<hex>
- Measured styles: .design-dna/references/strong-N-styles.json plus sha256:<hex>
- Structure observation: .design-dna/references/strong-N-observation.json plus sha256:<hex>
- Dominant static relationship:

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

`Recorded proof` binds primary evidence that independently shows the signature
arriving: the relevant reference/build mechanism observation for `motion:`, or
wide/narrow capture plus structure/style evidence for `static:`. It never
binds `signature-transfer.json`; that derived check reads this dossier, so
hash-binding it here would create a cycle. The final gate runs
`scripts/check_signature_transfer.mjs` after the dossier is finalized and
records its output separately in gate/review evidence.

For `motion:` rows, it requires the signature to name the single highest-weight
observed mechanism and requires the mapped final route to prove the same
behavior. For `static:` rows, it uses the wide/narrow captures plus structure
and style evidence to prove the claimed dominant composition, typography,
media, or color relationship. Incidental motion cannot force a false dynamic
signature, and a static label cannot hide a dominant untransferred mechanism.

`What a stranger would lose if this reference were cut` is the deletion test,
and it is the one cell no script can fill. Cover the reference's row and ask
what visibly goes. The answer must name a component the build actually ships,
because a loss nobody can point at is not a loss, and it must name an
arrangement or a behaviour: a ground, a radius, a size or a control dimension
is what survives when a reference was sampled rather than copied. If the
honest answer is "nothing anyone would name", that reference was not selected,
it was listed. Cut it or take its signature properly.

## Component sources

Every part that ships has a source line, or it is the producer's own design and
does not ship. There is no permission path for producer-designed components.
This is where the rejected builds came from: the references supplied one scroll
effect and the producer supplied the nav, buttons, list rows, and footer from
memory, and memory is the generic skeleton every time.

- Component census: __REPLACE_WITH_DESIGN_DNA_EVIDENCE_COMPONENT_CENSUS_JSON_PLUS_SHA256__

| Component | Source rank | Frame that shows it | Structure taken | Recorded values reproduced | Where it is used |
| --- | --- | --- | --- | --- | --- |
| first screen |  | strong-N-wide-events/eNNNN-kind.png, strong-N-narrow-events/eNNNN-kind.png, or strong-N.png |  |  |  |
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

`Frame that shows it` names the capture that shows this part, relative to the
reference captures directory, for example
`strong-4-frames/strong-4-006-scroll-settle.png`. The validator opens it. A
source line nobody can follow is not a source line: a producer once wrote
`footer <- index-space.org: a plain block, no rules` for a footer it had never
opened, because the table asked for a source and prose is free. If the frame
does not exist, go and observe the page that shows the part, or cut the
component.

`Source rank` is a selected rank. It is the only kind of source: the
owner-approved path for a producer's own part was removed in 10.0.0 on the
owner's standing order ("there is absolutely no using your design ... this
includes designs, layouts, fonts, and everything else"), and the validator
refuses the phrase anywhere in this table. A typeface row names the reference
whose family it self-hosts, or whose family `scripts/match_typeface.mjs`
matched by measurement; the match record is bound by the provenance check.

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
