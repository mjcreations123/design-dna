# Conditional tooling adapters

Use this only when an existing design or verification tool is present or the
user explicitly authorizes one. Import context and evidence, not a vendor's
default aesthetic.

## Contents

- [Apply the adapter rules](#apply-the-adapter-rules)
- [Normalize design-system context](#normalize-design-system-context)
- [Normalize state and visual evidence](#normalize-state-and-visual-evidence)
- [Normalize motion and 3D assets](#normalize-motion-and-3d-assets)
- [Use project-local drift hooks carefully](#use-project-local-drift-hooks-carefully)
- [Keep vendor boundaries explicit](#keep-vendor-boundaries-explicit)

## Apply the adapter rules

1. Detect existing files, packages, connections, documentation, and project
   ownership before suggesting a tool.
2. Prefer read-only inspection. Do not install, sync, publish, overwrite, or
   approve a baseline without authority.
3. Pin the source revision or retrieval date.
4. Normalize results into Design DNA records rather than making the vendor
   tool a new source of truth.
5. Mark incomplete mappings and screenshot-inferred behavior as `unknown`.
6. Verify the rendered implementation; a tool score or generated output is not
   final aesthetic, accessibility, or production evidence.

## Normalize design-system context

When Figma variables or Code Connect, Storybook, a component registry, package
documentation, or token files exist, capture:

- source, revision, owner, and supported platform;
- component name, code mapping, supported properties and variants;
- state, content, responsive, accessibility, and usage constraints;
- examples and real consumers;
- token source, aliases, themes or modes, transforms, and generated outputs;
- mapping confidence: confirmed, partial, provisional, or unknown;
- deprecation, migration, and drift state.

Do not generate replacement primitives until current supported components and
constraints are understood. Visual layers copied from another tool are not
assumed to remain bound to the production system.

For maintained multi-platform tokens, DTCG-compatible interchange may be used
when the project already supports it. Keep brand/expression tokens distinct
from functional semantic roles. Run read-only source-to-transform-to-output
drift checks; never silently push or synchronize.

## Normalize state and visual evidence

When Storybook or an equivalent state catalog exists, map critical component
and route contracts into executable stories or tests. Cover only relevant
combinations of state, viewport, theme, locale, content length, input, motion,
and failure behavior; record exclusions.

When Chromatic, Playwright screenshots, or another visual-regression system
exists, require:

- exact baseline and candidate build identities;
- pinned browser, operating system, fonts, DPR, color profile, locale,
  timezone, data, theme, and motion settings where material;
- raw baseline, actual, and diff artifacts;
- documented masks and dynamic regions;
- stale-baseline detection;
- explicit human approve or reject.

The baseline protects authored asymmetry, crops, spacing, and resting frames;
it must not normalize the design toward a generic default.

## Normalize motion and 3D assets

For Rive, Lottie or dotLottie, Spline, model-viewer, canvas, WebGL, or another
runtime asset, use the motion-asset contract template. Record:

- asset path, hash, version, owner, license, and export source;
- state, input, event, object, and variable names and types;
- trigger, autoplay, loop, settle, interruption, cleanup, and error behavior;
- supported input methods and runtime/browser boundaries;
- intrinsic and delivered size, CPU/GPU or frame evidence, load policy, and
  device budget;
- poster or static equivalent, reduced behavior, context-loss recovery, and
  no-runtime fallback.

Route implementation-specific 3D work to an appropriate specialist. Design DNA
owns the purpose, art direction, state meaning, and fallback contract.

## Use project-local drift hooks carefully

An established project may opt into a local pre-commit, pre-push, editor, or
task-runner hook for fast drift feedback. Do not install, enable, or modify a
hook silently. Require explicit project-local authorization and document the
command, scope, owner, expected runtime, and removal path.

A local drift hook must:

- inspect only the changed or explicitly selected scope;
- be deterministic and read-only, with no source rewrite, synchronization,
  dependency install, network mutation, publication, or baseline approval;
- identify the exact source, transform, generated output, component, story,
  route, or artifact that drifted;
- fail or warn according to a documented project policy;
- provide a documented bypass for exceptional work, including the reason,
  owner, and follow-up record rather than hiding that the check was skipped.

Changed-scope feedback is not whole-project or release evidence. Run the
project's clean full-scope drift scan before release, migration, baseline
approval, or a material tool/configuration change, and retain its exact
revision and result. If a suitable hook is absent, document the optional
command instead of silently installing infrastructure.

## Keep vendor boundaries explicit

Figma, Storybook, Tokens Studio, Chromatic, Rive, Lottie, Spline, and similar
tools are optional adapters, not dependencies. Do not:

- install them because they are mentioned here;
- treat their libraries, generated themes, or starter layouts as art
  direction;
- treat predictive attention, automated accessibility, or quality scores as
  user evidence or certification;
- assume a screenshot specifies responsive or interactive behavior;
- claim round-trip, pixel-perfect, or design-system parity without a checked
  mapping and rendered comparison.
