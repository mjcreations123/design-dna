# Forms and complex transactions

Use this for applications, intake, assessments, claims, questionnaires,
uploads, and other multi-step transactions. Fit the structure to the task and
evidence; do not impose one-question-per-page or reproduce a paper form by
default.

## Contents

- [Frame the transaction](#frame-the-transaction)
- [Structure the questions](#structure-the-questions)
- [Get the input mechanics right](#get-the-input-mechanics-right)
- [Preserve progress and control](#preserve-progress-and-control)
- [Validate and recover](#validate-and-recover)
- [Build trust and access](#build-trust-and-access)
- [Verify and escalate](#verify-and-escalate)

## Frame the transaction

Establish:

- the user's goal, eligibility, authority, and successful outcome;
- the information or evidence required, why it is needed, and when;
- deadlines, estimated effort, materials, costs, and supported channels;
- branching, review, submission, follow-up, and re-entry;
- the consequences of abandonment, error, duplication, or stale data;
- available help, alternatives, and escalation.

Remove questions without a confirmed purpose. Distinguish required, optional,
conditional, and unknown answers. Never invent a submission route, approval,
integration, processing time, or outcome.

## Structure the questions

- Group questions by the user's mental model and the decisions they support.
- Use one micro-topic per step when that reduces load or improves recovery;
  keep related short fields together when separation would slow the task.
- Reveal conditional detail only when relevant and explain why sensitive or
  unexpected information is requested.
- Use stable, plain, specific labels and instructions. Preserve meaning across
  localization, autofill, and assistive technology.
- Define how changing an earlier answer affects later answers, uploads,
  calculations, eligibility, and review.
- Show progress only when the sequence is knowable; orient users by meaningful
  stages rather than decorative step counts.

## Get the input mechanics right

Beneath the flow sits a layer of input mechanics that decides whether the
form fights its user. The accessibility baseline owns the conformance
floor; these are the recurring behaviors above it:

- Accept free text and validate after; do not block characters as they are
  typed, block paste anywhere, or reformat while the user is mid-entry.
- Let submission be attempted: pre-disabling the submit control to enforce
  validity hides what is wrong; the attempt should surface the errors.
  Disable re-entry only once the request is actually in flight, per the
  [feedback-states lifecycle](../craft/feedback-states.md).
- In a single-input context, Enter submits; in a multiline field, plain
  Enter writes a newline and a modifier chord submits. Do not invert
  either expectation.
- Trim leading and trailing whitespace before validating; text expansion
  and mobile autocorrect append spaces users cannot see, and a code or
  email rejected for an invisible space reads as a broken form.
- Disable spellcheck on emails, usernames, codes, and identifiers so the
  browser does not underline or "correct" them.
- Codes and one-time passwords are pasteable, accept their delivered
  formatting (spaces, hyphens), and work with password managers and
  autofill; fields that should not wake a password manager mark
  autocomplete off deliberately.
- A placeholder, where used at all under the microcopy label rules, shows
  a real example of the expected pattern rather than restating the label.
- Warn before navigation discards unsaved entries, and give consequential
  submissions an idempotency key or equivalent server-side duplicate
  protection so a retry or double-activation cannot double-book or
  double-charge.

## Preserve progress and control

Make browser Back, in-product Back, refresh, and correction safe. Retain valid
answers and uploads through recoverable errors. Where the task warrants it,
support save, resume, session-expiry warning, and return across devices or
channels according to the real account and storage model.

Before a consequential submission, provide a check-answers view organized by
topic, with direct change paths that do not force replay of irrelevant steps.
After submission, show a durable confirmation, reference, next step, and
record or receipt when the system supports one.

## Validate and recover

Accept human input formats and validate at a useful time. Associate each error
with its cause, explain how to fix it without blame, preserve the entered
value, and provide a summary when several errors exist.

Model the applicable loading, saving, saved, stale, offline, upload-progress,
upload-failed, invalid, partially saved, timed-out, duplicate, submitting,
submitted, cancelled, server-error, retry, and final-success states. Prevent
duplicate submission and show success only after authoritative confirmation.
Explain what was saved, what was not, and whether retry is safe.

## Build trust and access

Explain the task, purpose, expected effort, use of information, and support
before commitment. Apply [privacy, consent, and permission
guidance](privacy-consent-permissions.md) when personal data or device access
is involved.

Support visible labels, keyboard navigation, logical focus, error association,
status announcements, zoom, touch, password managers, autofill, suitable input
types, slow networks, and narrow screens. Provide an accessible alternative or
human handoff when the real service offers one. Escalate trauma-sensitive,
medical, financial, identity, child-directed, or similarly high-consequence
questions to qualified specialists.

## Verify and escalate

Test representative happy paths, every material branch, minimum and maximum
data, optional and unknown answers, corrections, back/refresh, save/resume,
session expiry, uploads, check-and-change, duplicate prevention, cancellation,
offline and server failure, retry, and authoritative confirmation. Verify
stored data and downstream effects, not only visible screens.

Test keyboard, screen reader, zoom, touch, localization, right-to-left layout,
mobile, slow network, and realistic content extremes. Use research or observed
service evidence for consequential structure decisions.

Require legal, privacy, security, accessibility, operations, data, identity,
payments, medical, or regulatory specialists for their respective rules,
calculations, assurance, production behavior, and compliance claims.
