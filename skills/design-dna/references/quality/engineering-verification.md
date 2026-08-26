# Engineering verification

Use this before declaring substantial web work complete. Scale the gate to the
change, but do not claim checks that were not run.

## Contents

- [Discover the project contract](#discover-the-project-contract)
- [Set the verification boundary](#set-the-verification-boundary)
- [Protect the accepted baseline](#protect-the-accepted-baseline)
- [Create useful project records](#create-useful-project-records)
- [Verify the implementation](#verify-the-implementation)
- [Verify design-code parity](#verify-design-code-parity)
- [Run visual and interaction regression](#run-visual-and-interaction-regression)
- [Run bounded source review](#run-bounded-source-review-when-proportionate)
- [Inspect the diff](#inspect-the-diff)
- [Protect external state](#protect-external-state)
- [Prepare production handoff](#prepare-production-handoff)
- [Completion record](#completion-record)

In every command below, replace `<DESIGN_DNA_SKILL_ROOT>` with the absolute
directory containing this installed `SKILL.md`. Quote that absolute path.
`PROJECT`, `TARGET`, and output paths refer to the website workspace, not the
skill directory. Never assume the current working directory is the installed
skill.

## Discover the project contract

Before implementation:

- read repository instructions and relevant documentation;
- inspect the framework, package manager, scripts, browser support, and
  deployment target;
- resolve or provisionally declare the project-specific
  [browser, engine, OS, and real-device support matrix](browser-support.md);
- resolve every dependency, version, and API surface from the project's own
  manifest and the current registry rather than from a remembered value;
  adopt the established package manager instead of replacing it, and leave
  unrelated dependency ranges untouched;
- identify the existing design system and testing conventions;
- map the authoritative sources for product facts, content, assets, tokens,
  components, interaction behavior, and release state;
- identify generated files, protected files and facts, integration contracts,
  and areas owned outside the requested change;
- preserve unrelated user changes;
- confirm whether data, integrations, tracking, and external services are live,
  mocked, or prohibited.

When design, documentation, code, and the deployed result disagree, do not
silently choose one. Determine whether the difference is approved, stale,
defective, environment-specific, or unresolved. Record consequential
ambiguity and ask the accountable owner only when it blocks a materially
different outcome.

## Set the verification boundary

Define the claim before choosing checks:

- exact routes, components, states, content sources, locales, themes,
  breakpoints, roles, and environments in scope;
- direct consumers and likely downstream consumers of changed shared tokens,
  primitives, components, data shapes, or interactions;
- the accepted behavior or artifact used for comparison;
- facts, files, contracts, integrations, and external state that must remain
  unchanged;
- the dimensions that cannot be verified in the available environment.

Scale breadth to risk. A copy correction may need a focused render and link
check. A token or shared-component change requires representative consumer
coverage. A route-family redesign requires cross-route, responsive, state,
interaction, and content review. A release claim requires the production
readiness boundary and applicable specialist gates.

## Protect the accepted baseline

Before consequential iteration, preserve an identifiable known-good
checkpoint using the project's established revision, branch, preview,
artifact, or backup mechanism. Record its identifier and environment. Do not
create a parallel versioning system when a reliable one exists.

Keep iteration reviewable:

1. choose one coherent scope, such as a token tier, component contract, route
   family, or user flow;
2. locate affected consumers and protected boundaries before editing;
3. create a new checkpoint when the scope reaches a stable review state;
4. compare it with the accepted baseline;
5. accept, revise, or restore before broadening the change.

Repository protections and generated-file rules are implementation controls;
a written instruction is not proof that a protected file remained unchanged.
Inspect the final diff and generated outputs. Never overwrite the only
recoverable accepted state of consequential work.

## Create useful project records

Capability classification controls the workflow; it does not by itself require
persisting every possible record. Initialize a profile only when its durable
records will preserve a consequential decision, evidence, or handoff. A small
project may complete a rigorous Standard or Showcase loop with concise working
notes and rendered evidence instead of a permanent internal dossier.

Initialize only records that preserve a consequential decision or evidence:

```text
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "PROJECT" --profile standard --json
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "PROJECT" --profile showcase --json
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "PROJECT" --profile range-study --json
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "PROJECT" --record direction --record handoff --json
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "PROJECT" --profile high-risk --json
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/owner_pattern_audit.py" "PROJECT" --init-review --json
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/owner_pattern_audit.py" "PROJECT" --phase prebuild --json
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/owner_pattern_audit.py" "PROJECT" --phase ready --json
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "PROJECT" --check-state --json
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "PROJECT" --check-prebuild --json
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "PROJECT" --check-ready --json
```

`PROJECT` is the application or repository boundary, not automatically its
static public root. Keep `.design-dna/`, source packets, review records,
transaction recovery, and private evidence outside anything that a local
server, deploy command, ZIP, or hosting adapter will publish. Record and pass
the narrower deployable root to serving, scanning, packaging, and rendered
capture tools. For a static concept with no existing structure, a useful shape
is `PROJECT/.design-dna/` beside `PROJECT/site/`; the name is an example, not a
required convention. Browser user data and other disposable runtime state
belong in a separately authorized temporary root, never in either tree.

`--check-state` verifies structure and reports draft records as warnings.
`--check-prebuild` is the broad-implementation permission gate. It requires a
selected, hash-bound, complete direction record and consumes any selected
exploration, calibration, proof, claims, Project Contrast, Direction Challenge,
Range/Batch planning, and Asset-led records. It fails when those records remain
draft or scaffold text; when Project Contrast is below
`direction-ready`; when Direction Challenge lacks reviewed cross-root proof,
its frozen independent observation, or an explicit `broad-implementation`
boundary; or when an Asset-led direction lacks a usable material asset. It is
not an aesthetic score and does not replace final review.
`--check-ready` is the completion gate: it uses the cumulative
`assurance_profiles` persisted in schema-2 `state.json` and fails until every
listed record is complete and hash-bound. Assets receive their own semantic
readiness checks. Record prose, a later capability request, or an explicitly
added record cannot silently weaken or escape the persisted gates.

The owner-pattern commands apply only when an accountable owner activates the
host-neutral contract and the project selects `owner-pattern-contract`. The
first command creates its project review once and refuses overwrite. The
integrated state, prebuild, and readiness checks call the matching audit when
the trigger is present; a missing or incomplete owner-pattern review therefore
cannot be bypassed by skipping the standalone command.

A standalone `--record` request intentionally selects only the named useful
record. `claims` and `user-validation` are supplemental evidence records, not
a High-risk classification: either one, or both together, can be selected for
an otherwise Standard project without silently creating the other record or a
High-risk gate. `--record` overrides `--profile`; select `--profile high-risk`
without `--record` when the project is actually consequential. That explicit
preset initializes direction, visual review, claims, and user-validation, and
its readiness gate requires the complete set. A `high-risk` evidence
capability is valid only alongside the High-risk assurance profile; it cannot
be selected on its own. Migration preserves any persisted High-risk profile or
capability even when its record inventory is incomplete, aligns the capability
to the profile, and adds only missing draft records. It never guesses from
claims or validation records that a new project is High-risk, and it never
downgrades a persisted consequential declaration because evidence is missing.
The compatibility
`validation` preset selects the standalone user-validation record and does not
select High-risk. The gate does not invent arbitrary records beyond selected
capabilities, run unlisted workflow or specialist reviews, or prove production
and launch readiness; apply those requirements separately when the delivery
claim needs them.

When an earlier schema is present, inspect the proposed migration before
applying it:

```text
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "PROJECT" --migrate --dry-run --json
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "PROJECT" --migrate --json
```

Substantive records begin as drafts. Mark one complete only after its contents
are reviewed and bound to the exact build or artifact file they describe:

```text
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "PROJECT" --mark-complete direction --binding-kind build --binding-id BUILD_ID --binding-path dist/index.html --completion-owner OWNER --limitations "No known limitations within the reviewed scope." --json
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "PROJECT" --mark-complete exploration --binding-kind artifact --binding-id EXPLORATION_ID --binding-path evidence/exploration-board.html --completion-owner OWNER --limitations "No known limitations within the reviewed exploration scope." --json
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "PROJECT" --mark-draft direction --json
```

The binding path is project-relative and its current SHA-256 is recorded.
Editing either the record body or bound artifact invalidates completion. Use
`--mark-draft` before revising an accepted record; do not hand-edit completion
metadata around that check.

Use `--dry-run` before a consequential refresh and `--force` only after
reviewing which packaged template files it will replace. Keep mutable state in
the project's `.design-dna/` directory, not in the installed skill. Follow each
record's classification and do not commit restricted research or confidential
material without its accountable owner's approval.

The initializer uses an exact rollback copy during each mutation. After a
validated additive merge or status-only update, it removes that task-generated
copy; a legacy migration or forced refresh retains a guarded recovery copy
because it can change or replace owner-authored structure. If staging or backup
cleanup cannot be verified, the result names the retained path instead of
claiming a clean transaction. Inspect that exact recovery state before any
owner-authorized cleanup; never use a broad `.design-dna*` deletion.

The helper validates structure and safety; it does not prove that a record's
claims or observations are complete or true. Review the substance and bind
visual evidence to the tested build. If Python 3.10+ is unavailable, create the
necessary records manually and disclose that helper validation did not run.

Use `showcase` only when the brief expressly calls for a premium, showcase, or
high-ambition answer, or when a rejected visual direction needs recovery; it
initializes exploration, direction, direction proof, and visual review. A
fresh public-facing site begins at Standard unless one of those Showcase
conditions is actually present.
Use `range-study` when independently addressable routes need deliberately
different creative worlds. It persists Standard plus Range Study capabilities
and adds the route-family record. Add Showcase separately only when the brief
independently meets its condition; route count, palette changes, or font
changes do not substitute for structural range or select Showcase.
Use `high-risk` for consequential flows that need direction, visual review,
claims, and user-validation records. The `--profile` values are request
presets, not mutually exclusive completion claims: repeated initialization
merges applicable capabilities, persists the canonical cumulative set, and
normalizes away redundant Quick or Standard tiers. `quick` and `standard` keep
completion requirements proportional; `substantial` and `greenfield` remain
compatibility aliases for Standard initialization.
Add `handoff` explicitly only for a maintained product, shared system, or
production-bound surface.

## Verify the implementation

For a Range Study, run the route-family audit after captures exist:

```text
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/route_family_audit.py" "." --render-review ".design-dna/render/render-review.json" --output ".design-dna/route-family-audit.json"
```

For a family larger than one rendered-review run can safely capture, produce
separate reports against the same build and repeat `--render-review` for every
batch. The family audit reconciles all declared routes and exact widths across
those reports; the renderer's per-run ceiling is an operational bound, not a
route-family design limit. Keep each report intact so every matched route and
viewport remains bound to its own report and screenshot hashes.

The default `.design-dna/route-atlas.html` is a dependency-free contact sheet
that references only project-local, hash-verified captures. Open it alongside
the JSON report for whole-family review. An explicit PNG atlas is optional and
requires Pillow; lack of that optional dependency must not block the portable
HTML evidence path.

Run the project-supported equivalents of:

- lockfile and dependency consistency inspection; run the project's established
  install only when required for the requested check and authorized by the
  task;
- formatter, lint, and typecheck;
- unit and integration tests affected by the change;
- production build;
- route or runtime smoke test;
- critical-path smoke tests in every materially different supported engine and
  real-device condition selected by the browser-support matrix;
- console and failed-network inspection;
- rendered visual review;
- accessibility baseline;
- performance checks proportional to changed assets or behavior.

Do not introduce a new tool only to satisfy this list when the project has an
established equivalent. Record unavailable checks and why.

Use the narrowest meaningful command first, then the established broader suite
when a shared contract or release boundary warrants it. A component test does
not cover every consumer; a full suite does not replace direct review of the
changed experience.

These checks establish only their recorded scope. Before using a broad
production or launch claim, apply the
[production-readiness boundary](production-readiness.md) and every specialist
gate triggered by the product, data, integrations, jurisdiction, and release
environment.

## Verify design-code parity

For consequential visual-system or component work, compare the accepted intent
with the implemented result. Use the project's existing mapping record when
one exists; otherwise create only the lightweight map needed for the scope.

Classify important design-to-code mappings as:

- **confirmed**: implementation, supported states, and rendered consumers were
  checked against the accepted intent;
- **partial**: the core mapping is known but named variants, states, tokens, or
  consumers remain unverified;
- **provisional**: the mapping is intentionally temporary or awaiting owner
  acceptance;
- **unknown**: available evidence cannot establish correspondence.

Check semantic structure, content and protected facts, token roles, component
anatomy, variants, responsive behavior, interaction states, keyboard and touch
behavior, themes, assets, typography, localization, reduced motion, and
resilient fallbacks as applicable. A matching name, generated mapping,
component-catalog example, or close screenshot is not enough to mark parity
confirmed.

Record intentional deviations and their owner. Resolve unapproved
implementation drift, or update a stale design artifact so the project does
not preserve two conflicting sources of truth. Mapping confidence describes
the evidence inspected; it is not a score for design quality.

## Run visual and interaction regression

Use the established visual or browser test system when available. Otherwise
perform a bounded manual comparison and preserve useful screenshots or notes.
Cover the changed scope plus representative shared consumers.

Visual regression should consider:

- reference narrow, intermediate, and wide widths plus responsive transition
  ranges where composition changes;
- default and supported themes, zoom or text enlargement, forced colors, and
  reduced motion when relevant;
- realistic, short, long, missing, localized, and error content;
- typography loading and fallback, media crop and failure, overflow, wrapping,
  stacking, alignment, focus visibility, and layout stability;
- page context, not only an isolated component specimen.

Interaction regression should exercise:

- keyboard, pointer, and touch paths appropriate to the control;
- hover, focus, active, selected, disabled, loading, empty, error, success, and
  permission states that the experience supports;
- navigation, deep links, history, focus movement, announcements, validation,
  cancellation, retry, and recovery where applicable;
- console errors, failed requests, duplicate submissions, stale state, and
  unintended external effects.

Image diffs, thresholds, snapshots, and automated event traces are signals for
review. They do not decide whether a difference is intentional, usable, or
visually coherent. Update an accepted baseline only after reviewing the
rendered change and binding it to the exact revision or build.

## Run bounded source review when proportionate

The optional scanner enforces high-severity gate findings by default:

```text
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/scan_project.py" "PROJECT" --json
```

Scanner classifications follow the scanner contract; do not silently remap
them through the human-review severity rubric.

The scanner is deliberately bounded to evidence-bearing source concerns:
literal filler, proof and claim provenance, content hidden by default,
nonfunctional public controls, public leakage of internal methodology or
unresolved production state, media truth/provenance/context, and incomplete
source coverage. A non-gating pre-heading candidate check may point to exact
heading- or section-leading-body relationships, including relationships through
bounded static wrappers, for contextual review. Known and unknown class tokens,
semantic-looking class or data names, text shape, and repetition are evidence
hints only: a name alone neither exempts nor condemns a label, and none
establishes AI authorship. The detector narrowly skips structurally strong
public roles such as navigation, form labels bound to controls, legends, time
elements, selected tabs, live status/progress semantics, and exact date or
progress text. Real categories, dates, sources, sequence, status, taxonomy,
breadcrumbs, filters, tabs, and legends can be necessary.

The scanner does not fail typography values, quantitative-claim density,
styled text fragments, gradients, pills, fade or hover recipes, emoji, icon
metaphors, generic calls to action, component-library tokens, large spacing,
technical vocabulary, diagrams, canvas/SVG, or any other aesthetic ingredient
by name or count. Judge those choices from the rendered result and an explicit
project concern, not from portable source heuristics. A consequential number
still needs provenance because of what it claims, not because a page contains a
particular count of figures. A pre-heading candidate is closed only by the
rendered [parseable-text](parseable-text.md) hierarchy review.

Use `--content-site` only when documentation and content sources are part of the
reviewed surface. Add `--structured-content` to opt in JSON, YAML, and YML;
those formats are never content-scanned by default. Sensitive configuration and
credential paths remain excluded unless a reviewed `--include` selects them, and
dependency/vendor trees remain excluded.

Read execution, source gate, selected scan scope, design-review trigger, and
exit policy as separate results. Inspect `execution_ok`,
`source_gate_passed`, `quality_status`, `scan_scope`, `scan_complete`,
`review_required`, `design_review_status`, and `exit_policy` independently. A
`design_review_status` of
`not-triggered-by-source` never waives rendered or explicit specificity review.
`--advisory-exit-zero` deliberately returns zero without changing a failed
`quality_passed` result. Unacknowledged eligible sources that cannot be decoded
or exceed the size limit keep the scan incomplete.

A scan of zero eligible source files cannot establish a source-quality pass.
Check that `PROJECT` names the intended root, that supported source exists, and
that the review did not select only ignored build, dependency, vendor,
credential, or private paths. Scan final generated output separately when the
source pipeline can materially change visible markup or styles.

For a justified exception, take the fingerprint from one actual current
overridable finding and have the scanner emit the entry:

```text
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/scan_project.py" "PROJECT" --emit-allowlist-entry FINGERPRINT --allowlist-entry-owner "OWNER" --allowlist-entry-reason "REVIEWED REASON"
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
requires a fresh review. A skipped-source acknowledgement must bind one exact
project-relative file with its current lowercase SHA-256 and exact
`size_bytes`; replacement or modification requires a new review.
Hand-written exceptions and skipped-source acknowledgements may expire no more
than 90 days in the future.
The high unfinished-filler gate applies to literal visible text nodes in HTML,
JSX/TSX, Liquid, Twig, Vue, Svelte, Astro, and MDX. Source-code strings and
unresolved dynamic template expressions remain advisory; explicit negative
examples are ignored.

An acknowledged skipped source remains `execution_ok: true` but
`source_gate_passed: false`, `quality_status: acknowledged-incomplete`, and
`scan_complete: false`. It keeps the default gate exit nonzero unless
`--advisory-exit-zero` is explicitly selected. Acknowledgement documents a
bounded omission; it never converts incomplete evidence into a pass.

The scanner is source-level evidence only. It cannot establish computed styles,
visible text after browser parsing, runtime-composed classes, shadow DOM,
canvas/WebGL pixels, image coherence, interaction behavior, or rendered
accessibility. Inspect the actual browser result for those dimensions.

For consequential font delivery, pair it with the dedicated bounded inventory:

```text
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/font_audit.py" "PROJECT"
```

The font report inventories declared and packaged evidence; it does not decide
whether a family is aesthetically appropriate, properly licensed, fully
covered for required glyphs, loaded by the browser, or associated with any
authoring method.

When Node.js 20 or newer, Playwright, and a compatible local Chromium-family
browser are available, create a separate machine-readable rendered capture:

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/rendered_review.mjs" "TARGET" --output "REVIEW_OUTPUT" --build-id BUILD_ID
```

Use a served local directory or authorized URL when multiple routes matter and
repeat `--route` for each in-scope path. For substantial review, create a
bounded capture-manifest JSON outside both the source and output trees and pass
`--capture-manifest "CAPTURE_MANIFEST"`. Use the command's `--help` contract as
the canonical field reference. Give every scenario a human-readable route and
state label, and derive exact widths, heights, preferences, input conditions,
and states from this project's supported audience, responsive transitions, and
risks. Manifest actions are intentionally
limited to `click`, `focus`, `fill`, `select`, and `check`; never try to encode
arbitrary JavaScript, cross-origin navigation, payment, submission, or another
consequential mutation. The harness applies the text-spacing override when
requested, but records 200% and 400% zoom as manual review still required
rather than pretending to simulate browser zoom.

Without a manifest, the reviewer uses its built-in compatibility matrix as a
convenience for broad discovery. That matrix is optional diagnostic coverage,
not a declaration of project breakpoints: it can be excessive for a bounded
repair and insufficient for a release. The report records console/network
events, layout overflow, normalized geometry and topology, computed typography
samples, computed font availability, media, focus traversal, current-viewport
peer-occlusion candidates, styled-fragment candidates, screenshots, and a
contact sheet. Occlusion candidates are bounded hit-test prompts rather than a
full-page visibility proof. These are neutral observations,
not composite-contrast measurement, glyph-level font proof, accessibility or
screen-reader results, aesthetic scores, authorship evidence, or a launch pass.
Review the findings and images, keep output outside the served source tree, and
bind accepted evidence to the exact build.

A generated command may repeat `--route` alongside `--capture-manifest` only
when those declarations normalize to the exact same route set as the manifest
scenarios; duplicate declarations are harmless, while missing or unexpected
destinations fail closed. In manifest mode, the declared scenario,
unique-route, and 72-capture ceilings govern instead of the compatibility-
matrix route limit.

When an accepted baseline and candidate were captured with the same frozen
schema-v3 contract, use the optional offline comparator described in
[`render-comparison.md`](render-comparison.md). It first
validates both owned evidence packages, then produces baseline, candidate, and
pixel-difference images without thresholds, masks, network access, baseline
mutation, or automatic approval. Bind its report and both build IDs into the
human visual-review record; a byte-identical result still requires human
review, and an incompatible contract must be recaptured rather than edited.

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

For the shipped HTML, CSS, and JavaScript itself, apply
[implementation integrity](implementation-integrity.md). Its silent-defeat
list covers declarations that parse, validate, and do nothing, which source
review and passing builds both miss by construction.

## Protect external state

Do not deploy, submit forms, create accounts, enable analytics, publish
tracking, charge payments, or mutate production data without explicit authority.
Use clearly labeled fixtures or local mocks.

## Prepare production handoff

For a production-bound change, provide the next accountable person with:

- the exact accepted revision, build, artifacts, and environment;
- scope, protected boundaries, authoritative sources, and approved design
  direction;
- token or component contract changes, lifecycle status, mapping confidence,
  migrations, compatibility constraints, and affected consumers;
- verified routes, viewports, themes, roles, content cases, interactions, and
  environments;
- supported browser/engine/OS/device rows actually exercised, plus every
  provisional, failing, or untested row;
- visual and interaction baselines that were intentionally accepted;
- known deviations, checks not run, specialist reviews still required, and
  owner decisions still open;
- deployment, configuration, cache, data-migration, monitoring, and rollback
  responsibilities where those systems are in scope.

Do not describe generated, built, previewed, staged, deployed, and live as the
same state. A handoff may prepare a release without authorizing it. Confirm
that documentation and examples describe supported behavior, deprecated
components identify a migration path, and no consumer must guess which source
or checkpoint is current.

## Completion record

Report:

- what changed;
- the verification boundary, protected facts and files, accepted baseline, and
  final revision or build;
- exact commands and checks run;
- routes, states, and environments inspected;
- measurable results;
- design-code mapping confidence, intentional deviations, changed system
  contracts, regression comparisons, and production-handoff state when
  applicable;
- final adversarial specificity-closure round and reviewer lens for every
  substantial new build or visual redesign, including the deeper lenses used
  when the request explicitly raised an AI-looking, vibe-coded, templated,
  generic, or house-style concern;
- checks not performed;
- remaining risks, placeholders, approvals, or owner decisions.

"Looks correct" is not a substitute for a build or browser check. A passing
build is not a substitute for rendered and task-level review.
