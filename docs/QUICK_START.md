# Design DNA quick start

## Start with one short request

In Codex:

```text
$design-dna Build a time-appropriate website for [business or product] using the supplied facts and assets.
```

In Claude Code with a direct personal skill:

```text
/design-dna Build a time-appropriate website for [business or product] using the supplied facts and assets.
```

Design DNA chooses a proportional assurance profile from the task. A fresh
public-facing site representing a business, product, organization, place,
creator, or campaign begins at Standard plus Enterprise Candidate, including
full public rendered, engineering, media, interaction, and copy-integrity
review. Add Showcase only when the brief expressly calls for premium,
showcase, high-ambition work or direction recovery; public status,
visibility, and route count alone do not select it. You can request Showcase explicitly
when that higher-ambition answer is actually wanted:

```text
$design-dna Use Showcase to build an exceptional, time-appropriate sample website for [business or product] using the supplied facts and assets.
```

When the work needs to be genuinely impressive rather than merely complete,
add the outcome you will judge in the render. For example:

```text
$design-dna Use Showcase and taste calibration. Build a client-facing website
for [business or product]. Research current project- and category-relevant
visual references, make a project-specific public encounter rather than a
generic template or internal design exercise, and show me the rendered wide and
narrow direction proof before scaling it. If the direction is ugly or
unconvincing, replace the organizing answer instead of just changing fonts,
colors, or effects.
```

Use `/design-dna` instead of `$design-dna` for a direct Claude Code skill. If
you deliberately installed the packaged Claude Code plugin, its namespaced
command is `/design-dna:design-dna`. Configure only one discovery route per
host.

Showcase initialization includes an optional `taste-calibration.md` working
record. Use it to preserve the public encounter, reference reasoning, and
rendered first-impression response that changed the direction; it is not a
form to complete merely to make a build look approved.

Relevant natural-language requests are intended to activate the skill, but
automatic loading is host- and version-dependent until observed in that
environment. Explicit invocation is the deterministic choice when Design DNA
is required.

## Choose assurance capabilities

| Capability | Choose it when | What it adds |
| --- | --- | --- |
| **Quick** | A bounded, low-risk repair or established-system change. | Focused context inspection, changed-state implementation, and affected checks. |
| **Standard** | A new route, meaningful feature, or ordinary redesign. | Direction framing, proportionate proof of consequential decisions, rendered review, and engineering verification. |
| **Enterprise Candidate** | Every fresh public website unless the task is an explicitly bounded repair or non-public surface. | Category-credible public topology, deliberate media and first-screen composition, key-state finish, high-attention copy integrity, and rendered wide/narrow closure. It does not claim enterprise scale, prescribe a style, or require a large site map. |
| **Connected Public Experience** | The brief explicitly asks for a detailed, connected, customer-facing, app-like, or client-demonstration experience, or its public promise depends on content, decisions, or state carrying between routes. | A direction-stage applicability decision, selected-root continuity model, truthful status crosswalk, meaningful path, handoffs, and rendered/functional proof plan before broad implementation; exact direct-entry/recovery evidence afterward. No page-count, admin, backend, database, funnel, or live-integration quota. |
| **Showcase** | The brief expressly asks for premium, showcase, or high-ambition work; a rejected direction needs recovery; or the owner explicitly asks for that deeper direction challenge. High visibility or owner sensitivity alone does not select it. | Project research and directly reviewable contrast sufficient to challenge the first default; full alternatives when uncertainty, stakes, or owner choice justify them; a recorded selection, deeper visual craft, and adversarial review. |
| **Project Contrast** | An unrelated public build must feel materially unlike recent studio work, or the owner says sites feel alike. | A brief-native counter-answer before broad implementation, the smallest owner-authorized closest-sibling comparison when available, and a wide/narrow collision review. It does not rotate visual ingredients. |
| **Direction Challenge** | An owner explicitly escalates recurrence, or deliberately asks for a high-ambition greenfield challenge. | Three or more incompatible brief-native roots before polished examples; two cross-root wide/narrow proof slices that bind material posture and actual asset use; a selected-versus-rejected rendered comparison; and an independent unprimed view. It must reach reviewed before broad implementation and is not a default concept quota. |
| **Range Study** | A real multi-route site must demonstrate meaningful creative range. | Dependable truth, navigation, accessibility, and operations; an explicit route-family record; route proof chosen by uncertainty; real-path checks; and a matched route atlas. |
| **Batch Study** | A controlled evaluation compares at least three unrelated website briefs; it is not the ordinary workflow for producing several client sites. | Frozen isolated briefs/builds, project-declared capture classes, renderer/public-manifest-bound captures, capture-set-bound site observations, a later neutral-label whole-system review, and a separate human contextual disposition. It does not produce an automatic aesthetic result. |
| **High-risk** | Identity, permissions, private data, money, regulated claims, consequential transactions, or difficult recovery. | Stronger task, state, content, specialist, recovery, and real-user evidence. |
| **Asset-led** | Physical or sensory recognition materially depends on media, the owner asks for photography/rich media, or imagery, video, audio, fonts, documents, maps, embeds, or generated media otherwise needs a durable record. | A usable bound asset before broad implementation, followed by type-specific provenance, rights, privacy, factual, approval, delivery, accessibility, and generated-media gates. |

