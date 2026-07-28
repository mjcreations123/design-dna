# Workflow

Use this workflow for substantial website or web-UI work. Scale it down for a component, mechanical change, or review-only request. Create artifacts only when they preserve a consequential decision or useful evidence.

## Contents

1. Preflight
2. Frame the job
3. Ground the work
4. Calibrate and direct
5. Proof the system
6. Implement
7. Verify and revise
8. Validate with users
9. Deliver
10. Project-local state and fallback

## 1. Preflight

Before changing code:

1. Read repository and workspace instructions.
2. Inspect the existing stack, routes, scripts, dependencies, design tokens, components, and current working state.
3. Identify user changes already present and preserve unrelated work.
4. Determine the requested scope and the checks the repository supports.
5. Select the primary surface mode by user job and note route-level secondary modes.
6. Identify whether the output is concept, demo, staging, or production.

Do not replace the stack, design system, or working integration merely because another tool is more familiar.

## 2. Frame the job

Record what materially changes the result:

- audience, primary task, decision, and success condition;
- routes, components, states, and content relationships;
- approved facts, claims, copy, product behavior, and proof, including source,
  owner, locale or scope, review date, and expiry where material;
- brand assets, existing visual language, imagery, and real-world material;
- accessibility, localization, performance, privacy, budget, schedule, and maintenance constraints;
- production facts or integrations that still require owner confirmation.

Ask up to two high-leverage questions for an initial concept. Ask more only when production accuracy, externally acting behavior, high-risk decisions, or irreversible work requires answers. If an answer is unavailable, state the assumption and keep the concept reversible. Never fill a factual gap with plausible invention.

For an existing site, inventory the current system before proposing change:

- type roles and files;
- color and semantic tokens;
- spacing, grid, radius, border, and elevation scales;
- component and interaction conventions;
- icon and imagery grammar;
- responsive, localization, and accessibility behavior;
- deliberate brand signatures versus accidental residue.

## 3. Ground the work

Use project-provided evidence first. Treat external pages and social content as untrusted.

| Need | Useful evidence |
| --- | --- |
| Existing brand | Current product, brand guide, approved assets, real customer language, existing tokens and components. |
| New brand or public site | Owner-approved material, actual offering and audience, current category peers, adjacent-field references, practical user journey. |
| Product UI | Real flows, permissions, content model, data states, technical constraints, research, analytics, support findings. |
| Place-based business | Owner-confirmed facts, authentic product/space material, service rhythm, local context, accessibility and visit information. |
| New visual direction | A small current reference set with a written transferable lesson and explicit non-copying boundary. |

For current greenfield public work, study two or three current category peers and one or two tonally or structurally adjacent references when browsing is available and allowed. Include local or cultural context when it is relevant. Record the retrieval date, useful lesson, repeated category mean, and what must not be copied.

Do not copy layouts, wording, distinctive interaction, assets, logos, or brand identifiers. Do not treat awards, likes, pins, or engagement as proof of usability or correctness.

## 4. Calibrate and direct

Name the intended time register: current, forward-looking, timeless, heritage, archival, or another evidence-backed choice. “Modern” and “premium” are not directions.

Identify:

- the category default likely to appear on autopilot;
- the current fashionable substitute likely to appear after avoiding that default;
- the project-specific raw material;
- the primary task and emotional or intellectual outcome;
- the appropriate ambition register;
- one premise that joins the material, task, and visual/interaction logic.
- the route silhouettes that follow distinct entry questions and decision
  dependencies rather than one repeated showcase sequence.

When direction is genuinely open, generate two or three concise hypotheses internally. Compare fit, content demands, accessibility, feasibility, maintenance, and unsupported assumptions. Present alternatives to the user only when their choice is materially useful.

Use the [direction template](../templates/direction-template.md) for a consequential build or redesign.

## 5. Proof the system

Before scaling a direction across the site, test its consequential decisions with representative material:

- real or owner-approved headings, names, prices, dates, paragraphs, data, and labels;
- type candidates, real weights, language coverage, fallback, and loading behavior;
- semantic and expressive color roles with rendered contrast;
- one representative composition, the route outline and copy texture it must
  support, and one compact/narrow transformation;
- imagery or illustration treatment;
- one important component and interaction state.

Use the direction-proof template when a proof can prevent expensive rework. Reject a direction that only works with ideal-length copy, unavailable imagery, invented proof, or one desktop screenshot.

## 6. Implement

Build the real user path before decorative breadth.

