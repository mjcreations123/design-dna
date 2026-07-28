# Typography and textual emphasis

Use this when choosing type, changing an established type system, or styling prominent copy.

## Preserve before replacing

Keep an established brand or product typeface when it remains legible, licensed, complete, and coherent. Do not replace it merely to look less conventional.

For greenfield work, select from voice and reading conditions:

1. Write three to five adjectives that describe the intended voice and exclude near-misses.
2. Gather representative copy: longest heading, paragraph, labels, numbers, prices, dates, and needed scripts.
3. Shortlist credible families with known provenance, licensing, weights, language coverage, and web delivery.
4. Compare rendered specimens in the actual layout.
5. Choose the candidate that best serves voice, hierarchy, reading, performance, and maintenance.

Read the dated [type-convergence watch](../../policy/type-convergence-watch.yml) for greenfield public-facing identity work. It is a research prompt, not a blacklist. If a watched family is the best fit, use it deliberately and make the surrounding system project-specific.

## Define roles

Specify the roles the product actually needs, such as:

- display or page title;
- section heading;
- body and long-form reading;
- label, metadata, caption, and helper text;
- control text;
- code, tabular number, or data label.

For each role, define family, weight, size behavior, line height, tracking, measure, and fallback. Avoid creating a new typographic voice for every component.

## Emphasize meaning

Apply the prominent-copy default and its canonical exceptions from
[owner defaults](../../policy/owner-defaults.yml). Changing a wrapper, span,
line, or component does not create meaning. When an exception applies, encode
and document the actual brand, link, status, data, quotation, product, or
editorial role rather than styling by position.

Prefer:

- stronger wording;
- syntax-aware line breaks;
- scale, weight, spacing, or measure;
- a meaningful whole phrase;
- semantic markup and state styling.

Preserve explicit accessible brand treatments and genuine semantic distinctions. Ensure links and states remain recognizable without color alone.

## Implement responsibly

- Self-host or use a reputable delivery source with clear rights.
- Subset only after confirming required scripts, symbols, and future content.
- Request only weights and styles that ship.
- Provide metric-compatible or carefully tuned fallbacks.
- Preload only critical files.
- Use `font-display` appropriate to the experience.
- Prevent faux bold, faux italic, invisible text, and avoidable layout shift.
- Prefer variable fonts when they reduce files without increasing complexity.
- For variable fonts, choose and test only axes the design uses. Verify default
  and extreme instances, optical sizing, weight/width interpolation, browser
  support, fallback, and whether subsetting preserves required variation data.
- Use OpenType features for a content role—such as tabular figures, fractions,
  localized forms, or code legibility—not as invisible decoration.

## Proof

Review real copy at narrow, intermediate, and wide widths. Test:

- fallback before the webfont loads;
- missing glyphs, diacritics, currency, and numerals;
- heading wraps and orphaned fragments;
- long labels and localization expansion;
- browser zoom and text-spacing overrides;
- tabular data and alignment;
- optical-size and variable-axis behavior at actual rendered sizes;
- contrast at every weight and size;
- measured font transfer and layout shift.

Record why the selected family won. Do not claim originality from font rarity.
