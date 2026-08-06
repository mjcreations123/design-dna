# Systems, components, and theming

Use this when creating or extending tokens, components, variants, or a
third-party UI library.

## Contents

- [Scale the system to the work](#scale-the-system-to-the-work)
- [Inherit before inventing](#inherit-before-inventing)
- [Establish sources of truth](#establish-sources-of-truth)
- [Structure token tiers](#structure-token-tiers)
- [Theme dependencies deliberately](#theme-dependencies-deliberately)
- [Design component contracts](#design-component-contracts)
- [Map design intent to implementation](#map-design-intent-to-implementation)
- [Preserve design-code parity](#preserve-design-code-parity)
- [Manage the component lifecycle](#manage-the-component-lifecycle)
- [Govern exceptions](#govern-exceptions)
- [Iterate through bounded checkpoints](#iterate-through-bounded-checkpoints)
- [Hand off a usable system](#hand-off-a-usable-system)
- [Detect first-pass residue](#detect-first-pass-residue)

## Scale the system to the work

Use the amount and form of governance that the real consumers, lifetime,
ownership, and change risk justify. A one-off may need only protected decisions
and working states; a durable shared product may need versioning, ownership,
migration, parity evidence, and consumer documentation. Those are possible
responses, not scope tiers or a required abstraction stack.

Do not create a registry, package, token alias, variant, or governance ceremony
without a current consumer or a named, funded near-term need. Conversely, do
not withhold useful structure merely to keep a system visually simple. Scale
process to risk while preserving working states, accessibility, and rendered
verification.

## Inherit before inventing

For an existing product:

1. Inventory tokens, component variants, behaviors, accessibility patterns, and
   known exceptions.
2. Identify which choices are intentional brand language and which are
   accidental residue.
3. Reuse working conventions.
4. Change foundations only when the benefit and migration path are clear.

For greenfield work, define the system the real routes and intended maintenance
need. It may be spare, rich, route-specific, layered, or deliberately plural.
Do not build abstractions solely for hypothetical screens.

## Establish sources of truth

Before changing foundations, map each consequential concern to its accountable
source. A design file, component catalog, code repository, content document,
and deployed interface may each be authoritative for different decisions.

| Concern | Record |
| --- | --- |
| Product facts and public copy | Approved source, accountable owner, locale, and review date where material. |
| Brand and art direction | Approved direction, assets, permitted transformations, and known exceptions. |
| Tokens and components | Canonical implementation, supported variants, consumers, and maintainer. |
| Interaction and responsive behavior | Executable implementation, behavioral specification, or accepted rendered evidence. |
| Release state | Exact revision or build, environment, and known deviations. |

Do not silently resolve a disagreement by copying whichever artifact is easiest
to access. Determine whether the difference is an intentional implementation
decision, stale design, code defect, content change, or environment issue.
Preserve protected facts, files, generated contracts, and integration
boundaries. When authority remains ambiguous and the choice is consequential,
surface the conflict to the accountable owner.

## Structure token tiers

Make the token model traceable and fit for its consumers. Reference,
semantic, component, contextual, and instance values are available patterns,
not required tiers; a project may combine, rename, omit, or extend them. Some
systems benefit from semantic roles across themes, while expressive route
families may also need local material, spatial, typographic, or motion values
that should not be promoted merely because they recur.

Record what each abstraction controls, who consumes it, and how a maintainer
traces it to the rendered result. Define contrast, forced-colors, theme,
high-zoom, and reduced-motion behavior where a value can affect them. Avoid
aliases or duplication that obscure authority, but do not reject a local or
visually named value when that is the clearest truthful model.

## Theme dependencies deliberately

Framework and library defaults are valid inputs, not automatic art direction.
Review the aspects that materially affect this project, which may include:

- palette and semantic tokens;
- font and type scale;
- radius, border, shadow, and elevation;
- spacing and density;
- icon family;
- control height and target size;
- focus, error, selection, and disabled states;
- motion and reduced-motion behavior.

Do not mechanically keep or replace every default. Make the decisions that
matter to project voice, task, access, and maintainability.

## Design component contracts

For each component, define only the contract its consumers and risks need. That
may include:

- purpose and content model;
- anatomy and semantic structure;
- variants and valid combinations;
- applicable resting, interaction, system, data, failure, and permission states;
- responsive behavior;
- keyboard and screen-reader behavior;
- localization and content limits;
- ownership of spacing, labels, icons, and actions.

Use composition, variants, configuration, bespoke implementations, or a
combination according to the actual contract. Prevent local pages from
accidentally forking shared behavior while preserving justified one-offs.

## Map design intent to implementation

Maintain a lightweight map for consequential shared elements. It may live in
existing system documentation; do not duplicate a working source.

For each mapped item, identify:

- the design concept or artifact and the implemented component, primitive, or
  pattern;
- corresponding properties, variants, slots, states, tokens, breakpoints, and
  content constraints;
- whether the mapping is **confirmed**, **partial**, **provisional**, or
  **unknown**, with the evidence and reviewer;
- intentional deviations and which side is expected to change;
- the routes or consumers used to verify the mapping.

Mapping confidence describes evidence, not aesthetic quality. A name match,
screenshot resemblance, generated suggestion, or imported component is not a
confirmed mapping by itself. Confirm important mappings in rendered context
with representative content and behavior. If a mapping is partial or unknown,
preserve the uncertainty rather than inventing missing variants or
interactions.

## Preserve design-code parity

Parity means that the accepted intent survives the implemented system, not
that every design-layer value is copied literally. Compare:

- semantic structure, content order, labels, and protected facts;
- token roles and theme behavior rather than only sampled colors;
- component anatomy, composition, variants, and state transitions;
- responsive reflow, content extremes, localization, and media behavior;
- focus order, keyboard and touch behavior, announcements, contrast, and
  reduced-motion behavior;
- icons, assets, crops, type loading, and fallbacks;
- intended exceptions and known implementation constraints.

Review the real implementation at relevant widths and states. When the design
artifact is stale, update or annotate it; when implementation drift is
unapproved, correct the implementation. Do not maintain a fictional parity
claim between two visibly different sources.

## Manage the component lifecycle

Use lifecycle states when multiple consumers need them. The project may adopt,
rename, extend, or replace labels such as:

- **provisional**: being proven in real page context and not yet a default;
- **supported**: documented, tested, owned, and safe for its named use;
- **deprecated**: still present for migration, with replacement and deadline
  where one is known;
- **retired**: no supported consumers remain and the implementation can be
  removed through the project's normal change process.

Before promoting a component, verify its actual content range, states,
responsive containers, theming, and accessibility. Before changing a supported
contract, locate consumers and choose a compatible change, migration, or
versioned break. Before retirement, prove that consumers, documentation,
tests, assets, tokens, exports, and examples have been reconciled.

## Govern exceptions

- Represent legitimate exceptions in the form their ownership and consumers
  can understand; a named variant, local composition, or documented one-off may
  each be correct.
- Document why consequential exceptions exist and where they apply.
- Reconcile dead or misleading variants and accidental duplicate primitives.
- Review new abstractions for an actual role without requiring every repeated
  aesthetic decision to become shared.
- Test components in page context as well as any isolated catalog that exists.

## Iterate through bounded checkpoints

For consequential system work, preserve an identifiable accepted baseline and
make changes in reviewable scopes such as one token family, component, route
family, or interaction contract. At each useful checkpoint:

1. record the revision or build and the intended scope;
2. inspect affected consumers and dependencies;
3. render representative states and containers;
4. compare visual, interaction, accessibility, and content behavior with the
   accepted baseline;
5. accept, revise, or revert before broadening the change.

Use the project's existing versioning, branch, preview, or artifact mechanism.
Do not require heavyweight infrastructure for a small change, but do not
overwrite the only known-good state of consequential shared work.

## Hand off a usable system

A production handoff for shared system changes should state, proportionately:

- canonical sources and the exact accepted revision or build;
- actual abstractions, supported themes, components, variants, and lifecycle
  states where used;
- mapping confidence, intentional deviations, and unresolved parity gaps;
- protected facts, files, contracts, and integration boundaries;
- migration steps, compatibility notes, and rollback boundary;
- verified routes, states, viewports, inputs, assistive behavior, and
  environments;
- owners for maintenance, content, design decisions, and implementation;
- checks not run and release decisions still required.

Examples and documentation must exercise supported behavior rather than stage
impossible ideal content. A handoff is not complete when consumers must infer
which source is current or which deviations are intentional.

## Detect first-pass residue

Check whether starter decisions survived without project rationale, repeated
structures or values drifted from their intended relationship, dependencies or
variants are unused, controls are dead, metadata is unfinished, or components
look operational without working behavior. Diagnose the concrete residue; do
not use a palette, radius, component family, or other ingredient as proof of
authorship.
