# Systems, components, and theming

Use this when creating or extending tokens, components, variants, or a third-party UI library.

## Inherit before inventing

For an existing product:

1. Inventory tokens, component variants, behaviors, accessibility patterns, and known exceptions.
2. Identify which choices are intentional brand language and which are accidental residue.
3. Reuse working conventions.
4. Change foundations only when the benefit and migration path are clear.

For greenfield work, define the smallest system that supports the real routes. Do not build a library for hypothetical screens.

## Theme dependencies deliberately

Framework and library defaults are valid scaffolding, not finished art direction. Review:

- palette and semantic tokens;
- font and type scale;
- radius, border, shadow, and elevation;
- spacing and density;
- icon family;
- control height and target size;
- focus, error, selection, and disabled states;
- motion and reduced-motion behavior.

Do not mechanically replace every default. Change the decisions that matter to project voice, task, and access.

## Design component contracts

For each component, define:

- purpose and content model;
- anatomy and semantic structure;
- variants and valid combinations;
- default, hover, focus, active, selected, disabled, loading, empty, error, success, and permission states;
- responsive behavior;
- keyboard and screen-reader behavior;
- localization and content limits;
- ownership of spacing, labels, icons, and actions.

Prefer composition over a large boolean-prop matrix. Prevent local pages from recreating token values.

## Govern exceptions

- Encode legitimate exceptions as named variants.
- Document why an exception exists and where it may be used.
- Remove dead variants and duplicate primitives.
- Review new tokens for an actual reusable role.
- Test components in page context, not only an isolated catalog.

## Detect first-pass residue

Check for untouched framework demo copy, stock palette/radius combinations, repeated generic cards, unused dependencies, dead controls, placeholder metadata, and components that look finished but do nothing. Treat these as fixable implementation evidence, not proof of authorship.
