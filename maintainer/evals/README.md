# Design DNA evaluation harness

This directory is maintainer infrastructure, not runtime skill context. The v3 harness runs a
neutral task in a fresh project and fake home, stages the exact selected runtime only for the skill
variant, and records attributable evidence for later review. It is a trusted-driver harness, not an
operating-system security sandbox.

Individual runner outputs are diagnostic records, not a release-reliability
claim. Before promotion, use the separate [evaluation reliability
qualification](QUALIFICATION.md) gate to predeclare the complete case, prompt-
family, partition, model, package, and repeated-trial matrix; bind every result;
and report first-pass, all-trials, blocker, and worst-trial evidence without
selecting a best run.

## Run a suite

### Install the release-test dependencies

Install the exact maintainer pins before running release-critical test discovery or the evaluation
harness:

```text
python -m pip install --require-hashes -r maintainer/requirements-dev.lock
```

`maintainer/tests/test_dependency_preflight.py` is intentionally never skipped. Missing,
unimportable, or version-mismatched pins make the discovered test suite fail; skip messages from
individual dependency-backed test classes do not constitute a release-valid green run.

Create the work and result directories before using explicit paths:

```text
python maintainer/scripts/run_evals.py maintainer/evals/fixtures/behavioral-cases.json \
  --host codex \
  --skill-root skills/design-dna \
  --driver <executable> \
  --driver-arg <argument> \
  --skill-provider <provider> \
  --skill-model <model> \
  --skill-model-version <concrete-version> \
  --skill-reasoning-effort <effort> \
  --work-root <empty-temporary-directory> \
  --results-dir maintainer/evals/results
```

On PowerShell, pass values that begin with a hyphen in `--option=value` form, for example
`--driver-arg=-c`. Repeat `--driver-arg` for every driver argument.

Required choices:

- `--host codex` stages the runtime at
  `<fake-home>/.agents/skills/design-dna`.
- `--host claude_code` stages it at
  `<fake-home>/.claude/skills/design-dna` as a direct skill.
- `--driver` is the trusted executable used for the skill variant. No shell is invoked.

Useful controls:

- `--baseline-driver` and repeated `--baseline-arg` add a baseline with no installed skill.
- `--skill-provider`, `--skill-model`, `--skill-model-version`, and
  `--skill-reasoning-effort` record the exact model context supplied to the
  trusted driver. Repeat `--skill-generation-config KEY=VALUE` for approved
  non-secret scalar settings such as temperature, seed, or output-token limit.
  This metadata records the run; it does not configure the driver.
- The corresponding `--baseline-*` options record a deliberately separate
  baseline context. When all baseline model options are omitted, a declared
  skill context is inherited so the comparison remains controlled. A partial
  declaration is refused. Moving aliases such as `latest`, secret-like values,
  and arbitrary generation-setting keys are refused.
- `invocation_mode: explicit` (the fixture default) gives only the skill variant the selected
  host's mapped instruction (`$design-dna` for Codex or `/design-dna` for Claude Code).
  `invocation_mode: implicit` gives both variants the identical natural task prompt and tests host
  discovery rather than prompt compliance.
- `installation_mode: direct-skill` (the fixture default) identifies the exact route the runner
  stages. `packaged-plugin` is represented so a fixture cannot blur the two Claude installation
  contracts, but the current runner refuses it before execution. It does not claim that copying a
  skill into `.claude/skills` proves installation through `.claude/plugins/cache` or invocation as
  `/design-dna:design-dna`. Packaged-plugin evidence requires a future host-native installer and
  invocation adapter.
- `--runs 2` through `--runs 20` samples repeatability and convergence. The default is one.
- Repeat `--case <case-id>` to select cases.
- Repeat `--monitor-root <existing-directory>` to fail the particular run that changes an external
  directory.
- Repeat `--pass-env <NAME>` only when a trusted driver genuinely needs a caller variable. Treat
  every passed value as sensitive: values shorter than eight characters are refused, names are
  recorded without values, loaded driver records and bounded output are redacted, and the complete
  temporary run tree is scanned for exact UTF-8, UTF-16, Base64, and URL-safe Base64 forms. A
  detected value or incomplete scan fails the run, blocks artifact promotion, and overrides
  `--keep-workspaces` so the temporary tree is removed.
