---
schema_version: 1
created_with: "__DESIGN_DNA_VERSION__"
classification: "restricted-research"
research_data_owner: "pending"
collection_basis: "pending"
access_scope: "need-to-know project team"
storage_location: "project-local restricted record; do not commit"
retention_rule: "pending"
deletion_owner: "pending"
deletion_status: "pending"
---

# User validation record

Store only necessary, consented information. Do not include sensitive personal data when a participant code is enough.

Before collecting observations, replace every `pending` privacy-control value in
the frontmatter. Record who owns the data, the consent or other approved
collection basis, who may access it, where it is stored, when it will be
deleted or de-identified, and who is accountable for deletion. Keep recruitment
lists, contact details, recordings, and raw transcripts outside this record in
an access-controlled system.

Before collecting participant data, run the packaged state validator. Inside a
Git worktree it fails when this record, `evidence/research/`, or a root
`*.restricted.*` file, including case variants, is already tracked;
`.gitignore` cannot protect a file that is already in the Git index. If
tracking cannot be verified, resolve that warning before collection.

## Study

- Decision this study can change:
- Audience and critical task:
- Hypothesis and highest-risk unknown:
- Prototype/build ID:
- Environment and date:
- Facilitator:
- Validation not performed and why:

## Participants

| Code | Relevant context | Access needs supported | Consent/status |
| --- | --- | --- | --- |
|  |  |  |  |

## Tasks and observations

| Task | Participant | Observed behavior or breakdown | Recovery | Severity/confidence |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |

Keep observations separate from interpretations. Add quotes only when consent and retention rules permit.

## Findings and decisions

| Finding | Evidence | Interpretation | Change or deferral rationale | Re-test |
| --- | --- | --- | --- | --- |
|  |  |  |  | yes, no, or pending |

## Limits

- Audience or conditions not represented:
- Accessibility or assistive technology not covered:
- Conflicting evidence:
- Sample-size and generalization limits:
- Research, legal, privacy, or specialist follow-up:

## Completion

- Changes implemented:
- Re-test result:
- Remaining risk:
- Owner/research approval:
- Retention/de-identification action completed:
- Deletion verified by/date:
