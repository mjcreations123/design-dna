# Direction Challenge

Use Direction Challenge only when the accountable owner explicitly escalates a
recurrence concern to its three-root contract, or deliberately asks for a
multi-root high-ambition greenfield concept challenge. A premium or
high-ambition website alone selects Showcase, not Direction Challenge. It is a
way to keep the first plausible answer from silently becoming the only
answer—not a standing aesthetic rule for every project.

It does not prescribe a font, palette, geometry, component set, animation,
section order, motif, or degree of novelty. It does not score beauty, detect
AI involvement, or guarantee that every viewer will like the result.

## Contents

[activate](#activate-deliberately) | [roots](#work-in-roots-not-reskins) |
[proof](#proof-before-broad-implementation) |
[independent review](#review-without-leaking-the-answer)

## Activate deliberately

Activate alongside Project Contrast with the owner-recurrence trigger:

```text
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "<PROJECT_ROOT>" --profile showcase --trigger owner-recurrence-requirement
```

`--trigger` is an initialization-or-merge operation. For this recurrence
trigger it selects both Project Contrast and Direction Challenge records, adds
both applicable capabilities, and writes the same trigger in each canonical
record. It may also be used with `--profile project-contrast`, `--profile
direction-challenge`, or an explicit one of those records; the paired record is
still selected.

For an already initialized paired state, use `--add-trigger
owner-recurrence-requirement` only when `state.json` already lists both records.
It adds the trigger to both existing records without replacing their evidence;
it does not create a missing counterpart. If either record is absent, use the
`--profile showcase --trigger ...` command above to create or merge the pair.

Once either canonical record declares this trigger, `--check-state` and
`--check-ready` require a non-orphaned pair: both records listed in
`state.json`, both applicable evidence capabilities, and the same trigger in
both records. They also reject a paired recurrence draft as clean state. This
does not prevent initialization from creating a truthful paired draft; it
prevents a later check from silently treating one as resolved.

For an explicitly requested multi-root high-ambition greenfield concept
challenge that has no cross-project comparison boundary, select the standalone
profile:

```text
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "<PROJECT_ROOT>" --profile direction-challenge
```

The second command does not imply that a comparison with prior client work is
authorized. It only makes the brief-qualified, reference-backed exploration
and proof boundary inspectable.

Do not invoke this merely because a project is new, because a trend list names
an ingredient, or because a previous site used a common visual choice. An
approved brand system, maintenance task, bounded repair, or low-ambition
utility route can have a single honest direction.

## Work in roots, not reskins

Complete the brief-fit reference dossier before defining roots. Record three or
more concept roots whose incompatible organizing relationships come from
different qualified, fully traversed reference combinations and whose content
counterparts exist truthfully in the present brief. A supplied brand book,
source packet, real product material, existing information architecture, or
protected system constraint remains authoritative, but it does not let the
producer invent the missing visual answer.

A root states all of these in project language:

- its brief anchor, selected reference ranks/observation hashes, and copied organizing logic;
- the first encounter and dominant content operation;
- the body progression and visitor agency; and
- the surface consequence caused by those decisions.

The roots need not be strange, maximal, or visually opposite. They do need to
be incompatible in at least two of the decisions that structure a visitor’s
encounter: organizing logic, opening, content operation, body progression, or
visitor agency. Record the exact pairwise challenge matrix. Replacing copy,
imagery, color, typography, shapes, or motion inside an unchanged encounter is
not an incompatible root.

The record’s reference-order events make the sequence inspectable: brief-fit
criteria are frozen first; qualified references are fully traversed and
compared next; and the three source-backed roots are recorded before any root
is rendered. Post-hoc inspiration cannot justify an existing root, and no root
may precede its measured source evidence.

## Proof before broad implementation

Build at least two small, rendered proof slices from two different source-backed roots before
the full site starts. Each slice binds a path-bound schema-3
`render-review.json` package, its frozen local source-manifest SHA-256, the
exact build ID and route, and the exact wide and narrow renderer capture IDs.
The auditor resolves those IDs through the package marker to the actual full-page
PNG artifacts, browser viewports, final routes, and source-snapshot boundary.
Do not substitute separately hashed image files, claimed dimensions, or a bare
review note for this package. Choose slices that expose the real uncertainty,
such as an opening model, reading sequence, task operation, material
relationship, or mobile recomposition. They are not required to be same-sized
pages, themed mockups, or a portfolio of style boards.

Select one root only after comparing it with a specific rendered rejected root.
Record both source combinations, their exact brief-fit evidence, and why the
rejected combination fits the current brief less well. This keeps the choice
reference-led rather than producer- or novelty-led.

Do not begin broad implementation at `roots-ready` or `proof-ready`. Freeze the
independent unprimed review, advance the record to `reviewed`, and explicitly
set `implementation_boundary.status` to `broad-implementation`; the packaged
`--check-prebuild` command enforces that transition. When a later render
challenges the selection, return to the earliest root decision instead of
applying cosmetic substitutions.

## Review without leaking the answer

An independent reviewer sees the proof slices before being given the root
labels, chosen-root statement, or selection rationale. A completed review must
declare `exposure: "unprimed-proof-slices-only"`; that means the reviewer was
shown only the named proof slices, with root labels and selected/rejected
rationale withheld. Record the first observation, exact proof-slice IDs,
relationship, `observed_at`, `frozen_at`, limitations, and a hash-bound
evidence file. Freeze at or after the observation and before the
selection rationale is recorded. `reference_order` establishes roots before
polished references; it is not a timestamp ledger, so
`selection.rationale_recorded_at` supplies the bounded review-to-selection
ordering declaration.

The auditor binds the declared exposure, times, proof IDs, and evidence hash;
it deliberately does not search freeform review prose to decide what a
reviewer saw. The declaration remains an accountable review boundary, not
machine-proof of a human's actual exposure. An independent agent review can
expose a blind spot; it is not owner acceptance, target-user research, or proof
of visual quality.
Owner acceptance, if the project needs it, is a separate accountable-owner or
owner-authorized-human decision recorded in its applicable review and release
evidence. Do not relabel an independent review as that acceptance.

The lifecycle is deliberately narrow:

- `draft` — no project-specific roots claimed;
- `roots-ready` — three incompatible brief-qualified reference-backed roots, reference order, and
  exact challenge matrix exist;
- `proof-ready` — two different roots have narrow/wide rendered proof and a
  selected-versus-rejected decision with a zoned rationale-recorded time exists; and
- `reviewed` — an independent unprimed review covers every proof slice.

Run the standard-library audit after the evidence exists:

```text
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/direction_challenge_audit.py" "<PROJECT_ROOT>" --contract ".design-dna/direction-challenge.json" --output ".design-dna/direction-challenge-audit.json" --require-ready
```

The audit checks declared structure, exact pair coverage, the schema-3
path-bound report marker, frozen local source manifest, build IDs, final routes,
exact wide/narrow PNG capture bindings, selected/rejected root proof, and
independent-review coverage. Wide and narrow proof must use the shipped
schema-3 renderer's 240-by-240 CSS-pixel minimum profile; this is an evidence
compatibility floor, not a recommended breakpoint. It cannot judge beauty or
certify human authorship.
The evidence boundary resists stale or copied standalone screenshots, but is not
a cryptographic signature against an actor able to rewrite every owned artifact.
`init_project_state.py --check-ready` includes the same readiness boundary when
the Direction Challenge record is selected. The standalone audit's `ready`
field is local-record readiness; under `owner-recurrence-requirement`, only
the initializer gate additionally verifies that both Direction Challenge and
Project Contrast records, capabilities, and the shared trigger are present.
