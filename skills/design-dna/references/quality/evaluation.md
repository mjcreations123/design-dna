# Visual and product evaluation

Use this after a representative implementation exists. Evaluate the final implementation round, not an obsolete screenshot.

## Separate review lenses

Run two distinct passes:

- **Perception review:** screenshots or recordings for specificity, hierarchy, composition, currentness, coherence, credibility, and generic-pattern clusters.
- **Implementation review:** live behavior, semantics, content, states, responsiveness, accessibility, performance, and engineering quality.
- **Specificity closure:** when the request explicitly rejects an AI-looking,
  vibe-coded, templated, generic, or repeated house-style result, run the
  [adversarial specificity review](specificity-review.md) on the final candidate
  and repeat affected checks after revision.

A screenshot cannot prove keyboard behavior or truth. A test suite cannot prove visual hierarchy.

## Build the matrix

Select representative routes and critical states. Include:

- narrow, intermediate, common, wide, and short-height viewports;
- touch, keyboard, pointer, hover/no-hover, and reduced motion as relevant;
- default, loading, empty, error, success, disabled, permission, and destructive states;
- short, long, missing, translated, and RTL content when supported;
- theme, zoom, text enlargement, and high contrast where applicable;
- production-like data without exposing private information.

## Review questions

1. **Specificity:** Which real project material explains the result?
2. **Clarity:** Is the next task and information sequence evident?
3. **Route silhouette:** Do route and section structures follow distinct user
   questions rather than one repeated showcase recipe?
4. **Copy texture:** Do headings, labels, actions, numbers, and ending lines
   avoid an unsupported rhetorical machine while preserving supplied voice?
5. **Evidence balance:** Is every polished proof module supported by truthful
   content, ownership, limits, and maintenance?
6. **Coherence:** Do tokens, components, imagery, language, and behavior form one system?
7. **Credibility:** Are claims, proof, assets, controls, metadata, and states truthful?
8. **Usability:** Can people complete, understand, recover, and adapt the experience?
9. **Resilience:** Does it survive content, viewport, input, network, and preference changes?

## Evidence

For each capture or recording, store:

- route and state;
- viewport, zoom, input, browser/version, and theme;
- build or commit identifier;
- capture date;
- artifact path;
- reviewer and review lens.

Record findings with severity, evidence, fix, verification, and remaining limitation. Do not calculate an “AI probability” or declare authorship from aesthetic signals.

For explicit specificity closure, record the final review round, observed
clusters and counterevidence, revisions, rerun checks, reviewer lens, accepted
exceptions, and remaining limitations. Self-review is not independent
perception evidence.
