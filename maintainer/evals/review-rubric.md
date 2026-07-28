# Rendered and behavioral review rubric

Use this after the infrastructure runner has produced an artifact. Command success and file presence do not establish design quality.

## Review protocol

1. Run each release-counted high-value prompt at least three times for both the skill variant and
   the unchanged baseline.
2. Randomize artifact labels so perception reviewers do not know model, host, skill, or baseline.
3. Review final rendered routes before reading implementation details.
4. Run implementation, accessibility, and task checks separately.
5. Bind every score to a case, run, build hash, route/state, viewport, browser, date, and evidence path.
6. Record disagreement and unperformed checks. Do not average away a critical blocker.
7. For prompts that explicitly reject an AI-looking, vibe-coded, templated,
   generic, or repeated house-style result, run a final adversarial specificity
   closure after revisions and bind it to the reviewed build.

Do not ask whether a site “looks AI-made.” Ask whether its visible choices are specific, coherent, current for its intended time register, truthful, usable, and finished.

## Release evidence contract

A release review is attributable evidence, not a declaration that evidence exists:

- Record a stable build producer, reviewer identity, review-process identity, method, time, and a
  process record that names them. `independent: true` is accepted only with a different producer and
  a separate-person, separate-agent, blinded-panel, or independent-specialist process.
- Every context has a nonempty route and state; viewport size and device-pixel ratio; browser; input
  modalities; zoom and text scale; reduced-motion and forced-colors settings; contrast preference;
  theme; locale; and text direction.
- Bind every context to a decodable PNG by path, SHA-256, media type, and decoded pixel dimensions.
  A perception release needs distinct mobile and desktop images and a passed `visual-layout` check
  that cites each image.
- Classify the build's motion as `none`, `minor`, or `significant`, with a concrete rationale.
  Static screenshots cannot prove timing, interruption, sequencing, scroll behavior, or a
  reduced-motion alternative. For significant motion, capture hash-bound WebM, MP4, or structured
  JSON temporal evidence for a matched normal-motion/reduced-motion context pair. Keep route,
  state, viewport, browser, theme, locale, and direction constant across the pair; change only the
  motion preference and behavior it is meant to exercise.
- Bind each performed check to path-and-hash evidence. Accessibility checks additionally cite a
  structured JSON record naming the exact check, context, method, result, time, executor, and
  observations.
- An implementation release needs passed structured evidence for keyboard navigation, visible
  focus, screen-reader behavior, contrast, 200% zoom and text scale, text spacing, reduced motion,
  and forced colors. Two ordinary screenshots cannot substantiate these claims.
- Perception dimensions and implementation dimensions listed below must be scored numerically for
  their respective release lenses. `N/A` remains available for other genuinely inapplicable
  dimensions, with a rationale.
- Use schema-version-3 finding records. Give every finding a stable ID and lifecycle status.
  `verified` requires both a resolution and a verification record; both records cite hash-bound
  evidence. `fixed-unverified` is still unresolved. `accepted-risk` can support only an explicit
  limitation when its severity permits it.
- Copy the run's `review_contract.sha256` into `requirement_closure.contract_sha256`. Close every
  contract requirement ID exactly once as `verified`, cite any related finding IDs, and provide
  hash-bound evidence. Missing, added, duplicated, stale, not-applicable, or blocked requirements
  do not count as release closure.

## Release coverage matrix

For each host claimed as passed, select at least four distinct cases whose fixture metadata marks
them high-value and representative. Every selected case needs at least three passed skill runs and
three passed baseline runs. Record and interpret the exact artifact hashes and every run; identical
hashes can demonstrate deterministic reliability and are neither an automatic failure nor proof of
quality. Together the selected cases must cover Persuade, Experience, Operate, and Read, at least
two scopes, one established framework application with local data and state, one adversarial case,
and one implicit-discovery case with bound host-native evidence.

Rendered evidence must not be assembled from unrelated successes. For each of at least four
behaviorally qualified cases, bind an independent perception review and an implementation review to
the same case ID, run ID, and build identity. The perception review also needs bound mobile and
desktop renders, exact requirement closure, and a structured comparison that binds every counted
skill and baseline run to its workspace hash. Record a per-run convergence observation and compare
at least project specificity, distinctiveness without novelty tax, and one additional dimension.
Neither core dimension may be baseline-stronger, and at least one representative case per host must
show a supported skill-stronger core outcome. Every skill and baseline run observation must cite a
verified render and hash. A source-only observation must be labeled as such and cannot substantiate
visual comparison. At least one same-build family must be adversarial.

