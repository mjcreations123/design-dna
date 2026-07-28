from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[2]
SCRIPTS = PLUGIN / "maintainer" / "scripts"
RUNNER = SCRIPTS / "run_evals.py"
SKILL = PLUGIN / "skills" / "design-dna"

sys.path.insert(0, str(SCRIPTS))
try:
    from common import content_manifest, eval_content_manifest
finally:
    sys.path.pop(0)


DRIVER_CODE = (
    "from pathlib import Path; import sys; "
    "prompt=Path(sys.argv[1]).read_text(encoding='utf-8'); print(prompt); "
    "Path('index.html').write_text('<main>evaluation</main>', encoding='utf-8'); "
    "Path('style.css').write_text('main { display: block; }', encoding='utf-8')"
)


def write_suite(
    path: Path,
    *,
    suite: str,
    cases: list[dict[str, object]],
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "suite": suite,
                "skill_instructions": {
                    "codex": (
                        "Use $design-dna for this task and follow its runtime contract."
                    ),
                    "claude_code": (
                        "Use /design-dna for this task and follow its runtime contract."
                    ),
                },
                "cases": cases,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def run_harness(
    fixture: Path,
    work: Path,
    results: Path,
    *extra: str,
    host: str = "codex",
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            str(fixture),
            "--host",
            host,
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
            "--work-root",
            str(work),
            "--results-dir",
            str(results),
            *extra,
        ],
        text=True,
        encoding="utf-8",
        capture_output=True,
        env=environment,
        timeout=120,
    )


def load_only_result(results: Path) -> dict[str, object]:
    documents = list(results.glob("*.json"))
    if len(documents) != 1:
        raise AssertionError(
            f"expected one top-level result JSON, found {len(documents)}"
        )
    return json.loads(documents[0].read_text(encoding="utf-8"))


