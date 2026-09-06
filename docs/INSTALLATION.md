# Installation and distribution

Design DNA supports two different delivery models. Choose one per host.

## Personal direct installation

This model preserves the short commands `$design-dna` in Codex and
`/design-dna` in Claude Code.

From the package root, first create an isolated Python environment and install
the exact locked dependency set. Then run the installer with that environment;
plain system Python may not include the required `jsonschema` package.

On Windows PowerShell:

```text
python -m venv .venv
.venv\Scripts\python.exe -m pip install --disable-pip-version-check --require-hashes -r maintainer\requirements-dev.lock
.venv\Scripts\python.exe -B maintainer\scripts\manage_install.py doctor
.venv\Scripts\python.exe -B maintainer\scripts\manage_install.py recover --host all --dry-run
.venv\Scripts\python.exe -B maintainer\scripts\manage_install.py recover --host all
.venv\Scripts\python.exe -B maintainer\scripts\manage_install.py sync --host all
.venv\Scripts\python.exe -B maintainer\scripts\manage_install.py doctor
```

On macOS or Linux:

```text
python3 -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check --require-hashes -r maintainer/requirements-dev.lock
.venv/bin/python -B maintainer/scripts/manage_install.py doctor
.venv/bin/python -B maintainer/scripts/manage_install.py recover --host all --dry-run
.venv/bin/python -B maintainer/scripts/manage_install.py recover --host all
.venv/bin/python -B maintainer/scripts/manage_install.py sync --host all
.venv/bin/python -B maintainer/scripts/manage_install.py doctor
```

`manage_install.py` is a local tree synchronizer, not a publisher-authentication
tool. When the source came from a commercial or remote release, first verify
the signed `release-package.json`, archive, and checksum from the independently
established publisher fingerprint. Extract that exact verified archive, then
run the installer from its package root. Content parity proves that the
installed tree matches the selected source; it does not prove who supplied an
unverified source.

`sync` installs missing routes, updates stale routes with recoverable backups,
and leaves current routes unchanged in one all-host transaction. The lower-level
`install` and `update` operations remain available for a deliberately selected
single host.

### Browser-evidence prerequisite

The direct installer copies only the skill runtime. It deliberately does not
copy `node_modules`, install Playwright, download Chromium, edit a global Node
configuration, or claim that either host activated the copied skill. Before a
task whose gate requires browser evidence, check the exact current direct route
against the actual project:

```text
.venv\Scripts\python.exe -B maintainer\scripts\manage_install.py doctor --host all --browser-project "C:\absolute\project"
```

The command runs each healthy installed route's `browser_preflight.mjs` in the
current operator process and launches only a blank local browser. It is a
prerequisite check, not Codex/Claude activation proof or finished site QA.
The launch probe also starts/stops timestamped screencast frames; a runtime
that can open a page but lacks the recording API is rejected. Actual recording
is restricted to the audited Playwright `1.61.1` bundle because encoder
byte-progress uses that version's artifact interface. An older or newer
untested project version is not automatically upgraded or treated as equivalent.
The source recorder also requires an existing full FFmpeg executable on PATH
or its explicit `--ffmpeg` path. Verify it with `ffmpeg -version`; the recorder
performs its own bounded encoder preflight before opening a source. Use a
trusted operating-system package when provisioning this dependency. Browser
sync does not silently install it. The CI matrix provisions it if absent and
verifies it before the mandatory real recording tests.

The resolver checks an explicit absolute
`DESIGN_DNA_PLAYWRIGHT_MODULE_DIR` first (and fails closed if it is invalid),
then the project’s exact `node_modules`, then the recognized source checkout’s
`maintainer/node_modules`, and finally exact `node_modules` directories inside
the installed skill. It never scans global module directories. A project that already has a
compatible Playwright needs no new configuration. To use this package’s pinned
closure from Windows PowerShell without modifying the project:

