# Engineering verification

Use this before declaring substantial web work complete. Scale the gate to the change, but do not claim checks that were not run.

## Contents

- [Discover the project contract](#discover-the-project-contract)
- [Verify the implementation](#verify-the-implementation)
- [Run bounded source review](#run-bounded-source-review-when-proportionate)
- [Inspect the diff](#inspect-the-diff)
- [Protect external state](#protect-external-state)
- [Completion record](#completion-record)

## Discover the project contract

Before implementation:

- read repository instructions and relevant documentation;
- inspect the framework, package manager, scripts, browser support, and deployment target;
- identify the existing design system and testing conventions;
- preserve unrelated user changes;
- confirm whether data, integrations, tracking, and external services are live, mocked, or prohibited.

## Verify the implementation

Run the project-supported equivalents of:

- lockfile and dependency consistency inspection; run the project's established
  install only when required for the requested check and authorized by the
  task;
- formatter, lint, and typecheck;
- unit and integration tests affected by the change;
- production build;
- route or runtime smoke test;
- console and failed-network inspection;
- rendered visual review;
- accessibility baseline;
- performance checks proportional to changed assets or behavior.

Do not introduce a new tool only to satisfy this list when the project has an established equivalent. Record unavailable checks and why.

These checks establish only their recorded scope. Before using a broad
production or launch claim, apply the
[production-readiness boundary](production-readiness.md) and every specialist
gate triggered by the product, data, integrations, jurisdiction, and release
environment.

## Run bounded source review when proportionate

The optional scanner enforces high-severity gate findings by default:

```text
python scripts/scan_project.py PROJECT --json
```

Use `--content-site` only when documentation and content sources are part of the
reviewed surface. Add `--structured-content` to opt in JSON, YAML, and YML; those
formats are never content-scanned by default. Sensitive configuration and
credential paths remain excluded unless a reviewed `--include` selects them,
and dependency/vendor trees remain excluded.

Read execution, source gate, selected scan scope, design-review trigger, and
exit policy as separate results. A `design_review_status` of
`not-triggered-by-source` never waives rendered or explicit specificity review.
`--advisory-exit-zero` deliberately returns zero without changing a failed
`quality_passed` result. Unacknowledged eligible sources that cannot be decoded
or exceed the size limit keep the scan incomplete.

For a justified exception, take the fingerprint from one actual current
overridable finding and have the scanner emit the entry:

```text
python scripts/scan_project.py PROJECT --emit-allowlist-entry FINGERPRINT --allowlist-entry-owner "OWNER" --allowlist-entry-reason "REVIEWED REASON"
```

Review and merge that output. Owner policy values guide and annotate review;
they do not suppress findings. Literal unfinished-filler `placeholder-proof`
findings are high-severity release gates. Because the literal can also be
legitimate specimen, quotation, or teaching content, an owner may except only
the exact reviewed finding through the path-, line-, fingerprint-, owner-, and
expiry-bound allowlist. Proof-shaped claims that might be valid remain
provenance advisories. The printed and packaged examples are non-usable
placeholders. Finding fingerprints bind the reported signal payload, and
expiry values use the exact `YYYY-MM-DD` string form, so changed evidence
requires a fresh review. Hand-written exceptions and skipped-source
acknowledgements may expire no more than 90 days in the future.
The high unfinished-filler gate applies to literal visible text nodes in HTML,
JSX/TSX, Liquid, Twig, Vue, Svelte, Astro, and MDX. Source-code strings and
unresolved dynamic template expressions remain advisory; explicit negative
examples are ignored.

Compound type/palette advisories identify a display or headline serif role and
signal cluster, including literal `font-serif` utility use on a prominent
heading; they do not blacklist named font families.

## Inspect the diff

Review:

- scope and unintended file changes;
- secrets, private data, and environment assumptions;
- unused imports, packages, flags, components, and assets;
- dead controls, links, and routes;
- starter titles, metadata, favicons, demo copy, and placeholder proof;
- exact claims, calculator assumptions, sources, owners, locale/scope, review
  dates, expiry, and public treatment;
- comments, names, and public source for creative-brief narration,
  skill-specific meta-language, or repeated house-style residue;
- error, empty, loading, disabled, and permission states;
- responsive behavior and localization;
- source licenses and generated-asset disclosures;
- whether screenshots match the final build.

## Protect external state

Do not deploy, submit forms, create accounts, enable analytics, publish tracking, charge payments, or mutate production data without explicit authority. Use clearly labeled fixtures or local mocks.

## Completion record

Report:

- what changed;
- exact commands and checks run;
- routes, states, and environments inspected;
- measurable results;
- final adversarial specificity-closure round and reviewer lens when the request
  explicitly raised an AI-looking, vibe-coded, templated, generic, or
  house-style concern;
- checks not performed;
- remaining risks, placeholders, approvals, or owner decisions.

“Looks correct” is not a substitute for a build or browser check. A passing build is not a substitute for rendered and task-level review.
