# Microcopy

Use this for the small functional strings: buttons, labels, helper text,
errors, empty states, confirmations, loading and success messages, tooltips,
and the sentence in a dialog that decides whether someone loses their work.
[Parseable text](../quality/parseable-text.md) is the gate that removes
strings which should not exist; this file is the craft of writing the ones
that must. [Content and IA](content-ia.md) owns headings, body, and
navigation naming.

Microcopy is where a product's voice is actually experienced, because it is
read at the moments that matter: when someone is confused, stuck, about to
commit, or has just lost something. It is also where generated defaults are
most obvious, because the statistical centre of this vocabulary is very
narrow.

## Contents

- [Write the outcome, not the mechanism](#write-the-outcome-not-the-mechanism)
- [Errors](#errors)
- [Empty states are four different states](#empty-states-are-four-different-states)
- [Confirmation and destruction](#confirmation-and-destruction)
- [Labels, helper text, and placeholders](#labels-helper-text-and-placeholders)
- [Waiting and success](#waiting-and-success)
- [Voice](#voice)
- [Named bans](#named-bans)
- [Verify](#verify)

## Write the outcome, not the mechanism

A control is named for what the person gets, in their words, not for what
the system does internally. "Submit" describes the form's action; "Book the
van" describes the person's. "Save" is fine when saving is the outcome;
"Execute" never is.

Match the verb in the button to the verb in the heading that introduced it,
and to the label on the page it leads to. A "Get a quote" button that opens a
page titled "Contact us" has broken a small promise, and those accumulate.

Length is a design decision, not an accident. A three-word button that names
the outcome beats a one-word button that names a category, and dialog
buttons are the one place where longer labels reliably reduce mistakes,
because "Delete 4 photos" and "Keep them" cannot be confused the way "OK" and
"Cancel" can.

## Errors

Every error message answers three things in this order: what happened, why,
and what to do next. The third is the one most often missing, and it is the
only one the reader actually needs.

- **Be specific about the cause.** "Something went wrong" tells a person
  nothing and is the single most recognisable generated string in the
  category. If the system knows the card was declined, say the card was
  declined.
- **Never blame the reader.** "Invalid input" makes them wrong; "Phone
  numbers need 10 digits" makes the requirement clear.
- **Never expose the internals.** A status code, a stack frame, an
  environment name, a component name, or a request ID shown as body copy
  fails the AUDIENCE question in
  [parseable text](../quality/parseable-text.md) and is a visible
  implementation detail under
  [ABSOLUTE 10](../../policy/absolutes.md). A support reference is different
  from a leaked internal, and is labelled as a reference the person can quote.
- **Put it where the problem is.** A field error belongs at the field, not
  only in a summary at the top, and it is announced to assistive technology
  rather than only coloured red.
- **Say whether the work survived.** After a failed save, the reader's first
  question is whether they lost what they typed. Answer it.
- **Distinguish what the person can fix from what they cannot.** A wrong
  password is theirs to correct; an outage is not, and it needs a status and
  a timeframe rather than a retry button that will fail again.

## Empty states are four different states

They are routinely written as one, which is why so many read as filler.

1. **First run.** Nothing exists yet because the person just arrived. This is
   the most valuable empty state and the most wasted: it teaches what the
   thing is for and offers the one action that starts it.
2. **No results.** Their query matched nothing. Say what was searched, and
   offer a way back: clear a filter, widen a date range, check a spelling.
   Never imply the data does not exist when only the filter is wrong.
3. **Cleared deliberately.** They finished everything or emptied it on
   purpose. This is a success state and should read as one.
4. **Failed to load.** Nothing is here because something broke. This is an
   error wearing an empty state's clothes, and writing it as "No items yet"
   is a lie the reader will act on.

## Confirmation and destruction

Name the specific object and the actual consequence. "Are you sure?" carries
no information; "Delete the Vine Avenue draft? This cannot be undone" carries
both. State whether the action is reversible, and if it is, say for how long.

The confirming button carries the verb, the cancelling button carries the
safe outcome, and the destructive action is never the default focus. Where
an undo is genuinely possible, an undo after the fact beats a dialog before
it; do not ship an undo the backend cannot honour, per
[complex forms](../flows/forms-complex-transactions.md).

## Labels, helper text, and placeholders

A placeholder is not a label. It vanishes on focus, fails contrast in most
implementations, and leaves the person staring at a filled field with no idea
what it holds. Label every field visibly.

Helper text sets expectations before the error: the format, the limit, the
reason a field is required, or what the business will do with it. One line,
above the interaction rather than after the failure.

Optional and required both need marking in a way that survives being read
aloud, and "required" is more honest than an asterisk with a legend
elsewhere.

## Waiting and success

Say what is happening if it will take long enough to notice, and be honest
about duration only when the system knows it. A progress bar that has no
progress information behind it is fabricated data.

Success messages confirm the specific thing that happened and, where
relevant, what happens next: who was emailed, when to expect a reply, where
the file went. A success message that just says "Success" makes the reader
check whether it worked.

## Voice

Microcopy inherits the project's voice from
[copy voice](../quality/parseable-text.md#copy-carries-information-the-visuals-cannot),
and it is where a voice most often collapses into the default cheerful
product register. A funeral home, a legal practice, and a skate shop should
not apologise in the same words. Decide the register with the direction, then
hold it in the smallest strings.

Exclamation marks are a decision, not punctuation weather. Most functional
strings need none.

Strings expand when translated, commonly by a third or more from English,
and concatenated fragments break entirely in other grammars. Write whole
sentences per string and leave room, per
[localization](../quality/localization.md).

## Named bans

- "Oops!", "Uh oh", "Whoops", and every variant of cheerful failure.
- "Something went wrong" with no cause and no next step.
- "Get Started" as a default CTA, per the
  [hero signature](../convergence-watch.md#dated-watch-the-hero-signature).
- "Click here" as link text, which breaks link-list navigation.
- "Please wait while we..." when the wait is imperceptible.
- A cute 404 that jokes before it helps the person find the page.
- An em dash anywhere in any string ([ABSOLUTE 1](../../policy/absolutes.md)).
- A status code, environment name, or component name as body copy
  ([ABSOLUTE 10](../../policy/absolutes.md)).
- Sentences that describe the interface back to the reader.

## Verify

Read every string aloud in the voice the direction chose. Pull all of them
into one list and read them in sequence: repeated constructions, mismatched
verbs, and drifting register are visible in a list and invisible in place.

Trigger the real states rather than reading them in source: submit an empty
form, submit a wrong value, kill the network mid-save, search for nonsense,
delete something, and arrive as a genuinely new user. Every string reached
that way is part of the
[parseable-text review pass](../quality/parseable-text.md#the-review-pass)
and the [preship gate](../../templates/preship-gate.md), including the ones
only a failure can produce.
