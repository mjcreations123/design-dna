# Parseable public text

Use this after the content model exists and again on the rendered candidate.
Its purpose is to prevent fabricated proof, implementation residue, empty
design jargon, and decorative text that accidentally masquerades as useful
information. It is not a punctuation guide, phrase blacklist, sentence-shape
recipe, or ban on atmosphere.

## Contents

- [Classify the string](#classify-the-string)
- [Use the four-question review](#use-the-four-question-review)
- [Default to the heading, not a pre-heading label](#default-to-the-heading-not-a-pre-heading-label)
- [Keep rationale and internal taxonomy off the public surface](#keep-rationale-and-internal-taxonomy-off-the-public-surface)
- [Distinguish atmosphere from false information](#distinguish-atmosphere-from-false-information)
- [Keep disclosure visitor-facing, not process-facing](#keep-disclosure-visitor-facing-not-process-facing)
- [Review copy specificity without writing by formula](#review-copy-specificity-without-writing-by-formula)
- [Run bounded residue checks](#run-bounded-residue-checks)
- [Close the rendered pass](#close-the-rendered-pass)

## Classify the string

Identify what each prominent or repeated string is doing:

- **Action:** navigation, control, instruction, error, recovery, or next step.
- **Subject content:** heading, explanation, caption, quotation, annotation,
  label, taxonomy, data, or evidence about the visitor's subject.
- **Atmosphere or voice:** language whose honest purpose is mood, rhythm,
  identity, humor, ceremony, or composition rather than instruction.
- **Disclosure:** source, limitation, privacy, generated-media, sample-data,
  legal, or operational context the visitor actually needs.
- **Residue or false information:** placeholder material, leaked component or
  variable names, fake telemetry, fabricated status, unexplained codes, or
  data-shaped decoration likely to be mistaken for a real fact.

All but the final class can be legitimate. Atmospheric language does not need
to pretend it is data or utility; review it for aesthetic success and
salience. Technical labels, version information, system status, and metrics
are legitimate when the real audience needs them and the values are truthful,
current, and accessible. They are defects when they are false, irrelevant, or
used as generic visual chrome.

## Use the four-question review

Apply these questions to high-salience, repeated, data-shaped, interactive,
or doubtful strings. A full node-by-node log is useful only when the scope or
risk warrants it.

1. **Meaning:** What does the string communicate, enable, or contribute to the
   intended experience?
2. **Truth:** Could it be mistaken for a fact, person, result, status, price,
   capability, quotation, or proof? If so, what source and freshness support
   it?
3. **Audience:** Is the language understandable and appropriate for the people
   and context in the brief, including legitimate specialist vocabulary?
4. **Relationship:** Does it clarify, distinguish, pace, or enrich its
   surroundings, or does it duplicate, compete, or create false hierarchy?

Remove, rewrite, relabel, or make real anything that cannot justify its public
role. Do not delete a successful aesthetic line merely because its purpose is
expressive rather than utilitarian.

## Default to the heading, not a pre-heading label

Do not add an eyebrow, kicker, overline, mini-label, or compact all-caps line
before a hero, heading, paragraph, or section as generic hierarchy. Start with
the actual heading or content. In particular, do not use a small line merely
to paraphrase or foreshadow the adjacent subject: "The optical study" above a
heading already about an optical study adds no visitor-useful information.

Keep or introduce a pre-heading label only when it communicates a different,
project-grounded fact that the adjacent heading cannot replace without losing
meaning: an actual category or taxonomy, source/date, true sequence, active
state, or an explicit editorial/brand convention. A desire to make a section
feel designed is not enough, and ordinary sections do not need a label.

This rule does not suppress functional text: form labels, navigation, captions,
credits, metadata, table labels, legends, and truthful operational status still
serve distinct jobs. It also does not turn the visual treatment itself into a
global style ban; evaluate the whole hierarchy and the current project's
evidence.

## Keep rationale and internal taxonomy off the public surface

Treat a brief's explanation of why a design should feel or work a certain way
as private direction. For example, "make the arrival quieter because visitors
are waiting" should affect the encounter, hierarchy, pacing, and material
choices; it does not authorize a public label, heading, caption, tooltip, or
"why this is here" panel that repeats the producer's reasoning.

Likewise, do not promote internal working language into visitor-facing
categories just because it helps organize the project. Source mappings, review
records, fixtures, source gaps, workflow stages, component names, route IDs,
database or content-model fields, raw back-end states, analytics terms, and
back-office categories are internal by default. A category belongs on the
public surface only when it names a real subject, choice, collection, status,
or task that the intended visitor recognizes and needs.

Before retaining a doubtful explanation or category, ask:

1. Did this originate as public source material or an explicit public-copy
   request, rather than a producer's note or implementation detail?
2. Does the visitor need it to understand the actual subject, make a choice,
   complete an action, or avoid a concrete misconception?
3. If status or disclosure is necessary, can it state the visitor consequence
   without narrating the design, workflow, or system behind it?

If the answer is no, remove it from the public surface and keep it in the
relevant project record. A product whose actual purpose is to explain methods,
operations, or technical systems can publish that information, but it still
needs a real audience and public job rather than a designer's self-explanation.

## Distinguish atmosphere from false information

Decorative marks, marginalia, ordinals, coordinates, badges, terminal-like
language, mono labels, status dots, and technical diagrams are neutral
ingredients. Inspect the whole relationship:

- Do they belong to the subject, voice, or composition?
- Could a reasonable visitor mistake them for live status, proof, sequence,
  location, or capability?
- Are any values real, current, and maintained?
- Do they outrank information or controls that matter more?
- Does the same gesture repeat across unrelated sections or projects without
  a reason?
- Does the treatment survive contrast, zoom, text spacing, forced colors,
  localization, and reduced motion where relevant?

A fictional or illustrative interface may use representative labels and data
when the demo boundary is proportionate and unmistakable. Do not present a
concept mockup as a real product screenshot, customer result, or operating
service.

## Keep disclosure visitor-facing, not process-facing

A necessary truth boundary should tell the visitor what could be misunderstood,
what is illustrative or unavailable, and what action remains safe. It should
not make the site repeatedly narrate the production workflow. Phrases such as
`design study`, `interaction study`, `code-native`, `source packet`, or
`commissioned scenario` may be accurate and may belong on a site that is
actually about its making. Elsewhere, treat them as review prompts: they often
describe the producer's evidence process rather than the visitor's subject.

Choose disclosure placement from the actual risk. An identity-level boundary,
a content-specific caption, a methods/source page, metadata, or a direct-entry
notice can each be appropriate. Do not mechanically repeat the same caveat in
the header, hero, every route, footer, and title; do not mechanically collapse
all disclosure into one hidden page either. Every route must remain honest on
direct entry, while the public identity and primary actions should lead with
the subject unless production status is itself the subject.

Generated-media status, fictional operating facts, unavailable capability, and
legal or safety limits are separate disclosure jobs. Combine them only when the
result remains clear. Keep internal fixtures, source-gap logs, assurance
profiles, tool names, and build methodology in project evidence unless the
audience genuinely needs them.

## Review copy specificity without writing by formula

Prefer accurate nouns, constraints, examples, process detail, and owner voice
when they are available. Preserve supplied language that is distinctive and
true. Avoid generic reassurance that could move unchanged to an unrelated
site, but do not force every section to contain a number, place, date,
opinion, or irregular sentence pattern.

Repeated phrasing is appropriate for navigation, taxonomy, product families,
campaign language, accessibility, and deliberate rhythm. It becomes a finding
when it adds no information, overwhelms hierarchy, or reveals an unexplained
cross-project copy machine. An eyebrow, FAQ, short fragment, three-item list,
or familiar marketing phrase is not a defect merely by its form. A pre-heading
label is a finding when it is mechanically inserted before headings, merely
repeats the adjacent subject, or acts as generic micro-hierarchy rather than
communicating an independent visitor-useful fact.

Do not manufacture humanity with typos, slang, fake quotations, invented
anecdotes, awkwardness, random punctuation, or intentional inconsistency.

## Run bounded residue checks

Extract rendered text from every relevant route and state, including hidden
panels that can become visible, plus accessible names, alt text, title, and
descriptions. Run deterministic checks for:

- unresolved placeholders and work markers such as `lorem`, `TODO`, `TBD`,
  `FIXME`, `asdf`, `your text here`, or bracketed media instructions;
- binding and serialization leaks such as `undefined`, `NaN`, `[object
  Object]`, unresolved template braces, raw JSON, or literal variable names;
- model or citation residue such as `oaicite`, `contentReference`, internal
  turn identifiers, Markdown markers, or prompt text;
- encoding damage including the replacement character and visually confirmed
  mojibake;
- generator tags, preview hosts, internal proof banners, skill vocabulary, or
  environment details that should not ship.

Treat these as review candidates rather than a blind global ban when a real
article, code sample, error-documentation page, or quoted source legitimately
contains the token. Search results need human triage.

Maintain a dated, review-only phrase watch only when current evidence supports
it. A phrase hit can trigger a copy read; it never proves authorship and never
blocks a page without a contextual finding.

## Close the rendered pass

1. Observe the page before loading motif vocabulary.
2. Review prominent, repeated, interactive, data-shaped, and doubtful text
   with the four questions.
3. Run and triage the bounded residue checks.
4. Inspect salience, hierarchy, typography, wrapping, and meaning at the
   relevant wide and narrow renders.
5. Exercise loading, empty, error, success, offline, permission, and recovery
   copy when those states exist.
6. Fix the underlying content or relationship, rerender the affected states,
   and record unresolved truth or owner decisions.

The pass succeeds when public text is truthful, comprehensible for its
audience, appropriate to its role, visually resolved, and free of accidental
internal residue. It does not require all sites to sound alike.
