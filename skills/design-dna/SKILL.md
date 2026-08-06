---
name: design-dna
description: Builds, redesigns, polishes, and visually reviews websites and web UIs that must feel specific, time-appropriate, non-generic, and production-quality. Use for landing pages, multi-page range studies, place and community publications, hospitality, ecommerce, portfolios, editorial sites, dashboards, product interfaces, documentation, components, requests to avoid AI-looking, vibe-coded, templated, cookie-cutter, accidentally dated, or time-incongruent design, feedback that a result feels plain, boring, under-designed, too safe, or lacks visual energy, and complaints that fonts look bad, ugly, or unstyled, or that pages carry random decorative text, labels, or symbols that make no sense. Apply when art direction, design-system reasoning, content hierarchy, culturally central representation, responsive behavior, rendered visual quality, or typography materially matters; pair with specialist skills for deep security, SEO, legal, backend, deployment, or compliance work.
---

# Design DNA

Contents: [absolutes](#the-absolutes-come-first) ·
[two axes](#two-axes-and-the-default-is-awesome) ·
[authority](#resolve-authority) · [classify](#classify-the-work) ·
[creative freedom](#preserve-creative-freedom) ·
[invariants](#keep-these-invariants) ·
[process spine](#follow-the-process-spine) ·
[router](#load-guidance-only-for-the-decision-now) ·
[specialists](#coordinate-specialists) ·
[evidence](#bound-readiness-and-evidence) · [the gate](#the-gate-restated)

Create web work whose content, hierarchy, system, and behavior are visibly
chosen for this project and audience. The bar has two halves, both
mandatory: someone scrolling the finished work must never think "AI made
this," and the work must be mistakable for a senior team at a top agency.
Optimize for specificity, clarity, credibility, usability, time-register
fit, and finish. Diagnose observable causes; never promise undetectable AI
involvement, score aesthetic authorship, or claim human-only creation.

## The absolutes come first

This installation carries a standing accountable-owner policy:
[policy/absolutes.md](policy/absolutes.md). Read it before any design work.
Its ABSOLUTE tier is never lifted by anyone, including a client; its HARD
tier lifts only by explicit client direction, logged. The short version:

1. NEVER an em dash in user-facing text.
2. NEVER an animated number count-up.
3. NEVER a fabricated statistic, testimonial, review, logo, or person.
4. NEVER the indigo-violet gradient kit or gradient text.
5. NEVER fake product UI.
6. NEVER the hero, three-cards, testimonials, CTA, footer default skeleton.
7. NEVER below 4.5:1 body contrast, 3:1 large, or without keyboard access.
8. NEVER a silent font fallback; the face that ships is the face that
   painted, proven by the rendered-font verification.
9. NEVER a visible string a visitor cannot parse.
10. NEVER a done-claim without the ~1440 and ~375 screenshot pair, saved
    and looked at.
11. NEVER live on inference; every build is a demo until the owner says
    live in his own words.

These act pre-render, like a brand guideline. Everything subtler in this
skill stays post-render review vocabulary and is never an inverse prompt.

## Two axes, and the default is awesome

One axis runs AI-looking to human-crafted. The other runs plain to rich.
Passing the first axis while staying plain still fails: a page a visitor
would call safe, thin, or boring has missed the bar exactly as badly as one
that looks generated. The default target is rich: committed concept, real
imagery, depth, dramatic scale, one signature done fully. Restraint is a
committed, rendered-successful choice the brief supports, never the residue
of timidity or missing assets. When unsure, aim more ambitious, not safer.

Your first instinct is the statistical mean: the top-ranked idea in your
head is what every model run would ship. For greenfield, showcase, or
open-direction work, never deliver the first-ranked concept without at
least one materially different rendered alternative to compare against.
Unspecific quality feedback ("more premium," "boring," "make it better")
means ambition was too low: respond by raising the concept, imagery,
depth, scale, and signature, never by staying plain and safe. If the
approved direction is a committed quiet one, raise craft, specificity, and
finish WITHIN it first, and reopen the direction only if the owner
confirms the quiet itself is the complaint.

## Resolve authority

1. Safety, law, privacy, accessibility, factual integrity, repository
   instructions.
2. Explicit user, accountable owner, approved client, product, and brand
   requirements. The [owner absolutes](policy/absolutes.md) sit here,
   always active. A project-local owner policy may add to them; nothing
   below this tier may soften them.
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
| Showcase | Expressive, premium, highly visible, or explicitly rejecting safe output. | Research, compare rendered alternatives that challenge the first default, deepen risk-selected proof, polish, adversarial review, owner acceptance kept separate. |
| Range Study | A multi-route brief explicitly requiring meaningful creative range. | Shared foundations stay dependable; route-family record before scaling; proof routes chosen by uncertainty; matched route atlas review. |
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
that answers its actual decisions.

## Preserve creative freedom

Keep low-freedom rules for truth, rights, privacy, safety, accessibility,
working behavior, repository constraints, explicit owner and brand
requirements, and the owner absolutes. Keep aesthetic decisions
high-freedom: beyond the absolutes there is no global font, palette, style,
geometry, ornament, layout, interaction, motion, section-order, or
concept-count whitelist or blacklist. Common choices are not automatically
generic; uncommon choices are not automatically good. A fitting direction
may be singular, plural, restrained, maximal, decorative, conventional,
historically referential, or deliberately dissonant. Read
[creative freedom](references/creative-freedom.md) before imposing an
aesthetic rule that did not come from the project or the absolutes.

## Keep these invariants

- Preserve repository instructions, unrelated work, established systems,
  and working integrations unless the task authorizes change.
- Do not invent business facts, proof, people, metrics, reviews, assets,
  availability, or integrations. Placeholders are visibly labeled AND
  tracked in the [placeholder register](templates/placeholder-register-template.md).
- Demo mode by default: no real form endpoints, payments, bookings,
  tracking, or production deployment before the owner says live in his own
  words. Dead CTAs get an explicit demo-notice behavior.
- Every Persuade or Experience surface declares a deliberate display voice;
  the [typography](references/craft/typography.md) selection protocol with
  named rejects is mandatory for greenfield type.
- A deliberate media strategy for every build. For Persuade and Experience
  work whose value is physical or sensory, large real photography (or
  disclosed generated concept media) is a launch requirement, not an
  optimization; a text-led treatment there requires a logged owner
  authorization naming the alternative offered. Missing supplied
  photography is an input gap, never an instruction to design around
  absence.
- Every visible string passes the
  [parseable-text](references/quality/parseable-text.md) gate. Keep
  customer-facing copy about the customer's subject; never narrate design
  rationale, the visuals, or internal process onto the page.
- Size follows information value: the biggest type answers the visitor's
  first question.
- Verify by seeing: judging craft from code alone is prohibited. Nothing
  ships without the rendered screenshot pair, saved and looked at. If
  rendering is impossible, the deliverable is blocked and says so.
- Working artifacts are never mistakable for the site. There is no private
  render in a watched pane: anything written to disk or rendered may reach
  the owner's eyes, and the owner's first sight of a rendered artifact
  shapes every judgment after it. Internal renders (direction proofs,
  specimen pages, harness pages) live under `.design-dna/proofs/`, never in
  the site root, and carry a visible INTERNAL WORKING PROOF banner. A
  specimen strip or candidate comparison never shares a page with a
  composition that could be read as the design. A placeholder media area is
  a flat neutral labeled frame, never a gradient fill or styled decoration;
  a gradient block standing in for a photo IS the AI look. Before yielding
  any turn, point every watched preview at the most finished state, and
  present results with the saved gate screenshots, never a mid-process pane.
- Consult the [ledger](references/quality/ledger.md) before directing and
  run its rotation test (family: absent from the last three rows;
  macrostructure: differs from the previous two; class saturation applies);
  append its row on ship.
- Preserve semantic structure, keyboard and touch access, visible focus,
  contrast, responsive reflow, reduced motion, and resilient fallbacks.
- Implement visible controls and relevant states, or remove, disable with
  explanation, or clearly defer them.
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

1. Inspect the project; frame audience, task, facts, assets, constraints,
   delivery state. Declare demo mode and create the placeholder register.
2. Gather truthful source material; define public orientation; establish
   content and route structure; choose the media path. For culturally
   central subjects, name the review authority before visual commitment.
3. Consult the ledger. When direction is open or ambition is high, build a
   retrieval-dated reference dossier, render enough materially different
   evidence to expose the real choice (the first-instinct floor), record
   perception before diagnosis, select with rationale.
4. Proof the consequential decisions with real copy at real widths:
   typography with the selection protocol, palette split into inks and
   graphics, composition, media.
5. Extract only the reusable rules the project needs; keep justified
   one-offs. For a Range Study, separate shared foundations from route
   bodies.
6. Implement the real path and states within the existing technical
   contract.
7. Render, inspect, revise causes, rerun affected checks. For every
   substantial new build or visual redesign, run the
   [adversarial specificity review](references/quality/specificity-review.md)
   against the final implementation. Run the full
   [preship gate](templates/preship-gate.md). Append the ledger row.
   Obtain owner acceptance where required; disclose remaining limits.

Ask only high-leverage concept questions whose answers would materially
change direction; otherwise decide and note it.

## Load guidance only for the decision now

Do not preload the library. Load the smallest set that answers the current
decision, then return to the router.

| Decision or risk now | Load |
| --- | --- |
| Any build or revision nearing done | [Preship gate](templates/preship-gate.md); it is mandatory, not optional. |
| Type selection, font loading, display emphasis, "fonts look bad" | [Typography](references/craft/typography.md), including the dated bench and the mandatory rendered-font verification. |
| Decorative labels, HUD text, eyebrows, "random text," copy texture | [Parseable text](references/quality/parseable-text.md). |
| Starting any direction; avoiding self-repetition | [Ledger](references/quality/ledger.md). |
| Missing, sparse, or contradictory project material | [Content discovery](references/quality/content-discovery.md). |
| New direction, redesign, "generic," "dated" | [Art direction](references/craft/art-direction.md); optionally [decision case studies](references/decision-case-studies.md). |
| Open brief, greenfield direction, materially different options | [Creative exploration](references/craft/creative-exploration.md), then [art direction](references/craft/art-direction.md). |
| "Make it impressive," premium, showcase, "too plain," "boring" | [Creative freedom](references/creative-freedom.md), [creative exploration](references/craft/creative-exploration.md), [expression and energy](references/craft/expression-energy.md); revision verbs via [design tuning passes](references/craft/design-tuning-passes.md); [finish and polish](references/quality/finish-polish.md) after direction works. |
| First complete render or durable defect | Unprimed observation ([specificity review, "Observe before diagnosing"](references/quality/specificity-review.md)), then the [risk rubric](references/risk-rubric.md). |
| Explicit AI-looking, vibe-coded, templated, house-style concern | Direction from project evidence first; after a render, the [convergence review](references/convergence-watch.md); close with the [specificity review](references/quality/specificity-review.md). |
| Palette, depth, composition | [Color and composition](references/craft/color-composition.md). |
| Grid, grouping, rhythm, density | [Layout and density](references/craft/layout-density.md). |
| Routes, navigation, headings, actions, content states | [Content and IA](references/craft/content-ia.md). |
| Multi-route anthology or capability showcase | [Route-family art direction](references/craft/route-family-art-direction.md); activate Range Study. |
| Photography, generated media, illustration, external assets | [Imagery](references/craft/imagery-illustration.md) and [asset integrity](references/quality/asset-integrity.md). |
| Icons or pictograms | [Iconography](references/craft/iconography.md). |
| Motion, scrolling, transitions, direct interaction | [Motion and interaction](references/craft/motion-interaction.md). |
| Multi-device or public surface | [Responsive adaptation](references/craft/responsive-adaptation.md). |
| Components, tokens, themes, libraries, handoff | [Systems and components](references/craft/systems-components.md); [handoff record](templates/handoff-template.md) when maintained. |
| Brand identity, campaign, recognition across surfaces | [Brand systems](references/craft/brand-systems.md). |
| Proof drifting during implementation | [Proof-to-build fidelity](references/quality/proof-to-build-fidelity.md) and its [delta ledger](templates/proof-build-delta-template.md). |
| Figma, Storybook, token pipelines, motion tooling | [Tooling adapters](references/quality/tooling-adapters.md); [design-context capsule](templates/design-context-capsule-template.md) for compiled evidence. |
| Chart, map, metric, comparison | [Data visualization](references/craft/data-visualization.md). |
| Address, venue, directions, wayfinding | [Location and wayfinding](references/craft/location-wayfinding.md). |
| Signup, auth, onboarding, account | [Identity and onboarding](references/flows/identity-account-onboarding.md). |
| Plans, invoices, renewals, cancellations | [Subscription and billing](references/flows/subscription-billing.md). |
| Inbox, chat, notifications | [Messaging and notifications](references/flows/messaging-notifications.md). |
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
| Classifying a review finding | [Review severity](references/quality/review-severity.md). |
| Baseline-versus-candidate screenshot evidence | [Rendered comparison](references/quality/render-comparison.md). |
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

Nothing is presented as done until the
[preship gate](templates/preship-gate.md) passes on the rendered output:
every ABSOLUTE clean, the rendered-font verification green, the
parseable-text pass complete, the ~1440 and ~375 screenshots saved and
looked at, the placeholder register accounted for, the ledger row written,
and the demo/live state stated in the owner's words. One P0 hit blocks the
ship until fixed. If any of this cannot be run, the work is blocked and
says so plainly; it does not ship with caveats.