Quick and Standard are proportional base presets. Enterprise Candidate applies
to fresh public websites; Showcase, Connected Public Experience, Project
Contrast, Direction Challenge, Range Study, Batch Study, High-risk, and
Asset-led can apply together. Adding a capability cannot silently remove a
stronger one.

High-visibility or owner-sensitive work still begins at Standard unless the
brief expressly calls for premium, showcase, high-ambition work or direction
recovery. Intensify Standard's rendered first-impression, surface-fidelity, and
taste review for those stakes; do not silently select Showcase.

For a detailed public experience whose content, decisions, or state must carry
between routes, request CPE explicitly:

```text
<INVOKE> Use Connected Public Experience. Build [subject] with the supplied
facts and assets. Record truthful delivery, content, and behavior statuses for
the consequential public paths; prove direct entry and recovery or continuation
against the exact build. Do not invent an admin, backend, database, funnel, or
live integration merely to make the experience look substantial.
```

For a new unrelated client or sample that must not reuse the studio's last
safe composition, request Project Contrast directly:

```text
<INVOKE> Use Project Contrast. Build [subject] as a genuine new
public encounter, not a reskin of recent work. Before broad implementation,
derive a brief-native counter-answer that changes the opening or content/body
operation. Compare only the smallest owner-authorized closest-sibling evidence
after that work exists. At review, test whether the result is still too close
after subject nouns, dominant media, accent, and motion are mentally removed.
If it is, reopen the earliest shared decision instead of swapping fonts,
colors, shapes, or effects.
```

Use Direction Challenge only for the explicit recurrence escalation or a
deliberately chosen high-ambition greenfield challenge. It pairs with Project
Contrast for the recurrence case; it can stand alone when no cross-project
comparison is authorized:

```text
<INVOKE> Use Showcase, Project Contrast, and Direction Challenge. Before
polished examples or broad implementation, derive at least three incompatible
brief-native roots. Bind wide and narrow proof slices from two different roots,
select the chosen root against a rendered rejected root, and freeze an
independent unprimed view. Do not treat changed fonts, colors, imagery, shapes,
or effects inside one composition as different roots.
```

Activate Batch Study before building its cases with `--profile batch-study`,
or create `.design-dna/batch-range.json` from the packaged template. The
`batch-range` filename is a stable internal interface; **Batch Study** is the
user-facing capability name. Freeze each site's packaged unprimed-observation
template before revealing sibling work, then use the packaged neutral-label
whole-system template to compare organizing logic, spatial and material
relationships, type roles, media, interaction, copy, and responsive behavior
in context. Those are review lenses, not ingredients every site must change.
`comparison_ready` means only that the declared protocol is covered. After the
whole-system review is frozen, a capture-set-bound human contextual disposition
may make `human_contextual_ready` true by closing material findings.
`final_ready` is their conjunction, and the audit still sets
`automatic_aesthetic_pass` to `false`. Those study fields do not qualify a
package for release or substitute for an owner judging a client-facing site.

For a multi-route showcase:

```text
<INVOKE> Use Showcase and Range Study to build a real multi-page website for
[subject]. Give every declared route an independently addressable, reloadable
path and a body whose content, structure, and creative logic follow that
route's job. Keep truth, navigation meaning, accessibility, and operations
dependable across the family. Record the family in
.design-dna/route-family.json, capture every route at the matched viewports the
project requires, run the route-family audit, and review the whole-site atlas.
Do not call surface substitutions meaningful range, and do not force every
route to differ through the same aesthetic fields.
```

When place, religion, ethnicity, language, or another lived identity is
central, request the cultural-context gate. The producing agent can verify
sources, terminology, directionality, and rendering but cannot certify its own
cultural acceptance or invent authority to waive review.

## Pass the prebuild boundary before scaling

The direction proof is allowed to be small. The full route family is not
allowed to spread until the selected direction-stage evidence is substantive,
complete, and bound to that proof.

