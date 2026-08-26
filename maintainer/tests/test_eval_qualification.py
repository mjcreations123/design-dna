from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[2]
SCRIPTS = PLUGIN / "maintainer" / "scripts"
RUNNER = SCRIPTS / "run_evals.py"
SUMMARIZER = SCRIPTS / "summarize_eval_qualification.py"
SKILL = PLUGIN / "skills" / "design-dna"

sys.path.insert(0, str(SCRIPTS))
try:
    import summarize_eval_qualification as qualification
finally:
    sys.path.pop(0)


DRIVER_CODE = (
    "from pathlib import Path; import sys; "
    "prompt=Path(sys.argv[1]).read_text(encoding='utf-8'); print(prompt); "
    "Path('index.html').write_text('<main>qualified</main>', encoding='utf-8')"
)

CASES = (
    (
        "family-canonical",
        "Create the primary service page with a clear booking path.",
        "dev",
        "canonical",
        "canonical",
    ),
    (
        "family-paraphrase",
        "Build the same service page, preserving the booking path and outcome.",
        "immutable-regression",
        "paraphrase",
        "semantics-preserving",
    ),
    (
        "family-pressure",
        "Repair the service page under conflicting style pressure; keep booking clear.",
        "promotion-holdout",
        "pressure",
        "adversarial",
    ),
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def seal(manifest: dict[str, object]) -> None:
    manifest["plan_sha256"] = qualification.digest_value(manifest["plan"])


def result_summary(runs: list[dict[str, object]]) -> dict[str, object]:
    return qualification.summary_counts(runs)


class EvalQualificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.fixture = cls.root / "protected-suite.json"
        write_json(
            cls.fixture,
            {
                "schema_version": 3,
                "suite": "qualification-suite",
                "skill_instructions": {
                    "codex": (
                        "Use $design-dna for this task and follow its runtime contract."
                    ),
                    "claude_code": (
                        "Use /design-dna for this task and follow its runtime contract."
                    ),
                },
                "cases": [
                    {
                        "id": case_id,
                        "task": task,
                        "review_requirements": [
                            "Inspect the exact output against the case invariant."
                        ],
                        "expected": {
                            "exit_codes": [0],
                            "files_exist": ["index.html"],
                            "file_contains": {
                                "index.html": ["<main>qualified</main>"]
                            },
                        },
                    }
                    for case_id, task, _, _, _ in CASES
                ],
            },
        )
        work = cls.root / "work"
        results = cls.root / "results"
        work.mkdir()
        results.mkdir()
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                str(cls.fixture),
                "--host",
                "codex",
                "--skill-root",
                str(SKILL),
                "--driver",
                sys.executable,
                "--driver-arg=-c",
                f"--driver-arg={DRIVER_CODE}",
                "--driver-arg={prompt_file}",
                "--baseline-driver",
                sys.executable,
                "--baseline-arg=-c",
                f"--baseline-arg={DRIVER_CODE}",
                "--baseline-arg={prompt_file}",
                "--skill-provider",
                "openai",
                "--skill-model",
                "gpt-test",
                "--skill-model-version",
                "2026-08-23",
                "--skill-reasoning-effort",
                "high",
                "--skill-generation-config",
                "temperature=0.2",
                "--runs",
                "3",
                "--work-root",
                str(work),
                "--results-dir",
                str(results),
            ],
            text=True,
            encoding="utf-8",
            capture_output=True,
            env=environment,
            timeout=180,
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stdout + completed.stderr)
        result_paths = list(results.glob("*.json"))
        if len(result_paths) != 1:
            raise AssertionError(f"expected one eval result, found {result_paths}")
        cls.result_path = result_paths[0]
        cls.result = json.loads(cls.result_path.read_text(encoding="utf-8"))
        context = cls.result["drivers"]["skill"]["model_context"]
        cls.expected_model = {
            key: copy.deepcopy(context[key])
            for key in qualification.MODEL_COMPARISON_FIELDS
        }
        cls.base_manifest = {
            "schema_version": 1,
            "record_type": "design-dna-eval-qualification-plan",
            "plan": {
                "qualification_id": "release-candidate-one",
                "suite": "qualification-suite",
                "created_at": "2026-01-01T00:00:00+00:00",
                "candidate_package_sha256": cls.result["package"][
                    "content_sha256"
                ],
                "comparison_claim": "controlled-skill-vs-baseline",
                "expected_model_context": cls.expected_model,
                "minimum_trials_per_case": 3,
                "required_partitions": [
                    "dev",
                    "immutable-regression",
                    "promotion-holdout",
                ],
                "case_matrix": [
                    {
                        "id": case_id,
                        "partition": partition,
                        "prompt_family": "service-booking",
                        "prompt_variant": {
                            "id": variant_id,
                            "relation": relation,
                            "invariant": (
                                "The booking path and service outcome remain clear."
                            ),
                        },
                    }
                    for case_id, _, partition, variant_id, relation in CASES
                ],
                "batches": [
                    {
                        "id": "codex-primary",
                        "host": "codex",
                        "case_ids": [case_id for case_id, *_ in CASES],
                        "runs_per_case": 3,
                        "fixture_sha256": sha256_file(cls.fixture),
                    }
                ],
            },
            "plan_sha256": "0" * 64,
            "result_files": [
                {
                    "batch_id": "codex-primary",
                    "path": str(cls.result_path),
                    "sha256": sha256_file(cls.result_path),
                    "fixture_path": str(cls.fixture),
                }
            ],
        }
        seal(cls.base_manifest)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def run_summary(
        self,
        manifest: dict[str, object],
        *,
        repository_root: Path = PLUGIN,
        output: bool = False,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan_path = root / "qualification-plan.json"
            write_json(plan_path, manifest)
            command = [
                sys.executable,
                str(SUMMARIZER),
                str(plan_path),
                "--repository-root",
                str(repository_root),
            ]
            output_path = root / "summary.json"
            if output:
                command.extend(["--output", str(output_path)])
            environment = os.environ.copy()
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            completed = subprocess.run(
                command,
                text=True,
                encoding="utf-8",
                capture_output=True,
                env=environment,
                timeout=60,
            )
            payload = json.loads(completed.stdout)
            if output and output_path.exists():
                self.assertEqual(
                    json.loads(output_path.read_text(encoding="utf-8")),
                    payload,
                )
            return completed, payload

    def write_result(
        self,
        root: Path,
        payload: dict[str, object],
        name: str = "result.json",
    ) -> Path:
        path = root / name
        write_json(path, payload)
        return path

    def bind_result(
        self,
        manifest: dict[str, object],
        path: Path,
        *,
        reference_index: int = 0,
    ) -> None:
        reference = manifest["result_files"][reference_index]
        reference["path"] = str(path)
        reference["sha256"] = sha256_file(path)

    def failure_codes(self, payload: dict[str, object]) -> set[str]:
        return {str(failure["code"]) for failure in payload["failures"]}

    def test_actual_eval_result_qualifies_only_with_repeatable_full_coverage(
        self,
    ) -> None:
        manifest = copy.deepcopy(self.base_manifest)
        completed, report = self.run_summary(manifest, output=True)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertTrue(report["qualified"])
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["counts"]["trials"], 9)
        self.assertEqual(report["overall"]["pass_at_1"], 1.0)
        self.assertTrue(report["overall"]["all_trials_pass"])
        self.assertEqual(report["overall"]["pass_power_k_empirical"], 1.0)
        self.assertEqual(report["overall"]["blocker_rate"], 0.0)
        self.assertEqual(
            {entry["partition"] for entry in report["partition_coverage"]},
            {"dev", "immutable-regression", "promotion-holdout"},
        )
        self.assertTrue(
            all(entry["covered"] for entry in report["partition_coverage"])
        )
        family = report["families"][0]
        self.assertEqual(family["prompt_family"], "service-booking")
        self.assertEqual(family["metrics"]["trial_count"], 9)
        logical = copy.deepcopy(report)
        report_hash = logical["integrity"].pop("report_sha256")
        self.assertEqual(report_hash, qualification.digest_value(logical))

    def test_one_attractive_trial_per_case_cannot_qualify(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = copy.deepcopy(self.result)
            result["runs"] = [run for run in result["runs"] if run["run"] == 1]
            result["provenance"]["runs_per_case"] = 1
            result["summary"] = result_summary(result["runs"])
            result_path = self.write_result(root, result)
            manifest = copy.deepcopy(self.base_manifest)
            manifest["plan"]["batches"][0]["runs_per_case"] = 1
            self.bind_result(manifest, result_path)
            seal(manifest)

            completed, report = self.run_summary(manifest)
            self.assertEqual(completed.returncode, 1)
            self.assertFalse(report["qualified"])
            self.assertIn("insufficient-trials", self.failure_codes(report))
            self.assertEqual(report["overall"]["pass_at_1"], 1.0)
            self.assertTrue(report["overall"]["all_trials_pass"])

    def test_failed_trial_controls_metrics_and_worst_trial(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = copy.deepcopy(self.result)
            failed = next(
                run
                for run in result["runs"]
                if run["case"] == "family-canonical"
                and run["variant"] == "skill"
                and run["run"] == 2
            )
            failed["passed"] = False
            failed["problems"] = ["visual blocker"]
            failed["returncode"] = 1
            result["summary"] = result_summary(result["runs"])
            result_path = self.write_result(root, result)
            manifest = copy.deepcopy(self.base_manifest)
            self.bind_result(manifest, result_path)

            completed, report = self.run_summary(manifest)
            self.assertEqual(completed.returncode, 1)
            self.assertFalse(report["qualified"])
            case = next(
                item
                for item in report["cases"]
                if item["case_id"] == "family-canonical"
            )
            self.assertAlmostEqual(case["metrics"]["pass_at_1"], 2 / 3)
            self.assertFalse(case["metrics"]["all_trials_pass"])
            self.assertAlmostEqual(
                case["metrics"]["pass_power_k_empirical"],
                (2 / 3) ** 3,
            )
            self.assertAlmostEqual(case["metrics"]["blocker_rate"], 1 / 3)
            self.assertTrue(case["metrics"]["worst_trial"]["blocked"])
            self.assertEqual(
                case["metrics"]["worst_trial"]["problems"],
                ["visual blocker"],
            )

    def test_empty_results_and_missing_partition_fail_closed(self) -> None:
        empty = copy.deepcopy(self.base_manifest)
        empty["result_files"] = []
        completed, report = self.run_summary(empty)
        self.assertEqual(completed.returncode, 1)
        self.assertFalse(report["qualified"])
        self.assertIn("empty-results", self.failure_codes(report))
        self.assertIn("missing-batch-result", self.failure_codes(report))

        missing = copy.deepcopy(self.base_manifest)
        missing["plan"]["required_partitions"].remove("promotion-holdout")
        seal(missing)
        completed, report = self.run_summary(missing)
        self.assertEqual(completed.returncode, 1)
        self.assertIn(
            "required-partition-declaration-missing",
            self.failure_codes(report),
        )

    def test_public_in_repository_holdout_fixture_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "public-repository"
            repository.mkdir()
            public_fixture = repository / "promotion-holdout.json"
            public_fixture.write_bytes(self.fixture.read_bytes())
            manifest = copy.deepcopy(self.base_manifest)
            manifest["result_files"][0]["fixture_path"] = str(public_fixture)

            completed, report = self.run_summary(
                manifest,
                repository_root=repository,
            )
            self.assertEqual(completed.returncode, 1)
            self.assertFalse(report["qualified"])
            self.assertIn(
                "public-promotion-holdout-fixture",
                self.failure_codes(report),
            )

    def test_public_in_repository_holdout_result_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "public-repository"
            repository.mkdir()
            public_result = repository / "promotion-result.json"
            public_result.write_bytes(self.result_path.read_bytes())
            manifest = copy.deepcopy(self.base_manifest)
            self.bind_result(manifest, public_result)

            completed, report = self.run_summary(
                manifest,
                repository_root=repository,
            )
            self.assertEqual(completed.returncode, 1)
            self.assertFalse(report["qualified"])
            self.assertIn(
                "public-promotion-holdout-result",
                self.failure_codes(report),
            )

    def test_controlled_comparison_rejects_mixed_package_and_model(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            second = copy.deepcopy(self.result)
            second["session_nonce"] = "f" * 64
            second["package"]["content_sha256"] = "e" * 64
            for run in second["runs"]:
                if run["variant"] == "skill":
                    run["skill_content_sha256"] = "e" * 64
            for variant in ("skill", "baseline"):
                context = second["drivers"][variant]["model_context"]
                context["model"] = "gpt-other"
                core = {key: value for key, value in context.items() if key != "sha256"}
                context["sha256"] = qualification.digest_value(core)
            second_path = self.write_result(root, second, "second.json")

            manifest = copy.deepcopy(self.base_manifest)
            manifest["plan"]["batches"].append(
                {
                    "id": "codex-second",
                    "host": "codex",
                    "case_ids": [case_id for case_id, *_ in CASES],
                    "runs_per_case": 3,
                    "fixture_sha256": sha256_file(self.fixture),
                }
            )
            manifest["result_files"].append(
                {
                    "batch_id": "codex-second",
                    "path": str(second_path),
                    "sha256": sha256_file(second_path),
                    "fixture_path": str(self.fixture),
                }
            )
            seal(manifest)

            completed, report = self.run_summary(manifest)
            self.assertEqual(completed.returncode, 1)
            codes = self.failure_codes(report)
            self.assertIn("controlled-package-hash-mixed", codes)
            self.assertIn("controlled-model-context-mixed", codes)
            self.assertFalse(report["qualified"])

    def test_prompt_family_metadata_requires_one_canonical_variant(self) -> None:
        manifest = copy.deepcopy(self.base_manifest)
        manifest["plan"]["case_matrix"][1]["prompt_variant"][
            "relation"
        ] = "canonical"
        seal(manifest)
        completed, report = self.run_summary(manifest)
        self.assertEqual(completed.returncode, 1)
        self.assertIn(
            "prompt-family-canonical-count",
            self.failure_codes(report),
        )

    def test_result_and_plan_hash_tampering_is_visible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tampered_result = root / "tampered.json"
            tampered_result.write_bytes(self.result_path.read_bytes() + b"\n")
            manifest = copy.deepcopy(self.base_manifest)
            manifest["result_files"][0]["path"] = str(tampered_result)
            completed, report = self.run_summary(manifest)
            self.assertEqual(completed.returncode, 1)
            self.assertIn("result-sha256-mismatch", self.failure_codes(report))

            stale_plan = copy.deepcopy(self.base_manifest)
            stale_plan["plan"]["minimum_trials_per_case"] = 4
            completed, report = self.run_summary(stale_plan)
            self.assertEqual(completed.returncode, 1)
            self.assertIn("plan-sha256-mismatch", self.failure_codes(report))


if __name__ == "__main__":
    unittest.main()
