# Browser, engine, and device support

Use this when implementation or readiness claims depend on web-platform
compatibility. A Chromium screenshot is evidence for that exact Chromium run,
not for every browser, operating system, assistive-technology pairing, or real
device.

## Set the support contract

Prefer an existing product support policy, contractual requirement, audience
evidence, and production analytics. Record a compact matrix with:

- browser and rendering engine, version policy, operating system, and whether
  the condition is real hardware, an emulator, or desktop emulation;
- supported input and assistive-technology pairings when they affect a critical
  task;
- support level: full task support, core-content/fallback support, explicitly
  unsupported, or unknown;
- critical routes, states, and capabilities that make the row materially
  different;
- evidence date, build, test result, limitations, and accountable owner.

Do not invent a universal "last two versions" promise or silently infer support
from the developer's own browser. If no owner-approved matrix exists, write a
provisional test hypothesis from the audience, delivery environment, and
features used. Label it provisional and disclose environments not exercised.

Use current MDN browser-compatibility data and Baseline status to screen each
consequential HTML, CSS, JavaScript, media, and platform feature. Baseline is a
feature-availability summary, not a substitute for this product's runtime,
accessibility, usability, performance, or device tests. A limited-availability
feature needs a tested fallback, a deliberately narrower support contract, or a
different implementation.

## Test materially different conditions

Exercise every critical route and task in each materially different supported
engine represented by the matrix. Chromium-family evidence does not cover
Gecko or WebKit. Select actual browsers from the contract; do not add engines
merely to make a checklist longer.

Check the mechanisms most likely to vary:

- font loading, shaping, synthesis, metrics, wrapping, form controls, native
  validation, autofill, password managers, and date or number input behavior;
- sticky and fixed positioning, viewport units, safe areas, scrollbars,
  overscroll, history, focus, dialogs, popovers, and keyboard traversal;
- image, audio, video, canvas, WebGL, color, print, downloads, uploads, and
  permission prompts;
- touch, hover, coarse pointer, orientation, virtual keyboard, focus zoom,
  browser chrome, reduced motion, forced colors, and text enlargement;
- loading, offline, blocked-feature, unsupported-feature, and recovery paths.

Use real iOS, Android, touch, camera, media, GPU, or virtual-keyboard hardware
when emulation cannot establish the claim. A desktop viewport preset changes
dimensions and selected signals; it does not become a phone, mobile browser,
network, thermal envelope, or assistive-technology pairing.

## Preserve a usable fallback

Prefer semantic HTML and progressive enhancement. When a supported environment
cannot run an enhancement, keep the core information and task usable or provide
the explicit fallback promised by the support matrix. Never hide a broken
critical path behind an unsupported-browser message when a simpler compatible
path is practical.

Record exact browser, engine, version, OS, hardware/emulation status, route,
state, build, and date. Report an untested or failing matrix row as a scoped
limitation; do not generalize one green engine into "cross-browser compatible."
