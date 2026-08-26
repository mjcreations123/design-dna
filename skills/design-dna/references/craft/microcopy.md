# Microcopy

Use this for small functional strings: controls, labels, helper text, errors,
empty or unavailable states, confirmations, progress, status, and recovery.
[Parseable text](../quality/parseable-text.md) decides whether a string has a
public job; this file helps write the strings that do. [Content and IA](content-ia.md)
owns navigation structure; [public copy and voice](public-copy.md) owns longer
headings and body copy.

Microcopy is part of behavior. Its quality depends on whether the interface
state is true, the intended audience understands the language, the next step
is possible, and the voice fits the project. No universal phrase list,
sentence order, word count, tone, or punctuation style applies.

## Contents

- [Bind the real state](#bind-the-real-state)
- [Distribute status and boundary copy](#distribute-status-and-boundary-copy)
- [Name actions and outcomes](#name-actions-and-outcomes)
- [Write errors and recovery](#write-errors-and-recovery)
- [Distinguish absence states](#distinguish-absence-states)
- [Handle consequential actions](#handle-consequential-actions)
- [Label and explain inputs](#label-and-explain-inputs)
- [Write progress, status, and success](#write-progress-status-and-success)
- [Carry the project voice](#carry-the-project-voice)
- [Audit strings for producer voice](#audit-strings-for-producer-voice)
- [Verify in context](#verify-in-context)

## Bind the real state

Before writing, record:

- what actually happened and what the system knows;
- what remains saved, pending, reversible, unavailable, or uncertain;
- what the person can do now and what requires another actor or system;
- whether a claim about time, delivery, identity, availability, or success has
  a real source;
- the audience's vocabulary, language, stress level, and accessibility needs.

Do not fill an unknown with reassuring prose. A fictional prototype may use
representative strings when its demo boundary is visible and the state cannot
be mistaken for a live fact.

Name a public state by what the person can understand, do, or expect next—not
by a raw implementation field, database value, internal workflow stage, or
producer category. Do not surface an internal state simply because it is
available in the model. Translate it only when the resulting visitor-facing
fact and consequence are true.

## Distribute status and boundary copy

Make a material fiction, demo, unavailable, generated-media, safety, or
operating boundary findable where a person can act on the mistaken assumption.
For a sparse, fictional, or internal concept, map the boundary from the
approved fixture or claim ledger and actual route behavior: a clear orientation
for context-free arrival, local status for each claim or action whose
illustrative or unavailable state changes the decision, and duplicate
placements that can be removed. A persistent site-level orientation may carry
through linked routes when it remains visible; a route likely to be shared or
opened directly needs its own intelligible context.

Then separate distinct consequences. A page-level concept status, an
image-level media fact, and a control-level unavailable state may all be
necessary; certification, transaction, and integration claims need the same
care. Do not use a generic `concept`, `demo`, or `internal` label as repeated
decorative copy, and do not use a boundary label to make fictional proof,
operations, or certifications appear real.

Consolidate copy that says the same thing, while retaining claim-local facts
whose consequence differs. Choose placement, persistence, and prominence from
likelihood of misunderstanding, consequence, direct-entry context, and the
surrounding task. Truthful status must not be hidden, but it does not
automatically need to be the loudest visual element. Verify the rendered entry
and point of action against the boundary map rather than counting disclosures.

## Name actions and outcomes

A control label should make the resulting action or state predictable in its
context. A conventional short label can be clearest; a longer object-specific
label can reduce ambiguity or risk. Choose by the surrounding heading,
control group, consequence, language, platform convention, and available
space rather than a fixed word count.

Keep terminology stable across the path unless the audience's mental model
genuinely changes. If one control opens a differently named destination, the
transition or destination should explain the relationship.

Collapse duplicate intent. When several controls on one surface perform the
same action under different names ("Get in touch", "Contact us", "Let's
talk"), the variety reads as three offers and dilutes all of them; pick the
one label the project's voice supports and repeat it. Repeating a true
label is clarity, not monotony; distinct labels are for distinct actions.

Distinguish the repeated unit of action from the completion condition. A turn,
step, move, item, stage, and finished outcome can each be valid, but a concise
walkthrough must not present the final outcome as though it occurs inside every
repeated unit. Verify the wording against the real state transition rather than
the visual number of illustrated panels.

Technical verbs, familiar defaults, playful language, icons, and terse labels
are all available when the audience understands them and the consequence is
clear. Review ambiguity and mismatch, not a phrase in isolation.

## Write errors and recovery

An error provides the information useful at that moment. Depending on the
case, it may need:

- the affected object or action;
- what happened or what remains unknown;
- whether entered work survived;
- what the person can change;
- what the service or another actor must resolve;
- a retry, alternate path, support reference, or safe stopping point.

Do not claim a cause, outage duration, retry outcome, or saved state the
system cannot establish. Do not expose stack traces, secrets, component names,
or raw infrastructure detail as ordinary body copy. A documented support
reference or expert-facing diagnostic is different when the audience can use
it and its sensitivity is controlled.

Place and announce an error where it is useful. A field-level issue normally
belongs with that field; a summary can complement it when several errors or a
long form make orientation difficult. Preserve input and focus where safe.

Write requirements without shaming the person. The exact register may be
direct, formal, warm, clinical, playful, or technical according to the
project; clarity and recovery are the outcome requirements.

## Distinguish absence states

Do not collapse meaningfully different causes into the same empty screen.
Possible states include first use, no matching results, completed work,
permission limits, offline or stale data, failed loading, archived content,
scheduled availability, and a genuinely empty collection. This is an open
set, not a required taxonomy.

For the state that actually exists, communicate only what helps: its cause
when known, the current scope or filter, whether data may exist elsewhere,
and an available next step. An intentionally quiet completion state or an
informational dead end may need no action at all.

## Handle consequential actions

For deletion, spending, publishing, permission changes, cancellation, or
other consequential actions, identify the affected object and actual
consequence. State reversibility, retention, timing, and downstream effects
only when known.

Choose confirmation, review, inline friction, delayed execution, or undo from
severity, frequency, reversibility, and platform convention. Do not force a
dialog for every action. Keep keyboard focus and accessible naming consistent
with the safest understandable path without hiding the intended action.

## Label and explain inputs

Every input needs an accessible name that remains available after the person
enters a value. A persistent visible label is usually the most resilient
implementation; another pattern must be proven under focus, autofill, error,
zoom, translation, and assistive technology. A placeholder may provide an
example or hint but does not by itself preserve the field's identity.

Give format, limit, purpose, privacy, or required/optional information before
failure when it materially changes what someone enters. Mark requirements in
a way that is perceivable without relying on one visual cue. Do not add helper
text merely to make every field look alike.

## Write progress, status, and success

Progress and status are valid when they report a real state the audience
needs. Choose determinate progress only when the system has meaningful
progress data; otherwise use honest pending language or another suitable
feedback pattern. Do not fabricate percentages, queue positions, liveness,
completion, or delivery estimates.

A success state confirms what actually happened and any relevant next step.
It may be a sentence, changed control state, receipt, redirect, animation,
sound, or quiet completion. Match persistence and prominence to consequence;
not every action needs a toast or celebratory voice.

## Carry the project voice

Derive functional voice from the approved direction, audience, locale, and
situation. Maintain enough consistency that controls feel related, while
allowing urgent, legal, safety, celebratory, and expert states to change
register when their jobs differ.

Familiar phrases, apologies, humor, exclamation marks, technical language,
and repeated action labels are not automatically good or bad. Review whether
they clarify the object, consequence, cause, or next step without delaying a
stressed user or impersonating a brand voice the project does not have.

Write whole localizable messages rather than concatenated English fragments.
Verify expansion, plural rules, gender or formality where applicable, script,
directionality, truncation, and screen-reader output with the
[localization guidance](../quality/localization.md).

## Audit strings for producer voice

Before delivery, re-read every rendered string as a stranger, aloud where
that helps, and flag:

- grammar that breaks mid-sentence or references an antecedent that never
  appeared;
- wordplay and evocative fragments that fail a second read: a phrase that
  sounds thoughtful but does not parse is worse than a boring one, and
  when unsure whether a string makes sense, replace it with a plain
  functional sentence;
- mock-humble or performative-craftsman phrasing standing in for real
  category names and facts;
- numbers wearing false precision: a decimal implies a measurement, so
  every precise-looking figure is either real with a source, visibly a
  scenario, or removed. Manufacturing "organic-looking" data is the same
  fabrication as a round invented statistic.

This audit is about truth and parseability, not banned words; route each
hit through the [parseable text](../quality/parseable-text.md) gate and the
project's claim records rather than a phrase blacklist.

## Verify in context

Build an inventory of reachable functional strings and group them by route,
state, action, and consequence. Look for terminology drift, false certainty,
unexplained status, inconsistent objects, repeated filler, and strings that
misdescribe the visible structure, count, relationship, or state after a
responsive or interaction change, or exist only because a component template
expected one. A precise number or noun must still map to
what the reader can actually see and operate; replace stale wording with the
current concept rather than forcing the interface to preserve an obsolete
count.

Trigger representative real states rather than reviewing source alone:
invalid and incomplete input, no results, permission limits, interruption,
slow or failed operations, recovery, consequential actions, and success as
applicable. Review keyboard and screen-reader announcement, focus, wrapping,
zoom, narrow layouts, translation, and long real content. Select cases from
the product's risks; no fixed state list substitutes for its behavior.
