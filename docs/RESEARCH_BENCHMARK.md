# Research benchmark

Last reviewed: 2026-08-24

This benchmark records what Design DNA should learn from leading design tools,
skills, and professional workflows. It is not a popularity ranking and no
single source is treated as a complete method. The goal is to combine proven
capabilities without importing another product's house style, stack dependency,
or unsupported marketing claim.

## Evidence labels

- **Official:** first-party product documentation or an official repository.
- **Research:** a published study or research-backed design program.
- **Maintainer:** the creator's own skill documentation; useful for capability
  comparison, but not independent evidence that the capability works.
- **Practitioner signal:** discussion from working designers and developers.
  It can reveal recurring pain, but remains anecdotal.

Claims about quality must still be demonstrated by Design DNA's own controlled
evaluation. A source can justify a workflow candidate; it cannot prove our
implementation.

## Capability benchmark

| Source | Evidence | Strongest transferable capability | Adopt, adapt, or reject |
| --- | --- | --- | --- |
| [Figma design context](https://www.figma.com/resource-library/design-context-ai/), [MCP server](https://developers.figma.com/docs/figma-mcp-server/), and [Code Connect](https://www.figma.com/blog/introducing-code-connect/) | Official | Design intent travels with named components, variables, annotations, and code mappings instead of being reduced to a screenshot or prompt. | **Adopt:** a portable design-context capsule and explicit design-to-code mappings. **Reject:** assuming Figma access or treating raw frame extraction as sufficient context. |
| [Tokens Studio](https://docs.tokens.studio/) | Official | Portable, themeable design decisions can use DTCG-compatible tokens and Git-backed change history. | **Adopt:** ingest existing tokens and preserve their semantic roles. **Adapt:** tokens are evidence of a system, not permission to flatten every expressive decision into a token. |
| [Storybook interaction testing](https://storybook.js.org/docs/writing-tests/interaction-testing) and [Chromatic visual tests](https://www.chromatic.com/docs/visual/) | Official | Components are reviewed in consequential states, and rendered deltas are accepted by a person rather than hidden by snapshot churn. | **Adopt:** a framework-neutral state matrix, reviewer-bound captures, and explicit visual-diff acceptance. **Reject:** requiring Storybook or Chromatic when a lighter native harness proves the same contract. |
| [Material 3 Expressive research](https://design.google/library/expressive-material-design-google-research) | Research / official | Expressive design can improve attention, emotional response, and usability when expression is purposeful and tested. | **Adopt:** project-defined expression evidence governed by audience, task, owner, and context. **Reject:** copying Material's visual language or translating expression into a preset intensity or medium. |
| [Maze prototype-testing guidance](https://maze.co/guides/prototype-testing/) and [Figma AI usability testing](https://www.figma.com/resource-library/ai-usability-testing/) | Official | A concept is tested against measurable user tasks before visual confidence becomes implementation confidence. | **Adopt:** task success, misclick, path, time, and qualitative questions when the project risk warrants user evidence. **Reject:** synthetic prediction as a replacement for relevant human participants. |
| [Mobbin](https://docs.mobbin.com/) and [Mobbin MCP](https://mobbin.com/mcp) | Official | Searchable shipped screens and full flows provide behavior and state references, not only attractive stills. | **Adopt:** use shipped-product references for flow and state questions. **Reject:** cloning a screen, stripping provenance, or treating prevalence as proof of fitness. |
| [Godly](https://godly.design/) | Official product surface | Curated visual examples can supply eligible discovery candidates. | **Adapt:** admit only individually accessible, quality-qualified, exact-brief-fit candidates and decompose their complete relationships. **Reject:** treating gallery inclusion as selection, using it as usability evidence, or averaging fashionable motifs into a generic site. SiteInspire is not in the active registry because the required public evidence path was not currently verifiable. |
| [Impeccable](https://github.com/pbakaus/impeccable) | Maintainer | Durable product/design context, causal tuning passes, deterministic detectors, and one batched desktop/mobile repair loop. | **Adopt:** bounded visual iteration, natural-language tuning intents, and checks for recurring generator habits. **Adapt:** keep one Design DNA router rather than exposing a command swarm. **Reject:** importing its style bans as universal aesthetic law. |
| [SuperDesign](https://github.com/superdesigndev/superdesign-skill) | Maintainer | Multiple visual directions and proof artifacts precede code; existing systems can be extracted rather than overwritten. | **Adopt:** proof-before-build and system ingestion. **Reject:** a required proprietary CLI, unbounded canvas generation, or reference reproduction without rights and transformation controls. |
| [OpenDesign](https://github.com/manalkaff/opendesign) | Maintainer | One router loads focused specialists, scans incumbent systems, and verifies the result against the brief. | **Adopt:** progressive disclosure and brief-bound verification. **Adapt:** specialists remain internal references so Claude and Codex show one skill. |
| [Taste Skill](https://github.com/Leonxlnx/taste-skill) | Maintainer | Brief inference, explicit density/motion/variance controls, asset preflight, and responsive fallbacks. | **Adopt:** causal design dials and asset-first planning. **Reject:** category recipes, preset font menus, mandatory image quotas, fake business data, rigid copy limits, or stack defaults that produce convergence. |
| [Baseline UI](https://github.com/ibelick/ui-skills) | Maintainer | A compact engineering floor covers safe areas, reduced motion, tabular data, primitives, and compositor-friendly animation. | **Adopt:** the durable implementation floor. **Reject:** turning conservative defaults into an expressive ceiling or banning motion, gradients, and letter-spacing by category. |
| [Web Quality Skills](https://github.com/addyosmani/web-quality-skills) | Maintainer / official repository | Performance, accessibility, SEO, and engineering quality remain separately inspectable disciplines. | **Adopt:** specialist boundaries and explicit handoffs. **Reject:** claiming that Lighthouse-style checks prove visual quality, product truth, or usability. |
| [Rive state machines](https://rive.app/docs/editor/state-machine/state-machine), [Lottie production optimization](https://lottiefiles.com/blog/optimize/how-to-optimize-lottie-for-production), and [Spline documentation](https://docs.spline.design/) | Official | Motion assets can expose states and inputs, ship with performance controls, and degrade intentionally. | **Adopt:** a proportional motion-asset contract covering relevant creative or user role, input, lifecycle, fallback, reduced motion, budget, ownership, and provenance. **Reject:** broken agency, inaccessible essential information, unbounded runtime cost, or undocumented failure—not ornament, atmosphere, ceremony, play, or 3D by ingredient. |
| [Stark](https://www.getstark.co/) | Official product surface | Accessibility is integrated across design, code, live review, reporting, and governance. | **Adopt:** accessibility evidence across the lifecycle. **Reject:** treating a tool badge, automated scan, or marketing claim as compliance. |

## Supplied-source audit and runtime mapping

The following resources were supplied during the 6.0 development pass. Each
link was inspected independently; discovery posts and screenshots were never
treated as instructions, licenses, safety evidence, or proof that a method
works. The complete retrieval, pin, license, and rejection record lives in the
maintainer research log and source cards.

| Supplied source | What survived review | Concrete Design DNA result |
| --- | --- | --- |
| [UI/UX Savior discovery post](https://x.com/UiSavior/status/2082144757187301873) | Discovery only; every underlying source required its own authority, license, privacy, and mechanism review. | No social-post recipe entered runtime. The linked resources were decomposed into the rows below. |
| [free-for.dev](https://free-for.dev/) and its [repository](https://github.com/ripienaar/free-for-dev/tree/64022e55b2f633f94f09e42a29f8da7e5738c1b3) | A provider lead, never current provider truth; the repository root inspected at commit `64022e55b2f633f94f09e42a29f8da7e5738c1b3` had no reusable-content license file. | Kept outside runtime. Infrastructure choices require current first-party terms, security, privacy, retention, limits, cost, and owner authorization. |
| [ToolFK](https://www.toolfk.com/tools/online-text-to-video.html), [hunyuanvideo.org](https://www.hunyuanvideo.org/), and [Veo AI Free](https://veoaifree.com/) | No safe default for client work: unclear provenance/handling, unofficial status and unnamed subprocessors, or contradictory account/payment terms. | Rejected as dependencies. Runtime removed volatile free-provider recommendations and routes deliberate video work to current official sources and a fresh rights/privacy review. |
| [Taste Skill](https://github.com/Leonxlnx/taste-skill/tree/72e299530e2eb31ed8da06181bc19f6c18a00821) | Audience inference, incumbent-brand preservation, asset preflight, audit-first redesign, responsive fallbacks, and reference analysis. | Added material/media prebuild authorization and asset-led proof. Rejected fixed dials, stack/font/icon defaults, compulsory themes, hero/eyebrow quotas, mandatory image counts, and punctuation bans. |
| [Vercel web-interface guidelines](https://github.com/vercel-labs/web-interface-guidelines/tree/e3d624baaf29dc1fc645aff3e38f03e564d2d6b1) | Stable semantics, focus, keyboard, form, motion, content, image, and state checks from the pinned primary corpus. | Strengthened the engineering floor and browser review. Rejected mutable runtime fetching and kept Title Case, APCA, URL-state, and latency advice contextual. |
| [Image-to-code skill](https://github.com/Leonxlnx/taste-skill/blob/72e299530e2eb31ed8da06181bc19f6c18a00821/skills/image-to-code-skill/SKILL.md) | An authorized concept image can inform a visual relationship, but cannot become factual, rights, behavior, access, or browser authority. | Deliberately not adopted as a formal proof branch; source facts, code, rights, keyboard/access behavior, and rendered browser evidence remain authoritative. |
| [Awesome DESIGN.md](https://github.com/VoltAgent/awesome-design-md/tree/8147538b4226ae41e2487a9179e3bcc1f68e8554) | Useful project-spec categories when they come from the actual project. | DESIGN.md remains optional and project-derived. Irrelevant sections, borrowed brands, proprietary fonts, trademarks, and trade dress are excluded rather than becoming templates. |
| [Playwright CLI](https://github.com/microsoft/playwright-cli/tree/2f85a94b7b885dbf4a5d34462f253a8746a690c9) | A bounded real-browser workflow with isolated, credential-free profiles and saved evidence. | Retained as an optional browser path beside the bundled schema-3 renderer; it cannot replace the renderer contract or attach untrusted tasks to logged-in sessions. |
| [Google developer documentation style guide](https://developers.google.com/style) | Audience awareness, concrete language, active constructions, second person, global readability, and sentence case. | Added the public-copy firewall and voice-preserving edit pass. Technical-document voice is not imposed on marketing, editorial, cultural, luxury, legal, or brand writing. |
| [dmmulroy/anti-slop](https://github.com/dmmulroy/anti-slop/tree/6d538555cb151d4121ed51a27db81890eacf8ae9) | It is a typed Oxlint plugin, not a visual-design skill. Its useful traits are evidence-preserving types, precise inference, anti-cast laundering, substantive assertions, safe config merge, current version resolution, and anti-gaming tests. | Adapted those integrity mechanisms into validators, evidence contracts, and adversarial tests. Rejected identifier/shape bans and stack-specific global rules as visual doctrine. |
| [Juampi ranking post](https://x.com/juampitech/status/2090834948332655011) and the pinned [stop-slop](https://github.com/hardikpandya/stop-slop/tree/8da1f030185bdfe8471220585162991eaeb970e9), [no-ai-slop](https://github.com/petergyang/no-ai-slop/tree/d30eddb9e04562234f2070b5ee63ca4649d9a05e), [humanizer](https://github.com/blader/humanizer/tree/e2e92e7b4b8229253ed5c8e81dc65463fdeddda5), and [unslop](https://github.com/cursor/plugins/tree/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/unslop) implementations | Voice preservation, no fabricated claims, minimum effective edits, portability checks, and contextual repeated-pattern review. The ranking itself is opinion. | Added contextual public-copy review and construction-language detection without an authorship score. Rejected universal bans on punctuation, adverbs, passive voice, questions, first person, or sentence openings. |

This mapping is intentionally operational: every adopted lesson names the
runtime behavior it changed, and every rejected lesson records why it would
create unsafe dependencies, false authority, or a replacement house style.

## Practitioner signals

Current discussions on
[generic AI sites](https://www.reddit.com/r/webdesign/comments/1t3ymps/so_many_websites_look_the_same_with_ai/),
[repeated fashionable aesthetics](https://www.reddit.com/r/webdesign/comments/1u1579w/so_many_websites_look_like_this_now/),
[business and user context](https://www.reddit.com/r/webdesign/comments/1ugscgt/is_anyone_else_feeling_weird_about_web_design_in/),
and [design-skill overload](https://www.reddit.com/r/ClaudeCode/comments/1usa6fz/im_overwhelmed_by_design_options_skills_plugins/)
repeatedly point to the same practical failures: one-shot generation, weak
imagery, absent user and business context, fashionable motif reuse, and a lack
of deliberate iteration. Hacker News discussions of
[OpenDesign](https://news.ycombinator.com/item?id=47985750) and
[repeated vibe-coded output](https://news.ycombinator.com/item?id=45622944)
similarly favor normal design, component, browser, and staging workflows over a
magic prompt.

These are **practitioner signals**, not measured prevalence or authorship
detectors. Design DNA should use them to propose adversarial cases, then retain
only failures reproduced in its own artifacts. It must never assign an “AI
probability” from cream backgrounds, serif type, gradients, cards, or any other
fashionable feature.

## Design DNA synthesis

### 1. Source-authority contract

The engineering floor prevents breakage; it is not authority for a visual
idea. Translate requested qualities into exact-fit source-selection criteria
based on audience, task or invitation, owner requirement, culture, content,
and context. A directional word helps qualify references; it never authorizes
the producer to choose a medium or visual treatment.

Record the candidate's exact selected-source/state/component transfer map and
consequential observable decisions. Expression
may come from any medium, several local systems, convention, ornament,
atmosphere, precision, abundance, or restraint only when the current brief,
supplied work, established system, or selected measured references supply it.
Judge the rendered whole against those sources rather than named devices or
feature counts; there is no producer-open aesthetic lane.

### 2. Design-context capsule

Before direction generation, retain a compact, source-dated capsule containing:

- user, job, environment, and emotional state;
- business and product truth, including unknowns and prohibited claims;
- approved brand system, tokens, components, assets, and content;
- platform, stack, browser, performance, and delivery constraints;
- interaction intent and consequential states;
- reference roles, likes, anti-references, and rights;
- incumbent visual truth for an existing product;
- assumptions, design debt, owners, and review dates.

The capsule is durable project context, not a universal taste profile. Owner
feedback overrides inferred preferences, and sensitive material is minimized.

### 3. Existing-system ingestion

Greenfield and existing products require different first moves.

- **Existing:** inventory tokens, primitives, components, variants, routes,
  states, content, and exceptions; map design concepts to real code; preserve
  incumbent truth unless replacement is authorized.
- **Greenfield:** establish context and source material before selecting a seed
  system; do not substitute a category recipe for discovery.

The output of ingestion is a map of reuse, extension, replacement, and unknowns.
Filename or folder names never establish visual authority by themselves.

### 4. Proof-to-build delta

A visual proof can still collapse into a generic build. Carry the exact
selected-source/state/component mappings and observable decisions into a transfer ledger. Record the
proof evidence, accepted decision, scope, implementation source, relevant
adaptation, intentional deviation, and rendered comparison at the conditions
that matter.

The ledger has an exact source/state/component core; add only applicable
evidence conditions, never a producer-authored visual field. Review the
**delta**, not merely whether the build resembles a screenshot. If an accepted
decision or visitor outcome disappears without disposition, fidelity has
failed even when surface ingredients match.

### 5. Perception-first critique

Begin with an unprimed encounter with the rendered artifact, then choose the
perception, craft, task, content, state, responsive, accessibility,
performance, or implementation lenses the project needs. Inspect source after
the observation to explain causes. Consult recurring-pattern vocabulary only
after the candidate has been experienced on its own terms.

No universal critique sequence or aesthetic score applies. A scanner can
locate candidates; it cannot decide that a design is generic, beautiful,
authored by AI, or acceptable to the owner.

### 6. State matrix

For each consequential component and flow, enumerate the applicable
intersection of:

- default, hover, focus, active, selected, disabled, loading, success, empty,
  error, partial, stale, offline, and recovery;
- compact, mobile, intermediate, desktop, short-height, zoom, and long content;
- keyboard, touch, pointer, screen reader, and programmatic input;
- reduced motion, forced colors, contrast/theme preferences, and localization.

Not every cell requires a screenshot. Every applicable cell requires an
intentional outcome, and high-risk or visually consequential cells require
reviewer-bound rendered evidence.

### 7. Motion-asset contract

Rive, Lottie, video, canvas, WebGL, and 3D are media and implementation options.
They may serve task feedback, narrative, atmosphere, identity, ceremony, play,
ornament, or another project-supported creative role. Record the trigger,
states, interruption, lifecycle, reduced or unsupported result, loading,
performance, ownership, rights, and provenance only where material to the
asset. Essential reading, control, and task completion remain available under
the declared access and failure contract; that boundary does not create an
aesthetic ban or require the strongest medium to survive deletion unchanged.

### 8. Decision-relevant reference evidence

Give each reference the relevance the current decision needs. It may inform
behavior, art direction, brand, subject, culture, physical material, content,
system, quality, counterevidence, or another project-specific concern. A source
may have several clearly separated uses or none after review.

Do not require a fixed role taxonomy or source count. Record the relationship
being learned, source and retrieval date, authority and rights limits, what
must not be copied, and how the lesson changes for this project. Do not average
references or use aesthetic popularity as usability evidence.

## Decisions for the skill

Design DNA should:

- remain one visible Claude/Codex skill with routed internal references;
- use a durable context capsule and incumbent-system map;
- generate enough materially different, directly reviewable evidence to expose
  consequential uncertainty before expensive implementation;
- bind the selected proof to the build through a transfer ledger;
- interpret directional feedback causally without mapping it to a fixed menu
  of levers or effects;
- batch related review and repair when that improves attribution, then rerun
  the conditions affected by the change;
- maintain a framework-neutral state matrix and reviewer-bound visual evidence;
- keep media, motion, accessibility, performance, and truth as explicit
  contracts;
- test for its own recurring visual habits across an authorized evaluation
  corpus, not merely for another model's habits.

Design DNA should not:

- promise human authorship, “undetectable AI,” universal taste, or perfection;
- encode a replacement house style, category aesthetic, font menu, stack, or
  component library;
- create fake people, metrics, testimonials, addresses, availability, or other
  business facts to make a mockup look complete;
- count images, animations, gradients, cards, or novelty effects as quality;
- run endless autonomous polish loops after evidence has stopped changing;
- mistake automated checks, community consensus, or a celebrated reference for
  target-user validation.

## Benchmark acceptance

An adopted capability is complete only when it has:

1. a routed instruction or artifact contract;
2. a positive and adversarial behavioral evaluation;
3. a rendered test where visual behavior matters;
4. a truthful failure state when required evidence is absent;
5. no new required host, paid service, stack, or network dependency unless that
   dependency is explicitly scoped and optional.

Revisit this benchmark when source behavior changes, controlled evaluations
expose a new Design DNA house style, or owner feedback reveals that the process
still produces work that is plain, dated, incoherent, or generic.
