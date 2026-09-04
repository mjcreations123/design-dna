# Codex behavior

Use the shared Design DNA workflow without duplicating rules in plugin metadata.

- The owner's standing orders in SKILL.md (no producer design, no quality-
  reducing shortcuts, required first-screen and final phases of one gate
  program, and the final verdict line quoted verbatim)
  applies on this host exactly as written. There is no host-specific relief.
- Invoke explicitly with `$design-dna`; natural-language discovery may also
  select it for relevant work.
- Inspect repository instructions and the existing working state before editing.
- Use browser, rendering, image, file, and test capabilities when they
  materially improve the requested result.
- For browser-capable work, inspect the actual route across relevant sizes,
  states, and input modes.
- Before a task that requires packaged browser evidence, run the installed
  `scripts/browser_preflight.mjs` from the target project (or the package
  `manage_install.py doctor --host codex --browser-project ABSOLUTE_PROJECT`
  command). It resolves only an explicit absolute module directory, the
  project's exact `node_modules`, a recognized source checkout's pinned
  maintainer modules, or exact `node_modules` directories inside the installed
  skill. It never installs,
  downloads, or globally scans. Its pass proves the operator process, not that
  Codex loaded the skill; a failure keeps required rendered QA blocked.
- For a no-browser task, perform safe source and reasoning checks, but keep any
  website candidate whose required rendered QA cannot run blocked from
  presentation. Do not replace a packaged check with homemade, hand-written,
  lower-threshold, or deferred evidence.
- Keep mutable direction, evidence, and review records project-local. Attribute
  owner decisions only when the owner made them; producer or automated evidence
  may remain explicitly provisional without becoming owner approval.
- Pair Design DNA with specialist skills when deep accessibility, performance,
  security, SEO, or deployment work is requested.
- A direct-skill update does not require abandoning the active maintenance task:
  finish source edits, static validation, packaging, and filesystem checks in
  the current task. To test whether subsequent model behavior actually loaded
  the new instructions, start a fresh task and reinvoke the skill. If the
  updated behavior does not appear there, restart Codex and verify the route;
  filesystem parity alone does not prove host activation or reload behavior.

Installation, packaging, cachebusting, and synchronization are maintainer
operations outside the runtime skill.
