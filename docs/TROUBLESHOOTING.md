# Troubleshooting

## The skill does not appear

Run:

```text
python -B maintainer/scripts/manage_install.py doctor
```

Confirm that the configured global filesystem roots contain exactly one
intended Design DNA discovery candidate and that its runtime hash matches the
canonical package. The doctor does not inspect plugin activation,
project- or administrator-scoped routes, or current-session visibility. Check
those host surfaces separately if the skill still does not appear. For direct
skills, restart only when discovery does not refresh or a top-level watched
directory was newly created.

## The skill appears more than once

Do not delete folders by guess. The doctor reports filesystem discovery
candidates, not confirmed active plugins. Inspect the host plugin manager to
identify which candidate is intentionally installed. Then use the management
tool's `uninstall --host HOST` operation to move an unintended managed direct
route into recovery storage. Plugin installations and cached plugin versions
must be resolved with the host's plugin manager. The installer fails closed
while another discovery candidate could create a duplicate.

## A maintainer command reports missing dependencies

Create an isolated Python 3.10+ environment and install the exact pins:

```text
python -m venv .venv
.venv/Scripts/python -m pip install --require-hashes -r maintainer/requirements-dev.lock
```

On macOS or Linux, use `.venv/bin/python`. Do not weaken a release check because
a required package is absent.

## The source scan passes but the site still looks wrong

The source scanner is bounded. Run the rendered review, inspect the actual
browser output, complete the adversarial specificity review, and revise causes.
A clean source scan never proves visual quality.

## Rendered review cannot launch a browser

Install a compatible Playwright package and browser, supply
`DESIGN_DNA_PLAYWRIGHT_MODULE_DIR`, or pass an explicit trusted browser
executable. The harness must report the unavailable capability rather than
silently substituting source-only review.

## A project record no longer validates

If a completed record changed, mark it draft and complete it again against the
new exact artifact. If its schema is old, use migration dry-run and inspect the
recovery path before applying the migration.

## A strict release audit fails

Read every failure literally. Missing host-native evaluations, independent
rendered reviews, signatures, or current route verification must remain release
blockers. Do not convert missing proof into a limitation merely to obtain a
green status.
