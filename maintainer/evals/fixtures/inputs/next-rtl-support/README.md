# Next.js bilingual support fixture

This is a synthetic Next.js App Router project. It is intentionally small, but its file layout and package metadata represent an established application rather than a blank static-site exercise.

## Approved behavior

- The route supports English (`en`) and Arabic (`ar`).
- The existing translated strings are approved and must remain local to the fixture.
- The support request is a demonstration only. It must never send data or imply that a backend exists.
- Name, email, and message are required.
- Validation and a successful demo state must be perceivable without color alone.
- The page must remain usable at 320 CSS pixels, with a virtual keyboard open, at 200% zoom, and by keyboard.
- Arabic uses right-to-left direction while email addresses remain left-to-right.

## Scope

Change only `app/[locale]/support/page.tsx` and `app/globals.css`. Keep
`package-lock.json` and all project configuration byte-for-byte unchanged. Do
not add dependencies, contact an application network service, or edit this
README.

## Reproducible review setup

When the trusted evaluation environment permits registry or cache reads, use
`npm ci --ignore-scripts --no-audit --no-fund`, run the existing build and
rendered checks, then stop the server and remove only this fixture's ephemeral
`node_modules` and `.next` paths before completion. If installation is
unavailable, report the build and rendered checks as not performed; never
substitute a source-only claim. The completed workspace must still contain only
the two authorized source changes.
