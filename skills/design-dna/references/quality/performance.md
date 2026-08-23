# Performance

Use this when planning assets, fonts, scripts, motion, embeds, rendering, or
production readiness.

## Contents

- [Set an objective](#set-an-objective)
- [Protect the critical path](#protect-the-critical-path)
- [Account for environmental and lifecycle cost](#account-for-environmental-and-lifecycle-cost)
- [Design resilient states](#design-resilient-states)
- [Measure](#measure)

## Set an objective

Use the project's measured baseline and contractual targets first. If none
exist, scale the objective to the selected assurance capabilities and delivery
stage:

- For Quick work or a local concept, record a provisional route-specific
  objective, representative device and network, and the checks actually run.
  Label it unapproved and do not use it for release claims.
- For Standard or Showcase work moving toward release, propose budgets and
  identify the accountable owner and review point.
- For production, contractual, or regression-gated work, use owner-approved
  targets and name monitoring and regression ownership before claiming
  readiness.

Include:

- critical route and representative device/network;
- Core Web Vitals objectives;
- transferred JavaScript, CSS, fonts, images, and total bytes;
- third-party count and purpose;
- interaction and animation constraints;
- monitoring owner and regression threshold.

Do not silently leave objectives blank. Label provisional or proposed budgets
as such, not as universal guarantees. A concept objective may guide learning
without owner acceptance; it is not production evidence.

## Protect the critical path

- Render meaningful content without waiting for nonessential scripts.
- Reduce, defer, or remove unused JavaScript and third parties.
- Reserve dimensions for media and dynamic regions.
- Size and format images for actual rendering conditions.
- Load fonts intentionally and avoid unused weights; preconnect to any
  origin that serves critical assets, preload only genuinely critical font
  files, and subset by script coverage so unused alphabets never ship.
- Lazy-load below-the-fold media without delaying likely next actions, and
  mark the one critical above-the-fold image as high fetch priority.
- Ship short ambient loops as compressed muted video, not animated GIF: a
  video element with autoplay, muted, loop, and inline playback is a
  fraction of the bytes, and its reduced-motion fallback is a poster frame.
  Where a target browser needs it, a video source inside a picture-style
  fallback with a still alternative covers the gap.
- Virtualize or content-gate very long lists; hundreds of offscreen rows
  cost layout and memory whether or not they are visible.
- Batch reads and writes of layout so they do not interleave, and move long
  computation off the main thread; an interaction budget dies in exactly
  these two places.
- Avoid render-blocking decoration, layout thrashing, and unbounded scroll work.
- Cache immutable assets and respect content freshness.

## Account for environmental and lifecycle cost

Scale the review to the feature. For heavy media, AI inference, 3D, continuous
updates, analytics, embeds, or other third parties, examine creation or
generation, storage, delivery, repeat use, device work, external processing,
maintenance, cache invalidation, and retirement. Record the user value,
frequency, major resource drivers, owner, and review or removal condition.

Provide a lower-impact path when it preserves the task: user-initiated loading,
responsive or shorter media, a poster or static summary, cached or precomputed
results, batched updates, fewer requests, reduced-data behavior, or removal of
low-value processing. Keep essential content and controls available when the
heavy feature, provider, or network is unavailable.

Measure bytes, requests, execution, inference or processing frequency, storage,
and device cost in proportion to the decision. Do not claim a feature or site
is sustainable, carbon-neutral, or lower-carbon without a credible method,
defined boundary, current evidence, and accountable review.

## Design resilient states

Performance is part of the experience. Define:

- meaningful loading, optimistic, stale, partial, offline, and retry states;
- input behavior while work is pending;
- priority among content, controls, proof, and decoration;
- fallback when video, 3D, maps, analytics, or embeds are unavailable;
- reduced-data or low-power behavior when relevant.

For WebGL, 3D, or sustained media effects, define load, memory, GPU, thermal,
battery, input, context-loss, and tab-background behavior with a useful static
or low-power fallback. Escalate complex spatial work to the relevant specialist.

Do not hide delay behind an endless shimmer or animate placeholders that do not
resemble final content.

## Measure

Use lab checks during development and field data when available. Record:

- route, build ID, browser, device profile, network, cache state, and date;
- measured LCP, INP or interaction evidence, CLS, and supporting diagnostics;
- resource totals and major contributors;
- before/after comparison for meaningful changes;
- limitations when no field data exists.

Test production-like builds. A development-server score is not release evidence.
Treat a single synthetic score as a clue, not a promise of user experience.
