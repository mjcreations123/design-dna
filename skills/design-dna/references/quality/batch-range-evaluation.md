# Batch Study evaluation

Use this protocol when planning and evaluating three or more unrelated sites
from separate briefs. It tests whether the working method transfers across contexts;
it does not detect authorship, score aesthetics, or create a list of ingredients
to avoid.

## Contents

- [Set up the study before building](#set-up-the-study-before-building)
- [Capture without diagnostic priming](#capture-without-diagnostic-priming)
- [Compare derivation rather than ingredients](#compare-derivation-rather-than-ingredients)
- [Record human contextual disposition](#record-human-contextual-disposition)
- [Audit the evidence](#audit-the-evidence)

## Set up the study before building

1. Write each brief without reference to the other study sites. Freeze each
   brief as a project-local file and record its SHA-256 before implementation.
2. Freeze a separate source packet for every site and hash it. Record the
   producer/build context, sibling-output exposure state and timing, allowed
   shared tooling, and every shared artifact or exception. This
   implementation-isolation attestation is distinct from brief independence.
   Unique brief or source-packet bytes do not prove isolation; the record stays
   inspectable human evidence and must name actual context, not only case IDs.
3. Give every site an isolated build root. Once built, record its exact public
   root and the SHA-256 reference to the successful rendered-review report.
   That report must remain bound to the public-file manifest it captured. Do
   not share page markup, a starter
   composition, copy scaffolding, or a theme between study cases. Shared build
   tooling is allowed only when its purpose and constraint are recorded.
4. Declare project-derived viewport classes with at least one `wide` role and
   one `narrow` role. Record their actual dimensions; do not turn the study's
   dimensions into universal device rules.
5. Assign neutral labels. Keep the identity-to-label mapping away from the
   whole-system reviewer until first observations are recorded. The internal
   schema retains `mask_label` and `masked`, and uses the value `"masked"` for
   `whole_system_comparison`, as stable interface names. They mean identity
   blinding, not pixel redaction.
6. Begin a frozen pre-build case as `planned`. Declare its non-overlapping
   future `build_root` and page routes, keep captures empty, leave its unprimed
   review `pending` or `not-run` with null review fields, and keep `blocker`
   null. Declaring the path does not authorize the initializer or auditor to
   create that directory. Change the status to `built` only after the build
   root and evidence actually exist.
7. Include a `correctly_blocked` case only when proceeding would require an
   invention, an unlicensed asset, missing authority, an unsafe action, or an
   unavailable required capability. Record the evidence and the condition that
   would unblock it. Do not relabel an ordinary weak build as blocked.

Copy `templates/batch-range-template.json` to
`.design-dna/batch-range.json`, replace every placeholder, and keep the record
project-local. The stable filename is an implementation detail; call the
user-facing capability **Batch Study** so it is not confused with a single
project's Range Study.

## Capture without diagnostic priming

- Apply [review data handling](data-handling.md) before capture. Complete the
  study's `data_handling` record with separate capture and contact-sheet
  authorization decisions and bases, classification, named recipients and
  access scope, and either a retention owner/date or a reasoned public or
  not-applicable disposition. Record every crop, redaction, or exclusion with
  its coverage impact. A planned study may keep this record pending; built
  captures cannot become comparison-ready until it is resolved. Neutral labels
  do not remove names, logos, copy, people, URLs, media, private states, or
  client identity from screenshot pixels. Use only authorized inputs; exclude
  restricted material, minimize or replace confidential content, define
  recipients and retention, and record how any crop, redaction, or exclusion
  changes comparison coverage. When an authorized transformation is needed,
  preserve the verified original inside its authorized evidence boundary and
  do not broaden access merely to retain it.
- Build each `built` case only from its frozen brief and source packet. Complete
  its implementation-isolation attestation before comparison. Keep research
  and artifacts isolated between sites; if sibling output was exposed, record
  when it happened rather than rewriting history.
- For every declared page, save matched captures for every required viewport
  class. Each capture records whether it is a viewport slice or full-page
  capture plus the renderer capture, scenario, and profile IDs. Use the same
  browser viewport dimensions across the batch, while allowing each site to
  adapt differently. A viewport slice must decode to the complete viewport;
  a full-page capture must match its viewport width and may extend to the
  document's rendered height. Do not confuse document height with viewport
  height.
- Before showing a risk list, skill diagnosis, or another site's implementation,
  have a reviewer record what they notice, where they notice it, and why it
  matters in that site's context. Record whether the reviewer had already seen
  sibling output as a separate field from diagnostic priming. Bind the review
  to the site's complete page × viewport × capture-mode set, record zoned
  observation and freeze times, then freeze the non-empty observation as its
  own evidence file and hash it. This release requires distinct paths and
  distinct bytes for every per-site observation; it does not model a shared
  review artifact.
- Review the complete sites again as a neutral-label set. Record the first
  comparison observation before diagnostic material or the site-identity map is
  revealed. Start it only after every built site's first observation is frozen;
  bind it to the whole capture-set digest, record zoned observation and freeze
  times, freeze it as a non-empty evidence file distinct from every per-site
  observation, and set both reveal fields truthfully in the contract. Compare
  hierarchy, content logic, responsive transformation, imagery use,
  interaction purpose, copy cadence, and overall system behavior. Do not
  compare isolated ingredients or reward difference for its own sake.
- Record only contextual findings. Tie each observation to named study sites,
  routes when applicable, and evidence. Give every finding a declared
  `severity` (`low`, `medium`, `high`, or `critical`) and `impact`
  (`informational`, `bounded`, `material`, or `release-blocking`). A finding
  is material when either field says so: `medium` or stronger severity, or
  `material`/`release-blocking` impact. A repeated observation may justify a
  workflow improvement; it never becomes a global font, style, layout, motion,
  or novelty ban by frequency alone.

Use the [unprimed site observation template](../../templates/batch-site-observation-template.md)
before the reviewer sees sibling captures or diagnostic vocabulary. Freeze and
hash that file before comparison. Then use the
[whole-system comparison template](../../templates/batch-whole-system-review-template.md)
with neutral labels and matched captures. A single reviewer may perform both
phases only when the first phase is durably frozen before any sibling output or
diagnostic list is revealed; record that timing honestly.

## Compare derivation rather than ingredients

The whole-system pass asks whether independent briefs produced independent
reasoning, not whether every site selected a different ingredient. Compare the
relationships among:

- the content job and the page's organizing mechanism;
- first-screen geometry, full-page silhouette, density, pacing, and endings;
- material or surface behavior, depth, edge, container, and rule grammar;
- typography roles, scale relationships, voice, and reading behavior;
- color roles and contrast architecture, not merely hue names;
- media's structural role, crop logic, subject specificity, and provenance;
- navigation, section transitions, interaction purpose, motion grammar, and
  responsive transformation;
- copy cadence, utility labels, proof, actions, and the nouns that make the
  experience belong to its subject.

These are review lenses, not required fields that every project must maximize
or differentiate. A shared convention, brand system, platform constraint,
access need, or genuinely similar task can explain repetition. Conversely,
different colors and photographs do not establish range when the same opening,
type-role relationship, rule system, section cadence, or interaction grammar
remains interchangeable.

When a repeated cluster lacks a project-derived explanation, revise at the
earliest shared decision that caused it. That may be the content model,
organizing metaphor, spatial logic, material register, type-role system, media
relationship, or interaction model. Do not treat a palette swap, font swap, or
added effect as a sufficient response. Mentally remove the dominant image,
accent color, and motion: if the remaining hierarchy and sequence could still
belong unchanged to several unrelated briefs, the revision is probably too
shallow. Record the before/after evidence and rerun both the affected site
review and the neutral-label comparison.

Do not turn a cluster into an AI score, an authorship claim, a permanent style
ban, or a novelty quota. The useful result is a contextual cause, a defensible
revision, and a regression condition that protects creative freedom.

## Record human contextual disposition

After the neutral-label whole-system review is frozen, create a separate
non-empty human disposition record from
[the human disposition template](../../templates/batch-human-contextual-disposition-template.md).
Hash it and add its path/SHA-256 to `human_contextual_disposition.evidence` in
the Batch Study contract. It is a durable statement of a human decision, not
an aesthetic score or proof of reviewer identity.

Bind that record to the exact current whole-study `capture_set_sha256`, name a
reviewer and zoned decision time after the frozen whole-system observation, and
record a substantive rationale. Keep this disposition record separate from the
per-site and neutral-label observation evidence so the later decision remains
inspectable.

Use exactly one of these statuses:

- `pending` while the current capture set does not yet have a final human
  disposition; leave reviewer, time, capture binding, evidence, rationale, and
  finding IDs null or empty.
- `no-material-cluster-observed` when the frozen capture set has no open or
  accepted material contextual cluster. Name no finding IDs.
- `revisions-required` when a human has identified the finding IDs that require
  change and a refreshed capture-set-bound decision.
- `accepted-contextual-risk` only when the record names exactly the material
  findings whose own disposition is `accepted-contextual-risk`; state why the
  risk is accepted in context. It cannot close a finding whose impact is
  `release-blocking`; resolve that finding before final readiness.
- `blocked` when a human disposition cannot yet be made. State the actual
  block and the evidence for it; do not relabel an ordinary weak build as
  blocked.

An open material finding keeps `human_contextual_ready` false even if all
capture, hash, timing, and isolation checks are complete. A resolved material
finding may be followed by `no-material-cluster-observed` only after the
current capture set and human record are refreshed. Low or bounded findings
remain visible but do not automatically override the recorded contextual
decision.

## Audit the evidence

```text
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/batch_range_audit.py" "<PROJECT_ROOT>" --contract .design-dna/batch-range.json --output .design-dna/batch-range-audit.json --atlas .design-dna/batch-range-atlas.png
```

The auditor verifies portable relative paths, frozen evidence hashes, isolated
build roots, unique sites and page routes, declared viewport-class coverage,
and every built public root against the bound rendered-review source manifest.
Each capture must identify a completed renderer route/scenario/profile record;
the renderer's screenshot path, SHA-256, decoded dimensions, requested/final
route, browser viewport, and device scale are checked against the Batch record.
Viewport captures must match both rendered viewport dimensions; full-page
captures must match rendered width and meet or exceed viewport height.
The audit also requires non-empty distinct per-site and whole-system review
evidence, capture-set digests, separate sibling-output and diagnostic-exposure
declarations, and zoned chronology from study freeze through site-review freeze
to whole-system observation. It preserves the separation among planned, built,
and correctly blocked cases. A valid
planned case produces explicit readiness gaps rather than being misreported as
built or blocked. The CLI summary records `execution_ok: true` and the separate
coverage and human-contextual fields. It exits nonzero whenever `final_ready`
is false, including when protocol coverage is complete but the required human
contextual disposition remains missing, pending, blocked, or cannot close a
material finding. That nonzero result marks incomplete readiness, not a
malformed contract or a machine-generated aesthetic verdict. PNG capture bytes
are decoded with the portable
runtime; JPEG and WebP capture verification requires Pillow. When Pillow is
available, `--atlas` assembles a neutral-label contact sheet only when
contact-sheet authorization is resolved and affirmative. Capture payloads are
not retained as a study-sized in-memory cache. The atlas pass re-reads one
capture at a time, rechecks its declared hash and decoded media identity, and
composites those exact bytes. It
copies the screenshot pixels; it does not redact their content. A declared
redaction or crop is not pixel verification, and the auditor never claims it is.
Atlas creation is optional and its absence does not change evidence integrity.
Store, share, and delete it under the strictest classification represented in
the inputs. A dated retention record becomes incomplete after its review date;
the auditor refuses a new atlas until an accountable owner renews the date or
the evidence is deleted under the recorded policy.

Treat `comparison_ready` as a coverage statement about the declared and
mechanically verifiable protocol only. `human_contextual_ready` reports whether
the capture-set-bound human disposition has closed every material contextual
finding, and `final_ready` is their conjunction. Evidence bytes and boolean
records do not prove that a reviewer followed the protocol honestly. Even a
complete report sets `automatic_aesthetic_pass` to `false`; `final_ready` means
only that the declared human contextual boundary is recorded, never that the
auditor judged the sites aesthetically good. If a case is still planned, fewer than three cases were built,
captures are missing, an
unprimed review is absent, review evidence is empty or reused, sibling output
or diagnostic material was seen before a required first observation, review
chronology or capture-set binding is incomplete, or the
neutral-label review is incomplete, keep the study incomplete. Resolve the gap
or report the honest block; never fill it with a score or an inferred aesthetic
verdict.
