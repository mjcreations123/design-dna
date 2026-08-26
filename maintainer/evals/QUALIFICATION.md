# Evaluation reliability qualification

`run_evals.py` records individual executions. It does not, by itself, qualify a Design DNA
candidate. A release or promotion claim must pass the separate repeatability gate:

```text
python maintainer/scripts/summarize_eval_qualification.py <qualification-plan.json> --repository-root . --output <qualification-summary.json>
```

The summarizer consumes the runner's actual schema-v3 result JSON files. It does not accept a
manually reduced score list or a selected "best" artifact. Exit code `0` means the complete
predeclared matrix is **reliability-qualified**, `1` means it was summarized but did not qualify,
and `2` means the input could not be interpreted safely. Both nonzero outcomes are fail-closed.

This is a necessary release gate, not an aesthetic-review replacement. `run.passed` and blocker
state come from the execution result; independent perception and implementation reviews, exact
review-requirement closure, responsive render evidence, and the other release gates remain
separately required. A visually strong first output cannot establish reliability, and repeated
infrastructure passes cannot establish visual quality.

## Admission rule

A candidate is reliability-qualified only when all of these are true:

- the canonical plan hash is valid and every predeclared batch has exactly one pinned result file;
- the result and fixture bytes match their SHA-256 pins and validate against the current runner
  schemas;
- every fixture case is present in the predeclared case matrix, so an unclassified prompt cannot
  ride inside an otherwise admitted suite;
- result provenance names the current trusted runner, suite schema, and result schema;
- every planned case has at least three skill trials, every planned trial is present, every trial
  passes, and no trial has a blocker;
- `dev`, `immutable-regression`, and `promotion-holdout` all have complete case coverage;
- every prompt family has exactly one canonical case plus at least one task-distinct metamorphic
  variant;
- every result uses the candidate package hash declared before execution;
- model identity is concrete rather than `unreported`;
- a `controlled-skill-vs-baseline` claim has paired baseline trials and one exact model context,
  package hash, and driver identity; and
- any fixture containing a promotion-holdout case resolves outside the supplied public repository
  root, as does its result JSON because captured driver output can retain prompt text.

The minimum of three matches the release repetition floor. Set a higher
`minimum_trials_per_case` when the model, host, or risk warrants it. One attractive trial can have
`pass_at_1: 1.0` and `all_trials_pass: true` but still cannot qualify because it does not meet the
predeclared minimum.

## Partitions

- `dev` is the editable prompt set used while developing a change. It catches immediate behavior
  errors but is not independent evidence.
- `immutable-regression` is a known prompt set whose exact fixture SHA-256 is frozen in the plan.
  Change the fixture only by creating a new plan identity; do not silently update the pin.
- `promotion-holdout` is the protected decision set. Keep its fixture and result JSON outside the
  repository and outside public packages. The result's bounded stdout or stderr can contain task
  text. The summarizer rejects in-repository holdout material even when its bytes and declared hash
  match.

