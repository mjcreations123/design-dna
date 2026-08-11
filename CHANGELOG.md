# Changelog

All notable changes to Design DNA are recorded here. Versions follow semantic
versioning for the portable skill contract; maintainer evidence and dated
convergence watches may receive review-only updates without changing runtime
behavior.

## 5.1.0 - Creative freedom and batch proof

This release repairs the restrictive aesthetic doctrine introduced during the
5.0 line and adds a controlled way to test whether Design DNA actually
transfers across unrelated projects. It keeps strict truth, rights, privacy,
accessibility, working-behavior, evidence, and delivery boundaries while
returning typography, copy, composition, media, color, motion, ornament, and
other aesthetic decisions to project evidence and rendered judgment.

### Changed

- Replaced the universal ABSOLUTE/HARD taste rulebook with assurance
  boundaries. Familiar or unusual fonts, gradients, cards, status styling,
  punctuation, system type, media choices, copy registers, and layout devices
  can all be correct when their meaning, project fit, and execution hold.
- Rebuilt typography around reading conditions, role relationships, language,
  spacing, delivery, fallback, and actual painted-font evidence. There is no
  portable "AI font" list, preferred family bench, rotation rule, fixed
  pairing count, mandated hosting method, or universal scale.
- Reworked convergence, specificity, parseable text, microcopy, dark-mode,
  email, exploration, energy, ledger, workflow, and preship guidance so
  post-render observations cannot harden into a reverse style guide or house
  voice.
- Made cross-project history opt-in, minimized, host-neutral, and
  owner-authorized. An existing ledger is not standing permission to inspect
  unrelated client history.

### Added

- `taste-calibration.md` and an optional project-local calibration record for
  high-visibility, owner-sensitive, open, or previously rejected directions.
  They use source-aware visual references, a rendered direction proof, and a
  first-impression surface-fidelity review without imposing a global font,
  palette, layout, media, or motion recipe.
- A Batch Study protocol for three or more independently briefed sites, with a
  project-local contract, schema, audit tool, neutral-label identity-blinded
  comparison, exact evidence hashes, isolated build roots, route/capture
  coverage, and optional atlas. Pixel transformation is optional and requires
  a justified hypothesis or authorized privacy need, original and transformed
  hashes, a recorded method, and an explicit coverage-impact statement.
  The result reports coverage and contextual findings; it never produces an
  authorship or aesthetic score.
- A launch-completeness contract for every new or materially redesigned
  website, covering the primary action, decision-blocking questions, response
  or delivery expectation, success state, compact-screen action, crawl and
  indexing policy, page descriptions and titles, sharing card, location and
  directions, text alternatives, privacy and policy boundary, analytics
  authorization, decision cue, and approved promotion. Each is recorded as
  included, not applicable, or blocked in a project-local record, and none may
  be satisfied by inventing an address, promise, policy, tracking ID, or offer.
  A companion section names the reflex implementation that turns several of
  these decisions into interchangeable furniture, so the item gets answered
  without a default component being installed to answer it.
- Regression contracts that reject renewed font/style whitelists, aesthetic
  absolutes, hidden worktree byte drift, untracked empty-directory identity,
  unsafe evidence URL queries, and unrelated malformed-skill discovery
  failures.

### Fixed

- A clean technical build can no longer be treated as evidence that a website
  is aesthetically convincing or client-ready. Direct feedback that a result is
  ugly, artificial, generic, or maker-facing now reopens the public proposition
  and creative logic rather than inviting only cosmetic polishing. Batch Study
  fixtures are explicitly not portfolio proof.
- GitHub Actions no longer uses the unavailable job-level `runner.temp`
  context, allowing the matrix to start rather than fail before creating a
  job.
- Windows evaluation timeouts use a kill-on-close Job Object and verified
  process-tree termination, with a measured fail-closed fallback.
- Release packaging now rejects line-ending/filter drift hidden by Git status,
  and distribution identity no longer binds empty directories that a clean
  clone cannot reproduce.
- The installer no longer mistakes an unrelated malformed skill for Design
  DNA merely because its body says the skills can be paired.
- Online evidence validation safely admits only the canonical single-video
  YouTube query shape, follows the current GOV.UK source, and removes the stale
  Spotify Design card after that publisher retired the cited site.

## 5.0.4 - Four missing surfaces

A coverage audit over the whole reference tree, prompted by the owner asking
what the skill still could not do. Most suspected gaps turned out to exist
under different vocabulary; four were genuinely absent. Each new file is
routed, so it loads when the decision arrives rather than sitting unreachable.

### Added

- `references/flows/conversational-interfaces.md`: the chat, assistant, and
  generated-answer surface. The streaming contract as a set of real states
  (idle, submitted, streaming, stopped, complete, and six distinguishable
  failure modes) rather than an effect; honest rendering of model output,
  including wide tables and code inside narrow containers and never treating
  model markup as live HTML; provenance and correction paths; the composer;
  metering and context limits. Named bans cover simulated typing on canned
  content, artificial delay before an instant answer, fabricated confidence
  scores, citation chrome with no retrieved source, and invented personas.
  Streaming text is the hardest case for assistive technology, so the verify
  section requires a real screen-reader pass rather than an assumption.
