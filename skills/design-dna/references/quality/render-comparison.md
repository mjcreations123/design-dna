# Cross-build rendered comparison

Use the optional offline comparator when an accepted baseline and a candidate
were captured with the same frozen schema-v3 rendered-review contract. The tool
validates both complete local evidence packages before it compares their PNG
captures. It never decides whether a change is good, updates a baseline, or
turns a pixel count into approval.

## Capture compatible evidence

Create baseline and candidate packages from frozen local files or directories
with the same routes, capture manifest, profiles, scenarios, preferences, and
settling policy:

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/rendered_review.mjs" "BASELINE_BUILD" --output "BASELINE_REVIEW" --build-id BASELINE_BUILD_ID --capture-manifest "CAPTURE_MANIFEST"
node "<DESIGN_DNA_SKILL_ROOT>/scripts/rendered_review.mjs" "CANDIDATE_BUILD" --output "CANDIDATE_REVIEW" --build-id CANDIDATE_BUILD_ID --capture-manifest "CAPTURE_MANIFEST"
```

Use the original output packages. Their ownership markers are path-bound, so
copied or relocated evidence is rejected.

## Compare

Use Node.js 20 or newer. Playwright may resolve normally from the calling
environment. If it lives in another `node_modules` directory, set
`DESIGN_DNA_PLAYWRIGHT_MODULE_DIR` to that directory.

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/compare_render_reviews.mjs" "BASELINE_REVIEW/render-review.json" "CANDIDATE_REVIEW/render-review.json" --output "COMPARISON_OUTPUT" --comparison-id "BUILD_A-vs-BUILD_B" --masks none
```

On PowerShell:

```powershell
node "<DESIGN_DNA_SKILL_ROOT>\scripts\compare_render_reviews.mjs" "BASELINE_REVIEW\render-review.json" "CANDIDATE_REVIEW\render-review.json" --output "COMPARISON_OUTPUT" --comparison-id "BUILD_A-vs-BUILD_B" --masks none
```

Supply `--browser-executable "FILE"` when browser discovery cannot find a local
Chromium-family browser. A maintainer checkout is not required: the comparator
loads `schemas/render-review.schema.json` from the installed skill tree.

## Output and interpretation

The new output directory contains:

- `render-comparison.json`, a bounded machine report;
- `comparison.html`, an offline three-column review sheet;
- baseline, actual-candidate, and pixel-difference PNGs for every capture;
- `.design-dna-render-comparison.json`, a path-bound output marker.

The diff colors every changed decoded RGBA pixel magenta and leaves unchanged
pixels as a subdued grayscale reference. Reports include per-capture and total
mismatch pixel counts and ratios. These are factual diagnostics, not a
perceptual threshold, accessibility result, visual-quality score, or approval.

The report also binds both build, source, report, capture-contract, and
execution-environment identities. A baseline more than 30 days older than the
candidate is marked stale. It can still be reviewed, but the reviewer must
decide whether its product, browser, and design-system context remains useful.

Schema-v3 packages contain explicit route, scenario, profile, and capture
identities. The comparator still requires an identical full capture contract,
route order, and matched capture set so the pixels describe the same reviewed
conditions. Do not edit evidence to make incompatible packages appear
compatible; recapture both builds with one manifest.

## Safety boundary

The comparator:

- accepts only complete, frozen local render reports;
- rejects URLs, remote-target reports, symbolic links, path traversal, unsafe
  Windows path forms, missing files, incompatible contracts, and tampering;
- blocks every browser request and decodes PNGs on `about:blank`;
- creates a new output transaction and never replaces a prior comparison;
- applies no masks; `--masks none` is an explicit declaration;
- never updates a baseline or emits an automatic accept or pass result;
- persists no absolute input paths.

## Human decision

Review every triplet in page context, then record accept, revise, reject, or
insufficient evidence in the project visual-review record. Bind that human
decision to both build IDs and the comparison-report SHA-256. Do not mutate the
machine report into an approval.
