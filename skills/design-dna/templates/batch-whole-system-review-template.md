# Batch Study neutral-label whole-system review

Begin only after every included site's unprimed observation is frozen. Review
matched captures under neutral labels. Neutral labels obscure the identity map;
they do not redact the screenshot pixels.

Do not transform screenshot pixels by default. If a stated hypothesis or
authorized privacy-minimization need requires a transformed copy, keep the
verified original within its authorized boundary and complete the optional
record below. Do not claim geometry preservation; state what the transform
prevents the reviewer from concluding.

## Evidence identity

- Study ID:
- Reviewer ID:
- Pre-review study-contract snapshot path and SHA-256:
- Whole-study capture-set SHA-256:
- Atlas path and SHA-256, if used:
- Included specimen labels:
- Viewport classes:
- Site identity revealed before first comparison observation: yes / no
- Diagnostic material revealed before first comparison observation: yes / no
- Observed at (zoned timestamp):
- Frozen at (zoned timestamp, after observation):

Copy the two reveal answers exactly into
`whole_system_review.site_identity_revealed_before_observation` and
`whole_system_review.diagnostic_material_seen_before_observation`; also copy
the capture-set digest and times into `capture_set_sha256`, `observed_at`, and
`frozen_at`. A complete
comparison-ready record requires both values to be `false`. Freeze this
non-empty review as its own file; do not reuse a per-site observation file or
its bytes as the whole-system evidence.

## Optional pixel-transformation record

Complete only when a transformation was actually authorized and used.

- Purpose: hypothesis-test / privacy-minimization
- Justification:
- Authorizing authority and evidence path/SHA-256:
- Exact method:
- Coverage impact:

| Original path and SHA-256 | Transformed path and SHA-256 | Where used |
|---|---|---|
|  |  |  |

## First comparison observation

Before consulting a checklist, record the repeated relationships, meaningful
differences, strongest specimens, weakest specimens, and any family resemblance
you notice. Explain where in the captures each observation appears.

## Contextual cluster review

Use only the lenses that matter to this study. They may include organizing
mechanism; opening and full-page silhouette; density and pacing; material,
surface, edge, container, or rule grammar; typography-role relationships;
color roles; media relationships; navigation; section transitions; interaction
and motion grammar; responsive transformation; copy cadence; labels; proof;
actions; and endings.

| Cluster ID | Specimens/routes | Observed relationship | Rendered evidence | Project-derived explanation or missing derivation | Severity / impact | Disposition and rerun |
|---|---|---|---|---|---|---|
| CL-001 |  |  |  |  | low / medium / high / critical; informational / bounded / material / release-blocking |  |

Different hues, fonts, photos, or effects do not by themselves resolve a
shared scaffold. When a cluster lacks a defensible explanation, revise the
earliest shared decision that caused it and compare the affected specimens
again. Preserve legitimate brand, task, platform, genre, content, access, and
maintenance explanations.

## Transfer conclusions

- Which parts of the method transferred well across unrelated briefs?
- Which repeated defaults came from the method rather than the briefs?
- Which guidance, tool, template, or regression fixture should change?
- Which observations remain contextual and must not become a blacklist?
- Which sites require revision and a new unprimed review?

## Decision boundary

- Comparison status: complete / incomplete
- Automatic aesthetic pass: false
- Site identity revealed before first comparison observation: yes / no
- Diagnostic material revealed before first comparison observation: yes / no
- Human contextual decision:
- Known limitations:
- Frozen review record path:

After freezing, record this file's SHA-256 in the study contract or audit
record that references it. Do not append a self-hash to this file. Then make a
separate [Batch Study human contextual disposition](batch-human-contextual-disposition-template.md)
for the same capture set after diagnostic material is eligible. The later
disposition must not reuse this whole-system observation as its evidence, and
it never turns the audit into an automatic aesthetic pass.