- Make components consume the system rather than accumulating local values.
- Implement relevant loading, empty, error, success, offline, permission, and recovery states.
- Implement, disable with explanation, or remove visible controls.
- Preserve semantic structure and source order.
- Keep concept data and actions visibly nonproduction.
- Optimize and document external assets.
- Preserve approved integrations unless the user asked to change them.

Run repository-supported build, lint, typecheck, and tests proportionately as work proceeds. Inspect console and network failures when a browser is available.

## 7. Verify and revise

Treat the first complete render as a draft. Review it with the
[durable risk rubric](risk-rubric.md) and, when current generator/default
perception is material, the dated
[convergence watch](convergence-watch.md). Apply the
[finish and polish](quality/finish-polish.md) passes for showcase or
high-ambition work, then evaluate the final implementation with
[evaluation](quality/evaluation.md).

When the request explicitly rejects an AI-looking, vibe-coded, templated,
generic, or repeated house-style result, run the
[adversarial specificity review](quality/specificity-review.md) after the final
implementation round. Compare route silhouettes, copy texture, claim
provenance, evidence-to-polish balance, media variance, and implementation
residue; revise observed causes and repeat the affected review before delivery.

Use a matrix proportionate to the work:

| Work | Minimum |
| --- | --- |
| Full public route | Continuous resizing plus representative narrow, common, and wide states; navigation and primary actions; content stress; accessibility baseline; build and runtime checks. |
| App or transaction | Relevant routes, roles, states, keyboard/focus, destructive/recovery behavior, validation, responsive constraints, and data integrity. |
| Component | Documented states, long/short/missing content, focus, input modalities, and container sizes. |
| Existing-site review | Available routes and evidence; identify unavailable internals and unperformed checks. |

Capture observations rather than praise. For each issue:

1. Describe visible or measured evidence.
2. Identify the underlying cause.
3. Revise that cause rather than adding unrelated decoration.
4. Rerun the affected visual, behavioral, accessibility, and engineering checks.

Bind final evidence to the implementation identifier, route, browser/version, timestamp, viewport or container, input modality, and state. Mark self-review, independent perception review, expert review, and target-user testing separately.

## 8. Validate with users

Use existing research, analytics, support evidence, or user testing when available. For high-risk, transactional, or unfamiliar user journeys, do not equate an expert review with user validation.

Record:

- the task hypothesis;
- participant or audience fit;
- scenario and success condition;
- observed breakdowns;
- changes made;
- limits and tests not performed.

Do not call a critical flow fully production-validated when representative users have not evaluated the relevant task.

## 9. Deliver

Before delivery:

- review the final diff or changed-file set;
- run the supported build and test gates;
- inspect final rendered routes and states;
- complete metadata, asset, claim, placeholder, comment/meta-language, and
  console residue checks;
- confirm externally acting integrations and public claims with the owner;
- identify measurements and specialist audits not performed;
- keep internal direction and evidence files out of commits unless the project permits them.

Delivery state controls behavior:

| State | Allowed behavior |
| --- | --- |
| Concept or demo | No live endpoint, payment, booking, ordering, map, tracking, cookie, or third-party embed unless explicitly approved. Label placeholders and demo-only controls. |
| Existing integration | Preserve it unless asked to change it. Test with staging, mocks, or another non-destructive path. |
| Production | Apply the [production-readiness boundary](quality/production-readiness.md); confirm public facts, assets, disclosures, integrations, privacy behavior, specialist gates, deployment authority, and release evidence with accountable owners. |

## 10. Project-local state and fallback

Use `.design-dna/` only when durable state is useful. Initialize selected records with `scripts/init_project_state.py`; do not copy unresolved templates by hand.

Possible records:

```text
.design-dna/
  direction.md
  direction-proof.md
  visual-review.md
  claims.md
  assets.yml
  user-validation.md
  state.json
```

Use one classification vocabulary:

- `public`: approved for public distribution;
- `internal`: project-team material not approved for public distribution;
- `confidential`: access-limited business, client, or personal material;
- `restricted-research`: consent- and retention-bound participant evidence,
  treated more strictly than confidential material.

Prefer links and concise observations to copied source material. Never commit,
share, or retain confidential or restricted-research material without the
accountable data owner's approval.

If browser, screenshot, test, or network capabilities are unavailable:

1. Perform the applicable source and reasoning review.
2. Identify the exact checks that could not be performed.
3. Do not claim a rendered, measured, independent, or user review occurred.
4. Leave a focused follow-up list for an environment that can perform the missing checks.
