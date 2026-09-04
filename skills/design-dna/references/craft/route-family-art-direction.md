# Route-family art direction

Use this for a multi-route site whose bodies need distinct compositions,
editorial voices, or interaction models. Use **Range Study** when expressive
range is itself part of the brief.

Range is not a contest to maximize difference, and family is not permission
to reskin the same page repeatedly. Each route qualifies and follows an exact
reference observation whose content job matches its own, while the site remains
trustworthy and navigable.

## Contents

- [Define the shared contract](#define-the-shared-contract)
- [Use it beyond Range Study](#use-it-beyond-range-study)
- [Let route jobs qualify source reuse](#let-route-jobs-qualify-source-reuse)
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

## Use it beyond Range Study

Read this guidance for any public build with multiple independently
addressable routes when their visitor situations, material, or sequence might
diverge. **Range Study** remains the stronger evidence capability for an
explicit anthology or expressive-range claim; an ordinary multi-route site
does not need to manufacture a range record merely because it has navigation.

Before one body recipe spreads, make a concise project-local map of each
route's visitor occasion, dominant content operation, first task-bearing or
subject-bearing encounter, progression, ending or next state, and relevant
narrow transformation. If two routes intentionally share a body operation,
state the task, content, brand, platform, or maintenance reason. This maps
actual route ownership; it is not a list of required page archetypes or visual
ingredients.

When a content object, decision, or state travels between routes, add its
visitor-facing handoff to that same map: what carries, what intentionally
resets, how a direct entry reconstructs context, and what result or recovery
remains available. Do not add artificial persistence merely to make a family
look like an application; a clearly bounded local state or a deliberate fresh
entry can be the appropriate behavior.

At wide and narrow conditions, inspect whether persistent navigation, identity,
context, or a public shell helps orientation without replacing the route's own
first meaningful material or useful action. A shared shell may be completely
correct. When it dominates unrelated route bodies, treat that as a direction
question to explain or reopen rather than as a reason to rotate fonts, colors,
shapes, or effects.

## Let route jobs qualify source reuse

Distinguish:

- **foundations:** reliable behavior and authority shared across the site;
- **reusable source decisions:** measured tokens, components, content rules, or
  relationships from a selected observation that genuinely serve several routes;
- **route-local source decisions:** compositions, type behavior, media treatments,
  interactions, or editorial rules bound to that route's selected observation;
- **source one-offs:** measured local work with a named reference, fallback, and
  maintenance boundary when those are consequential.

One optional vocabulary for this distinction is
[Brad Frost's components, recipes, and snowflakes model](https://bradfrost.com/blog/post/design-system-components-recipes-and-snowflakes/):
reuse reliable foundations without forcing unlike content through one recipe.
The vocabulary is explanatory rather than a required organizational structure.

Do not abstract visual similarity merely because it exists. Do not duplicate
functional, accessibility, truth, or state behavior merely to make pages feel
different.

## Record the family without prescribing it

For an explicit Range Study, create `.design-dna/route-family.json` when the
installed schema and audit tooling are in use. Bind it to the exact study and
candidate/build. Record the declared paths, exact selected reference
rank/ID/observation/hash per route, shared contracts, direct-entry expectations,
complete capture coverage, review status, and consequential source-mapped
differences.

For every visual field, use the exact route source mapping, source state,
component-source row, and observable decision. Project-authored prose cannot
create or extend a visual relationship:

| Route | User or editorial job | Exact selected source/state | Census component and observable transfer | Relevant adaptations and fallbacks | Evidence and status |
| --- | --- | --- | --- | --- | --- |
|  |  | selected rank, observation hash, mapped relationship | source-bound content, structure, composition, type, media, color, ornament, or interaction | every declared route/state/viewport plus additional material conditions |  |

A route need not demonstrate any named aesthetic device or prescribed page
form. Add source-evidence fields when they improve evaluation. Omit irrelevant
fields rather than inventing differences or connective design.

Write differences as observations, not mood labels. State what changes in
content order, spatial behavior, media use, interaction, reading, or another
meaningful property and why the route requires it.

An empty `deliberate_differences` list is valid when the closest routes should
honestly reuse a source-bound decision. Record the reason in observable
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
material, and desired outcome, then qualify and bind references whose structure
and expression already fit those needs.
Some routes may correctly share a form because their jobs match. Others may
need radically different bodies. Do not assign page types, interactions,
palettes, or effects merely to satisfy a diversity quota.

Surface changes can be consequential when the medium itself changes the
experience. Conversely, different colors, fonts, photographs, or animations
do not prove range when the content order and encounter remain the same.

For a commissioned Range Study, map every planned route to qualified reference
evidence before scaling and build enough early source-bound proof to test the
riskiest relationships. Final evidence still covers the entire authoritative
manifest; no early sample can stand in for an untested route.

## Adapt each route on its own terms

Reproduce the selected reference's responsive and reduced-motion behavior, and
bind unsupported-runtime and no-JavaScript outcomes where relevant to the route
and stack. Preserve complete tasks, content, truth, and navigation. When access
or runtime requires a change, use another qualified source with the needed
adaptation rather than flattening every route into a producer-authored stack.

Use every wide and narrow viewport in the authoritative route manifest and add
further widths when a source or project condition can change the conclusion.
Give them stable IDs and use exact comparable widths across routes. The
packaged draft uses `null` widths so it cannot fake proof; replace every null
from the manifest before changing a route from `planned` or claiming readiness.

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
- whether the first wide and narrow encounter gives each materially distinct
  route its own subject-bearing material or useful action before a persistent
  shell becomes the whole public impression;
- whether repeated decisions have a task, brand, content, platform, or
  maintenance reason;
- whether allegedly different routes remain the same experience with new
  words and pictures;
- route-specific responsive, input, preference, loading, and failure behavior;
- source, asset, cultural-review, performance, and maintenance coverage;
- accountable human judgment of range, coherence, and visual quality.

Use pairwise grouping to locate the closest siblings, not to demand maximum
difference between every pair. Fix sameness at the content model, structure,
or source/state/component mapping when that is the cause. Do not add decorative novelty merely
to move a route farther from another.
