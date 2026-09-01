---
name: design-dna
description: Builds, redesigns, polishes, and visually reviews websites and web UIs that must feel specific, current, non-generic, and production-quality. Use for landing pages, multi-page sites, place and community publications, hospitality, ecommerce, portfolios, editorial sites, dashboards, product interfaces, documentation, and components; requests to avoid AI-looking, vibe-coded, templated, cookie-cutter, accidentally dated, or time-incongruent design; feedback that a result feels plain, boring, under-designed, too safe, or visually weak; complaints about ugly or unstyled typography; and public copy that sounds generic, robotic, over-explained, construction-facing, or littered with random decorative labels, micro-text, or symbols. Apply when art direction, visual systems, content hierarchy, culturally central representation, responsive behavior, rendered quality, copy voice, or typography materially matters. Pair with specialist skills for deep security, SEO, legal, backend, deployment, or compliance.
---

# Design DNA

## Contents

[boundaries](#assurance-boundaries-come-first) |
[quality axes](#separate-specificity-from-ambition) |
[authority](#resolve-authority) | [classify](#classify-the-work) |
[creative freedom](#preserve-creative-freedom) |
[invariants](#keep-these-invariants) |
[direction start](#start-direction-progressively) |
[router](#load-guidance-only-for-the-decision-now) |
[specialists](#coordinate-specialists) |
[evidence](#bound-readiness-and-evidence) | [the gate](#the-gate-restated)

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

An installation may carry such a source. Prefer the host-neutral canonical
record at `~/.design-dna/owner-standards.md`; use a host-local compatibility
record such as `~/.claude/design-dna/owner-standards.md` only when the
canonical record is absent or expressly delegates to it. Read the applicable
record before the direction exists.
It is the accountable owner's own dated record, so the constraints in it are
traced and enforceable pre-render for that owner's work, unlike a trend list.
It closes only the ingredients it names, for that owner only; everything else
stays open. If no such file exists, proceed without one and do not
reconstruct its contents from memory.

An owner record may reference the host-neutral machine contract at
`~/.design-dna/owner-pattern-contract.json`. When that active contract applies,
read it before direction selection and add the `owner-pattern-contract`
initialization trigger beside any owner-required recurrence trigger. Its items
must describe failed relationships rather than naked ingredients. Create and
complete the project-local review through
`scripts/owner_pattern_audit.py`; do not replace it with prose, a source scan,
or an assurance that the result feels different. A contract-controlled failure
must be dispositioned before broad implementation and proven absent against the
exact final distinct wide and narrow full-page rendered evidence, with every
capture bound to the same reviewed build. Missing, reused, pending, blocked, or
contract-drifted evidence blocks the corresponding gate. This proves closure
of the named owner failures only; it is not an AI detector or an authorship
claim.

## Separate specificity from ambition

One quality axis asks whether the work is project-specific rather than a
reusable first draft. Another asks whether the chosen ambition is fully
realized. A third asks whether the finished artifact is credible for the
public reality it claims. A quiet information page can be more resolved than a
cinematic showcase; a maximal composition can be more coherent than a minimal
one. Neither richness nor restraint is the default, and distinctiveness does
not compensate for theatricality, implausibility, or visitor-irrelevant design
performance.

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
| New build, visual redesign, or route family | Preflight, direct, proof, implement, complete rendered plus engineering review. A fresh public-facing representation starts at Standard with the full public rendered-review rigor; add Showcase only when its brief calls for it. For multiple independently addressable routes, name each route's body job before one page recipe spreads across them. |
| Component or meaningful visual change | Inherit the system, define the component's job and states, test changed behavior. |
| Visual or UX review | Inspect rendered and source evidence; report observed causes and unperformed checks. |
| Mechanical or purely functional change | Preserve the visual system, verify proportionately. |

Capability presets are cumulative; adding one cannot remove another:

| Preset | Use when | Minimum |
| --- | --- | --- |
| Quick | Bounded repair in an established system, low risk. | Inspect context, preserve the system, implement changed states, run affected checks plus the preship gate on the touched surface. |
| Standard | New route, meaningful feature, ordinary redesign. | Frame, direct, prove consequential decisions, implement, full rendered plus engineering review, artifact-credibility review for a public proposition, full preship gate. |
| Enterprise Candidate | Every fresh public website, unless the task is an explicitly bounded repair or non-public surface. | Standard plus category-appropriate public topology, intentional media/composition planning, fully considered key states, and a rendered wide/narrow review that must close obvious first-draft defects before preview. It does not claim a financial valuation, require an oversized scope, prescribe a style, or automatically select Showcase. |
| Showcase | The brief expressly calls for premium, showcase, high-ambition work, or direction recovery after a rejected visual answer. | Research and externalize directly reviewable contrast sufficient to challenge the first default; build full alternatives when uncertainty, stakes, or owner choice justify them; deepen risk-selected proof, polish, adversarial review, owner acceptance kept separate. |
| Project Contrast | The owner says this work must differ from recent authorized work, says sites feel alike, or declares an owner-scoped recurrence requirement. | Before broad implementation, create a truthful `draft` record, settle it to `direction-ready` from grounded project evidence, challenge the first answer with an organizing alternative, and record why the selected encounter differs from the closest authorized comparator. Bind wide/narrow proof at `proof-ready`; only a reviewed record can support the comparison claim. This is not a font, color, or novelty quota. |
| Direction Challenge | The owner explicitly activates a three-root recurrence escalation or expressly asks for a multi-root high-ambition greenfield concept challenge. A premium or high-ambition site alone remains Showcase. | Before broad implementation, record three or more incompatible brief-native roots before polished examples, bind two different roots to path-bound schema-3 wide/narrow rendered proof slices, choose one against an explicitly rendered rejected root, freeze the independent unprimed view, advance the record to `reviewed`, and explicitly open its `broad-implementation` boundary. The schema is review evidence, not a site architecture, style catalog, rotation schedule, or ingredient quota. |
| Range Study | A multi-route brief explicitly requiring meaningful creative range. | Shared foundations stay dependable; route-family record before scaling; proof routes chosen by uncertainty; matched route atlas review. |
| Batch Study | A controlled evaluation of at least three unrelated website briefs. | Freeze independent briefs and source packets; record human-auditable implementation isolation; resolve capture and contact-sheet data handling for built cases; bind each capture to its rendered route, profile, exact public-build manifest, and capture mode; freeze capture-set-bound site observations before sibling output or diagnostics; record the neutral-label whole-system first observation only after those reviews are frozen; then record a later capture-set-bound human contextual disposition that closes material findings separately from protocol coverage; keep planned and correctly blocked cases separate. It is an evaluation method, not evidence that fictional specimens are a client-ready portfolio or a substitute for owner taste review. |
| High-risk | Consequential transactions, identity, money, regulated claims. | Task, state, and specialist evidence first; visual ambition cannot waive a safety gate. |
| Asset-led | Material imagery, fonts, or media need a durable record; also select it when a physical/sensory subject depends on recognizable material or the owner explicitly asks for photos or rich media. | Before broad implementation, bind at least one usable project-relevant asset and record its role, provenance, rights, factual status, privacy, responsive delivery, and accessibility. No global image count or genre is implied. |

A fresh public-facing site that represents a business, product, organization,
place, creator, or campaign begins at **Standard plus Enterprise Candidate**,
even when the brief says only "build a website." Complete its full rendered,
engineering, public-surface, and copy-integrity review for the candidate. Add
**Showcase** only when the
brief actually requests a premium, showcase, high-ambition answer or when a
rejected visual direction needs recovery; public status or route count alone
does not select it. This chooses process depth and does not choose a house
style. For
Showcase work without an approved rendered direction, load [taste
calibration](references/craft/taste-calibration.md) before generating the
first public surface.

Read [Enterprise Candidate](references/quality/enterprise-candidate.md) before
the first visual candidate. It is an execution-quality default for public work:
derive the scale, content depth, media role, interaction coverage, and visual
ambition from the actual brief. Do not turn it into a fake
"enterprise" claim, a trillion-dollar fiction, a site-map quota, a one-size
hero, or a brand/style recipe. Routine visual QA and root-cause refinement are
part of the build, not approval checkpoints the owner must rediscover through
repeated feedback.

For every fresh Enterprise Candidate public website, read
[Reference-led direction](references/quality/reference-led-direction.md) before
the first visual candidate. Start from the maintained public source registry,
weight eligible sources by this brief, record ten strong individual references
and at least three project-specific counterexamples, then map a selected subset
of five through ten references into one internal direction. A public gallery
entry can qualify even when no live website exists. Do not use inaccessible
material, treat a gallery listing as proof of quality, turn the result into a
generic collage, or expose the research process on the customer-facing site.

A prior result rejected as AI-looking, generic, ugly, or in bad taste selects
at least Standard plus [taste calibration](references/craft/taste-calibration.md),
the convergence and specificity reviews. When the rejection reopens the visual
premise, add Showcase as direction recovery; a contained defect that preserves
the premise may remain Standard. A direct rejection of the visual answer
reopens the direction before more pages or cosmetic polish are added.

Bind a direct visual rejection to the exact candidate and record the scoped
relationship cluster that failed: relevant type posture, CTA grammar, edge and
container behavior, depth/effects, section rhythm, material/media absence, and
public-copy behavior. Preserve facts, functions, integrations, and accepted
decisions separately. Use that first-party rejection before generating the
replacement; do not turn one failed cluster into a permanent global font,
shape, shadow, color, or photography ban.

Select **Project Contrast** when an owner says recent work feels alike, asks
for this work to differ from recent authorized work, or has an owner-scoped
recurrence requirement. It adds productive friction at the moment that
otherwise produces a reusable first draft: a brief-native anchor, an alternate
organizing answer, an authorized nearest-sibling comparison when available,
and a rendered collision test. It does not require every project to change
every surface ingredient, and an inherited product or brand system may
truthfully use the lighter exemption recorded in the contract. Read
[visual-grammar variance](references/quality/visual-grammar-variance.md) when
the complaint concerns the same hero, type posture, CTA treatment, containers,
background panels, underlines, route rhythm, or mobile collapse. Compare the
candidate with actual authorized output; whether the same layout could
theoretically suit another industry is not the test.

Escalate to **Direction Challenge** only when the owner explicitly activates
the three-root recurrence escalation or expressly requests a multi-root
high-ambition greenfield concept challenge. A generic premium or high-ambition
website selects Showcase, not Direction Challenge. This escalation adds
Direction Challenge beside Project Contrast; its roots and cross-root proof
slices apply only to the declared challenge. It does not turn ordinary
exploration into a standing three-concept rule. Read [Direction
Challenge](references/quality/direction-challenge.md) before any polished-
example search or broad implementation.

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
  [placeholder register](templates/placeholder-register-template.md). For a
  sparse, fictional, or internal concept, use the approved fixture or claim
  ledger and actual behavior to distinguish context-free entry orientation from
  claim- or action-local status; do not fill every route with duplicate boundary
  words.
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
  Standard-or-stronger work records that decision in the direction record's
  `Material, media, and public-copy boundary`. Select Asset-led when the
  physical/sensory subject requires recognizable material or the owner asks
  for photos/rich media. Before broad implementation, `.design-dna/assets.yml`
  must contain a usable bound asset; “no photos were supplied” cannot serve as
  the project's media-light rationale. A physical/sensory media-light exception
  must explain the specific visitor or truth benefit and record explicit
  owner/client approval with an ISO date.
- Every visible string passes the
  [parseable-text](references/quality/parseable-text.md) gate. Keep
  customer-facing copy relevant to the customer's subject or task. Do not
  expose design rationale, implementation residue, component names, or false
  system theater as visitor content. Truthful operational status, technical
  detail, or atmosphere remains valid when the audience needs it and its
  meaning is clear.
- For Standard-or-stronger public builds, read
  [Public copy integrity](references/quality/public-copy-integrity.md) before
  drafting prominent public language and close it in the final Enterprise
  Candidate review. A slogan, headline, or brand statement must earn its place
  through an approved voice or a concrete project/category/visitor anchor;
  do not manufacture a polished brand thesis merely because the draft needs a
  line above an image. Treat every count, ordinal, and step label as public
  information: retain it only when a visitor needs a real fact, quantity,
  comparison, deadline, reference, or action order. Do not manufacture “four
  reasons,” “six easy steps,” `01 / 02 / 03`, or a numbered hero merely to give
  the page a cadence. Review the complete visible and accessible public corpus
  before preview, including rendered paragraph density and numeric/listicle
  framing; do not use text to fill an otherwise empty layout.
- For Enterprise Candidate public builds, complete the project-local
  `reference-dossier.md` before broad implementation. It must bind the active
  public source context, ten strong individual references, at least three
  weak/mismatched counterexamples, and a selected five-through-ten-reference
  project synthesis. Reference material is a decision input, not a visual
  parts bin: transfer only project-relevant relationships and retain explicit
  non-copying boundaries for brands, copy, assets, code, and distinctive whole
  pages. The final rendered review must close the resulting direction against
  its positive and negative evidence.
- Treat an owner's explanation of why a design choice fits as internal
  direction, not customer-facing copy. Do not turn a design rationale, producer
  note, project record, workflow stage, internal-only state, content-model or
  back-end category, raw field name, or implementation term into a public
  heading, label, category, caption, tooltip, help panel, or navigation item
  merely because it helped construct the work. Let it shape the design instead.
  Surface it only when the owner explicitly requests public explanation or a
  visitor needs it to understand the subject, navigate, act, or avoid a concrete
  misconception; state the visitor consequence rather than the production story.
- Default a hero, paragraph, or section to its actual heading and content. Do
  not add an eyebrow, kicker, overline, or micro-label merely to announce the
  subject of the copy that follows or to make the composition feel designed.
  Keep one only when it communicates an independent, visitor-useful category,
  source/date, sequence/state, or explicit project/brand editorial convention
  with a real project basis. Form labels, navigation, captions, credits,
  legends, and operational status remain normal functional text. This is a
  hierarchy and copy rule, not a ban on the treatment itself; use
  [parseable text](references/quality/parseable-text.md) and
  [content IA](references/craft/content-ia.md) to review the relationship.
- When an actual public launch or delivery scope introduces discovery,
  conversion, contact, transaction, location, policy, measurement, or promotion
  decisions, load [launch completeness](references/quality/launch-completeness.md)
  after the direction exists and record only the relevant families. Do not make
  a fifteen-row marketing inventory the default input to every new design or
  manufacture a CTA, FAQ, promise, location, policy, tracker, or promotion.
- Size and prominence follow the intended encounter. The dominant element
  should support the visitor's first question, task, invitation, or deliberate
  point of tension; no universal type-size ordering applies.
- Review visual intensity and repeated devices across the whole rendered route
  and route family, not only one section at a time. A device may succeed once
  and become an unsupported producer fingerprint when every section repeats
  its scale, color field, border, numbering, card, crop, CTA, motion, or copy
  cadence. Do not require quietness or ban expressive ingredients; revise the
  cumulative relationship when the artifact makes every ordinary content job
  perform as a showcase moment.
- When an applicable active owner-pattern contract exists, treat every item as
  the precisely defined failure state in that contract—not as a trend-list
  ingredient or an invitation to build the opposite template. Record all
  direction dispositions as `controlled` before scaling the route family and
  all final dispositions as `absent` before completion. A meaningful instance
  of an ingredient does not satisfy a failure definition; an agent's claim that
  an unexplained instance is “intentional” does not clear it.
- Verify by seeing: code inspection cannot establish rendered craft. Save and
  inspect project-relevant rendered evidence across the widths, states, and
  preferences that can change the conclusion - normally including wide and
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
- When Project Contrast is active, settle the selected opening, dominant
  content operation, and body progression against a materially different
  counter-answer before propagating code. For an owner recurrence requirement,
  select a nonempty project-derived axis set that includes an encounter axis and
  a surface-language axis, then write a project-specific structural/encounter
  prompt and surface-language prompt. Neither is a list of ingredients that
  must differ. A same-project rejected candidate is useful rejection evidence,
  but it cannot replace the authorized cross-project closest sibling required
  to test recurrence among unrelated builds. If that nearest sibling remains close after noun,
  dominant-media, accent, and motion removal, reopen the earliest shared
  organizing decision rather than rotate a font, palette, effect, or shape.
- When Direction Challenge is active, record three or more roots before
  polished examples except supplied brand or source material; prove at least
  two roots with path-bound schema-3 wide/narrow slices; and select the chosen root
  against an explicitly rejected rendered root. This escalation is evidence
  for the current owner-triggered or explicitly multi-root high-ambition
  project, not a
  universal concept count or visual style rule.
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
- For a substantial public build, complete the
  [artifact credibility and cumulative-pattern review](references/quality/artifact-credibility.md)
  on final wide and narrow captures. Ask whether the site plausibly operates
  for its claimed audience, whether business/category reality survives without
  the maker's rationale, and whether media, copy, typography, and recurring
  visual machinery feel specific rather than staged. When recurrence is in
  scope, separately audit container/backplate logic and link/button/underline
  affordance across the whole route; do not infer a pass from changed colors,
  fonts, images, or industry nouns. Producer self-review may guide revision but
  cannot be relabeled as independent review, target-user validation, owner
  acceptance, or proof of authorship.
- When Enterprise Candidate is active, record its closure in the final
  visual-review record using the accompanying template section. Before any
  user-facing readiness claim, inspect the exact wide and narrow rendered
  candidate for public-surface credibility, first-screen composition,
  media-to-slot fit, key interaction/state finish, public-copy integrity, and
  the affected route family's shared geometry. An observed blank composition,
  unintended crop, off-screen opening content, broken state, first-draft
  residue, or generic brand-manifesto pattern reopens the source relationship
  across that family; do not patch one screenshot or sentence and call the site
  finished.

## Start direction progressively

For a substantial build or redesign, begin with [Direction
start](references/quality/direction-start.md) before making the first visual
candidate. It covers the compact pre-direction decisions: non-negotiable
boundaries, factual and delivery framing, proportional capability selection,
and the exact trigger for Project Contrast or Direction Challenge. Any early
direction at this point is a provisional hypothesis, not committed creative
logic. Before settling it or advancing a record to `direction-ready`, inspect
the minimum repository/system context and project/category material that could
materially change the encounter. Use project-provided evidence when it is
enough; research current external material only when it is available,
permitted, and could change the decision. Do not fetch material merely to
perform research theatre. Do not preload the whole workflow merely to select a
direction.

Once grounding supports the selected creative logic, load only the phase of
[the workflow](references/workflow.md) that is now needed: proof,
implementation, rendered revision, user validation, or delivery. The workflow
retains the detailed requirements for each phase and the project-local records
that make a consequential decision reviewable.

Before writing the full route family or propagating the selected visual system,
run the executable phase gate:

```text
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/owner_pattern_audit.py" "<PROJECT_ROOT>" --init-review
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "<PROJECT_ROOT>" --check-prebuild
```

Run the first command only when an applicable owner-pattern contract exists,
and run it once: it refuses to overwrite an existing review. Complete the
generated direction lane before the prebuild check. When the
`owner-pattern-contract` trigger is active, the prebuild gate invokes the audit
and fails closed on a missing, incomplete, or drifted review.

A nonzero result blocks broad implementation. The selected direction-stage
Markdown records must be hash-bound and `complete`; capability-only state,
untouched Range/Batch scaffolds, and draft records cannot pass. Close the cited
direction, material/media, Project Contrast, Direction Challenge, and proof gaps; do not
continue because the app compiles, a renderer emitted pixels, or the agent
intends to complete the records later. Small proof slices needed to satisfy the
gate remain allowed and must stay visibly separate from accepted public work.

Selection never waives the later gates. Standard-or-stronger work still needs
the final rendered and engineering review, the [adversarial specificity
review](references/quality/specificity-review.md), the [artifact credibility
review](references/quality/artifact-credibility.md) for a public proposition,
and the applicable
[preship gate](templates/preship-gate.md). Project Contrast and Direction
Challenge still require their project-local records and final proof boundaries;
Batch Study still reaches command success only at `final_ready`. Ask only
high-leverage concept questions whose answers would materially change
direction; otherwise decide and note the basis.

Freeze an unprimed first impression before revealing the rationale; record the
perceived category, stakes, and next action only as project-situated evidence.
Then reconcile every concrete consequential direction commitment against an
exact rendered or behavioral condition. Missing or partial consequential work
reopens the affected completion claim; prose confidence and build success do
not substitute for the artifact.

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

Open the [decision router](references/router.md) when a concrete decision or
risk arrives. Read the matching row and only the references it names; do not
scan every row as a generation prompt. Return here after the decision closes.

## Coordinate specialists

Design DNA owns project-specific art direction, content hierarchy, visual
coherence, responsive composition, and rendered finish. A specialist skill
owns its narrower domain. Combine conclusions at the boundary: a specialist
never introduces an unrelated visual system, and visual polish never waives
a specialist gate. Satisfy the stricter safety, truth, access, and
operational requirement, then preserve the chosen direction within it.

When **Frontend Design** is also active, Design DNA determines the
project-derived encounter and any Project Contrast evidence boundary;
Frontend Design translates that direction into intentional interface choices.
Neither skill may replace the brief-native decision with a reusable color,
type, component, or anti-default recipe.

## Bound readiness and evidence

"Production-quality design and implementation" describes only verified
dimensions. Authentication, personal data, payments, uploads, regulated
claims, public indexing, and production operations require the applicable
specialist review or an explicit `unverified` release block.

Create only useful evidence records with `scripts/init_project_state.py`.
The relevant workflow phase names its project-local record and template;
do not create the full catalog for every project. Keep mutable records
project-local with their stated privacy classification, follow
[owner-policy onboarding](references/owner-policy.md) only when that opt-in
governance applies, and run the initializer's `--check-ready` gate before
claiming records satisfy the selected capabilities. The
[preship gate](templates/preship-gate.md) remains the final cross-project
record.

`--check-prebuild` and `--check-ready` answer different claims. Prebuild is the
permission boundary before full-route implementation; readiness is the final
evidence boundary after implementation and review. Passing either never supplies
an automatic aesthetic judgment.

For Showcase, complete `taste-calibration.md` as an evidence record, not a
private moodboard: name a retrieval-dated reference dossier, hash-bind the
selected and counter proof artifacts, and explicitly disposition recurrence
risk as `active`, `not-applicable`, or `blocked`. `active` recurrence risk
must have an owner statement or authorized comparison basis; Showcase status,
a portfolio/sample purpose, a demo, or an evaluation alone does not select
Project Contrast. `not-applicable` and `blocked` need a substantive reason
rather than a silent exemption.

For a Standard-or-stronger final visual-review completion, bind the reviewed
build and source snapshot to one valid schema-3 renderer report. Its capture
matrix must make an explicit applicable/not-applicable/blocked decision for
each materially distinct reviewed body, with real wide and narrow captures for
each applicable body. Bind the first-impression/surface-fidelity,
adversarial-specificity, and preship closures to exact emitted PNGs. This is
evidence of what was reviewed, not an aesthetic score, fixed viewport count,
or recipe. Quick remains proportionate direct rendered review; legacy records
remain migratable and must be honestly reopened where new final-build evidence
was never recorded. When a reviewed Direction Challenge proof build differs
from the final reviewed build, bind the hash-checked proof-to-build delta ledger
with the changed decisions before readiness can be claimed.
The completed visual-review build is the canonical final identity: a completed
Connected Public Experience closure, every verified final continuity capture,
and any concrete Project Contrast candidate or verified capture set must name
that exact build. `--check-ready` fails closed on cross-record drift even when
each evidence lane is otherwise internally valid. Earlier user research may
truthfully bind a prototype; do not relabel it as final-build validation.
When the `owner-pattern-contract` trigger is active, readiness also requires
the matching project-local owner-pattern review to bind that same visual-review
build and a distinct wide plus narrow full-page PNG pair for every contract
failure state.

When Enterprise Candidate is active, the same exact reviewed build must also
close the Enterprise Candidate section of `visual-review.md`. A clean build,
successful route status, or an agent's confidence cannot replace the required
rendered observations. The owner need not approve ordinary polish iterations;
ask only when a missing business, brand, cultural, truth, or delivery decision
would materially change the candidate.

If Python 3.10+ or another capability is unavailable, perform every safe
manual equivalent that still answers the claim, name the checks not run, and
do not broaden the result. A manual visual review may improve and accurately
describe an agent-reviewed candidate; it does not fabricate the package's
schema-3 renderer record or close a formal readiness gate that explicitly
requires that record. Keep working through the remaining safe phases and label
only the blocked proof. The scanner supplies bounded source-review prompts;
the rendered proofs in the preship gate are never replaced by it.

## The gate, restated

Nothing is presented as done until the applicable
[preship gate](templates/preship-gate.md) passes on the rendered output. Bind
the exact build and risk-selected route, width, state, preference, typography,
content, media, access, and engineering evidence. A violated assurance
boundary blocks the corresponding completion or release claim. Missing
optional evidence is disclosed in scope; it does not become a fabricated
pass, a taste rule, or a reason to invent records.