- `--require-driver-report` requires the driver to write its self-reported load record. The legacy
  option spelling `--require-host-attestation` is accepted only as a compatibility alias; neither
  spelling turns a driver-authored claim into verified host evidence.
- `--host-native-evidence-dir <directory>` uses an independent adapter mailbox. The runner writes
  unpredictable per-run challenges below `challenges/` and reads matching responses below
  `responses/`. `--require-host-native-evidence` requires one for every run. Implicit skill runs
  require this evidence even without the flag.
- `--host-native-evidence-timeout <seconds>` controls how long a required run waits for its
  response (default 5, maximum 60). Optional runs never wait.
- Every completed workspace is promoted by default to a stable, hash-verified bundle below
  `results/artifacts/`. `--keep-workspaces` additionally retains temporary run workspaces for
  debugging; otherwise those temporary directories are removed.

Use a tiered cadence. During ordinary edits, run static validation, the full unit suite, and the
smallest behavioral cases that exercise the changed contract. Run the complete cross-host,
multi-run, independently rendered comparison and convergence matrix for release candidates and
material runtime-policy changes. Do not manufacture ceremonial records merely to make a routine
documentation patch resemble a release qualification. One verified render may be reused for runs
only when their exact workspace hash is identical; record that reuse explicitly.

Structural host-evidence fixtures are useful for testing the harness but never qualify a release.
Strict audit rejects mock, test, fixture, demo, example, and sample source identities. A release
source must also match the owner-controlled host, source ID, version, method, implementation path,
and implementation SHA-256 in `maintainer/compatibility/trusted-host-adapters.yml`. That registry is
itself included in the aggregate release identity, so editing trust policy invalidates the manifest.

Every result records `model_context` for both driver variants and binds its
canonical JSON with SHA-256. Omitting all model fields produces the honest
`unreported` state so diagnostic work can proceed without fabricated metadata.
Unreported identity is release-ineligible. Promoted evidence requires declared,
concrete model identity and a review binding to the exact result, run artifact,
and model-context hash.

### Host-native challenge protocol

An adapter watches `<evidence-dir>/challenges/*.json`. Each schema-v2 challenge carries a
cryptographically random 256-bit session nonce, a fresh 256-bit run nonce, a derived challenge ID,
the issue time, and the exact host/case/variant/run/skill identity. The adapter hashes the exact
challenge file bytes and atomically publishes `<evidence-dir>/responses/<challenge-id>.json`.

The response must contain exactly `schema_version`, `challenge_id`, `challenge_sha256`,
`session_nonce`, `run_nonce`, `host`, `case`, `variant`, `run`, `run_id`, `skill_loaded`,
`skill_content_sha256`, `method`, `source_id`, `source_version`, and `observed_at`. It echoes the
challenge identity, supplies the SHA-256 of the challenge bytes, identifies the independent source,
and records a timezone-aware observation made during that run. The challenge is deliberately not
passed to the driver request or environment.

The runner retains both challenge and response bytes under `results/host-evidence/`, verifies their
binding, and rejects stale or future observations. Strict audit independently re-hashes both files,
recomputes the challenge ID, checks run/session time bounds, and rejects reused session nonces, run
nonces, challenge IDs, challenge bytes, or response bytes within or across result documents.
Precomputed files named from a predictable run ID and schema-v1 evidence are invalid.

The default result directory is `maintainer/evals/results`. It must already exist. A caller-supplied
work root must either exist or have an existing parent. Work, result, runtime, and monitored roots
must not overlap. Monitor roots must exist, be unique, be ordinary directories, and must not nest
inside one another.

## Fixture v3 contract

Fixtures conform to `maintainer/evals/schema.json`:

