# Conversational and assistant interfaces

Use this for chat, assistants, copilots, generated-answer panels, and any
surface where a person types a request and a model or an agent answers.
[Messaging and notifications](messaging-notifications.md) covers human-to-human
inboxes and owns presence, delivery, and moderation honesty; this file owns the
generated-answer surface. For the product framing around it, pair with
[software products](../verticals/software-product.md).

Decide the container and visual language from the real conversation model,
product context, content length, user task, and supported behavior. Bubbles,
documents, inline answers, logs, panels, avatars, indicators, and send icons are
all available when their relationships fit. After rendering, use the
[post-render convergence review](../convergence-watch.md) if an unexplained
bundle of familiar defaults has displaced the project's needs.

## Contents

- [Model the conversation first](#model-the-conversation-first)
- [Model the response lifecycle](#model-the-response-lifecycle)
- [Render generated output honestly](#render-generated-output-honestly)
- [Uncertainty, provenance, and correction](#uncertainty-provenance-and-correction)
- [The composer](#the-composer)
- [Limits, cost, and context](#limits-cost-and-context)
- [History and persistence](#history-and-persistence)
- [Truth and safety failures](#truth-and-safety-failures)
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

## Model the response lifecycle

Record how this product actually responds: settled, chunked, token-streamed,
tool-running, queued, offline, human-reviewed, or another supported model. Then
design only the states and controls that model can produce. Relevant states may
include idle, submitted, waiting, receiving, tool activity, stopped, partial,
complete, refused, timed out, rate-limited, filtered, disconnected, or failed;
their number and distinction follow real behavior and recovery needs.

If the product streams, decide what is announced, whether interruption is
supported, what a stop action actually cancels, and how a partial response is
identified. If it returns settled or delayed results, show that honestly. A
typing indicator over canned content, an artificial delay, or a fake token
reveal misrepresents system behavior under the
[assurance boundaries](../../policy/absolutes.md) and
[parseable-text review](../quality/parseable-text.md).

## Render generated output honestly

Model output may contain headings, lists, tables, code, math, links, media, or
another product-specific structure. Support only the forms the product
actually returns, with semantics and controls appropriate to their use. Decide
deliberately what happens when content exceeds its container. Local scrolling,
wrapping, alternate views, downloads, responsive transformation, and page-level
overflow each have different access and usability costs; choose and test the
result rather than imposing one container recipe.

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
behind it is fabricated data under the
[assurance boundaries](../../policy/absolutes.md). Prefer stating the limit in words
that a visitor can act on, such as what the assistant cannot see, when its
knowledge ends, and what it will not do.

Provide correction, retry, feedback, source inspection, or human escalation
when the task, uncertainty, consequence, or real service supports it. Do not
render decorative recovery or escalation controls whose path does not exist.
For regulated subjects follow
[production readiness](../quality/production-readiness.md) and require the
applicable specialist before shipping.

## The composer

When a composer exists, treat it as a consequential control and decide its
supported input, keyboard contract, growth, attachment or paste behavior,
validation, submission, progress, failure, and draft persistence. A read-only
answer panel, proactive assistant, voice surface, inline copilot, or embedded
tool may have no composer or may make another control primary.

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

## Truth and safety failures

- A typing or thinking indicator on content that is not being generated.
- An artificial delay added to make an instant answer feel considered.
- A fabricated confidence score, star rating, or accuracy percentage.
- Citation chrome on an answer with no retrieved source behind it.
- A generated avatar or invented persona name presented as a real person,
  which violates the [assurance boundaries](../../policy/absolutes.md).
- A stop control that hides output while the request continues.
- Raw model markup injected as live HTML.
- A blinking terminal caret beside static copy when it falsely implies live
  generation.

Emoji, mascots, icons, avatars, status markers, and terminal language remain
contextual design ingredients. Review their meaning, tone, alternatives,
operating truth, and rendered fit without treating the category itself as a
failure.

## Verify and escalate

Select tests from the real lifecycle, supported content, consequential actions,
failure and recovery paths, persistence model, input methods, responsive
transitions, and user settings. Use representative short, long, structured,
partial, and failing content only where the product can produce it. Derive
exact widths from the supported layout rather than a permanent device number.

When text streams, avoid a live region that announces every token. Choose an
announcement cadence that fits the product, preserve focus, and verify the
actual result with relevant assistive technology rather than assuming, per the
[accessibility baseline](../quality/accessibility-baseline.md). Settled,
chunked, and tool-running interfaces need their own status and focus behavior.

Use the specialists implicated by the real product and claim. Security,
privacy, legal, safety, or domain review is required when its corresponding
retention, training, regulated-advice, data, agentic-action, or capability risk
is in scope; a bounded read-only surface does not inherit an unrelated
specialist checklist.
