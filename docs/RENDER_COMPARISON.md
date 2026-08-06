# Cross-build rendered comparison

The portable copy of this operating guide lives at
[`skills/design-dna/references/quality/render-comparison.md`](../skills/design-dna/references/quality/render-comparison.md)
and ships with direct skill installations.

`compare_render_reviews.mjs` is an optional, offline evidence tool. It compares
two complete local `rendered_review.mjs` packages only after validating their
path-bound markers, report identities, capture contracts, screenshot paths,
byte counts, SHA-256 hashes, and PNG dimensions.

It does not decide whether a change is good. A zero-pixel difference and a
large difference both produce `human-accept-reject-required`.

## Capture compatible evidence

Create baseline and candidate reviews from frozen local files or directories
using the same routes, capture manifest, profiles, scenarios, preferences, and
settling policy:

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/rendered_review.mjs" "BASELINE_BUILD" --output "BASELINE_REVIEW" --build-id BASELINE_BUILD_ID --capture-manifest "CAPTURE_MANIFEST"
node "<DESIGN_DNA_SKILL_ROOT>/scripts/rendered_review.mjs" "CANDIDATE_BUILD" --output "CANDIDATE_REVIEW" --build-id CANDIDATE_BUILD_ID --capture-manifest "CAPTURE_MANIFEST"
```

Use the original output packages. Their ownership markers are intentionally
path-bound, so copied or relocated evidence is rejected.

## Compare

Use Node.js 20 or newer. The comparator loads Playwright through normal Node
resolution. When Playwright lives in another `node_modules` directory, point
`DESIGN_DNA_PLAYWRIGHT_MODULE_DIR` to that directory explicitly:

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/compare_render_reviews.mjs" "BASELINE_REVIEW/render-review.json" "CANDIDATE_REVIEW/render-review.json" --output "COMPARISON_OUTPUT" --comparison-id "BUILD_A-vs-BUILD_B" --masks none
```

On PowerShell:

```powershell
node "<DESIGN_DNA_SKILL_ROOT>\scripts\compare_render_reviews.mjs" "BASELINE_REVIEW\render-review.json" "CANDIDATE_REVIEW\render-review.json" --output "COMPARISON_OUTPUT" --comparison-id "BUILD_A-vs-BUILD_B" --masks none
```

For an explicit external module directory, set
`DESIGN_DNA_PLAYWRIGHT_MODULE_DIR` before the command. A maintainer checkout is
not required: the comparator reads its render-review schema from the installed
skill tree.

Supply `--browser-executable "FILE"` when browser discovery cannot find a local
Chromium-family browser.

## Output and interpretation

The new output directory contains:

- `render-comparison.json`, validated by
  `maintainer/schemas/render-comparison.schema.json`;
- `comparison.html`, an offline three-column review sheet;
- a baseline, actual candidate, and pixel-diff PNG for every capture;
- `.design-dna-render-comparison.json`, a path-bound output marker.

The diff colors every changed decoded RGBA pixel magenta and leaves unchanged
pixels as a subdued grayscale reference. Reports include per-capture and total
mismatch pixel counts and ratios. These values are factual diagnostics, not a
perceptual threshold, accessibility result, visual-quality score, or approval.

The report also pins both build/source/report identities, capture-contract
digests, execution environments, environment differences, and baseline age.
A baseline more than 30 days older than the candidate is explicitly marked
stale. It may still be reviewed, but the reviewer must decide whether its
product, browser, and design-system context remains authoritative.

## Safety boundary

The comparator:

- accepts only complete, frozen local render reports;
- rejects URLs, remote-target reports, symlinks, junction-like symbolic
  entries, path traversal, Windows alternate-data-stream paths, missing files,
  incompatible contracts, and tampered screenshots;
- blocks every browser request and decodes PNGs on `about:blank`;
- creates a new output transaction and never replaces a prior comparison;
- applies no masks; `--masks none` is an explicit required declaration;
- never updates a baseline or emits an automatic accept/pass result;
- persists no absolute input paths.

Current schema-v3 render reports bind explicit route, scenario, profile, and
capture identities. The comparator still requires the same full capture
contract, route order, and matched capture set so the compared pixels describe
the same reviewed conditions. Do not “repair” incompatibility by editing
evidence. Recapture both builds with one manifest.

## Human decision

Review every triplet in page context, then record one of:

- accept candidate;
- revise candidate;
- reject candidate;
- insufficient evidence.

Store that decision in the project’s human visual-review record, bound to both
build IDs and the comparison-report SHA-256. Do not mutate the machine report
into an approval.
