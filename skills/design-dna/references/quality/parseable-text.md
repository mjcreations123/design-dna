# Parseable text

Every visible string must earn its place. This file exists because the
owner's single most repeated rejection, across four separate projects, is
text on the page that a visitor cannot parse: decorative readouts, mono
micro-labels, internal vocabulary, numbers pretending to be data. His words:
"random text in the middle of nowhere that doesn't make sense and is just an
eyesore." Tufte named the mechanism in 1983: ink whose purpose is to make
the surface LOOK precise without carrying information.

This is an owner ABSOLUTE (see [absolutes](../../policy/absolutes.md)). The
gate below runs on the RENDERED page, in every state, at every breakpoint,
on every build and revision round.

## Contents

- [The four-question gate](#the-four-question-gate)
- [The five string classes](#the-five-string-classes)
- [Named bans from this studio's record](#named-bans-from-this-studios-record)
- [Copy carries information the visuals cannot](#copy-carries-information-the-visuals-cannot)
- [Residue vocabulary sweep](#residue-vocabulary-sweep)
- [The review pass](#the-review-pass)

## The four-question gate

For EVERY visible text node, in order:

1. **MEANING.** Can a first-time visitor say what this string tells them or
   lets them do? If the honest answer is "nothing, it is decoration
   pretending to be information," it fails.
2. **TRUTH.** If it looks like data (number, coordinate, timestamp, version,
   status, price), is it real, and does it stay correct without manual
   upkeep? A pulsing dot on static content, a fake terminal caret, a
   coordinate that matches nothing: fail.
3. **AUDIENCE.** Is every word one this business's customer would use about
   the business? Codebase vocabulary (component names, state names like
   idle/active, mode labels, internal codenames, skill jargon) fails.
4. **COST OF DELETION.** Delete it mentally. Did the visitor lose anything?
   If nothing is lost, the string goes, or is folded into the adjacent
   heading, or is replaced by one true specific fact that survives the same
   test.

A string must pass all four or be removed, made real, or rewritten.

## The five string classes

Legitimate: **action copy** (navigation, buttons, controls), **content
copy** (headings, body, captions that carry subject information), and
**authored marginalia** (a footnote or annotation that rewards reading with
a specific checkable fact).

Illegitimate: **decorative props** (fake telemetry, coordinates, serials,
"SYS.01", degree readouts, barcode strings, crosshair labels, blueprint
annotations on non-technical subjects) and **internal residue** (debug
counters, placeholder copy, unresolved tokens, developer vocabulary).

Decorative technical marks are permissible only when the subject genuinely
is technical, every mark is TRUE, and at most one or two appear per
viewport. Beyond that the aesthetic crosses into parody regardless of truth.

## Named bans from this studio's record

Each of these was rejected by the owner on a real build. Severity follows
[policy/absolutes.md](../../policy/absolutes.md): items backed by an
ABSOLUTE run inside the P0 parseable-text pass of the
[preship gate](../../templates/preship-gate.md); items in the HARD tier are
enforced at P1 and lift only by logged client direction.

P0 (ABSOLUTE-backed, never lifted):

- **Decorative pseudo-data.** HUD readings, coordinates, serials,
  telemetry, tick-marked ledes, stamps, registry micro-chrome in margins or
  letterbox bars. "What are they even doing there."
- **Fake liveness.** Pulsing status dots, "ONLINE" badges, ticking
  counters, streaming logs on static content. Animate only what real data
  changes.
- **Strings below the size floor.** The canonical floor lives in the
  [typography numbers](../craft/typography.md#the-numbers): list every
  rendered string under 12px and justify each one's information value;
  unjustified strings are deleted, not shrunk. Nothing below 11px except
  legally required fine print.
- **Claim repetition.** A claim stated more than twice on one page is
  noise. A "too busy" complaint triggers a repetition count before any
  motion change.

P1 (HARD-tier, liftable only by logged client direction):

- **Mono micro-label chrome** outside code and data (HARD 6).
- **Ordinal decoration on parallel items.** 01/02/03 kickers, index glyphs,
  dots, and slashes on cards or categories that are not a genuine sequence
  (HARD 7).
- **The eyebrow template.** The same kicker construction above three or
  more sections with no taxonomy, sequence, or navigation job (HARD 3). If
  the eyebrow contains no word absent from the heading below it, delete it
  or merge the one useful word into the heading.

## Copy carries information the visuals cannot

No sentence may describe what the visitor is already looking at. Every text
block adds subject information the visuals cannot carry: what it is, what
it does, what it costs, what happens next. Scenery narration is filler even
when beautifully written.

Strip self-descriptors: premium, luxury, world-class, high-end. Demonstrate,
never claim. If a headline could sit unchanged on ten other products, the
typography cannot save it; rewrite the words first.

Write from checkable specifics: real nouns, prices, street names, people,
dates. Every major section carries at least one fact only this business
could state. Take one side per page: a stated preference, a limit, an
honest constraint ("closed Mondays") reads human where inoffensiveness
reads generated. Vary sentence shape: follow a long sentence with a
fragment, and when lists keep landing in threes, restructure some to one,
two, or four items. Ship an FAQ entry only when it answers a question a
real customer asked, with a fact the owner confirmed; an answer with no
number, price, or policy in it is deleted. Keep real quotes verbatim with
their irregular phrasing. Irregularity comes from real voice kept intact,
never from manufactured typos, slang, or planted awkwardness.

## Residue vocabulary sweep

Grep the RENDERED text of every page and state, including empty, loading,
error, and hidden accordion panels, plus alt text and meta descriptions:

- Placeholder: `lorem`, `ipsum`, `dolor`, `coming soon`, `under
  construction`, `TODO`, `TBD`, `FIXME`, `asdf`, `placeholder`, `sample
  text`, `your text here`
- Binding leaks: `undefined`, `NaN`, `null`, `[object Object]`, `{{`, `}}`,
  `${`, `%s`, `Infinity`, raw JSON braces
- Encoding: the mojibake signature, grepped with the encoding-proof
  spelling `[\xC2\xC3\xE2]` (ripgrep) so the pattern itself survives any
  console encoding, plus the replacement character; expect rare false
  positives on legitimate French or Portuguese text and clear them by eye
- Owner copy bans: the em dash character in any user-facing file
- AI-era phrases, compiled 2026-08, review by 2027-02 (the vocabulary is
  era-dated and shifts per model generation; refresh, never trust the 2023
  list): `elevate`, `seamless`, `unlock`, `empower`, `delve`, `leverage`,
  `streamline`, `supercharge`, `in today's fast-paced`, `look no further`,
  `nestled in the heart of`, `commitment to excellence`, `it's not just`,
  `isn't just`. A hit is a rewrite trigger, not proof; the cluster
  diagnosis lives in [convergence-watch](../convergence-watch.md)
  RISK-COPYFORM-001. This grep list is its mechanical arm.
- Paste artifacts from model output: `oaicite`, `contentReference`,
  `turn0search`, `[cite:`, `utm_source` inside body links, stray `**` and
  `#` markdown residue, curly-quote inconsistency

Any hit is a ship blocker. These are mechanical greps the workflow actually
runs; a rule that exists only as prose gets violated.

## The review pass

1. Extract every visible string per page per state (a DOM walk, not the
   source).
2. Run the residue greps.
3. Apply the four-question gate to every string; log verdicts for anything
   borderline.
4. Count repeated constructions: identical eyebrow templates, identical
   claims, identical strings inside one component.
5. Salience check on the screenshots: name the first three things noticed
   at each breakpoint. If any is a decorative string rather than the
   headline, the imagery, or the action, the decoration outranks the
   content and is reduced or cut.
6. Fix, re-render, re-check. The pass is complete when every surviving
   string has a job a visitor could name.
