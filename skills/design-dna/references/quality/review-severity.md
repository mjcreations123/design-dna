# Human-review severity

Use this vocabulary for visual, content, accessibility-baseline, specificity,
and product-review findings. Scanner classifications remain governed by the
scanner contract.

Severity measures impact if the finding ships. Confidence measures certainty
that the evidence and diagnosis are correct. Record them separately.

## Assign severity

Consider:

- harm to safety, rights, privacy, truth, dignity, or accessibility;
- whether a primary task is blocked, corrupted, or materially misdirected;
- reach across routes, audiences, devices, roles, or repeated components;
- likelihood under realistic use;
- recoverability and whether harm is reversible;
- release state and exposure;
- contractual, regulatory, financial, or reputational consequence.

Use the highest level supported by any consequential dimension. Do not lower
severity because a fix is difficult or raise it because a treatment is
personally disliked.

| Severity | Definition | Typical evidence | Required disposition |
| --- | --- | --- | --- |
| Critical | Immediate or irreversible risk to people, rights, secrets, data, money, production systems, release integrity, or a broad destructive operation; exploitation or ordinary use can cause catastrophic impact. | Exposed credential, arbitrary-directory deletion, unauthorized payment or production mutation, destructive data loss, critical-path deception with immediate harm. | Stop the affected work and release. Contain the risk, preserve recovery evidence, involve the accountable security, legal, privacy, financial, or operational owner, and require independently verified remediation before resuming. |
| High | Likely or plausible serious harm; false public representation; blocked critical task; inaccessible critical path; destructive, financial, privacy, or release-integrity failure; or a repeated defect affecting most of the surface. | Unusable checkout, fabricated proof, keyboard trap, unreadable required content, deceptive consent, apparently live but nonfunctional transaction. | Block the affected release or scope until fixed, removed, safely disabled, or explicitly excluded by an accountable specialist or owner with documented authority. |
| Medium | Material degradation of comprehension, credibility, task success, recovery, responsiveness, or project specificity without meeting the high threshold. | Broken intermediate layout, misleading hierarchy, unrecoverable form input, repeated generic route silhouette, unsupported medium-impact claim, missing important state. | Fix before ordinary completion. Defer only with named owner, reason, bounded impact, and follow-up condition. |
| Low | Localized friction or finish defect with limited reach and a clear workaround; it does not materially alter truth, access, or the primary task. | Isolated alignment error, weak secondary label, minor crop issue, inconsistent but understandable spacing. | Fix when proportionate or record as accepted with rationale. |
| Note | Observation, opportunity, or taste alternative with no demonstrated defect. | Optional refinement or preference variation. | Never use as a release gate. Preserve as a suggestion only when useful. |

## Record confidence

Use:

- `high`: directly reproduced, measured, or verified against an authoritative
  source;
- `medium`: supported by clear evidence but with an untested condition or
  plausible alternative cause;
- `low`: hypothesis or perception requiring reproduction or corroboration.

A low-confidence high-impact concern still deserves prompt investigation, not
an unsupported declaration.

## Apply hard gates

The following remain release blockers regardless of an aesthetic severity
vote when applicable:

- unresolved safety, legal, privacy, security, or regulatory requirement;
- fabricated or materially unsupported public proof;
- inaccessible critical path against the project's required baseline;
- exposed secret or restricted personal/research data;
- apparently live consequential behavior that is unconfigured or unverified;
- a required test, approval, or accountable-owner decision explicitly marked
  as blocking.

Escalate to the applicable specialist rather than resolving specialized risk by
visual-review consensus.

## Close findings

For every critical, high, or medium finding, record:

1. stable identifier and affected route, state, viewport, and build;
2. observable evidence;
3. likely cause and confidence;
4. user or release impact;
5. implemented fix, removal, or authorized disposition;
6. exact rerun evidence on the revised candidate;
7. remaining limitation and owner.

Use one lifecycle vocabulary:

- `open`: confirmed or under investigation and not yet resolved;
- `fixed-unverified`: a change exists, but the affected check has not passed;
- `verified`: the affected check passed on the revised exact candidate;
- `accepted-risk`: an accountable owner accepted a bounded non-critical risk
  with rationale, reach, mitigation, and review condition;
- `deferred`: scheduled outside the current scope with an owner and condition;
- `blocked`: resolution depends on missing authority, input, or external state;
- `not-applicable`: evidence shows the finding does not apply.

`accepted-risk`, `deferred`, and `blocked` are not synonyms for `verified`.
Critical findings cannot be accepted as ordinary design risk. Stop polish when
remaining items are notes or documented low-severity tradeoffs and all required
specialist gates are satisfied or explicitly blocked.
