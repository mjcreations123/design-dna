# Operate mode

Use when the primary task is to create, inspect, change, approve, move,
monitor, transact, or recover real state. Typical surfaces include
applications, dashboards, admin tools, configuration, checkout, booking, and
multi-step workflows.

When a requested staff/admin task is paired with a public experience, name the
public/back-office boundary in the Connected Public Experience record. Use
approved, sandbox, or clearly local fixture state with a non-empty meaningful
case; do not manufacture an empty decorative admin just to imply operations.
Keep public claims and staff permissions independently truthful.

Mode describes the operational job, not a visual style. Familiar conventions
often reduce risk, but expressive, branded, dense, sparse, novel, or highly
visual treatment can be used only when an established approved system or
brief-qualified measured reference supplies it.

## Model the task and authority

- Map actors, permissions, objects, states, transitions, dependencies, and
  failure modes.
- Identify high-frequency, high-risk, destructive, and irreversible actions.
- Establish navigation and information relationships from real work.
- Cover the states the product can actually enter, including relevant
  loading, stale, empty, partial, offline, error, success, disabled,
  permission, cancellation, and recovery behavior.
- Keep auditability, consequence, recovery, and help near actions when their
  risk requires it.

Do not use fake live data, placeholder analytics, or controls that do nothing.

## Trace visible state to its source

For every material value, status, count, permission, or action, keep a semantic
trace:

`visible value or label -> UI behavior -> query or command -> source of truth
-> freshness, error, and permission behavior -> accountable owner`

Record transformations, caching, optimistic state, fallback, and asynchronous
boundaries that can change what the user sees. A state label is an operating
claim, not decorative interface language.

Demo fixtures, examples, mocks, and static snapshots need an explicit boundary
and cannot be presented as current production state. When authorized and safe,
verify critical traces end to end. Otherwise keep them unverified and remove,
disable, or qualify claims that depend on them.

## Bind the real operational patterns

Use the task to qualify shipped-product references, then reproduce their
fitting operational patterns rather than inventing a dashboard recipe.
Depending on the work, this may include finding and inspecting, editing, creating, reviewing,
submitting, scheduling, acting in bulk, reconciling, importing, exporting,
monitoring, or recovering.

- Preserve search, filters, sorting, pagination, selection, and context where
  those mechanisms exist.
- Explain formats and consequences; preserve user work through validation and
  recoverable failures.
- Distinguish actions according to their real meaning and side effects.
- Make selection scope, bulk consequences, partial failure, and individual
  errors clear.
- Provide undo or a documented recovery path when feasible.

These are functional possibilities, not required sections or visual forms.

## Protect different users

- Expose permission and ownership without leaking restricted data.
- Do not rely on color alone for state, status, priority, or consequence.
- Support efficient inputs without hiding essential controls.
- Keep the chosen density and type legible at zoom and relevant containers.
- Adapt complex information deliberately rather than translating every form
  into the same mobile component.

Use exact selected-source/state/component mappings and observable transfer decisions for the visual
system. Do not reject cards, spaciousness, density, animation, ornament,
strong branding, or unusual composition by ingredient, but require exact
source authority for each. Revise the mapping when the rendered treatment impedes
decisions, misrepresents state, breaks access, or exposes an unexplained
producer default.

## Verify

Test every role, route/state/wide-narrow manifest cell, and critical transition
with realistic data. Cover applicable keyboard, focus, touch, permissions,
validation, duplicate action, interruption, refresh, concurrency, slow and
failed networks, offline/stale state, import/export, destructive recovery,
audit evidence, and responsive operational constraints. Keep unavailable
real-source checks blocked rather than treating a smaller presentation sample
as proof.
