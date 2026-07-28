# Evaluation notes

## Result

Built a dependency-free, one-page concept for a new neighborhood coffee shop:

- `index.html`
- `style.css`
- `script.js`
- `.design-dna/direction.md`
- `.design-dna/visual-review.md`

The concept uses a contemporary neighborhood notice-board premise rather than vintage café shorthand. It is intentionally text-led because no logo, photography, place, schedule, menu, story, reviews, prices, or transaction details were supplied. “Neighborhood Coffee” is visibly labeled as a working label, and all missing business facts remain marked as owner inputs.

No live services were contacted. Nothing was published. There are no third-party requests, dependencies, webfonts, images, maps, forms, analytics, cookies, ordering endpoints, or embeds.

## Checks performed

### Source and runtime

- `node --check script.js` — passed.
- Local mock interaction test — confirmed the print button registers a click handler and calls `window.print()`.
- Local Python HTTP server on `127.0.0.1:4173`.
- `Invoke-WebRequest` smoke tests:
  - `/` — HTTP 200, 8,291 B, `text/html`
  - `/style.css` — HTTP 200, 13,259 B, `text/css`
  - `/script.js` — HTTP 200, 130 B, `text/javascript`
- Total source size: 21,680 B.
- External `http://` or `https://` references: 0.
- Internal anchors checked: 7; missing targets: 0.
- Duplicate IDs: 0.
- CSS braces: 127 opening / 127 closing.
- `state.json` parsed as valid JSON.
- Placeholder/residue scan found no starter filler, sample domains, development markers, live URLs, forms, analytics, prices, ratings, or fake review content.

### Accessibility baseline

- Controlled-browser DOM snapshot confirmed:
  - skip link;
  - banner, navigation, main, regions, and footer landmarks;
  - one H1 and ordered H2 section hierarchy;
  - descriptive link and button names;
  - native disclosure semantics;
  - definition-list semantics for visit information.
- Source review confirmed visible `:focus-visible`, reduced-motion handling, forced-color adaptation, semantic controls, and 44px minimum navigation/control targets.
- Calculated contrast ratios:
  - ink / paper: 17.28:1
  - muted / paper: 6.34:1
  - white / blue action: 6.09:1
  - ink / coral: 4.95:1
  - white / coral large display: 3.82:1
  - ink / yellow status: 13.89:1
  - white / ink: 18.88:1

The initial coral produced only 2.85:1 behind white display text. It was replaced with `#e94b28`, bringing that pairing above the 3:1 large-text threshold.

### Historical browser observation

- A controlled Chrome render at a requested 1440 × 1000 viewport was inspected,
  but no screenshot was retained and the exact inspected bytes cannot be
  reconstructed from this note.
- A later desktop/mobile review found two medium defects in this artifact:
  unjustified one-word color emphasis and incomplete skip-link focus transfer.
- Treat the observations in this file as historical debugging notes only. They
  are superseded by `manual-browser-review-20260726.md` and are not rendered,
  release, or quality-gate evidence.

### Truth and scope

- Copy was traced against the brief. The only business premise presented as fact is “new neighborhood coffee shop.”
- Address, hours, menu, prices, dietary information, ordering, identity, photography, accessibility details, policy, and contact information are labeled pending or omitted.
- No logo, history, review, rating, availability, opening status, sourcing claim, amenity, product, or location was invented.

## What remains unverified

- Final-build screenshots at narrow, intermediate, common, wide, and short-height viewports.
- Continuous browser resizing and horizontal-overflow inspection.
- Live keyboard-only and focus-order pass.
- Print-preview appearance in a browser.
- Automated accessibility scan.
- Screen-reader smoke test.
- 200% and 400% zoom/reflow.
- Text-spacing override.
- Forced-colors/high-contrast and reduced-motion rendering.
- Touch and no-hover behavior on a physical device.
- Final console and failed-network inspection.
- Lighthouse, Core Web Vitals, slow-network, and cache measurements.
- Localization expansion and RTL.
- Independent perception review and target-user testing.

These checks remain unverified because the available Chrome control session repeatedly stalled after the first successful render and semantic snapshot. Source-level responsive, focus, motion, and forced-color rules were reviewed, but they are not represented here as completed browser tests.

## Release status

Concept only. Do not publish until the owner supplies and approves the real shop identity, address, hours, menu, prices, dietary/allergen language, photography direction, accessibility and policy information, contact channels, and any future ordering or map integration.

The packaged `init_project_state.py` helper was attempted, but its repository-protection rule refused this evaluation path because it lives inside the package tree. Project-local records were therefore created manually with resolved `design-dna 2.0.0` metadata and no unresolved template tokens.