Passing a repository path that is narrower than the real public repository weakens the visibility
check. Use the checkout root (the default when running this repository's script).

## Prompt-family and metamorphic metadata

Each `case_matrix` entry declares a `prompt_family` and a `prompt_variant`:

- `canonical` is the single reference phrasing for a family;
- `semantics-preserving` changes wording while retaining the same intended outcome;
- `constraint-preserving` changes surrounding constraints while retaining the named invariant;
- `adversarial` applies misleading, conflicting, or high-pressure instructions while retaining the
  named invariant.

Variant IDs must be unique within the family. The exact task hashes must also differ, so duplicate
prompts cannot be relabeled as metamorphic coverage. `invariant` is reviewer-facing metadata that
states what must remain stable across the variation; it does not override the fixture or automatic
expectations.

## Predeclare the plan

The input contract is
`maintainer/schemas/eval-qualification-plan.schema.json`. The `plan` object is intentionally
separate from `result_files`, so the execution matrix can be hash-bound before result hashes exist.
A compact controlled plan has this shape:

```json
{
  "schema_version": 1,
  "record_type": "design-dna-eval-qualification-plan",
  "plan": {
    "qualification_id": "v-next-promotion-one",
    "suite": "promotion-suite",
    "created_at": "2026-08-23T12:00:00+00:00",
    "candidate_package_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "comparison_claim": "controlled-skill-vs-baseline",
    "expected_model_context": {
      "provider": "openai",
      "model": "gpt-example",
      "model_version": "2026-08-23",
      "reasoning_effort": "high",
      "generation_config": {
        "temperature": 0.2
      }
    },
    "minimum_trials_per_case": 3,
    "required_partitions": [
      "dev",
      "immutable-regression",
      "promotion-holdout"
    ],
    "case_matrix": [
      {
        "id": "family-canonical",
        "partition": "dev",
        "prompt_family": "service-flow",
        "prompt_variant": {
          "id": "canonical",
          "relation": "canonical",
          "invariant": "The primary service outcome and action remain clear."
        }
      },
      {
        "id": "family-paraphrase",
        "partition": "immutable-regression",
        "prompt_family": "service-flow",
        "prompt_variant": {
          "id": "paraphrase",
          "relation": "semantics-preserving",
          "invariant": "The primary service outcome and action remain clear."
        }
      },
      {
        "id": "family-pressure",
        "partition": "promotion-holdout",
        "prompt_family": "service-flow",
        "prompt_variant": {
          "id": "pressure",
          "relation": "adversarial",
          "invariant": "The primary service outcome and action remain clear."
        }
      }
    ],
    "batches": [
      {
        "id": "codex-primary",
        "host": "codex",
        "case_ids": [
          "family-canonical",
          "family-paraphrase",
          "family-pressure"
        ],
        "runs_per_case": 3,
        "fixture_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
      }
    ]
  },
  "plan_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "result_files": []
}
```

Calculate the canonical plan hash before execution:

```text
python maintainer/scripts/summarize_eval_qualification.py <qualification-plan.json> --print-plan-sha256
```

Paste that value into `plan_sha256`, then preserve the plan or its hash in an immutable CI or
release record. `created_at` must precede every admitted result. The plan hash prevents an
undisclosed matrix edit; it does not independently prove when or where the plan was committed.

Run each batch with the exact declared host, selected cases, fixture bytes, and `--runs` count.
Afterward append one reference per batch without changing `plan`:

```json
"result_files": [
  {
    "batch_id": "codex-primary",
    "path": "results/promotion-suite-codex-20260823-120000.json",
    "sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    "fixture_path": "C:/protected-evals/promotion-suite.json"
  }
]
```

On PowerShell, obtain the byte hash with:

```text
(Get-FileHash -Algorithm SHA256 -LiteralPath '<result.json>').Hash.ToLowerInvariant()
```

Paths may be absolute or relative to the plan file. A result's fixture path is required so the
summarizer can re-hash the exact suite, recompute task and prompt hashes, and enforce the public
repository boundary. Do not copy a protected fixture into the checkout for convenience.

## Metrics

The output contract is
`maintainer/schemas/eval-qualification-summary.schema.json`. Metrics are reported overall, for each
case, for each prompt family, and within each partition:

- `pass_at_1` is passing skill trials divided by all admitted skill trials.
- `all_trials_pass` is true only when every admitted trial passes with no blocker.
- `pass_power_k_empirical` is `(pass_at_1) ^ trial_count`, an empirical independence estimate that
  makes repeatability loss visible. It does not replace the exact all-trials gate.
- `blocker_rate` is blocker trials divided by all admitted trials. A failed run, a nonempty
  `problems` list, a timeout, or an output-limit event is a blocker.
- `worst_trial` is the deterministic blocker-first run record retained for diagnosis. When all
  trials tie, the stable run identity breaks the tie; it is not a claim of aesthetic scoring.

`integrity.plan_sha256` binds the predeclared matrix. `integrity.result_set_sha256` binds the sorted
result/fixture hash set. `integrity.report_sha256` hashes the canonical report before that final
field is inserted.

## Trust boundary

This gate detects omission relative to the declared batches, byte tampering, fixture substitution,
run-count drift, duplicate result/session reuse, task or prompt drift, public holdout leakage, and
false controlled-comparison metadata. It cannot prove that a maintainer did not backdate a new plan
or repeatedly execute a private batch and retain only a preferred first result. Use an immutable
external job record that stores the pre-run plan hash and the first produced result hash. Keep
protected prompt text and fixtures out of public logs and packages.