- `references/craft/theming-dark-mode.md`: a second colour scheme as a second
  design, not a filter. When to ship one at all, and the derivation rules that
  inversion gets wrong: no pure black, no full-strength white body text,
  accents that need retuning per scheme, elevation logic that reverses, and
  per-scheme ink variants because a value that clears 4.5:1 on paper commonly
  fails on dark. Imagery and logos need per-asset decisions rather than a
  blanket CSS invert. The preference contract has three states (system, light,
  dark), not two. Both schemes are separate deliverables under ABSOLUTE 11.
- `references/craft/email-design.md`: email as its own medium. The structural
  floor (tables, inline styles, backgrounds on cells, no flexbox or grid in
  the installed base), designing for blocked images so alt text is visible
  design, mail-client dark-mode inversion, fallback type as the real
  typography, and the parts nobody designs: subject, preheader, sender name,
  plain-text alternative, footer. Verification requires captures from real
  mail clients, since a browser does not render this medium.
- `references/craft/microcopy.md`: the generative counterpart to
  parseable-text.md, which only removes strings. Outcome-not-mechanism
  naming; the three parts of an error message and the ban on leaking
  internals as body copy (ABSOLUTE 10); empty states as four distinct states
  that are routinely written as one, including the failed-to-load case whose
  "No items yet" copy is a lie the reader acts on; destructive confirmation;
  why a placeholder is not a label; and translation expansion.

## 5.0.3 - Second-build hardening

Learned from a build outside the studio: a friend of the owner tried the
skill and reported two things back, both traceable to one root cause. The
content that would have stopped them already existed, three files deep in
post-render review vocabulary, and never surfaced pre-render where it would
have prevented the build rather than caught it afterward.

### Added

- `policy/absolutes.md`: **ABSOLUTE 10, NEVER show system, connection, or
  build status to a visitor.** A green dot, an "Online"/"Connected"/
  "Synced"/"Live" badge, an environment name, a build or version string, a
  component or variable name: none of it is the visitor's business,
  fabricated or genuinely true, on any page type, not only product or
  dashboard UI. This is the pre-render half of the fix: it is now read
  before any design work begins, not discovered only at the post-render
  parseable-text pass. Existing absolutes 10 and 11 renumber to 11 and 12.
- `templates/preship-gate.md` gains a matching P0 line: grep the rendered
  DOM for status words and for any bare colour-dot element, since a status
  dot is a shape, not a string, and no text grep catches it alone.
- `references/quality/parseable-text.md` strengthens the existing "fake
  liveness" entry (it already banned fabricated status dots) to name the
  identical failure when the status is real, cross-referenced to the new
  absolute, and adds "operational state" as a named illegitimate string
  class alongside decorative props and internal residue.
- The router row for parseable-text.md gains explicit trigger words
  (status/connection/live indicator, implementation or system detail) so a
  build carrying this symptom actually routes to the file that names it,
  rather than depending on "decorative labels, HUD text" reading as a match.

## 5.0.2 - First-build hardening

Learned from the skill's first live test (a one-page demo shop built,
adversarially reviewed, and revised in one session).

### Added

