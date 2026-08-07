# Email as a medium

Use this when the deliverable is an email: a receipt, a password reset, an
order confirmation, a booking notice, a digest, or a campaign. Email is not a
narrow web page. It renders in dozens of engines that disagree, it is often
read with images switched off, and its layout language is closer to 2003 than
to the rest of the work in this skill.
[Messaging and notifications](../flows/messaging-notifications.md) owns which
messages exist and what preferences govern them; this file owns making one
render.

## Contents

- [Decide the job and the class](#decide-the-job-and-the-class)
- [The structural floor](#the-structural-floor)
- [Design for images off](#design-for-images-off)
- [Dark mode in mail clients](#dark-mode-in-mail-clients)
- [Type in email](#type-in-email)
- [The parts nobody designs](#the-parts-nobody-designs)
- [Access, law, and honesty](#access-law-and-honesty)
- [Verify in real clients](#verify-in-real-clients)

## Decide the job and the class

Record which class this is, because the rules differ:

- **Transactional**, sent because a person did something: receipts, resets,
  confirmations, alerts. One job each, the answer at the top, no marketing
  smuggled in. These are usually the most-opened messages a business sends
  and are worth designing properly.
- **Lifecycle or digest**, sent on a schedule or a trigger. Needs a real
  reason to exist per send and a frequency the recipient chose.
- **Campaign**, sent to a list. Requires consent, an unsubscribe, and the
  sender's real postal identity.

Name the single question each email answers, and put that answer in the first
screen: the amount and the date on a receipt, the button on a reset, the time
and place on a booking. Everything else is support.

## The structural floor

Compiled 2026-08; mail-client behaviour shifts, so re-verify against current
client testing rather than trusting this list forever.

- **Tables carry layout.** Flexbox and CSS Grid are not usable across the
  installed base, notably Outlook's desktop rendering engine on Windows.
  Nested tables with explicit widths remain the reliable structure.
- **Styles go inline.** Treat a `<style>` block as an enhancement that some
  clients strip, not as the mechanism. Media queries are progressive.
- **Around 600px** for the content column, fluid within it, single column
  unless a second column genuinely carries different information. Multi-column
  layouts that collapse on phones need explicit stacking rules.
- **Backgrounds belong on table cells.** Outlook ignores background colour on
  many inline elements but honours it on a `<td>`, which is why a durable
  button puts the fill and padding on the cell and the link inside it rather
  than styling an anchor.
- **No JavaScript, no forms, no embedded video.** A poster image linking out
  is the honest pattern.
- **Padding beats margin.** Margin collapses inconsistently across clients.

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
- Avoid pure white and pure black as the design's structural colours; both
  are the values clients most aggressively invert.
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
[typography numbers](typography.md#the-numbers) still apply: body around 16px
and up, generous line-height, a measure that does not run the full width of a
desktop mail window.

Nothing below the size floor. Legal fine print in an email is still text a
person has to be able to read.

## The parts nobody designs

- **The subject line** is the first design surface and is frequently
  truncated; front-load it.
- **The preheader**, the text a client previews after the subject, is
  designed content. Left alone it fills with "View in browser" or the first
  words of a header. Write it.
- **The sender name** is read more than the subject.
- **The plain-text alternative** is a real deliverable, not an afterthought.
- **The footer** carries the legal identity, the unsubscribe, and the reason
  this person is receiving the message.

## Access, law, and honesty

Real text, semantic structure, a language attribute, sufficient contrast, and
a link purpose that survives being read out of context. Tables used for
layout carry a presentation role so assistive technology does not announce a
grid where there is none.

The [owner absolutes](../../policy/absolutes.md) apply here in full and name
emails explicitly: no em dash in any string, and no fabricated content. Do
not invent an order number, a delivery estimate, a savings figure, a
countdown, or a personalised claim the system cannot support. A merge field
that can render empty gets a designed fallback rather than "Hi ,".

Consent, unsubscribe, and the sender's postal identity are legal requirements
in most jurisdictions, and an unsubscribe that does not work is worse than
none. Route these through
[privacy and consent](../flows/privacy-consent-permissions.md) and
[production readiness](../quality/production-readiness.md), and get a
specialist before any live send.

## Verify in real clients

A browser is not a verification environment for email. Send real test
messages and look at them in the clients this audience actually uses, at
minimum a desktop Outlook rendering, Gmail in browser and in app, and Apple
Mail on a phone, in both light and dark, with images blocked and with images
allowed.

The screenshot requirement in [ABSOLUTE 11](../../policy/absolutes.md)
applies to the deliverable as it renders: for email that means captures from
mail clients, not from a local page. Check the plain-text alternative, every
link target, the unsubscribe path end to end, and the message with a long
name, a missing merge value, and a very long line of unbroken text.
