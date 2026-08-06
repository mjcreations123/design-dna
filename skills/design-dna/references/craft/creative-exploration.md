# Creative exploration and direction selection

Use this when a consequential visual decision remains open: greenfield work,
a substantial redesign, an expressive request, a disputed direction, or a
result the accountable owner rejects as generic, boring, wrong, or too close
to another site. Exploration should reveal a real choice before implementation
hardens around the first plausible answer.

Read the [creative freedom boundary](../creative-freedom.md) first. Do not use
this method to impose a Design DNA house style.

## Contents

- [Scale exploration to the decision](#scale-exploration-to-the-decision)
- [Establish the field without trend priming](#establish-the-field-without-trend-priming)
- [Identify the consequential question](#identify-the-consequential-question)
- [Develop materially different answers](#develop-materially-different-answers)
- [Limit anchoring when capability allows](#limit-anchoring-when-capability-allows)
- [Choose proof that matches the uncertainty](#choose-proof-that-matches-the-uncertainty)
- [Review perception before rationale](#review-perception-before-rationale)
- [Select for fit, not compliance](#select-for-fit-not-compliance)
- [Deepen before broad propagation](#deepen-before-broad-propagation)
- [Iterate without erasing accepted work](#iterate-without-erasing-accepted-work)
- [Close the exploration record](#close-the-exploration-record)

## Scale exploration to the decision

Explore when different answers could materially change audience response,
comprehension, task flow, identity, content structure, media requirements,
cost, or maintainability. Scale it down when an established system, approved
reference, urgent repair, or narrow component scope already settles most of
the field.

The amount of exploration depends on uncertainty, stakes, reversibility,
schedule, available evidence, and what an accountable owner needs to decide.
There is no universal concept count, proof count, candidate format, or required
creative device. Record why the explored field was sufficient.

Do not treat prose labels as visual proof. When the decision is materially
visual, make the important difference visible at a fidelity appropriate to
the decision before scaling the full build.

## Establish the field without trend priming

Start from project evidence rather than a catalog of generic or allegedly
AI-looking motifs. Gather what is available and authorized:

- audience situations, tasks, decisions, content, and failure conditions;
- the subject's real objects, language, rituals, behavior, data, place,
  materials, people, and constraints;
- approved identity, cultural, editorial, product, and system evidence;
- current category behavior and useful conventions;
- adjacent creative or non-web references that expand the field;
- technical, accessibility, rights, performance, and maintenance boundaries;
- owner preferences, rejections, and examples, with their exact scope.

Record source, retrieval date, relevance, transferable relationship, and what
must not be copied. A reference may inform composition, sequence, behavior,
material, typography, image treatment, density, or another attribute without
becoming a whole-site template. Galleries and social posts are discovery
evidence, not proof of usability, truth, popularity, or rights.

When browsing or source material is unavailable, state the gap and keep the
direction reversible. Never invent a reference review or a local tradition.

## Identify the consequential question

Write the choice the exploration must expose. Examples include how the site
should orient a first-time visitor, whether a story should unfold through
reading or interaction, how a product's physical character should enter the
interface, or which relationship between identity and utility should lead.
These are examples, not required axes.

Separate constraints before generating:

| Constraint | Class | Authority and evidence | Consequence |
| --- | --- | --- | --- |
|  | non-negotiable, inherited, negotiated, or open |  |  |

Do not promote a producer preference, scanner observation, familiar Design DNA
pattern, or fashionable reference into a project constraint.

## Develop materially different answers

Generate candidates independently enough that each can answer the brief on
its own terms. A candidate may differ in any consequential combination of
content, order, spatial model, type, media, color, material, interaction,
motion, ornament, density, tone, or responsive behavior. It need not cross a
predefined set of axes.

Surface substitutions inside an unchanged composition are normally one
direction. A type-, palette-, media-, or ornament-led candidate can still be a
genuinely different answer when that medium changes the experience rather than
reskinning it.

For each candidate, create an extensible `creative_logic` record:

| Field | Record |
| --- | --- |
| `logic_id` | Stable candidate identifier when useful. |
| `statement` | The candidate's proposed answer in plain project language. |
| `evidence` | Material, references, owner direction, specimens, or observations supporting it. |
| `decisions` | Only the consequential design decisions this answer actually makes. |
| `limits` | Assumptions, rights, content, cultural, accessibility, technical, or maintenance boundaries. |
| `status` | Provisional, accepted, revised, rejected, or blocked. |
| `extensions` | Candidate-specific information that improves evaluation. |

Use an observable decision ledger rather than mandatory taste fields:

| Decision ID | Concern | Decision | Why it belongs | Expected observation | Adaptation or limit |
| --- | --- | --- | --- | --- | --- |
|  |  |  | project, audience, aesthetic, editorial, cultural, or production evidence | what a reviewer should see, understand, feel, use, or maintain | relevant state, size, input, language, fallback, or removal condition |

Candidate-specific aesthetic descriptions may be useful. None is a required
field; do not invent one to make the record look complete.

## Limit anchoring when capability allows

When several candidates are warranted and fresh contexts or collaborators are
available, give them the same approved source packet without exposing sibling
drafts. Bind each result to that packet and equivalent constraints. If
independent contexts are unavailable, checkpoint one answer before beginning
another from the source material rather than mutating only its surface.

Candidate isolation reduces first-draft anchoring; it does not guarantee
quality or replace shared comparison. Record the method and limitation only
when this level of provenance matters to the decision.

## Choose proof that matches the uncertainty

Render or prototype the part that can settle the decision. Depending on the
candidate, that might be an opening, a reading passage, a task sequence, a
responsive transformation, an image sequence, a motion study, a component
state, or another representative slice. Do not force every direction into a
hero-and-sections proof.

Use real approved copy and representative media dimensions where available.
Hold enough source content, route/state, and viewport conditions constant to
make the intended comparison fair. Bind important evidence to candidate/build
identity, source packet, route or state, viewport, date, and artifact path or
hash when the project's assurance level requires it.

No universal minimum number of rendered candidates applies. The evidence is
sufficient when it exposes the consequential tradeoff and supports a decision.
If a missing render, behavior, asset, script, or device condition prevents
that, label it unproven instead of calling the gate passed.

## Review perception before rationale

When capability allows, show the rendered candidate to an unbriefed reviewer
before exposing them to its rationale, scanner output, recurring-pattern list,
or sibling feedback. Ask open questions about what they understand, notice,
feel, remember, expect to do, and find confusing. Anchor actionable comments
to the exact artifact and region.

Do not force responses into a universal emotional or memorability score. Use
the success conditions established by the project and record reviewer
relationship, exposure, limitations, and disagreement.

## Select for fit, not compliance

Compare candidates against the actual brief and constraints. Relevant criteria
may include task, comprehension, requested feeling, owner preference, project
specificity, cultural fit, content and media demands, accessibility,
performance, technical feasibility, maintenance, and unresolved assumptions.
Use only the criteria that matter to the decision.

Choose the strongest overall fit, not the rarest or loudest answer. Record:

- which candidate was selected and the evidence supporting it;
- why alternatives lost, without turning those losses into global bans;
- useful decisions retained from another candidate, if any;
- unresolved assumptions, owner decisions, and required proof;
- a reversible checkpoint appropriate to the repository and risk.

When the accountable owner's choice would materially change the result,
present directly reviewable alternatives and ask. Otherwise proceed with a
recorded rationale inside the user's authority.

## Deepen before broad propagation

Before repeating a new direction across many routes or components, implement
enough of the riskiest or most representative material to test its creative
logic, real content, states, responsive behavior, access, and production
feasibility. The representative slice is chosen by risk and project value;
there is no required “golden” page type.

Do not propagate a visual trick merely to manufacture consistency. Reuse the
decisions that should be systemic, keep route- or content-specific decisions
local, and allow justified exceptions.

## Iterate without erasing accepted work

For a material revision:

1. bind the observed problem to the current route, state, viewport, and build;
2. identify the decision or constraint involved;
3. preserve accepted facts, assets, integrations, and design decisions outside
   the affected scope;
4. change the smallest coherent cause;
5. rerender the same relevant conditions;
6. inspect whole-page and shared-consumer effects.

Regenerate broadly only when the direction itself has been reopened. A local
defect does not automatically authorize replacing accepted work.

## Close the exploration record

Proceed when the consequential choice is visible enough to decide, the chosen
`creative_logic` and observable decisions are recorded, hard constraints are
met or explicitly blocked, important assumptions are labeled, responsive and
state consequences are understood at the needed fidelity, and the selection
has an accountable disposition.

Do not require a named aesthetic device, fixed progression, candidate count,
proof count, or test ritual unless this project's own brief or decision owner
requires it.
