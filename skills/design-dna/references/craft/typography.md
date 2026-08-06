# Typography

Use this when choosing type, changing an established type system, styling
prominent copy, or closing a build. Typography is where this studio's work
has failed most often, so this file ends in a mandatory verification protocol:
a build is not done until the intended fonts are proven to have painted.

The three causes of every "terrible fonts" verdict on record, in order of
frequency:

1. **The face was never chosen.** A system stack (Segoe, Aptos, Arial,
   system-ui) or one neutral grotesk carried the whole page, so the render
   looked like an unstyled OS dialog. Competent hierarchy cannot rescue an
   unchosen voice.
2. **The chosen face never painted.** A CDN failed, a specificity bug ate the
   size rule, a weight was missing and the browser synthesized it. CSS said
   one thing, the pixels said another, and nobody looked.
3. **The numbers were wrong.** Tracking, leading, measure, or scale outside
   the ranges that read as professional.

Every section below exists to kill one of those three.

## Contents

- [Choose a voice on purpose](#choose-a-voice-on-purpose)
- [The pairing procedure](#the-pairing-procedure)
- [The dated bench](#the-dated-bench)
- [The numbers](#the-numbers)
- [Fluid type](#fluid-type)
- [Inks versus graphics](#inks-versus-graphics)
- [Ship fonts like an engineer](#ship-fonts-like-an-engineer)
- [Motion and masking laws](#motion-and-masking-laws)
- [Proof real language in the real composition](#proof-real-language-in-the-real-composition)
- [Proof Hebrew and mixed-direction type](#proof-hebrew-and-mixed-direction-type)
- [Audit delivery and provenance](#audit-delivery-and-provenance)
- [MANDATORY: verify the rendered font](#mandatory-verify-the-rendered-font)

## Choose a voice on purpose

Every Persuade or Experience surface MUST declare a deliberate display voice
distinct from its body face. A system stack as the rendered display face is
an automatic fail on those surfaces; a system stack is permissible only for
dense Operate UI, by written decision.

Selection is a decision with named rejects, never a reach:

1. Write three to five voice adjectives derived from THIS client's world, and
   the near-misses they exclude.
2. Shortlist three or more credible candidates. Set the longest real headline
   and a real paragraph in each, at real sizes, and look.
3. Record the winner, the two strongest rejects, and why the winner fits this
   client. If the justification would fit any client in the vertical, it is
   not a choice yet.
4. Diff against the [ledger](../quality/ledger.md): the display family MUST
   NOT repeat from the previous build, and no two builds in one batch may
   share a family.

The owner's recorded taste, learned from three rejection rounds: the reliable
target is a **characterful grotesk at confident weight, mixed case**. The
three recorded failure directions: bookish old-style serifs read
old-fashioned; neutral defaults (Geist, Inter, Archivo as display) read
unstyled; quirky display faces (Unbounded, Syne class) read vibe-coded.
Verticals may override with their own character (a wedding shop earned an
elegant serif); the audience must always be able to read it. Character never
at the cost of legibility: no script faces or high-contrast Didones for
body-adjacent or navigational text, and every display choice names the
audience and why they can read it.

A familiar face is not automatically generic and an unusual face is not
automatically good. The tell is the absence of decision. Preserve an
established, authorized brand typeface that still serves the work.

## The pairing procedure

One face leads, one supports. Subtle differences look like accidents; clear
differences look like design.

1. Choose the display face for voice (previous section).
2. Choose the body face from a DIFFERENT construction model with similar
   proportions: high-contrast serif display over neutral grotesk body,
   characterful grotesk display over quiet humanist body. Never two similar
   sans or two similar serifs.
3. The body face must be a proven workhorse: multiple real weights, true
   italics, open apertures, x-height around 60 to 75 percent of cap height,
   no clotting in a squint test at 16px.
4. Sanity-check x-height compatibility: set both at 16px and compare
   lowercase x heights; over ~15 percent mismatch needs size compensation.
5. Two families maximum. A third requires a distinct recorded role (true
   code, tabular data) and its own loading budget. One variable family with
   well-used axes often beats two static families.

## The dated bench

Compiled 2026-08. A starting bench, not a whitelist: leaving it costs one
recorded sentence. Named lists decay (Instrument Serif went from
recommendation to tell in about a year), so re-verify this list against
current discourse after mid-2027 and date any replacement.

**Burned in this studio** (ledger-repeated or discourse-saturated; require a
HARD-tier justification): Inter as display, Space Grotesk, Geist, Archivo,
Schibsted Grotesk, the Clash Display + Switzer pairing, Instrument Serif
italic heroes, Playfair Display heroes, Poppins, Montserrat.

**Characterful grotesks (display):** Bricolage Grotesque (passed owner
review), Cabinet Grotesk, General Sans at heavy weights, Familjen Grotesk,
Hanken Grotesk at black, Anybody, Archivo Expanded variants only with a
recorded reason. **Serifs with drawing (display or editorial):** Fraunces
(passed for wedding vertical), Gambetta, Erode, Sentient, Boska, Zodiak.
**Quiet bodies:** Switzer (body only), General Sans, Supreme, Ranade, Jost
(passed), Be Vietnam Pro, Source Sans 3. **Mono, code and data only:**
JetBrains Mono, Martian Mono, Spline Sans Mono.

Free tiers: Fontshare and uncut.wtf before the Google Fonts top ten. For
identity-bearing client work with budget, real foundries outrank all of the
above: Klim, Commercial Type, ABC Dinamo, Grilli Type, Displaay, Pangram
Pangram, OH no Type.

## The numbers

Floors and ranges, checkable from computed styles. Deviations demand rendered
proof, not intent.

| Property | Rule |
| --- | --- |
| Body size | 16 to 21px; nothing anywhere below 14px except legally required fine print, and never below 11px |
| Body line-height | 1.4 to 1.6, unitless, rising with measure (60-75ch wants 1.5-1.7) |
| Measure | 45 to 75ch target on desktop, 30 to 40ch on phones; max-width roughly 30x body px size |
| Heading line-height | 0.95 to 1.25, falling as size rises; a multi-line H1 at body leading is a named amateur tell |
| Display tracking | 0 to -0.03em at 48px+, to -0.04em at 80px+ for tight grotesks; NEVER below -0.05em; NEVER negative below 32px |
| Uppercase tracking | +0.05em to +0.12em, always positive; uppercase limited to labels of a few words, never sentences |
| Lowercase body tracking | 0; positive tracking on lowercase body only below ~12px |
| Scale | 3 to 5 sizes from one ratio (dense UI 1.2, general 1.25, landing 1.333 to 1.5); hero-to-body ratio 2.0+ on landing pages |
| Hierarchy | adjacent levels differ on at least TWO axes (size + weight, size + case); same size in two weights within one role is a broken system |
| Weights | one weight per role; load every weight and style the CSS uses; `font-synthesis: none` as a tripwire |
| Alignment | left for reading text; centered only up to 3 lines; justify only with `hyphens: auto`; no pure #000 on #FFF for long-form |
| Emphasis | italic OR weight, never both on one run; underline is for links only; under ~10 percent of any paragraph |
| Punctuation | curly quotes in prose; `text-wrap: balance` on headings; no em dashes anywhere user-facing (owner ABSOLUTE) |
| Size follows value | the biggest type goes to the highest-value information; a scale effect that demotes the primary answer below 16px loses |

## Fluid type

- clamp() belongs on display text with 8px+ of range; body stays fixed 16 to
  19px or one breakpoint bump.
- Every clamp() derives from two explicit anchors and is written as rem
  bounds with a rem + vw preferred value. A bare `Nvw` preferred value breaks
  browser zoom and fails WCAG 1.4.4.
- Verify numerically at 320, 375, 768, 1440, 1920: monotonic, inside bounds,
  and the hierarchy never inverts (h1 > h2 > body at every width).
- On phones, headings shrink 30 to 50 percent while body holds or grows.

## Inks versus graphics

Split every palette at token time into INKS (text and text-bearing fills,
4.5:1 minimum on their real surfaces) and GRAPHICS (borders, icons, decor,
3:1 minimum). One hex MUST NOT hold both jobs; a brand accent used on text
gets a purpose-built darker ink variant. This studio has shipped the same
failure three times; the token split is the fix.

Text over photography or gradients requires a scrim or plate sized to the
text block, verified by sampling the rendered composite pixels behind the
actual glyphs. Token arithmetic cannot see a pale window behind a headline.
If the photo can change, the scrim alone must guarantee the floor.

## Ship fonts like an engineer

- **Self-host every face** as subsetted woff2 in the repo, same origin. A
  third-party fonts CSS link is a defect unless the client requires it. CDNs
  fail under ad blockers, firewalls, and outages, and the failure is silent.
- `<link rel="preload" as="font" type="font/woff2" crossorigin>` for the one
  or two above-the-fold faces. The `crossorigin` attribute is mandatory even
  same-origin; without it the font downloads twice.
- `font-display: swap` for identity faces; `optional` only for decorative
  flourishes whose fallback is acceptable forever.
- Ship a metric-compatible fallback: a second @font-face over `local()` with
  `size-adjust`, `ascent-override`, `descent-override` tuned so a failed load
  does not move layout. Verify by blocking the font and comparing heights.
- Subset against the site's real corpus including punctuation, curly quotes,
  diacritics, and currency; a probe string can pass while the headline's
  apostrophe paints in the fallback.
- Maximum 4 font files or 1 to 2 variable files; woff2 only.
- On Windows, write files as explicit UTF-8 and grep shippable files for the
  mojibake signature `[ÂÃâ]` after any edit touching typographic punctuation.

## Motion and masking laws

Learned on this studio's own builds:

- Never CSS-transition `font-weight` or `font-variation-settings` on text
  that animates or scrubs; snap the axis under a paint-cheap cover.
- Text-fitting code must suppress transitions while measuring, must not read
  back its own previous inline value as a baseline, and must solve against
  advance width minus trailing tracking.
- Any masked or clipped text reveal gets descender slack: padding-bottom
  ~0.2em with compensating negative margin, mask sized ~1.3em for roll
  reveals. Verify with a deep-descender test string ("yes, giddy typography
  jumps") at rest and mid-animation.

## Proof real language in the real composition

Build specimens from content that will ship: the longest likely heading,
ordinary paragraphs, controls, navigation, names, numbers, prices, dates,
punctuation, every required script. Judge inside the intended layout beside
its actual media, at narrow, intermediate, and wide widths. Inspect crowded
joins, clogged counters, kerning collisions in rendered headlines (AV, Wa,
To pairs), line breaks, widows, and how the composition recomposes on a
phone. A desktop poster lockup must not collapse into crowded fragments at
375px. Test browser zoom at 200 percent, text-spacing overrides, and
forced-colors mode.

## Proof Hebrew and mixed-direction type

When Hebrew appears, define its content job before styling it: locale,
isolated term, parallel translation, quotation, and sacred text carry
different direction, line-breaking, and review requirements. Follow the
current W3C Hebrew Layout Requirements and the
[localization contract](../quality/localization.md):

- tie base direction to the active locale; mark passages with accurate
  `lang` and `dir`;
- isolate embedded names, URLs, numbers, and dates with deliberate
  bidirectional markup;
- use logical properties and meaningful source order;
- inspect punctuation, numerals, wrapping, selection, and copy/paste in real
  mixed-language sentences;
- verify every required letter, mark, and diacritic exists in the actual
  files and fallbacks; proof shaping and mark placement at shipping sizes;
- never treat the script as visual texture, and never invent sacred text;
- verify transliteration and sacred material with an accountable authority,
  plus the [cultural-context review](../quality/cultural-context-review.md)
  when lived identity is central.

## Audit delivery and provenance

Inventory what the browser is asked to load and what actually ships: source,
license, redistribution rights, formats, subsets, weights, styles, axes,
required scripts, fallback order, preload and failure behavior. Do not infer
rights or glyph coverage from a family name. Do not ship unused weights.

When Python 3.10+ is available, run the bounded source inventory:

```text
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/font_audit.py" "PROJECT"
```

The report is source evidence only. It is not a browser proof, license
ruling, glyph test, or authorship detector. Rendered proof comes from the
protocol below.

## MANDATORY: verify the rendered font

Run this after every build and every revision that touches type, in the real
browser, before any ship claim. Steps 1 through 7 are loader- and
layout-level APIs that work even in a hidden automation tab; only the final
screenshot needs a visible pane. Two traps make the obvious checks lie:
`document.fonts.check()` returns true for typo'd and system families, so it
is only ever a negative signal; and `getComputedStyle().fontFamily` reports
the requested stack, never the face that painted.

1. **Registration proof.** For every (family, weight, style) the CSS uses:
   `const faces = await document.fonts.load('<style> <weight> 16px "<Family>"')`.
   An empty array is the deterministic detector for a family-name or weight
   mismatch. Require `faces.length > 0` and every status `loaded`.
2. **Paint proof.** Canvas width comparison with a width-diverse probe AND
   the site's real headline string:
   `ctx.font='72px monospace'` vs `'72px "Family", monospace'`; widths must
   differ. Repeat against serif as a second baseline. Equal widths mean the
   fallback painted, whatever the CSS says.
3. **Synthesis proof.** Enumerate every (family, weight, style) combination
   in computed styles; each must map to a loaded face covering that weight
   and style. CSS 700 over a loaded 400 means faux bold is on screen.
4. **Network proof.** `performance.getEntriesByType('resource')` contains
   every expected font URL with transferSize > 0 or a cache hit. Zero font
   entries on a page declaring webfonts means the fonts never applied.
5. **Console proof.** Zero messages matching "Refused to load the font",
   CORS, or 404 on font URLs.
6. **Computed-size proof.** For each type role (hero, section head, body,
   caption) assert `getComputedStyle().fontSize` at 360, 768, and 1440
   against the intended values. A hero whose computed size equals the
   generic heading size means a specificity bug ate the rule; this exact bug
   shipped on this studio's own showpiece.
7. **Fallback rehearsal.** Block the font origin or toggle the faces off,
   reload: layout must not collapse, the deliberate fallback must be
   readable, and heights must match within CLS tolerance.
8. **Look.** The ~1440 and ~375 screenshots from the
   [preship gate](../../templates/preship-gate.md), opened and examined:
   does the display voice read as chosen, are descenders intact, is any
   text clipped, does the hierarchy read at arm's length?

A failure at any step is a build failure. Fix the loading, the file, or the
CSS; never ship the fallback silently and never downgrade the check to the
declared stack.
