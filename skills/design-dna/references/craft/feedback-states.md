# Feedback, waiting, and in-between states

Use this when an interface must respond to an action whose result is not
instant, show that work is pending, recover from failure, or occupy the
moments between states: loading, submitting, saving, empty, stale,
undoing. These states are part of the design, carry more trust weight per
pixel than any hero, and are where an otherwise finished build most often
exposes its first draft. [Microcopy](microcopy.md) owns the words; this
reference owns the temporal and structural behavior.

## Contents

- [Time feedback honestly](#time-feedback-honestly)
- [Design the submit lifecycle](#design-the-submit-lifecycle)
- [Make skeletons truthful](#make-skeletons-truthful)
- [Use optimism with a receipt](#use-optimism-with-a-receipt)
- [Give destructive actions a way back](#give-destructive-actions-a-way-back)
- [Leave no dead ends](#leave-no-dead-ends)
- [Verify the in-between states](#verify-the-in-between-states)

## Time feedback honestly

Feedback that appears and vanishes in a flash reads as a glitch; feedback
that appears instantly for fast operations trains users to expect flicker.
Two timing disciplines, both measured against the real operation:

- **Show-delay:** hold a pending indicator back briefly (a commonly
  effective band is roughly 150 to 300 ms) so operations that finish
  fast never flash one.
- **Minimum visible time:** once shown, keep it up long enough to be
  perceived (roughly 300 to 500 ms) even if the operation finished
  earlier, so completion reads as completion rather than flicker.

The bands are starting points, not law; a long-running export and an
inline toggle earn different treatments. What is not open: an indicator
that lies. Determinate progress only when real progress data exists;
otherwise honest indeterminate pending, per the microcopy status rules.
Never fabricate percentages or countdowns.

## Design the submit lifecycle

A submit control is a small state machine, and every state is designed:

- **Ready:** enabled. Do not pre-disable submission to enforce validity;
  letting the attempt surface the validation errors is usually the more
  accessible and less mysterious behavior, per the forms guidance.
- **In flight:** the control shows pending and keeps its label; a spinner
  that replaces the label costs the user the memory of what they pressed.
  Disable re-entry now, not before, to prevent duplicate submission.
- **Slow:** if the operation can exceed a few seconds, say so or show
  progress; silence past the expected duration reads as failure.
- **Failed:** the entered work survives, the error explains the fix near
  its cause, and retry is safe; pair consequential retries with an
  idempotency key or equivalent server-side duplicate protection so a
  double-click or resend cannot double-charge or double-book.
- **Succeeded:** confirmation matched to consequence, per the success
  rules in microcopy and the launch-completeness success-state decision.

Warn before navigation discards unsaved work, and make Back safe, as the
forms reference requires.

## Make skeletons truthful

A skeleton is a promise about incoming layout. It earns its place only
when it mirrors the final content's actual shape: same regions, same
approximate dimensions, so the handoff from skeleton to content produces
no layout shift. A generic shimmer block that gets replaced by a
different-shaped reality is worse than a plain pending state, and an
endless shimmer over content that never arrives is a lie. Reserve
dimensions for anything that loads late (media, embeds, dynamic regions)
whether or not a skeleton is drawn. Spinners, skeletons, progressive
content, and quiet inline pending are all valid instruments; choose by
what the wait is for and how long it plausibly lasts.

## Use optimism with a receipt

Optimistic interfaces show the intended result before the server
confirms. Use them where the operation almost always succeeds and the
user's flow benefits; never for consequential state a person might act on
before confirmation. The contract has three parts: show the optimistic
state immediately, reconcile with the authoritative response, and on
failure either roll back visibly with an explanation or convert to a
retry offer. A rollback the user never notices is state corruption from
their side of the glass. Announce asynchronous outcomes through the
established status region so they are perceivable without stealing focus.

## Give destructive actions a way back

Deletion, cancellation, sending, publishing, and spending need either a
confirmation proportionate to their weight or, often better for frequent
reversible-by-design operations, immediate action with a genuine undo
window. If undo is offered, honor it reliably for its stated window and
make the window findable; an undo that sometimes works is worse than a
confirmation. Never both nag and act irreversibly. The consequential-
action rules in microcopy and the pointer-cancellation and recovery
requirements in the accessibility baseline apply.

## Leave no dead ends

Every state a user can land in offers a next step: an empty collection
says how it fills, per the microcopy absence-state rules; a failed load
offers retry or an alternate path; a permission wall says who to ask; a
finished flow points somewhere. Audit the states nobody designed: the
zero-results filter, the expired link, the half-loaded page on a dropped
connection, the return visit to a completed one-time flow. A dead end is
a defect even when every happy path is polished.

## Verify the in-between states

These states are exactly the ones a normal-speed demo never shows, so
they are verified deliberately: throttle the network and watch the
skeleton-to-content handoff for shift; make the failing request fail and
walk the recovery; double-click the submit; navigate away mid-flight and
come back; reach the empty and zero-result states with real filters.
Capture the consequential ones as rendered evidence like any other state.
The engineering review's state matrix and the preship gate's
empty/error/success rows govern which of these the project must prove.
