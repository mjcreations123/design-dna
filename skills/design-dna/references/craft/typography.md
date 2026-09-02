# Typography

Use this when choosing type, changing an established type system, styling
prominent copy, or closing a build. Typography is both an expressive medium
and a delivery system. Judge the family, roles, spacing, language, layout,
loading, fallback, and surrounding composition together.

There is no universal set of "AI fonts," approved fonts, forbidden fonts,
pairing categories, family count, hosting method, scale ratio, or tracking
formula. A common face may be exactly right; a rare face may be arbitrary.
The failure is an unexamined or poorly executed system, not a family name.

## Contents

- [Choose type for beauty and brand fit](#choose-type-for-beauty-and-brand-fit) |
[Start from the reading situation](#start-from-the-reading-situation)
- [Choose roles, not a recipe](#choose-roles-not-a-recipe)
- [Compare enough to make a real decision](#compare-enough-to-make-a-real-decision)
- [Tune spacing and hierarchy in the render](#tune-spacing-and-hierarchy-in-the-render)
- [Treat emphasis as meaning](#treat-emphasis-as-meaning)
- [Deliver fonts deliberately](#deliver-fonts-deliberately)
- [Proof real language and mixed direction](#proof-real-language-and-mixed-direction)
- [Audit delivery and provenance](#audit-delivery-and-provenance)
- [Verify the delivered type system](#verify-the-delivered-type-system)

## Choose type for beauty and brand fit

A typeface earns its place on a public site for two reasons only: it is
beautiful in the render, and it fits this brand and audience. Two families at
most, and the producer must be able to defend each one on its own, with no
reference to justify it. Never choose a face because a reference site used
something like it, and never answer a reference's licensed font with a
monospace, pixel, novelty, or display face as a substitute; the answer is a
free face of the same quality, a license, or dropping the element. The
studio's own tell records apply before any reference does. This is the owner's
law of 2026-09-02, after a rebuild shipped a pixel title and a monospace
label face copied from a manual-style reference.

## Start from the reading situation

Before naming a face, establish the actual conditions:

- audience, language, script, familiarity, accessibility needs, and devices;
- content roles, reading duration, density, tone, and highest-value message;
- approved brand or product continuity and the degree of expressive freedom;
- real headline lengths, names, numbers, punctuation, controls, and data;
- performance, privacy, licensing, redistribution, maintenance, and fallback
  constraints;
- owner feedback about voice, age, crowding, small text, or sameness, scoped
  to the exact work that caused it.

Record a short type brief in project language. Examples of useful criteria
are warm without nostalgia, fast scanning under pressure, comfortable Torah
study in Hebrew and English, or mechanical without pretending to be code.
These are examples, not selectable presets.

## Choose roles, not a recipe

Define only the roles the content needs. A project may use one family across
every role, several related voices, a system stack, a custom face, variable
axes, lettering, or no conventional display role. Pairing is optional. A
system font can be an intentional identity decision, not an automatic sign of
missing design.

For every consequential role, decide:

- what the role must communicate or help someone do;
- which face, style, weight, width, optical size, case, and punctuation serve
  it;
- how it relates to adjacent roles in scale, rhythm, contrast, and density;
- how it changes with content, width, language, zoom, and user settings;
- what fallback remains acceptable and what evidence will prove it.

Use hierarchy to express information value. Adjacent levels need enough
perceptible difference to remain distinguishable, but size, weight, width,
case, color, placement, spacing, and motion are all available. Do not force a
fixed modular scale or family count when another system reads better.

## Compare enough to make a real decision

When type is open or the owner has rejected the fonts, render enough credible
possibilities to expose the consequential difference. Use the longest real
headline, ordinary paragraphs, navigation, controls, numbers, punctuation,
and every required script inside the intended composition.

The comparison may contain several families, one family with different
settings, an established brand option against a repair, or a system-stack
continuity option. Its size follows uncertainty. Record the selected option,
the strongest alternative or tension considered, and the project-specific
reason the choice won. Do not require a named number of rejects.

Do not consult a portable font blacklist or dated recommendation bench. When
owner-authorized cross-project history exists, compare the rendered system
with recent work only after the candidate exists. Repetition is a prompt to
ask whether producer habit displaced project fit; it is not an automatic
veto.

Do not treat a new font as a cosmetic rescue for a rejected direction. When the
whole page feels ugly, generic, artificial, or wrong, inspect how type behaves
with subject material, composition, hierarchy, public voice, and media before
swapping families. A change of face can be the right root correction when the
role itself is wrong; it cannot make an unrelated public proposition feel
considered by itself. Use [taste calibration](taste-calibration.md) when the
owner's objection is to the rendered answer rather than a clearly isolated type
role.

## Tune spacing and hierarchy in the render

No numerical value fails merely for falling outside a house range. Use real
copy and evaluate the relationships at the widths and settings that ship.

Inspect:

- **Letter spacing:** collisions, clogged counters, broken ligatures, loose
  lowercase body text, over-tracked labels, and compressed words. Large type
  may tolerate tighter spacing than small text; judge the actual face and
  language rather than copying a universal value.
- **Line spacing:** whether adjacent lines remain distinct without breaking
  the intended texture. Test ascenders, descenders, diacritics, wrapped links,
  and mixed scripts.
- **Measure:** whether reading becomes tiring, choppy, or visually detached
  from the composition. Responsive measure may change by role.
- **Scale:** whether the largest type answers the first important question and
  whether ordinary reading and controls remain comfortably legible.
- **Weight and style:** whether requested files or variable-axis ranges exist,
  whether synthesis occurs, and whether emphasis survives on the real
  background.
- **Wrapping:** intentional breaks, widows, orphaned fragments, hyphenation,
  narrow columns, localization expansion, and text-spacing overrides.
- **Label/value separation:** whether repeated metadata, facts, legends, or
  compact controls keep the label and value perceptibly distinct at the real
  narrow width. A fixed label track can silently become shorter than the
  longest actual label; verify content-aware spacing, wrapping, localization,
  and text-spacing overrides without prescribing one layout.
- **Descender clearance:** italic or swash display words containing y, g,
  j, p, or q clip against very tight leading, especially when the line box
  sits directly on a boundary. Audit every italic display word in the
  render and reserve the leading or padding the descenders actually need;
  the clip is measurable from glyph boxes and invisible in the source.
- **Numerals and protected pairs:** choose tabular figures when comparison or
  column alignment benefits from equal-width digits; proportional figures may
  better fit prose, display work, or the selected face. Protect a value and
  unit, shortcut and key, or approved multi-word mark with a non-breaking space
  or local no-wrap only when a rendered wrap damages meaning, recognition, or
  use. Natural wrapping may be the safer choice at narrow widths or in expanded
  translations, so test the actual content rather than gluing every pair. An
  isolated final headline line, even a single word, is a post-render diagnostic
  prompt rather than an automatic defect. Keep it when the break creates
  intentional, convincing,
  project-supported rhythm, emphasis, or voice and remains legible through
  the relevant widths, languages, zoom, and text settings. Revise it only
  when rendered evidence shows that it reads as accidental, breaks the
  intended syntax or hierarchy, or fails under supported conditions. Do not
  apply `text-wrap: balance`, hard breaks, non-breaking spaces, forced type
  resizing, or container reshaping as an automatic repair; choose the
  smallest content or composition change that the observed failure supports.

Treat observed collisions, lost letterforms, exhausting density, unreadable
small text, or hierarchy that fails under actual content and user settings as
review evidence. Judge the role, audience, script, device, contrast, zoom,
text-spacing overrides, and rendered result; do not create a portable pixel,
tracking, leading, width-axis, or scale threshold. Legal text is not exempt
from readability.

Test at project-relevant narrow, intermediate, and wide widths, 200 percent
zoom, browser text-spacing overrides, and forced colors where applicable.
Fluid type must preserve zoom and hierarchy; avoid viewport-only formulas
that prevent text from scaling.

## Treat emphasis as meaning

A colored, italic, underlined, outlined, animated, or differently faced word
can be excellent. It becomes a generic tell when the gesture repeats without
a semantic, editorial, interactive, or brand reason, fragments reading, or
looks copied from an unrelated project.

Review emphasis in the full sentence and across the whole page:

- What relationship does the change express?
- Is that relationship understandable without relying on color alone?
- Does the treatment survive contrast, reflow, forced colors, and reduced
  motion?
- Does the page use the gesture consistently enough to communicate without
  turning every headline into the same trick?

Keep or remove it based on the rendered answer, not because a category is
fashionable or associated with generated sites.

## Deliver fonts deliberately

Choose self-hosted files, a trusted service, platform fonts, system fonts, or
another delivery path from rights, privacy, performance, resilience, tooling,
and maintenance evidence. No method is globally required.

For downloadable fonts:

- record source, license, redistribution rights, files, subsets, weights,
  styles, axes, and script coverage. Professional foundry libraries with
  free commercial licensing and privacy-conscious mirrors of common font
  CDNs are legitimate sources when budget or data-protection constraints
  apply; the license record is identical either way;
- when the direction's face is licensed and cannot ship, record the
  substitute mapping explicitly: the closest available face, the
  corrective settings that make it serve the role, and at least one named
  face that would not be an acceptable substitute, with the reason. A
  recorded mapping keeps future editors from silently degrading the role;
- load only what the rendered project uses and configure an appropriate
  `font-display` behavior; subset by script coverage where the license and
  tooling allow, so readers do not download alphabets the site never sets;
- preload only genuinely critical files and avoid duplicate variable-font
  binaries declared as separate downloads;
- set an intentional fallback and prevent unexpected faux bold or italic;
- test failure behavior and layout stability rather than assuming the CSS
  declaration is enough.

For system or platform fonts, record why continuity, density, latency,
privacy, regulation, or the chosen aesthetic makes that path appropriate.
Verify the actual platform/browser matrix relevant to the project and define
acceptable fallbacks.

Write text files as UTF-8 and inspect for mojibake after edits touching
punctuation or non-Latin scripts. Treat hits as encoding evidence to inspect,
not as a reason to prohibit punctuation.

## Proof real language and mixed direction

Build proofs from the content that will ship: the longest likely heading,
ordinary paragraphs, controls, navigation, names, numbers, dates, currencies,
punctuation, and every required script. Judge them inside the intended layout
beside actual media at the widths that change the composition.

When Hebrew or another right-to-left script appears, define its content job
before styling it. Follow current script-specific layout requirements and the
[localization contract](../quality/localization.md):

- mark language and base direction accurately;
- isolate embedded names, URLs, numbers, and dates deliberately;
- use logical properties and meaningful source order;
- inspect punctuation, numerals, wrapping, selection, and copy/paste in real
  mixed-language sentences;
- verify the required letters, marks, shaping, and diacritics in the actual
  files and fallback chain;
- never use an unfamiliar script as visual texture or invent sacred text;
- obtain accountable review for transliteration, sacred material, or
  culturally central language.

## Audit delivery and provenance

When Python 3.10+ is available, run the bounded source inventory:

```text
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/font_audit.py" "PROJECT"
```

`<DESIGN_DNA_SKILL_ROOT>` is the directory containing the installed
`SKILL.md`. The report inventories source contracts; it is not a browser
proof, license ruling, quality score, font blacklist, or authorship detector.
When present, `source_integrity_complete` means only that this bounded source
and file-inventory scan completed without its recorded incompleteness
conditions. It is not a rendered typography-quality pass and does not replace
the evidence below.

## Verify the delivered type system

After a build or a revision that affects type, choose evidence from the actual
claim and failure risk. Bind every observation to the browser, build, route,
state, width, and date. A CSS stack alone does not establish browser use, but
no single universal proof sequence applies.

Keep these evidence types separate:

- **Source inventory:** declared faces, files, descriptors, license record,
  subsets, axes, and fallback intent. This shows configuration, not browser
  selection.
- **Browser availability:** `document.fonts`, `document.fonts.ready`, and
  explicit load checks for consequential downloadable combinations. This can
  establish registration or availability, not which face painted every glyph.
- **Computed styling:** family stack, size, weight, style, leading, tracking,
  language, and direction for selected roles. Computed `font-family` reports a
  request, not glyph-level face selection.
- **Delivery evidence:** requested URLs, status, MIME type, decoded bytes,
  cache/service behavior, CORS/CSP, and console errors when network delivery is
  material.
- **Metric differential:** canvas or layout measurements against chosen
  fallbacks can show that metrics changed. Similar metrics can collide, so call
  this indirect evidence rather than paint proof and use real project strings
  and scripts when it matters.
- **Synthesis and axis evidence:** compare consequential requested
  weight/style/axis combinations with registered descriptors when faux or
  nearest-match substitution could change meaning or identity. Do not require
  an exhaustive matrix when the project does not use it.
- **Rendered layout:** inspect real wraps, line boxes, clipping, overflow,
  hierarchy, scripts, and emphasis at the conditions that can change them.
- **Fallback rehearsal:** when failure is material, block or disable the real
  downloadable path, verify that the failure actually occurred, and inspect
  readability, content visibility, and layout stability.
- **Visual inspection:** open the final captures and inspect voice, spacing,
  line breaks, descenders, mixed scripts, and the complete hierarchy. Repeat
  under zoom, text-spacing, or platform conditions that are relevant.

Use stronger browser or specialist instrumentation when a claim requires
glyph-level face identification; the bundled rendered reviewer does not prove
it. Record exact failures and revisions without upgrading indirect evidence to
a stronger claim.

A font-loading defect blocks only the type-delivery or visual claim it affects;
it does not imply that every project must use a downloadable display face.
