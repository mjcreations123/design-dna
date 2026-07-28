---
name: design-dna
description: Build, redesign, polish, or visually review websites and web UIs that must feel specific, contemporary, non-generic, and production-quality. Use for landing pages, hospitality, ecommerce, portfolios, editorial sites, dashboards, product interfaces, documentation, components, or requests to avoid AI-looking, vibe-coded, templated, cookie-cutter, or dated design. Apply when art direction, design-system reasoning, content hierarchy, responsive behavior, or rendered visual quality materially matters; pair with specialist skills for deep security, SEO, legal, backend, deployment, or compliance work.
---

# Design DNA

Create web work whose content, hierarchy, system, and behavior are visibly
chosen for this project and audience. Optimize for specificity, clarity,
credibility, usability, contemporary fit, and finish. Never promise that AI
involvement is undetectable or claim human-only authorship.

## Runtime map

- [Authority](#resolve-authority)
- [Scope and mode](#classify-the-work)
- [Hard invariants](#keep-these-invariants)
- [Workflow](#follow-one-workflow)
- [Decision router](#load-guidance-only-for-the-decision-now)
- [Readiness boundary](#bound-readiness-claims)
- [Records and fallback](#record-only-useful-evidence)

## Resolve authority

Use this order:

1. Safety, law, privacy, accessibility, factual integrity, and repository instructions.
2. Explicit user, accountable owner, approved client, product, and brand requirements.
3. The task, surface mode, content, stack, and delivery constraints.
4. Project evidence and documented rationale.
5. This installation's [owner defaults](policy/owner-defaults.yml) and heuristics.

When same-tier sources conflict, do not choose by convenience or recency.
Preserve an established approved requirement, identify the accountable decision
owner, and ask only when the unresolved choice would materially change the
result. Owner defaults are preferences, not project approval or authorship
detectors.

## Classify the work

| Scope | Required process |
| --- | --- |
| New build, visual redesign, or route family | Preflight, direct, proof, implement, and complete rendered plus engineering review. |
| Component or meaningful visual change | Inherit the system, define the component's job and states, and test changed behavior and containers. |
| Visual or UX review | Inspect available rendered and source evidence; report observed causes and unperformed checks. |
| Mechanical or purely functional change | Preserve the visual system and verify proportionately. |

Choose one primary mode by the user's job:

- Decide or convert: [Persuade](references/modes/persuade.md).
- Explore or experience a sequence: [Experience](references/modes/experience.md).
- Complete a workflow: [Operate](references/modes/operate.md).
- Comprehend or reference: [Read](references/modes/read.md).

Use secondary modes only where a route or component's job changes.

## Keep these invariants

- Preserve repository instructions, unrelated work, established systems, and working integrations unless the task authorizes change.
- Do not invent business facts, proof, people, metrics, reviews, assets, availability, product evidence, or integrations. Make concept and placeholder status explicit.
- Do not activate publishing, payments, ordering, booking, form delivery, tracking, accounts, maps, or other external behavior without authority and real configuration.
- Use familiar patterns when they serve the task. Specificity must come from project evidence and coherent craft, not random novelty or a replacement house style.
- When the request explicitly rejects an AI-looking, vibe-coded, templated, generic, or repeated house-style result, complete an adversarial specificity review against the final implementation; a scanner or first render is not closure.
- Keep prominent display copy in one coherent type and foreground treatment unless a complete semantic phrase or an approved brand, link, status, data, quotation, or editorial rule supplies meaning. See the canonical exceptions in [owner defaults](policy/owner-defaults.yml).
- Preserve semantic structure, keyboard and touch access, visible focus, contrast, responsive reflow, reduced motion, content variation, and resilient fallbacks.
- Implement visible controls and relevant states, or remove, disable with explanation, or clearly defer them.
- Never claim a browser, screenshot, user, accessibility, performance, security, host, build, or release check occurred when it did not.

## Follow one workflow

For a substantial build or redesign, read [the workflow](references/workflow.md)
and use it as the sole detailed process:

1. Inspect the project and frame the real audience, task, facts, assets, constraints, and delivery state.
2. Ground a project-specific direction in supplied material and a small dated reference set when research is useful and allowed.
3. Proof consequential type, color, composition, content, media, interaction, and narrow-screen decisions before scaling.
4. Implement the real path and states within the existing technical contract.
5. Render, inspect, revise causes, rerun affected checks, and disclose remaining limits.

Ask up to two high-leverage concept questions when the answers would materially
change direction. Ask additional focused questions only for factual, risky,
externally acting, or irreversible choices.

## Load guidance only for the decision now

Do not preload the library.

| Decision or risk now | Load |
| --- | --- |
| New direction, redesign, “generic,” “dated,” or “make it impressive” | [Art direction](references/craft/art-direction.md); add [durable risks](references/risk-rubric.md). |
| Explicit “AI-looking,” vibe-coded, templated, generic, or house-style concern | Diagnose with the dated [convergence watch](references/convergence-watch.md), then close the final candidate with the [adversarial specificity review](references/quality/specificity-review.md); neither is authorship detection. |
| Type selection, font loading, or display emphasis | [Typography](references/craft/typography.md); for greenfield public identity also load the dated [type watch](policy/type-convergence-watch.yml). |
| Palette, depth, or visual composition | [Color and composition](references/craft/color-composition.md). |
| Grid, grouping, rhythm, or density | [Layout and density](references/craft/layout-density.md). |
| Routes, navigation, headings, actions, copy, or content states | [Content and IA](references/craft/content-ia.md). |
| Photography, generated media, illustration, or external assets | [Imagery](references/craft/imagery-illustration.md) and [asset integrity](references/quality/asset-integrity.md). |
| Icons or pictograms | [Iconography](references/craft/iconography.md). |
| Motion, scrolling, transitions, or direct interaction | [Motion and interaction](references/craft/motion-interaction.md). |
| Multi-device or public surface | [Responsive adaptation](references/craft/responsive-adaptation.md). |
| Components, tokens, themes, or UI libraries | [Systems and components](references/craft/systems-components.md). |
| Chart, map, metric, or quantitative comparison | [Data visualization](references/craft/data-visualization.md). |
| Public or interactive implementation | [Accessibility baseline](references/quality/accessibility-baseline.md). |
| Material runtime cost, media, fonts, or third parties | [Performance](references/quality/performance.md). |
| Multiple locales, translated content, or RTL | [Localization](references/quality/localization.md). |
| Research, analytics, or target-user evidence | [Research and validation](references/quality/research-user-validation.md). |
| Software or SaaS marketing/product continuity | [Software products](references/verticals/software-product.md). |
| Place- or service-based business | [Local business](references/verticals/local-business.md). |
| Catalog, cart, checkout, or fulfillment | [Ecommerce](references/verticals/ecommerce.md). |
| Premium/showcase finish or final visual refinement | [Finish and polish](references/quality/finish-polish.md). |
| Scoped completion | [Engineering verification](references/quality/engineering-verification.md) and [evaluation](references/quality/evaluation.md). |
| Production, launch, deployment, or broad readiness claim | [Production readiness](references/quality/production-readiness.md) and every applicable specialist gate. |

Load [Claude](references/platform-claude.md) or
[Codex](references/platform-codex.md) behavior only when host capability,
fallback, or installation is uncertain.

## Bound readiness claims

“Production-quality design and implementation” describes only the dimensions
actually verified. It is not a security, privacy, legal, SEO, deployment,
operational, or regulatory approval. Authentication, personal data, payments,
uploads, user-generated content, regulated claims, public indexing, external
integrations, and production operations require their applicable specialist
review or an explicit `unverified` disclosure and release block.

## Record only useful evidence

Use `scripts/init_project_state.py` to create only needed project-local records:

| Record | Trigger | Template or selector | Default handling |
| --- | --- | --- | --- |
| `.design-dna/direction.md` | Consequential direction | [direction template](templates/direction-template.md), `direction` | Internal; commit only with owner/project approval. |
| `.design-dna/direction-proof.md` | Proof prevents expensive rework | [proof template](templates/direction-proof-template.md), `direction-proof` | Internal; retain the winning decision and useful rejection lesson. |
| `.design-dna/visual-review.md` | Rendered, implementation, or explicit specificity-closure review | [review template](templates/visual-review-template.md), `visual-review` | Internal; bind observations to the tested build and name the review lens. |
| `.design-dna/claims.md` | Public copy, calculations, or interactions contain exact or authority-shaped claims | [claim ledger](templates/claim-ledger-template.md), `claims` | Internal; approve, qualify, visibly label as scenario, replace, defer, or omit every entry. |
| `.design-dna/assets.yml` | Nontrivial external or generated assets | [asset manifest](templates/asset-manifest.yml), `assets` | Internal; block public use while rights, privacy, truth, or approval is pending. |
| `.design-dna/user-validation.md` | Actual target-user evidence | [validation template](templates/user-validation-template.md), `user-validation` | Restricted research; do not commit or share without explicit data-owner approval. |
| `.design-dna/scan-allowlist.json` | A scanner exception is justified | [allowlist placeholder](templates/scan-allowlist.json) | Emit the entry from an actual current finding; owner-labelled, fingerprint-bound, narrow, and short-lived. |

If Python 3.10+ is unavailable, do not install or improvise a runtime. Create
necessary records and checks manually and report which helper validation or
scan was not run. `scripts/scan_project.py` supplies source-level review prompts,
not authorship evidence or a substitute for rendered inspection.

The scanner enforces high-severity gate findings by default. For application
source, run:

```text
python scripts/scan_project.py PROJECT --json
```

For a content-oriented site whose reviewed scope includes documentation and
structured content, opt those sources in explicitly:

```text
python scripts/scan_project.py PROJECT --content-site --structured-content --json
```

JSON, YAML, and YML are never content-scanned by default. `--structured-content`
adds them, while sensitive authentication, configuration, credential, key,
password, private, secret, and token paths remain excluded unless a reviewed
`--include` selects them. Dependency and vendor trees remain excluded.

Treat `execution_ok`, `source_gate_passed`, `quality_status`, `scan_scope`,
`review_required`, `design_review_status`, and `exit_policy` as separate facts.
`not-triggered-by-source` means only that this bounded scan raised no design
prompt; it never waives rendered or explicit specificity review.
`--advisory-exit-zero` is an explicit exit-code opt-out; it does not turn a
failed quality policy into a pass.

Create an exception only from an actual current, overridable finding:

```text
python scripts/scan_project.py PROJECT --json
python scripts/scan_project.py PROJECT --emit-allowlist-entry FINGERPRINT --allowlist-entry-owner "OWNER" --allowlist-entry-reason "REVIEWED REASON"
```

Review and merge the emitted document into the project allowlist. The owner
policy annotates findings but cannot suppress them. Literal unfinished
`placeholder-proof` findings remain high-severity release gates by default. A
legitimate visible specimen, quotation, or teaching example may be excepted
only through the normal owner-reviewed, exact-path, exact-line,
fingerprint-bound, expiring allowlist process; never infer that exception from
the literal alone. `--print-allowlist-example` and the packaged allowlist file
are non-usable placeholders, not entries to copy into a project. Finding
fingerprints bind the reported signal payload, so changed evidence requires a
fresh review and exception. Expiry values use the exact `YYYY-MM-DD` string
form and may be no more than 90 days in the future.

The high-severity unfinished-filler gate applies to literal visible text nodes
in HTML, JSX/TSX, Liquid, Twig, Vue, Svelte, Astro, and MDX. Source-code
strings and unresolved dynamic template expressions remain advisory; explicit
negative examples are ignored. Proof-shaped marketing language that might be
valid is a provenance advisory, not a declaration that the claim is false.

Private cross-project pattern history may be used only with owner authorization,
outside the installed skill, and without confidential client details. Repetition
is an investigation prompt; continuity within one brand or product family is
often correct. Read [evidence policy](references/evidence.md) only when changing
a risk rule or evaluating a new “AI-looking” claim.
