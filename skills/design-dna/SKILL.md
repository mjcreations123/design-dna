---
name: design-dna
description: Builds, redesigns, polishes, and visually reviews websites and web UIs that must feel specific, time-appropriate, non-generic, and production-quality. Use for landing pages, multi-page range studies, place and community publications, hospitality, ecommerce, portfolios, editorial sites, dashboards, product interfaces, documentation, components, requests to avoid AI-looking, vibe-coded, templated, cookie-cutter, accidentally dated, or time-incongruent design, feedback that a result feels plain, boring, under-designed, too safe, or lacks visual energy, and complaints that fonts look bad, ugly, or unstyled, or that pages carry random decorative text, labels, or symbols that make no sense. Apply when art direction, design-system reasoning, content hierarchy, culturally central representation, responsive behavior, rendered visual quality, or typography materially matters; pair with specialist skills for deep security, SEO, legal, backend, deployment, or compliance work.
---

# Design DNA

## Contents

[boundaries](#assurance-boundaries-come-first) ·
[quality axes](#separate-specificity-from-ambition) ·
[authority](#resolve-authority) · [classify](#classify-the-work) ·
[creative freedom](#preserve-creative-freedom) ·
[invariants](#keep-these-invariants) ·
[process spine](#follow-the-process-spine) ·
[router](#load-guidance-only-for-the-decision-now) ·
[specialists](#coordinate-specialists) ·
[evidence](#bound-readiness-and-evidence) · [the gate](#the-gate-restated)

Create web work whose content, hierarchy, system, and behavior are visibly
chosen for this project and audience. Optimize for specificity, clarity,
credibility, usability, time-register fit, visual quality, and finish.
Reduce generic, repetitive, unsupported, careless, and artifact-heavy
signals through project evidence and rendered review. Never promise
undetectable AI involvement, score aesthetic authorship, claim human-only
creation, or treat one ingredient as proof of how a site was made.

## Assurance boundaries come first

Read [the assurance boundaries](policy/absolutes.md) before substantial
design work. They reserve low freedom for truth, rights, privacy, access,
working behavior, evidence honesty, delivery authority, and explicit project
contracts. They do not contain a font, palette, punctuation, layout, motion,
media, ornament, component, or style blacklist.

Before enforcing any aesthetic constraint, trace it to an explicit owner,
brand, cultural, repository, or project source. If it comes only from a past
build, trend discussion, scanner, or producer preference, keep it as a
post-render hypothesis. Do not invent a standing owner law from remembered
criticism.

An installation may carry such a source. Look for an owner-standards record
at `~/.claude/design-dna/owner-standards.md`, or the host-neutral
`~/.design-dna/owner-standards.md`, and read it before the direction exists.
It is the accountable owner's own dated record, so the constraints in it are
traced and enforceable pre-render for that owner's work, unlike a trend list.
It closes only the ingredients it names, for that owner only; everything else
stays open. If no such file exists, proceed without one and do not
reconstruct its contents from memory.

## Separate specificity from ambition

One quality axis asks whether the work is project-specific rather than a
reusable first draft. Another asks whether the chosen ambition is fully
realized. A quiet information page can be more resolved than a cinematic
showcase; a maximal composition can be more coherent than a minimal one.
Neither richness nor restraint is the default.

Set energy, density, media, scale, motion, and surprise from the brief,
audience, content, genre, owner preference, and production reality. Avoiding
generic signals by stripping everything away is not a solution, and adding
effects to a weak direction is not a solution. When feedback says "boring,"
"too plain," or "not enough pizzazz," inspect the rendered organizing cause
and raise the relevant ambition. When it says "noisy" or "confusing," edit
the relevant hierarchy and relationships. Do not map either response to a
universal style recipe.

For an open or consequential direction, externalize enough contrast to
challenge the first plausible answer. The useful evidence may be a second
composition, a focused fragment, a reference decomposition, a content model,
or a full rendered alternative. Its form and count follow uncertainty and
stakes; no fixed concept quota applies.

## Resolve authority

1. Safety, law, privacy, accessibility, factual integrity, repository
   instructions.
2. Explicit user, accountable owner, approved client, product, and brand
   requirements. A project-local policy may add exact constraints when its
   owner, source, date, scope, and exception path are recorded.
3. The task, surface mode, content, stack, and delivery constraints.
4. Project evidence and documented rationale.
5. Bundled [publisher defaults](policy/owner-defaults.yml), then heuristics.

When same-tier sources conflict, preserve an established approved
requirement, identify the accountable decision owner, and ask only when the
unresolved choice would materially change the result.

## Classify the work

| Scope | Required process |
| --- | --- |
| New build, visual redesign, or route family | Preflight, direct, proof, implement, complete rendered plus engineering review. |
| Component or meaningful visual change | Inherit the system, define the component's job and states, test changed behavior. |
| Visual or UX review | Inspect rendered and source evidence; report observed causes and unperformed checks. |
| Mechanical or purely functional change | Preserve the visual system, verify proportionately. |

Capability presets are cumulative; adding one cannot remove another:

| Preset | Use when | Minimum |
| --- | --- | --- |
| Quick | Bounded repair in an established system, low risk. | Inspect context, preserve the system, implement changed states, run affected checks plus the preship gate on the touched surface. |
| Standard | New route, meaningful feature, ordinary redesign. | Frame, direct, prove consequential decisions, implement, full rendered plus engineering review, full preship gate. |
| Showcase | Expressive, premium, highly visible, or explicitly rejecting safe output. | Research and externalize directly reviewable contrast sufficient to challenge the first default; build full alternatives when uncertainty, stakes, or owner choice justify them; deepen risk-selected proof, polish, adversarial review, owner acceptance kept separate. |
| Range Study | A multi-route brief explicitly requiring meaningful creative range. | Shared foundations stay dependable; route-family record before scaling; proof routes chosen by uncertainty; matched route atlas review. |
| Batch Study | A controlled evaluation of at least three unrelated website briefs. | Freeze independent briefs and source packets; record human-auditable implementation isolation; resolve capture and contact-sheet data handling for built cases; bind each capture to its rendered route, profile, exact public-build manifest, and capture mode; freeze capture-set-bound site observations before sibling output or diagnostics; record the neutral-label whole-system first observation only after those reviews are frozen; keep planned and correctly blocked cases separate. |
| High-risk | Consequential transactions, identity, money, regulated claims. | Task, state, and specialist evidence first; visual ambition cannot waive a safety gate. |
| Asset-led | Material imagery, fonts, media needing a durable record. | Per-asset provenance, rights, privacy, factual status, delivery, accessibility. |

A prior result rejected as AI-looking, generic, or ugly selects at least
Standard plus the convergence and specificity reviews; add Showcase when the
owner also asks for impressive, premium, or really good.

Identify every surface mode that describes the user's job: Persuade
([modes/persuade](references/modes/persuade.md)), Experience
([modes/experience](references/modes/experience.md)), Operate
([modes/operate](references/modes/operate.md)), Read
([modes/read](references/modes/read.md)). A hybrid route uses the guidance
that answers its actual decisions. Name one primary job per route and any
secondary jobs that materially change content, state, or review. When mode
guidance pulls in different directions, the assurance boundaries and explicit
project contract win first; then the primary job governs composition while a
secondary mode adds only its applicable requirements.

## Preserve creative freedom

Keep low-freedom rules for truth, rights, privacy, safety, accessibility,
working behavior, repository constraints, and explicit owner and brand
requirements. Keep aesthetic decisions high-freedom: there is no global font, palette, style,
geometry, ornament, layout, interaction, motion, section-order, or
concept-count whitelist or blacklist. Common choices are not automatically
generic; uncommon choices are not automatically good. A fitting direction
may be singular, plural, restrained, maximal, decorative, conventional,
historically referential, or deliberately dissonant. Read
[creative freedom](references/creative-freedom.md) before imposing an
aesthetic rule that did not come from the project or its assurance boundaries.

## Keep these invariants

- Preserve repository instructions, unrelated work, established systems,
  and working integrations unless the task authorizes change.
- Do not invent business facts, proof, people, metrics, reviews, assets,
  availability, or integrations. When unresolved material or behavior remains,
  label it where confusion could occur and track it in the
  [placeholder register](templates/placeholder-register-template.md).
- Respect the declared delivery state. When the accountable owner or active
  project policy says the work is a demo, do not connect real form endpoints,
  payments, bookings, tracking, or production deployment until that owner
  authorizes live operation. A demo control works locally, explains its state,
  or is removed; it does not silently impersonate a live integration.
- Treat typography as a designed system. Use the
  [typography](references/craft/typography.md) protocol to choose, deliver,
  and verify the roles the project actually needs. No family category,
  pairing count, hosting method, or shortlist size is globally required.
- Make a deliberate media decision for every build. When physical or sensory
  recognition matters, test whether the selected photography, illustration,
  generated concept media, data, objects, or type-led treatment actually
  conveys it. Missing supplied photography is an input gap to resolve, not an
  automatic instruction either to omit imagery or to manufacture a photo.
- Every visible string passes the
  [parseable-text](references/quality/parseable-text.md) gate. Keep
  customer-facing copy relevant to the customer's subject or task. Do not
  expose design rationale, implementation residue, component names, or false
  system theater as visitor content. Truthful operational status, technical
  detail, or atmosphere remains valid when the audience needs it and its
  meaning is clear.
- Size and prominence follow the intended encounter. The dominant element
  should support the visitor's first question, task, invitation, or deliberate
  point of tension; no universal type-size ordering applies.
- Verify by seeing: code inspection cannot establish rendered craft. Save and
  inspect project-relevant rendered evidence across the widths, states, and
  preferences that can change the conclusion—normally including wide and
  compact conditions for a substantial public surface. If the requested
  visual conclusion cannot be rendered, identify that exact blocked claim.
- Working artifacts are never mistakable for the accepted site. Separate
  internal proofs according to the repository and host contract; a
  project-local `.design-dna/proofs/` directory is one portable option, not a
  mandatory location. Mark purpose wherever a reasonable viewer could confuse
  a proof with final work, using wording and presentation suited to that host.
  A placeholder media area is visibly labeled and cannot impersonate final
  documentary or product imagery. If the agent controls a watched preview,
  leave it on the most finished relevant state before yielding; otherwise do
  not claim the preview was changed. Present saved screenshots only when they
  were actually captured and remain useful evidence.
- When several unrelated studio builds are in scope and owner-authorized
  minimized history exists, consult the
  [ledger](references/quality/ledger.md). Repetition is a review prompt, not
  an automatic veto; project and brand fit outrank novelty for its own sake.
- Preserve semantic structure, keyboard and touch access, visible focus,
  contrast, responsive reflow, reduced motion, and resilient fallbacks.
- Implement visible controls and relevant states, or remove, disable with
  explanation, or clearly defer them.
- Treat route count as information architecture, not a design quota. Every
  page needs a distinct direct-entry question, content dependency, or task;
  do not pad a multi-page request with aliases or split one encounter
  arbitrarily. On a one-page site, omit sections that do not advance its real
  encounter rather than stacking a generic long-form skeleton.
- Never claim a browser, screenshot, user, accessibility, performance, or
  release check occurred when it did not.
- When a community, religion, language, or lived identity is materially
  central, record its authority and review boundary; the producing agent
  cannot self-certify cultural acceptance.
- Direct owner rejection or observed user confusion reopens the affected
  work until the revised result is rendered and reviewed again.

## Follow the process spine

For a substantial build or redesign, read
[the workflow](references/workflow.md) and use it as the spine:

1. Inspect the project; frame audience, task, facts, assets, constraints, and
   delivery state. Create a placeholder register only when unresolved material
   or behavior exists.
2. Gather truthful source material; define public orientation; establish
   content and route structure; choose the media path. For culturally
   central subjects, name the review authority before visual commitment.
3. When authorized cross-project evidence exists, consult the ledger without
   turning repetition into a ban. For an open or high-stakes direction, build
   a retrieval-dated reference dossier and externalize enough materially
   different evidence to expose the real choice. Record perception before
   diagnosis and select with rationale.
4. For Standard or stronger new work and redesigns, record a free-form,
   project-derived organizing logic and at least one consequential decision a
   reviewer can observe; a bounded Quick repair may inherit the established
   logic. Then proof consequential decisions with real material at real conditions.
   Select the smallest evidence that can settle the chosen direction's actual
   typography, color, composition, media, interaction, content, or responsive
   risks; no fixed ingredient set applies.
5. Extract only the reusable rules the project needs; keep justified
   one-offs. For a Range Study, separate shared foundations from route
   bodies. For a Batch Study, freeze each brief and source packet; record the
   actual producer context, sibling-output exposure, allowed shared tooling,
   shared exceptions, and study-level data handling; keep research,
   implementation, and review exposure isolated between sites. Treat that
   record as inspectable human evidence, not automatic proof. Do not
   manufacture difference or transfer an aesthetic system merely to improve
   the comparison.
6. Implement the real path and states within the existing technical
   contract.
7. Render, inspect, revise causes, rerun affected checks. For every
   substantial new build or visual redesign, run the
   [adversarial specificity review](references/quality/specificity-review.md)
   against the final implementation. Run the full
   [preship gate](templates/preship-gate.md). Update an authorized ledger only
   when its owner-approved milestone applies.
   When Batch Study is active, finish each site's own gate and unprimed
   observation before diagnostics, then record the neutral-label whole-system
   first observation before revealing diagnostic material or the site-identity
   map, and run the batch-range audit. Coverage readiness is not aesthetic
   acceptance or proof that the human protocol was followed honestly.
   Obtain owner acceptance where required; disclose remaining limits.

Ask only high-leverage concept questions whose answers would materially
change direction; otherwise decide and note it.

## Load guidance only for the decision now

Do not preload the library. Load the smallest set that answers the current
decision, then return to the router.

Load in phases, because when guidance arrives changes what it does. Read the
direction references before the first candidate exists, and load the
diagnostic or finish references only after a render exists to diagnose. A
post-render vocabulary consulted while choosing turns into an inverse
prompt: the work starts being assembled to dodge a list instead of to answer
the brief, which is the mechanism that produces something safe, generic, and
already covered by [the two axes](#separate-specificity-from-ambition).

| Decision or risk now | Load |
| --- | --- |
| Any build or revision nearing done | [Preship gate](templates/preship-gate.md); it is mandatory, not optional. |
| Type selection, font loading, display emphasis, "fonts look bad" | [Typography](references/craft/typography.md), including project-derived selection, spacing, delivery, and the applicable rendered-font verification branch. |
| Decorative labels, HUD text, eyebrows, "random text," copy texture, a status/connection/live indicator, implementation or system detail on the page | [Parseable text](references/quality/parseable-text.md). |
| Fiction/demo/unavailable/generated-media status that repeats, competes with the subject, or dominates direct entry | [Microcopy](references/craft/microcopy.md) for distinct consequences and proportional hierarchy, with [Content discovery](references/quality/content-discovery.md) for the underlying truth boundary. |
| Authorized studio-history comparison; avoiding self-repetition | [Ledger](references/quality/ledger.md). Do not search or invent history when comparison is not authorized. |
| Controlled comparison of three or more unrelated sites | [Batch Study evaluation](references/quality/batch-range-evaluation.md); activate Batch Study before building the cases, freeze an [unprimed site observation](templates/batch-site-observation-template.md) for each, then complete the [neutral-label whole-system review](templates/batch-whole-system-review-template.md). |
| Missing, sparse, or contradictory project material; fictional, sample, demo, or prototype identity or scenario content | [Content discovery](references/quality/content-discovery.md), including the identity-to-fixture fit check even when the material appears plentiful. |
| New direction, redesign, "generic," or "dated" | [Art direction](references/craft/art-direction.md); optionally [decision case studies](references/decision-case-studies.md). |
| Open brief, greenfield direction, materially different options | [Creative exploration](references/craft/creative-exploration.md), then [art direction](references/craft/art-direction.md). |
| "Make it impressive," premium, showcase, "too plain," "boring" | [Creative freedom](references/creative-freedom.md), [creative exploration](references/craft/creative-exploration.md), [expression and energy](references/craft/expression-energy.md); revision verbs via [design tuning passes](references/craft/design-tuning-passes.md); [finish and polish](references/quality/finish-polish.md) after direction works. |
| First complete render or observed durable defect | Unprimed observation ([specificity review, "Observe before diagnosing"](references/quality/specificity-review.md)), then the [risk rubric](references/risk-rubric.md). |
| Explicit AI-looking, vibe-coded, templated, house-style concern | Direction from project evidence first; after a render, the [convergence review](references/convergence-watch.md); close with the [specificity review](references/quality/specificity-review.md). |
| Palette, depth, composition | [Color and composition](references/craft/color-composition.md). |
| Dark mode, a second colour scheme, a theme toggle | [Dual themes and dark mode](references/craft/theming-dark-mode.md): derive rather than invert, and both schemes are separate deliverables. |
| Grid, grouping, rhythm, density | [Layout and density](references/craft/layout-density.md). |
| Routes, navigation, headings, actions, content states | [Content and IA](references/craft/content-ia.md). |
| Buttons, errors, empty states, confirmations, labels, any small functional string | [Microcopy](references/craft/microcopy.md). |
| Multi-route anthology or capability showcase | [Route-family art direction](references/craft/route-family-art-direction.md); activate Range Study. |
| Photography, generated media, illustration, external assets | [Imagery](references/craft/imagery-illustration.md) and [asset integrity](references/quality/asset-integrity.md). |
| Icons or pictograms | [Iconography](references/craft/iconography.md). |
| Motion, scrolling, transitions, direct interaction | [Motion and interaction](references/craft/motion-interaction.md). |
| Multi-device or public surface | [Responsive adaptation](references/craft/responsive-adaptation.md). |
| Components, tokens, themes, libraries, handoff | [Systems and components](references/craft/systems-components.md); [handoff record](templates/handoff-template.md) when maintained. |
| Brand identity, campaign, recognition across surfaces | [Brand systems](references/craft/brand-systems.md). |
| Proof drifting during implementation | [Proof-to-build fidelity](references/quality/proof-to-build-fidelity.md) and its [delta ledger](templates/proof-build-delta-template.md). |
| Figma, Storybook, token pipelines, motion tooling | [Tooling adapters](references/quality/tooling-adapters.md); [design-context capsule](templates/design-context-capsule-template.md) for compiled evidence. |
| Chart, map, metric, comparison, topology, process drawing, or other content-bearing explanatory diagram | [Data visualization](references/craft/data-visualization.md) with [responsive adaptation](references/craft/responsive-adaptation.md) when conditions change. |
| Address, venue, directions, wayfinding | [Location and wayfinding](references/craft/location-wayfinding.md). |
| Signup, auth, onboarding, account | [Identity and onboarding](references/flows/identity-account-onboarding.md). |
| Plans, invoices, renewals, cancellations | [Subscription and billing](references/flows/subscription-billing.md). |
| Inbox, chat, notifications | [Messaging and notifications](references/flows/messaging-notifications.md). |
| Chat, assistant, copilot, generated-answer or streaming surface | [Conversational interfaces](references/flows/conversational-interfaces.md): the streaming contract, honest rendering of model output, provenance, and contextual failure modes. |
| Receipt, reset, confirmation, digest, campaign: the deliverable is an email | [Email as a medium](references/craft/email-design.md). |
| Multi-step forms, consequential transactions | [Complex forms](references/flows/forms-complex-transactions.md). |
| Cross-channel journeys, service handoffs | [Service journeys](references/flows/service-journey-handoffs.md); [service blueprint](templates/service-blueprint-template.md) when complex. |
| Support, complaints, disputes, appeals | [Support flows](references/flows/support-complaints-appeals.md). |
| Consent, permissions, personal data | [Privacy and consent](references/flows/privacy-consent-permissions.md). |
| Software or SaaS continuity | [Software products](references/verticals/software-product.md). |
| Place- or service-based business | [Local business](references/verticals/local-business.md). |
| Community or civic publication | [Place and community publications](references/verticals/place-community-publication.md); add [cultural-context review](references/quality/cultural-context-review.md) when identity is central. |
| Catalog, cart, checkout | [Ecommerce](references/verticals/ecommerce.md). |
| Publication or information product | [Editorial publishing](references/verticals/editorial-publishing.md) and [editorial art direction](references/craft/editorial-art-direction.md). |
| Portfolio or case studies | [Portfolio](references/verticals/portfolio-case-studies.md). |
| Marketplace or community | [Marketplace and community](references/verticals/marketplace-community.md). |
| Travel, ticketing, reservations | [Travel and reservations](references/verticals/travel-reservations.md). |
| Nonprofit, campaign, donations | [Nonprofit and fundraising](references/verticals/nonprofit-fundraising.md). |
| Courses, schools, credentials | [Education](references/verticals/education.md). |
| Public or interactive implementation | [Accessibility baseline](references/quality/accessibility-baseline.md). |
| Runtime cost, media weight, third parties | [Performance](references/quality/performance.md). |
| Locales, translation, RTL | [Localization](references/quality/localization.md). |
| Research, analytics, user evidence | [Research and validation](references/quality/research-user-validation.md); [design-partner cadence](references/quality/design-partner-cadence.md) for durable products. |
| Critique, heuristic or perception review | [Critique and expert review](references/quality/critique-and-expert-review.md); [expressive perception template](templates/expressive-perception-template.md). |
| Private previews, screenshots, evaluation data | [Review data handling](references/quality/data-handling.md). |
| Promoting, corroborating, or retiring a risk rule | [Evidence policy](references/evidence.md): source types, the corroboration bar, review intervals, and what never proves generated authorship. |
| Classifying a review finding | [Review severity](references/quality/review-severity.md). |
| Baseline-versus-candidate screenshot evidence | [Rendered comparison](references/quality/render-comparison.md). |
| Capturing or probing a page for the gate | [Render harness](references/quality/render-harness.md): the shipped Playwright capture boundary, project-declared scenarios, capture limitations, and separate manual or specialist measurements. |
| Scoped completion | [Engineering verification](references/quality/engineering-verification.md) and [evaluation](references/quality/evaluation.md). |
| Production, launch, deployment claims | [Production readiness](references/quality/production-readiness.md) and every applicable specialist gate. |

Load [Claude behavior](references/platform-claude.md) or
[Codex behavior](references/platform-codex.md) only when host capability or
installation is uncertain.

## Coordinate specialists

Design DNA owns project-specific art direction, content hierarchy, visual
coherence, responsive composition, and rendered finish. A specialist skill
owns its narrower domain. Combine conclusions at the boundary: a specialist
never introduces an unrelated visual system, and visual polish never waives
a specialist gate. Satisfy the stricter safety, truth, access, and
operational requirement, then preserve the chosen direction within it.

## Bound readiness and evidence

"Production-quality design and implementation" describes only verified
dimensions. Authentication, personal data, payments, uploads, regulated
claims, public indexing, and production operations require the applicable
specialist review or an explicit `unverified` release block.

Create only useful evidence records with `scripts/init_project_state.py`.
Templates: [exploration](templates/exploration-template.md),
[direction](templates/direction-template.md),
[route family](templates/route-family-template.json),
[batch study](templates/batch-range-template.json),
[batch site observation](templates/batch-site-observation-template.md),
[batch whole-system review](templates/batch-whole-system-review-template.md),
[direction proof](templates/direction-proof-template.md),
[visual review](templates/visual-review-template.md),
[expressive perception](templates/expressive-perception-template.md),
[proof-to-build delta](templates/proof-build-delta-template.md),
[design-context capsule](templates/design-context-capsule-template.md),
[motion asset contract](templates/motion-asset-contract-template.md),
[state matrix](templates/state-matrix.example.yml),
[service blueprint](templates/service-blueprint-template.md),
[claims](templates/claim-ledger-template.md),
[assets](templates/asset-manifest.yml) and
[complete example](templates/asset-manifest.example.yml),
[user validation](templates/user-validation-template.md),
[handoff](templates/handoff-template.md),
[scan allowlist](templates/scan-allowlist.json),
[placeholder register](templates/placeholder-register-template.md),
[studio ledger](templates/ledger-template.md), and the
[preship gate](templates/preship-gate.md). The
[owner-policy example](templates/owner-policy.example.yml) is opt-in
governance; follow [owner-policy onboarding](references/owner-policy.md).
Keep mutable records project-local with their stated privacy
classification; run the initializer's `--check-ready` gate before claiming
records satisfy the selected capabilities.

If Python 3.10+ or another capability is unavailable, perform the safe
manual equivalent, name the checks not run, and do not broaden the result.
The scanner supplies bounded source-review prompts; the rendered proofs in
the preship gate are never replaced by it.

## The gate, restated

Nothing is presented as done until the applicable
[preship gate](templates/preship-gate.md) passes on the rendered output. Bind
the exact build and risk-selected route, width, state, preference, typography,
content, media, access, and engineering evidence. A violated assurance
boundary blocks the corresponding completion or release claim. Missing
optional evidence is disclosed in scope; it does not become a fabricated
pass, a taste rule, or a reason to invent records.
