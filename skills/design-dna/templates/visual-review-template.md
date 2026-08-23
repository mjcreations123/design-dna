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

## Canonical evidence-record status

- Project Contrast record path and current status, if active:
- Direction Challenge record path and current status, if active:
- Record/auditor result consulted, with date and limitation:

This review may summarize evidence but does not advance, approve, or replace a
canonical Project Contrast or Direction Challenge lifecycle record.

## Contents

- [Rendered review](#rendered-review)
- [Review scope and capture rationale](#review-scope-and-capture-rationale)
- [First-impression and surface-fidelity review](#first-impression-and-surface-fidelity-review)
- [Connected public experience closure](#connected-public-experience-closure-when-selected)
- [Preship and specificity closure](#preship-and-specificity-closure)
- [Project Contrast review context](#project-contrast-review-context)
- [Direction Challenge review context](#direction-challenge-review-context-when-selected)
- [Typography stress evidence](#typography-stress-evidence)
- [Narrow-screen pacing and explanatory-graphic evidence](#narrow-screen-pacing-and-explanatory-graphic-evidence)
- [Findings](#findings)
- [Owner and release state](#owner-and-release-state)
- [Project-specific review](#project-specific-review)

## Rendered review

- Build or artifact ID:
- Final implementation reviewed: __REPLACE_WITH_YES_NO_OR_PARTIAL__
- Reviewer relationship: __REPLACE_WITH_RELATIONSHIP_OR_NOT_YET_REVIEWED__

| Route/state | Viewport/context | Rendered PNG path and SHA-256 | Observation |
| --- | --- | --- | --- |
|  |  |  |  |

One row can be enough for a small ordinary project. Add rows only for materially
different routes, states, content, containers, inputs, languages, preferences,
or failure conditions that actually apply. Each row binds a decodable PNG;
structured reports, logs, DOM evidence, recordings, and manual observations
remain separately typed evidence and cannot be renamed or substituted as a
screenshot.

## Review scope and capture rationale

For Standard or stronger work, declare every route/body represented by the
schema-3 render report. Mark a route/body `applicable` only when its exact
wide/narrow capture IDs are bound below. Mark it `not-applicable` only when it
does not add a materially distinct reviewed body, and say why. This is a
coverage decision for this build, not a required route count or visual recipe.

| Route/state or reviewed body | Material review risk or not-applicable reason | Wide capture ID | Narrow capture ID | Disposition |
| --- | --- | --- | --- | --- |
|  |  |  |  | applicable / not-applicable / blocked |

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

| Review focus | Applicability or disposition | Rendered PNG path and SHA-256 | Observation or limitation |
| --- | --- | --- | --- |
| First impression and surface fidelity | applicable / not-applicable / blocked |  |  |

## Connected public experience closure (when selected)

Use only when the selected direction record names a detailed, connected,
customer-facing, app-like, or client-demonstration experience, or when the
public promise depends on linked content or state. Bind the actual direct-entry
and path evidence; do not treat a collection of attractive routes as proof of
continuity.

The selected `connected-public-experience.json` record owns the canonical
applicability, selected-root model, status crosswalk, and final functional
closure. For an applicable record, its exact reviewed build, rendered evidence,
functional artifact or recorded result, and direct-entry plus recovery or
continuation proof must agree with this review. A justified not-applicable
record needs its reason; a blocked record remains a limitation, not a pass.

- Subject and useful next move on direct entry:
- Material route questions and cross-route relationship result:
- Representative action, outcome, continuation, and recovery result:
- Delivery/content/behavior status-crosswalk treatment:
- Boundary/disclosure hierarchy result:
- Identity-to-content-model fit result:
- Staff/admin public/back-office split and Operate-mode result, if requested:

| Closure | Applicability or disposition | Rendered or functional evidence | Result or limitation |
| --- | --- | --- | --- |
| Connected public experience | applicable / not-applicable / blocked |  |  |

## Preship and specificity closure

For Standard or stronger work, bind the actual final rendered evidence used to
close the adversarial specificity review and the preship gate. A `not-applicable`
or `blocked` decision still needs a precise reason and bound review evidence;
neither is a hidden pass. This records review scope and limitations, not an
automatic beauty or release verdict.

| Closure | Applicability or disposition | Rendered PNG path and SHA-256 | Result or limitation |
| --- | --- | --- | --- |
| Adversarial specificity review | applicable / not-applicable / blocked |  |  |
| Preship gate | applicable / not-applicable / blocked |  |  |

## Project Contrast review context

Complete only when the Project Contrast capability is active. Freeze the first
observation before looking at nearest-sibling diagnostic language. The goal is
to make a reviewer-facing, project-specific decision; it is not a numerical
  uniqueness test or a requirement to change every visual ingredient.

- Canonical Project Contrast record path and current status:
- Selected-direction direct reviewable wide/narrow artifact:
- Counter-direction decision-proportionate artifact or record:
- Exact inability, impact, and next reviewable action, if the declared
  counter-answer cannot yet be reviewed:
- Comparison authority and limitation:
- Closest authorized sibling, inherited system, or no-comparator disposition:
- Unprimed first observation of this candidate:
- What remains project-specific after subject nouns, dominant media, accent,
  and motion are mentally removed:
- Which shared foundation is correct and why:
- Which repeated encounter-level relationship is unexplained, if any:
- Earliest cause to reopen and rerender status:

| Candidate route/state | Comparator or limitation | Encounter/body relationship | Project reason or concern | Wide/narrow evidence | Disposition | Rerun |
| --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |

For Project Contrast, do not mark the selected candidate's comparison reviewed
from prose alone: bind its relevant wide/narrow rendered evidence and record
the actual counter-answer evidence. The counter-answer remains proportional to
the decision and may truthfully be a nonrendered content model, annotated
wireframe, reference decomposition, or other reviewable record; this template
does not turn it into a mandatory wide/narrow counter render. When Direction
Challenge is active, its separate canonical record requires wide/narrow proof
for the selected and explicitly rejected roots. Record an exact inability and
resulting limitation whenever either required evidence boundary is not met.

## Direction Challenge review context (when selected)

- Canonical Direction Challenge record path and current status:
- Selected root and direct reviewable wide/narrow proof artifacts:
- Rejected or counter root and direct reviewable wide/narrow proof artifacts:
- Exact inability, impact, and next reviewable action, if a proof is missing:
- Review limitation and implementation-boundary result:
- Direction Challenge proof-to-build delta evidence:

When the final build differs from selected proof, bind a project-relative
artifact plus SHA-256 that names the selected proof build, final build, and
reviewed changed decisions. Use `not-applicable` only when the final build
exactly matches the selected proof build.

An independent unprimed Direction Challenge review is evidence that a reviewer
saw the proof before root labels and selection rationale. It can expose a blind
spot, but it is not owner acceptance or target-user validation. Record owner
acceptance separately, only where the project requires it, with the accountable
owner or owner-authorized-human relationship and its own evidence.

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
- Pre-heading label, eyebrow, or kicker disposition (or none used): independent
  visitor fact versus duplicated adjacent subject, with route/state:
- Internal-rationale, producer-process, record, or back-end/content-model
  vocabulary leak disposition (or none found), with route/state:
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

- Reviewer conclusion: __REPLACE_WITH_SCOPE_AND_CURRENT_CONCLUSION__
- Owner disposition: __REPLACE_WITH_ACCEPTED_REJECTED_PENDING_OR_NOT_APPLICABLE__
- Release blockers:

Record the exact scope and current state. `owner accepted` requires review by an
accountable owner or owner-authorized human. A blocked conclusion must name the
unresolved blocker; any other conclusion must record blockers as resolved,
none, or not applicable. Template defaults and producer review are not
evidence of owner acceptance.

## Project-specific review

Optional. Add any perceptual, content, cultural, interaction, craft,
maintenance, or operational observations that matter to this project. Do not
borrow a fixed list of aesthetic traits merely because another project used it.