```json
{
  "schema_version": 3,
  "suite": "safe-filename-slug",
  "skill_instructions": {
    "codex": "Use $design-dna for this task and follow its required verification.",
    "claude_code": "Use /design-dna for this task and follow its required verification."
  },
  "cases": [
    {
      "id": "specific-case-id",
      "invocation_mode": "explicit",
      "installation_mode": "direct-skill",
      "task": "Neutral task text shared by the skill and baseline variants.",
      "input_dir": "inputs/optional-project",
      "timeout_seconds": 300,
      "adversarial": true,
      "review_requirements": [
        "Inspect the exact rendered build at the declared routes and viewports."
      ],
      "release_coverage": {
        "high_value": true,
        "representative": true,
        "primary_mode": "operate",
        "scope": "redesign",
        "project_stratum": "framework-application-data"
      },
      "expected": {
        "exit_codes": [0],
        "stdout_contains": ["marker"],
        "files_exist": ["index.html"],
        "files_absent": ["forbidden.txt"],
        "files_unchanged": ["README.md"],
        "changed_files_only": ["index.html", "style.css"],
        "max_changed_input_files": 2,
        "file_contains": {"index.html": ["<main"]},
        "file_not_contains": {"index.html": ["placeholder"]}
      }
    }
  ]
}
```

`suite` and case IDs are lowercase filename-safe slugs. `skill_instructions`
records the actual explicit invocation syntax for each supported host; the
runner selects the entry matching `--host`. Omitted `invocation_mode` resolves
to `explicit`; use `implicit` only when the host's ordinary skill-discovery
path is the behavior under test. Omitted `installation_mode` resolves to
`direct-skill`. Selecting `packaged-plugin` fails closed because this harness
does not install a plugin package or exercise Claude's namespaced plugin command.
`input_dir` is resolved relative to the
fixture file and cannot leave that directory. Input files are copied without following links and
hashed before the driver runs. `files_unchanged`, `changed_files_only`, and
`max_changed_input_files` compare the completed workspace with that exact input snapshot.
`changed_files_only` retains its historical name but now evaluates every entry; when a run creates
a new subdirectory, the allowlist must name that directory as well as its allowed files.

`adversarial: true` is a review obligation, not an informational tag. The runner converts it and
the ordered `review_requirements` into a deterministic, hash-bound `review_contract` in every run.
A schema-v3 perception review closes that exact contract by requirement ID; changing, omitting,
reordering, or adding a requirement changes the contract hash and invalidates stale closure.

`release_coverage` is explicit release-selection metadata. Mark a case only when it is genuinely
high-value and representative, then classify its primary surface mode, scope, and project stratum.
Strict release audit does not infer these judgments from free-form tags.

Automatic expectations are deterministic smoke checks. Output containment searches the complete
captured stream even when the JSON stores only a bounded 250,000-character head-and-tail
representation. File expectations are project-relative and cannot traverse a link, junction, or
reparse point.

For media-dependent design cases, use authorized immutable local assets, a human-readable brief,
and machine-readable provenance sufficient for the question. Define the media roles and the
fictional or documentary boundary from that case rather than assigning a universal shot list,
asset count, or image-to-text ratio. Include an accessible non-media path to any essential
information or action without requiring every aesthetic experience to become text-led.
`inputs/supplied-media-relay` is one reference fixture: its particular assets cover atmosphere,
human use, and material detail; their SHA-256 values are pinned; image generation and network
retrieval are forbidden during that run; and its public result must remain clearly fictional.

## Driver contract

Driver arguments can contain these placeholders:

- `{workspace}`: fresh writable project directory
- `{home}`: fresh fake user home
- `{prompt_file}`: UTF-8 prompt file
- `{request_json}`: structured v3 run request
- `{variant}`: `skill` or `baseline`
- `{case_id}`: fixture case ID
- `{skill_root}`: staged runtime route for skill runs, otherwise an empty string
- `{host}`: `codex` or `claude_code`

Only exact documented placeholder names are substituted. Other braces, such as JSON, CSS, object
literals, template syntax, and unknown brace-delimited text, remain literal.

The request document contains the suite, case, variant, resolved invocation mode, host, run ID and
number, prompt path, workspace, fake home, staged route, staged runtime content hash, frozen input
hash, and driver-report path. The driver also receives:

- `DESIGN_DNA_EVAL_REQUEST`
- `DESIGN_DNA_EVAL_VARIANT`
- `DESIGN_DNA_EVAL_HOST`
- `DESIGN_DNA_SKILL_ENABLED`
- `DESIGN_DNA_SKILL_ROOT`
- `DESIGN_DNA_DRIVER_REPORT`

