# Rendered and behavioral review rubric

Use this after the infrastructure runner has produced an artifact. Command success and file presence do not establish design quality.

## Review protocol

1. Run each release-counted high-value prompt at least three times for both the skill variant and
   the unchanged baseline.
2. Randomize artifact labels so perception reviewers do not know model, host, skill, or baseline.
3. Review final rendered routes before reading implementation details.
4. Run implementation, accessibility, and task checks separately.
5. Record every applicable score as a value plus its own concise rationale and
   hash-bound evidence. Bind the review to a case, run, build hash, route/state,
   viewport, browser, and date. A bare number is not review evidence; mark a
   dimension not applicable with rationale and evidence instead of guessing.
6. Record disagreement and unperformed checks. Do not average away a critical blocker.
7. For prompts that explicitly reject an AI-looking, vibe-coded, templated,
   generic, or repeated house-style result, run a final adversarial specificity
   closure after revisions and bind it to the reviewed build.
8. Run a blinded entry-perception check for public concepts. For task, service,
   and product work, ask whether the offer or task, relevant audience or
   situation, useful action, and prominent controls are understandable without
   the creative brief. For art, narrative, editorial, or entertainment work,
   ask whether the intended invitation, orientation, continuation, and degree
   of unfolding are legible. Record which question the experience is meant to
   answer instead of forcing every genre into conversion-page behavior.
9. Treat direct accountable-owner rejection as a hard failure for the affected
   artifact. An automated pass, producer self-review, or different agent cannot
   overrule it; revise and rerender before seeking a new disposition.
10. On an expressive, energetic, memorable, premium, or showcase brief, a
    `Direction` or `Distinctiveness without novelty tax` score of 3 requires a
    visibly excellent, project-fitting, well-resolved result. It may achieve
    that through singular, plural, layered, conventional, ornamental,
    restrained, maximal, or deliberately dissonant logic. No signature device,
    channel count, novelty bet, or loud/quiet sequence is required.
11. When the run-bound review contract contains
    `release_coverage.expressive_perception_gate: true`, every perception
    review counted toward release must score exactly 3 for both `Direction`
    and `Distinctiveness without novelty tax`. This is an opt-in absolute
    quality floor for marked Showcase or expressive cases, not a novelty
    requirement for quiet, utilitarian, or otherwise unmarked work.
12. When the contract contains `quiet_perception_gate: true`, a counted
    perception review must score exactly 3 for `Direction`,
    `Project specificity`, and `Distinctiveness without novelty tax`. The
    reviewer should find authored, project-specific restraint; louder color,
    scale, motion, or decoration is neither required nor sufficient.
13. When the contract contains `route_family_showcase_gate: true`, bind a
    `route_family_analysis` to the exact route-family manifest and reviewed
    build. Every declared route must be a unique directly addressable path,
    every route must have matched required-width capture evidence, and no
    unresolved repeated-skeleton cluster may remain. A hash, query parameter,
    alias, redirect, or client-side state name does not establish another
    route. A passing machine report is necessary evidence, never an automatic
    aesthetic pass.
14. When the contract contains `cultural_context_gate: true`, bind a
    `cultural_context_review` for the exact candidate. `accepted` requires a
    named accountable community authority or owner-authorized cultural
    reviewer who is not the producer. Producer self-review, a separate
    automated agent, technical bidi or language checks, and a `pending` or
    `rejected` disposition cannot satisfy the gate.

Do not ask whether a site “looks AI-made.” Ask whether its visible choices are specific, coherent, current for its intended time register, truthful, usable, and finished.

## Release evidence contract

A release review is attributable evidence, not a declaration that evidence exists:

- Record a stable build producer, reviewer identity, review-process identity, method, time, and a
  process record that names them. `independent: true` is accepted only with a different producer and
  a separate-person, separate-agent, blinded-panel, or independent-specialist process.
- A premium, showcase, sale-readiness, or accountable-owner-sensitive visual
  claim additionally needs human visual acceptance from the accountable owner
  or a named owner-authorized human approver. A separate agent is useful
  adversarial evidence but does not satisfy this acceptance.
- Record that decision in `owner_disposition`. Use a stable person or account
  identity rather than a role such as `owner`, bind `candidate_id` to the exact
  review build, and declare `claim_scope` as `standard`,
  `premium-showcase-sale-readiness`, or `accountable-owner-sensitive`.
  Accepted, rejected, and `not-required` dispositions cite nonempty UTF-8 JSON,
  Markdown, text, or log evidence that names the exact status, decision-owner
  ID, candidate ID, and reviewed timestamp. The timestamp cannot predate the
  captured build or be in the future. Pending may retain request or
  partial-feedback evidence but remains a release block. `not-required` is an
  accountable, evidenced decision available only to `standard`; it cannot
  waive required human acceptance.
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
- For a conditional generated-image case, record the run or host capability
  disposition. When capability is declared available and media is used, bind
  the review to real decodable local files, provenance, a contact sheet,
  artifact inspection, and the final responsive crops. When capability is
  explicitly unavailable, record that limitation and leave generation,
  contact-sheet, crop, and visual-artifact checks unperformed; do not simulate
  files or provenance. Image generation is not mandatory for unmarked cases.
- For a route-family case, record the normalized route path, direct-entry
  result, matched capture status, and rendered-body summary for every declared
  route. Compare closest siblings through their actual jobs and observable
  decisions. Include normalized geometry, content bands, focal placement,
  density, media/control geometry, typography roles, fixed/sticky regions, and
  viewport transformation when relevant. No route must differentiate on every
  dimension. Shared navigation and accessibility foundations are not
  repetition defects; recolored, reworded, or rephotographed copies are.
