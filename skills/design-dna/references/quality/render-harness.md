# Render harness

How to actually capture, probe, and measure a page when the preship gate
demands rendered proof. Every trap here was hit on a real build; the
methods are the ones that survived.

## Contents

- [Driving Chrome over CDP](#driving-chrome-over-cdp)
- [Full-page capture without reflow](#full-page-capture-without-reflow)
- [Probe sequencing](#probe-sequencing)
- [Element-anchored measurement](#element-anchored-measurement)
- [Pixel-sampled contrast, done right](#pixel-sampled-contrast-done-right)
- [Fallback rehearsal mechanics](#fallback-rehearsal-mechanics)

## Driving Chrome over CDP

When a preview pane cannot composite (hidden tab) or cannot resize, drive
real Chrome headless directly: spawn with `--headless=new
--remote-debugging-port=P --user-data-dir=<temp> --hide-scrollbars
--force-device-scale-factor=1`, fetch `/json/list` for the page target,
speak CDP over its WebSocket. Node's native fetch and WebSocket need zero
dependencies. Enable `Page`, `Runtime`, `Log`, and `Network` domains and
collect `Runtime.consoleAPICalled`, `Log.entryAdded`, and
`Network.loadingFailed` in the same run; the console proof and network
proof come free with every capture.

## Full-page capture without reflow

NEVER capture a full page by resizing the viewport to the document height.
vh-based layout re-flows against the new viewport, the page grows, and the
capture truncates while looking complete; this studio shipped a review
round on such a truncated pair. The correct method keeps the viewport at
its real size:

1. `Page.getLayoutMetrics` for `cssContentSize`.
2. `Page.captureScreenshot` with `captureBeyondViewport: true` and a
   `clip` of `{x:0, y:0, width, height: contentSize.height}`.

Confirm completeness mechanically: the capture height matches
`scrollHeight` at the UNCHANGED viewport, and the bottom rows sample as
footer pixels, not mid-section content.

`captureBeyondViewport` never fires `loading="lazy"` images; a far-below-
fold image captures as an empty box while nearer ones happen to load. Before
the capture, sweep the scroll position through the full document height,
return to the top, and `await Promise.all([...document.images].map(i =>
i.decode()))` so every image is painted.

## Probe sequencing

Probes run at whatever viewport the LAST navigation left. Three reads of
`getComputedStyle().fontSize` after a mobile shot test mobile three times;
clamp() and vw resolve against the current viewport. Run per-width probes
immediately after that width's navigation, or re-emulate metrics and
re-navigate before probing. The same applies to media-feature emulation:
re-navigate after `Emulation.setEmulatedMedia` or the override may not
take.

## Never run an interaction twice

An interaction expression passed as BOTH the shot's `evalAfter` and a probe
runs twice, and every toggle it performs is undone. This studio spent a
debugging cycle on three "broken" features that were correct: claim, hold
and pin had each been clicked twice. Separate the two roles absolutely:
`evalAfter` ACTS, the probe only READS. Stash anything the action needs to
report on `window.__x` and read it back in the probe.

Subscribe to `Runtime.exceptionThrown` as well as console and network
events. A module that throws during import attaches no listeners, so every
control silently does nothing while the console stays empty; without
exception capture that reads exactly like a state bug.

## Element-anchored measurement

Never sample screenshots at hardcoded pixel offsets; any layout change
silently moves the target and the numbers describe the wrong region. Probe
`getBoundingClientRect()` (plus `scrollY`) for every element under test in
the same run as the capture, and drive the sampler from those rects.

## Pixel-sampled contrast, done right

Sampling a text region on a normal screenshot poisons the measurement two
ways: the glyph pixels themselves, and the antialiasing halo between glyph
and ground, which always produces mid-contrast values that read as
failures. Filtering by color distance does not fix it; neighboring TEXT in
another ink registers as low-contrast background.

The clean method: capture twice. Second capture runs an `evalAfter` that
sets `visibility:hidden` on the text elements under test, leaving the true
composite background. Sample every few pixels across each element's rect
on THAT capture and take the worst contrast against the element's ink
token. Floors: 4.5:1 body, 3:1 large. This is the only trustworthy method
for text over photographs, gradients, or scrims, and it is cheap.

## Fallback rehearsal mechanics

Block the font FILES, not the origin: `Network.setBlockedURLs` with
`["*.woff2"]` before navigation, then reload and verify: the fallback
stack's first face actually painted, document height within ~1 percent of
the loaded run, key element boxes unchanged, and the page readable. Expect
one blocked entry per declared font file in `Network.loadingFailed`; a
count mismatch means a file you did not know you were shipping.
