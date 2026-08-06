# Research and user validation

Use this for substantial greenfield work, redesigns, unfamiliar domains, or consequential user journeys.

## Contents

- [Triangulate references](#triangulate-references)
- [Establish hypotheses](#establish-hypotheses)
- [Set decision measures](#set-decision-measures)
- [Protect measurement integrity](#protect-measurement-integrity)
- [Use the lightest credible method](#use-the-lightest-credible-method)
- [Validate with appropriate people](#validate-with-appropriate-people)
- [Protect restricted research](#protect-restricted-research)
- [Interpret responsibly](#interpret-responsibly)
- [Own post-launch learning](#own-post-launch-learning)

## Triangulate references

When browsing is available and permitted, inspect a compact, current set and
record the retrieval date:

- current category peers;
- adjacent-field references;
- real project, local, or cultural material;
- task-specific usability standards or research.

Record the source, retrieval date, transferable lesson, limitation, and what must not be copied. Use galleries and social platforms for discovery, not as proof of usability or truth.

Do not make research a blocker when tools or access are unavailable. Disclose the limitation and use reversible decisions.

## Establish hypotheses

Write:

- intended audience and critical task;
- current evidence from analytics, support, research, or owner knowledge;
- assumptions and highest-risk unknowns;
- what success or failure would look like;
- which decisions the study can actually change.

Do not call internal preference “user research.”

## Set decision measures

Choose measures that correspond to the decision rather than collecting
available numbers by habit:

- **Baseline:** the current condition before the change, with source, segment,
  and measurement window.
- **Outcome:** the behavior or understanding the work is intended to improve,
  such as successful completion, first-click accuracy, comprehension, or
  qualified conversion.
- **Guardrail:** a result that must not worsen, such as errors, abandonment,
  recovery, accessibility, support demand, trust, or performance.

For each measure, record the instrument, accountable owner, review date, and
what difference would change a decision. When a reliable baseline is
unavailable, say so and define the first observation as baseline rather than
inventing precision.

## Protect measurement integrity

For production instrumentation or experiments, define:

- event and property semantics, trigger, denominator, segment, window, and
  source of truth;
- consent and data-minimization boundaries, retention, access, and excluded
  traffic;
- duplicate, missing, delayed, blocked, offline, cross-device, and
  version-change behavior;
- implementation and build binding, test evidence, monitoring owner, and known
  data-quality limits;
- allocation, exposure, guardrail, stopping, and decision rules for an
  experiment.

Verify that an instrument emits the intended event once, in the correct state
and scope, without exposing restricted data. Confirm that dashboards and
reports use the same definition and release. Treat missing or unverified
instrumentation as an explicit limitation; do not infer lift, causality, or a
population-wide effect from it.

Require analytics or data, privacy, security, research, or statistical
specialists for production event architecture, regulated data, experiments,
causal claims, or material business decisions. Design DNA may define the
decision question and interface guardrails; it does not certify
instrumentation or statistical validity.

## Use the lightest credible method

Match the method to the riskiest unknown, genre, and fidelity needed to answer
it. A five-second exposure is optional: for task-, service-, or product-led
work it may test subject, audience or situation, and next action; for narrative,
art, editorial, cultural, or entertainment work it may instead test invitation,
orientation, continuation, or intended unfolding. Do not require immediate
full comprehension when the experience deliberately reveals meaning over time.

Other lightweight options include:

- first-click testing for navigation and action hierarchy;
- a short task walkthrough with representative people using realistic content;
- terminology or content-comprehension checks;
- an accessibility walkthrough with relevant assistive technology and, when
  feasible, people who use it;
- review of search terms, support themes, analytics, and observed sessions.

Record what each method can and cannot establish. Small studies can expose
breakdowns and guide iteration; they do not establish population-wide
preference or certainty.

### Bound simulated review

Use simulated personas or model-based critique only to generate hypotheses and
find candidates for human review. Give each simulation a specific starting
context, goal, constraints, success condition, and available information.
Label the result `simulated`; never count it as target-user observation,
accessibility validation, or accountable approval. Verify consequential
findings through real behavior, domain evidence, or qualified review.

## Validate with appropriate people

Choose participants who plausibly represent the audience, including relevant access needs. Use realistic content and tasks. Observe behavior before asking for opinions.

Capture:

- participant context without unnecessary personal data;
- task, environment, and prototype/build version;
- observed behavior, breakdown, hesitation, and recovery;
- quotes only with appropriate consent;
- severity, confidence, and affected decision;
- change made or reason for deferral.

Keep perception review, usability observation, accessibility testing, and stakeholder approval distinct.

## Protect restricted research

Complete every privacy-control value before collection; a quoted empty value is
not a completed decision. Keep recruitment details, recordings, raw
transcripts, and unnecessary personal data out of the project record.

Run the packaged state validator before collection and after changing Git
configuration. It checks the privacy ignore block and, inside a Git worktree,
fails when `user-validation.md`, `evidence/research/`, or a root
`*.restricted.*` file, including case variants, is already tracked. Treat an
unverified Git-status warning as unresolved: ignore rules do not remove files
that are already in the index.

## Interpret responsibly

- Separate observation from inference.
- Look for task breakdowns, not votes on visual taste.
- Do not generalize from a tiny or homogeneous sample.
- Preserve contradictory evidence and unresolved questions.
- Re-test material changes when risk warrants it.
- State when no target-user validation occurred.

## Own post-launch learning

Before release, name the person or role responsible for reviewing outcome and
guardrail measures, support evidence, and material user feedback. Set the first
review date, escalation or rollback triggers, and where decisions and follow-up
changes will be recorded. Keep unresolved findings visible until accepted,
tested, or explicitly deferred by the accountable owner.

For a durable product or service with ongoing ownership, recurring access to
appropriate participants, and decisions spanning releases, conditionally use
the [design-partner cadence](design-partner-cadence.md). Do not impose it on a
one-off surface or treat co-created possibilities, preferences, or feature
requests as validated requirements.

Use the user-validation template for a durable record. Escalate high-stakes, regulated, or research-heavy work to qualified specialists.