```text
<PYTHON> -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "<PROJECT_ROOT>" --profile enterprise-candidate
<PYTHON> -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "<PROJECT_ROOT>" --mark-complete direction --binding-kind artifact --binding-id "<PROOF_ID>" --binding-path "<PROJECT_RELATIVE_PROOF_PATH>" --completion-owner "<REVIEWER>" --limitations "<KNOWN_LIMITS_OR_NONE_WITHIN_SCOPE>"
<PYTHON> -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "<PROJECT_ROOT>" --check-prebuild
```

Use only the opt-in initializer forms that match the brief:

```text
<PYTHON> -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "<PROJECT_ROOT>" --profile connected-public-experience
<PYTHON> -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "<PROJECT_ROOT>" --profile direction-challenge
<PYTHON> -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "<PROJECT_ROOT>" --profile showcase --trigger owner-recurrence-requirement
<PYTHON> -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --project "<PROJECT_ROOT>" --record assets --evidence-capability asset-led
<PYTHON> -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --print-asset-example
```

For Asset-led work, initialize the applicable base profile first, then run the
incremental `--record assets --evidence-capability asset-led` command. The
printed manifest is a schema-valid, deliberately release-blocked example, not
project evidence; replace it with the exact approved files and provenance.

Close every failure the command reports. Do not treat a selected capability, a
renderer run, or a plan to fill records later as permission to continue. In
particular:

- Standard or stronger work needs its selected `direction.md` complete and
  hash-bound. Any selected exploration, taste-calibration, direction-proof, or
  claims record must also be complete rather than decorative paperwork.
- Asset-led work needs `.design-dna/assets.yml` and at least one usable bound
  asset; “no photos were supplied” is an unresolved dependency, not an art
  direction.
- Direction Challenge must be `reviewed`, with two different roots proven at
  wide and narrow conditions and its broad-implementation boundary explicitly
  opened.
- Applicable Connected Public Experience work must reach `direction-ready`
  with its selected-root continuity, path, handoffs, truth/status model, and
  proof plan resolved. Final rendered and functional evidence remains a later
  requirement.
- Selected Range and Batch records must replace their packaged scaffolds with
  project-specific routes, viewports, and bound source material.

After the real implementation and rendered revision, run `--check-ready` for
the separate final evidence claim. Passing prebuild never supplies an
automatic aesthetic, accessibility, owner-acceptance, production, or release
judgment.

## Use an advanced prompt only when useful

The short command is normally enough. Use this version when you want the
exploration contract in the request. Replace `<INVOKE>` with the invocation for
the one installation you configured:

```text
<INVOKE> Use Showcase to build a time-appropriate website for [business or
product] using only supplied or approved facts and assets. Research the
project, audience, current category context, and useful adjacent creative
evidence at the depth this decision needs. Externalize directly reviewable
contrast sufficient to challenge the first plausible default; build full
alternatives when uncertainty, stakes, or my choice genuinely warrants them,
and do not manufacture a concept quota or merely reskin one composition.
Select the strongest answer with rationale and record its extensible
creative_logic plus consequential observable decisions. Preserve a reversible
checkpoint when useful, prove the decisions most likely to fail before broad
propagation, then implement the real routes and states. Inspect the exact
rendered build across relevant widths, content, inputs, preferences, and
failure conditions. Revise confirmed causes of generic, weak, inaccessible,
or unfinished output, rerun affected checks, and report unperformed checks and
remaining limits.
```

If an existing result feels plain or looks like the same site with different
words and pictures, give that observation directly:

```text
<INVOKE> Use Showcase. Reopen this rendered direction: the result is too plain
and its structure and visual grammar feel reused from another site. Compare
materially different answers grounded in this project's real content and owner
preferences. Revise the underlying creative logic rather than adding detached
effects, preserve truth and working behavior, and show me the exact rerendered
desktop and mobile candidate for review.
```

When that response is an accountable owner's rejection, preserve the exact
rejected public tree and create
`.design-dna/rejections/<REJECTION_ID>.json` from the packaged
`owner-rejection-template.json`. Bind the canonical tree manifest and the
owner's first-party decision evidence, identify the affected relationship
cluster, and list the facts and functions the replacement must protect. Then
run:

```text
<PYTHON> -B "<DESIGN_DNA_SKILL_ROOT>/scripts/owner_rejection_audit.py" "<PROJECT_ROOT>" --contract ".design-dna/rejections/<REJECTION_ID>.json" --stdout
```

Build `candidate.files` with the canonical `sha256-tab-lf-v1` algorithm:
enumerate every regular, non-link file below the rejected public root, record
its POSIX path relative to that root and the SHA-256 of its exact bytes, sort by
path, and SHA-256 the UTF-8 stream of
`<path><TAB><file-sha256><LF>` lines. Store that final digest in
`candidate.manifest_sha256`. The auditor independently recomputes the file set,
file hashes, and manifest digest; a listed-but-changed, missing, extra, linked,
or unsafe file fails closed.

