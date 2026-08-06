# Shared service-status banner contract v2

## Public state

The root element uses `data-state` with one of:

- `ready`
- `degraded`
- `outage`
- `recovered`

State meaning must remain available without color. A state update changes the
visible label, description, action availability, and assistive announcement as
one transaction.

## Semantics

- The root is a named status region.
- `outage` is announced assertively only when it results from a user-triggered
  sample-state change; initial page load must not interrupt the reader.
- Other updates use a polite announcement.
- Repeating the current state must not create a duplicate announcement.

## Actions

Only `recovered` may expose a dismiss action. Dismissal hides that consumer for
the current in-memory page session and dispatches
`service-status:dismissed`. A later state change restores the consumer.

## Resilience

Without JavaScript, both consumers show truthful static status guidance and no
nonfunctional dismiss control. Forced colors, reduced motion, keyboard use,
touch, narrow layout, and 200% zoom are supported.
