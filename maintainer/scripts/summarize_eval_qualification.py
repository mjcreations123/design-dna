#!/usr/bin/env python3
"""Fail-closed repeatability qualification for Design DNA eval results.

This is deliberately separate from run_evals.py. It consumes the runner's
schema-v3 result documents only after a hash-bound plan declares the complete
case, partition, prompt-family, metamorphic-variant, and batch matrix.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from jsonschema import Draft202012Validator

from common import absolute, emit, is_within, load_json, strict_format_checker


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_ROOT = PACKAGE_ROOT / "maintainer" / "schemas"
PLAN_SCHEMA_PATH = SCHEMA_ROOT / "eval-qualification-plan.schema.json"
SUMMARY_SCHEMA_PATH = SCHEMA_ROOT / "eval-qualification-summary.schema.json"
RESULT_SCHEMA_PATH = SCHEMA_ROOT / "eval-result.schema.json"
SUITE_SCHEMA_PATH = PACKAGE_ROOT / "maintainer" / "evals" / "schema.json"
HARNESS_PATH = PACKAGE_ROOT / "maintainer" / "scripts" / "run_evals.py"
REQUIRED_PARTITIONS = (
    "dev",
    "immutable-regression",
    "promotion-holdout",
)
MODEL_COMPARISON_FIELDS = (
    "provider",
    "model",
    "model_version",
    "reasoning_effort",
    "generation_config",
)
MAX_SOURCE_BYTES = 128 * 1024 * 1024


class QualificationInputError(RuntimeError):
    """The qualification plan cannot be interpreted safely."""

    def __init__(self, failures: list[dict[str, str]]) -> None:
        super().__init__(failures[0]["message"] if failures else "invalid input")
        self.failures = failures


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest_value(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_text(value: str) -> str:
    return digest_bytes(value.encode("utf-8"))


def issue(code: str, message: str, path: str | None = None) -> dict[str, str]:
    result = {"code": code, "message": message}
    if path:
        result["path"] = path
    return result


def add_issue(
    failures: list[dict[str, str]],
    code: str,
    message: str,
    path: str | None = None,
) -> None:
    candidate = issue(code, message, path)
    key = (candidate["code"], candidate.get("path"), candidate["message"])
    existing = {
        (item["code"], item.get("path"), item["message"])
        for item in failures
    }
    if key not in existing:
        failures.append(candidate)


def json_pointer(parts: Iterable[object]) -> str:
    encoded = []
    for raw in parts:
        value = str(raw).replace("~", "~0").replace("/", "~1")
        encoded.append(value)
    return "/" + "/".join(encoded) if encoded else "/"


def schema_failures(
    payload: object,
    schema: object,
    *,
    code: str,
    prefix: str,
) -> list[dict[str, str]]:
    if not isinstance(schema, dict):
        return [issue("invalid-local-schema", "Local schema is not an object.")]
    errors = sorted(
        Draft202012Validator(
            schema,
            format_checker=strict_format_checker(),
        ).iter_errors(payload),
        key=lambda error: list(error.absolute_path),
    )
    return [
        issue(
            code,
            error.message,
            prefix + json_pointer(error.absolute_path),
        )
        for error in errors
    ]


def duplicate_free_json(data: bytes, path: Path) -> object:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        text = data.decode("utf-8")
        return json.loads(text, object_pairs_hook=reject_duplicates)
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise QualificationInputError(
            [issue("invalid-json", str(exc), str(path))]
        ) from exc


def stable_file_bytes(path: Path) -> bytes:
    try:
        first = path.stat()
        if not path.is_file():
            raise OSError("path is not a regular file")
        if first.st_size > MAX_SOURCE_BYTES:
            raise OSError(
                f"file exceeds the {MAX_SOURCE_BYTES}-byte qualification limit"
            )
        data = path.read_bytes()
        verification = path.read_bytes()
        second = path.stat()
    except OSError as exc:
        raise QualificationInputError(
            [issue("source-read-failed", str(exc), str(path))]
        ) from exc
    first_identity = (first.st_size, first.st_mtime_ns)
    second_identity = (second.st_size, second.st_mtime_ns)
    if (
        first_identity != second_identity
        or len(data) != second.st_size
        or data != verification
    ):
        raise QualificationInputError(
            [
                issue(
                    "source-changed-during-read",
                    "Source bytes changed while qualification was reading them.",
                    str(path),
                )
            ]
        )
    return data


def resolve_source(raw: str, plan_root: Path) -> Path:
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = plan_root / candidate
    try:
        return candidate.resolve(strict=True)
    except OSError as exc:
        raise QualificationInputError(
            [issue("source-path-invalid", str(exc), raw)]
        ) from exc


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def model_hash_valid(context: dict[str, object]) -> bool:
    core = {key: value for key, value in context.items() if key != "sha256"}
    return context.get("sha256") == digest_value(core)


def comparable_model_context(context: dict[str, object]) -> dict[str, object]:
    return {key: context.get(key) for key in MODEL_COMPARISON_FIELDS}


def effective_trial(
    run: dict[str, object],
    *,
    result_sha256: str,
) -> dict[str, object]:
    problems = [str(value) for value in run.get("problems", [])]
    if bool(run.get("timed_out")) and "timed_out" not in problems:
        problems.append("timed_out")
    if (
        bool(run.get("output_limit_exceeded"))
        and "output_limit_exceeded" not in problems
    ):
        problems.append("output_limit_exceeded")
    passed = bool(run.get("passed"))
    blocked = not passed or bool(problems)
    return {
        "source_result_sha256": result_sha256,
        "run_id": str(run["run_id"]),
        "case_id": str(run["case"]),
        "host": str(run["host"]),
        "run": int(run["run"]),
        "passed": passed and not blocked,
        "blocked": blocked,
        "problem_count": len(problems),
        "problems": problems,
    }


def worst_trial(trials: list[dict[str, object]]) -> dict[str, object] | None:
    if not trials:
        return None
    ordered = sorted(
        trials,
        key=lambda trial: (
            -int(bool(trial["blocked"])),
            -int(trial["problem_count"]),
            -int(not bool(trial["passed"])),
            str(trial["run_id"]),
            str(trial["source_result_sha256"]),
        ),
    )
    return dict(ordered[0])


def metrics(trials: list[dict[str, object]]) -> dict[str, object]:
    count = len(trials)
    passing = sum(bool(trial["passed"]) for trial in trials)
    blockers = sum(bool(trial["blocked"]) for trial in trials)
    pass_at_1 = passing / count if count else 0.0
    return {
        "trial_count": count,
        "passing_trials": passing,
        "blocker_trials": blockers,
        "pass_at_1": pass_at_1,
        "all_trials_pass": bool(count and passing == count and blockers == 0),
        "pass_power_k_empirical": pass_at_1**count if count else 0.0,
        "blocker_rate": blockers / count if count else 0.0,
        "worst_trial": worst_trial(trials),
    }


def summary_counts(runs: list[dict[str, object]]) -> dict[str, object]:
    passed = sum(bool(run.get("passed")) for run in runs)
    by_variant: dict[str, dict[str, int]] = {}
    for variant in ("skill", "baseline"):
        selected = [run for run in runs if run.get("variant") == variant]
        if selected:
            variant_passed = sum(bool(run.get("passed")) for run in selected)
            by_variant[variant] = {
                "total": len(selected),
                "passed": variant_passed,
                "failed": len(selected) - variant_passed,
            }
    return {
        "total": len(runs),
        "passed": passed,
        "failed": len(runs) - passed,
        "by_variant": by_variant,
    }


def validate_plan_semantics(
    plan: dict[str, object],
    failures: list[dict[str, str]],
) -> tuple[
    dict[str, dict[str, object]],
    dict[str, dict[str, object]],
    dict[str, list[dict[str, object]]],
    dict[str, int],
]:
    cases: dict[str, dict[str, object]] = {}
    families: dict[str, list[dict[str, object]]] = {}
    for index, case in enumerate(plan["case_matrix"]):
        case_id = str(case["id"])
        if case_id in cases:
            add_issue(
                failures,
                "duplicate-case-id",
                f"Case {case_id!r} appears more than once in the plan.",
                f"plan.case_matrix/{index}",
            )
            continue
        cases[case_id] = case
        families.setdefault(str(case["prompt_family"]), []).append(case)

    declared_partitions = set(plan["required_partitions"])
    required = set(REQUIRED_PARTITIONS)
    for missing in sorted(required - declared_partitions):
        add_issue(
            failures,
            "required-partition-declaration-missing",
            f"Qualification must require the {missing!r} partition.",
            "plan.required_partitions",
        )
    for partition in REQUIRED_PARTITIONS:
        if not any(case["partition"] == partition for case in cases.values()):
            add_issue(
                failures,
                "required-partition-uncovered",
                f"No planned case covers the {partition!r} partition.",
                "plan.case_matrix",
            )

    for family_id, family_cases in sorted(families.items()):
        variants = [str(case["prompt_variant"]["id"]) for case in family_cases]
        if len(set(variants)) != len(variants):
            add_issue(
                failures,
                "duplicate-prompt-variant",
                f"Prompt family {family_id!r} repeats a variant ID.",
                f"plan.case_matrix/{family_id}",
            )
        canonical_count = sum(
            case["prompt_variant"]["relation"] == "canonical"
            for case in family_cases
        )
        if canonical_count != 1:
            add_issue(
                failures,
                "prompt-family-canonical-count",
                (
                    f"Prompt family {family_id!r} must contain exactly one "
                    f"canonical case; found {canonical_count}."
                ),
                f"plan.case_matrix/{family_id}",
            )
        if len(family_cases) < 2 or not any(
            case["prompt_variant"]["relation"] != "canonical"
            for case in family_cases
        ):
            add_issue(
                failures,
                "prompt-family-metamorphic-coverage-missing",
                (
                    f"Prompt family {family_id!r} needs a canonical case and "
                    "at least one non-canonical metamorphic variant."
                ),
                f"plan.case_matrix/{family_id}",
            )

    batches: dict[str, dict[str, object]] = {}
    expected_trials = {case_id: 0 for case_id in cases}
    for index, batch in enumerate(plan["batches"]):
        batch_id = str(batch["id"])
        if batch_id in batches:
            add_issue(
                failures,
                "duplicate-batch-id",
                f"Batch {batch_id!r} appears more than once.",
                f"plan.batches/{index}",
            )
            continue
        batches[batch_id] = batch
        for case_id in batch["case_ids"]:
            if case_id not in cases:
                add_issue(
                    failures,
                    "unknown-batch-case",
                    f"Batch {batch_id!r} names unknown case {case_id!r}.",
                    f"plan.batches/{index}/case_ids",
                )
                continue
            expected_trials[str(case_id)] += int(batch["runs_per_case"])

    minimum = int(plan["minimum_trials_per_case"])
    for case_id, count in sorted(expected_trials.items()):
        if count < minimum:
            add_issue(
                failures,
                "insufficient-trials",
                (
                    f"Case {case_id!r} declares {count} trial(s); at least "
                    f"{minimum} are required."
                ),
                f"plan.case_matrix/{case_id}",
            )
    return cases, batches, families, expected_trials


def validate_model_contexts(
    result: dict[str, object],
    *,
    comparison_claim: str,
    expected: dict[str, object] | None,
    failures: list[dict[str, str]],
    path: str,
) -> str | None:
    drivers = result["drivers"]
    skill_driver = drivers["skill"]
    skill_context = skill_driver["model_context"]
    if not model_hash_valid(skill_context):
        add_issue(
            failures,
            "model-context-hash-mismatch",
            "Skill model-context SHA-256 does not match its canonical content.",
            path,
        )
    if skill_context["declaration_status"] != "declared":
        add_issue(
            failures,
            "model-context-unreported",
            "Qualification requires a concretely declared skill model context.",
            path,
        )
        return None
    comparable = comparable_model_context(skill_context)
    fingerprint = digest_value(comparable)
    if expected is not None and comparable != expected:
        add_issue(
            failures,
            "controlled-model-context-mismatch",
            "Skill model context differs from the hash-bound qualification plan.",
            path,
        )

    baseline_driver = drivers.get("baseline")
    if comparison_claim != "controlled-skill-vs-baseline":
        return fingerprint
    if not isinstance(baseline_driver, dict):
        add_issue(
            failures,
            "controlled-baseline-missing",
            "A controlled comparison requires a baseline driver and runs.",
            path,
        )
        return fingerprint
    baseline_context = baseline_driver["model_context"]
    if not model_hash_valid(baseline_context):
        add_issue(
            failures,
            "model-context-hash-mismatch",
            "Baseline model-context SHA-256 does not match its canonical content.",
            path,
        )
    if baseline_context["declaration_status"] != "declared":
        add_issue(
            failures,
            "model-context-unreported",
            "A controlled baseline requires a concrete model context.",
            path,
        )
    if comparable_model_context(baseline_context) != comparable:
        add_issue(
            failures,
            "controlled-model-context-mismatch",
            "Skill and baseline use different model contexts.",
            path,
        )
    driver_identity = (
        "sha256",
        "argument_template_sha256",
        "argument_count",
    )
    if any(skill_driver[key] != baseline_driver[key] for key in driver_identity):
        add_issue(
            failures,
            "controlled-driver-mismatch",
            "Skill and baseline use different driver identities or arguments.",
            path,
        )
    return fingerprint


def validate_result_semantics(
    result: dict[str, object],
    fixture: dict[str, object],
    *,
    result_sha256: str,
    batch: dict[str, object],
    plan: dict[str, object],
    cases: dict[str, dict[str, object]],
    failures: list[dict[str, str]],
    path: str,
) -> tuple[list[dict[str, object]], dict[str, str]]:
    expected_cases = [str(value) for value in batch["case_ids"]]
    selected_cases = [str(value) for value in result["provenance"]["selected_cases"]]
    if set(selected_cases) != set(expected_cases) or len(selected_cases) != len(
        expected_cases
    ):
        add_issue(
            failures,
            "batch-case-mismatch",
            "Result selected cases do not exactly match the predeclared batch.",
            path,
        )
    if result["provenance"]["runs_per_case"] != batch["runs_per_case"]:
        add_issue(
            failures,
            "batch-run-count-mismatch",
            "Result runs-per-case differs from the predeclared batch.",
            path,
        )
    if result["suite"] != plan["suite"]:
        add_issue(
            failures,
            "suite-mismatch",
            "Result suite differs from the qualification plan.",
            path,
        )
    if result["host"] != batch["host"]:
        add_issue(
            failures,
            "batch-host-mismatch",
            "Result host differs from the predeclared batch.",
            path,
        )
    if result["package"]["content_sha256"] != plan["candidate_package_sha256"]:
        add_issue(
            failures,
            "candidate-package-mismatch",
            "Result was produced from a different candidate package hash.",
            path,
        )

    fixture_cases = {str(case["id"]): case for case in fixture["cases"]}
    for case_id in expected_cases:
        if case_id not in fixture_cases:
            add_issue(
                failures,
                "fixture-case-missing",
                f"Fixture does not contain predeclared case {case_id!r}.",
                path,
            )

    runs = result["runs"]
    if result["summary"] != summary_counts(runs):
        add_issue(
            failures,
            "result-summary-mismatch",
            "Stored result summary does not match the actual run records.",
            path,
        )

    comparison_claim = str(plan["comparison_claim"])
    variants = (
        ("skill", "baseline")
        if comparison_claim == "controlled-skill-vs-baseline"
        else ("skill",)
    )
    by_identity: dict[tuple[str, str, int], dict[str, object]] = {}
    task_hashes: dict[str, str] = {}
    skill_trials: list[dict[str, object]] = []
    instruction = str(fixture["skill_instructions"][result["host"]])
    snapshot_records = result["provenance"]["input_snapshots"]

    for run_index, run in enumerate(runs):
        case_id = str(run["case"])
        variant = str(run["variant"])
        number = int(run["run"])
        run_path = f"{path}/runs/{run_index}"
        identity = (case_id, variant, number)
        if identity in by_identity:
            add_issue(
                failures,
                "duplicate-trial-identity",
                f"Result repeats trial identity {identity!r}.",
                run_path,
            )
        by_identity[identity] = run
        if case_id not in expected_cases:
            add_issue(
                failures,
                "unexpected-result-case",
                f"Result contains undeclared case {case_id!r}.",
                run_path,
            )
            continue
        expected_run_id = (
            f"{result['suite']}:{result['host']}:{case_id}:{variant}:{number}"
        )
        if run["run_id"] != expected_run_id:
            add_issue(
                failures,
                "run-id-mismatch",
                "Run ID does not match its suite, host, case, variant, and number.",
                run_path,
            )
        if run["host"] != result["host"]:
            add_issue(
                failures,
                "run-host-mismatch",
                "Run host differs from its result document.",
                run_path,
            )
        fixture_case = fixture_cases.get(case_id)
        if fixture_case is None:
            continue
        task = str(fixture_case["task"]).strip()
        task_sha256 = digest_text(task)
        if run["task_sha256"] != task_sha256:
            add_issue(
                failures,
                "task-hash-mismatch",
                "Run task hash does not match the hash-bound fixture task.",
                run_path,
            )
        previous_task = task_hashes.setdefault(case_id, str(run["task_sha256"]))
        if previous_task != run["task_sha256"]:
            add_issue(
                failures,
                "case-task-drift",
                f"Case {case_id!r} has multiple task hashes.",
                run_path,
            )
        prompt = f"Task: {task}"
        if variant == "skill" and run["invocation_mode"] == "explicit":
            prompt = f"{instruction}\n\n{prompt}"
        if run["prompt_sha256"] != digest_text(prompt):
            add_issue(
                failures,
                "prompt-hash-mismatch",
                "Run prompt hash does not match the fixture and invocation mode.",
                run_path,
            )
        snapshot = snapshot_records.get(case_id)
        if not isinstance(snapshot, dict) or (
            run["input_snapshot_sha256"] != snapshot.get("sha256")
        ):
            add_issue(
                failures,
                "input-snapshot-mismatch",
                "Run input hash does not match result provenance.",
                run_path,
            )
        if variant == "skill":
            if (
                not run["skill_staged"]
                or run["skill_content_sha256"]
                != plan["candidate_package_sha256"]
                or not run["skill_route_verified_before"]
                or not run["skill_route_verified_after"]
            ):
                add_issue(
                    failures,
                    "skill-route-integrity-failed",
                    "Skill trial lacks exact before/after candidate route parity.",
                    run_path,
                )
            if bool(run["passed"]) and (
                run["problems"]
                or run["timed_out"]
                or run["output_limit_exceeded"]
            ):
                add_issue(
                    failures,
                    "run-pass-safety-inconsistent",
                    "A passing run contains blocker or safety state.",
                    run_path,
                )
            skill_trials.append(
                effective_trial(run, result_sha256=result_sha256)
            )
        elif variant == "baseline":
            if run["skill_staged"] or run["skill_content_sha256"] is not None:
                add_issue(
                    failures,
                    "baseline-skill-contamination",
                    "Baseline run reports staged skill content.",
                    run_path,
                )

    expected_numbers = set(range(1, int(batch["runs_per_case"]) + 1))
    for case_id in expected_cases:
        for variant in variants:
            observed = {
                number
                for observed_case, observed_variant, number in by_identity
                if observed_case == case_id and observed_variant == variant
            }
            if observed != expected_numbers:
                add_issue(
                    failures,
                    "trial-sequence-incomplete",
                    (
                        f"{case_id!r} {variant} trials are {sorted(observed)}; "
                        f"expected {sorted(expected_numbers)}."
                    ),
                    path,
                )
        if comparison_claim == "controlled-skill-vs-baseline":
            for number in expected_numbers:
                skill = by_identity.get((case_id, "skill", number))
                baseline = by_identity.get((case_id, "baseline", number))
                if not isinstance(skill, dict) or not isinstance(baseline, dict):
                    continue
                paired_fields = (
                    "task_sha256",
                    "input_snapshot_sha256",
                    "invocation_mode",
                    "installation_mode",
                )
                if any(skill[field] != baseline[field] for field in paired_fields):
                    add_issue(
                        failures,
                        "controlled-pair-mismatch",
                        "Skill and baseline trial pair does not share control inputs.",
                        path,
                    )

    return skill_trials, task_hashes


def summarize_plan(
    plan_path: Path,
    *,
    repository_root: Path = PACKAGE_ROOT,
) -> dict[str, object]:
    plan_path = absolute(plan_path)
    plan_bytes = stable_file_bytes(plan_path)
    manifest = duplicate_free_json(plan_bytes, plan_path)
    plan_schema = load_json(PLAN_SCHEMA_PATH)
    initial_failures = schema_failures(
        manifest,
        plan_schema,
        code="qualification-plan-schema-invalid",
        prefix="plan",
    )
    if initial_failures:
        raise QualificationInputError(initial_failures)
    assert isinstance(manifest, dict)
    plan = manifest["plan"]
    assert isinstance(plan, dict)

    failures: list[dict[str, str]] = []
    calculated_plan_sha256 = digest_value(plan)
    if manifest["plan_sha256"] != calculated_plan_sha256:
        add_issue(
            failures,
            "plan-sha256-mismatch",
            "Plan SHA-256 does not match its canonical plan object.",
            "plan_sha256",
        )
    cases, batches, families, expected_trials = validate_plan_semantics(
        plan,
        failures,
    )

    result_refs = manifest["result_files"]
    if not result_refs:
        add_issue(
            failures,
            "empty-results",
            "Qualification requires actual eval result JSON files.",
            "result_files",
        )
    refs_by_batch: dict[str, list[tuple[int, dict[str, object]]]] = {}
    for index, reference in enumerate(result_refs):
        refs_by_batch.setdefault(str(reference["batch_id"]), []).append(
            (index, reference)
        )
        if reference["batch_id"] not in batches:
            add_issue(
                failures,
                "unknown-result-batch",
                f"Result references unknown batch {reference['batch_id']!r}.",
                f"result_files/{index}",
            )
    for batch_id in batches:
        references = refs_by_batch.get(batch_id, [])
        if not references:
            add_issue(
                failures,
                "missing-batch-result",
                f"Predeclared batch {batch_id!r} has no result file.",
                "result_files",
            )
        elif len(references) > 1:
            add_issue(
                failures,
                "duplicate-batch-result",
                f"Predeclared batch {batch_id!r} has multiple result files.",
                "result_files",
            )

    result_set_records = []
    for reference in result_refs:
        batch = batches.get(str(reference["batch_id"]))
        result_set_records.append(
            {
                "batch_id": reference["batch_id"],
                "result_sha256": reference["sha256"],
                "fixture_sha256": (
                    batch["fixture_sha256"] if batch is not None else None
                ),
            }
        )
    result_set_records.sort(
        key=lambda value: (
            str(value["batch_id"]),
            str(value["result_sha256"]),
        )
    )
    result_set_sha256 = digest_value(result_set_records)

    result_schema = load_json(RESULT_SCHEMA_PATH)
    suite_schema = load_json(SUITE_SCHEMA_PATH)
    trusted_hashes = {
        "result_schema": digest_bytes(stable_file_bytes(RESULT_SCHEMA_PATH)),
        "suite_schema": digest_bytes(stable_file_bytes(SUITE_SCHEMA_PATH)),
        "harness": digest_bytes(stable_file_bytes(HARNESS_PATH)),
    }
    try:
        repository_root = repository_root.resolve(strict=True)
    except OSError as exc:
        raise QualificationInputError(
            [issue("repository-root-invalid", str(exc), str(repository_root))]
        ) from exc

    all_trials: list[dict[str, object]] = []
    case_task_hashes: dict[str, set[str]] = {case_id: set() for case_id in cases}
    seen_result_hashes: set[str] = set()
    seen_sessions: set[str] = set()
    controlled_package_hashes: set[str] = set()
    controlled_model_fingerprints: set[str] = set()
    validated_result_files = 0
    plan_created_at = parse_datetime(str(plan["created_at"]))

    for index, reference in enumerate(result_refs):
        reference_path = f"result_files/{index}"
        batch = batches.get(str(reference["batch_id"]))
        if batch is None:
            continue
        if reference["sha256"] in seen_result_hashes:
            add_issue(
                failures,
                "duplicate-result-sha256",
                "The same result bytes cannot satisfy multiple predeclared batches.",
                reference_path,
            )
            continue
        seen_result_hashes.add(str(reference["sha256"]))
        try:
            result_path = resolve_source(str(reference["path"]), plan_path.parent)
            result_bytes = stable_file_bytes(result_path)
        except QualificationInputError as exc:
            for failure in exc.failures:
                add_issue(
                    failures,
                    failure["code"],
                    failure["message"],
                    reference_path,
                )
            continue
        actual_result_sha256 = digest_bytes(result_bytes)
        if actual_result_sha256 != reference["sha256"]:
            add_issue(
                failures,
                "result-sha256-mismatch",
                "Result bytes differ from the plan's pinned SHA-256.",
                reference_path,
            )
            continue
        try:
            result = duplicate_free_json(result_bytes, result_path)
        except QualificationInputError as exc:
            failures.extend(exc.failures)
            continue
        result_errors = schema_failures(
            result,
            result_schema,
            code="eval-result-schema-invalid",
            prefix=reference_path + "/result",
        )
        if result_errors:
            failures.extend(result_errors)
            continue
        assert isinstance(result, dict)

        try:
            fixture_path = resolve_source(
                str(reference["fixture_path"]),
                plan_path.parent,
            )
            fixture_bytes = stable_file_bytes(fixture_path)
        except QualificationInputError as exc:
            for failure in exc.failures:
                add_issue(
                    failures,
                    failure["code"],
                    failure["message"],
                    reference_path + "/fixture_path",
                )
            continue
        fixture_sha256 = digest_bytes(fixture_bytes)
        if fixture_sha256 != batch["fixture_sha256"]:
            add_issue(
                failures,
                "fixture-sha256-mismatch",
                "Fixture bytes differ from the predeclared batch hash.",
                reference_path,
            )
            continue
        if result["provenance"]["fixture_sha256"] != fixture_sha256:
            add_issue(
                failures,
                "result-fixture-binding-mismatch",
                "Result provenance is not bound to the supplied fixture bytes.",
                reference_path,
            )
            continue
        try:
            fixture = duplicate_free_json(fixture_bytes, fixture_path)
        except QualificationInputError as exc:
            failures.extend(exc.failures)
            continue
        fixture_errors = schema_failures(
            fixture,
            suite_schema,
            code="eval-fixture-schema-invalid",
            prefix=reference_path + "/fixture",
        )
        if fixture_errors:
            failures.extend(fixture_errors)
            continue
        assert isinstance(fixture, dict)
        fixture_case_ids = {str(case["id"]) for case in fixture["cases"]}
        undeclared_fixture_cases = fixture_case_ids - set(cases)
        if undeclared_fixture_cases:
            add_issue(
                failures,
                "fixture-case-matrix-mismatch",
                (
                    "Fixture contains cases absent from the predeclared matrix: "
                    + ", ".join(sorted(undeclared_fixture_cases))
                    + "."
                ),
                reference_path + "/fixture",
            )
        holdout_ids = {
            case_id
            for case_id, case in cases.items()
            if case["partition"] == "promotion-holdout"
        }
        contains_holdout = bool(fixture_case_ids & holdout_ids)
        if contains_holdout:
            if is_within(fixture_path, repository_root):
                add_issue(
                    failures,
                    "public-promotion-holdout-fixture",
                    (
                        "Promotion-holdout task fixtures must remain outside the "
                        "public repository tree."
                    ),
                    reference_path + "/fixture_path",
                )
            if is_within(result_path, repository_root):
                add_issue(
                    failures,
                    "public-promotion-holdout-result",
                    (
                        "Promotion-holdout result JSON may retain prompt text in "
                        "captured output and must remain outside the public "
                        "repository tree."
                    ),
                    reference_path + "/path",
                )

        provenance = result["provenance"]
        provenance_expectations = (
            ("result_schema_sha256", trusted_hashes["result_schema"]),
            ("suite_schema_sha256", trusted_hashes["suite_schema"]),
            ("harness_sha256", trusted_hashes["harness"]),
        )
        for field, trusted in provenance_expectations:
            if provenance[field] != trusted:
                add_issue(
                    failures,
                    "untrusted-eval-provenance",
                    f"Result {field} differs from the local trusted source.",
                    reference_path,
                )
        if parse_datetime(str(result["started_at"])) < plan_created_at:
            add_issue(
                failures,
                "result-predates-plan",
                "Result started before the declared qualification plan existed.",
                reference_path,
            )
        session_nonce = str(result["session_nonce"])
        if session_nonce in seen_sessions:
            add_issue(
                failures,
                "duplicate-result-session",
                "Qualification cannot reuse an evaluation session nonce.",
                reference_path,
            )
        seen_sessions.add(session_nonce)

        controlled_package_hashes.add(str(result["package"]["content_sha256"]))
        expected_model = plan.get("expected_model_context")
        model_fingerprint = validate_model_contexts(
            result,
            comparison_claim=str(plan["comparison_claim"]),
            expected=(expected_model if isinstance(expected_model, dict) else None),
            failures=failures,
            path=reference_path,
        )
        if model_fingerprint is not None:
            controlled_model_fingerprints.add(model_fingerprint)

        trials, task_hashes = validate_result_semantics(
            result,
            fixture,
            result_sha256=actual_result_sha256,
            batch=batch,
            plan=plan,
            cases=cases,
            failures=failures,
            path=reference_path,
        )
        all_trials.extend(trials)
        for case_id, task_sha256 in task_hashes.items():
            if case_id in case_task_hashes:
                case_task_hashes[case_id].add(task_sha256)
        validated_result_files += 1

    if plan["comparison_claim"] == "controlled-skill-vs-baseline":
        if len(controlled_package_hashes) > 1:
            add_issue(
                failures,
                "controlled-package-hash-mixed",
                "Controlled comparison contains multiple candidate package hashes.",
                "result_files",
            )
        if len(controlled_model_fingerprints) > 1:
            add_issue(
                failures,
                "controlled-model-context-mixed",
                "Controlled comparison contains multiple skill model contexts.",
                "result_files",
            )

    for family_id, family_cases in sorted(families.items()):
        observed_hashes: dict[str, str] = {}
        for case in family_cases:
            case_id = str(case["id"])
            hashes = case_task_hashes.get(case_id, set())
            if len(hashes) > 1:
                add_issue(
                    failures,
                    "case-task-drift",
                    f"Case {case_id!r} has multiple task hashes.",
                    f"plan.case_matrix/{case_id}",
                )
            if len(hashes) == 1:
                task_hash = next(iter(hashes))
                if task_hash in observed_hashes:
                    add_issue(
                        failures,
                        "metamorphic-task-not-distinct",
                        (
                            f"Prompt-family variants {observed_hashes[task_hash]!r} "
                            f"and {case_id!r} have identical task hashes."
                        ),
                        f"plan.case_matrix/{family_id}",
                    )
                observed_hashes[task_hash] = case_id

    case_trials: dict[str, list[dict[str, object]]] = {
        case_id: [] for case_id in cases
    }
    for trial in all_trials:
        case_id = str(trial["case_id"])
        if case_id in case_trials:
            case_trials[case_id].append(trial)

    case_reports: list[dict[str, object]] = []
    for case_id, case in sorted(cases.items()):
        observed = case_trials[case_id]
        expected = expected_trials[case_id]
        if len(observed) != expected:
            add_issue(
                failures,
                "case-trial-count-mismatch",
                (
                    f"Case {case_id!r} has {len(observed)} observed skill trials; "
                    f"expected {expected}."
                ),
                f"plan.case_matrix/{case_id}",
            )
        case_metrics = metrics(observed)
        if observed and not case_metrics["all_trials_pass"]:
            add_issue(
                failures,
                "case-trials-not-all-pass",
                f"Case {case_id!r} did not pass every predeclared trial.",
                f"plan.case_matrix/{case_id}",
            )
        case_reports.append(
            {
                "case_id": case_id,
                "partition": case["partition"],
                "prompt_family": case["prompt_family"],
                "prompt_variant": case["prompt_variant"]["id"],
                "metamorphic_relation": case["prompt_variant"]["relation"],
                "expected_trials": expected,
                "metrics": case_metrics,
            }
        )

    family_reports: list[dict[str, object]] = []
    for family_id, family_cases in sorted(families.items()):
        family_case_ids = sorted(str(case["id"]) for case in family_cases)
        family_trials = [
            trial
            for case_id in family_case_ids
            for trial in case_trials[case_id]
        ]
        family_reports.append(
            {
                "prompt_family": family_id,
                "case_ids": family_case_ids,
                "partitions": sorted(
                    {str(case["partition"]) for case in family_cases}
                ),
                "variants": [
                    {
                        "case_id": str(case["id"]),
                        "variant_id": str(case["prompt_variant"]["id"]),
                        "relation": str(case["prompt_variant"]["relation"]),
                    }
                    for case in sorted(
                        family_cases,
                        key=lambda value: str(value["id"]),
                    )
                ],
                "metrics": metrics(family_trials),
            }
        )

    partition_reports: list[dict[str, object]] = []
    declared_partitions = set(plan["required_partitions"])
    for partition in REQUIRED_PARTITIONS:
        planned = sorted(
            case_id
            for case_id, case in cases.items()
            if case["partition"] == partition
        )
        observed = sorted(case_id for case_id in planned if case_trials[case_id])
        partition_trials = [
            trial for case_id in planned for trial in case_trials[case_id]
        ]
        covered = bool(planned) and all(
            len(case_trials[case_id]) == expected_trials[case_id]
            and expected_trials[case_id] >= int(plan["minimum_trials_per_case"])
            for case_id in planned
        )
        partition_reports.append(
            {
                "partition": partition,
                "required": partition in declared_partitions,
                "covered": covered,
                "planned_cases": planned,
                "observed_cases": observed,
                "metrics": metrics(partition_trials),
            }
        )

    overall = metrics(all_trials)
    qualified = not failures and bool(overall["all_trials_pass"])
    report: dict[str, object] = {
        "schema_version": 1,
        "record_type": "design-dna-eval-qualification-summary",
        "qualification_id": plan["qualification_id"],
        "suite": plan["suite"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "qualified": qualified,
        "comparison_claim": plan["comparison_claim"],
        "candidate_package_sha256": plan["candidate_package_sha256"],
        "integrity": {
            "algorithm": "sha256-canonical-json-v1",
            "plan_sha256": calculated_plan_sha256,
            "result_set_sha256": result_set_sha256,
        },
        "counts": {
            "declared_result_files": len(result_refs),
            "validated_result_files": validated_result_files,
            "planned_cases": len(cases),
            "prompt_families": len(families),
            "trials": len(all_trials),
            "passing_trials": sum(bool(trial["passed"]) for trial in all_trials),
            "blocker_trials": sum(bool(trial["blocked"]) for trial in all_trials),
        },
        "partition_coverage": partition_reports,
        "cases": case_reports,
        "families": family_reports,
        "overall": overall,
        "failures": failures,
    }
    report_hash = digest_value(report)
    report["integrity"]["report_sha256"] = report_hash
    summary_schema = load_json(SUMMARY_SCHEMA_PATH)
    output_errors = schema_failures(
        report,
        summary_schema,
        code="qualification-summary-schema-invalid",
        prefix="summary",
    )
    if output_errors:
        raise QualificationInputError(output_errors)
    return report


def atomic_write(path: Path, payload: dict[str, object]) -> None:
    destination = absolute(path)
    if not destination.parent.is_dir():
        raise QualificationInputError(
            [
                issue(
                    "output-parent-missing",
                    "Output parent directory must already exist.",
                    str(destination.parent),
                )
            ]
        )
    data = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )
    temporary: Path | None = None
    try:
        descriptor, raw_path = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
        )
        temporary = Path(raw_path)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        temporary = None
    except OSError as exc:
        raise QualificationInputError(
            [issue("output-write-failed", str(exc), str(destination))]
        ) from exc
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description=(
            "Summarize hash-bound repeated eval results and fail closed unless "
            "every planned trial and partition qualifies."
        )
    )
    result.add_argument("plan", type=Path)
    result.add_argument(
        "--repository-root",
        type=Path,
        default=PACKAGE_ROOT,
        help="Public repository boundary used to protect promotion holdouts.",
    )
    result.add_argument("--output", type=Path)
    result.add_argument(
        "--print-plan-sha256",
        action="store_true",
        help="Print the canonical SHA-256 of only the plan object and exit.",
    )
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.print_plan_sha256:
            plan_path = absolute(args.plan)
            payload = duplicate_free_json(stable_file_bytes(plan_path), plan_path)
            if not isinstance(payload, dict) or not isinstance(
                payload.get("plan"),
                dict,
            ):
                raise QualificationInputError(
                    [
                        issue(
                            "qualification-plan-missing",
                            "Document must contain a plan object.",
                            str(plan_path),
                        )
                    ]
                )
            emit({"plan_sha256": digest_value(payload["plan"])})
            return 0
        report = summarize_plan(
            args.plan,
            repository_root=args.repository_root,
        )
        if args.output:
            atomic_write(args.output, report)
        emit(report)
        return 0 if report["qualified"] else 1
    except QualificationInputError as exc:
        emit({"ok": False, "qualified": False, "failures": exc.failures})
        return 2
    except (OSError, ValueError, TypeError, KeyError) as exc:
        emit(
            {
                "ok": False,
                "qualified": False,
                "failures": [
                    issue("qualification-failed", str(exc))
                ],
            }
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
