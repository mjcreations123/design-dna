---
schema_version: 1
created_with: "__DESIGN_DNA_VERSION__"
classification: "internal"
evidence_contract: "proportional-evidence-v1"
findings_contract: "visual-review-findings-v2"
---

# Visual review

<!-- proportional-evidence-v1 -->

Review the final implementation round as rendered. Add project-specific review
notes freely; the compact tables below exist only to bind coverage and finding
lifecycle. Never infer checks that were not performed.

## Contents

- [Rendered review](#rendered-review)
- [First-impression and surface-fidelity review](#first-impression-and-surface-fidelity-review)
- [Typography stress evidence](#typography-stress-evidence)
- [Narrow-screen pacing and explanatory-graphic evidence](#narrow-screen-pacing-and-explanatory-graphic-evidence)
- [Findings](#findings)
- [Owner and release state](#owner-and-release-state)
- [Project-specific review](#project-specific-review)

## Rendered review

- Build or artifact ID:
- Final implementation reviewed: no
- Reviewer relationship: producer-self

| Route/state | Viewport/context | Rendered PNG path and SHA-256 | Observation |
| --- | --- | --- | --- |
|  |  |  |  |

One row can be enough for a small ordinary project. Add rows only for materially
different routes, states, content, containers, inputs, languages, preferences,
or failure conditions that actually apply. Each row binds a decodable PNG;
structured reports, logs, DOM evidence, recordings, and manual observations
remain separately typed evidence and cannot be renamed or substituted as a
screenshot.

## First-impression and surface-fidelity review

Use when visual character, public credibility, owner taste, or a prior
direction rejection is material. Accessibility, working behavior, and a clean
technical report are necessary but do not establish that the visual answer is
good.

- Surface-review relationship and rationale/diagnostic exposure before viewing:
- Exact route/state/viewport and rendered evidence:
- What the first encounter communicates or invites:
- Does it feel like a credible public surface for this subject and audience?
  Why or why not:
- What feels project-specific, convincing, beautiful, useful, or worth
  protecting:
- What feels generic, artificial, maker-facing, visually weak, or wrong:
- Narrow-condition encounter result, when relevant:
- Disposition: keep / revise / reopen direction / reject / not applicable:

## Typography stress evidence

Record the real rendered roles that were easiest to overlook, not compliance
with a house scale. Use the face, script, audience, contrast, casing, tracking,
viewport, and surrounding composition to judge whether each role remains
comfortable to read. A numerical value is diagnostic evidence, never an
automatic pass or failure.

- Smallest ordinary-reading role actually inspected:
- Smallest interactive, caption, credit, legend, or utility role actually inspected:
- Narrow-width and text-spacing result:
- Repeated compact-uppercase or tracking pattern disposition:
- Exact route/state and rendered evidence:

Delete a line only when that role truly does not exist, and say why in the
project-specific review. Do not hide weak hierarchy by calling public text
microcopy, metadata, legal copy, or decoration.

## Narrow-screen pacing and explanatory-graphic evidence

Record only the roles that apply. There is no universal mobile page length or
screen-count target.

- First meaningful subject content or useful action, with route/state/width:
- Intervening sequence or measured runway and its project-specific effect:
- Later meaningful anchors whose distance changed the task or reading experience:
- Deliberate long-form or spatial rationale, or revision disposition:
- Content-bearing diagram, map, chart, or process drawing inspected:
- Teaching-model parity result for any briefing, tutorial, schematic, example, or preview, including names, topology, encodings, action unit, and completion condition:
- Direct-entry first-action result before or at the task artifact:
- Narrow label-and-relationship result, including recompose, contextual pan or zoom, equivalent path, or another chosen response:
- Overview/detail orientation result when the core artifact requires panning:
- Initial-view inventory result for consequential callouts, unknowns, statuses, or relationship categories:
- Initial/intermediate/terminal position result, including whether the start reads as a located endpoint rather than an empty or uninitialized control:
- Comparison task result, including whether equivalent fields remain meaningfully comparable:
- Deep-path comparison context, including record-key, selected-lens, and reacquisition result:
- Consequential dependency order after reflow, including eligibility/exclusion or prerequisite/action pairs:
- Decorative line, connector, frame, or continuity-device result at the pressure point:
- Composite reading-ground result where tonal, image, texture, gradient, or motion boundaries pass near text:
- Caption/body result where a sibling band, sticky surface, or positioned peer could cover rendered text:
- Reused-source observation result when different crops or treatments claim different evidence:
- Repeated status/disclosure hierarchy and distinct-consequence disposition:
- Referential copy result where labels or counts describe visible structure, relationships, or state:
- Domain-symbol ambiguity result where decorative labels could imply a real token, value, or selection:
- Repeated label/value separation result at narrow width and with applicable text-spacing/localization pressure:
- Exact rendered evidence:

## Findings

Use `not-applicable` for a reviewed concern that does not apply. Critical, high,
and medium findings must be `verified` or `not-applicable`; producer self-review
cannot convert an unresolved issue into owner acceptance.

| Severity | Confidence | Evidence | User/release impact | Cause | Fix or disposition | Rerun verification | Status | Owner |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |  |

## Owner and release state

- Reviewer conclusion: self-reviewed candidate
- Owner disposition: pending
- Release blockers:

Record the exact scope and current state. `owner accepted` requires review by an
accountable owner or owner-authorized human. A blocked conclusion must name the
unresolved blocker; any other conclusion must record blockers as resolved,
none, or not applicable.

## Project-specific review

Optional. Add any perceptual, content, cultural, interaction, craft,
maintenance, or operational observations that matter to this project. Do not
borrow a fixed list of aesthetic traits merely because another project used it.
