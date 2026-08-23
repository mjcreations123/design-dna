# Render harness

Use this when rendered evidence needs repeatable capture or browser-derived
observations. Choose the capture and measurement method from the claim being
made. A screenshot, computed style, network record, pixel sample, accessibility
tree, and human visual review are different evidence; none silently substitutes
for another.

## Contents

- [Use the bundled reviewer truthfully](#use-the-bundled-reviewer-truthfully)
- [Drive interactive capture with the Playwright CLI](#drive-interactive-capture-with-the-playwright-cli)
- [Bound host capture and browser state](#bound-host-capture-and-browser-state)
- [Declare the scenarios that matter](#declare-the-scenarios-that-matter)
- [Understand full-page capture](#understand-full-page-capture)
- [Sequence state and probes](#sequence-state-and-probes)
- [Anchor measurements to the rendered element](#anchor-measurements-to-the-rendered-element)
- [Measure contrast with an appropriate method](#measure-contrast-with-an-appropriate-method)
- [Rehearse failures separately](#rehearse-failures-separately)
- [Protect captured data](#protect-captured-data)

## Use the bundled reviewer truthfully

The shipped `scripts/rendered_review.mjs` uses Playwright with a compatible
local Chromium-family browser. It can save full-page screenshots and a contact
sheet, and it records bounded observations such as console and network events,
geometry, overflow, current-viewport text occlusion by a peer surface, computed
typography, font availability, media, and focus traversal. Text occlusion is an
advisory sampled from DOM text paint and hit testing; it can reveal a sibling
band, sticky surface, or positioned ornament covering a caption, but it does
not prove that every text pixel on a full page is unobscured. Read the
command's `--help` output for the current interface.

It does not use the raw-CDP recipe that older versions of this reference
described. It also does not prove composite contrast, glyph-level font
selection, screen-reader behavior, usability, aesthetic quality, or
authorship. Keep every conclusion within the report's own limitations and the
evidence actually collected.

Use the project's established browser or visual-regression system when it
already provides the needed evidence. Do not add or replace tooling merely to
match this reference.

## Drive interactive capture with the Playwright CLI

For the hands-on capture and probing between bundled-reviewer runs
(state exploration, media-emulation checks, scroll-position slices,
element crops, quick console and network reads), the standard tool is the
Playwright CLI: the `@playwright/cli` npm package, a one-shot command
interface over a per-workspace daemon that keeps the live browser, page
state, and emulation between shell commands. Pin the installed version in
the project record; it tracks a Playwright prerelease channel, so an
unpinned install can change behavior between runs. On a machine with a
real Chrome installed it uses that browser directly with no download.

The invocations that cover this reference's recurring needs: `open` and
`resize` for viewport control, with `--device` or `--mobile` for true
device emulation including pixel ratio; `screenshot` for viewport,
`--full-page`, `--hires` (device pixels), or an element by selector;
`snapshot --boxes` for an accessibility tree with geometry; `console` and
`requests` for errors; `eval` for computed styles and font status; and
`run-code` for anything needing the full API in one batch, including
media emulation for reduced motion, color scheme, and forced colors,
which then persists for subsequent commands. Sessions are scoped to the
working directory, matching the one-session-per-project convention;
`kill-all` clears zombie daemons, an environment variable unlocks
`file://` targets when no server exists, and capture output should be
directed outside cloud-synced trees.

Two disciplines make its evidence trustworthy. First, identity: every
command response reports the page URL, title, and any non-success HTTP
status, and navigation failure exits nonzero. Bind title and status into
recorded observations, so a dead server's error page can never pass as a
green capture; a probe result without page identity is not evidence.
Second, the full-page limitation below still applies: `--full-page` is
the same composite-from-top capture as any other tool, so scroll-driven
work is proven with real scrolling plus viewport captures, never with a
full-page image alone.

The raw devtools-protocol script remains a named fallback for
environments where the CLI cannot install, with the same identity
discipline; the bundled reviewer remains the only source of the
schema-bound review report, which the CLI complements and never
replaces.

## Bound host capture and browser state

In a desktop agent or GUI host, prefer an established project harness or the
bundled reviewer when either can collect the claim-relevant evidence. Treat a
host screenshot or raw browser-protocol path as supplemental, not as a reason
to keep retrying a less reliable capture route. Give each attempt a bounded
deadline. A hang, incorrect device-pixel crop, or unverifiable output ends that
attempt; fall back to the bounded harness, preserve any useful limitation, and
continue the review. Do not multiply capture matrices or persistent browser
profiles to compensate for one failed screenshot call.

If a browser path needs a user-data directory, create a unique, credential-free
directory in the operating system's temporary area or another explicitly
authorized scratch root. Keep it outside source, deployable/public output,
accepted evidence, and project-state trees. Close the browser and remove that
exact owned directory on every success, failure, timeout, and interruption
path. If cleanup cannot be verified, report the exact retained path and size;
do not call the run clean. Reuse an authenticated or persistent profile only
when the real task requires that session and the authority and data-handling
boundaries permit it—never merely to render a local static site.

Stop task-owned preview servers after evidence collection unless the owner
asked to keep a preview available. Server reachability, browser launch, and a
saved PNG are separate facts; report each only when observed.

## Declare the scenarios that matter

For substantial review, create a bounded capture manifest that names the real
routes, states, exact viewport dimensions, input conditions, and preferences
that can change the conclusion. Derive them from the product, audience,
supported devices, responsive transitions, failure modes, and the changed
surface. The manifest is the primary evidence contract; no permanent list of
device widths is sufficient for every project.

When no manifest is supplied, the bundled reviewer uses a compatibility matrix
as a convenience for broad discovery. Treat that matrix as optional diagnostic
coverage. It may be excessive for a small repair and insufficient for a real
release claim. Do not describe its built-in dimensions as the project's
responsive requirements or as privileged “real” devices.

Keep scenarios bounded. Capture only the routes and states needed for the
decision, and record any relevant state that the safe manifest actions cannot
reach rather than injecting arbitrary script or triggering consequential
external behavior.

## Understand full-page capture

The bundled reviewer currently asks Playwright for `fullPage: true`. That is a
useful overview, not a guarantee that every visual state was observed. Lazy
content, viewport-height composition, sticky or scroll-linked behavior,
virtualized lists, canvas or WebGL content, and intersection-driven reveals may
need separate evidence.

By default the reviewer does not actively scroll the document before capture.
For an authorized local target, `--scroll-sweep` can visit the page before the
screenshot to warm some lazy or offscreen content. A sweep can also change
intersection, sticky, animation, or scroll-linked state, so record that it ran
and do not treat the result as equivalent to passive first-entry behavior.

When a full-page image reflows, truncates, duplicates, or misses the experience,
use the project's browser tooling to capture viewport-sized states at recorded
scroll positions, or save another artifact suited to the interaction. Bind that
evidence to the same build and disclose that it came from a separate method;
the bundled reviewer does not currently assemble those slices.

## Sequence state and probes

Apply viewport, media preferences, content, and interaction state before
reading computed values or taking the screenshot. A probe describes the state
that exists when it runs, not a state implied by its filename. Keep mutating
actions separate from read-only observations so a toggle, submit, or stop
control is not accidentally exercised twice.

Record route, state label, viewport, preference, input modality, build ID, and
capture time with each consequential observation. Console silence is not proof
that an interaction works; exercise the supported path and inspect its visible
result.

## Anchor measurements to the rendered element

When measuring pixels or geometry outside the bundled reviewer, locate the
target from the current DOM and its rendered rectangles rather than hard-coded
screenshot offsets. For multi-line text, range rectangles can describe the
actual lines more accurately than a block element's full column. Re-resolve
the target after viewport, font, content, or state changes.

These mechanics prevent a sampler from drifting onto unrelated pixels. They do
not decide which measurement is valid or whether the rendered result is good.

## Measure contrast with an appropriate method

The bundled reviewer does not calculate text contrast. Use an accessibility
tool or measurement procedure that is validated for the actual background and
content in question. Simple opaque foreground/background pairs, gradients,
photographs, transparency, antialiasing, video, and changing canvas content may
require different methods.

A paired capture that hides only the text under test can help sample the
composited background beneath that text, but it is an optional custom method,
not a shipped `rendered_review.mjs` feature. If used, document the selectors,
state mutation, sample geometry, color source, algorithm, standards threshold,
browser, and validation against known cases. Do not report a computed token
ratio or an unaudited pixel heuristic as measured composite contrast.

## Rehearse failures separately

Font blocking, image failure, offline behavior, reduced motion, forced colors,
and other fallbacks need the mechanism appropriate to the real delivery path.
The bundled capture manifest does not expose arbitrary request interception.
Use existing tests or an authorized browser session to create the failure,
verify that it actually occurred, inspect the resulting task and layout, and
record the separate evidence. Do not infer a fallback from CSS declarations or
from a failed request count alone.

## Protect captured data

Before capturing private or multi-project material, apply
[review data handling](data-handling.md). Screenshots and contact sheets retain
visible names, logos, copy, people, URLs, and media even when their filenames or
labels are neutral. Classify and minimize the input, use synthetic data where
required, define recipients and retention, and inspect every artifact before
sharing.