- `references/quality/render-harness.md`: capture and measurement methods
  that survived real failures: full-page capture via layout-metrics clip
  (never viewport resize, which re-flows vh layout and truncates), probe
  sequencing (probes run at the LAST navigation's viewport), element-
  anchored sampling, the two-capture hidden-text contrast method (defeats
  glyph and antialiasing contamination), and fallback rehearsal via
  Network.setBlockedURLs. Router row added.
- Imagery: the archetype trap (a generator draws the statistical archetype
  of a subject's NAME, not the subject described) with the mandatory
  subject-accuracy check, and the prior-fighting rule (one retry, then own
  the element in copy; set consistency beats single-image purity).
  RISK-IMGSET-001 updated to match.
- Typography synthesis proof: a reference implementation snippet for
  descriptor-range coverage, so the check gets run instead of approximated.
- Harness laws from three further builds: never double-run an interaction
  (act in the navigation step, read in the probe, never both, or the second
  run reports the toggled-back state), capture the exception rather than the
  symptom, and the duplicate-variable-font trap where several weight-named
  files are one variable face fetched repeatedly.
- The vh full-page capture trap: `captureBeyondViewport` never converges on
  a vh-driven layout, because the surface grows to the content height, the
  vh sections grow with it, and the measurement chases itself. Capture
  viewport slices at known offsets, and set `scrollBehavior = "auto"` first
  or smooth scrolling silently returns the previous position and every slice
  comes back identical.
- Range-anchored contrast measurement: sample the glyph boxes from
  `range.getClientRects()`, not the element box. A block-level heading spans
  its whole column while its words cover a fraction of it, so element-box
  sampling reports the darkest pixel of empty background and invents
  failures that are not there.

### Fixed

- The paint-proof coincidence: two faces can measure identically and still
  both be fallbacks, so the proof now requires a positive identification
  rather than a difference.
- Lazy images never load during a full-page capture, so the capture step
  now forces them before measuring.
- Copy voice gains a fingerprint axis, since repeated sentence shapes across
  projects are a house tell in the same way a repeated palette is.

### Package

- `references/evidence.md` is reachable. It had no inbound link and no
  router row, which the package audit reported as
  `runtime-reference-unreachable`; it governs how risk rules are promoted
  and retired, so it is now routed from the decision table.
- Runtime prose is wrapped to the 80-column house convention. Roughly a
  third of the files had drifted wider, which turned small edits into
  whole-paragraph diffs. Markdown links are treated as atomic, because the
  wide lines were wide precisely to keep `[text](target)` unbroken.
- Contents maps added where the package's own 100-line rule requires them.
- Package identity is one version across the runtime, both host plugin
  manifests, and the compatibility matrix. The SBOM and release manifest are
  regenerated from that identity rather than asserted.

## 5.0.1 - Working-artifact hygiene

The owner saw in-progress direction proofs in a watched preview pane and
judged them as the site. New invariant and workflow rules: internal renders
live under .design-dna/proofs/ with visible INTERNAL banners, specimen
strips never share a page with a composition, placeholder media areas are
flat labeled frames (never gradient fills), and watched previews are
pointed at the most finished state before any turn ends. Parseable-text
gains the studio's own process language as an internal-residue class;
preship gate gains the no-reachable-working-artifact line.

## 5.0.0 - The merge

Merges three generations into one skill: the 4.0.0 candidate's architecture
(authority order, capability presets, decision router, flows, verticals,
cultural review, scripts), the 3.4.0 dated risk vocabulary (restored and
refreshed as expiring post-render tables, including the dated-signal watch
for the opposite "looks like 2004" failure), and the original owner doctrine
that 2.x removed. Grounded in a 9-agent research sweep (typography craft,
font-slop discourse, font-loading engineering, stray-text tells, YouTube
transcript mining, instruction-following research) and a failure-corpus
audit of this studio's real builds and rejections.

### Added

- `policy/absolutes.md`: the restored two-tier owner policy. ABSOLUTE (never
  lifted): em dashes, count-ups, fabricated proof, the indigo-violet
  gradient kit, fake product UI, the default skeleton, contrast floors, the
  silent-font-fallback ban, the parseable-string ban, the screenshot ship
  gate, demo-by-default. HARD (client-liftable, logged): watch-cluster
  faces on greenfield identity, single-word emphasis swaps, eyebrow
  repetition, third families, emoji-as-interface, mono-as-dressing,
  ordinals on parallel items. Includes the two-lane rule: absolutes act
  pre-render; everything else stays post-render diagnostic.
- `references/quality/parseable-text.md`: the four-question gate (meaning,
  truth, audience, deletion cost) for every visible string, the five string
  classes, named bans from the studio's own rejections, and mechanical
  residue greps (placeholder vocabulary, binding leaks, mojibake, em dash).
- `references/quality/ledger.md` + `templates/ledger-template.md`: the
  studio ledger at `~/.claude/design-dna/LEDGER.md`, consulted before
  directing, appended on ship, with the two-part rotation test; standing
  owner authorization for cross-project comparison.
- `templates/preship-gate.md`: the one-page runnable P0/P1/P2 gate that
  operationalizes every absolute plus the font, text, screenshot, ledger,
  and demo-state checks.
- `templates/placeholder-register-template.md`: tracked stand-ins with the
  must-be-empty-before-live rule.
- Typography: the mandatory 8-step rendered-font verification (registration,
  paint, synthesis, network, console, computed-size, fallback rehearsal,
  look), built on the documented failure modes of document.fonts.check and
  computed styles; the numeric floors table; the pairing procedure; the
  dated bench with burned-list; the inks-versus-graphics token split with
  pixel-sampled scrims; self-hosting law; motion and masking laws from the
  studio's own defect record.
- Risk rubric: RISK-PLAIN-001 (human-crafted but plain still fails),
  RISK-PARSE-001 (unparseable strings), RISK-FONTPAINT-001 (declared face
  is not the painted face).
- Convergence watch: dated 2026-08 cluster tables restored (treatment kit,
  glow, emphasis swaps, stats bands, HUD pseudo-data, the two font clusters
  with decay clocks), the dated-signal RISK-PERIOD table, the
  self-fingerprint section, and the "avoidance converges too" guard.

### Changed

- SKILL.md restructured for instruction-following: absolutes on the first
  screen, the gate restated at the end, unhedged imperatives, every ban
  paired with its replacement.
- Creative freedom keeps its no-global-blacklist stance with one carve-out:
  the owner absolutes are active Inherited constraints at tier 2, plus the
  two-axis (AI-looking/human-crafted and plain/rich) review model.
- Creative exploration gains the fixed first-instinct floor: greenfield,
  Showcase, and open-direction work never ships the first-ranked concept
  without one materially different rendered alternative.
- Workflow: demo-by-default and the placeholder register at preflight,
  ledger consult at direction, three mandatory verification passes (see it,
  prove the fonts painted, parse every string), the preship gate and ledger
  append at delivery.
- Specificity review: the ledger replaces "cross-project repetition not
  assessed" as the comparison baseline; the parseable-text gate joins the
  copy audit as P0.
- owner-defaults.yml: new require dispositions for absolutes, screenshot
  gate, font verification, parseable text, demo-by-default, ledger, and the
  preship gate.

### Added from the detection research sweep

A second 9-agent research pass over the owner-supplied source list (YouTube
detection and critique content, Framer/Lovable/Bolt/v0/Durable/Wix/10Web
builder output, Wappalyzer/BuiltWith/isitvibecoded detection tools, AI-copy
detection, Reddit and HN discourse, GitHub detectors, academic detection
papers, and an AI-versus-award-tier dataset comparison) produced:

- Four new dated watch clusters: RISK-SUBSTRATE-001 (the shadcn/v0/Bolt
  substrate and its reskinnability test), RISK-FORMULA-001 (the
  small-business builder formula), RISK-REVEAL-001 (uniform scroll-reveal
  motion), RISK-IMGSET-001 (the generated-image tell set).
- The builder-fingerprint hygiene sweep: technical signals detection tools
  use (generator tags, builder hosts and attributes, stock tokens, scaffold
  residue, bundle comments), so hand-built work never carries false builder
  signals; wired into the preship gate.
- The dated AI-phrase grep list and paste-artifact sweep in parseable-text,
  plus positive copy doctrine (checkable specifics, one side per page,
  sentence-shape variety, FAQ facts, verbatim quotes).
- Human-creativity indicators in the specificity review: the authorship
  properties generated output does not exhibit, as review questions.

### Removed

- `scripts/__pycache__/` build residue.

## 4.0.0 - Unreleased candidate

This candidate adds a bounded Range Study capability and cultural-context
release contract. The entries describe the intended portable runtime and
maintainer interfaces; final qualification still depends on current tests,
host installation evidence, rendered forward tests, and human review.

This is a breaking creative-freedom release. It removes the former
type-convergence policy, fixed visual-direction slots, fixed candidate/proof
counts, route archetype recipes, and ingredient-level AI-tell heuristics.
Projects must derive their aesthetic decisions from their own evidence and
rendered result; strictness remains for truth, rights, privacy, accessibility,
working behavior, cultural authority, and honest verification.

### Changed

- Expanded the cumulative assurance model with Range Study for multi-route
  briefs that explicitly require meaningful creative range among real routes.
- Replaced "make every page different" as an unbounded styling instruction with
  a shared-foundation contract: truth, navigation semantics, accessibility,
  identity, performance, and operations remain dependable while route bodies
  own their content-derived compositions and justified one-offs.
- Established a creative-freedom boundary: truth, rights, privacy,
  accessibility, working behavior, and explicit project authority remain
  evidence-bound while typography, palette, composition, media, ornament,
  interaction, motion, page form, concept count, and other aesthetic choices
  stay open unless project evidence closes them.
- Replaced fixed direction counts, proof counts, route archetypes, expression
  channels, signature devices, and energy recipes with extensible
  `creative_logic`, observable design decisions, exploration proportional to
  uncertainty, and post-render aggregate convergence review.
- Replaced unconditional “contemporary” discovery copy with time-appropriate,
  project-derived time-register language so historically referential work
  remains valid when the brief supports it.
- Made direct entry, reload, stable path identity, history, current-page state,
  canonical/indexing intent, and not-found behavior part of the route-family
  definition. Hash sections, query variants, aliases, and redirects do not
  count as additional pages.
- Strengthened motion guidance for scroll stories and same-origin
  cross-document transitions with complete static, no-JavaScript,
  unsupported-runtime, reduced-motion, interruption, and history outcomes. The
  contract prohibits global smooth scrolling and scrolljacking.
- Added Hebrew and mixed-direction type proof for language, direction,
  punctuation, glyph coverage, shaping, copy/paste, keyboard, screen-reader,
  and narrow-screen behavior.

### Added

- `references/craft/route-family-art-direction.md`, defining shared
  foundations, route-local creative logic, justified one-offs, risk-selected
  proof, real route identity, responsive transformation, and matched
  route-atlas review.
- `templates/route-family-template.json`, the portable
  `.design-dna/route-family.json` contract for shared rules, route-specific
  design decisions, capture requirements, review state, and cultural
  acceptance.
- `references/quality/cultural-context-review.md`, separating source review,
  language review, producer inspection, owner authority, and independent
  cultural acceptance. A producing agent cannot self-certify acceptance or
  waive it on the owner's behalf.
- `references/verticals/place-community-publication.md`, covering publishing
  stance, current versus historical source handling, plural place
  representation, authentic media, visitor utility, and time-sensitive links.
- `scripts/route_family_audit.py`, a fail-closed structural auditor for
  declared paths, direct documents, redirects, local links, orphans, matched
  capture coverage, repeated main-content silhouettes, and a dependency-free
  HTML route atlas. It reports grouped evidence without an authorship or
  aesthetic score.
- A standalone rendered-comparison path whose input schema and operating guide
  live inside the portable skill tree, plus an isolated-tree real-browser
  regression that proves no maintainer checkout is required.
- Direction and visual-review fields for route-family identity, observable
  route decisions, direct-entry results, matched route atlases, repeated
  structural clusters, terminology, representation, reviewer authority, exact
  cultural-review scope, and re-review triggers.
- Permanent positive and adversarial fixtures for a ten-route anthology,
  recolored duplicate skeletons, hash-navigation impostors, broken and
  orphaned routes, stable navigation with different bodies, mixed
  Hebrew/English directionality, and missing cultural authority, plus a real
  browser regression that captures ten routes at matched 1440px and 390px
  viewports.
- Schema-2 migrations and regression coverage for every active route-family
  fixture, including an intentional contract-invalid hash case and protection
  against retired fixed route fields becoming either recipes or vocabulary
  blacklists.
- A schema-3 rendered-review contract that records normalized geometry,
  layout topology, media/control density, and computed typography evidence
  while keeping font names, palette, copy, and image identity out of cosmetic
  reskin similarity decisions.
- A required hash-bound masked-layout comparison for controlled evaluation,
  with copy, logos, and dominant media removed or neutralized before reviewers
  assess same-system convergence.
- Current evidence cards and sampled YouTube-frame research showing that
  authorship cannot be inferred from a single font or motif; the actionable
  risk is a cluster of unearned defaults, interchangeable structure, weak
  content judgment, broken behavior, and skipped rendered QA.

### Release boundaries

- Automated route and silhouette analysis remains bounded implementation
  evidence. It does not score authorship, taste, cultural correctness, or
  human-made appearance.
- Culturally central public work remains blocked while required cultural
  acceptance is pending or rejected. Prior-version approval, automated checks,
  and producer self-review cannot close that gate.

## 3.5.0 - Superseded unreleased candidate

The Range Study and cultural-context work began under this candidate number.
It was never promoted. The completed contract, including the breaking
creative-freedom and rendered-evidence changes, is carried forward as 4.0.0.

## 3.4.0 - Unreleased candidate

This candidate records implemented workflow and package changes. Formal host,
comparative, independent rendered-review, and strict release qualification are
still pending; the entries below are not claims of a qualified outcome.

### Changed

- Rebalanced the skill from defensive anti-pattern avoidance toward
  constructive, contemporary art direction with controlled visual energy,
  emotional intent, attention design, and one bounded aesthetic risk.
- Made open, expressive, rejected, and showcase work explore visibly before
  convergence: three independently developed hypotheses and at least two
  like-for-like rendered proof slices are the normal expectation, while the
  gate judges meaningful directional coverage rather than a numeric quota.
- Added proportional Quick, Standard, Showcase, and High-risk assurance
  profiles. Showcase is the recommended path for portfolio, demo, pitch,
  sample, and other high-visibility work.
- Strengthened direction, proof, and review records so hero intent, system
  mapping, accepted-baseline drift, care, and visual regression evidence
  cannot disappear behind a passing scanner.
- Expanded the workflow from source and content structure through rendered
  direction selection, a reversible checkpoint, one deeply reviewed golden
  route or flow, bounded iteration, propagation, and production handoff.

### Added

- A complete creative-exploration method and durable exploration record with a
  mixed reference dossier, subject-world extraction, divergent concept cards,
  directly accessible visual comparison, selection rationale, and golden-route
  contract.
- Positive voice, terminology, representative-state copy, measurable outcomes,
  lightweight validation, and post-launch learning ownership.
- Proportional token, component, design-to-code mapping, lifecycle, parity,
  regression, and handoff requirements.
- Dedicated guidance for complex transactions, service-journey handoffs,
  consent and permissions, adaptive scaffolds, broader exclusion mapping, and
  lower-impact lifecycle choices.
- Evidence-backed exploration, regression, voice, and complex-form records,
  plus an expressive stateful-product behavioral case.
- Constructive design-tuning passes, brand-system extraction, editorial art
  direction, proof-to-build fidelity, expert critique, design-partner cadence,
  and conditional adapters for existing Figma, Storybook, token, motion, 3D,
  and visual-regression tools.
- Project-local templates for expressive perception, proof/build deltas,
  design-context capsules, runtime motion assets, executable state matrices,
  and complex service blueprints.
- A fail-closed, offline cross-build rendered comparator that validates both
  evidence packages, produces baseline/candidate/pixel-diff triplets, records
  factual mismatch counts, and always requires a separate human decision.
- A stronger media strategy for physical and sensory subjects, comfortable
  typography checks, exact font provenance, decorative split-color headline
  review, and a dated informational type-convergence watch rather than a font
  blacklist.

### Implemented safeguards

- Implemented a workflow intended to address polished-but-plain samples by
  requiring visible directional divergence, a first-view design thesis,
  deliberate high/quiet pacing, meaningful media roles, and character checks
  that remove the dominant photo or loudest surface device in turn. Its effect
  remains subject to formal qualification.
- Tightened completed-record validation so selected-direction parity,
  attention, aesthetic-risk fallback, system mapping, baseline drift, care,
  and regression evidence are substantive rather than optional notes.
- Removed generic-hover false positives for underline `scaleX`, directional
  link motion, axis-only scale, and unrelated rotation while preserving
  repeated lift, uniform scale, shadow, glow, and utility-pattern detection.
- Added a restrictive CSP and hostile-label escaping regression to rendered
  contact sheets.
- Added optional hash-bound comparison-report validation to project visual
  review records without turning a machine diff into acceptance.

## 3.3.0 - 2026-07-29

### Changed

- Made requested visual ambition an enforceable project contract instead of
  optional prose. Expressive briefs now require observable energy, an explicit
  under-design failure, a project-specific signature carried across multiple
  design channels, and deliberate contrast between focal and quiet sections.
- Added a constructive expression-and-energy method for generating materially
  different directions, mapping route intensity, encoding the result as a
  system, adapting it responsively, and testing it without its dominant photo,
  accent color, motion, or loud surface recipe.
- Distinguished visual depth from surface-only volume so saturated rectangles,
  giant sans-serif type, tickers, and offset cards cannot substitute for a
  project-specific premise.
- Reclassified accountable-owner feedback such as plain, boring,
  under-designed, too safe, or lacking pizzazz as direction evidence that
  reopens the candidate rather than a request for decorative effects.
- Strengthened the Coffee and Relay Room behavioral cases and the blinded
  review rubric so a neutral gallery, repeated card stack, or polished safe
  minimum cannot receive top marks on an expressive brief.

### Added

- `RISK-AMBITION-001`, bound to an owner-policy default and checked across the
  publisher policy, opt-in policy template, schema, scanner, evidence registry,
  project-state records, behavioral fixtures, and regression tests.
- Runtime-router reachability validation so every reference remains directly
  discoverable from `SKILL.md` without multi-hop instruction loading.
- Draft owner-policy template validation against the active schema after safe
  in-memory placeholder substitution.
- Required direction research disclosure plus motion and performance sections
  in completion validation; omitted evidence can no longer pass as complete.

### Fixed

- Reconciled the source package with previously installed visual-ambition
  guidance and removed the source/install version split.
- Updated Claude Code package validation guidance to the current strict command
  and documented development-plugin reload behavior.
- Made entrance effects fail open, added a scanner advisory for content hidden
  behind unconfirmed reveal states, and required longest-content review at
  320, 375, and 430 CSS-pixel widths.

## 3.1.0 - 2026-07-29

### Changed

- Made five-second public comprehension, a deliberate sensory-media strategy,
  comfortable typography, and customer-facing copy hard review requirements
  for substantial local-business and experience-led website work.
- Replaced universal anti-pattern avoidance with positive guidance for
  photo-led, text-led, and mixed art direction, including owner-authorized
  generated concept photography with distinct atmosphere, human-use, and
  material-detail jobs.
- Added a display-compression budget so tight tracking, short leading, narrow
  stretch, and extreme width cannot silently accumulate into crowded type.
- Made direct owner rejection reopen prior review and override scanner passes,
  agent self-review, and earlier candidate conclusions.

### Added

- Advisory source checks for sensory categories without a media strategy,
  compound display compression, public methodology copy, fake or pointless
  concept controls, and over-instrumented technical concept decks.
- Route-local media and concept checks for HTML, Astro, JSX, TSX, Svelte, and
  Vue, plus severe single-control, body-text, inline-style, and Tailwind
  typography-compression review.
- Executable visual-review and design-review owner disposition contracts.
  Producer self-review can only yield an agent-reviewed candidate; accepted
  and rejected decisions bind the exact candidate and evidence, and rejection
  forces a blocked or revise outcome.
- Known-bad Coffee and Relay Room calibration criteria, plus a deterministic
  supplied-media evaluation fixture with pinned ImageGen provenance and
  atmosphere, human-use, and material-detail roles.
- Regression coverage for owner-rejected website patterns and readable,
  photo-led counterexamples so the skill does not turn photography into a
  universal requirement.

### Fixed

- Generated-media detection now recognizes natural disclosures such as
  “photography is generated,” not only adjective-first wording.
- Visual-review completion now validates reviewer relationship, perceptual
  conclusion, accountable-owner disposition, and blocked-release semantics
  instead of accepting those fields as unchecked prose.
- Direction and visual-review completion now requires every first-screen
  comprehension, media, typography, public-copy, and technical-concept check;
  deleting any one of those fields reopens the record.
- Owner decisions now require a stable person identity, claim scope,
  attributable UTF-8 evidence, exact candidate binding, and valid chronology.
  Evidence-backed `not-required` is limited to standard claims, pending review
  may retain partial evidence, and premium/showcase claims require accountable
  human acceptance.
- Claude direct-install synchronization now honors `CLAUDE_CONFIG_DIR`
  independently of the default home and isolates backups, locks, skill
  discovery, and plugin-cache discovery for each configured root.
- Claude evaluation records now distinguish direct-skill and packaged-plugin
  installation modes; unsupported packaged-plugin execution fails explicitly
  instead of being silently replaced with direct-skill evidence.

## 3.0.0 - 2026-07-28

### Added

- Portable, tamper-evident Codex Plugin Creator validation evidence with
  strict live replay against an explicit external validator.
- Positive art-direction guidance for business evidence, audience, content,
  route purpose, visual world, typography, imagery, motion, interaction, and
  responsive composition before implementation begins.
- Task-specific flow guidance and broader vertical playbooks for editorial,
  education, marketplace, nonprofit, portfolio, travel, ecommerce, software,
  and local-service work.
- Contemporary typography and emphasis controls that review family choice,
  licensing, loading, fallback metrics, role discipline, copy-driven
  line-breaking, overused convergence patterns, and decorative split-color
  headline fragments without treating any popular font as proof of AI use.
- A machine-readable font audit, rendered browser-review harness, safe scanner
  allowlist example, private-data handling rules, review severity policy,
  decision case studies, and location/wayfinding craft guidance.
- Cross-host installation manager with locked, preflighted, transactional
  synchronization, duplicate-route discovery, rollback, and exact-content
  verification for Codex and Claude Code.
- Fail-closed interrupted-install recovery that understands provable staging
  and pending states, supports all-host dry runs, rejects ambiguous or tampered
  residue, and is covered by real hard process exits at every target-rename
  boundary.
- A runtime-visible, schema-valid asset-record example and a non-mutating
  initializer command that prints it without pretending example content is
  approved release evidence.
- A release SBOM, hash-locked Python and npm dependencies, strict package
  archive construction, detached-signature verification, compatibility
  evidence, and schemas for every promoted release artifact.

### Changed

- Reframed the skill around what to make: a defensible design thesis,
  project-specific content and route architecture, coherent systems,
  production behavior, and final perceptual judgment. Anti-patterns now act as
  diagnostics instead of becoming the art direction.
- Reworked the runtime entrypoint as a short progressive-disclosure router so
  agents load only the references required by the current surface, vertical,
  risk, and review stage.
- Strengthened state and evidence handling with transactional migration,
  process locking, stale-lock recovery, exact rollback, minimized provenance
  records, explicit concept status, and schema-bound review findings.
- Expanded source inspection across frameworks and file types while keeping
  source heuristics advisory unless they prove an objective defect. Scan
  completeness, policy identity, suppressions, and exceptions are now explicit
  and machine-verifiable.
- Made rendered review a required closure step for appearance-sensitive work,
  with real browser captures, multiple viewports, keyboard and preference
  checks, runtime diagnostics, output ownership markers, bounded artifact
  trees, and fail-closed concurrent-change protection.
- Separated local diagnostic builds, host-native evaluations, independent
  reviews, compatibility declarations, and release evidence so one kind of
  success cannot silently stand in for another.

### Integrity

- Added adversarial regression coverage for path escape, links and redirects,
  DNS rebinding, credential leakage, secret encodings, symlinks and reparse
  points, archive confusion, stale artifacts, forged evidence, concurrent
  mutation, duplicate install routes, and malformed schemas.
- Bound release identity to the complete distributable tree, runtime hash,
  metadata, schemas, tests, evidence, compatibility records, lockfiles, SBOM,
  and the previous manifest identity needed to detect accidental omission.
- Hardened evaluation isolation so explicitly passed secrets are redacted and
  scanned in raw, UTF-16, Base64, and URL-safe Base64 forms; detected leaks
  block promotion and force workspace removal.
- Hardened Codex plugin validation with a dated publisher-reviewed validator
  byte pin, Python isolated mode and explicit UTF-8 behavior, already-read
  validator execution, private plugin and pure-Python PyYAML snapshots,
  duplicate-key and trust-window checks, an exact one-line success contract,
  and no retained validator output content or output hashes.
- Distinguished verbatim evidence snapshots, paraphrases, and maintainer
  summaries, with hashes and validation that prevent a summary from being
  presented as a source quotation.
- Added pinned multi-platform CI declarations, rendered Chromium verification,
  retained and identity-bound evidence import guidance, scheduled evidence
  review, dependency update configuration, and zero-skip attestation policy
  while keeping unobserved CI and unavailable host runs truthfully marked as
  such.
- Made strict release derive all nine declared OS/Python pairs from the pinned
  workflow and require a retained, byte-checked CI import plus clean audit and
  zero-skip test evidence for each pair; workflow declarations alone cannot be
  promoted into compatibility passes.

### Commercial-readiness boundaries

- Added proprietary licensing, third-party notices, contribution, security,
  support, data-handling, owner-policy, installation, troubleshooting,
  migration, evaluation, release, and commercial-readiness documentation.
- A signed release still requires the owner's externally controlled signing key
  and independently established fingerprint. Formal host-native Codex and
  Claude Code evaluations, independent reviewer records, transaction-specific
  commercial terms, and configured support/security contacts remain separate
  release inputs and are never fabricated by this package.

## 2.2.0 - 2026-07-28

### Added

- A mandatory adversarial specificity-closure pass for requests to avoid
  generic, vibe-coded, house-style, or AI-looking output, including route
  silhouettes, copy texture, claim precision, media-set coherence, production
  residue, and evidence-to-polish balance.
- A project-local claim ledger with transactional initialization, schema
  validation, provenance status, review dates, and explicit concept handling.
- Scanner advisories for repeated decorative labels, rhetorical copy clusters,
  suspicious quantitative density, uniform copy texture, parallel route
  skeletons, presentation-script comments, concept/material imbalance, and
  media-authenticity review.
- Host-specific behavioral-evaluation instructions for Codex and Claude Code,
  plus adversarial closure, framework-preservation, responsive, comparison, and
  cross-case convergence evidence contracts.
- A deterministic React and Vite established-project fixture, and lockfiles
  with offline-verifiable install protocols for the React, Next.js, and
  SvelteKit fixtures.
- Broader local-business journey verification for visits, appointments, quotes,
  urgent service, regulated clinics, and events.

### Changed

- Separated source gates, advisory review triggers, execution status, and
  rendered-review closure so a clean source scan cannot be mistaken for visual
  approval.
- Narrowed non-overridable placeholder proof to literal unfinished filler;
  plausible proof-shaped statements now require provenance review instead of
  being declared false by pattern matching.
- Made explicit invocation host-correct (`$design-dna` in Codex and
  `/design-dna` in Claude Code) while keeping implicit discovery evidence
  honest and host-bound.
- Replaced simplistic output-hash diversity with contextual, perceptual
  comparison across unrelated briefs; deterministic output is not treated as a
  design failure by itself.
- Qualified cross-project comparison behind owner-authorized, minimized design
  history while allowing synthetic release fixtures to test house-style
  convergence safely.

### Integrity

- Added negative regression coverage for review closure, release
  representation, comparison efficacy, run/hash binding, cross-case
  convergence, and host-specific invocation.
- Hardened Windows test cleanup against copied read-only attributes without
  broad or unsafe deletion targets.
- Added repository text-normalization policy and deterministic dependency
  checks without committing dependency or build output.

## 2.1.0 - 2026-07-28

### Added

- Positive, evidence-to-system art-direction method and a dated convergence
  watch separated from the durable risk rubric.
- Production-readiness, final-polish, data-visualization, and software-product
  guidance.
- Current typography convergence policy, variable-font and OpenType proofing,
  and stronger prominent-copy emphasis rules.
- Generated-media provenance, credential, transformation, disclosure, legal,
  rights, approval, and privacy records.
- Temporal review evidence for significant motion and matched reduced-motion
  behavior.
- Current framework-default, repeated decorative-label, copy-form, and
  production-security review signals.

### Changed

- Reduced the entry skill to a progressive-disclosure router with explicit
  authority, readiness boundaries, artifact classifications, and specialist
  escalation.
- Made asset privacy review pending by default and required attributable reasons
  for completed privacy decisions.
- Strengthened language, localization, wide-gamut color, view-transition,
  scroll-animation, WebGL, 3D, and constrained-device verification.
- Reworked example prompts to avoid hospitality or coffee-shop anchoring.

### Integrity

- Expanded release identity to bind runtime files, package metadata, maintainer
  tooling, schemas, tests, fixtures, evidence, evaluation artifacts,
  compatibility verification, and distribution documentation.
- Hardened route discovery, standalone evidence validation, scanner semantics,
  evaluation workspace accounting, host-evidence freshness, and transactional
  synchronization.
- Bound scanner exceptions to complete matched-signal payloads; expanded
  literal fabricated-proof gates across common renderable template formats;
  and aligned policy, expiry, scalar, and portable path validation.
- Added role-based `font-serif` heading detection without turning popular font
  families into an authorship blacklist.
- Rejected quoted-empty privacy controls and already Git-tracked restricted
  research records, including case variants, while retaining an explicit
  warning when Git status cannot be verified.
- Required an explicit motion assessment in rendered review evidence and kept
  malformed unrelated skills as route-scan warnings rather than hiding valid
  Design DNA routes.
- Added machine-readable test and installed-route attestations for strict
  release verification.
- Locked the complete release-tool dependency closure and made date, date-time,
  and URI schema checks deterministic even when optional validator extras are
  absent.
- Kept generated Python bytecode outside release identities while rejecting it
  from runtime and every executable maintainer tree before local imports,
  audit, test attestation, or manifest construction; also rejected package and
  untrusted `PYTHONPATH` entries that can shadow standard-library or pinned
  release dependencies.
- Moved superseded diagnostic records out of the live evaluation-results tree
  and normalized tracked text files to deterministic LF endings.