Add one release-level cross-case analysis bound to the counted mobile and desktop render hashes.
It must cover the exact same four-mode counted set and compare route silhouette, type/palette
relationships, label cadence, card grammar, motion grammar, and media grammar. Record task-derived
differences and counterevidence for every dimension. Track repeated clusters explicitly. A resolved
cluster needs its cause, cause-level resolution, and hash-bound independent verification; an
unresolved cluster blocks the pass.

Do not mark a host passed when execution is unavailable. Record the host as blocked or incomplete
and preserve the reason; a limitation cannot stand in for host-native behavioral or rendered proof.

Treat this as a release-candidate matrix, not the edit loop. Ordinary changes use static checks,
unit tests, and targeted behavioral cases; material runtime changes and release candidates run the
complete cross-host matrix. Identical workspace hashes may share one verified render only when the
reuse is explicit and hash-bound.

## Scale

| Score | Meaning |
| --- | --- |
| 0 | Fails the task or has a critical contradiction, fabrication, inaccessible path, or unfinished shell. |
| 1 | Material weakness; generic or fragile first pass; requires structural revision. |
| 2 | Competent and usable; some choices remain conventional, weakly evidenced, or under-resolved. |
| 3 | Strong, project-specific, coherent, verified, and appropriate to the requested ambition. |
| N/A | Dimension genuinely does not apply; explain why. |

## Perception dimensions

| Dimension | Review question |
| --- | --- |
| Project specificity | Which supplied fact, material, audience need, place, product, or constraint visibly explains the result after the logo, font, or palette is mentally removed? |
| Direction | Does one intelligible premise govern the composition, type, color, imagery, density, and behavior without becoming a reusable skill house style? |
| Task hierarchy | Do route silhouettes, section depth, labels, and emphasis follow the user's decisions and content importance rather than a default act recipe? |
| Contemporary fit | Does the result match its documented time register without accidental nostalgia or fashionable shorthand? |
| Typography | Do family, roles, spacing, wrapping, loading, and fragment emphasis serve real content and language? |
| Composition and density | Do grouping, rhythm, alignment, space, and surface roles fit the task across sizes? |
| Media and icons | Are assets purposeful, coherent, truthful, naturally varied where documentary credibility matters, accessible, responsive, and appropriately sourced without staged roughness? |
| Copy and IA | Are route structure, labels, headings, actions, exact claims, evidence, and states concrete and findable, with source-based copy texture rather than one repeated rhetorical machine? |
| Distinctiveness without novelty tax | Is the work memorable through relevant craft without breaking useful conventions or adding random irregularity? |

## Implementation dimensions

| Dimension | Review question |
| --- | --- |
| Functional completeness | Do visible controls, routes, forms, links, states, and recovery paths work or disclose their limits? |
| Responsive adaptation | Does the task survive continuous resizing, content pressure, input modes, zoom, localization, and virtual keyboards? |
| Accessibility baseline | Do semantics, keyboard, focus, contrast, reflow, labels, errors, media alternatives, and motion preferences hold? |
| Truth and provenance | Are claims, proof, data, calculator assumptions, assets, generated media, concepts, and integrations sourced, scoped, current, accurately labeled, and approved? |
| System and code | Are tokens, components, dependencies, metadata, comments, names, and architecture coherent with the repository and free of creative-brief or skill-jargon residue? |
| Performance and resilience | Are fonts, media, scripts, loading, failure, reduced-data, and low-performance behavior proportionate? |
| Residue | Are starter metadata, placeholder copy, dead paths, console failures, demo artifacts, and unexplained defaults absent? |
| Cultural and representational fit | Does the result respect language, directionality, local conventions, dignity, and audience context? |

## Critical blockers

A single confirmed blocker prevents a pass regardless of the average:

- fabricated or misleading factual proof;
- a visible primary control or route that is unusable without honest disclosure;
- a build or runtime failure on the critical path;
- a severe keyboard, focus, contrast, reflow, or assistive-technology barrier;
- unlicensed or privacy-violating material;
- accidental production mutation, live charge, tracking, or publication;
- a production-readiness claim that exceeds the checks actually performed.
- an explicit specificity concern declared closed without a final adversarial
  review bound to the delivered build.

## Comparative interpretation

Report per-dimension distributions, blocker counts, reviewer agreement, and
representative findings. Treat a one-point change in one run as noise until
repeated. A successful revision should improve route specificity, copy texture,
evidence-to-polish balance, and quality without producing a repeated house style
across routes or unrelated prompts.
