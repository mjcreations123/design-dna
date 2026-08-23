# Localization and bidirectional interfaces

Use this when a route supports more than one locale, translated content,
locale-aware formatting, right-to-left direction, or a language switcher. Do
not claim localization from a mirrored screenshot or translated paragraph.

## Contents

- [Define the locale contract](#define-the-locale-contract)
- [Implement language and direction](#implement-language-and-direction)
- [Verify Hebrew and mixed-direction content](#verify-hebrew-and-mixed-direction-content)
- [Source review matrix](#source-review-matrix)
- [Rendered and behavioral matrix](#rendered-and-behavioral-matrix)

## Define the locale contract

Record the supported locales, source locale, content owner, translation state,
fallback behavior, URL or routing strategy, and what happens to the current
task when language changes. Distinguish translated, reviewed, fallback, and
unavailable content. Never imply that an automatic translation was
professionally reviewed when it was not.

Keep user-facing strings outside component logic when the stack supports it.
Give translators context, variables, plural meaning, character limits only when
genuinely necessary, and examples for ambiguous labels. Avoid concatenating
sentence fragments or assuming English word order.

## Implement language and direction

- Set the document and route `lang` accurately; mark meaningful mixed-language
  passages when pronunciation or processing changes.
- Set `dir` from the active locale and use CSS logical properties for layout,
  spacing, alignment, borders, and positioning.
- Isolate user-generated names, identifiers, and mixed-direction values with
  appropriate bidirectional markup such as `bdi` or a deliberate `dir`
  strategy.
- Mirror spatial relationships where reading direction requires it, but do not
  mirror brand marks, photographs, charts, media controls, clocks, or other
  directionally meaningful content without a reason.
- Use locale-aware APIs or libraries for dates, times, time zones, numbers,
  currency, units, relative time, plural categories, lists, and collation.
  Store underlying values separately from their localized presentation.
- Choose the interface language from the user's declared language
  preferences, never from IP geolocation; travelers, expatriates, and
  shared networks make location a wrong proxy for language.
- Mark brand names, product tokens, code, and identifiers as
  not-to-be-translated (`translate="no"` or the equivalent), so browser
  machine translation does not garble the words that must stay exact.
- Confirm font coverage, fallback metrics, line breaking, hyphenation,
  diacritics, shaping, numerals, and punctuation for every shipped script.
- Keep validation, status, empty, error, permission, and recovery messages in
  the same locale as the task.

A language switch must be named in each available language, keyboard operable,
and understandable without flag-only labels. Define whether it preserves the
route, query, form state, focus, scroll, and history; do not silently discard an
in-progress task.

## Verify Hebrew and mixed-direction content

When Hebrew is material, use the current
[W3C Hebrew Layout Requirements](https://www.w3.org/International/hlreq/) as a
script-specific reference and complete the
[mixed-direction typography proof](../craft/typography.md#proof-real-language-and-mixed-direction).

- Use `lang="he"` and `dir="rtl"` for Hebrew passages. Do not set the whole
  document to RTL when the active interface locale remains English.
- Keep characters in logical reading order. Do not reverse strings, manually
  reorder words, or use CSS transforms to create RTL.
- Isolate embedded names, Latin text, URLs, email addresses, phone numbers,
  dates, and identifiers with appropriate `bdi`, `dir`, or `dir="auto"`
  behavior. Prefer markup over invisible directional control characters.
- Use CSS logical properties. Review flex and grid ordering, breadcrumbs,
  arrows, progress, tables, form affordances, and icon meaning instead of
  mirroring the entire interface.
- Proof brackets, quotation marks, punctuation, list markers, numerals,
  line-breaking, selection, copy/paste, truncation, search, validation, and
  editable fields with real mixed-language content.
- Confirm screen-reader pronunciation and reading order with accurate language
  boundaries. A visually correct screenshot does not establish assistive-
  technology or linguistic correctness.

When text is sacred, quoted, or culturally consequential, use approved source
text and human language/cultural review. Do not synthesize plausible Hebrew or
use it as decorative texture.

## Source review matrix

Check, as applicable:

- no hard-coded user-facing strings remain in localized components;
- `lang` and `dir` follow the active route rather than a build-time default;
- physical left/right CSS does not break supported bidirectional layouts;
- interpolation and plural branches cover all target-locale categories;
- dates, numbers, currencies, names, addresses, and sorting use locale-aware
  data rather than hand-built strings;
- metadata, alternate-language links, errors, notifications, emails, and
  accessible names follow the same locale contract;
- fallback content is visible and truthfully labeled where incompleteness
  matters.
- Hebrew and mixed-direction samples preserve logical order, punctuation,
  isolation, selection, copy/paste, and expected accessible reading.

## Rendered and behavioral matrix

Use representative short and long content for every supported locale and
script, with coverage proportional to its routes and risks. Inspect the widths,
zoom, text spacing, navigation, tables, forms, dialogs, messages, charts,
truncation, mixed-direction values, reading order, font failure, and language-
switch behavior that can change a real task. Do not invent or ship a locale
merely to satisfy a stress-test category. When useful, an explicitly labeled
non-shipping pseudolocale may expose expansion or direction assumptions; it is
engineering evidence, not translated or culturally reviewed content.

Record which locales, routes, content states, browsers, assistive technologies,
and formatting cases were actually checked. Machine translation, pseudolocale
testing, automated screenshots, and lint rules are useful evidence, not human
linguistic or cultural validation.
