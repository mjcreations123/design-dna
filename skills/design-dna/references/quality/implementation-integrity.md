# Implementation integrity

The design decisions in this skill only reach a visitor through shipped
HTML, CSS, and JavaScript. This file governs that layer: not whether the
code is tidy, but whether it does what it says it does.

Working behavior is a low-freedom area, like truth and access. Nothing
here constrains an aesthetic choice, and nothing here is a style
preference. Every rule below exists because a declaration that looked
correct in source did nothing in the browser.

## Contents

- [The principle](#the-principle)
- [Silent defeat](#silent-defeat-valid-code-that-does-nothing)
- [Let structure carry the meaning](#let-structure-carry-the-meaning)
- [The cascade is a contract](#the-cascade-is-a-contract)
- [JavaScript enhances and never gates](#javascript-enhances-and-never-gates)
- [Remove the residue](#remove-the-residue)
- [Comments that earn their line](#comments-that-earn-their-line)
- [Before calling implementation done](#before-calling-implementation-done)

## The principle

Prefer constructions whose effect is observable over constructions that
merely assert an intent. When code claims something the runtime does not
guarantee, the claim needs either a mechanism that enforces it or a
measurement that confirms it.

This is the same evidence discipline the rest of the skill applies to
design decisions, moved one layer down. A rendered screenshot proves a
composition; a computed style proves a declaration. In both cases the
source file is the weakest available evidence, because it records what
the author meant rather than what the browser did.

The practical consequence: for any declaration in the list below, read the
computed value or the rendered result before treating it as applied.

## Silent defeat: valid code that does nothing

The dangerous defect class in web implementation is not the syntax error,
which announces itself. It is the declaration that parses, validates,
survives every linter, and is inert. These are the observed cases; each
one shipped or nearly shipped in real work.

- **`aspect-ratio` defeated by a dimension attribute.** `width` and
  `height` attributes on a replaced element are presentational hints that
  create a definite size, and a definite size disables `aspect-ratio`
  entirely. Keep the attributes, since they reserve layout space and
  prevent shift, and add the explicit `height: auto` that hands control
  back to the ratio.
- **`hidden` defeated by any component class.** The user-agent rule is a
  bare `[hidden] { display: none }`, so any class on the same element that
  sets `display` wins on specificity and the element stays visible.
  Specificity juggling does not fix this reliably. Ship one global
  `[hidden] { display: none !important }` and the attribute becomes
  trustworthy everywhere.
- **A section rule repainting a component.** A context selector such as a
  dark-band rule setting link color is one class more specific than the
  component's own modifier, so the component silently loses its color
  inside that section. This is a frequent source of contrast failures on
  an element that measures correctly in isolation. Scope context rules to
  exclude the components they must not touch, and measure the component
  inside every section it appears in, not only on its default ground.
- **Scroll-driven and viewport-triggered reveals stuck at their start
  state.** An element animated from opacity zero stays at zero whenever
  the trigger never fires: a hidden tab, a paused timeline, a capture
  taken from the top of the document, or a browser without the feature.
  The start state must be the visible state, with motion added on top, so
  a trigger that never fires costs an animation rather than the content.
- **Sticky positioning constrained by its own container.** A sticky child
  can never travel beyond its containing block, so a sticky element inside
  a short wrapper appears not to stick at all. Verify the scroll behavior
  in the render, not from the declaration.
- **A form field silently dropped by its own name.** Indexed access on a
  form's element collection resolves built-in members before author
  fields, so a control named for one of those members returns the built-in
  and the field reads as absent. Prefer an explicit query over indexed
  access, and confirm every field appears in the submitted payload.
- **Overflow measurements taken through a clipping container.** Some
  overflow values suppress the very scroll dimensions used to detect
  overflow, so an overflowing page reports none. Detect horizontal
  overflow by measuring element geometry against the viewport, and
  self-test the detector against a case known to be broken.

Treat this as a live list. When a declaration is found inert in the render,
record the mechanism here so the next build checks for it directly.

## Let structure carry the meaning

Use the element that already means what the content is. Landmarks,
headings in order, lists for lists, buttons for actions, links for
navigation, `<time>` for dates, real labels bound to real controls. This
is the cheapest accessibility, the cheapest keyboard behavior, and the
cheapest resilience, since a semantic document degrades gracefully and a
generic one does not.

A generic element carrying a role, a tabindex, and a key handler is a
reimplementation of a native control, and it will be incomplete. Reach for
it only when no native element expresses the behavior, and then implement
the full state and interaction contract rather than its happy path.

Keep the accessible name and the visible label saying the same thing. A
label shortened for layout while an overriding accessible name keeps the
old wording breaks voice control, and every automated check stays green
through it.

## The cascade is a contract

Decide once where a value comes from, and keep the rest of the sheet from
competing with that decision.

- Put shared values in custom properties at the level that owns them, and
  let components read the token rather than restating the literal.
- Keep specificity flat and let source order resolve the rest. An
  escalating specificity war is a sign that two rules both believe they
  own the same property.
- Reserve `!important` for the narrow class of rules that must survive any
  context, such as the `hidden` rule above. Using it to win a local fight
  moves the fight rather than settling it.
- When a component must look different inside a context, express that as a
  variant the component defines, not as a context rule reaching in.
- State every property a state depends on. A rule that changes color on
  focus but inherits its outline from elsewhere will lose the outline the
  moment the elsewhere changes.

## JavaScript enhances and never gates

The page renders complete with scripts disabled or failed. Content,
navigation, and the primary action exist in the markup; script improves
them. A build whose first paint depends on script has traded its entire
audience against a progressive-loading effect.

- Bind behavior to elements that already work. A link with a real target
  gains an interception; it does not start as an inert element.
- Guard every listener against the element being absent. A single
  reference error stops the rest of the script silently.
- Give one subtree one animation owner. Two systems writing the same
  transform produce a fight that reads as jitter and is difficult to
  attribute later.
- Prefer values the browser can interpolate, and read layout in a batch
  before writing it, so a scroll handler does not force synchronous layout
  on every frame.
- Honor reduced-motion at the source of the motion, not by hiding the
  result.

## Remove the residue

Ship the build, not its history. Before completion, remove unused rules,
dead selectors, orphaned assets, unreferenced files, abandoned experiments,
starter metadata, and any framework scaffolding the project never adopted.

Residue is not only weight. A dead selector that still names a live class
misleads the next editor, and an abandoned experiment left in the sheet
gets found later and mistaken for the current system.

## Comments that earn their line

Write a comment to state a constraint the code cannot express: a value
derived from a measurement, a workaround bound to a specific browser
behavior, an ordering that matters for a non-obvious reason, an owner
decision that would otherwise look arbitrary.

Do not narrate what the next line does, restate the selector in prose,
mark a change as new or fixed, or explain the reasoning behind a choice to
a reviewer who is no longer reading. Do not leave creative-brief language,
process vocabulary, or direction notes in shipped source; public source is
part of the delivered surface.

## Before calling implementation done

Confirm in the rendered result, not the source:

- every declaration from the silent-defeat list that the build actually
  uses resolved to its intended computed value;
- the page renders complete with scripts disabled;
- the console is clean and no request failed;
- every interactive control is reachable and operable by keyboard, with a
  visible focus indicator that survives its section context;
- each component was measured for contrast inside every ground it appears
  on, not only its default one;
- no residue, starter metadata, or internal language remains in public
  source.

These checks establish implementation integrity only. They do not
establish that the design decisions were right, that the content is true,
or that the release is authorized; those remain with
[engineering verification](engineering-verification.md), the
[preship gate](../../templates/preship-gate.md), and
[production readiness](production-readiness.md).
