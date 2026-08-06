# Design DNA

**A web-design skill for coding agents, built to stop the output from looking
like a coding agent made it.**

It runs in Claude Code and Codex. Point it at a project and it works the way a
studio does: read the real material first, write an art direction the project
actually implies, prove the risky decisions at real widths before propagating
them, build, then *look at the rendered page* and review what is actually
there.

Three things make it different from a prompt that says "make it look nice":

- **No house style.** There is no bundled palette, font pool, or hero recipe
  to inherit, because a beautiful default is still a fingerprint. Every visual
  choice has to be derived from this project and defensible for it.
- **It verifies by seeing.** Judging craft from source is prohibited. Nothing
  is finished without rendered screenshots at desktop and mobile widths, and
  the harness measures the page: real contrast against the real composited
  background, which font actually painted, whether the strings on screen mean
  anything.
- **It cannot invent.** No fabricated statistics, reviews, people, or product
  UI. Placeholders are labeled and tracked, and every build stays a demo until
  its owner says otherwise in their own words.

The runtime stays small. A decision router loads only the guidance the current
decision needs, so a font question does not drag in the ecommerce, motion, and
localization libraries.

New here? [Quick start](docs/QUICK_START.md) ·
[Install](#install-one-route-per-host) · [What it changes](#what-it-changes) ·
[The skill itself](skills/design-dna/SKILL.md)

---

> **Release status:** `5.0.2` is an unreleased candidate. Its workflow and
> package changes are implemented, but formal host, comparative, independent
> rendered-review, and strict release qualification remain pending. The
> checked-in attestations predate this source and are retained as historical
> inputs until regenerated; see
> [the compatibility matrix](maintainer/compatibility/matrix.yml).

Design DNA is a cross-host website-design skill for work that must feel
specific, time-appropriate, coherent, truthful, and fully implemented. It keeps
truth, rights, accessibility, working behavior, and explicit project authority
strict while leaving typography, composition, media, color, ornament,
interaction, and other aesthetic choices open. The skill helps an agent
develop project-specific art direction, carry accepted decisions through
responsive production code, and inspect the rendered result for generic
defaulting, weak craft, unfinished behavior, accessibility failures, and
release residue.

Version 5.0 merges three generations into one skill: the 4.0 architecture
(authority order, capability presets, the decision router, flows, verticals,
cultural review, scripts), the 3.4 dated risk vocabulary restored as expiring
post-render tables, and the owner doctrine that 2.x had removed. It adds a
two-tier accountable-owner policy whose ABSOLUTE tier no one may lift, a
parseable-text gate for every visible string, a studio ledger that makes the
skill notice when it repeats itself, and a one-page preship gate. The 5.0.x
line then hardens all of it against real builds, most of that work in the
capture-and-measurement harness.

It carries forward the 4.0 Range Study contract for deliberately varied
multi-route sites, and its cultural-context boundaries for place and community
publications. Shared truth, navigation, access, and identity stay dependable
while route bodies stay free to find materially different answers. There is no
font-convergence policy and no fixed visual recipe; rendered comparison
examines normalized geometry, topology, media and control density, and
computed typography rather than treating font names, copy, palette, or image
identity as aesthetic verdicts.

It is not a style pack. It does not impose a replacement house style, infer
authorship from aesthetics, or promise that AI involvement is undetectable.

## What it changes

Design DNA adds a repeatable operating system for:

- discovering the project's real content, constraints, audience, and task;
- researching project, category, cultural, technical, and adjacent creative
  evidence in the mix needed for the actual decision;
- exploring enough materially different, directly reviewable answers to expose
  consequential uncertainty without manufacturing candidates to satisfy a
  quota;
- selecting a direction with rationale, recorded constraints, observable
  design decisions, and a reversible checkpoint when the risk warrants one;
- translating requested visual and experiential qualities into
  project-specific observations rather than a preset expression recipe;
- carrying the chosen `creative_logic` through whatever combination of
  typography, color, imagery, layout, motion, ornament, density, interaction,
  convention, or restraint the work needs;
- proving the riskiest or most consequential decisions before broad
  propagation, using the route, fragment, flow, or comparison that best
  answers the uncertainty;
- authoring a route-family record for a Range Study, proving real direct-entry
  routes, comparing meaningful route differences, and reviewing a matched
  route atlas;
- separating reusable foundations, route-owned compositions, and justified
  one-offs so creative range does not become random inconsistency;
- establishing cultural authority, terminology, representation, and human
  acceptance boundaries for culturally central community work;
- handling local business, commerce, software, editorial, portfolio, travel,
  education, nonprofit, and marketplace contexts without collapsing them into
  the same landing-page formula;
- implementing real routes, states, forms, account flows, billing surfaces,
  messaging, location behavior, and content structures when the project needs
  them;
- preserving claims, media provenance, rights, privacy, and factual boundaries;
- reviewing source and rendered behavior at relevant viewports and input modes;
- recording findings, fixes, evidence, limitations, and unperformed checks.

The runtime remains compact. Detailed craft, workflow, vertical, state, and
quality guidance is loaded only when the task needs it.

## Choose assurance capabilities

Design DNA scales its evidence and review to the work. Quick and Standard are
proportional base presets. The project state stores a canonical cumulative
capability set: Showcase, Range Study, and High-risk can apply together, and an
asset-led record automatically adds its own gate without weakening another.
Redundant lower presets are normalized away rather than retained as misleading
extra assurances.

| Capability preset | Use it for | Minimum assurance |
| --- | --- | --- |
| **Quick** | A bounded repair or low-risk change inside an established system. | Inspect context, preserve the system, implement changed states, and run affected checks. |
| **Standard** | A new route, meaningful feature, or ordinary redesign. | Frame and direct the work, prove consequential decisions proportionately, implement, and complete rendered plus engineering review. |
| **Showcase** | Expressive, premium, highly visible, owner-sensitive work, or a brief that rejects safe or generic output. | Research the real decision, compare enough directly reviewable answers to challenge the first default, select and checkpoint when useful, deepen consequential decisions, and run adversarial review. |
| **Range Study** | A multi-route brief explicitly asks pages to demonstrate meaningful creative range. | Keep dependable truth, navigation, access, and operations; author the route-family record; prove routes selected by uncertainty; verify real paths; and review a matched route atlas. |
| **High-risk** | Identity, permissions, private data, money, regulated claims, consequential transactions, or difficult recovery. | Prioritize task, state, content, specialist, and real-user evidence; visual ambition cannot waive a safety or production gate. |
| **Asset-led** | Material imagery, video, audio, fonts, documents, maps, embeds, or generated media needs a durable record. | Gate every listed asset on type-specific provenance, rights, privacy, factual status, approval, delivery, accessibility, and generated-media evidence. |

**Showcase is the recommended capability preset for portfolio pieces, sample
sites, client-facing demos, pitch concepts, and other work intended to
demonstrate visual capability.** Use every applicable capability: Showcase work
can also be High-risk.

For substantial open or expressive work, exploration is not decoration around
a first idea. Develop enough materially different evidence to expose the
choice that matters; the appropriate number, fidelity, medium, and comparison
shape depend on uncertainty, stakes, inherited authority, and the owner's
decision needs. Candidates differ because they propose different answers to
the brief, not because a fixed list of surface attributes changes. Record the
selected `creative_logic` and consequential observable decisions, preserve a
reversible checkpoint when useful, and deepen the proof that can prevent the
most expensive propagation error.

## Use it

For a direct personal installation, start with a short request:

| Host | Example |
| --- | --- |
| Codex | `$design-dna Build a time-appropriate website for this coffee shop using the supplied facts and assets.` |
| Claude Code | `/design-dna Build a time-appropriate website for this coffee shop using the supplied facts and assets.` |

Design DNA selects the proportional assurance capabilities from the task. Say
`Use Showcase` when the result is a portfolio piece, sample, pitch, demo, or
another high-visibility expression of design capability. Say `Use Range Study`
when a real multi-route site must demonstrate materially different page forms
while retaining one usable family.

Both host integrations are designed for relevant natural-language discovery,
but actual automatic loading is host- and version-dependent and must be
observed in that environment. Use explicit invocation when Design DNA is
required or when selection itself is part of the test.

The Claude route and slash command in this package are for **Claude Code**.
Installing the local skill does not add it to ordinary conversations on
claude.ai or the Claude Desktop chat application.

Give the agent the best available business facts, copy, images, brand material,
constraints, stack, required routes, and examples with reasons. Missing proof,
pricing, reviews, people, availability, policies, or integrations must remain
omitted or honestly pending.

See [Quick start](docs/QUICK_START.md) for capability guidance, a paste-ready
Showcase prompt, and the material checklist.

## Install one route per host

The canonical runtime is `skills/design-dna`. A personal installation should
configure exactly one intended Design DNA discovery route in each host.

Get the package first:

```text
git clone https://github.com/mjcreations123/design-dna.git
cd design-dna
```

### Supported route: the installer

First create an isolated Python environment and install the exact locked
maintainer dependencies. On Windows PowerShell:

```text
python -m venv .venv
.venv\Scripts\python.exe -m pip install --disable-pip-version-check --require-hashes -r maintainer\requirements-dev.lock
.venv\Scripts\python.exe -B maintainer\scripts\manage_install.py doctor
.venv\Scripts\python.exe -B maintainer\scripts\manage_install.py sync --host all
.venv\Scripts\python.exe -B maintainer\scripts\manage_install.py doctor
```

On macOS or Linux:

```text
python3 -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check --require-hashes -r maintainer/requirements-dev.lock
.venv/bin/python -B maintainer/scripts/manage_install.py doctor
.venv/bin/python -B maintainer/scripts/manage_install.py sync --host all
.venv/bin/python -B maintainer/scripts/manage_install.py doctor
```

`sync` installs a missing direct route, updates a stale one with a recoverable
backup, and leaves a current route unchanged. It handles mixed Codex/Claude
states transactionally. The doctor reports missing, current, stale, external,
or colliding filesystem discovery candidates; packaged plugins remain managed
by their host. A candidate is not proof of plugin activation or current-session
visibility.

The default direct routes preserve the short commands shown above:

- Codex: `~/.agents/skills/design-dna`
- Claude Code: `~/.claude/skills/design-dna`

When `CLAUDE_CONFIG_DIR` is set, the installer resolves Claude Code's direct
route and plugin-cache scan beneath that directory independently of `--home`.
Codex routes and recoverable backup storage remain under the selected home.

Do not activate a direct skill and packaged plugin for the same host at the same
time. The package includes both `.codex-plugin/plugin.json` and
`.claude-plugin/plugin.json` for portable distribution, but those manifests are
source artifacts until the corresponding plugin is deliberately installed.

### Unsupported route: copy the runtime by hand

Without Python, copy `skills/design-dna` to the host route directly. This
installs the same runtime, but nothing verifies the result: no doctor report,
no stale-route detection, no recoverable backup, and no transactional handling
of a mixed Codex/Claude state. Prefer the installer whenever Python is
available.

```text
# Claude Code, macOS or Linux
cp -r skills/design-dna ~/.claude/skills/design-dna

# Claude Code, Windows PowerShell
Copy-Item -Recurse skills\design-dna $HOME\.claude\skills\design-dna

# Codex: use ~/.agents/skills/design-dna as the destination instead
```

Restart the host, then confirm the skill is discoverable before relying on it.
Updating means repeating the copy, and removing an old copy first avoids
leaving stale reference files behind.

### Scoping the skill to one project

To limit Design DNA to a single repository rather than the whole account, copy
`skills/design-dna` into that project's `.claude/skills/design-dna` instead of
the home route. Per-project installations carry the same verification caveat as
the manual route above.

See [Installation and distribution](docs/INSTALLATION.md) for update, rollback,
removal, and plugin details. Use [Troubleshooting](docs/TROUBLESHOOTING.md) for
diagnosis and [Project-state migration](docs/MIGRATION.md) when an existing
project record needs a schema upgrade.

## Package layout

```text
design-dna/
  .claude-plugin/plugin.json
  .codex-plugin/plugin.json
  skills/design-dna/
    SKILL.md
    policy/
    references/
    templates/
    scripts/
  maintainer/
    attestations/
    compatibility/
    evals/
    evidence/
    schemas/
    scripts/
    tests/
  docs/
```

`SKILL.md` is the runtime router and precedence contract. References provide
progressive disclosure. Templates carry project-local state. Runtime scripts
initialize that state and perform bounded source analysis. Maintainer tooling
validates the package, evidence, evaluations, installations, and release
identity.

## Validate a development checkout

Maintainer tools require Python 3.10 or newer and the exact pinned dependency
closure. Reuse the isolated environment created above; in the commands below,
`<PYTHON>` means `.venv\Scripts\python.exe` on Windows or
`.venv/bin/python` on macOS and Linux:

```text
npm --prefix maintainer ci --ignore-scripts --no-audit --no-fund
npm --prefix maintainer exec -- playwright install chromium
<PYTHON> -B maintainer/scripts/attest_tests.py --plugin-root . --output maintainer/attestations/test-attestation.json
<PYTHON> -B maintainer/scripts/attest_codex_plugin.py --plugin-root . --validator "<ABSOLUTE_PLUGIN_CREATOR_VALIDATOR>" --output maintainer/attestations/codex-plugin-validation.json
<PYTHON> -B maintainer/scripts/validate_evidence.py --plugin-root .
<PYTHON> -B maintainer/scripts/check_links.py .
<PYTHON> -B maintainer/scripts/audit_package.py --plugin-root . --codex-validator "<ABSOLUTE_PLUGIN_CREATOR_VALIDATOR>"
```

The Codex validator must match the deliberately reviewed byte pin in
`maintainer/trust/codex-plugin-validator.json`. Do not copy a mismatching hash
into that file without reviewing the new validator source; the pin is publisher
evidence, not an OpenAI signature. The attestor uses Python isolation and
private input snapshots and does not retain validator output content.

Rendered browser review additionally needs Node.js 20 or newer, Playwright,
and a compatible browser. The commands above install the exact JavaScript
dependency closure and
Playwright Chromium. On Windows PowerShell, use `npm.cmd` in place of `npm` if
script execution policy blocks `npm.ps1`. A trusted compatible system browser
may be selected instead. The runtime reports that check as unavailable when
those tools are absent; source cleanliness is never promoted into visual proof.

Use `-B` as shown. Compiled Python artifacts are excluded from identity hashes
and forbidden in executable runtime and maintainer trees.
The attested suite has a fixed one-hour safety ceiling because it exercises
real browser and interrupted-filesystem lifecycle cases; a timeout remains an
unavailable result, never a pass.

## Proof and release boundary

Design DNA separates:

1. static package validity;
2. host discovery and behavioral execution;
3. exact artifact and rendered-browser evidence;
4. independent perception, implementation, accessibility, and target-user
   review;
5. repeated skill-versus-baseline comparison.

A diagnostic build is useful feedback, not release proof. The strict release
audit fails closed when controlled host evidence, responsive rendered evidence,
review attribution, test integrity, route parity, or current compatibility
records are missing. It does not turn unavailable evidence into a marketing
claim.

See [Evaluation guide](docs/EVALUATION.md),
[cross-build rendered comparison](docs/RENDER_COMPARISON.md),
[Release procedure](docs/RELEASE.md), and
[Commercial readiness](docs/COMMERCIAL_READINESS.md).

## Product policies

- [Security](SECURITY.md)
- [Support](SUPPORT.md)
- [Data handling and privacy](DATA_HANDLING.md)
- [Owner-policy onboarding](docs/OWNER_POLICY.md)
- [Contributing](CONTRIBUTING.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)
- [Proprietary rights notice](LICENSE)
- [Changelog](CHANGELOG.md)

Price, legal terms, support commitments, and customer satisfaction are business
questions. This repository can establish a high-integrity product and evidence
process; it cannot guarantee a sale price or universal taste.
