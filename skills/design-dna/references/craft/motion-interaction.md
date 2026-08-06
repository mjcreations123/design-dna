# Motion and interaction

Use this when time, transition, animation, scrolling, direct manipulation, or
animated media materially shapes an experience. This reference protects
agency, access, and runtime quality without prescribing a single temporal
premise, motion grammar, effect family, or amount of movement.

## Contents

- [Define the temporal creative logic](#define-the-temporal-creative-logic)
- [Compose time without a house recipe](#compose-time-without-a-house-recipe)
- [Build scroll stories and route transitions progressively](#build-scroll-stories-and-route-transitions-progressively)
- [Specify behavior and failure](#specify-behavior-and-failure)
- [Protect agency and access](#protect-agency-and-access)
- [Budget the real runtime](#budget-the-real-runtime)
- [Review the rendered experience](#review-the-rendered-experience)

## Define the temporal creative logic

Classify the constraints before choosing effects:

- **non-negotiable:** essential information and action remain available;
  input, focus, interruption, reduced-motion, and failure behavior are sound;
  applicable accessibility and performance requirements pass;
- **inherited:** supplied brand motion, platform conventions, media, physical
  references, or product behavior the owner intends to keep;
- **negotiated:** intensity, attention cost, pacing, novelty, and other choices
  that need owner or audience judgment;
- **open:** choreography, style, duration, rhythm, dimensionality, temporal
  structure, ornament, atmosphere, ceremony, play, and any other unconstrained
  aesthetic choice.

Record the relevant `creative_logic`: what time contributes, what evidence
supports it, which observable decisions express it, where it must yield, and
which extensions remain open. Motion may confirm, connect, explain, reveal,
orient, dramatize, decorate, delight, establish atmosphere, create ritual,
support play, or do something else the project can defend. Utility is not the
only legitimate purpose.

## Compose time without a house recipe

The experience may use one temporal language, several related languages,
deliberate contrast, or chapter-specific one-offs. It may be linear,
responsive, ambient, cyclical, interruptible, simultaneous, sparse,
continuous, theatrical, or predominantly still. Spatial continuity,
progressive understanding, direct manipulation, state transition, atmosphere,
and other models may coexist when the rendered whole remains learnable and
the combination serves the work.

Storyboard the states and transitions that carry material risk or meaning.
The needed record might include resting, triggering, intermediate, settled,
reversed, cancelled, skipped, repeated, failed, and resumed conditions, but do
not manufacture states or a fixed beat count solely to complete a template.

Derive timing and motion properties from the creative logic, input mechanics,
content, and runtime. Reusable tokens can protect recurring behavior; a
commissioned sequence or singular event may use its own values. Fast, slow,
smooth, abrupt, elastic, mechanical, organic, silent, and spectacular motion
can all be right. Review the actual sequence rather than treating an easing
curve or effect name as a quality signal.

The non-animated or not-yet-animated state must preserve whatever is essential
for that state and user path. It does not have to reproduce the same aesthetic
experience when animation is itself the medium, but the alternative must be
complete, honest about what changes, and usable under the declared support
contract.

## Build scroll stories and route transitions progressively

For a scroll-led experience, document enough of the contract to implement and
test it safely:

- why scroll or changing time belongs in this work;
- source-visible content and semantic order;
- how entry, progress, reverse travel, interruption, completion, deep links,
  and history should behave where relevant;
- behavior of sticky or pinned regions and how users leave them;
- touch, keyboard, reduced-motion, unsupported-runtime, and no-JavaScript
  results;
- media loading, failure, and performance conditions.

Use ordinary document scrolling as the default input model. Do not replace
wheel or touch distance, trap the viewport, or require exact scrubbing to
access essential content. Global smooth scrolling and scrolljacking are not
art-direction shortcuts. A bounded alternate input model is possible only
when the experience truly requires it, equivalent access exists, users retain
control, and the accountable owner accepts the tradeoff.

CSS
[scroll-driven animations](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Scroll-driven_animations),
JavaScript timelines, video, canvas, WebGL, and other runtimes are tools. Select
them from the needed behavior and support evidence. Enhance from a complete
source and default-CSS state; guard optional capabilities; keep event work
bounded; and fail open when media, observation, animation, or code is absent.

For true multi-page work, same-origin
[cross-document View Transitions](https://developer.mozilla.org/en-US/docs/Web/API/View_Transition_API/Using)
may connect complete documents. Source and destination must remain correct on
direct entry, hard reload, unsupported browsers, history navigation, and
cancelled transition. Preserve focus and expected scroll behavior. Shared
transition names should identify actual counterparts, not force unrelated
pages into one visual grammar.

Under `prefers-reduced-motion: reduce`, remove or transform movement that may
trigger discomfort or impair use. Preserve information, state, sequence,
cause and effect, and action. The reduced result may be still, discrete,
shortened, crossfaded, user-triggered, text-led, or otherwise recomposed; a
near-zero duration is not automatically equivalent access.

## Specify behavior and failure

For each significant or unusual behavior, record only the fields needed to
make it accountable. A useful ledger may include:

| Behavior | Creative or user role | Trigger and inputs | States and interruption | Reduced/unsupported result | Runtime and failure | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |

The ledger may document atmosphere, memorability, ceremony, rhythm, or play as
well as task utility. It is not a quota and does not require an element to
become static merely because its value is aesthetic. Findings should identify
an actual mismatch, harm, broken state, unsupported cost, or lack of project
rationale.

Keep feedback appropriately related to the action or state that caused it.
Essential state changes must not be held hostage by a decorative sequence.
Specify cancellation, rapid repeat, competing input, loading, error, cleanup,
and recovery wherever those conditions can occur.

For Rive, Lottie or dotLottie, Spline, model-viewer, canvas, WebGL, or another
runtime asset, use the
[motion and 3D runtime asset contract](../../templates/motion-asset-contract-template.md).
Pin versions when reproducibility or supply-chain risk requires it, and record
the relevant inputs, events, states, loading, cleanup, unsupported-browser,
context-loss, reduced, static, and failure paths.

## Protect agency and access

- Keep essential navigation, reading, and actions available without hover,
  precision gestures, autoplay, or successful animation initialization.
- Provide keyboard and non-drag alternatives for interactions that require
  direct manipulation.
- Preserve visible focus and programmatic state through route, dialog, menu,
  validation, and animated layout changes.
- Make auto-moving or flashing content pausable, stoppable, or hideable when
  applicable requirements or user needs call for it.
- Stop background work when it is no longer visible or relevant.
- Keep destructive or irreversible actions explicit and recoverable where the
  product permits.
- Do not convey essential meaning through motion, position, color, or sound
  alone.

Reduced motion, screen readers, zoom, text enlargement, touch, keyboard,
coarse pointer, and no-hover are design conditions, not cleanup modes.

## Budget the real runtime

Estimate cost from the behavior's frequency, duration, concurrency, media,
device support, and visibility lifecycle rather than assigning it to a fixed
motion tier. Repeated control feedback, an occasional transition, a cinematic
sequence, and persistent ambience have different risks, but no category
dictates an aesthetic treatment.

Prefer efficient implementation when it preserves the intended result. Avoid
layout-thrashing listeners, unbounded scroll work, leaked animation loops,
unnecessary decoding, and hidden background rendering. Transform and opacity
are useful, not mandatory; other properties and runtimes are acceptable when
measured evidence supports them.

Inspect representative recordings or frames where normal-speed review hides
problems. Verify input latency, cancellation, settle, compositing, clipping,
text sharpness, memory, CPU/GPU use, battery implications, loading, cleanup,
and background-tab return in proportion to risk.

## Review the rendered experience

Begin with an unprimed observation at normal speed. Describe what the temporal
experience communicates before naming familiar effects. Then verify the
states, routes, viewports, inputs, browsers, devices, content, and user settings
where the declared behavior can fail.

Include direct entry, hard reload, rapid and repeated input, interruption,
reverse travel, history navigation, missing media, animation disabled,
JavaScript unavailable, and reduced motion when applicable. Full-page capture
must not depend on pre-scrolling every hidden observer target. Bind compared
evidence to the same build, route, state, viewport, browser, theme, locale, and
content fixture.

Ask whether the motion supports the declared creative logic, whether plural or
mixed temporal systems feel authored, whether agency and meaning survive
failure and alternatives, and whether the runtime cost is acceptable. A
fade-up, marquee, morph, parallax field, hover effect, typewriter sequence,
ambient loop, or motionless passage is neither good nor bad in isolation.
Report the concrete rendered relationship, not the ingredient.
