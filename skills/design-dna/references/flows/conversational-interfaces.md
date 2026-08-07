# Conversational and assistant interfaces

Use this for chat, assistants, copilots, generated-answer panels, and any
surface where a person types a request and a model or an agent answers.
[Messaging and notifications](messaging-notifications.md) covers human-to-human
inboxes and owns presence, delivery, and moderation honesty; this file owns the
generated-answer surface. For the product framing around it, pair with
[software products](../verticals/software-product.md).

The default chat UI is one of the most converged surfaces on the web: a
centred column of alternating bubbles, a circular avatar per turn, three
bouncing dots, and a paper-plane send icon. Reaching for that whole bundle
unexamined is the same failure the
[generator defaults](../convergence-watch.md#dated-watch-the-generator-defaults)
describe. Decide the container from the conversation, not from the memory of
every other chat product.

## Contents

- [Model the conversation first](#model-the-conversation-first)
- [The streaming contract](#the-streaming-contract)
- [Render generated output honestly](#render-generated-output-honestly)
- [Uncertainty, provenance, and correction](#uncertainty-provenance-and-correction)
- [The composer](#the-composer)
- [Limits, cost, and context](#limits-cost-and-context)
- [History and persistence](#history-and-persistence)
- [Named bans](#named-bans)
- [Verify and escalate](#verify-and-escalate)

## Model the conversation first

Record, before styling anything:

- who is answering: a model, a retrieval system over named sources, a human,
  or a mix, and whether the visitor is told which;
- what the assistant may actually do: answer only, or read, write, spend,
  send, book, or act on the person's behalf;
- what it knows: training data with a cutoff, live retrieval, the user's own
  documents, or the current page;
- turn shape: single question and answer, a long thread, a branching tree,
  or an inline panel beside real work;
- who else can see the transcript, how long it is kept, and whether it
  trains anything.

When the assistant can act rather than only answer, its states and controls
belong to
[agentic behavior](../verticals/software-product.md#model-agentic-behavior)
and its consequential steps to
[complex forms](forms-complex-transactions.md). An assistant that can spend
money or send mail on someone's behalf is a High-risk surface, not a chat
widget.

## The streaming contract

Token-by-token rendering is the 2026 baseline expectation, and it is a
contract, not an effect. Design every state it implies:

- **idle**, with a composer that says what this assistant is for in the
  client's own words, not "Ask me anything";
- **submitted**, before the first token, which is the only honest place for a
  waiting indicator;
- **streaming**, with a visible stop control that genuinely aborts the
  request rather than hiding the output;
- **stopped by the user**, which keeps the partial answer and says it is
  partial;
- **complete**, with whatever follow-up actions the product supports;
- **failed**, distinguished by cause: a refusal, a timeout, a dropped
  connection mid-stream, a rate limit, a content filter, an upstream outage.
  Each needs its own recovery path, and a stream that dies halfway is not
  the same event as a request that never started.

Never simulate any of this. A typing indicator over canned content, an
artificial delay before an instant answer, or a fake token-by-token reveal of
text that already arrived whole are fabrications under
[ABSOLUTE 3](../../policy/absolutes.md) and fake liveness under
[parseable text](../quality/parseable-text.md). Animate the arrival of real
tokens or do not animate.

## Render generated output honestly

Model output is structured text and the surface has to carry its real
structure: headings, lists, tables, code with a language label and a copy
control, math, and links. Decide deliberately what happens to output the
container cannot hold, because a wide table or a long code block inside a
narrow centred bubble is the most common broken state on these surfaces. Give
code and tables their own scroll container, never the page.

Treat any markup the model emits as untrusted text. Render it as content, not
as live markup, and never let a generated string reach the page as raw HTML.

Keep the person's own words and the generated answer visually distinct
without caricature. Bubbles are one valid answer; a document-style
transcript, a two-column log, an annotated panel, or an inline answer under
the query can each be correct, and the choice follows from whether the
content is short and conversational or long and referenceable.

## Uncertainty, provenance, and correction

Show what the answer rests on. When the system retrieves, cite the actual
source with a title and a working link, and make it inspectable before the
person acts on it. When it does not retrieve, do not dress a model's fluency
in citation chrome.

Never present a generated claim with more confidence than the system has, and
never invent a confidence number to display: a percentage with no calibration
behind it is fabricated data under
[ABSOLUTE 3](../../policy/absolutes.md). Prefer stating the limit in words
that a visitor can act on, such as what the assistant cannot see, when its
knowledge ends, and what it will not do.

Give every answer a correction path: report, retry, edit the question, or
reach a human, with the escalation route real rather than decorative. For
regulated subjects follow
[production readiness](../quality/production-readiness.md) and require the
applicable specialist before shipping.

## The composer

The composer is the primary control and deserves more than an input with a
send icon. Decide: multi-line growth and its ceiling, keyboard contract
(Enter sends or Enter newlines, stated and consistent), attachment and paste
handling with real progress and failure, whether an empty submit is possible,
and what happens to a draft on navigation or reload.

Suggested prompts are content, not decoration. Ship them only when each one
leads somewhere genuinely useful for this product; three invented examples of
things the assistant cannot actually do well is a fabricated capability
claim.

## Limits, cost, and context

If the product meters usage, the person needs to know the unit, what they
have left, and what happens at zero before they hit it, per
[subscription and billing](subscription-billing.md). If a conversation has a
context limit, say what happens when it is reached: truncation, summary, or a
new thread. Silent forgetting reads as the product breaking.

## History and persistence

Decide and then show whether a conversation survives reload, which device it
lives on, whether it can be renamed, searched, exported, or deleted, and what
deletion actually removes. Follow
[privacy and consent](privacy-consent-permissions.md) for anything retained
or used for training, and never imply a deletion the backend does not
perform.

## Named bans

- A typing or thinking indicator on content that is not being generated.
- An artificial delay added to make an instant answer feel considered.
- A fabricated confidence score, star rating, or accuracy percentage.
- Citation chrome on an answer with no retrieved source behind it.
- A generated avatar or invented persona name presented as a person, which
  is a fabricated person under [ABSOLUTE 3](../../policy/absolutes.md).
- Emoji as the assistant's face or as status markers (HARD 5).
- A stop control that hides output while the request continues.
- Raw model markup injected as live HTML.
- The blinking terminal caret beside static hero copy, per the
  [hero signature](../convergence-watch.md#dated-watch-the-hero-signature).

## Verify and escalate

Test a first-run empty state, a one-word question, a very long answer, a
wide table and a long code block at 375px, a stopped generation, each
distinct failure mode, a refusal, a rate limit, a dropped connection
mid-stream, reload during streaming, a restored conversation, keyboard-only
operation through send and stop, and reduced motion.

Streaming text is the hardest part of these surfaces for assistive
technology. A naive live region announces every token. Announce that a
response has started, then the settled result, and keep focus stable while
tokens arrive; verify with a screen reader rather than assuming, per the
[accessibility baseline](../quality/accessibility-baseline.md).

Require security, privacy, legal, and domain specialists for retention,
training use, regulated advice, agentic actions with real consequence, and
any claim about what the model can or cannot do.