def respond_to_host_challenges(
    evidence_root: Path,
    stop: threading.Event,
    *,
    observed_at: str | None = None,
) -> None:
    """Act as a separate adapter that only sees the challenge mailbox."""
    completed: set[str] = set()
    while not stop.is_set():
        challenge_root = evidence_root / "challenges"
        response_root = evidence_root / "responses"
        if challenge_root.is_dir() and response_root.is_dir():
            for challenge_path in challenge_root.glob("*.json"):
                if challenge_path.name in completed:
                    continue
                try:
                    challenge_bytes = challenge_path.read_bytes()
                    challenge = json.loads(challenge_bytes)
                except (OSError, json.JSONDecodeError):
                    continue
                response = {
                    "schema_version": 2,
                    "challenge_id": challenge["challenge_id"],
                    "challenge_sha256": hashlib.sha256(
                        challenge_bytes
                    ).hexdigest(),
                    "session_nonce": challenge["session_nonce"],
                    "run_nonce": challenge["run_nonce"],
                    "host": challenge["host"],
                    "case": challenge["case"],
                    "variant": challenge["variant"],
                    "run": challenge["run"],
                    "run_id": challenge["run_id"],
                    "skill_loaded": challenge["skill_loaded"],
                    "skill_content_sha256": challenge[
                        "skill_content_sha256"
                    ],
                    "method": "host-adapter-event",
                    "source_id": "mock-host-adapter-test",
                    "source_version": "1.0.0",
                    "observed_at": (
                        observed_at
                        or datetime.now(timezone.utc).isoformat()
                    ),
                }
                destination = response_root / challenge_path.name
                staging = response_root / f".{challenge_path.name}.staging"
                try:
                    staging.write_text(
                        json.dumps(response, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    staging.replace(destination)
                except OSError:
                    continue
                completed.add(challenge_path.name)
        time.sleep(0.01)


class EvalInvocationContractTests(unittest.TestCase):
    def assert_stable_bundle(
        self,
        results: Path,
        run: dict[str, object],
    ) -> None:
        bundle = run["artifact_bundle"]
        self.assertIsInstance(bundle, dict)
        bundle_path = results / bundle["path"]
        self.assertTrue(bundle_path.is_dir(), bundle_path)
        records, content_hash = eval_content_manifest(bundle_path)
        self.assertEqual(content_hash, run["workspace_sha256"])
        self.assertEqual(content_hash, bundle["sha256"])
        self.assertEqual(records, run["files"])
        self.assertEqual(bundle["entry_count"], len(records))
        self.assertEqual(
            bundle["file_count"],
            sum(item["type"] == "file" for item in records),
        )
        self.assertEqual(
            bundle["bytes"],
            sum(
                int(item["size"])
                for item in records
                if item["type"] == "file"
            ),
        )

    def test_default_explicit_and_unverified_implicit_prompt_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = root / "suite.json"
            work = root / "work"
            results = root / "results"
            work.mkdir()
            results.mkdir()
            write_suite(
                fixture,
                suite="invocation-contract",
                cases=[
                    {
                        "id": "default-explicit",
                        "task": (
                            "Create a small local website for an evaluation fixture."
                        ),
                        "review_requirements": [
                            "Inspect the exact prompt and retained artifacts."
                        ],
                        "expected": {
                            "exit_codes": [0],
                            "files_exist": ["index.html", "style.css"],
                        },
                    },
                    {
                        "id": "neutral-implicit",
                        "invocation_mode": "implicit",
                        "task": (
                            "Create a polished responsive one-page website for a "
                            "neighborhood bakery using dependency-free local files."
                        ),
                        "review_requirements": [
                            "Require host-native telemetry before claiming discovery."
                        ],
                        "expected": {
                            "exit_codes": [0],
                            "files_exist": ["index.html", "style.css"],
                        },
                    },
                ],
            )

            result = run_harness(
                fixture,
                work,
                results,
                "--keep-workspaces",
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            document = load_only_result(results)
            runs = {
                (item["case"], item["variant"]): item
                for item in document["runs"]
            }
            self.assertEqual(document["summary"]["total"], 4)
            self.assertEqual(document["summary"]["passed"], 3)
            self.assertEqual(
                document["prompt_contract"]["invocation_modes"],
                {
                    "default-explicit": "explicit",
                    "neutral-implicit": "implicit",
                },
            )

            explicit_skill = runs[("default-explicit", "skill")]
            explicit_baseline = runs[("default-explicit", "baseline")]
            self.assertEqual(explicit_skill["invocation_mode"], "explicit")
            self.assertEqual(explicit_baseline["invocation_mode"], "explicit")
            self.assertNotEqual(
                explicit_skill["prompt_sha256"],
                explicit_baseline["prompt_sha256"],
            )
            self.assertIn("$design-dna", explicit_skill["stdout"])
            self.assertNotIn("$design-dna", explicit_baseline["stdout"])
            self.assertTrue(explicit_skill["passed"])
            self.assertTrue(explicit_baseline["passed"])

            implicit_skill = runs[("neutral-implicit", "skill")]
            implicit_baseline = runs[("neutral-implicit", "baseline")]
            self.assertEqual(implicit_skill["invocation_mode"], "implicit")
            self.assertEqual(implicit_baseline["invocation_mode"], "implicit")
            self.assertEqual(
                implicit_skill["prompt_sha256"],
                implicit_baseline["prompt_sha256"],
            )
            self.assertNotIn("$design-dna", implicit_skill["stdout"])
            self.assertEqual(implicit_skill["stdout"], implicit_baseline["stdout"])
            self.assertEqual(
                implicit_skill["host_native_evidence_status"],
                "missing",
            )
            self.assertFalse(implicit_skill["passed"])
            self.assertTrue(
                any(
                    "host-native" in problem
                    for problem in implicit_skill["problems"]
                )
            )
            self.assertTrue(implicit_baseline["passed"])
            self.assertEqual(
                implicit_baseline["host_native_evidence_status"],
                "not_requested",
            )

            for run in runs.values():
                workspace = Path(run["workspace"])
                request = json.loads(
                    (workspace.parent / "request.json").read_text(
                        encoding="utf-8"
                    )
                )
                prompt = (workspace.parent / "prompt.txt").read_text(
                    encoding="utf-8"
                )
                self.assertEqual(
                    request["invocation_mode"],
                    run["invocation_mode"],
                )
                self.assertEqual(
                    hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                    run["prompt_sha256"],
                )
                staged_route = (
                    Path(request["home"])
                    / ".agents"
                    / "skills"
                    / "design-dna"
                )
                if run["variant"] == "skill":
                    self.assertTrue(staged_route.is_dir())
                    self.assertEqual(
                        request["skill_root"],
                        str(staged_route),
                    )
                else:
                    self.assertFalse(staged_route.exists())
                    self.assertIsNone(request["skill_root"])
                self.assert_stable_bundle(results, run)

    def test_explicit_instruction_matches_the_selected_host(self) -> None:
        for host, invocation, route_parts in (
            ("codex", "$design-dna", (".agents", "skills", "design-dna")),
            (
                "claude_code",
                "/design-dna",
                (".claude", "skills", "design-dna"),
            ),
        ):
            with self.subTest(host=host), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "suite.json"
                work = root / "work"
                results = root / "results"
                work.mkdir()
                results.mkdir()
                write_suite(
                    fixture,
                    suite=f"{host.replace('_', '-')}-explicit-contract",
                    cases=[{
                        "id": "explicit-route",
                        "task": "Create a local interface for host-routing verification.",
                        "review_requirements": [
                            "Inspect the exact host-specific invocation and route."
                        ],
                        "expected": {
                            "exit_codes": [0],
                            "files_exist": ["index.html", "style.css"],
                        },
                    }],
                )
                result = run_harness(
                    fixture,
                    work,
                    results,
                    "--keep-workspaces",
                    host=host,
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    result.stdout + result.stderr,
                )
                document = load_only_result(results)
                runs = {
                    item["variant"]: item for item in document["runs"]
                }
                self.assertEqual(document["host"], host)
                self.assertIn(
                    invocation,
                    document["prompt_contract"]["skill_instruction"],
                )
                self.assertIn(invocation, runs["skill"]["stdout"])
                other_invocation = (
                    "/design-dna" if invocation == "$design-dna" else "$design-dna"
                )
                self.assertNotIn(other_invocation, runs["skill"]["stdout"])
                self.assertNotIn(invocation, runs["baseline"]["stdout"])
                request = json.loads(
                    (
                        Path(runs["skill"]["workspace"]).parent
                        / "request.json"
                    ).read_text(encoding="utf-8")
                )
                expected_route = Path(request["home"]).joinpath(*route_parts)
                self.assertEqual(Path(request["skill_root"]), expected_route)
                self.assertTrue(expected_route.is_dir())

    def test_bound_mock_host_event_permits_structural_implicit_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = root / "suite.json"
            work = root / "work"
            results = root / "results"
            evidence = root / "host-evidence-source"
            work.mkdir()
            results.mkdir()
            evidence.mkdir()
            suite = "implicit-telemetry-contract"
            case = "neutral-implicit"
            task = (
                "Create a current responsive website concept for a local repair "
                "service using only dependency-free local files."
            )
            write_suite(
                fixture,
                suite=suite,
                cases=[
                    {
                        "id": case,
                        "invocation_mode": "implicit",
                        "task": task,
                        "review_requirements": [
                            "Bind independently supplied mock adapter telemetry."
                        ],
                        "expected": {
                            "exit_codes": [0],
                            "files_exist": ["index.html", "style.css"],
                        },
                    }
                ],
            )
            stop = threading.Event()
            responder = threading.Thread(
                target=respond_to_host_challenges,
                args=(evidence, stop),
                daemon=True,
            )
            responder.start()
            try:
                result = run_harness(
                    fixture,
                    work,
                    results,
                    "--host-native-evidence-dir",
                    str(evidence),
                    "--host-native-evidence-timeout",
                    "2",
                )
            finally:
                stop.set()
                responder.join(timeout=5)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            document = load_only_result(results)
            runs = {item["variant"]: item for item in document["runs"]}
            self.assertEqual(document["summary"]["passed"], 2)
            challenges = [
                run["host_native_challenge"] for run in runs.values()
            ]
            self.assertEqual(
                len({item["challenge_id"] for item in challenges}),
                len(challenges),
            )
            self.assertEqual(
                len({item["run_nonce"] for item in challenges}),
                len(challenges),
            )
            self.assertEqual(
                {item["session_nonce"] for item in challenges},
                {document["session_nonce"]},
            )
            self.assertTrue(runs["skill"]["passed"])
            self.assertEqual(
                runs["skill"]["host_native_evidence_status"],
                "bound",
            )
            bound = runs["skill"]["host_native_evidence"]
            challenge = runs["skill"]["host_native_challenge"]
            self.assertEqual(challenge["session_nonce"], document["session_nonce"])
            self.assertEqual(bound["session_nonce"], document["session_nonce"])
            self.assertEqual(bound["run_nonce"], challenge["run_nonce"])
            self.assertEqual(bound["challenge_id"], challenge["challenge_id"])
            self.assertEqual(bound["challenge_sha256"], challenge["sha256"])
            challenge_path = results / challenge["path"]
            self.assertTrue(challenge_path.is_file())
            self.assertEqual(
                hashlib.sha256(challenge_path.read_bytes()).hexdigest(),
                challenge["sha256"],
            )
            bound_path = results / bound["path"]
            self.assertTrue(bound_path.is_file())
            self.assertEqual(
                hashlib.sha256(bound_path.read_bytes()).hexdigest(),
                bound["sha256"],
            )
            self.assertTrue(runs["baseline"]["passed"])
            self.assertFalse(runs["baseline"]["skill_staged"])
            self.assertEqual(
                runs["skill"]["prompt_sha256"],
                runs["baseline"]["prompt_sha256"],
            )
            self.assertNotIn("$design-dna", runs["skill"]["stdout"])
            for run in runs.values():
                self.assert_stable_bundle(results, run)
            sys.path.insert(0, str(SCRIPTS))
            try:
                from audit_package import (
                    eval_semantic_failures,
                    fixture_catalog,
                )
            finally:
                sys.path.pop(0)
            catalog, catalog_failures = fixture_catalog(root)
            self.assertEqual(catalog_failures, [])
            self.assertEqual(
                eval_semantic_failures(
                    document,
                    catalog,
                    "challenge-bound-result",
                    harness_path=RUNNER,
                    suite_schema_path=(
                        PLUGIN / "maintainer" / "evals" / "schema.json"
                    ),
                    result_schema_path=(
                        PLUGIN
                        / "maintainer"
                        / "schemas"
                        / "eval-result.schema.json"
                    ),
                    result_path=next(results.glob("*.json")),
                ),
                [],
            )

    def test_stale_and_future_host_events_are_rejected(self) -> None:
        for timestamp, fragment in (
            ("2000-01-01T00:00:00+00:00", "predates this run"),
            ("2099-01-01T00:00:00+00:00", "in the future"),
        ):
            with self.subTest(timestamp=timestamp), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "suite.json"
                work = root / "work"
                results = root / "results"
                evidence = root / "host-evidence-source"
                work.mkdir()
                results.mkdir()
                evidence.mkdir()
                write_suite(
                    fixture,
                    suite="host-event-time-contract",
                    cases=[
                        {
                            "id": "neutral-implicit",
                            "invocation_mode": "implicit",
                            "task": (
                                "Create a dependency-free local website for "
                                "challenge timing validation."
                            ),
                            "review_requirements": [
                                "Reject evidence outside the current run window."
                            ],
                            "expected": {
                                "exit_codes": [0],
                                "files_exist": ["index.html", "style.css"],
                            },
                        }
                    ],
                )
                stop = threading.Event()
                responder = threading.Thread(
                    target=respond_to_host_challenges,
                    args=(evidence, stop),
                    kwargs={"observed_at": timestamp},
                    daemon=True,
                )
                responder.start()
                try:
                    result = run_harness(
                        fixture,
                        work,
                        results,
                        "--host-native-evidence-dir",
                        str(evidence),
                        "--host-native-evidence-timeout",
                        "2",
                    )
                finally:
                    stop.set()
                    responder.join(timeout=5)
                self.assertEqual(
                    result.returncode,
                    1,
                    result.stdout + result.stderr,
                )
                document = load_only_result(results)
                skill_run = next(
                    run
                    for run in document["runs"]
                    if run["variant"] == "skill"
                )
                self.assertFalse(skill_run["passed"])
                self.assertEqual(
                    skill_run["host_native_evidence_status"],
                    "invalid",
                )
                self.assertTrue(
                    any(fragment in problem for problem in skill_run["problems"]),
                    skill_run["problems"],
                )


if __name__ == "__main__":
    unittest.main()
