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

Design DNA chooses a proportional assurance profile from the task. You do not
need to describe its internal method. For a portfolio piece, client sample,
pitch, demo, or other high-visibility work, request Showcase explicitly:

```text
$design-dna Use Showcase to build an exceptional, time-appropriate sample website for [business or product] using the supplied facts and assets.
```

Use `/design-dna` instead of `$design-dna` for a direct Claude Code skill. If
you deliberately installed the packaged Claude Code plugin, its namespaced
command is `/design-dna:design-dna`. Configure only one discovery route per
host.

Relevant natural-language requests are intended to activate the skill, but
automatic loading is host- and version-dependent until observed in that
environment. Explicit invocation is the deterministic choice when Design DNA
is required.

## Choose assurance capabilities

| Capability | Choose it when | What it adds |
| --- | --- | --- |
| **Quick** | A bounded, low-risk repair or established-system change. | Focused context inspection, changed-state implementation, and affected checks. |
| **Standard** | A new route, meaningful feature, or ordinary redesign. | Direction framing, proportionate proof of consequential decisions, rendered review, and engineering verification. |
| **Showcase** | Expressive, premium, highly visible, owner-sensitive work or a brief that rejects safe or generic output. | Project research, enough directly reviewable alternatives to challenge the first default, a recorded selection, deeper visual craft, and adversarial review. |
| **Range Study** | A real multi-route site must demonstrate meaningful creative range. | Dependable truth, navigation, accessibility, and operations; an explicit route-family record; route proof chosen by uncertainty; real-path checks; and a matched route atlas. |
| **High-risk** | Identity, permissions, private data, money, regulated claims, consequential transactions, or difficult recovery. | Stronger task, state, content, specialist, recovery, and real-user evidence. |
| **Asset-led** | Material imagery, video, audio, fonts, documents, maps, embeds, or generated media needs a durable record. | Type-specific provenance, rights, privacy, factual, approval, delivery, accessibility, and generated-media gates. |

Quick and Standard are proportional base presets. Showcase, Range Study,
High-risk, and Asset-led can apply together. Adding a capability cannot
silently remove a stronger one.

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

## Use an advanced prompt only when useful

The short command is normally enough. Use this version when you want the
exploration contract in the request. Replace `<INVOKE>` with the invocation for
the one installation you configured:

```text
<INVOKE> Use Showcase to build a time-appropriate website for [business or
product] using only supplied or approved facts and assets. Research the
project, audience, current category context, and useful adjacent creative
evidence at the depth this decision needs. Develop enough materially different,
directly reviewable answers to challenge the first plausible default; do not
manufacture a fixed number of concepts or merely reskin one composition.
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

Missing material remains pending, is omitted, or receives an honestly labeled
and owner-authorized concept treatment. Do not invent proof, reviews, history,
prices, availability, people, policies, access, or integrations.

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
implemented site plus an honest review of the exact build.

## Avoid duplicate installations

Use one intended Design DNA route in each host. A personal direct skill and a
packaged plugin must not both be configured for discovery in the same host.
Run the package doctor after installation or update. Its bounded filesystem
scan treats every additional `SKILL.md` candidate as a fail-closed collision
risk; it does not prove plugin activation, project- or administrator-scoped
routes, or current-session visibility.
