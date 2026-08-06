# Iconography

Use this when symbols, illustrations, marks, or pictorial controls communicate
actions, navigation, state, categories, concepts, atmosphere, or identity.

## Decide the role from context

An icon can aid recognition, support scanning, preserve continuity, teach a
metaphor, create character, carry ornament, or contribute to a larger visual
language. Text, icon, image, gesture, or a combination may be the right form.
Consequential or unfamiliar actions still need a label or explanation that the
intended audience can understand.

Do not maintain an ingredient blacklist. Emoji, familiar library symbols,
custom marks, detailed illustrations, text glyphs, animated symbols, and
decorative motifs can all be valid. Judge whether their meaning, cultural
implication, originality, rights, rendered quality, and frequency support the
project's creative logic.

## Define the system that the work needs

Document the relevant `creative_logic`, evidence, decisions, limits, and open
extensions. Decide which properties should be shared and which may vary. Those
properties might include construction, optical size, stroke, fill, material,
color, dimensionality, animation, metaphor, or another project-specific
quality, but there is no required inventory.

One visual grammar is not universally preferable. A product may need a highly
consistent control set, distinct families for different contexts, or a
deliberate collision of symbolic languages. Coherence can come from role,
placement, behavior, provenance, or art direction rather than identical
geometry. Preserve useful irregularity and commissioned one-offs when their
difference is meaningful.

Select or create symbols for the real concepts. Do not ship a library's demo
selection unchanged unless it genuinely fits. Custom work is not automatically
better than an established symbol, and familiarity is not automatically
generic.

## Make meaning and operation robust

- Give icon-only controls an accessible name and a visible explanation where
  recognition is uncertain or the action is consequential.
- Keep decorative symbols out of the accessibility tree unless their presence
  conveys meaning that must be described.
- Expose selected, expanded, pressed, busy, invalid, and disabled states
  programmatically when those states exist.
- Make the operable target appropriate to the input context independently of
  the glyph's visible bounds.
- Do not rely on color, shape, position, animation, or sound alone when a state
  or action must be understood.
- Provide non-hover and non-gesture paths, and preserve focus behavior.

If symbols vary by locale, culture, platform, or direction, verify the intended
meaning with appropriate reviewers. Mirroring, replacement, or retaining the
original orientation should follow meaning rather than a blanket RTL rule.

## Review the rendered result

Start with an unprimed observation of the actual interface. Then verify the
symbols in the combinations where risk exists: with and without labels,
beside actual type, at rendered sizes, under zoom and forced colors, across
supported themes, inputs, locales, states, and assistive technology.

Ask whether users can recognize and operate the experience, whether decorative
or expressive symbols feel intentional, and whether repeated or mixed icon
families support the declared creative logic. Record concrete ambiguity,
inconsistency, rights, rendering, or accessibility failures. Do not reject a
symbol merely because it is popular, ornamental, custom, playful, or drawn in
a different style from another family.
