# Performance

Use this when planning assets, fonts, scripts, motion, embeds, rendering, or production readiness.

## Set an objective

Use the project's measured baseline and contractual targets first. If none exist, propose route-specific budgets and obtain owner acceptance. Include:

- critical route and representative device/network;
- Core Web Vitals objectives;
- transferred JavaScript, CSS, fonts, images, and total bytes;
- third-party count and purpose;
- interaction and animation constraints;
- monitoring owner and regression threshold.

Do not silently leave objectives blank. Label proposed budgets as proposals, not universal guarantees.

## Protect the critical path

- Render meaningful content without waiting for nonessential scripts.
- Reduce, defer, or remove unused JavaScript and third parties.
- Reserve dimensions for media and dynamic regions.
- Size and format images for actual rendering conditions.
- Load fonts intentionally and avoid unused weights.
- Lazy-load below-the-fold media without delaying likely next actions.
- Avoid render-blocking decoration, layout thrashing, and unbounded scroll work.
- Cache immutable assets and respect content freshness.

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

Do not hide delay behind an endless shimmer or animate placeholders that do not resemble final content.

## Measure

Use lab checks during development and field data when available. Record:

- route, build ID, browser, device profile, network, cache state, and date;
- measured LCP, INP or interaction evidence, CLS, and supporting diagnostics;
- resource totals and major contributors;
- before/after comparison for meaningful changes;
- limitations when no field data exists.

Test production-like builds. A development-server score is not release evidence. Treat a single synthetic score as a clue, not a promise of user experience.