The record is scoped to that exact candidate. It must not convert “these
compressed headings, hard-shadow cards, and photo absence failed here” into a
permanent ban on a typeface category, shape, shadow, media choice, or layout.
An active record keeps the direction reopened; a resolved record requires a
separate hash-bound owner acceptance decision.

## Supply useful material

Give the agent whatever is approved and available:

- audience situations, tasks, and useful outcomes;
- real business, product, service, location, policy, and contact facts;
- brand assets, existing-system authority, and usage rules;
- real copy, imagery, product data, screenshots, research, and cultural
  context;
- required stack, routes, integrations, and delivery state;
- examples of what feels right or wrong, including the reason.

References can come from the project, current peers, adjacent creative fields,
shipped products, physical material, culture, editorial work, owner examples,
or another relevant source. Use the mix and quantity needed to answer the
decision. Record transferable relationships and copying limits; do not average
references into a fashionable template or treat a gallery as usability proof.

In a real project, missing material remains pending, is omitted, or receives
an honestly labeled and owner-authorized concept treatment. Do not invent
proof, reviews, history, prices, availability, people, policies, access, or
integrations and present them as real. An explicitly fictional sample may use
bounded, non-impersonating scenario worldbuilding when its premise and status
remain unmistakable; it still cannot borrow real people, institutions,
credentials, endorsements, or operating behavior to manufacture authority.

For Standard or stronger work, make the material decision explicit in
`direction.md`: whether the subject is physical or sensory, whether the owner
asked for photography or rich media, the selected material posture, what each
medium does, what it must not imply, and what internal rationale or backend
taxonomy must stay off the public surface. A physical/sensory media-light
exception is valid only for a project reason such as truth, rights, privacy,
accessibility, visitor-task fit, documentary ethics, or a real performance
budget, and it needs explicit owner/client approval with an ISO date plus a
hash-bound first-party decision file. It is not a loophole for inconvenient
asset work.

For an asset-led Direction Challenge proof, listing an image in a package is
not enough. The proof record binds the asset and the implementation source, and
the auditor verifies that the source actually references the asset.

## Understand creative proof

Exploration proves a consequential choice; it does not satisfy a concept
quota. Candidates are materially different when they embody different answers
that a reviewer can perceive and decide between. A type-, media-, palette-, or
ornament-led answer may be genuinely different when that medium changes the
experience. Surface replacement inside an unchanged system usually is not.

The proof can be an opening, reading passage, task flow, responsive
transformation, image sequence, interaction, motion study, route body, or
another representative artifact. Use the form and fidelity that can settle the
uncertainty. Keep compared conditions sufficiently controlled for the intended
decision and label anything unrendered or untested honestly.

For a high-visibility or owner-sensitive visual result, include a
first-impression check: does the render feel like a credible public website for
the actual subject and visitor, use material intentionally, and remain
convincing at a narrow condition? Passing a test suite is not an answer to that
question. A direct “ugly” or “bad taste” response reopens the direction rather
than calling for random polish.

Carry the selected result in an extensible `creative_logic` record and an
observable decision ledger. These records describe what this candidate
actually uses; they do not require a hero, signature device, font count,
expression channel, page type, energy arc, or aesthetic risk.

Before broad reuse, deepen the route, fragment, flow, state, or responsive
behavior most likely to expose an expensive mistake. The proof target comes
from project risk, not a fixed “golden” page.

## Ask for evidence

For a substantial build, add:

```text
Bind important visual evidence to the exact candidate/build, route or state,
viewport, content/media identity, and artifact. Compare the implementation
with the accepted observable decisions, inspect the relevant responsive and
state matrix, run the Design DNA source and rendered review when available,
fix confirmed causes, rerun affected checks, and list limitations. Judge
familiar and unusual aesthetic choices in context; no single ingredient is a
genericity or authorship finding.
```

An attractive first screenshot is not completion. The useful result is the
implemented site plus an honest review of the exact build. That project-level
evidence does not establish skill installation, host activation, or package
release status; those require the separate current evidence in the release
procedure.

## Avoid duplicate installations

Use one intended Design DNA route in each host. A personal direct skill and a
packaged plugin must not both be configured for discovery in the same host.
Run the package doctor after installation or update. Its bounded filesystem
scan treats every additional `SKILL.md` candidate as a fail-closed collision
risk; it does not prove plugin activation, project- or administrator-scoped
routes, or current-session visibility.
