# Batch Study unprimed site observation

Complete this before seeing sibling implementations, a convergence diagnosis,
or a list of suspected tells. Bind it to the exact build and capture hashes.
Keep confidential pixels or copy out of this record unless its classification
and retention allow them.

## Evidence identity

- Study ID:
- Neutral specimen label:
- Internal site ID, if the protocol permits the reviewer to know it:
- Reviewer ID:
- Build/source identity:
- Pre-review study-contract snapshot path and SHA-256:
- Capture-set SHA-256:
- Observed at (zoned timestamp):
- Frozen at (zoned timestamp, after observation):
- Sibling output seen before observation: yes / no / unknown
- Diagnostic material seen before observation: yes / no / unknown

Copy those values exactly into `unprimed_review.capture_set_sha256`,
`observed_at`, `frozen_at`,
`sibling_output_seen_before_observation`, and
`diagnostic_material_seen_before_observation`. Comparison readiness requires
both exposure answers to be `no`/`false`.

## Reviewed capture manifest

List every reviewed route, viewport class, and capture mode. Add rows for
additional routes, states, motion preferences, themes, locales, directions,
or interaction evidence; do not compress a multi-route site into one nominal
wide/narrow pair. Use the contract modes `viewport` or `full-page` for bound
Batch captures. Label any anchored-region, temporal, or interaction artifact
as supplemental evidence rather than substituting it for required captures.

| Page or route | State or task | Viewport class | CSS viewport | Capture mode | Artifact path | SHA-256 | Review coverage or limitation |
|---|---|---|---|---|---|---|---|
|  |  |  |  | viewport / full-page |  |  |  |

## First observation

- What is the site for, based only on the rendered experience?
- What makes the first screen recognizable as this subject rather than an
  interchangeable category page?
- What organizing logic governs the body?
- What feels authored, useful, or unusually well resolved?
- What feels unexplained, generic, repetitive, careless, or difficult to use?

## Whole-page behavior

- Hierarchy, silhouette, density, pacing, and ending:
- Typography and reading behavior:
- Material, color, media, and edge/container behavior:
- Navigation, interaction, motion, and feedback:
- Cross-viewport and route-specific transformations:
- Truth, provenance, accessibility, or performance limitations visible within
  this review scope:

## Contextual findings

For every high or medium finding, record location, evidence, user impact,
likely cause, and the condition that would verify a fix. Do not infer
authorship or score the site by a style-ingredient list. When the finding is
added to the Batch Study contract, declare both `severity` (`low`, `medium`,
`high`, or `critical`) and `impact` (`informational`, `bounded`, `material`,
or `release-blocking`) so the later human disposition can distinguish a
material unresolved issue from a bounded note.

## Disposition

- Strongest defensible project-specific decision:
- Highest-priority open issue:
- Review status: complete / incomplete
- Limitations:
- Frozen review record path:

After freezing, record this file's SHA-256 in the study contract or audit
record that references it. Do not append a self-hash to this file.
