# Redesigning an existing site

Use this when the brief changes a site that already exists and already has
users, rankings, integrations, analytics, or habits. A redesign is not a
greenfield build wearing an old URL: the live site is evidence, its
traffic is an asset, and the riskiest failures are the invisible ones that
break things which currently work. New-build direction guidance still
applies to whatever is genuinely reopened; this reference governs what must
be learned first and what must never change silently.

## Contents

- [Audit before touching anything](#audit-before-touching-anything)
- [Choose the intervention depth](#choose-the-intervention-depth)
- [What never changes silently](#what-never-changes-silently)
- [Protect search and inbound continuity](#protect-search-and-inbound-continuity)
- [Apply the levers in cost order](#apply-the-levers-in-cost-order)
- [Verify against the live baseline](#verify-against-the-live-baseline)

## Audit before touching anything

Inventory the live site before proposing anything:

- brand tokens actually in use, and which are intentional identity versus
  accumulated residue;
- the information architecture: routes, their traffic and inbound links
  where analytics are available, and the jobs each route performs;
- content blocks worth preserving: proof, copy that converts, photography
  with rights, documents users link to;
- patterns users have learned: navigation labels, form flows, account
  paths, saved bookmarks;
- integrations and their coupling: forms, payments, bookings, analytics
  events, webhooks, embeds, emails that reference pages;
- the SEO baseline: indexed routes, titles, descriptions, structured
  data, canonical behavior, and current rankings where the owner can
  export them;
- known defects the redesign is expected to fix, from the owner's own
  words.

Record what is being preserved on purpose, what is being retired on
purpose, and what is unknown. An unknown coupling discovered after launch
is the classic redesign incident.

## Choose the intervention depth

Name the mode explicitly with the owner, because each carries different
obligations:

- **Preserve:** the identity stays; craft, hierarchy, and implementation
  improve. The current design is the direction record.
- **Evolve:** the identity carries but the system is rebuilt; roughly the
  most value at the least continuity risk when IA, content, and search
  equity are sound. Most client redesigns belong here.
- **Overhaul:** the direction itself reopens, with full greenfield
  process on the reopened surface. Choose this because the owner rejected
  the current identity, not because rebuilding is more interesting than
  evolving.

When IA, content, and search continuity are sound, a targeted evolution
usually captures most of an overhaul's value at a fraction of its risk;
say so when recommending, and let the owner choose knowingly.

## What never changes silently

Each of these may change, but only as an explicit, owner-visible decision
with its migration handled, never as a side effect of rebuilding:

- **URL structure.** Every changed or removed route ships a 301 from the
  old address; inbound links, search equity, and printed materials point
  at the old paths.
- **Primary navigation labels.** Users have learned them; renaming is a
  decision about their vocabulary, not a copywriting refresh.
- **Form field names and order.** Analytics events, autofill profiles,
  saved passwords, and downstream integrations key on them; a renamed
  field silently breaks all four.
- **The brand mark and its lockup.** Refinement is a brand decision the
  owner signs, not a build detail.
- **Legal, consent, and policy copy.** Changing it changes what users
  agreed to; route through the owner and, where applicable, their counsel.
- **Transactional and notification email content** tied to page flows.
- **Third-party contracts:** analytics property IDs, pixel events,
  webhook payloads, embed configurations.

## Protect search and inbound continuity

Search migration is the highest-stakes technical risk in a public-site
redesign. Before launch:

- map every indexed old route to its new home; 301 permanently, one hop;
- carry or deliberately improve titles, descriptions, canonical tags, and
  structured data per route, per the launch-completeness metadata rows;
- preserve or regenerate the sitemap and verify the crawl policy matches
  the new delivery state;
- keep stable anchors and file URLs that other sites and documents cite;
- schedule a post-launch check of coverage and 404 reports in whatever
  search tooling the owner has, and name who watches it.

A redesign that gains beauty and loses the routes that ranked has lost the
owner money; treat that as a release-blocking defect class, not polish.

## Apply the levers in cost order

When the goal is modernization rather than a new identity, spend in the
order that buys the most visible change per unit of risk, and stop when
the brief is satisfied rather than completing the list:

1. **Typography:** the largest visual lift for the smallest structural
   risk; the whole system, not a family swap.
2. **Spacing and rhythm:** recut the cadence before touching structure.
3. **Color recalibration:** within or beside the existing brand, with the
   contrast floors re-proven.
4. **Motion:** added or removed deliberately, under the motion reference.
5. **Hero and key-section recomposition:** structural, higher risk.
6. **Full block replacement:** the most expensive lever; by this point
   the work is an overhaul and should be named as one.

## Verify against the live baseline

The live site is the baseline candidate. Capture it before work begins,
at the same routes, widths, and states the redesign will be proven at,
and keep those captures with the evidence. The redesign's review then
answers, with rendered pairs: what improved, what changed neutrally, what
regressed, and what was preserved on purpose. Run the redirect map, the
form integrations, and the analytics events in the staging environment as
part of the engineering review, not after launch. The preship gate and
launch-completeness record apply in full; rows the live site already
satisfied are re-verified on the rebuilt result rather than inherited on
trust.
