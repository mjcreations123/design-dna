# Post-render convergence review

Use this review only after a real first render exists. Do not read it to
choose fonts, colors, layouts, components, effects, copy formulas, or a style
before making that render. Its job is to diagnose an observed result, not to
supply an inverse template for generation.

This file is post-render review vocabulary: dated, expiring, cluster-based,
never a one-ingredient verdict, and never an inverse prompt; the canonical
two-lane rule lives in the [owner absolutes](../policy/absolutes.md). One
exception: the font-cluster tables below are also consumed at selection time
when HARD 1's comparison protocol requires it.

## Contents

- [Neutral-alone rule](#neutral-alone-rule)
- [What this review may diagnose](#what-this-review-may-diagnose)
- [Required counterevidence](#required-counterevidence)
- [Post-render procedure](#post-render-procedure)
- [Dated watch: current clusters](#dated-watch-current-clusters)
- [Dated watch: the font clusters](#dated-watch-the-font-clusters)
- [Dated-signal watch: the opposite failure](#dated-signal-watch-the-opposite-failure)
- [Builder-fingerprint hygiene](#builder-fingerprint-hygiene)
- [The self-fingerprint](#the-self-fingerprint)

## Neutral-alone rule

Every aesthetic ingredient is neutral when considered alone, whether common,
uncommon, fashionable, unfashionable, restrained, expressive, familiar, or
experimental. Do not flag, replace, or discourage a choice because it appears
in a trend discussion, is popular, resembles an example, or can be generated
easily. Popular choices can be exactly right. Rare choices can be arbitrary.
One ingredient is not a convergence finding. The owner absolutes are the sole
exception, and they are owner law, not detection.

## What this review may diagnose

Only diagnose one or more of these observed aggregate failures:

| Failure | Evidence required in the rendered work | Constructive response |
| --- | --- | --- |
| **Defaulting** | Several independent decisions carry a starter, generator, library demo, previous route, or the maker's unrelated-project grammar without a project reason. | Return to actual content, brand, task, audience, and medium. Re-decide the affected relationships; do not rotate to a fashionable opposite. |
| **Irrelevance** | Multiple effects, labels, surfaces, motions, images, or copy gestures compete with the message or task, reveal no useful meaning, or remain after their reason disappears. | Keep anything that clarifies, delights, proves, or supports the intended experience. Revise or remove only what cannot explain its role. |
| **Inconsistency** | Hierarchy, interaction language, visual language, terminology, density, asset quality, or state behavior conflicts across the same experience without a legible reason. | Reconcile the relationships that should agree and document intentional contrast. |
| **Unchecked behavior** | The delivered journey accumulates bugs, dead controls, missing states, misleading affordances, unreadable content, broken mobile behavior, placeholders, invented evidence, or first-pass residue. | Verify the real path and its states on rendered desktop and mobile. Fix the underlying defect. |

## Required counterevidence

Before keeping a finding, record credible project-serving explanations: an
approved brand, platform, culture, genre, editorial system, or supplied
reference; a clearer task, hierarchy, or voice; required consistency for a
route family or accessible convention. If the counterevidence explains the
choice and the execution holds up, close the finding. Do not penalize a
design for resembling a trend.

## Post-render procedure

1. Review the first render without consulting the tables below. Record the
   page's actual job, strongest content, intended attention path, and any
   immediate owner response.
2. Exercise the real journey at relevant desktop and mobile widths,
   including keyboard, focus, reduced-motion, loading, empty, and error
   behavior where applicable.
3. Name concrete observations before assigning a category, with route,
   state, viewport, and evidence.
4. Group observations under defaulting, irrelevance, inconsistency, or
   unchecked behavior. Do not create a finding from a named motif alone.
5. Record counterevidence. Compare unrelated projects through the
   [ledger](quality/ledger.md), which is standing owner authorization for
   minimized cross-project comparison.
6. Revise the cause, render again, verify the affected journey. Never merely
   exchange one recognizable style bundle for another.
7. For an explicit AI-looking, vibe-coded, templated, generic, or
   house-style concern, complete the
   [adversarial specificity review](quality/specificity-review.md).

## Dated watch: current clusters

Compiled 2026-08. Review by 2027-02. These are expiring review candidates,
not style bans; investigate the combination and project fit, and never fail
a design for one ingredient. After the review-by date, refresh from current
discourse before using any row in a current-facing recommendation.

| ID | Current candidate cluster | Positive action | Legitimate exception |
| --- | --- | --- | --- |
| `RISK-KIT-001` | Two or more of: gradient text on a headline, eyebrow badge above a centered H1, uppercase letterspaced label above every section, indigo-violet accent, glow shadows, three-card icon row, left-border accent cards. The reflexive co-occurrence is the mean, whatever the fonts. | Count eyebrow labels per page and keep only the ones doing navigation or taxonomy work; derive accent from the client's world; give cards a project reason or remove the container. | Each element alone can be right; an eyebrow is fine as a real taxonomy, a glow is fine when light is the concept. |
| `RISK-GLOW-001` | Radial glow "lights" scattered across a dark SaaS layout; ambient gradients with no light source or content job. | Maximum one motivated ambient light per page; darkness needs a concept, not decoration. | A genuine lighting concept executed with discipline. |
| `RISK-EMPH-001` | One word of a headline swapped to a different color or italic serif to manufacture a focal point; repeated across sections. (A gradient on the word is not reviewable here; gradient text is ABSOLUTE-banned.) | Strengthen the wording, whole-phrase hierarchy, scale, or placement. | A documented brand or semantic phrase treatment in color or italic that survives contrast and forced-colors checks, logged per HARD 2. |
| `RISK-STATS-001` | A stat band of round numbers with plus signs and emoji; metric tiles no system produced; "10,000+ happy customers." | Real numbers with sources, or an honest number-shaped hole. Fabricated stats are an owner ABSOLUTE, not just a watch item. | Real, sourced, current figures presented statically. |
| `RISK-MOCK-001` | CSS-built fake dashboards, browser chrome, phone shells standing in for product evidence. | Real screenshots of the real product, a labeled concept mock, a diagram, or nothing. Fake product UI is an owner ABSOLUTE. | A clearly labeled concept mock communicating a proposed interaction. |
| `RISK-SURFACE-001` | Nearly every item inside a soft rounded container, containers nested in containers, uniform radii and shadows everywhere. | Define surface and radius roles; use spacing, rules, and alignment where no real containment exists. | Pills for compact semantic tokens; nested surfaces representing real layered state. |
| `RISK-DENSITY-001` | Centered sections, uniformly large gaps, tiny support text, low information density repeated regardless of task. | Tune density to content and audience; establish a real focal hierarchy. | Spacious centered composition for short ceremonial content. |
| `RISK-COPYFORM-001` | Vague superlatives, interchangeable CTAs, "Revolutionize your workflow," repeated question openings, polished "not X, Y" contrasts, aphoristic endings, the same claim restated across sections. | Rewrite from concrete source language: inputs, outputs, constraints, consequences, next steps. Count claim repetitions; more than twice is noise. | Supplied brand language and a real editorial voice. |
| `RISK-HUD-001` | Decorative pseudo-data: coordinates, serials, version strings, timestamps, degree readouts, barcode text, crosshair labels, terminal carets, pulsing dots on static content. | Run the [parseable-text](quality/parseable-text.md) four-question gate; bind to real data or delete. | A genuinely technical subject where every mark is true, at most one or two per viewport. |
| `RISK-FWK-001` | An untouched starter or component-library preset carrying its stock tokens, radii, icons, spacing, and example composition into a public identity. | Inspect the actual preset; theme the relationships that need a project voice. | Defaults as an intentional internal or product standard. |
| `RISK-SUBSTRATE-001` | The shadcn/v0/Bolt substrate read whole, whatever tool made it: zinc-slate neutral scale, Geist or Inter, one radius on every element, 1px muted borders, blanket Lucide icons, library token names surviving verbatim, developer-tool minimalism carried onto a non-developer subject. The test is reskinnability: if swapping theme tokens would change nothing, the layout is the library's. | Re-author the token layer until component provenance is not guessable: project-named tokens, a neutral scale with a chosen temperature, radius roles, curated or custom iconography. The client's world outranks the toolkit; a wedding shop must not pass as a developer dashboard. | A genuine developer tool whose audience lives in that language, with tokens still themed on purpose. The fully untouched preset is RISK-FWK-001. |
| `RISK-FORMULA-001` | A builder house formula beyond the skeleton: industry stock hero, client-logo carousel, service-card row, about blurb, tiered pricing, contact form with map, palette derived mechanically from the logo, one generic quote funnel. Everything on the page is derivable from business type plus location, which is exactly what a 30-second wizard collects. | Build from facts a wizard never asked for: real inventory, the actual buying journey, the owner's photos and voice. The skeleton verdict itself belongs to ABSOLUTE 6's swap test in the [owner absolutes](../policy/absolutes.md); this row diagnoses the surrounding gestalt. | Any single formula section survives when a recorded content derivation put it there and its proof is real. |
| `RISK-REVEAL-001` | One reveal cloned to every section: scroll-triggered fade-up applied uniformly, marketplace parallax layers, drifting blur backdrops with no content job. The motion equivalent of an unchosen font. | Spend the motion budget on purpose-built moments at full intensity, a different mechanism per act, each teaching or revealing something. Delete reveals that merely announce a section exists. | One orchestrated entrance for genuinely sequential content, with reduced-motion honored. |
| `RISK-IMGSET-001` | The generated-image tell set: garbled or pseudo-text inside images, impossible hands or geometry, glossy default-model sheen, images that disagree on light, grade, and lens because each was pulled or generated alone, and the archetype trap: the image shows the statistical archetype of the subject's name while the copy claims something more specific. Hotlinked stock CDNs and stranger-stock genres read the same way. | Art-direct imagery as one set under one grade recipe, inspect every final pixel, and run the subject-accuracy check in [imagery](craft/imagery-illustration.md): the thing shown must be the thing the copy names. | Documentary variation across real photographs is evidence, not a defect. |

## Dated watch: the font clusters

Compiled 2026-08. Review by 2027-02. Two clusters that read differently.
Full selection doctrine lives in [typography](craft/typography.md).

| ID | Cluster | Reading | Positive action |
| --- | --- | --- | --- |
| `RISK-TYPE-LLM` | Inter as the whole page, Space Grotesk as the "distinctive" pick, Geist, Instrument Serif italic heroes, the sans-headline-with-one-italic-serif-word pattern, DM Sans, Manrope, Sora, Plus Jakarta Sans as near-neighbors. | Vibe-coded: the statistical center of the training data. Not bad faces, unchosen faces. | Replace, do not re-treat. Run the selection protocol with named rejects. Inter may survive as a supporting body face under a chosen display voice. |
| `RISK-TYPE-TEMPLATE` | Poppins, Montserrat, Playfair Display heroes, Lato, Raleigh-class geometric sans on everything. | Cheap theme: Canva and Fiverr, not AI. | A template-cluster face can be rehabilitated only with a treatment the templates never use, recorded. |
| `RISK-TYPE-STUDIO` | Studio-burned by ledger repetition, owner-dated 2026-08: Archivo (four projects), Schibsted Grotesk (two builds in one batch), the Clash Display + Switzer pairing. A bench face joins this row when it appears in three of the last ten ledger rows. | Self-similarity, not trend: the studio's own forming fingerprint. Replace via the selection protocol. | A returning client whose established identity already uses the face. |

This table is the single canonical watch list; HARD 1 in the
[owner absolutes](../policy/absolutes.md) gates every face on it, and the
[typography bench](craft/typography.md#the-dated-bench) defers to it. Any
face on a current "use this instead" list is on a 12 to 18 month decay
clock; Instrument Serif flipped from recommendation to tell in about a year.
Date every recommendation.

## Dated-signal watch: the opposite failure

The tables above push away from what is fashionable. Used alone they have a
predictable failure mode: work retreats out of a trend cluster and lands in
a historical one. That is not neutrality; it is a different dated choice,
and an accountable owner rejects "looks like 2004" as fast as "looks
generated." Review these when a result reads old, tired, or amateur.

| ID | Dated candidate cluster | Positive action | Legitimate exception |
| --- | --- | --- | --- |
| `RISK-PERIOD-001` | An OS-default face (Segoe, Aptos, Arial, Verdana, Georgia, Times, Courier) carries the display voice or wordmark, usually because a webfont was never chosen or never loaded. | Choose and self-host a real display voice; run the rendered-font verification. The fallback must never become the identity. | Dense Operate UI, product continuity, or regulated delivery, by written decision, per [typography](craft/typography.md). |
| `RISK-PERIOD-002` | Hairline rules, 1px-bordered tables, and boxed panels supply most of the structure; hierarchy comes from lines rather than space, scale, weight, colour, or depth. | Rebuild hierarchy with spacing, scale, and grouping; keep rules that encode real rows and boundaries. | Genuine tabular data, financial documents, schedules, spec sheets. |
| `RISK-PERIOD-003` | Body text below ~15px with tight leading and long measures: a CRT-era desktop application. | Contemporary reading sizes and leading per the typography numbers. | Data-dense professional tools where the operator wants density. |
| `RISK-PERIOD-004` | Flat neutral ground, no imagery, no depth, no colour field, no motion, presented as restraint. Removing the one accent leaves an undifferentiated page. | Absence must be an authored decision, not an unfilled gap. Quiet passes when the brief or owner language supports it, the rendered result reads authored with one nameable memorable element, and it was compared against a richer rendered alternative or inherits an approved direction. For Persuade and Experience work whose value is physical or sensory, real photography is a launch requirement; a committed type-led direction is valid only per RISK-MEDIA-001's recorded-authorization terms. | Text-first reference, documentation, archival surfaces where typography and structure genuinely carry the work. |
| `RISK-PERIOD-005` | A centred fixed-width column on an undifferentiated ground, symmetrical margins, no bleed, overlap, or asymmetry anywhere. | Use the full canvas where the content supports it: asymmetry, bleed, layering, varied section silhouettes. | Long-form reading, ceremonial pages, print-faithful documents. |
| `RISK-PERIOD-006` | Dense mono or uppercase micro-label type tables with hairline rules: reads "made in 2002." Owner-rejected verbatim. | Consumer-facing pages get contemporary hierarchy; mono stays with code and data. | An archival or terminal concept the brief explicitly asked for. |

An expressive or showcase brief must clear this table as well as the ones
above. Absence of trend is not presence of craft.

## Builder-fingerprint hygiene

Compiled 2026-08. Review by 2027-02. Detection tools identify builders from
six technical surfaces: meta tags, script and asset hosts, DOM attributes,
class and token patterns, HTTP responses, and package heritage. A hand-built
site that accidentally carries a builder's signals gets filed as template
output by anyone with a free browser extension. The rule is positive: every
external host, token name, and metadata field on the shipped site is one the
author chose. Run this sweep on the RENDERED DOM and the shipped bundle, not
the authored source; libraries inject attributes at runtime.

Sweep the shipped output for:

- `<meta name="generator">` in any form, from any framework or plugin
- Builder hosts: framerusercontent, framer.com/m/, events.framer.com,
  lovable.app, lovable-uploads, cdn.gpteng.co, gptengineer, bolt.host
- Builder attributes and globals: `data-framer-`, `data-lovable`,
  `data-component-id`, `__framer`, tagger plugins in any config file
- Tool names and generated comments inside the JS bundle; bundles are
  grepped by detectors, not just the DOM
- Stock or placeholder tokens verbatim: bare-HSL shadcn variables, "Color 1"
  and "Heading H1" style names, an untouched components/ui folder,
  `placeholder.svg?height=` images
- Default Tailwind palette classes on an untouched config (indigo-500,
  slate-200 borders) surviving into a public identity
- Scaffold leftovers: default favicon, default title, sample og-image,
  machine-hashed asset filenames, create-next-app residue
- Package heritage: builder plugins and unused scaffold dependencies in the
  lockfile of a client-owned repo
- An empty root div whose content exists only after hydration; the pitch
  must be readable in the initial HTML

Vercel and Netlify hosting headers are unavoidable and weak; leave them.
Detector scoring is a quorum: one direct builder artifact convicts alone,
stack coincidences convict only together. Eliminate the direct class to
zero, then thin the coincidences until no quorum can form.

## The self-fingerprint

The maker's own recurring shorthand is a convergence source no third-party
trend list can catch: all-caps eyebrow labels, decorative 01/02 markers,
split oversized headings, three-part slogan rails, warm paper, ruled grids,
mono micro-chrome, repeated reveal motion, the same signature diagram, the
same wireframe skeleton under different paint. Two of this studio's QA
builds shipped the identical skeleton with different palettes; the owner
kills builds for exactly this.

Audit the current route BEFORE reading this file's vocabulary, then diff the
proposed hero composition, headline scale and case, eyebrow treatment,
section rhythm, and footer form against the previous two ledger rows. If
the wireframes match, the build has already failed regardless of palette
and family. Typography and structure are one fingerprint.

COPY VOICE is a fingerprint axis of its own, and the hardest to see from
inside: a batch review of three structurally distinct builds still
attributed all three to one writer by their kicker constructions,
honesty-flex closers ("if not we say so"), shared demo-notice sentence
skeletons, separator punctuation, and four-count section logic. For batch
work, give each build its own voice register (dry administrative, blunt
trade, warm narrative) and vary the mandated boilerplate's construction,
not just its nouns. Masked copy from two builds should not read as one
author.