```powershell
npm.cmd --prefix maintainer ci --ignore-scripts --no-audit --no-fund
npm.cmd --prefix maintainer exec -- playwright install chromium
$env:DESIGN_DNA_PLAYWRIGHT_MODULE_DIR = (Resolve-Path ".\maintainer\node_modules").Path
$env:DESIGN_DNA_BABEL_PARSER_MODULE_DIR = $env:DESIGN_DNA_PLAYWRIGHT_MODULE_DIR
.venv\Scripts\python.exe -B maintainer\scripts\manage_install.py doctor --host all --browser-project "C:\absolute\project"
```

Those `$env:` assignments affect only that PowerShell process and its children.
For an intentionally shared Windows installation, save the already verified
bundle path in the current user's settings as well. Check existing values
before changing them; do not overwrite another configured bundle silently:

```powershell
$designDnaModules = (Resolve-Path ".\maintainer\node_modules").Path
$designDnaNames = @('DESIGN_DNA_PLAYWRIGHT_MODULE_DIR', 'DESIGN_DNA_BABEL_PARSER_MODULE_DIR')
foreach ($designDnaName in $designDnaNames) {
    $designDnaExisting = [Environment]::GetEnvironmentVariable($designDnaName, 'User')
    if ($designDnaExisting -and $designDnaExisting -ne $designDnaModules) {
        throw "Review the existing user setting before changing $designDnaName"
    }
}
foreach ($designDnaName in $designDnaNames) {
    [Environment]::SetEnvironmentVariable($designDnaName, $designDnaModules, 'User')
}
```

Already-running hosts retain their inherited environment. Relaunch them from
an environment containing the updated settings before testing a fresh task.
Do not call saved settings proof of host activation. If the source checkout is
moved or its pinned dependencies change, update and verify the shared bundle
explicitly; an invalid configured path continues to fail closed.

