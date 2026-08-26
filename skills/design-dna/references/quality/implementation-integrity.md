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
- [Make script dependency intentional](#make-script-dependency-intentional)
- [Preserve evidence through typed code](#preserve-evidence-through-typed-code)
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

- **A ratio that never participates in sizing.** HTML `width` and `height`
  attributes can provide dimensions and an intrinsic ratio; they do not by
  themselves defeat CSS `aspect-ratio`. The ratio stops deciding a used size
  when both axes are otherwise definite. Keep truthful intrinsic dimensions
  where they reserve space, choose which axis may remain automatic for a fluid
  treatment, and verify the computed and rendered box instead of assuming that
  either the attributes or `aspect-ratio` won.
- **`hidden` defeated by any component class.** The user-agent rule is a
  bare `[hidden] { display: none }`, so any class on the same element that
  sets `display` wins on specificity and the element stays visible.
  Fix the component or add a narrow author rule only when the project needs
  one. Do not ship a blanket `[hidden] { display: none !important }`: it also
  overrides `hidden="until-found"`, whose content must remain discoverable by
  find-in-page and fragment navigation. If an author rule is necessary, a
  scoped form such as
  `[hidden]:not([hidden="until-found"]) { display: none !important; }` keeps
  that state outside the override. Verify ordinary hidden, until-found,
  reveal, and accessibility behavior in the target browsers rather than
  assuming the selector is sufficient.
- **A section rule repainting a component.** A context selector such as a
  dark-band rule setting link color is one class more specific than the
  component's own modifier, so the component silently loses its color
  inside that section. This is a frequent source of contrast failures on
  an element that measures correctly in isolation. Scope context rules to
  exclude the components they must not touch, and measure the component
  in the section and states that create the real risk, not only on an isolated
  default ground.
- **Scroll-driven and viewport-triggered reveals stuck at their start
  state.** An element animated from opacity zero stays at zero whenever
  the trigger never fires: a hidden tab, a paused timeline, a capture
  taken from the top of the document, or a browser without the feature.
  Keep required content visible in the base document and apply the hidden
  start state only after the motion system and its trigger are known to be
  active. A failed trigger must cost the enhancement rather than the content.
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
- Reserve `!important` for a documented boundary that genuinely must survive
  its supported contexts. Using it to win a local fight moves the fight rather
  than settling it.
- When a component must look different inside a context, express that as a
  variant the component defines, not as a context rule reaching in.
- State every property a state depends on. A rule that changes color on
  focus but inherits its outline from elsewhere will lose the outline the
  moment the elsewhere changes.

## Make script dependency intentional

Choose the failure contract from the surface. A public information or
marketing route should normally keep its essential content, navigation, and
primary destination available when optional script fails. A dashboard,
editor, configurator, or other JavaScript application may legitimately depend
on script for its task. It still needs an intelligible bootstrap, timeout,
unsupported, authentication, and failure path instead of a blank page or a
control that pretends to work.

Do not turn `no JavaScript` into a universal release test. Select it when the
project promises progressive enhancement, public crawlable content, a server-
rendered route, or another script-independent path. For a script-dependent
application, test slow boot, chunk or API failure, offline behavior where
supported, and recovery against the declared application contract.

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

## Preserve evidence through typed code

When the project uses TypeScript or another typed boundary, keep known evidence
precise instead of widening it and asserting it back later:

- parse untrusted network, storage, URL, form, and message values at their I/O
  boundary, then pass named domain values inward;
- retain useful inference with the project's ordinary tools, such as
  `satisfies`, literal preservation, or a schema-derived type, when that makes
  the contract clearer;
- reject chained assertion laundering such as `value as unknown as User` and
  a known value widened to a broad type only to be cast back at use;
- keep `unknown`, broad objects, and catch-all dictionaries at genuine
  boundaries rather than using them as the ordinary internal model;
- when an assertion is truly necessary, name the concrete invariant, how it
  was established, and the assertion's scope. A marker such as `SAFETY:` with
  no explanation is not evidence.

These are evidence-preservation checks, not a mandatory lint dialect. Module
mocking, runtime type checks, framework conventions, Effect-specific rules,
and identifier vocabulary remain project and stack decisions unless an
established repository policy says otherwise. Merge a new checker into the
existing toolchain only when the task authorizes that dependency and its rules
fit the project.

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

Do not narrate what the next line does, restate the selector in prose, or mark
a change as new or fixed. Preserve reasoning that a future maintainer needs to
keep an invariant intact; move creative-brief narration, abandoned process
notes, and direction experiments out of shipped source. Public source is part
of the delivered surface.

## Before calling implementation done

Confirm in the rendered result, not the source:

- every declaration from the silent-defeat list that the build actually
  uses resolved to its intended computed value;
- the declared script-failure path works for this surface: complete essential
  public content where progressive enhancement is promised, or an honest and
  recoverable application failure state where script is required;
- no unexpected console error or request failure affects the reviewed task;
- every interactive control is reachable and operable by keyboard, with a
  visible focus indicator that survives its section context;
- contrast was checked in the representative grounds and states that can
  change the result, not only an isolated default;
- no residue, starter metadata, or internal language remains in public
  source.

These checks establish implementation integrity only. They do not
establish that the design decisions were right, that the content is true,
or that the release is authorized; those remain with
[engineering verification](engineering-verification.md), the
[preship gate](../../templates/preship-gate.md), and
[production readiness](production-readiness.md).
