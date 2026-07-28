# Localization and bidirectional interfaces

Use this when a route supports more than one locale, translated content,
locale-aware formatting, right-to-left direction, or a language switcher. Do
not claim localization from a mirrored screenshot or translated paragraph.

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
- Confirm font coverage, fallback metrics, line breaking, hyphenation,
  diacritics, shaping, numerals, and punctuation for every shipped script.
- Keep validation, status, empty, error, permission, and recovery messages in
  the same locale as the task.

A language switch must be named in each available language, keyboard operable,
and understandable without flag-only labels. Define whether it preserves the
route, query, form state, focus, scroll, and history; do not silently discard an
in-progress task.

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

## Rendered and behavioral matrix

Use representative short and long content in each script. Inspect narrow,
intermediate, wide, zoomed, and text-spaced states; navigation, tables, forms,
dialogs, toasts, charts, truncation, and mixed-direction values; keyboard and
screen-reader order; font loading failure; and language switching during a
real task. Include at least one locale whose expansion, grammar, and direction
stress different assumptions from the source locale.

Record which locales, routes, content states, browsers, assistive technologies,
and formatting cases were actually checked. Machine translation, pseudolocale
testing, automated screenshots, and lint rules are useful evidence, not human
linguistic or cultural validation.