`HOME`, `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `TEMP`, `TMP`, `CODEX_HOME`, and
`CLAUDE_CONFIG_DIR` point inside the run root. The parent environment is reduced to operating-system
execution essentials such as `PATH` and, on Windows, `SYSTEMROOT` and `COMSPEC`; credentials and
arbitrary caller variables are not inherited unless explicitly named with `--pass-env`. The leak
scan is a bounded exact-value control, not a general secret scanner; use a short-lived, least-
privilege evaluation credential and revoke it after the run. Drivers must still be treated as
trusted code because they can access the machine by paths or APIs available to their process.

On timeout, the harness terminates the driver process tree and records the run as timed out. It
captures stdout and stderr to files before producing a bounded head-and-tail JSON representation.
An output limit terminates drivers that attempt to produce an unbounded stream.

## Isolation and mutation rules

For a skill run, the canonical runtime is hashed, copied to the host-specific fake-home route, and
checked for exact content parity before and after driver execution. A baseline run starts and ends
with no Design DNA route. Each case input is frozen once, copied with parity checks for every run,
and rechecked after execution. In explicit mode, the skill instruction is the only intended prompt
delta. In implicit mode, prompt bytes are identical, the skill route is staged only for the skill
variant, and a skill run cannot pass without separately bound host-native discovery evidence.

Each monitor is snapshotted immediately before and after each run. Snapshots include directories and
all files, including names normally omitted from release manifests such as `__pycache__` and
`.pyc`. Creation, modification, deletion, or replacement of a monitor root fails only the run during
which it occurred, preserving attribution for later runs.

Evaluation inputs, workspace diffs, manifests, inventory limits, and promoted artifact bundles use
the same all-entry evidence view. It includes `__pycache__`, `.pyc`, `.pyo`, and empty directories,
so a driver cannot hide a mutation behind runtime-release exclusions. Entry count, file count, and
total file bytes are bounded independently. Runtime skill staging and release identities retain
their existing cache exclusions; the broader view applies only to evaluation evidence.

A link, junction, reparse point, unreadable entry, or unstable tree in a workspace or staged skill
must fail closed and be recorded as a run problem when attributable. Cleanup also refuses to
traverse unsafe entries; it preserves the exact failed run directory for manual recovery and reports
that path.

Never use the harness with untrusted drivers. Drivers must not deploy, contact production systems,
use real credentials, message people, or write outside the supplied workspace and fake home.
Monitoring is a mutation detector for declared roots, not a complete containment boundary.

## Result v3 contract

Each timestamped JSON document is validated against
`maintainer/schemas/eval-result.schema.json` and contains:

- canonical package version, path, and content hash;
- fixture, harness, schema, driver executable, argument-template, input-snapshot, environment-name,
  execution-order, limit, and cleanup provenance;
- a random per-session nonce, bounded session timestamps, and bounded per-run timestamps;
- driver contracts, resolved invocation modes, and the declared prompt delta;
- case, host, variant, and run identity;
- the deterministic review contract, including adversarial state, stable requirement IDs and
  hashes, and explicit release-coverage classification;
- task and prompt hashes;
- whether and which exact skill was staged and its before/after parity;
- the driver's explicitly labeled self-report, which is never treated as sole host-load proof;
- the retained per-run nonce challenge and separately hash-bound host-native adapter or telemetry
  response when supplied, including issue, observation, and capture times;
- return code, timeout, output-limit status, duration, full-stream hashes and byte counts, bounded
  output, and per-stream truncation status;
- per-run monitor hashes, bounded changed-entry lists, and snapshot errors;
- all-entry workspace content manifest, entry/file/byte counts, and hash plus a stable promoted
  bundle whose files and empty directories are re-hashed during strict package audit;
- changed paths, expectation or safety problems, and cleanup disposition;
- aggregate totals and per-variant totals.

Maintainers must also recompute semantic invariants during package audit: totals must equal the
actual runs, variant summaries must agree, task hashes must match between paired skill and baseline
runs, host and package identity must be current, skill staging fields must agree with the variant,
passing runs must not contain problems, and every emitted review contract must exactly match the
current fixture case.

## Review closure and release coverage

The infrastructure result is an input to review; a passing run does not close any visual or
adversarial requirement. Release reviews use
`maintainer/schemas/design-review.schema.json` schema version 3:

- every finding has a stable ID and an explicit lifecycle status;
- `verified` findings include resolution and verification records with hash-bound evidence;
- `fixed-unverified`, `deferred`, `blocked`, and unresolved medium/high findings cannot be hidden
  behind `pass` or `pass-with-limitations`;
- a clean `pass` has no unresolved findings; accepted low-risk limitations belong in
  `pass-with-limitations`;
- `requirement_closure` binds the exact run contract hash and records every required ID exactly
  once as `verified`, with rationale and hash-bound evidence;
- `owner_disposition` names the claim scope, accountable decision owner, exact build candidate,
  reviewed time, rationale, and hash-bound UTF-8 decision record. Accepted, rejected, and
  `not-required` decisions require attributable evidence that names those exact values. Pending
  decisions may retain hash-bound request or partial-feedback evidence but cannot close release.
  `not-required` is limited to the `standard` claim scope; premium, showcase, sale-readiness, and
  accountable-owner-sensitive claims require human acceptance.

Strict release audit requires each host marked `passed` to supply all of the following:

- at least four distinct cases explicitly marked high-value and representative;
- at least three passed skill runs and three passed baseline runs for every counted case, with
  exact artifact hashes and a contextual observation for every run; identical hashes are recorded
  and interpreted, not treated as an automatic failure or proof of quality;
- coverage of all four primary modes (Persuade, Experience, Operate, and Read) and at least two
  scopes;
- at least one established framework application with local data, state, assets, and scope-control
  constraints;
- at least one adversarial case;
- at least one implicit-discovery case with bound host-native evidence;
- same-case, same-run, same-build perception and implementation reviews for at least four counted
  cases, with an independent perception reviewer and bound mobile and desktop renders for each;
- exact requirement closure and structured skill-versus-baseline comparison for every counted
  review family, including observations for every repeated run, no baseline-stronger result on the
  core specificity dimensions, and at least one supported core skill benefit per host; every run
  observation cites a verified render, while explicitly source-only observations are segregated
  and cannot support visual claims;
- release-level cross-case analysis bound to counted render hashes, with
  `rendered_geometry` as the universal core and a neutral-label,
  identity-blinded first comparison observation. Identity blinding leaves the
  verified screenshot pixels unchanged; an optional pixel transformation is
  admissible only for a stated hypothesis or authorized privacy-minimization
  need and must bind authority, method, original and transformed hashes, and
  coverage impact. Additional lenses are selected from evidence in the actual
  projects and outputs. Typography, color or material behavior, labels,
  components, motion, media, CTA endings, and responsive transformation are
  non-exhaustive examples, not requirements.
  Record applicability and supporting evidence for every chosen lens; explain
  a not-applicable result instead of inventing counterevidence or manufacturing
  a difference. Similarity is not a defect and difference is not a quota. A
  repeated cluster must either remain an explicit blocker or carry cause-level
  resolution and hash-bound verification;
- at least one adversarial perception review on that same build family that closes every
  run-bound review requirement.

A host recorded as `blocked`, `untested`, or otherwise incomplete remains incomplete. Missing host
execution cannot be converted into a passing limitation.

Cross-case analysis schema 2 records this protocol in
`identity_blinded_comparison`. Each counted build keeps its original responsive
render hashes and a unique neutral label. Set `pixel_transformation` to `null`
for the default unchanged-pixel review; a non-null record must carry its
purpose, authorization evidence, method, original/transformed hash pairs, and
coverage impact.

## What results do and do not prove

Exit codes, strings, files, hashes, and mutation checks establish that the controlled driver ran
under the recorded contract and produced the recorded artifacts. A driver report establishes only
what that driver reported; it does not independently establish that the host loaded the skill.
These records do not prove design quality,
specificity, usability, accessibility, cultural fit, truthfulness, human authorship, or freedom from
generic patterns.

A release-quality behavioral evaluation must additionally use the runtime evaluation rubric,
render the exact result at the declared routes, states, viewports, and environments, and record:

- independent perception review;
- implementation and interaction review;
- target-user review when risk warrants it;
- skill-versus-baseline comparison;
- repeated-run convergence and diversity observations;
- decoded mobile and desktop renders bound by hash and pixel dimensions to the exact build;
- check-specific, hash-bound records for keyboard, focus, screen-reader, contrast, zoom/reflow,
  text spacing, reduced motion, and forced-colors claims;
- limitations and checks not performed.

Never convert the result into an “AI probability,” human-authorship claim, or guarantee of
undetectability. Treat every generated result as review input until the required reviewers have
approved the exact build.
