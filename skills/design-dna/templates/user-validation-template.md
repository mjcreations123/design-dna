---
schema_version: 1
created_with: "__DESIGN_DNA_VERSION__"
classification: "restricted-research"
evidence_contract: "proportional-evidence-v1"
research_data_owner: "pending"
collection_basis: "pending"
access_scope: "need-to-know project team"
storage_location: "project-local restricted record; do not commit"
retention_rule: "pending"
deletion_owner: "pending"
deletion_status: "pending"
---

# User validation record

<!-- proportional-evidence-v1 -->

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

## Contents

- [Study](#study)
- [Measures and method](#measures-and-method)
- [Participants](#participants)
- [Tasks and observations](#tasks-and-observations)
- [Findings and decisions](#findings-and-decisions)
- [Limits](#limits)
- [Completion](#completion)

## Study

- Decision this study can change:
- Audience and critical task:
- Hypothesis and highest-risk unknown:
- Prototype/build ID:
- Environment and date:
- Facilitator:
- Validation not performed and why:

## Measures and method

| Kind | Measure | Baseline and source | Instrument and segment | Guardrail or decision threshold | Owner and review date |
| --- | --- | --- | --- | --- | --- |
| baseline / outcome / guardrail |  |  |  |  |  |

- Chosen method and why it can answer the riskiest unknown:
- Method limits:
- Production measurement integrity, when applicable: event/property semantics,
  trigger, denominator, segment, window, source of truth, consent and
  minimization, duplicate/missing/delayed behavior, build binding, QA,
  monitoring owner, and known data-quality limits
- Experiment or causal-claim specialist boundary and unverified items:
- Simulated review, if used: context, goal, constraints, success condition,
  result, and explicit statement that it is hypothesis generation rather than
  target-user evidence:

## Participants

| Code | Relevant context | Access needs supported | Consent/status |
| --- | --- | --- | --- |
|  |  |  |  |

## Tasks and observations

| Task | Participant | Observed behavior or breakdown | Recovery | Severity/confidence |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |

Keep observations separate from interpretations. Add quotes only when consent and retention rules permit.

For public concepts or unfamiliar directions, include an unbriefed entry task
only when it can answer the declared question. For task-, service-, or
product-led work, ask whether the offer or task, relevant audience or
situation, useful action, and prominent controls are understandable. For art,
narrative, editorial, cultural, or entertainment work, ask whether the intended
invitation, orientation, continuation, and degree of unfolding are perceptible.
Do not force a primary action or reveal the creative premise before recording
the first answer.

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
- Post-launch learning owner, first review date, and evidence source:
- Escalation, rollback, or further-research trigger:
- Where follow-up decisions will be recorded:
- Remaining risk:
- Owner/research approval:
- Retention/de-identification action completed:
- Deletion verified by/date:
