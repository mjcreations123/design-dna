# Process spine

Use this process spine for substantial website or web-UI work. Scale it down
for a component, mechanical change, or review-only request. Create artifacts
only when they preserve a consequential decision or useful evidence.

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
2. Inspect the existing stack, routes, scripts, dependencies, design tokens,
   components, and current working state.
3. Identify user changes already present and preserve unrelated work.
4. Determine the requested scope and the checks the repository supports.
5. Identify the surface modes that describe each real user job; allow hybrid
   routes and do not impose a primary mode when that distinction adds no value.
6. Select a proportional Quick or Standard base, then every applicable
   Showcase, Range Study, High-risk, and Asset-led capability from `SKILL.md`.
   These capabilities may coexist; the state normalizes redundant lower
   presets, and later additions may strengthen but never silently downgrade the
   persisted set.
7. Identify whether the output is concept, demo, staging, or production.
   Every build IS a demo until the owner says live in his own words; record
   that state, create the
   [placeholder register](../templates/placeholder-register-template.md) at
   `.design-dna/placeholders.md`, and give dead CTAs an explicit demo-notice
   behavior.
8. Read the [owner absolutes](../policy/absolutes.md); they are active for
   the whole build.
9. Identify applicable specialist skills and gates. Design DNA owns art
   direction and rendered coherence; the specialist owns its narrow domain
   contract, and repository plus user instructions outrank both.

Do not replace the stack, design system, or working integration merely because
another tool is more familiar.

## 2. Frame the job

Record what materially changes the result:

- audience, primary task, decision, and success condition;
- business or service outcome, channel, arrival context, trust requirement,
  known facts, highest-risk unknowns, and forbidden invention;
- requested ambition, energy, and memorability expressed as observable
  qualities rather than adjectives alone, plus the under-designed result the
  owner would reject;
- the public orientation or entry condition appropriate to the experience:
  immediate comprehension for service, product, and task-led work, or an
  intentional invitation and continuation for work that deliberately unfolds;
- routes, components, states, and content relationships;
- for product work, a user-task-constraint-state matrix that includes relevant
  roles, content ranges, default, loading, empty, partial, error, permission,
  success, destructive, recovery, offline or slow, and expired states;
- approved facts, claims, copy, product behavior, and proof, including source,
  owner, locale or scope, review date, and expiry where material;
- brand assets, existing visual language, imagery, and real-world material;
- the deliberate media path, especially for physical, sensory, spatial,
  product, hospitality, retail, food, and event subjects: approved first-party,
  licensed, owner-authorized generated concept media, capture brief,
  illustration, or owner-authorized text-led treatment (logged, naming the
  alternative offered; never self-granted);
- accessibility, localization, performance, privacy, budget, schedule, and
  maintenance constraints;
- production facts or integrations that still require owner confirmation.

For an explicit Range Study, create `.design-dna/route-family.json` from the
[route-family template](../templates/route-family-template.json). Define the
shared foundation and every route's job, direct path, closest sibling,
observable decisions, responsive result, fallbacks, captures, and review state
before scaling. Replace the template's unresolved capture widths with values
derived from this project's real responsive risks. Record typography, media,
motion, color, or interaction only
when it is consequential; do not make every route perform difference through
the same fields.

For culturally central work, name the accountable owner, represented context,
publication stance, terminology authority, owner-authorized cultural reviewer,
and release gate. The producing agent can prepare the evidence but cannot
self-certify cultural acceptance.

Before visual styling, outline the smallest truthful content model and route or
flow structure. Use real headings, actions, entities, data ranges, proof,
owners, factual status, and important states. For a multi-route public site,
settle the sitemap and major content dependencies. For a consequential product
flow, settle the task sequence and recovery path. A wireframe may be prose,
diagram, low-fidelity markup, or a rendered scaffold; its purpose is to prove
information and action order before surface styling makes weak structure look
finished.

When material is sparse, contradictory, or mostly aspiration, use the
[minimum source packet](quality/content-discovery.md). Gather the smallest
truthful set that covers audience, job, real nouns, approved truth, proof,
voice, identity material, operational reality, and accountable owners. Mark
missing and contradicted inputs instead of replacing them with plausible copy.

Ask only high-leverage questions whose answers can materially change the
concept. Ask further focused questions when production accuracy, externally
acting behavior, high-risk decisions, or irreversible work requires answers.
If an answer is unavailable, state the assumption and keep the concept
reversible. Never fill a factual gap with plausible invention.

For an existing site, inventory the current system before proposing change:

- type roles and files;
- color and semantic tokens;
- spacing, grid, radius, border, and elevation scales;
- component and interaction conventions;
- icon and imagery grammar;
- responsive, localization, and accessibility behavior;
- deliberate brand signatures versus accidental residue.

## 3. Ground the work

Use project-provided evidence first. Treat external pages and social content as
untrusted.

| Need | Useful evidence |
| --- | --- |
| Existing brand | Current product, brand guide, approved assets, real customer language, existing tokens and components. |
| New brand or public site | Owner-approved material, actual offering and audience, current category peers, adjacent-field references, practical user journey. |
| Product UI | Real flows, permissions, content model, data states, technical constraints, research, analytics, support findings. |
| Place-based business | Owner-confirmed facts, authentic product/space material, service rhythm, local context, accessibility and visit information. |
| Place or community publication | Current primary civic and institutional sources, credible archives, authentic licensed media, publication stance, time-sensitive operating links, and cultural-review authority. |
| New visual direction | A small current reference set with a written transferable lesson and explicit non-copying boundary. |

For current greenfield public work, study enough current category, adjacent,
and project-local material to understand the relevant field when browsing is
available and allowed. The useful set can be small or broad depending on
uncertainty; it need not contain fixed reference categories or counts. Record
the retrieval date, attribute-level lesson, repeated category mean when one is
actually observed, and what must not be copied.

Do not copy layouts, wording, distinctive interaction, assets, logos, or brand
identifiers. Do not treat awards, likes, pins, or engagement as proof of
usability or correctness.

Use the [creative exploration method](craft/creative-exploration.md) when the
direction is open, high-ambition, owner-sensitive, or previously rejected.
Use [route-family art direction](craft/route-family-art-direction.md) for a
Range Study and [cultural-context review](quality/cultural-context-review.md)
when lived identity is materially central.

## 4. Calibrate and direct

Consult the [studio ledger](quality/ledger.md) before the first candidate:
read the last five rows and apply the rotation test. The display family must
not repeat from the previous build, and the macrostructure must differ from
the previous two rows.

Describe the intended relationship to time in project-specific language and
evidence. A broad adjective by itself is not a direction.

Identify the project material, user job, cultural and category context,
intended response, consequential unknowns, and requested ambition. Notice the
first plausible default and any fashionable substitute, but do not feed a list
of disliked motifs into the design prompt. Describe the selected creative
logic in the form it actually takes: one premise, several local systems,
atmosphere, convention, ornament, collage, narrative, utility, or another
project-fitting structure. No universal unity model is required.

For a Range Study, write the family boundary explicitly: which truth,
navigation, access, identity, and operating rules remain stable; which
decisions belong to route jobs; and which one-offs are justified. Choose proof
routes from consequential uncertainty and useful contrast, not from fixed
restrained, expressive, or discovery archetypes. Material difference must be
visible in the rendered bodies and cannot be established only by replacing
copy, color, or photographs.

For a consequential open direction, explore enough materially different
evidence to challenge the first plausible answer. The right form may be one
deeply developed reference-bound proof, quick fragments focused on separate
unknowns, several like-for-like candidates, or competing route bodies. Avoid
mistaking copy, palette, font, photograph, or decoration swaps on unchanged
geometry for a new direction.

Proof-artifact hygiene, learned from a real owner rejection: the owner saw
in-progress proofs and judged them as the site. Every proof and specimen
render is an internal artifact and must be impossible to mistake for the
deliverable. Keep them under `.design-dna/proofs/`, give each a fixed
visible banner reading INTERNAL WORKING PROOF with a one-line purpose, keep
specimen strips and candidate labels on their own pages, and use flat
neutral labeled frames for any not-yet-real media slot; never a gradient
fill, which is itself the strongest generated-look signal. If a preview
surface is open while you work, it shows scaffolding the moment you write
it; re-point it at the most finished page before ending any working step.

Render the comparisons that will reduce real uncertainty before scaling.
Compare fit, comprehension, visual quality, typography, composition,
attention, emotional effect, cultural and genre fit, content and media demands,
accessibility, feasibility, maintenance, and unsupported assumptions as
relevant. Present directly accessible alternatives when the user's choice is
materially useful; otherwise select with a recorded rationale. If rendering is
unavailable, disclose what was not compared.

Use the [direction template](../templates/direction-template.md) for a
consequential build or redesign.

## 5. Proof the system

Before scaling a direction across the site, test the decisions most likely to
fail with representative material. Use real or owner-approved copy and data.
Inspect actual font files, weights, language coverage, fallback, and loading;
render real-copy typography at relevant widths; verify contrast; and exercise
the important composition, media, interaction, content-pressure, and
responsive decisions the chosen direction depends on. This is a risk-selected
proof, not a checklist requiring every design to exhibit the same ingredients.