- For a culturally central or material case, record the exact authority,
  terminology decisions, representation decisions, open questions, review
  time, and evidence. Technical Hebrew, RTL, font, and assistive-technology
  verification remains separate from wording and representation acceptance.
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
The counted set must also contain at least two distinct cases whose run-bound
contract marks `expressive_perception_gate: true`; both need qualifying
same-build perception evidence at the absolute score floor above. One strong
showcase sample cannot establish expressive reliability.
It must also contain at least one marked quiet-specific case meeting its three
absolute perception floors. When bound host or run evidence declares image
generation available, the counted set must include at least one marked
generated-media capability case using real generated image files with
hash-bound availability, artifact, and inspection evidence. A bound
`unavailable` disposition leaves that conditional gate inactive and may not
claim generated artifacts or inspection.
The counted set must additionally contain at least one case marked
`route_family_showcase_gate: true` with a passing same-build
`route_family_analysis`, and at least one case marked
`cultural_context_gate: true` with an accepted same-build
`cultural_context_review`. One case may satisfy both gates only when all route
and cultural evidence independently qualifies; neither gate may be inferred
from the other.

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

Keep the comparison calibrated: the expressive absolute floor does not force a
`skill-stronger` label. Record `tie`, `mixed`, or `skill-stronger` according to
the evidence for each case and run. The separate supported skill-benefit
requirement remains release-level evidence, not permission to inflate every
expressive comparison.

Add one release-level cross-case analysis bound to the counted mobile and desktop render hashes and
covering the exact same four-mode counted set. Every analysis must include `rendered_geometry` and
an identity-blinded pass: randomize neutral artifact labels, hide model, host, variant, producer, and
case identity as the protocol requires, and freeze the first comparison observation before reveal.
Identity blinding does not alter or redact the source pixels. Choose any additional lenses from
evidence in the actual projects and rendered outputs, not from a universal checklist. Typography
roles, color or material behavior, label or section cadence, component grammar, motion, media, CTA
endings, and responsive transformations are useful non-exhaustive examples, not a required set.

Pixel transformations are optional and exceptional. Use one only for a stated comparison hypothesis
or an authorized privacy-minimization need. Bind the authority, method, original and transformed
hashes, and coverage impact; do not certify an unmeasured `geometry-preserved` claim. A transformed
artifact cannot silently replace the verified original or support conclusions about details it
removed or displaced.

Record this as cross-case analysis schema 2 under
`identity_blinded_comparison`. Use unique neutral labels and the original
responsive render hashes for every counted case. The default
`pixel_transformation` value is `null`.

For every declared lens, record applicability and supporting evidence. When it applies, record
task-derived similarities, differences, and counterevidence; when it does not, explain why without
manufacturing a difference or counterevidence. Similarity is not a defect by itself, and difference
is not a quota. Track repeated clusters explicitly. A resolved cluster needs its cause, cause-level
resolution, and hash-bound independent verification; an unresolved cluster blocks the pass.

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
| Project specificity | Which supplied fact, material, audience need, place, product, constraint, or accountable aesthetic intent visibly explains the result, and does it remain more than a cosmetic reskin of an unrelated project? Judge specificity in the medium the direction actually uses; image-led work may depend on images and typographic work may depend on type. |
| Direction | Does the chosen logic—singular, plural, layered, conventional, restrained, maximal, ornamental, or deliberately contradictory—feel intentional, fitting, and well executed without becoming a reusable skill house style? Does the result meet the requested ambition? Does an unbriefed entry-perception check succeed on the questions appropriate to this experience: task and action clarity where immediate action matters, or invitation, orientation, continuation, and intended unfolding for narrative or exploratory work? |
| Task hierarchy | Do route silhouettes, section depth, labels, and emphasis follow the user's decisions and content importance rather than a default act recipe? |
| Time-register fit | Does the result match its documented time register without accidental nostalgia or fashionable shorthand? |
| Typography | Do family, roles, spacing, wrapping, loading, and fragment emphasis create convincing art direction for the actual content and language? Are tracking, leading, width or stretch, size, weight, and measure comfortable in combination? A common family may excel and an unusual family may fail; names and rarity are not scores. |
| Composition and density | Do grouping, rhythm, alignment, space, and surface roles fit the task across sizes? |
| Media and icons | Are assets purposeful, coherent, truthful, accessible, responsive, and appropriately sourced without staged roughness? For a sensory or physical subject, does the chosen media strategy communicate the project-specific qualities and visitor decisions the direction depends on, or is media presence or absence merely an unexamined fallback? No shot list, asset count, documentary style, or photo requirement applies universally. |
| Copy and IA | Are route structure, labels, headings, actions, exact claims, evidence, and states concrete and findable, with source-based copy texture rather than one repeated rhetorical machine? |
| Distinctiveness without novelty tax | Is the rendered combination specific and memorable enough for this task without relying on subject swaps, surface-only substitutions, random irregularity, or forced novelty? Useful convention, restraint, ornament, spectacle, accumulation, and local variation may all be valid. |

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
- an accountable-owner rejection of the reviewed candidate that has not been
  revised, rerendered, and newly dispositioned.
- an accountable-owner finding that the reviewed candidate is plain, boring,
  under-designed, too safe, or short on energy that has not been revised,
  rerendered, and newly dispositioned.
- a premium, showcase, or sale-readiness visual claim based only on producer or
  agent review without required accountable human acceptance.

## Comparative interpretation

Report per-dimension distributions, blocker counts, reviewer agreement, and
representative findings. Treat a one-point change in one run as noise until
repeated. A successful revision should improve route specificity, copy texture,
evidence-to-polish balance, and quality without producing a repeated house style
across routes or unrelated prompts.
