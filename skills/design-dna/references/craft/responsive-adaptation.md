# Responsive adaptation

Use this for every route that must work across changing viewport, container, content, input, or user settings.

## Adapt the task, not just the columns

1. Identify what must remain visible, adjacent, ordered, or persistent.
2. Let content pressure reveal breakpoints.
3. Recompose navigation, controls, and media when stacking would weaken the task.
4. Use container queries when a component's available space matters more than the viewport.
5. Preserve source order and semantics unless a tested alternative remains coherent.

A mobile layout is not a desktop layout with every box stacked. A wide layout is not a narrow layout stretched until reading and relationships break.

## Cover input and environment

Design for:

- touch, mouse, keyboard, stylus, hover, and no-hover;
- portrait, landscape, split-screen, and short-height windows;
- safe areas, browser chrome, virtual keyboards, and dynamic viewport units;
- zoom, text enlargement, text-spacing overrides, and forced colors;
- slow networks, blocked assets, and offline or stale states when relevant;
- translated content, RTL, long names, and locale-specific numbers or dates.

When the product actually supports multiple locales or right-to-left
direction, use the [localization reference](../quality/localization.md); visual
mirroring alone is not sufficient implementation.

## Media and data

- Art-direct crops around the subject.
- Match source size and format to display conditions.
- Preserve data meaning when charts, tables, or comparisons collapse.
- Give dense tables an intentional small-screen strategy: prioritization, reflow, disclosure, scroll with context, or a task-specific alternate view.
- Keep captions, legends, controls, and consequences associated with their object.

## Verify continuously

Resize through the full supported range rather than checking only named devices. Include:

- narrow, intermediate, common, wide, and unusually wide;
- a short-height viewport;
- 200% and 400% zoom where applicable;
- sparse and worst-plausible content;
- browser text enlargement;
- open menus, dialogs, errors, and virtual keyboard;
- sticky and fixed elements at every edge.

Fix the structural cause of overflow, clipping, or order confusion. Do not hide overflow or add one-off breakpoints as the first response.
