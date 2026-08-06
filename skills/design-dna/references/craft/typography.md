# Typography and textual emphasis

Use this when choosing type, changing an established type system, or styling
prominent copy.

## Contents

- [Keep selection open](#keep-selection-open)
- [Separate expression from eligibility](#separate-expression-from-eligibility)
- [Proof real language in the real composition](#proof-real-language-in-the-real-composition)
- [Protect reading comfort](#protect-reading-comfort)
- [Proof Hebrew and mixed-direction type](#proof-hebrew-and-mixed-direction-type)
- [Use emphasis deliberately](#use-emphasis-deliberately)
- [Audit delivery and provenance](#audit-delivery-and-provenance)
- [Verify the finished system](#verify-the-finished-system)

## Keep selection open

There is no runtime list of preferred, approved, overused, AI-associated, or
forbidden typefaces. A familiar choice is not automatically generic, and an
unusual choice is not automatically distinctive. Preserve an established
brand or product typeface when it still serves the work and its use is
authorized.

For an open direction, begin with the project's actual words, audience,
reading conditions, scripts, media, and maintenance reality. Consider any
credible option that can meet those needs. Do not start from a category
pairing recipe, a fashionable substitution, or a quota for how many typefaces
the design may use. The finished system may be spare, varied, conventional,
experimental, inherited, or mixed; its coherence and performance must be
proved in context.

When the choice is consequential or uncertain, compare enough rendered
evidence to expose the real tradeoff. Do not require a fixed number of
candidates or concepts. Record why the selected approach fits this project,
not why another typeface is supposedly an AI tell.

## Separate expression from eligibility

Evaluate two contracts independently:

- **Aesthetic fit:** voice, cadence, hierarchy, texture, proportion, image
  relationship, cultural context, and the character of the actual language.
- **Technical eligibility:** rights, source integrity, file behavior, required
  glyphs and scripts, fallbacks, weight and style coverage, browser delivery,
  performance, accessibility, and maintenance.

A technically eligible typeface may still be wrong for the composition. An
expressive specimen may still be unusable because its license, script
coverage, fallbacks, or loading behavior is unresolved. Do not let either
contract stand in for the other.

Let roles emerge from the interface and content rather than from a universal
type-system checklist. Define the family, size behavior, weight or style,
line height, tracking, measure, fallback, and responsive behavior for every
role the project actually uses. Reuse roles when that improves continuity;
create a justified exception when the content or composition needs one.

## Proof real language in the real composition

Build specimens from the content that will ship, including the longest likely
heading, ordinary paragraphs, short and long controls, navigation, names,
numbers, prices or dates when relevant, punctuation, and every required
script. Include realistic missing, translated, or expanded content where the
surface supports it.

Judge type inside the intended layout and beside its actual media. Look at:

- word and line texture, syntax, cadence, and hierarchy;
- legibility of confusable characters, punctuation, numerals, and small text;
- line breaks, measures, alignment, crop relationships, and whitespace;
- how the same language recomposes at narrow, intermediate, and wide widths;
- whether fallback and loading transitions preserve meaning and composition.

Use axes, alternates, optical behavior, case, slant, width, or other features
when they serve the project's creative logic, identity, atmosphere, formal
aim, content, or reading purpose. Static and variable delivery are both
neutral options. If a feature or axis is used, inspect the actual instances
and transitions rather than trusting its availability.

## Protect reading comfort

Treat tracking, leading, width, weight, optical behavior, size, and measure as
cumulative controls. A display moment can be compressed or expansive when the
rendered words support it. Do not copy that treatment into reading text,
navigation, labels, controls, or helper text by convenience; a deliberate
extension is valid when its creative role, legibility, states, and relevant
widths are actually proved.

Inspect crowded joins, clogged counters, ambiguous shapes, clipped marks,
line collisions, uneven word texture, fragile wrapping, and the effort needed
to parse the sentence. Recheck narrow and intermediate widths instead of
assuming a smaller size preserves the desktop composition. Test browser zoom,
text-spacing overrides, font-loading failure, and user-selected contrast or
color modes. A short display exception does not set the default for the rest
of the surface.

## Proof Hebrew and mixed-direction type

When Hebrew appears, define its content job before styling it. A Hebrew locale,
an isolated term in another language, a parallel translation, a quotation,
and sacred text have different language, direction, line-breaking, and review
requirements.

Use current
[W3C Hebrew Layout Requirements](https://www.w3.org/International/hlreq/) as a
script-specific review aid and pair it with the
[localization contract](../quality/localization.md):

- tie the document's base direction to the active locale and mark meaningful
  passages with accurate `lang` and `dir`;
- isolate embedded names, URLs, numbers, dates, identifiers, and punctuation
  with deliberate bidirectional markup where appropriate;
- use logical properties and meaningful source order;
- inspect punctuation, numerals, lists, form fields, line edges, wrapping,
  selection, and copy/paste in real mixed-language sentences;
- verify every required letter, mark, diacritic, symbol, and numeral in the
  actual files and fallbacks;
- proof shaping, mark placement, counters, baseline, line gap, weights, styles,
  and fallback at the sizes that ship;
- avoid manipulation that separates marks, reverses reading, clips glyphs, or
  treats the script as visual texture;
- verify transliteration, translation, and sacred material with an accountable
  language or cultural authority.

When the script is material, include narrow and wide specimens, loading
failure, zoom, text-spacing override, forced colors, selection and copy,
keyboard order, and assistive-technology review. Do not invent language or
sacred text to fill a composition. Also complete the
[cultural-context review](../quality/cultural-context-review.md) when lived
identity is central.

## Use emphasis deliberately

Color, face, slant, underline, marker, sticker, outline, motion, and isolated
word treatments are available design choices, not forbidden ingredients.
Judge what the treatment does in this composition and whether repetition has
become automatic or interchangeable across unrelated copy.

Emphasis may clarify syntax, meaning, hierarchy, voice, action, brand, state,
quotation, data, or a compositional relationship. It may also be purely visual
when the whole rendered composition supports it. Judge its actual relationship
and repetition; do not manufacture semantic justification after styling an
interchangeable fragment.

Preserve links, states, and meaning without color alone. Verify contrast,
legibility, reflow, forced-colors behavior, and comprehension. A recurring
treatment should form a coherent project rule; a consequential one-off should
remain a deliberate exception rather than being copied everywhere.

## Audit delivery and provenance

Inventory what the browser is asked to load and what the project actually
ships:

- source, license, redistribution and self-hosting rights;
- file format, subset, byte size, weights, styles, features, and axes used;
- required scripts, diacritics, symbols, currencies, and numerals;
- fallback order, metric adjustments, synthetic styles, and layout shift;
- preload, cache, cross-origin, failure, and unused-request behavior.

Do not infer rights, glyph coverage, quality, or authorship from a family name.
Do not ship unused files or styles that survive only in a specimen.

When Python 3.10+ is available, run the bounded source inventory:

```text
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/font_audit.py" "PROJECT"
```

Replace `<DESIGN_DNA_SKILL_ROOT>` with the quoted absolute directory containing
the installed `SKILL.md`. The report inventories source contracts and files;
it is not a browser proof, license ruling, glyph test, aesthetic score, or
authorship detector. It prunes packaged `.design-dna` state, its transaction
backups/stages, and declared build, dependency, and vendor roots before descent.
An access failure in included project source remains an execution failure; an
excluded internal root is not typography evidence.

For source-level unused-family review, the audit follows an unambiguous static
CSS custom-property value across scanned files only when a `font` or
`font-family` declaration references that property. Defining a font-valued
property alone does not count as use, and conflicting project-wide definitions
remain unresolved rather than being guessed.

Choose local or remote delivery, subsetting, static or variable files, and
loading behavior from the project's measured needs and authorization. Request
only what ships, preload only what is critical, prevent synthetic styles and
avoidable layout shift, and verify every feature or axis actually used.

## Verify the finished system

Review the final rendered surface with real content at its meaningful widths
and states. Test fallback before loading, missing glyphs, translated and
expanded text, heading wraps, controls, data alignment, zoom, text-spacing
overrides, contrast at every used weight and size, transfer cost, and layout
stability. Inspect computed browser use rather than assuming declarations won.

Record the aesthetic rationale separately from the technical evidence. Name
unverified rights, glyph, fallback, browser, performance, language, and
cultural conditions. Never claim originality from rarity or reject a correct
choice because another tool also uses it.
