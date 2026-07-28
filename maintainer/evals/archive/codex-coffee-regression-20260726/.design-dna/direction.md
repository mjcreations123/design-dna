---
schema_version: 1
created_with: "design-dna 2.0.0"
classification: "internal"
---

# Direction brief

## Outcome

- Audience and context: People evaluating a future neighborhood coffee shop online; secondary audience is the owner reviewing a reversible concept.
- Primary task or decision: Understand what the site will communicate, find the future visit essentials, and see which business inputs are still required.
- Success condition: The concept feels current and specific while every unsupported business detail remains visibly pending.
- Critical risk or unknown: No shop name, identity, photography, place, hours, menu, prices, story, reviews, contact details, or service integration was supplied.
- Launch state: Concept only.

## Routes and modes

| Route or component | User task | Primary mode | Source/readiness | Required states and QA |
| --- | --- | --- | --- | --- |
| `index.html` | Understand the concept and future visit path | Persuade | Approved premise plus labeled placeholders | Default, details open/closed, print action, narrow through wide, keyboard, reduced motion |

## Evidence and content

| Content, claim, proof, or integration | Status | Source/owner | Public treatment |
| --- | --- | --- | --- |
| This is a new neighborhood coffee shop | approved | User brief | Show |
| Name, logo, address, hours, menu, history, reviews, prices | pending | Future owner input | Label as needed or omit |
| Ordering, maps, forms, tracking, third parties | prohibited for concept | User brief and skill | Omit and disclose |

- Approved brand assets and constraints: None supplied. No external assets will be used.
- Existing-system decisions to preserve: None; the result directory was initially absent.
- Product, place, cultural, or operational raw material: Only the category and neighborhood orientation.
- Open assumptions and reversible placeholders: “Neighborhood Coffee” is explicitly marked as a working label; all business fields are replaceable.
- Content owner, review date, and expiration needs: Owner approval is required for every business fact before public use.

## Research

| Dated reference | Kind | Transferable lesson | Limitation or do-not-copy note |
| --- | --- | --- | --- |
| Design DNA 2.0.0 local-business guidance, read 2026-07-26 | standard | Prioritize visit information and avoid category costume | No external style or content copied |
| Design DNA type-convergence watch, reviewed 2026-07-26 | standard | Avoid unexamined serif/sage/cream and generator-font clusters | A diagnostic prompt, not a blacklist |

- Category mean: Sepia, chalkboard, beans, craft nostalgia, or generic warm editorial luxury.
- Dated shorthand to avoid using unexamined: Faux heritage, script lettering, kraft texture, industrial coffee imagery.
- Current fashionable default to avoid using unexamined: Cream plus display serif plus sage, oversized photography, rounded pill controls.
- Local, cultural, language, or representation considerations: No specific neighborhood or locale was supplied; English/LTR is the concept baseline, not a production assumption.
- Research not performed and why: Current external peers were not contacted because the evaluation explicitly prohibits live services.

## Chosen direction

- Direction statement: A contemporary neighborhood notice-board—direct typographic wayfinding, saturated civic color, hard rules, and compact status information.
- Real material it amplifies: The neighborhood premise and the practical information people need before visiting.
- Intended time register: Current.
- Ambition: Expressive and brand-led, bounded by an information-first public route.
- Why it serves the task: It feels like a place-facing identity without relying on invented photography, product details, or nostalgia.
- Familiar conventions intentionally retained: Visible navigation, descriptive anchors, clear section headings, a structured visit-information list, and a native disclosure.
- Conspicuous choices and their rationale: Blue, orange, and yellow create sign-like contrast; square geometry and one heavy system sans keep the concept direct and dependency-free.
- Direction rejected and why: A warm editorial café treatment was rejected because the supplied brief provides no heritage, natural-material, or photographic evidence for it.

## System

- Type roles, specimen result, license, language coverage, and fallback: Arial/Helvetica was selected over Segoe UI (too interface-neutral) and Trebuchet MS (too soft and era-specific). The installed system stack avoids font requests and supports broad Latin text.
- Heading and textual-emphasis rule: One family, one foreground treatment per heading, with scale and line breaks carrying emphasis.
- Color and semantic roles: Cool paper canvas, near-black text/rules, blue action, orange identity field, yellow status/focus.
- Grid, spacing rhythm, density, and optical exceptions: A two-column decision layout on wide screens, structural recomposition below 800px, and a small tokenized spacing scale.
- Component and dependency theming: No component library or runtime dependency. Buttons, rows, disclosure, and navigation use native semantic elements.
- Imagery, illustration, icon, and asset direction: Text-led; no external or generated imagery. The signal board is CSS composition, not factual product evidence.
- Motion, interaction, and reduced-motion intent: Only local hover feedback and disclosure rotation; all meaning remains without motion.
- Responsive recomposition: Hero and content columns become a deliberate single-column sequence; decision rows compact rather than merely shrinking.
- Content, navigation, taxonomy, and microcopy: Introduction → visit essentials → decision path → launch needs → truth explanation.

## Quality contract

- Accessibility target and specialist handoff: WCAG 2.2 AA baseline; this is not a compliance certification.
- Proposed or approved performance objectives: Proposed concept budget under 70 KB transferred, zero third-party requests, and no layout-dependent media.
- Engineering and browser constraints: Static HTML/CSS/JS; evergreen browser baseline; meaningful content without JavaScript.
- Localization and RTL: Not implemented; layout should be revisited with real locales before production.
- Privacy, security, legal, and data constraints: No personal data, forms, cookies, analytics, or factual safety claims.
- Integrations, tracking, embeds, and deployment authority: None; publishing is prohibited.

## Acceptance

- Critical user tasks: Reach visit essentials, understand what remains unconfirmed, open the truth disclosure, and invoke the print checklist.
- Viewport, container, input, theme, locale, and state matrix: 390px, 768px, 1440px, and wide desktop; pointer and keyboard; default and reduced motion; disclosure closed/open.
- Content stress cases: Long pending-detail labels, single-column reflow, short-height view, 200% zoom.
- Required build, functional, accessibility, performance, and visual checks: Source validation, local HTTP smoke test, console check, screenshots, keyboard focus, anchor/disclosure/print behavior, contrast review, resource totals.
- Required user validation or explicit `not performed` disclosure: Target-user testing not performed.
- Public release blockers: All real business identity, visit, menu, price, policy, asset, and integration details remain unapproved.
