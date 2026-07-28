# Operate mode

Use when the primary task is to create, inspect, change, approve, move, monitor, or recover real state. Typical surfaces include applications, dashboards, admin tools, configuration, checkout, booking, and multi-step workflows.

## Quality target

Make the correct action, current state, ownership, consequence, and recovery path clear. Familiar conventions are often a form of care.

## Model the task

1. Map actors, permissions, objects, states, transitions, dependencies, and failure modes.
2. Identify high-frequency, high-risk, destructive, and irreversible actions.
3. Establish navigation and information density from real work.
4. Design default, loading, stale, empty, partial, offline, error, success, disabled, and permission states.
5. Keep auditability, recovery, and help near consequential actions.

Do not use fake “live” data, placeholder analytics, or controls that do nothing.

## Design core patterns

### Find and inspect

- Preserve search terms, filters, sorting, pagination, and result context.
- Make result count, active constraints, and no-result recovery clear.
- Keep row identity and selection stable through updates.
- Pair charts with accessible summaries and underlying data where appropriate.

### Change

- Explain required formats and consequences before input.
- Preserve user work through validation and recoverable failures.
- Distinguish save, submit, publish, schedule, approve, and delete.
- Show autosave, unsaved, synchronization, and concurrent-edit state truthfully.
- Provide review-before-submit for high-consequence actions.

### Act at scale

- Make selection scope explicit.
- Preview bulk consequences and partial failure.
- Preserve individual error details.
- Provide undo or a documented recovery path when feasible.

## Protect different users

- Expose permissions and ownership without leaking restricted data.
- Do not rely on color alone for status or priority.
- Support keyboard-efficient paths without hiding essential controls.
- Keep dense layouts legible at zoom and on smaller containers.
- Adapt tables deliberately rather than collapsing them into unrelated cards.

## Common risks to review

- marketing theatrics in a frequent workflow;
- excessive cards, padding, animation, rounding, or glass effects;
- under-designed tables, forms, filters, and error handling;
- status badges with unclear semantics;
- dashboards optimized for a screenshot rather than decisions;
- destructive actions presented as ordinary buttons;
- activity indicators that imply monitoring not actually implemented.

## Verify

Test each role and critical transition with realistic data. Cover keyboard, focus, touch, permissions, validation, duplicate submission, interruption, refresh, concurrency, slow and failed networks, offline/stale state, import/export, destructive recovery, audit evidence, and mobile operational constraints.
