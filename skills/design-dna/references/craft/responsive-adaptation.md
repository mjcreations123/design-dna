# Responsive adaptation

Use this for experiences that must survive changing viewport, container,
content, input, locale, device capability, or user settings. Responsive design
preserves meaning and creative intent; it does not require a standard device
list, breakpoint set, or mobile silhouette.

## Contents

- [Define what must survive](#define-what-must-survive)
- [Let observed pressure drive adaptation](#let-observed-pressure-drive-adaptation)
- [Cover the declared environment](#cover-the-declared-environment)
- [Verify around actual change](#verify-around-actual-change)

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

### Review narrow-screen runway in context

At every project-relevant narrow condition, identify where the route first
delivers meaningful subject content or a useful action. Record the actual
starting state and the intervening sequence, scroll distance, or interaction
needed to reach it. Treat those measurements as evidence about this audience,
task, reading mode, and composition, not as a universal pixel, viewport,
screen-count, or page-length limit.

A long essay, deliberate pause, immersive sequence, or spacious composition
may be correct. Revise when repeated framing, caveats, display-scale passages,
empty fields, or equal modules delay the route's distinct value without a
project-derived reason. Check the distance between later meaningful anchors as
well as the opening; shortening every mobile page is not the goal. When an
important action follows a long object, article, or process, test whether an
early jump, contents path, repeated action, or uninterrupted reading is the
more coherent result for this task. None is a portable default.

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

When a chart, map, topology, process drawing, or other content-bearing diagram
does explanatory work, also use [data visualization](data-visualization.md).
Save narrow evidence that its labels and essential relationships remain usable,
not merely present. Recomposition, segmentation, prioritization, contextual pan
or zoom with orientation, and equivalent text or structured views are possible
responses; none is a required form. Shrinking the wide graphic until it fits is
not proof that its information survived. When detail requires panning, test
whether a complete overview, locator, extent cue, or other orientation method
is needed before or alongside the detail. A fit-to-width preview is one option,
not a universal diagram recipe. Exercise the initial, intermediate, and terminal
positions when position affects understanding. The initial state must read as a
real located endpoint rather than an empty, uninitialized, or broken control;
use perceptible visual and textual orientation that fits the chosen artifact.
This does not require a progress bar, thumb, or fixed interaction pattern.

### Preserve the comparison task

For a comparison, verify the action the reader must perform, not only that each
record remains present. Serially stacking complete records can move equivalent
fields several screens apart and destroy comparison even when reflow and
document width pass. Depending on the content, viable responses include a
field-first transpose, anchored identifiers, synchronized disclosure, a
state-preserving selector, an oriented scroll surface, or another
project-specific composition. No response is required by category; capture a
representative comparison path and check whether the intended differences can
still be held together. Follow the path past its first viewport: a correct
field-first transpose can still become memory-heavy when record identity,
selected lens, units, or the comparison key disappear several sections before
the reader needs them. Verify reacquisition and working context at the deepest
meaningful field, not only the opening arrangement. A persistent key, repeated
local identifier, bounded selector, changed grouping, or another response may
help; none is a portable requirement.

### Preserve consequential dependency order

When one choice depends on an exclusion, prerequisite, safety limit, price,
permission, or other consequence, inspect the relationship after responsive
reordering and disclosure. A wide adjacent pair can become a permissive action
followed several screens later by the condition that limits it. Keep the
dependency understandable before or at the point of action through source
order, concise qualification, a local cross-reference, progressive disclosure,
or another tested response that fits the task. Do not repeat every warning at
every step; preserve the consequence where delay could change a decision.

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

Inspect decorative continuity devices as content reflows: route lines, rules,
connectors, frames, and absolute ornaments must not cross text or controls,
imply false relationships, or occupy the space needed by the narrow task.
Moving, interrupting, simplifying, or omitting one at a pressure point can
preserve the larger identity better than forcing its wide geometry to survive.
Apply the same check to gradients, tonal bands, images, textures, and animated
fields behind text. A paragraph that remains technically visible can still
lose a stable reading ground when a changing boundary passes through its
lines; inspect the actual composite at the consequential passage and relevant
motion endpoints rather than sampling only the surrounding base color.

Begin review with the rendered result before applying motif labels. Ask whether
the transformation preserves the declared creative logic and hard safeguards,
not whether it follows a familiar responsive pattern. Record concrete failures
and the conditions that produce them.