An explicit `--browser-executable` or `DESIGN_DNA_BROWSER_EXECUTABLE` selects a
browser only after a Playwright module has resolved; it cannot bypass that
module prerequisite. When the package management tooling is unavailable, run
the installed preflight directly from the project root:

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/browser_preflight.mjs" --project-root "ABSOLUTE_PROJECT" --launch
```

Construction and proof-slice source checks additionally use the pinned
`@babel/parser` from the same dependency bundle. The package pins a version
compatible with the advertised Node.js 20 minimum. The parser resolver accepts
the explicit parser directory, the shared Playwright module directory, or an
exact project/source-checkout/installed-skill dependency directory. An invalid
explicit parser path is an error. It never silently uses a global parser or
falls back to pattern matching when parsing is unavailable.

Verify it from the installed route before a construction/proof check:

```text
node "<DESIGN_DNA_SKILL_ROOT>/scripts/babel_parser_resolver.mjs" --check
```

If a process or machine interruption leaves a hidden `.stage-*` or `.pending-*`
transaction record, normal inspection and mutation fail closed. Preview the
exact repair with `recover --host all --dry-run`, inspect its
`recovery_actions` and `resolved_paths`, then run `recover --host all`.
Recovery accepts only schema-valid, hash-matching transaction state beneath the
dedicated backup roots. It restores or finalizes provable trees, rejects
ambiguous or tampered residue, and is idempotent when no residue remains.

The installer uses the current user's home directory, creates recoverable
backups outside discovery roots, stages the complete runtime, verifies content
parity, and fails closed when multiple filesystem discovery candidates could
collide. Its scan does not prove plugin activation, project- or
administrator-scoped routes, or current-session visibility. Use `--dry-run`
before a consequential update.

Default routes:

| Host | Direct route |
| --- | --- |
| Codex | `~/.agents/skills/design-dna` |
| Claude Code | `~/.claude/skills/design-dna` |

If `CLAUDE_CONFIG_DIR` is set, replace `~/.claude` in the Claude row with that
exact configuration directory. `--home` still controls Codex routes and the
recoverable backup base; it does not override Claude's explicit configuration
root. Backups for non-default Claude roots are isolated by a stable
configuration-path digest so history from one root cannot be restored into
another.

The Claude route is specifically a **Claude Code** skill. It does not
automatically update claude.ai or ordinary Claude Desktop chat conversations.

Do not create an additional copy under `~/.codex/skills`, a project skill
directory, or a plugin cache while using the direct route. Project and
administrator scopes are not covered by the global-root doctor scan, so inspect
those host surfaces separately.

## Packaged Codex distribution

The package root is a Codex plugin because it contains
`.codex-plugin/plugin.json`. Distribute a versioned release archive or publish it
through a supported plugin marketplace. Do not install that plugin on a machine
that already uses the direct Codex route.

Validate the package with the current Plugin Creator validator, its trust-pinned
sibling import, and the package's own development audit before distribution.

## Packaged Claude Code distribution

The package root is also a Claude Code plugin because it contains
`.claude-plugin/plugin.json` and the shared `skills/` directory.

For isolated development testing:

```text
claude --plugin-dir /absolute/path/to/design-dna
```

Before representing the packaged plugin as host-validated, run the official
Claude Code validator from the package root:

```text
claude plugin validate . --strict
```

If Claude Code is missing or not authenticated, record this check as
`unverified`; the repository's JSON-schema validation is not a substitute for
the host validator.

For distribution, publish the plugin through a Claude Code marketplace and bump
the manifest version for every release. Plugin skills are namespaced; the
installed command is `/design-dna:design-dna`.

Do not install the Claude plugin alongside the personal direct
`~/.claude/skills/design-dna` route.

## Updates

After updating a direct skill, start a fresh task or conversation and reinvoke
it so earlier instructions are not already fixed in the active context. If the
updated behavior is not observed, restart the host and run `doctor`; filesystem
route parity alone does not prove that a host loaded the new content. For a
deliberately tested development plugin, run `/reload-plugins` after component
changes; installed marketplace plugins use the host's plugin update flow.

Run `doctor` after every update and use a fresh task or conversation for formal
evaluation so the evaluated context is unambiguous.

For project-local record upgrades, follow
[Project-state migration](MIGRATION.md). For route, dependency, state, or
validation failures, use [Troubleshooting](TROUBLESHOOTING.md).

## Installer lifecycle evidence

Maintainers can prove the direct-route happy-path lifecycle without touching
the current user's real Codex or Claude installation:

```text
python -B maintainer/scripts/attest_install_lifecycle.py --plugin-root . --output maintainer/attestations/install-lifecycle.json
python -B maintainer/scripts/attest_install_lifecycle.py --plugin-root . --output maintainer/attestations/install-lifecycle.json --check
```

The attestor creates a fresh temporary home, invokes the actual installation
manager in a new subprocess for every stage, and performs this exact sequence
for both hosts:

1. install a derived prior-runtime fixture;
2. update to the exact release runtime;
3. roll back to the prior fixture;
4. uninstall the restored fixture.

It schema-validates all four operation records and every persisted backup
record, binds the runtime and relevant manager/schema files by SHA-256, confirms
the expected installed tree after each stage, and confirms that both final
routes are absent. `--check` does not trust the saved result by itself: it
repeats the lifecycle in a new isolated home and compares the stable semantic
record.

This evidence is deliberately narrower than a general installation guarantee.
It does not prove a user's current routes, packaged marketplace installation,
or host plugin update behavior. The unit suite separately forces real process
termination at each target-rename boundary and verifies fail-closed,
hash-checked, idempotent recovery for both hosts. Neither test class simulates
every storage-device, filesystem, power-loss, malware, or concurrent
out-of-band mutation failure.

## Removal and rollback

The management tool moves the exact route into a recovery directory instead of
permanently deleting it:

```text
python -B maintainer/scripts/manage_install.py uninstall --host codex
python -B maintainer/scripts/manage_install.py rollback --host codex --backup-id BACKUP_ID
python -B maintainer/scripts/manage_install.py recover --host codex --dry-run
python -B maintainer/scripts/manage_install.py recover --host codex
```

Use the equivalent `claude` host value for Claude Code. Inspect the JSON result
and select an exact `available_backups[].backup_id` before rollback. The tool
refuses an ambiguous rollback.
