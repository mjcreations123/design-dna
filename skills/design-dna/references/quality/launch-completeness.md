# Website launch completeness

Use this reference for every new or materially redesigned website before
delivery. It turns a familiar launch list into fifteen explicit project
decisions. It does not turn every decision into the same visible section,
claim, tracking script, or legal page.

Create `.design-dna/launch-completeness.md` from the
[template](../../templates/launch-completeness-template.md), or use an
equivalent maintained project record. For every item, record one of:

- **included**: name the exact route, state, configuration, or asset and how
  it was checked;
- **not applicable**: state why the site's audience, delivery state, or
  product model does not call for it;
- **blocked**: name the missing authority, source, integration, or decision.
  Do not present the dependent behavior as live.

`Not applicable` is a deliberate conclusion, not a blank. `Blocked` is not
permission to invent a policy, location, response promise, analytics ID, or
promotion just to complete the record. A Quick repair can record only the
affected rows; a new website must resolve all fifteen.

## Contents

1. [Primary above-fold action](#1-primary-above-fold-action)
2. [Decision-blocking questions](#2-decision-blocking-questions)
3. [Response or delivery expectation](#3-response-or-delivery-expectation)
4. [Success and thank-you state](#4-success-and-thank-you-state)
5. [Compact-action treatment](#5-compact-action-treatment)
6. [Crawl and indexing policy](#6-crawl-and-indexing-policy)
7. [Page descriptions](#7-page-descriptions)
8. [Page titles](#8-page-titles)
9. [Social sharing image](#9-social-sharing-image)
10. [Location and directions](#10-location-and-directions)
11. [Text alternatives](#11-text-alternatives)
12. [Privacy and policy boundary](#12-privacy-and-policy-boundary)
13. [Analytics](#13-analytics)
14. [Decision cue or USP bar](#14-decision-cue-or-usp-bar)
15. [Approved social promotion](#15-approved-social-promotion)

- [Where these turn into furniture](#where-these-turn-into-furniture)
- [Verification](#verification)

## 1. Primary above-fold action

For a persuasive, transactional, booking, inquiry, or conversion-led route,
make the first meaningful action clear before the visitor must scroll. It can
be a real action, a useful next step, or a truthful unavailable/demo state.
The action must fit the route's actual primary job; an editorial or reference
page can be `not applicable` when an action would distract from reading.

## 2. Decision-blocking questions

Include an FAQ or another easy-to-find question-and-answer treatment when
known questions materially affect a visitor's decision, eligibility, timing,
price, safety, or next step. Use approved answers. Do not pad a site with
generic questions merely to create an FAQ section.

## 3. Response or delivery expectation

For a request, quote, support, order, booking, or digital-delivery path,
state the confirmed response or delivery expectation, or keep the promise
unmade and record the missing owner input. A visible promise needs a source
and an operational owner; it cannot be inferred from a typical business.

## 4. Success and thank-you state

Every successful submission, signup, order, booking, or request flow needs an
honest completion state. It may be a distinct thank-you route, an in-place
confirmation, a receipt, or an externally owned confirmation page. It must
say what happened, what happens next, and any relevant recovery/contact path.
A nonworking demo action must say that it is a demo rather than imply success.

When the completion state is also the measurement, follow-up, or autoresponder
anchor, a distinct addressable route survives reload, back navigation, and an
emailed link in a way an in-place swap does not. That remains a project
decision, not a default. Keep a completion route out of the index, and make
its own next step real rather than a dead end.

## 5. Compact-action treatment

Consider a sticky or persistent compact-screen action when it improves a
mobile visitor's primary task. Test safe areas, keyboard focus, text zoom,
scroll restoration, overlays, and the action's relationship to the real
content. Do not add a sticky CTA where it obscures reading, controls, or an
already easy action.

## 6. Crawl and indexing policy

Resolve `robots.txt`, robots meta directives, and sitemap/canonical behavior
for the declared delivery state. A local demo, staging site, private preview,
or concept normally needs a no-index choice rather than a production crawl
policy. A public launch needs an intentional policy for every indexable route;
do not let a starter's defaults decide it.

## 7. Page descriptions

Give each indexable direct-entry page a distinct, truthful meta description
that describes its real purpose. Verify the rendered HTML or framework output,
not only a shared source template. Pages deliberately excluded from indexing
may record why a description is not needed.

A description is the result listing's own copy, not a keyword field, and a
search engine may replace it with page text. Lead with the distinguishing
fact, because common result layouts truncate well before a long sentence
finishes.

## 8. Page titles

Give each direct-entry page a distinct, useful title appropriate to its route
and indexing policy. Verify titles during direct-entry/reload checks. Do not
repeat a site-wide title across unrelated pages just because a framework makes
that easy.

Front-load the words that distinguish this route. A repeated brand prefix
consumes the visible part of a truncated listing, a browser tab, and a
bookmark, so decide deliberately where the brand belongs in the pattern.

## 9. Social sharing image

For a page likely to be shared, provide an approved social card and bind its
Open Graph/Twitter metadata to the final asset. Inspect the actual crop and
rendered words at social-card dimensions. A concept or private preview can
omit it or use a clearly appropriate asset; never fake documentary proof or
use unlicensed media.

Bind an absolute URL; relative paths fail in most scrapers, which is the
common cause of a card that renders blank from a correct-looking tag. Any
words inside the asset must stay legible at the small preview a messaging
client draws, not only at full size. Because the card that ships is the one
a scraper actually fetched, recheck against the deployed destination rather
than the local build.

## 10. Location and directions

For a physical destination, include an accurate, accessible location and a
usable directions path. Link to an approved map/directions service or a
verified address. Do not invent an address, embed a map that traps keyboard
users, or imply access to a venue that has not authorized it. A digital-only
product records `not applicable`.

## 11. Text alternatives

Give meaningful images, diagrams, media controls, and functional icons
context-appropriate accessible names or alternatives. Decorative imagery is
explicitly decorative. Check emitted markup and the rendered experience; a
file name is not alt text.

When an image carries words that appear nowhere else, the alternative carries
those words. When a visible caption already states the point, the alternative
does a different job than the caption and repeating it verbatim only adds
noise. Write for someone who cannot see the image but needs what it
contributes here.

## 12. Privacy and policy boundary

Resolve the policy and notice pages required by the actual data, payments,
subscriptions, cookies, tracking, geography, and owner legal policy. Link to
approved terms where they apply. Do not invent legal promises or boilerplate.
For a demo with no real collection or tracking, communicate that truthful
boundary rather than pretending to have a production legal program.

A contact form, an embedded map, a hosted font, an error reporter, and an
analytics tag can each create a disclosure obligation. Enumerate the third
parties actually in this delivery path, the data each one receives, and the
owner's real legal entity and contact route. A policy naming processors the
site does not use, or omitting ones it does, is a false statement on the
record rather than a formality.

## 13. Analytics

Add GA4 only when the owner supplies an approved measurement configuration,
consent/notice requirements are resolved, and the delivery state permits
tracking. Verify the exact event plan and no duplicate page views. Do not
insert a placeholder Measurement ID, unapproved tracker, or surveillance into
a concept or local demo.

## 14. Decision cue or USP bar

Use a concise, truthful differentiation, proof, or reassurance treatment when
it helps the visitor choose, trust, compare, or continue. It may be a USP bar,
a proof strip, an editorial callout, or another project-specific form. Every
claim needs authority; a row of generic benefits is not a substitute for a
real reason to choose the offering.

## 15. Approved social promotion

Use a DM, social follow, bonus, or other promotional invitation only when a
real approved offer, channel, eligibility rule, and operating path exist. Link
to the correct channel and make the result honest. Otherwise mark it `not
applicable`; never invent a bonus, giveaway, or inbox that nobody operates.

## Where these turn into furniture

Several of these items have a reflex implementation that is itself a
convergence pattern. The decision stays required; the reflex is what fails.
Diagnose against the rendered result, and apply any owner-standards record
this installation carries before treating a reflex as available.

- **Item 1** reflexively becomes a tinted or gradient full-width band with a
  centered heading and one high-radius button. The decision is only that the
  primary action is reachable from the opening encounter at the project's real
  narrow and wide conditions. It requires no band, centered stack, button
  shape, glyph, or ground treatment. "Above the fold" is a print phrase with
  no fixed pixel meaning; verify reachability in the render rather than
  against a viewport number.
- **Item 5** reflexively becomes a pill fixed to the bottom of the viewport
  with a directional glyph. The decision is that the primary action stays
  reachable during a long compact-screen scroll. An inline repeat at the
  decision point, a persistent header action, a reachable native call or mail
  affordance, or nothing at all can each satisfy it. Whatever ships must clear
  the safe-area inset, must not cover the content beneath it at its real
  height, and must survive text zoom and an open keyboard.
- **Item 14** reflexively becomes a three- or four-column strip of icon, short
  heading, and one line of benefit copy. The decision is that a visitor can
  tell why this offering rather than an interchangeable one. Test each claim
  by substituting a direct competitor's name: anything that survives the
  substitution is not a differentiator and is spending space. Specific
  operating facts usually outperform adjectives.
- **Item 2** reflexively becomes generated questions nobody asked. Source them
  from what the owner is actually asked, and cut any answer that exists only
  to fill a section. Real objections earn the space; invented ones read as
  padding and weaken the true claims beside them.
- **Item 12** reflexively becomes generated boilerplate describing practices
  the site does not perform. A policy is a factual document about this
  business, and an inaccurate one is a worse position than a missing one.
  Resolve it from real sources or record the row as blocked.

Deleting an ingredient because it is named here is the same error facing the
other way. The finding is the unexamined reflex, never the category, and a
band, a persistent action, a benefit row, an FAQ, or a policy page can each
be exactly right when the project chose it.

## Verification

Bind the record to the exact build and perform the checks that can expose a
wrong implementation:

- inspect direct-entry metadata, titles, robots/canonical behavior, and
  social-card references in the emitted site;
- exercise each included action, including success, failure, unavailable, and
  compact-screen states where they exist;
- open the physical directions path, policy links, and approved social channel
  without assuming a widget or an icon is sufficient;
- run the accessibility checks for alternatives and persistent controls;
- inspect analytics only in the approved environment, with consent state and
  duplicate-event behavior included in the result;
- retain the exact owner decision, source, or block for operational promises,
  addresses, promotions, legal material, and measurement configuration.

The record proves that the launch decisions were confronted and checked; it
does not prove legal compliance, campaign performance, search ranking, or
production deployment.
