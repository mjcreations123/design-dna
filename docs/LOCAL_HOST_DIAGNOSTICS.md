# Local host diagnostics — 13.0.0 candidate

Recorded 2026-09-06 UTC on Windows. These are deliberately bounded local
diagnostics, not protected host-evaluation or rendered-review promotion records.

## Package and filesystem checks

The official Claude Code 2.1.222 command `claude plugin validate . --strict`
passed against `.claude-plugin/plugin.json`, SHA-256
`7e9778acf10afd4d18399a4c9b703ebe038c10788fea5fa0382efb78d8f4c845`.
That is manifest validation, not authentication or website behavior.

The direct Codex and Claude installation routes had identical entrypoint and
release metadata bytes for the following fresh-session attempts:

- `SKILL.md`: `bc43ff3d78ee6b776c66eafffb9e7e50d4674e70f3b046c4cbe96b2764914b02`
- `release.json`: `21d3a9313dec1ef9e04b67ac5423c7f34acfa8f8ff094fbd705cea74f3c209ca`

Whole-runtime filesystem parity is separately checked by the current
`maintainer/attestations/route-verification.json` record.
These entrypoint hashes do not claim that every runtime script was exercised
by a model.

## Shared dependency configuration

An empty-project installed-runtime check without temporary environment
assignments returned `playwright-unavailable` and `babel-parser-unavailable`.
The pinned bundle existed, but neither Design DNA directory variable had a
saved user or machine value. The two previously unset **user-level** directory
settings now point to this checkout's verified `maintainer/node_modules`;
machine settings and project dependencies were not changed.

After loading those saved values into a new child invocation, the installed
Codex route passed an actual Chromium launch and timestamped screencast
start/frame/stop cycle with Playwright `1.61.1`, and parsed TSX with
`@babel/parser` `7.28.5`. This verifies configured prerequisites, not current
whole-tree parity, a host restart, or model activation. Already-running hosts
must receive the updated environment before a fresh-task check. The portable
setup and existing-setting safeguards are in [Installation](INSTALLATION.md).

## Fresh read-only model attempts

Both attempts used new empty work directories and requested no files, browser,
services, deployment, or delegation. The scenario was a small hachnasas orchim
demo with a brief but no measured references. It asked for the loaded skill
path/version, permitted next step, reference-count rule, gate phases, delivery
check, and internal-proof boundary.

Codex CLI 0.153.4 with `gpt-6-astra`, an ephemeral session and a read-only
sandbox returned the updated coverage-justified reference rule, no reduced
quality mode, required first-screen/final phases, and the delivery-status
check. Its direct `SKILL.md` and `release.json` reads were rejected by the
diagnostic execution policy. It correctly reported that direct installed-file
and version verification were unavailable. No sandbox or policy bypass was
attempted. The response alone is not proof of complete host activation.

Claude Code 2.1.222, restricted to Skill/Read/Glob/Grep with no session
persistence or external MCP servers, returned `Not logged in · Please run
/login` with `is_error: true` and zero model tokens. No Claude model behavior
was observed. Authentication requires the operator; manifest validation and
filesystem parity do not replace that missing run.

The Codex desktop version, formal controlled host/model evaluations,
independent rendered reviews, and owner acceptance remain unverified by these
checks. See the [release procedure](RELEASE.md) for the distinct promotion
requirements.
