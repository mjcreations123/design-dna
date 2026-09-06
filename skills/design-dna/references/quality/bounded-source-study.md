# Bounded source study and internal proofs

## Contents

[Progress and termination](#progress-and-termination) |
[Gesture and closed-root coverage](#gesture-and-closed-root-coverage-boundaries) |
[Internal proof slice](#one-internal-proof-slice) |
[Reporting boundaries](#report-what-each-result-establishes)

Read this when observing a reference, recovering from failed research, or
testing the skill with one internal first screen. The public selection and
final-build requirements in [Reference-led direction](reference-led-direction.md)
remain in force.

## Progress and termination

Use the packaged observer and recorder. Their source-study controller records
new frames, events, targets, routes, states, the last progress timestamp, and
the exact configured bounds. The progress JSON and hash-chained JSONL are
operational evidence. A timer heartbeat or another unchanged screenshot is
not evidence that missing source coverage was completed.

The default no-progress bound is 60 seconds and a screenshot is bounded to 30
seconds. The observer's total budget is derived from its declared route
scope: 90 minutes for the primary route with its passes, scroll-hold
traversal and states, plus 8 minutes for each route at both profiles, so the
total budget is clamped to a four-hour hard ceiling. The default route
ceiling is 1000. Resource bounds never establish complete coverage.
The recorder's budget is 60 minutes
default; its 90-second-per-profile minimum remains required and its requested
dwell is capped at 600 seconds per profile to reserve processing time within
the whole-command budget. Per-step bounds are derived from each step's own
scope (a mechanism pass or scroll traversal may take 240 settled positions; a
census walks every discovered target) and may end a run earlier. Those bounds
stop the attempt and preserve incomplete evidence; they never turn a partial
source into a qualified one.

The observer studies the primary route, every authored-state route, and
discovered inner routes. `--max-inner-routes` is a resource ceiling (default
1000, minimum 2). Remaining discovered routes are recorded as unvisited and
make the study ineligible, even when the declared ceiling was reached.
Authored-state routes never substitute for missing inner-route coverage.

Use one active study per source. Do not fan out duplicate observers while an
earlier attempt is still running. Before another attempt, inspect its progress
and terminal artifact, close its owned browser/process, and record the changed
input or repaired blocker. Reuse of the same run ID/output is refused to keep
the existing artifact chain intact. Do not delete evidence to make a rerun look
fresh or launch unchanged retries until a task's time is consumed.

After an unexpected process/machine exit, a source-output or shared-machine
lease may remain. The next command preserves it and reports the exact path and
recorded owner as a typed recovery blocker. Do not automatically delete or
steal it: verify that the named owner is no longer running and no same-output
study is active, then recover only that exact stale lease. Ambiguous ownership
stays blocked. Ordinary completion releases its own lease.

The packaged recovery is `node scripts/source_study_leases.mjs --list`, which
reports both machine-wide runner slots and their recorded owners, and
`--recover` (with `--output-lock FILE` for a source-output lease), which
removes only a lease whose owner PID is provably gone, after a second probe
and a token re-check, and appends the removal to `recovery-log.jsonl` beside
the slots. Acquisition never recovers anything on its own. Check the owner PID
with a real process query first; a filtered `tasklist` piped through `grep`
has reported live owners dead on Windows.

Per-event callback frames on the source surface watch are advisory. They are
taken outside the study controller with a 12 s bound and capped at four per
watch for animation-tick events; a slow or capped frame is recorded as a typed
skip or capture failure and the study continues. A surface that appears is
always captured, and every event still needs its before and after frames, so
an overlay that animates on the first screen no longer ends the observation.

The recorder supports the audited Playwright `1.61.1` dependency bundle. It
uses that version's encoder artifact for real byte-progress evidence; a merely
launchable browser or an untested newer/private API is insufficient. Use the
pinned shared bundle when maintaining the source package, or provision that
exact version through `DESIGN_DNA_PLAYWRIGHT_MODULE_DIR` for an installed
runtime. The runtime does not
silently upgrade the website's dependencies.

A failed attempt retains captured artifact identities and the exact cause:
missing coverage, no progress, target/route loop, expanding graph, screenshot
timeout, lost browser/document, ambiguous consent, inaccessible source, or
postprocessing failure. If writing a failure artifact also fails, the terminal
error must retain the original cause and say which evidence could not be
committed. A stale active snapshot cannot be reported as continuing work.

Only a completed public-source study with current observation, recording,
artifact hashes, and required quality/coverage evidence may participate in
public selection. Partial, failed, blocked-consent, inaccessible, rejected,
and proof-only material is ineligible. A source's accessible screenshot does
not erase its failed behavioral study. Report a source defect separately from
a tool or capture defect.

The recorder's representative wide/narrow captures bind generated screenshots
of the actual primary source entry, its exact successful navigation, and its
video/frame time. The raw video retains its entire timeline, including the
pre-navigation blank frame; that frame cannot represent the studied source.

## Gesture and closed-root coverage boundaries

Registered event listeners are code-hook candidates, not proof of a custom
gesture. The generated inventory preserves neutral delegated hooks as
`unverified-code-hook-candidate`, with `observed_gesture_behavior: false`;
review those candidates alongside the actual source encounter. Do not infer a
required custom gesture from generic event delegation, or claim those hooks
were exercised. Visible drag/range/grab affordances, gesture-specific cues,
and direct rendered-mutation hooks create explicit unsupported coverage gaps
until the exact material behavior can be observed. Framework names grant no
exception, and newly discovered material behavior reopens the source study.

Visible content inside an unaddressable closed shadow root also leaves a
typed coverage gap, with its exact host and observed material kind. This is
a limitation of the capture protocol, not a verdict that the source design is
defective. It blocks both public qualification and a proof that would omit
that visible component; empty, style-only, or invisible roots do not invent
a material failure. An image sequence changing its source URL during decode
is likewise reported as an unsettled proof state, not mislabeled broken media.

## One internal proof slice

When full research is blocked, a useful local specimen is allowed only if one
exact source state supports its entire primary screen. It requires a current
brief, actual wide/narrow arrangement captures, generated proof-source
observation, and a component map covering every visible element's measured
layout, typography, color, spacing, control, and media relationship. If those
inputs are absent, create no visible specimen and report the missing inputs.

Use [proof-slice-template.json](../../templates/proof-slice-template.json).
Keep the visible label `Internal unverified proof slice — not for public
release`. The packaged builder connects the declared source to the exact
served output, and the proof scanner checks both viewport profiles, the
visible label, component/style/media coverage, and absence of extra routes,
sections, or embedded surfaces. The label is internal status, not part of the
borrowed source's design or public copy.

Run the separate proof gate:

```text
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/gate.py" --project "<PROJECT_ROOT>" --build-id "<IMMUTABLE_PROOF_BUILD_ID>" --phase proof-slice --proof-slice .design-dna/proof-slice.json
```

Its immutable result belongs to the internal specimen. It never emits a
standard first-screen authorization or grants permission for another section.
Run the ordinary first-screen and final gates after complete public research
qualifies the selected sources. Failed or absent formal gates leave the
requested website blocked.

## Report what each result establishes

Report research status, source observation status, implementation status,
proof-slice status, proof gate result, standard first-screen result, final gate
result, and any tested local/deployed/live/owner-approved status separately.
Quote the actual verdict. Use `the gate did not run` when appropriate.
Do not call a failed broad build a finished concept or use its link as a
successful deliverable. An explicitly labeled internal specimen can be shown
with its limitations and full failure record.

For a finished-site link, run `scripts/delivery_status.py --project <PROJECT>`.
It delegates to the complete packaged readiness validator and reports current
local evidence eligibility, with a blocked exit status on stale or absent
evidence. It does not infer deployment, live verification, or owner acceptance.

Hashes establish byte identity and expose drift; locally writable records are
not cryptographic proof that an untrusted producer obeyed every instruction.
Mechanical checks enforce their stated observations. Aesthetic quality,
recognition of the source's main experience, cultural acceptance, and owner
approval still need attributable review; never fabricate those conclusions.
