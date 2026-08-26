# Content, information architecture, and copy

Use this when shaping navigation, page sequence, labels, calls to action, or
user-facing language. Use [public copy and voice](public-copy.md) for longer
headings and body copy that must preserve a project voice without falling into
portable producer patterns.

## Contents

- [Model the information need](#model-the-information-need)
- [Write useful interface copy](#write-useful-interface-copy)
- [Design the content system](#design-the-content-system)
- [Review](#review)

## Model the information need

1. Name what the user is trying to understand, decide, find, or complete.
2. Inventory approved facts, proof, legal text, owner, status, and expiration.
3. Group content by user question rather than an internal department, producer
   workstream, direction record, or database/content-model category.
4. Order information by decision dependency.
5. Choose navigation, taxonomy, search, filtering, and cross-links for the
   actual corpus.
6. Define what happens when content is absent, stale, restricted, or unknown.
7. When a material entity, selection, or decision crosses routes, state what
   carries, what intentionally resets, what direct entry needs to reconstruct,
   and why that relationship helps the visitor.
8. Give stable, non-sensitive, permission-safe state a reproducible address
   when deep linking genuinely helps: a public filter, tab, page, or variant
   may belong in the URL, while transient interaction, private activity, and
   access-controlled state may belong in history, session, or application
   state instead. Never place a secret, token, personal datum, draft value, or
   sensitive selection in a URL merely for convenience; addresses can persist
   in history, logs, analytics, screenshots, and referrers. Navigation between
   documents uses real links when their semantics fit (including open-in-new-
   tab and middle-click), and Back restores the user-meaningful position and
   state promised by the chosen navigation model.

Do not invent history, metrics, testimonials, customers, availability, features,
policies, locations, prices, or integrations. Label demo and placeholder
content.

For every exact quantity, price, time, warranty, universal or near-universal
statement, regulated claim, and calculator assumption, record the source,
accountable owner, locale or scope, reviewed date, expiry, and public treatment.
Approve, qualify, label as a scenario, replace, defer, or omit it. A concept
may use clearly illustrative values; it must not turn specificity into
proof-shaped authority.

## Write useful interface copy

- Make the offer, object, action, invitation, or narrative entry concrete at
  the point where the audience needs it.
- On direct entry to a task surface, make the first meaningful action or
  reading instruction discoverable before or at the artifact it governs. A
  later detailed control can remain; the opening should not require using the
  artifact before learning what to do.
- Name consequential actions by their result when that result matters.
- Explain requirements before input and errors near the cause.
- Make confirmation, recovery, cancellation, and destructive consequences
  explicit.
- Keep terminology stable across navigation, headings, controls, and help.
- Use plain language unless specialist vocabulary helps the intended audience.
- Treat a request's "because" clause and other design rationale as internal
  input. Let it shape the encounter, hierarchy, media, and interaction; do not
  echo it as a public explanation, label, category, or help panel unless the
  brief explicitly asks for that explanation or a visitor needs it for a real
  task, consequence, or disclosure.
- Let headings summarize, invite, orient, quote, provoke, decorate, or perform
  another editorial role when that role is intentional and accessible.
- Preserve useful copy texture from supplied voice and subject-matter language.
  Do not make every section open with a question, misconception, polished
  contrast, aphorism, or reassurance.
- Start heroes and sections with their actual heading or content. Do not add a
  supporting eyebrow, kicker, overline, or label merely to tell the visitor
  what the following heading or paragraph is about. Keep one only when it
  independently communicates a real category, sequence, source/date, state,
  or explicit editorial/brand convention the heading cannot replace; a
  compositional desire alone is not enough.
  Avoid reusing a domain symbol, token, state letter, or measurement mark as
  decoration when that reuse can imply a real selection or value.

When a briefing, tutorial, schematic, worked example, or simplified preview
teaches a real interface, compare the teaching model with the operable model.
Object names, positions, topology, encodings, available moves, and units of
action must agree wherever a difference could change understanding. If a
simplification is useful, identify its limits where they matter instead of
quietly changing the grammar at the point of use. Keep the repeated action
cycle distinct from the completion or success condition.

Review promises, superlatives, rhetorical patterns, actions, and explanations
as a system. Preserve intentional supplied voice; revise unsupported claims,
ambiguity, or repeated producer grammar rather than banning a sentence shape.
For a substantial public copy pass, apply [public copy and
voice](public-copy.md) after the information model and facts are settled.

### Establish voice, tone, and terminology

- Record as much or as little voice guidance as the project needs. Derive it
  from approved brand language, audience expectations, culture, genre, and the
  relationship the work should create; express consequential decisions through
  observable writing evidence rather than a fixed trait count.
- Keep or vary voice and tone according to the approved identity and moment.
  Orientation, action, waiting, risk, failure, recovery, and success may need
  different qualities; do not assign a universal emotional register to them.
- Record terminology decisions for concepts whose consistency, translation,
  domain meaning, or audience wording matters. The format and number of terms
  follow the corpus. Preserve intentional synonyms and register changes when
  the audience genuinely distinguishes them.
- Draft the consequential representative copy states the experience can
  actually produce early enough to shape hierarchy and components. Use
  approved real language where possible; when voice evidence is missing, use
  plainly provisional scenario or placeholder language whose register follows
  the audience and task instead of manufacturing a brand voice.

## Design the content system

Define:

- content type and required fields;
- factual or subject-matter owner and truth-approval source;
- editorial or voice owner and craft-approval source;
- accessibility, legal, policy, localization, and accountable-owner reviewers
  when applicable;
- created, reviewed, and expiration dates;
- locale and translation status;
- allowed length and fallback behavior;
- relationship to routes, metadata, structured data, and search;
- cross-route entity, selection, state, handoff, reset, and recovery behavior
  when they are material;
- empty, error, loading, success, and permission-denied messages.

Derive required and optional fields from the real or approved scenario corpus,
not from the visual desire to make every item equally complete. Test sparse,
rich, ordinary, and outlier entries. Let honest differences in history,
evidence, availability, authorship, media, state, or editorial importance change
the amount and form of presentation when those differences matter. Do not pad
every card, title, profile, product, article, or record to the same length just
to complete a component matrix. In a fictional fixture, any variation must
belong to the bounded world and content model; random omissions, fake wear, or
manufactured inconsistency are not evidence of human authorship.

For translated routes, locale-aware data, or language switching, use the
[localization reference](../quality/localization.md) rather than treating
translation as a late text-replacement pass.

## Review

Select the passes that answer the work's actual content and release risks.
Truth, task, and access are non-negotiable where their risks exist; an
informational fragment, artwork, narrative, or bounded repair need not invent
navigation levels, calls to action, states, or reviewers that do not apply.

- **Outline:** When those structures exist, read only navigation, headings,
  and actions. The journey or reading logic should still make sense.
- **Route silhouette:** Compare the ordered user questions, proof, interactions,
  and actions across routes; shared structure needs a shared task reason.
- **Truth:** Trace every factual claim and item of proof to a source or explicit
  placeholder.
- **Task:** Confirm each page answers the question implied by its entry point.
- **Voice:** Mark repeated rhetorical constructions, unsupported broad
  reassurance, and copy that fails to reflect this project's facts, audience,
  task, or approved voice. Do not add fake roughness or errors.
- **Stress:** Test long, short, missing, translated, and user-generated content.
- **Access:** Check descriptive link text, heading order, instructions, errors,
  and pronunciation-sensitive text.
- **Production second eye:** When claim risk, release stakes, owner policy, or
  cultural context warrants independent review, have someone other than the
  primary writer or generator check visible copy in the rendered build for
  omissions, contradictions, truncation, stale language, stray methodology text,
  and broken links. Record who maintains time-sensitive content and its next
  review trigger.

Do not use SEO keywords to distort comprehension. Metadata and structured data
must match visible, approved content.
