# Responsive adaptation

Use this for experiences that must survive changing viewport, container,
content, input, locale, device capability, or user settings. Responsive design
preserves meaning and creative intent; it does not require a standard device
list, breakpoint set, or mobile silhouette.

## Define what must survive

Classify non-negotiable, inherited, negotiated, and open constraints. Identify
the relationships, actions, states, atmosphere, and identity that should remain
recognizable across conditions. Record the relevant `creative_logic` and how
it may transform rather than assuming every surface should look alike.

Some experiences preserve adjacency; others preserve sequence, hierarchy,
comparison, immersion, or a particular gesture. A small-screen version may be
a new composition, interaction, crop, or temporal arrangement. A wide version
may reveal new simultaneity or retain deliberate narrowness. Neither is
obligated to stack or stretch the other.

## Let observed pressure drive adaptation

Map the real content and behavior under supported conditions, then change the
scaffold when a relationship stops working. Grid, flex, flow, overflow,
reordering, disclosure, container queries, and viewport queries are tools, not
visual defaults. Multiple scaffolds or route-specific transformations are
valid when their differences are intentional and maintainable.

Preserve semantic and action order unless a tested alternative remains
coherent for keyboard, assistive technology, reading, and operation. If visual
order, disclosure, or persistence changes, keep labels, state, consequences,
captions, legends, and controls associated with the object they affect.

## Cover the declared environment

Select conditions from the audience, support contract, analytics, content,
and design risk. Consider relevant combinations of:

- touch, mouse, keyboard, stylus, hover, and no-hover;
- portrait, landscape, split-screen, short-height, and unusually wide windows;
- safe areas, browser chrome, virtual keyboards, and dynamic viewport units;
- zoom, text enlargement, text-spacing overrides, and forced colors;
- slow networks, blocked assets, reduced data, stale state, and offline use;
- translated content, right-to-left direction, long names, and locale-specific
  numbers, dates, and input methods;
- missing, unusually shaped, or slow media and dense data.

When localization or right-to-left support is real, use the
[localization reference](../quality/localization.md). Visual mirroring alone is
not sufficient.

Art-direct media to preserve meaning, not merely dimensions. Provide an
intentional strategy for tables, charts, comparisons, navigation, dialogs,
sticky regions, and other structures that become difficult under pressure.
The strategy may be reflow, prioritization, disclosure, scrolling with context,
an alternate view, or another project-specific solution.

## Verify around actual change

Resize continuously around every condition where structure or behavior
changes. Include representative and worst-plausible content, supported zoom
and text settings, open interactive states, relevant input methods, and the
declared extremes of the support range. Named widths are evidence only when
the project or audience makes them relevant; they are not a universal capture
quota.

At pressure points, inspect actual headings, labels, prices, controls,
translations, unbroken tokens, crops, focus order, hit targets, and state—not
only document `scrollWidth`. Fix the structural cause of clipping, overflow,
lost context, or order confusion. Do not hide overflow or collect one-off
breakpoints solely to make screenshots pass.

Begin review with the rendered result before applying motif labels. Ask whether
the transformation preserves the declared creative logic and hard safeguards,
not whether it follows a familiar responsive pattern. Record concrete failures
and the conditions that produce them.
