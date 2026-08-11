# Email as a medium

Use this when the deliverable is an email: a receipt, a password reset, an
order confirmation, a booking notice, a digest, or a campaign. Email is not a
narrow web page. It renders in clients with materially different capabilities
and is often read with images switched off.
[Messaging and notifications](../flows/messaging-notifications.md) owns which
messages exist and what preferences govern them; this file owns making one
render.

## Contents

- [Decide the job and the class](#decide-the-job-and-the-class)
- [The structural floor](#the-structural-floor)
- [Design for images off](#design-for-images-off)
- [Dark mode in mail clients](#dark-mode-in-mail-clients)
- [Type in email](#type-in-email)
- [Commonly overlooked message surfaces](#commonly-overlooked-message-surfaces)
- [Access, law, and honesty](#access-law-and-honesty)
- [Verify in real clients](#verify-in-real-clients)

## Decide the job and the class

Record which class this is, because the rules differ:

- **Transactional**, sent because a person did something: receipts, resets,
  confirmations, alerts. Prioritize the information and next action the
  triggering event requires. Keep unrelated promotion from obscuring service
  information; do not force a multi-part receipt, safety notice, or account
  change into a one-job or answer-first formula when its real task differs.
- **Lifecycle or digest**, sent on a schedule or a trigger. Needs a real
  reason to exist per send and a frequency the recipient chose.
- **Campaign**, sent to a list. Apply the consent, preference or unsubscribe,
  sender-identification, and postal-identity obligations that govern the
  audience, message, sender, and jurisdiction.

Name the decision, record, invitation, or sequence the email must support.
Prioritize the information needed before scrolling when urgency or task
completion requires it. A receipt, narrative newsletter, safety notice, and
campaign may need different openings and more than one related question; do
not force them into one conversion formula.

## The structural floor

Compiled 2026-08; mail-client behaviour shifts, so re-verify against current
client testing rather than trusting this list forever.

- Table-based layout remains the widest conservative baseline, notably for
  desktop Outlook engines. Use modern layout only for a target-client contract
  that supports it, with a complete fallback for the rest of the audience.
- Keep critical presentation in the delivery form the selected clients
  preserve. Inline styles are often the durable baseline; `<style>` blocks and
  media queries can enhance clients that retain them.
- Derive content width and column behavior from message density, expected
  reading environment, and the actual client matrix. A roughly 600px fluid
  column is common, not mandatory. Define how any columns stack or simplify.
- Put backgrounds, padding, and click targets on elements the target clients
  reliably render. Table cells are a common interoperable button foundation;
  another implementation needs equivalent client evidence.
- JavaScript is not available in ordinary email. Forms, embedded video, AMP,
  and other enhanced features require an explicitly supported delivery
  ecosystem plus an honest static or linked fallback.
- Verify margin, padding, and spacing in real clients; their support and
  collapse behavior differ.

## Design for images off

Many clients block remote images until the reader allows them, and some
readers never do. Design the message to work with every image missing.

- Never set essential text as part of an image. A price, a code, a date, or
  a button label inside a JPEG disappears for a blocked reader and for a
  screen reader alike.
- Write real alt text that carries the information, not the filename and not
  "image". Alt text is visible design in this medium, so it is styled and
  sized like the text it stands in for.
- Give every image explicit width and height so the layout does not collapse
  before they load.
- Keep the message legible as a plain text block: a well-structured email
  still reads correctly when reduced to its words.

## Dark mode in mail clients

A large share of readers are in dark mode, and mail clients do not agree on
what that means. Some invert nothing, some recolour selectively, and some
forcibly invert whole blocks, which is how a white logo lockup acquires a
grey halo and a carefully chosen brand colour becomes something else.

- Prefer transparent-background PNG or SVG logos so the mark sits on whatever
  ground the client produces.
- Include pure and near-black/white values in the real-client test matrix when
  the direction uses them. If a target client inverts or halos them in a way
  that harms meaning or identity, adjust that relationship or provide an
  asset/scheme-specific treatment; the values are not globally prohibited.
- Do not rely on a coloured background alone to carry meaning, since it may
  not survive.
- Test the actual dark rendering in the clients that matter to this client's
  audience rather than assuming the light version holds. The general craft
  of a second scheme is in
  [dual themes and dark mode](theming-dark-mode.md); the difference here is
  that the client, not the design, decides.

## Type in email

Webfonts load in some clients and not others, so the fallback stack is the
real typography for a meaningful share of readers. Choose a stack whose
metrics do not wreck the layout when the intended face is absent, and set
line-height and size for the fallback as well as the ideal. The
[typography protocol](typography.md) still applies: tune the fallback's size,
line-height, measure, weight, hierarchy, and wrapping in the real email layout.
Persistent small print remains readable under zoom and client text settings;
no universal type scale or family is imposed.

## Commonly overlooked message surfaces

- **The subject line** is an early recognition and decision surface. Write it
  so truncation in the target clients does not hide the information this
  message most needs to convey.
- **The preheader**, the text a client may preview after the subject, is an
  intentional delivery decision. Supply, suppress, or allow it from the
  message and target-client evidence; do not let accidental utility chrome or
  irrelevant header text become the preview by oversight.
- **The sender identity and subject** work together to establish recognition,
  trust, and purpose. Do not claim a universal ranking without audience and
  client evidence.
- **The plain-text alternative**, when the delivery contract provides one, is
  reviewed as a real representation rather than generated and ignored.
- **The footer** carries the identity, preference, unsubscribe, explanation,
  or legal information that applies to this message and jurisdiction.

## Access, law, and honesty

Real text, semantic structure, a language attribute, sufficient contrast, and
a link purpose that survives being read out of context. Tables used for
layout carry a presentation role so assistive technology does not announce a
grid where there is none.

The [assurance boundaries](../../policy/absolutes.md) apply to email. Do not
invent an order number, delivery estimate, savings figure, countdown, or
personalized claim the system cannot support. Punctuation remains a voice and
readability decision. A merge field that can render empty gets a designed
fallback rather than "Hi ,".

Consent, unsubscribe, sender identification, and postal-address obligations
depend on message class and jurisdiction. A required preference or unsubscribe
path must work. Route these through
[privacy and consent](../flows/privacy-consent-permissions.md) and
[production readiness](../quality/production-readiness.md), and get a
specialist before any live send.

## Verify in real clients

A browser alone is not a verification environment for email. Send real test
messages and inspect the clients this audience actually uses, including a
materially different or constrained rendering engine when compatibility risk
is high. Select light/dark, images blocked/allowed, desktop/mobile, and other
conditions from the recipient and delivery evidence rather than a permanent
brand list.

Rendered review applies to the medium: for email that means representative
mail-client captures rather than only a local webpage. Check the plain-text
alternative, link targets, the unsubscribe path end to end, and relevant
content-pressure cases such as a long name, missing merge value, or an
unbroken string.
