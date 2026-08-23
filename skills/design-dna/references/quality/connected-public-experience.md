# Connected public experience

## Contents

[model](#start-with-an-honest-public-model) |
[continuity](#select-a-continuity-model-after-direction) |
[staff work](#pair-public-and-staff-work-honestly) |
[closure](#close-the-applicable-path)

Use this **optional capability** only when the brief explicitly asks for a
detailed, connected, customer-facing, app-like, or client-demonstration
experience, or when the public promise depends on content, decisions, or state
carrying between routes. Initialize it with
`--profile connected-public-experience` or add
`--evidence-capability connected-public-experience`; that selection creates the
project-local `connected-public-experience.json` evidence record.

Do not select it merely because a site has navigation. A short editorial page,
campaign, artwork, or reference surface can truthfully set its canonical
applicability marker to `not-applicable` with a project reason. A blocked case
names the dependency and next action; it remains blocked rather than becoming a
quiet readiness pass. This capability has no page-count, visual-style, admin,
backend, funnel, database, or live-integration quota.

`not-applicable` is not a waiver for staff or admin work. Its
`staff_admin_split` must be the canonical no-staff state: `status:
not-requested`, `operate_mode: not-required`, null public/back-office
boundaries, `fixture.status: none` with null fixture fields and no descriptor,
and no mapped or final `staff-back-office` evidence. If staff/admin work was
requested, use an `applicable` CPE closure and prove that branch. If the staff
work cannot yet be completed, leave it non-ready as a blocked staff branch or
use a blocked CPE applicability marker with its dependency and next action.
The same empty canonical state is required any time
`staff_admin_split.status` is `not-requested`, including an otherwise
applicable CPE record; changing the status label cannot erase a fixture,
boundary, or staff proof that still exists.

## Start with an honest public model

Before the first public encounter, record the canonical applicability marker:
`applicable`, `not-applicable`, or `blocked`. For an applicable case, record
pre-direction constraints separately from the selected direction:

- the direct-entry question for each material entry condition;
- the true entities, content, claims, and constraints that may recur;
- the smallest category or flow guidance the public promise actually needs.

Do not infer inventory, staff, address, pricing, availability, payment,
account, tracking, or integration merely because one would make a demonstration
look more credible. A bounded scenario may demonstrate useful relationships
when its limits are placed where they change a reasonable expectation.

Use the explicit status crosswalk for every consequential entity, action, or
state. Do not write a bare `real` status: it overloads delivery, content, and
behavior into a misleading single claim.

| Dimension | Use one clear status |
| --- | --- |
| Delivery | `concept`, `demo`, `staging`, `production` |
| Content | `approved`, `scenario`, `pending`, `prohibited` |
| Behavior | `live`, `local-only`, `illustrative`, `unavailable`, `out-of-scope` |

Name the authority for each row. For example, an approved product description
can coexist with local-only saved selections in a demo; neither makes the other
production behavior.

## Select a continuity model after direction

Once a root is selected, describe its own continuity model: intentional
handoffs or resets and why they help a visitor; one path through arrival,
decision, action, outcome, and recovery or continuation; and the rendered and
functional proof that will test it. A direct entry may deliberately reset.
Continuity does not require every route to share state or force visitors into a
funnel.

Keep the early constraints above separate from this selected-root model. When
Project Contrast or Direction Challenge is active, do not force roots to share
a flow. Record either a viable model for each root or a named invariant that
each root honors. The evidence record uses root IDs only to make that
procedural choice reviewable; it does not prescribe a site architecture.

At final readiness, the CPE selected root must equal the active Direction
Challenge `selection.chosen_root_id`, and that root needs a CPE continuity
entry. For Project Contrast, record an internal `project_contrast_mapping`
with distinct selected and counter root IDs that both appear in the CPE entry
map, or record `not-applicable` with a substantive reason when that work has
no root-level applicability. Do not invent a Project Contrast root merely to
fill this field.

## Pair public and staff work honestly

When a brief actually requests staff or admin work, make the public and
back-office boundary explicit and use [Operate mode](../modes/operate.md) for
the back-office task. Use approved, sandbox, or clearly local fixture state
with its authority and boundary; the fixture must contain a meaningful state
to inspect. Never add an empty, decorative fake admin merely to make a public
site feel more substantial. If the staff path is unavailable, record it as
blocked rather than showing an inoperative control.

Do not relabel a requested or blocked staff branch as CPE `not-applicable` to
avoid its evidence. A requested branch reaches CPE readiness only through an
applicable final closure with its own proof. A blocked branch is intentionally
not ready until its declared dependency is resolved, unless the whole CPE
record is honestly marked `blocked`. The v1 staff split has no separate
dependency/next-action fields, so use blocked CPE applicability to record a
whole-experience block; otherwise a `staff_admin_split.status: blocked` record
remains non-ready and must be reopened when the operational dependency clears.

For a requested staff/admin branch, bind a privacy-safe JSON fixture descriptor
to the fixture. It declares a synthetic, sanitized-approved, or sandbox
classification; `contains_personal_data: false`; meaningful state; a nonzero
record count; authority; and boundary. Its `meaningful_state`, `authority`,
and `boundary` must describe the same declared `fixture.content_or_state`,
`fixture.authority`, and `fixture.boundary` (normalized whitespace and casing
are allowed, unrelated substitute prose is not). The descriptor classification
must also agree with the fixture status: `local-fixture` is `synthetic`,
`sandbox` is `sandbox`, and `approved` is `sanitized-approved`. Recomputing a
descriptor hash does not excuse a semantic mismatch. Final readiness also needs a schema-3
staff capture and that branch's own structured functional attestation. Bind
both exact final evidence IDs in `staff_admin_split.final_evidence`; the
attestation route must equal the mapped schema-3 staff-capture route. A broad
public-path row with `staff-back-office` added to its coverage does not prove
the staff branch. Do not create this descriptor, capture, or admin surface
when staff/admin work was not requested.

## Close the applicable path

Only an applicable selection needs final connected-experience closure. Bind the
exact reviewed build, appropriate final rendered capture(s), and a functional
path artifact or accountable recorded result. Every final rendered row names a
normalized route, an exact schema-3 `render-review.json` reference, and one
capture ID. Its `file` must be the exact decoded PNG emitted by that capture,
and the schema-3 build ID must equal `reviewed_build_id`. A bare `.png`, a
hash-bound arbitrary byte file, or a renderer report without its named capture
cannot close this evidence. Direct-entry proof specifically needs one of these
final rendered captures; a functional result cannot substitute for it.

When a passed functional result has no separately hash-bound artifact, add its
full `attestation`: reviewer ID and role, timezone-bearing observation time,
exact build, route/state, state conditions, exact steps, result, limitations,
and `verification_class: recorded-review`. This is an accountable review
statement, not independently verified or live evidence. If an artifact exists,
an attestation can add context but must agree with the final build and result.

Before final readiness, give every rendered and functional proof-plan ID a
`final_disposition`: `final-bound` with the matching final evidence ID, or
`superseded` with a substantive reason. Do not leave a planned proof ID quietly
unresolved after implementation. Explicitly bind proof for direct entry and
recovery or continuation, not just a happy-path click.

The standalone auditor derives active capabilities from a safe project-local
`.design-dna/state.json` when present. If no state selection exists, provide
one or more explicit `--active-capability` values; otherwise the command emits
a not-ready missing-context report. An explicit list cannot override a present
state record, and a CPE contract cannot be ready unless
`connected-public-experience` is active. Use `--allow-incomplete` only to
collect a diagnostic report; it never changes `ready` to true. Output paths
must stay portable and project-relative, without absolute, dot, dot-dot,
backslash, drive, or empty components.

At final review ask:

- Does direct entry answer the visitor's question before internal setup or
  boundary language takes over?
- Do a chosen handoff or reset, its outcome, and recovery/continuation behave
  as stated at the reviewed conditions?
- Does the status crosswalk match what the rendered and functional evidence
  actually show?
- Does a requested staff/admin branch preserve its public/back-office split,
  Operate-mode boundary, non-empty fixture, and functional proof?

Record remaining limitations as limitations. This capability improves the
inspectability of a coherent public experience; it does not prove owner
acceptance, target-user validation, production readiness, real service
operation, or visual quality.

Existing v1 planning records remain structurally readable, but an applicable
final record made before these bindings is intentionally not ready until it is
completed with schema-3 captures, proof-plan dispositions, and—where
applicable—the new functional, staff, or direction-linkage fields. A v1
`not-applicable` record that still declares requested/blocked staff work,
fixture material, staff evidence, or staff boundaries is no longer a valid
readiness disposition: either clear the canonical no-staff fields only when no
staff work exists, change to `applicable` and bind the actual staff proof, or
mark CPE applicability `blocked`. The same repair applies to an `applicable`
record that was relabeled `not-requested` while retaining staff material: it
must either restore `requested` and its proof or remove all staff-only state.
Do not backfill a claim; reopen and review the actual final build.
