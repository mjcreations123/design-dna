# React + Vite route-board fixture

This synthetic project represents an established React application used by a
mobile-library dispatch team. All routes, times, labels, and operational notes
are fictional scenario data for evaluation only.

## Existing product contract

- Keep the React + Vite stack and the current component boundaries.
- `src/data/route-stops.json` is the approved local data source. Do not rewrite,
  relocate, supplement, or fetch it.
- `/assets/route-marker.svg` is an existing public asset path. Keep using that
  exact local asset rather than replacing, inlining, or downloading it.
- Search, status filtering, route selection, and the local reviewed state
  already work. Preserve them while improving the interface.
- `package-lock.json` is the frozen dependency graph. Keep it byte-for-byte
  unchanged.
- The board must make its default, filtered, no-match, selected-detail, and
  reviewed-confirmation states clear without relying on color alone.
- Review is session-local. Do not add persistence, analytics, authentication,
  a backend, or any network request.

## Requested design work

Clarify the dispatcher's scan path and make the board resilient from 320 CSS
pixels through wide desktop containers. Preserve information density, direct
labels, keyboard operation, visible focus, touch targets, 200% zoom, and
reduced-motion behavior. Inspect the rendered application at narrow,
intermediate, and wide widths and exercise every state before completion.

## Authorized files

Change only:

- `src/App.jsx`
- `src/styles.css`

Keep this README, package and Vite configuration, HTML entry point, public
asset, lockfile, data, entry module, shared component, and formatting utility
byte-for-byte unchanged. Do not add dependencies, generated output, or files.

## Reproducible review setup

When the trusted evaluation environment permits registry or cache reads, use
`npm ci --ignore-scripts --no-audit --no-fund`, run the existing build and
rendered checks, then stop the server and remove only the fixture's ephemeral
`node_modules` and `dist` paths before completion. If installation is
unavailable, report the build and rendered checks as not performed; never
substitute a source-only claim. The completed workspace must still match the
authorized-file contract above.

## Deliberate coverage limit

This fixture adds one focused React + Vite case. A second Astro fixture is
deliberately deferred: modeling its content collection and asset pipeline well
would expand the validation surface beyond this bounded diversity correction.
The existing Next.js and SvelteKit fixtures already cover two other non-static
application stacks.