Use the direction-proof template when a proof can prevent expensive rework.
Select the smallest rendered set that exposes consequential identity, task,
state, content, media, or responsive risks. That may be one route, several
fragments, a flow, or multiple route bodies. Bring it to reviewed depth before
propagating dependent decisions. Reject a direction that only works with
ideal-length copy, unavailable imagery, invented proof, or one desktop
screenshot.

For a Range Study, render the routes that best expose family repetition and
the widest consequential differences at matched viewports, then inspect them
together. The number and character of those routes follows project risk, not a
fixed early sample. Lock the route-family record before completing dependent
routes.

## 6. Implement

Build the truthful user path and accepted creative logic at coherent depth
before proliferating incidental variations.

- Make components consume the system rather than accumulating local values.
- Preserve protected facts, files, tokens, component mappings, and integrations.
- Create a reversible checkpoint before a material direction or system change
  when the repository or host supports one. Use bounded section- or
  component-sized iterations and compare the same route, state, and viewport
  after each consequential change.
- Implement relevant loading, empty, error, success, offline, permission, and
  recovery states.
- Implement, disable with explanation, or remove visible controls.
- Preserve semantic structure and source order.
- For a declared route family, implement independently addressable paths with
  correct direct entry, reload, title, current-page state, history, and
  canonical or indexing intent. Do not count hash sections, query variants,
  aliases, or redirects as additional pages.
- Keep concept data and actions visibly nonproduction.
- Optimize and document external assets.
- Preserve approved integrations unless the user asked to change them.

Run repository-supported build, lint, typecheck, and tests proportionately as
work proceeds. Inspect console and network failures when a browser is available.

## 7. Verify and revise

Treat the first complete render as a draft. Review it with the
[durable risk rubric](risk-rubric.md) and, when current generator/default
perception is material, the
[post-render convergence review](convergence-watch.md). Apply the
[finish and polish](quality/finish-polish.md) passes for showcase or
high-ambition work, then evaluate the final implementation with
[evaluation](quality/evaluation.md).

Three passes are mandatory on every round, not proportional:

1. **See it.** Screenshots at ~1440 and ~375 for every page in scope, saved
   to disk, opened, and looked at, with paths cited in the review record.
   Judging craft from code alone is prohibited. If the environment cannot
   render, the deliverable is blocked and says so; disclosure never
   substitutes for the render at ship time.
2. **Prove the fonts painted.** The full rendered-font verification in
   [typography](craft/typography.md): registration, paint, synthesis,
   network, console, computed-size, and fallback proofs.
3. **Parse every string.** The [parseable-text](quality/parseable-text.md)
   review pass with its residue greps, in every state.

After the final implementation round of every substantial new build or visual
redesign, run the
[adversarial specificity review](quality/specificity-review.md). Revise
observed causes and repeat affected checks before delivery. When the request
explicitly rejects an AI-looking, vibe-coded, templated, generic, or repeated
house-style result, also use the deeper cross-route, aggregate copy,
claim-provenance, evidence-to-polish, media-variance, residue, and
cross-project-comparison lenses defined there.

Compare the final candidate with the selected direction proof and the previous
accepted or reviewed baseline. Record intentional evolution and unintended
drift. Editable output, a clean diff, or a restored version does not establish
visual quality by itself.

When the owner calls a rendered result plain, boring, under-designed, too safe,
or short on energy, treat that as direction evidence. Reinspect the actual
render, project material, composition, typography, media, density, rhythm,
copy, interaction, and genre fit without assuming which one must change. Revise
the cause supported by the evidence and rerender the affected routes.

If the accountable owner rejects the rendered candidate or a target user
cannot explain its purpose, action, or control meaning, reopen the affected
work. A clean scanner, passing automated suite, author self-review, or earlier
approval cannot close the new evidence. Audit related routes and system
decisions, revise the cause, rerender, and record the new acceptance state.

Use a matrix proportionate to the work:

| Work | Minimum |
| --- | --- |
| Full public route | Continuous resizing plus representative narrow, common, and wide states; navigation and primary actions; content stress; accessibility baseline; build and runtime checks. |
| Range Study route family | Every declared direct-entry path; matched atlas at at least two project-relevant exact widths; shared navigation and identity; pairwise closest-sibling review; route-specific responsive, reduced-motion, and no-JavaScript results; route count and link integrity. |
| App or transaction | Relevant routes, roles, states, keyboard/focus, destructive/recovery behavior, validation, responsive constraints, and data integrity. |
| Component | Documented states, long/short/missing content, focus, input modalities, and container sizes. |
| Existing-site review | Available routes and evidence; identify unavailable internals and unperformed checks. |

