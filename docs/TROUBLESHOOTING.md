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

An explicit browser executable does **not** replace the Playwright JavaScript
module: it is consulted only after that module resolves. The installed skill
never installs, downloads, bundles, or globally searches for either resource.

From the package root, first check the exact installed runtime against the
actual project. This is a read-only launch check for the current terminal
process; it does not prove that Codex or Claude Code activated the skill:

```text
.venv\Scripts\python.exe -B maintainer\scripts\manage_install.py doctor --host all --browser-project "C:\absolute\project"
```

On macOS or Linux, use `.venv/bin/python` and normal slash separators. The
runtime resolves only these existing local module locations, in order:

1. an explicit absolute `DESIGN_DNA_PLAYWRIGHT_MODULE_DIR` (an invalid explicit
   path fails rather than falling through);
2. the target project's exact `node_modules` directory;
3. `maintainer/node_modules` beside a recognized source checkout; and
4. ordinary Node resolution from the installed skill.

For a package checkout's pinned browser closure on Windows PowerShell:

```powershell
npm.cmd --prefix maintainer ci --ignore-scripts --no-audit --no-fund
npm.cmd --prefix maintainer exec -- playwright install chromium
$env:DESIGN_DNA_PLAYWRIGHT_MODULE_DIR = (Resolve-Path ".\maintainer\node_modules").Path
.venv\Scripts\python.exe -B maintainer\scripts\manage_install.py doctor --host all --browser-project "C:\absolute\project"
```

Alternatively, use the project's already-installed compatible Playwright; the
preflight discovers that project-local module without an environment variable.
Run the installed script directly when the installer is unavailable:

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/browser_preflight.mjs" --project-root "ABSOLUTE_PROJECT" --launch
```

The preflight performs no installation or download. If it reports a missing
module or browser, keep required rendered evidence blocked; do not relabel a
source-only check as browser QA.

## A project record no longer validates

If a completed record changed, mark it draft and complete it again against the
new exact artifact. If its schema is old, use migration dry-run and inspect the
recovery path before applying the migration.

## A strict release audit fails

Read every failure literally. Missing host-native evaluations, independent
rendered reviews, signatures, or current route verification must remain release
blockers. Do not convert missing proof into a limitation merely to obtain a
green status.
