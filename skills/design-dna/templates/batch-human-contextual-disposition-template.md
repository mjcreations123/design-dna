# Batch Study human contextual disposition

Create this only after the neutral-label whole-system observation is frozen.
This is a separate decision record: it does not replace the per-site unprimed
observations or the neutral-label whole-system review, and it does not claim an
automatic aesthetic pass.

## Evidence identity

- Study ID:
- Reviewer ID:
- Status: pending / no-material-cluster-observed / revisions-required / accepted-contextual-risk / blocked
- Whole-study capture-set SHA-256:
- Frozen whole-system review path and SHA-256:
- Decided at (zoned timestamp, after the whole-system review was frozen):
- Decision evidence record path and SHA-256:

Copy the status, reviewer, capture-set digest, decision time, and evidence
reference exactly into `human_contextual_disposition` in the Batch Study
contract. Do not append a self-hash to this file; hash its frozen bytes from the
contract instead. The decision evidence must be its own frozen artifact: do not
reuse a capture, render report, brief, source packet, per-site review,
whole-system review, contextual-finding attachment, or blocker file merely by
giving it a new role in the contract.

## Context and rationale

- What evidence was reviewed after the neutral-label observation:
- Why the selected status fits this capture set and the affected visitors:
- Known limitations that this decision does not resolve:

## Finding disposition

List the contextual findings addressed by this decision. Include every material
finding accepted as contextual risk; do not list resolved findings merely to
make the record look comprehensive.

| Finding ID | Severity | Impact | Current finding disposition | Human decision and rationale | Follow-up evidence or unblock condition |
|---|---|---|---|---|---|
|  | low / medium / high / critical | informational / bounded / material / release-blocking | open / resolved / accepted-contextual-risk |  |  |

## Decision boundary

- `no-material-cluster-observed`: use only when the frozen capture set has no
  open or accepted material contextual finding; leave contract `finding_ids`
  empty.
- `revisions-required`: name the findings that need change; rerender and record
  a new capture-set-bound human disposition afterward.
- `accepted-contextual-risk`: name exactly the material findings whose own
  contract disposition is `accepted-contextual-risk`. A `release-blocking`
  finding cannot close through accepted risk; resolve it before final readiness.
- `blocked`: state the concrete decision block and its evidence. A weak result
  alone is not a block.
- `pending`: use only before a final disposition; leave the contract's reviewer,
  time, capture binding, evidence, rationale, and finding IDs null or empty.

Automatic aesthetic pass: false.
