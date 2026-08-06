# Route-family art direction

Use this for a multi-route site whose bodies need distinct compositions,
editorial voices, or interaction models. Use **Range Study** when expressive
range is itself part of the brief.

Range is not a contest to maximize difference, and family is not permission
to reskin the same page repeatedly. Each route should follow its content and
visitor job while the site remains trustworthy and navigable.

## Contents

- [Define the shared contract](#define-the-shared-contract)
- [Let route jobs determine reuse](#let-route-jobs-determine-reuse)
- [Record the family without prescribing it](#record-the-family-without-prescribing-it)
- [Prove real routes](#prove-real-routes)
- [Create difference from purpose and material](#create-difference-from-purpose-and-material)
- [Adapt each route on its own terms](#adapt-each-route-on-its-own-terms)
- [Review the whole family](#review-the-whole-family)

## Define the shared contract

Define the shared foundation the real family needs. The following concerns are
available prompts, not a required aesthetic layer or fixed record shape:

| Foundation | Stable concern |
| --- | --- |
| Truth | Claim sources, dates, uncertainty, media status, and disclosure vocabulary. |
| Navigation | Destination meaning, relative order when repeated, current-page indication, landmarks, keyboard behavior, and direct-link behavior. |
| Accessibility | Semantic structure, focus, contrast, alternatives, reflow, language direction, and preference handling. |
| Identity | The recognition assets and voice the accountable owner requires across routes. |
| Operations | Canonical paths, metadata, privacy, security, analytics authority, status behavior, and not-found handling. |
| Maintenance | Sources of truth, reusable behavior, asset records, ownership, and test expectations. |

Repeated navigation mechanisms must keep the same relative destination order
unless the user initiates a change. Apply the intent of
[WCAG 2.2 Consistent Navigation](https://www.w3.org/WAI/WCAG22/Understanding/consistent-navigation.html):
visual treatment may vary, but visitors should not relearn what the site links
mean or how the navigation operates on every page.

The shared foundation does not require one grid, font system, color field,
header silhouette, component recipe, motion language, density, or page cadence
unless project authority makes that choice systemic.

## Let route jobs determine reuse

Distinguish:

- **foundations:** reliable behavior and authority shared across the site;
- **reusable design decisions:** tokens, components, content rules, or
  relationships that genuinely serve several routes;
- **route-local decisions:** compositions, type behavior, media treatments,
  interactions, or editorial rules that belong to a route's material;
- **one-offs:** deliberately local work with a named owner, fallback, and
  maintenance boundary when those are consequential.

This uses the practical insight behind
[Spotify Encore](https://spotify.design/article/reimagining-design-systems-at-spotify)
and [Brad Frost's components, recipes, and snowflakes model](https://bradfrost.com/blog/post/design-system-components-recipes-and-snowflakes/):
reuse reliable foundations without forcing unlike content through one recipe.
It does not require either source's organizational structure.

Do not abstract visual similarity merely because it exists. Do not duplicate
functional, accessibility, truth, or state behavior merely to make pages feel
different.

## Record the family without prescribing it

For an explicit Range Study, create `.design-dna/route-family.json` when the
installed schema and audit tooling are in use. Bind it to the exact study and
candidate/build. Record the declared paths, shared contracts, direct-entry
expectations, capture coverage, review status, and the consequential
differences that the brief requires.

For creative fields, use an extensible `creative_logic` and observable
decision model rather than a fixed route menu. `creative_logic` may be one
clear statement or a project-defined object whose keys follow the work; the
object is not a hidden checklist to fill:

| Route | User or editorial job | `creative_logic` | Observable decisions | Relevant adaptations and fallbacks | Evidence and status |
| --- | --- | --- | --- | --- | --- |
|  |  | local statement and evidence | content, structure, composition, type, media, color, ornament, interaction, or another project concern | only conditions material to this route |  |

A route need not demonstrate any named aesthetic device or prescribed page
form. Add project-specific fields when they improve evaluation. Omit
irrelevant fields rather than inventing differences.

Write differences as observations, not mood labels. State what changes in
content order, spatial behavior, media use, interaction, reading, or another
meaningful property and why the route requires it.

An empty `deliberate_differences` list is valid when the closest routes should
honestly reuse a decision. Record the reason in `creative_logic` or observable
evidence; never invent novelty just to populate the list.

The neutral route-family template records cultural acceptance as
`not-required`. Change it only when the actual subject, claims, language,
imagery, or represented community triggers cultural review. Once required,
acceptance still needs an eligible independent authority; the producing agent
cannot waive or self-certify it.

## Prove real routes

Count a page only when its declared path:

- is independently addressable without a fragment or query-string disguise;
- returns the intended document or application state on direct entry and hard
  reload;
- has an appropriate title, heading, canonical/indexing intent, and
  current-page navigation state;
- survives back/forward navigation with expected history behavior;
- is not merely an alias or redirect for another counted page.

Server-rendered and client-routed applications can both provide real routes
when direct entry and reload are configured. Hash sections, query variants,
carousel slides, tabs, and modal states do not become separate pages because a
menu lists them.

Use the route-family audit when available. Its route, link, silhouette, and
atlas outputs are bounded evidence; they do not score authorship, taste,
cultural fit, or design quality.

The family contract is not limited by one renderer invocation. When the
declared family exceeds a capture run's safe route or capture capacity, split
the exact route set into deterministic batches, keep the same declared
viewport widths and tested build across batches, and pass every untouched
schema-compatible report to the family audit with repeated `--render-review`
arguments. Coverage, evidence hashes, and the atlas must reconcile the whole
declared family; no batch may stand in for an untested remainder.

## Create difference from purpose and material

Start each route from its visitor question, content dependency, source
material, and desired outcome. Choose the structure and expression afterward.
Some routes may correctly share a form because their jobs match. Others may
need radically different bodies. Do not assign page types, interactions,
palettes, or effects merely to satisfy a diversity quota.

Surface changes can be consequential when the medium itself changes the
experience. Conversely, different colors, fonts, photographs, or animations
do not prove range when the content order and encounter remain the same.

For a commissioned Range Study, explore enough of the family early to test
whether the requested breadth is real. The number and choice of early routes
depend on project risk and uncertainty; no fixed early sample or route
archetype is required.

## Adapt each route on its own terms

Design responsive, reduced-motion, unsupported-runtime, and no-JavaScript
outcomes where relevant to the route and stack. Preserve complete tasks,
content, truth, and navigation. Creative adaptation may recompose, substitute,
reduce, or remove an effect; it need not flatten every route into one centered
stack or mimic desktop literally.

Choose at least two capture widths because they expose this project's real
layout risks, not because a universal desktop/mobile pair was prescribed.
Give them project-meaningful IDs, use comparable exact widths across routes
when family comparison matters, and add further widths only when they answer a
specific responsive question. The packaged draft uses `null` widths rather
than device-like numbers so it cannot anchor the choice; replace every null
with an exact project-derived width before changing a route from `planned` or
claiming readiness.

If the visual navigation container varies, preserve destination meaning and
order, accessible name, current-page state, focus behavior, and menu mechanics.
Use the [motion and interaction contract](motion-interaction.md) for
significant temporal behavior.

## Review the whole family

Create matched evidence at the viewports required by the project, then inspect
the family before declaring range or polishing isolated pages. Review:

- declared versus verified routes, direct entry, links, aliases, redirects,
  orphaning, history, and not-found behavior;
- shared navigation, identity, truth, terminology, access, and operations;
- repeated main-content sequences, openings, component grammar, type roles,
  media treatment, interaction, motion, copy cadence, and endings;
- whether repeated decisions have a task, brand, content, platform, or
  maintenance reason;
- whether allegedly different routes remain the same experience with new
  words and pictures;
- route-specific responsive, input, preference, loading, and failure behavior;
- source, asset, cultural-review, performance, and maintenance coverage;
- accountable human judgment of range, coherence, and visual quality.

Use pairwise grouping to locate the closest siblings, not to demand maximum
difference between every pair. Fix sameness at the content model, structure,
or creative logic when that is the cause. Do not add decorative novelty merely
to move a route farther from another.