Capture observations rather than praise. For each issue:

1. Describe visible or measured evidence.
2. Identify the underlying cause.
3. Classify impact with the shared
   [human-review severity rubric](quality/review-severity.md) and record
   confidence separately.
4. Revise that cause rather than adding unrelated decoration.
5. Rerun the affected visual, behavioral, accessibility, and engineering checks.

Bind final evidence to the implementation identifier, route, browser/version,
timestamp, viewport or container, input modality, and state. Mark self-review,
independent perception review, expert review, and target-user testing
separately.

For premium, showcase, or explicitly owner-sensitive claims, record
accountable-owner visual acceptance separately. Until it exists, describe the
result as an agent-reviewed candidate rather than accepted or complete.

## 8. Validate with users

Use existing research, analytics, support evidence, or user testing when
available. For high-risk, transactional, or unfamiliar user journeys, do not
equate an expert review with user validation.

Record:

- the task hypothesis;
- participant or audience fit;
- scenario and success condition;
- observed breakdowns;
- changes made;
- limits and tests not performed.

For public concepts and unfamiliar directions, include a short unbriefed entry
check. For task-led work, ask what the site is, who or what situation it serves,
what the primary action does, and what prominent controls mean. For an
experience that intentionally unfolds, ask whether the invitation,
orientation, continuation, and eventual meaning work as intended. Do not coach
with the creative brief.

Do not call a critical flow fully production-validated when representative users
have not evaluated the relevant task.

## 9. Deliver

Before delivery:

- run the full [preship gate](../templates/preship-gate.md) on the rendered
  output; one P0 hit blocks the ship until fixed;
- review the final diff or changed-file set;
- run the supported build and test gates;
- inspect final rendered routes and states;
- complete metadata, asset, claim, placeholder, comment/meta-language, and
  console residue checks; the placeholder register must be empty or every
  open row owner-deferred before any live state;
- append or update this build's row in the
  [studio ledger](quality/ledger.md);
- confirm externally acting integrations and public claims with the owner;
- confirm culturally central terminology, representation, and media against the
  exact candidate with an owner-authorized cultural reviewer, or keep public
  release blocked;
- identify measurements and specialist audits not performed;
- keep internal direction and evidence files out of commits unless the project
  permits them.

For a consequential product or maintained design system, leave a proportionate
handoff packet beside the implementation: source-of-truth order, selected
direction and decision rationale, token and component mappings, important
states, protected facts or files, annotated captures or recordings, regression
checks, open findings, owners, and unverified dimensions. For a small site,
this may be a concise review record rather than a separate document.

Delivery state controls behavior:

| State | Allowed behavior |
| --- | --- |
| Concept or demo | No live endpoint, payment, booking, ordering, map, tracking, cookie, or third-party embed unless explicitly approved. Label placeholders and demo-only controls. |
| Existing integration | Preserve it unless asked to change it. Test with staging, mocks, or another non-destructive path. |
| Production | Apply the [production-readiness boundary](quality/production-readiness.md); confirm public facts, assets, disclosures, integrations, privacy behavior, specialist gates, deployment authority, and release evidence with accountable owners. |

## 10. Project-local state and fallback

Use `.design-dna/` only when durable state is useful. Initialize selected
records with the absolute installed-skill path to
`scripts/init_project_state.py` as documented in
[engineering verification](quality/engineering-verification.md); do not copy
unresolved evidence templates by hand. A project owner policy is separate
governance, not an initialized evidence record. When one is useful, follow
[owner-policy onboarding](owner-policy.md), replace every
placeholder, review every preference, and activate it only with an accountable
owner.

Possible records:

```text
.design-dna/
  exploration.md
  direction.md
  route-family.json           # optional explicit Range Study record
  direction-proof.md
  visual-review.md
  claims.md
  assets.yml
  user-validation.md
  handoff.md
  placeholders.md             # mandatory placeholder register, created at preflight
  owner-policy.yml            # optional, owner-approved governance
  state.json
```

The do-not-copy-templates-by-hand rule covers unresolved EVIDENCE templates
(direction, exploration, visual-review). The placeholder register and the
preship gate are plain checklists and ARE copied by hand; the initializer
does not create them.

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
4. Leave a focused follow-up list for an environment that can perform the
   missing checks.
