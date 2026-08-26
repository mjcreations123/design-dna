# Accessibility baseline

Use this for every public-facing or interactive surface. Target WCAG 2.2 AA
unless the project's jurisdiction, policy, or contract requires more. This is
a selective build baseline, not an exhaustive criterion map or compliance
certification. Verify every applicable requirement for the actual product and
jurisdiction.

## Contents

- [Structure and perception](#structure-and-perception)
- [Exclusion and assisted access](#exclusion-and-assisted-access)
- [Keyboard and focus](#keyboard-and-focus)
- [Input and interaction](#input-and-interaction)
- [Custom composite widgets](#custom-composite-widgets)
- [Motion, time, and cognition](#motion-time-and-cognition)
- [Required verification](#required-verification)
- [Screen-reader smoke-test script](#screen-reader-smoke-test-script)
- [Specialist handoff](#specialist-handoff)

## Structure and perception

- Declare the page's primary human language accurately and mark meaningful
  language changes in parts; verify the final rendered document rather than
  relying on a framework default.
- Use semantic landmarks, headings, lists, tables, and controls.
- Preserve a logical reading and focus order.
- Give meaningful non-text content an appropriate text alternative; hide
  decoration.
- Provide captions, transcripts, descriptions, or alternatives for time-based
  media as required.
- Do not use color, position, shape, sound, or motion as the only cue.
- Meet WCAG 2.2 AA contrast requirements: at least 4.5:1 for normal text,
  3:1 for qualifying large text, and 3:1 for applicable meaningful UI
  boundaries or graphics. Treat APCA only as an additional developmental
  legibility diagnostic, never as a WCAG substitute or conformance claim.
- Support reflow at 400%/320 CSS pixels (1.4.10) and user text-spacing overrides
  (1.4.12).
- Keep instructions valid across orientation, zoom, theme, and input mode.

## Exclusion and assisted access

Map barriers beyond conformance criteria on each critical path:

- literacy, numeracy, jargon, memory load, stress, interruption, and time
  pressure;
- language, locale, translation quality, reading direction, and cultural
  context;
- older or shared devices, small screens, limited storage, blocked media, slow
  or costly networks, offline use, and unavailable platform features;
- missing documents, payment methods, identity credentials, private space, or
  confidence using the technology;
- use with a trusted helper, interpreter, caregiver, advocate, support worker,
  phone agent, or supported non-digital channel.

For each material barrier, record who may be excluded, the consequence, the
evidence, and a usable prevention, alternative, or recovery path. Use plain
language, manageable steps, save and resume, forgiving errors, low-bandwidth
paths, and language or human support where the real service provides them.

Verify assisted and alternate paths through the same meaningful outcome,
including privacy, consent, authority, handoff, confirmation, and recovery.
Do not invent staffed support, translated coverage, offline capability, or
equivalent access that has not been confirmed.

## Keyboard and focus

- Make every operation available by keyboard without a trap.
- Use visible focus (2.4.7) that is not obscured by authored content (2.4.11).
  Sticky headers, docked bars, and overlays are the usual offenders: tab
  through the full page and confirm the focused element is never hidden
  behind a fixed surface. Review focus indicator area and contrast as a
  quality target; do not misrepresent the WCAG 2.2 AAA Focus Appearance
  criterion (2.4.13) as an AA requirement.
- Style focus for keyboard visibility without flashing rings on every
  pointer click: the focus-visible distinction exists for exactly this, and
  removing an outline is acceptable only with an equal-or-better visible
  replacement in place.
- Give in-page anchor targets scroll margin so a heading landed on by a
  fragment link or skip mechanism is not buried under a sticky header.
- Preserve focus when content opens, closes, updates, or navigates.
- Give bypass mechanisms for repeated content.
- When a skip link changes the URL fragment, verify keyboard focus reaches a
  meaningful programmatically focusable target; hash movement or visual
  scrolling alone is not a completed bypass.
- Make titles, headings, and link purposes descriptive.
- Avoid single-character shortcuts unless they can be disabled, remapped, or
  limited to focus.

## Input and interaction

- Associate labels, instructions, descriptions, and errors programmatically.
- Identify input purpose and expose names, roles, values, and states.
- Keep visible label text in the accessible name, in the same order where
  practical, so speech-input users can activate controls by the words they see
  (2.5.3).
- Complete pointer actions on release when feasible, allow abort or undo, and
  avoid irreversible action on pointer-down (2.5.2).
- Provide error identification, suggestions, and prevention for consequential
  submissions.
- Avoid asking for the same information twice in one process (3.3.7).
- Keep help in a consistent location when repeated (3.2.6).
- Provide authentication that does not depend on a cognitive-function test
  (3.3.8).
- Offer non-drag and non-motion alternatives (2.5.7 and 2.5.4).
- Meet the WCAG 2.2 AA 24 × 24 CSS pixel target-size floor or its documented
  spacing/inline/equivalent-control exceptions (2.5.8). Aim near 44 CSS pixels
  for important touch controls when density and context allow; document a
  smaller intentional target and verify spacing and error risk.
- Announce status changes without moving focus unnecessarily (4.1.3).

## Custom composite widgets

Prefer a native element when it provides the needed semantics and behavior. If
the product genuinely needs a custom dialog, combobox, tabs, listbox, menu,
tree, grid, toolbar, slider, or another composite widget, map its purpose to the
closest current WAI-ARIA Authoring Practices Guide pattern. Record and verify
the promised role, accessible name, owned structure, states and properties,
entry and exit, roving or active-descendant focus model, complete keyboard
contract, pointer and touch behavior, announcements, dismissal, and return
focus as applicable.

APG is informative guidance, not a normative standard, comprehensive design
system, or production-ready component library. Its examples are illustrative,
can have browser and assistive-technology support gaps, and must not be copied
without testing the actual implementation in the project's supported
[browser and assistive-technology matrix](browser-support.md). Deviations need
an equally complete, standards-conforming interaction contract and direct
evidence; adding a role without its behavior breaks the promise.

### Forms and submissions

For every form that can affect a person, account, inquiry, booking, order, or
stored record:

- choose the correct native input type and use `autocomplete` and `inputmode`
  tokens that match the field's real purpose;
- keep labels visible, allow paste and password-manager/autofill behavior, and
  never require placeholder text or formatting alone to explain input;
- validate at a useful time without erasing values, trapping focus, or
  announcing the same error repeatedly;
- associate field errors programmatically and, for multi-error submissions,
  provide a concise summary whose focus behavior helps the user reach each
  cause;
- expose pending state, prevent accidental duplicate submission, and provide
  clear success, recoverable failure, cancellation, and retry behavior;
- preserve entered values after a recoverable error unless retaining a
  sensitive value would create greater risk;
- explain why personal information is needed, minimize collection, and keep
  optional consent separate from service-essential terms;
- verify the real server response and failure path rather than treating a
  client-side success animation as completion.

## Motion, time, and cognition

- Respect reduced-motion preferences and preserve meaning without animation.
- Let users pause, stop, or hide applicable moving content.
- Keep flashing below applicable seizure thresholds; remove or redesign
  uncertain flashing rather than relying on reduced-motion alone (2.3.1).
- Avoid autoplay audio. If audio plays automatically for more than three
  seconds, provide a mechanism to pause or stop it, or control its volume
  independently (1.4.2).
- Avoid unexpected context changes on focus or input.
- Explain time limits and provide extension or recovery when applicable.
- Use stable terminology, predictable placement, forgiving input, and undo where
  feasible.
- Test zoom, memory burden, interruption, and error recovery on the critical
  path.

## Required verification

Perform, as applicable:

- keyboard-only pass;
- focus-order and visible-focus inspection;
- automated accessibility scan;
- contrast measurement;
- screen-reader smoke test on the critical route;
- document language and language-of-parts inspection;
- 200% and 400% zoom/reflow;
- text-spacing override;
- reduced motion;
- visible-label and accessible-name parity, including a representative
  speech-input check;
- pointer cancellation on consequential controls;
- flashing and autoplay-media inspection;
- high contrast or forced colors;
- touch target and orientation checks.

Automated checks are supporting evidence, not coverage. Record tools, versions,
routes, states, results, and unresolved limitations.

## Screen-reader smoke-test script

Choose a supported browser and screen-reader pairing and record both versions,
operating system, route, state, build, language, and date. Use the same pairing
for reruns unless the support matrix requires more.

On the critical route:

1. Load from a fresh navigation and confirm the page title, language, first
   meaningful announcement, landmarks, and heading outline.
2. Use the bypass mechanism and confirm focus reaches the intended target.
3. Navigate headings, links, controls, form fields, regions, and any table or
   collection. Confirm names, roles, values, states, order, and repeated labels
   are understandable without the visual layout.
4. Complete the primary task without a pointer. Trigger one representative
   validation error, pending state, success or confirmation, and recoverable
   failure. Confirm useful announcements occur once and focus remains or moves
   for a documented reason.
5. Open and close each critical menu, disclosure, modal, or composite widget.
   Confirm entry, containment where required, dismissal, return focus, and
   keyboard operation.
6. Trigger one dynamic update, filter, pagination, or incoming-status change
   when present. Confirm the update is perceivable without stealing focus or
   repeatedly interrupting reading.
7. Confirm meaningful images, charts, audio, video, maps, and generated media
   have an equivalent appropriate to their real purpose; decoration is silent.

Record expected and observed behavior, failure evidence, severity, fix, and
rerun result. A smoke test covers only the named journey and pairing. It does
not establish full assistive-technology compatibility, WCAG conformance, or
representative disabled-user validation.

## Specialist handoff

Escalate to a dedicated accessibility audit and qualified human testing for
high-risk services, legal certification, procurement conformance, complex
widgets, charts, authentication, media, or assistive-technology claims. Never
describe this baseline as an ADA/WCAG certification.
