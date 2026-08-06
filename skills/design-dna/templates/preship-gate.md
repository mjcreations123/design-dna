# Preship gate

Copy this checklist into the working response and tick every line. Run it on
every build and every revision round, on the RENDERED output. Do not present
the result until every P0 passes; a P0 hit is fixed and re-verified, never
waived. P1 items are fixed or shown to carry a logged client direction.

## P0: owner absolutes

- [ ] Zero em dashes in user-facing text (mechanical grep of shippable
      files and rendered DOM)
- [ ] Zero animated number count-ups
- [ ] Zero fabricated stats, testimonials, reviews, logos, people; every
      demo stand-in visibly labeled AND present in the placeholder register
- [ ] No indigo-violet gradient kit; no gradient text
- [ ] No fake product UI (div dashboards, invented metrics, drawn chrome)
- [ ] Not the default skeleton (hero, three cards, testimonials, CTA,
      footer); section structure derived from this business
- [ ] Contrast: 4.5:1 body, 3:1 large text and UI, from RENDERED computed
      styles; pixel-sampled where text sits on photos or gradients
- [ ] Keyboard access works; focus visible
- [ ] Rendered-font verification passed (all 8 steps in
      [typography](../references/craft/typography.md)): registration,
      paint, synthesis, network, console, computed sizes at 360/768/1440,
      fallback rehearsal, and the look
- [ ] Parseable-text pass complete (four-question gate + residue greps in
      [parseable text](../references/quality/parseable-text.md)): no
      decorative pseudo-data, no internal vocabulary, no placeholder or
      binding residue, no mojibake
- [ ] Screenshot pair at ~1440 AND ~375 for every page in scope, saved to
      disk, actually opened and looked at, paths cited
- [ ] Demo/live state correct: still a demo unless the owner said live in
      his own words; dead CTAs carry the demo notice

## P1: hard tier and structure

- [ ] No watch-cluster face carrying a greenfield identity without the
      logged comparison (two named rejects and the reason it wins)
- [ ] No single-word emphasis swaps without a recorded reason
- [ ] No repeated eyebrow template above 3+ sections without a real job
- [ ] Two type families max (third has a recorded role)
- [ ] No emoji as interface; no mono outside code and data; no ordinals on
      parallel items
- [ ] Ledger consulted at direction time; this build's row appended or
      updated in `~/.claude/design-dna/LEDGER.md`
- [ ] Macrostructure differs from the previous two ledger rows
- [ ] Placeholder register empty, or every open row explicitly deferred by
      the owner (required empty before any live state)

## P2: polish sweep

- [ ] Type numbers inside ranges (tracking, leading, measure, scale) or
      carrying rendered proof for the exception
- [ ] Descenders intact through every masked reveal
- [ ] No claim stated more than twice on one page
- [ ] Salience check: first three things noticed at each width are content,
      not decoration
- [ ] One memorable element nameable per page (absence of flaws is not
      presence of identity)
- [ ] Reduced motion respected; images carry alt text; states (loading,
      empty, error) render written content
