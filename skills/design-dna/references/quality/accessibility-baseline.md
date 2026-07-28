# Accessibility baseline

Use this for every public-facing or interactive surface. Target WCAG 2.2 AA unless the project's jurisdiction, policy, or contract requires more. This is a build baseline, not a compliance certification.

## Structure and perception

- Declare the page's primary human language accurately and mark meaningful
  language changes in parts; verify the final rendered document rather than
  relying on a framework default.
- Use semantic landmarks, headings, lists, tables, and controls.
- Preserve a logical reading and focus order.
- Give meaningful non-text content an appropriate text alternative; hide decoration.
- Provide captions, transcripts, descriptions, or alternatives for time-based media as required.
- Do not use color, position, shape, sound, or motion as the only cue.
- Meet contrast requirements for text (1.4.3) and meaningful UI boundaries or graphics (1.4.11).
- Support reflow at 400%/320 CSS pixels (1.4.10) and user text-spacing overrides (1.4.12).
- Keep instructions valid across orientation, zoom, theme, and input mode.

## Keyboard and focus

- Make every operation available by keyboard without a trap.
- Use visible focus (2.4.7) that is not obscured by authored content (2.4.11).
- Preserve focus when content opens, closes, updates, or navigates.
- Give bypass mechanisms for repeated content.
- When a skip link changes the URL fragment, verify keyboard focus reaches a meaningful programmatically focusable target; hash movement or visual scrolling alone is not a completed bypass.
- Make titles, headings, and link purposes descriptive.
- Avoid single-character shortcuts unless they can be disabled, remapped, or limited to focus.

## Input and interaction

- Associate labels, instructions, descriptions, and errors programmatically.
- Identify input purpose and expose names, roles, values, and states.
- Provide error identification, suggestions, and prevention for consequential submissions.
- Avoid asking for the same information twice in one process (3.3.7).
- Keep help in a consistent location when repeated (3.2.6).
- Provide authentication that does not depend on a cognitive-function test (3.3.8).
- Offer non-drag and non-motion alternatives (2.5.7 and 2.5.4).
- Meet target-size minimums or documented exceptions (2.5.8).
- Announce status changes without moving focus unnecessarily (4.1.3).

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
- Avoid unexpected context changes on focus or input.
- Explain time limits and provide extension or recovery when applicable.
- Use stable terminology, predictable placement, forgiving input, and undo where feasible.
- Test zoom, memory burden, interruption, and error recovery on the critical path.

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
- high contrast or forced colors;
- touch target and orientation checks.

Automated checks are supporting evidence, not coverage. Record tools, versions, routes, states, results, and unresolved limitations.

## Specialist handoff

Escalate to a dedicated accessibility audit and qualified human testing for high-risk services, legal certification, procurement conformance, complex widgets, charts, authentication, media, or assistive-technology claims. Never describe this baseline as an ADA/WCAG certification.
