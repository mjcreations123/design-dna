from __future__ import annotations

import copy
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker


PLUGIN = Path(__file__).resolve().parents[2]
SCRIPTS = PLUGIN / "maintainer" / "scripts"
SCHEMAS = PLUGIN / "maintainer" / "schemas"
sys.path.insert(0, str(SCRIPTS))
try:
    import attest_tests
    import audit_package
finally:
    sys.path.remove(str(SCRIPTS))


def make_attestation_fixture(root: Path) -> Path:
    plugin = root / "plugin"
    maintainer = plugin / "maintainer"
    for name in ("tests", "scripts", "schemas"):
        directory = maintainer / name
        directory.mkdir(parents=True)
        (directory / f"{name}.txt").write_text(
            f"stable {name}\n",
            encoding="utf-8",
        )
    shutil.copy2(
        PLUGIN / "maintainer" / "requirements-dev.txt",
        maintainer / "requirements-dev.txt",
    )
    return plugin


def fake_unittest_result(
    command: list[str],
    *,
    passed: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    if passed:
        stderr = (
            "test_one (suite.Case.test_one) ... ok\n"
            "test_two (suite.Case.test_two) ... skipped 'fixture'\n"
            "\n"
            "----------------------------------------------------------------------\n"
            "Ran 2 tests in 0.010s\n"
            "\n"
            "OK (skipped=1)\n"
        ).encode("utf-8")
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=stderr)
    stderr = (
        "test_one (suite.Case.test_one) ... FAIL\n"
        "\n"
        "----------------------------------------------------------------------\n"
        "Ran 1 test in 0.010s\n"
        "\n"
        "FAILED (failures=1)\n"
    ).encode("utf-8")
    return subprocess.CompletedProcess(command, 1, stdout=b"", stderr=stderr)


def write_skill(path: Path, marker: str = "same") -> None:
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text(
        "---\n"
        "name: design-dna\n"
        "description: Route proof fixture.\n"
        "---\n\n"
        f"# Design DNA\n\n{marker}\n",
        encoding="utf-8",
    )


def after_timestamp(value: str, *, hours: int = 0, seconds: int = 0) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (
        parsed + timedelta(hours=hours, seconds=seconds)
    ).isoformat().replace("+00:00", "Z")


def remove_test_tree(path: Path) -> None:
    """Remove a known temporary fixture tree even when copied files are read-only."""

    if path.name != "attestations" or path.parent.name != "maintainer":
        raise AssertionError(f"unexpected test cleanup target: {path}")

    def clear_readonly_and_retry(operation, target: str, _error) -> None:
        os.chmod(target, os.stat(target).st_mode | stat.S_IWRITE)
        operation(target)

    shutil.rmtree(path, onerror=clear_readonly_and_retry)


def run_detect(
    canonical: Path,
    roots: list[Path],
    expected: list[Path],
    output: Path,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        "-B",
        str(SCRIPTS / "detect_routes.py"),
        "--canonical",
        str(canonical),
    ]
    for root in roots:
        command.extend(("--root", str(root)))
    for route in expected:
        command.extend(("--expected", str(route)))
    command.extend(("--output", str(output)))
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONUTF8"] = "1"
    return subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        capture_output=True,
        env=environment,
        timeout=120,
    )


class TestAttestationTests(unittest.TestCase):
    def test_attestation_hashes_exclude_but_reject_compiled_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_attestation_fixture(Path(temporary))
            baseline = attest_tests.attested_input_hashes(plugin)
            scripts = plugin / "maintainer" / "scripts"
            tests = plugin / "maintainer" / "tests"
            cache = scripts / "__pycache__"
            cache.mkdir()
            (cache / "tool.pyc").write_bytes(b"tool")
            loose = tests / "suite.pyo"
            loose.write_bytes(b"suite")

            self.assertEqual(
                attest_tests.identity_group_sha256(
                    plugin,
                    ("maintainer/scripts",),
                ),
                baseline["tooling_sha256"],
            )
            self.assertEqual(
                attest_tests.identity_group_sha256(
                    plugin,
                    ("maintainer/tests",),
                ),
                baseline["tests_sha256"],
            )
            with self.assertRaises(attest_tests.ToolFailure) as raised:
                attest_tests.attested_input_hashes(plugin)
            self.assertEqual(
                raised.exception.issue.code,
                "test-attestation-compiled-python-residue",
            )
            self.assertEqual(Path(raised.exception.issue.path), cache)

    def test_dependency_attestation_rejects_an_incomplete_closure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_attestation_fixture(Path(temporary))
            requirements = (
                plugin / "maintainer" / "requirements-dev.txt"
            )
            requirements.write_text(
                "\n".join(
                    line
                    for line in requirements.read_text(
                        encoding="utf-8"
                    ).splitlines()
                    if not line.casefold().startswith("attrs==")
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaises(attest_tests.ToolFailure) as raised:
                attest_tests.pinned_dependencies(plugin)
            self.assertEqual(
                raised.exception.issue.code,
                "test-attestation-dependency-closure-incomplete",
            )

    def test_records_exact_suite_environment_counts_output_and_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_attestation_fixture(Path(temporary))

            def runner(
                selected_plugin: Path,
                command: list[str],
            ) -> subprocess.CompletedProcess[bytes]:
                self.assertEqual(selected_plugin, plugin)
                self.assertEqual(
                    command[1:],
                    list(attest_tests.UNITTEST_ARGUMENTS),
                )
                return fake_unittest_result(command)

            record = attest_tests.create_attestation(plugin, runner=runner)
            self.assertEqual(record["command"][1], "-B")
            schema = json.loads(
                (
                    SCHEMAS / "test-attestation.schema.json"
                ).read_text(encoding="utf-8")
            )
            errors = list(
                Draft202012Validator(
                    schema,
                    format_checker=FormatChecker(),
                ).iter_errors(record)
            )
            self.assertEqual(errors, [])
            self.assertEqual(record["result"]["status"], "passed")
            self.assertEqual(record["result"]["tests_run"], 2)
            self.assertEqual(record["result"]["skipped"], 1)
            self.assertEqual(
                record["inputs"],
                attest_tests.attested_input_hashes(plugin),
            )
            self.assertEqual(
                record["dependencies"],
                attest_tests.pinned_dependencies(plugin),
            )

    def test_unstable_inputs_never_replace_an_existing_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_attestation_fixture(Path(temporary))
            output = Path(temporary) / "attestation.json"
            output.write_text('{"previous":"record"}\n', encoding="utf-8")

            def mutating_runner(
                selected_plugin: Path,
                command: list[str],
            ) -> subprocess.CompletedProcess[bytes]:
                test_input = (
                    selected_plugin
                    / "maintainer"
                    / "tests"
                    / "tests.txt"
                )
                test_input.write_text("changed during run\n", encoding="utf-8")
                return fake_unittest_result(command)

            with self.assertRaises(attest_tests.ToolFailure) as raised:
                record = attest_tests.create_attestation(
                    plugin,
                    runner=mutating_runner,
                )
                attest_tests.atomic_write_json(output, record)
            self.assertEqual(
                raised.exception.issue.code,
                "test-attestation-input-unstable",
            )
            self.assertEqual(
                output.read_text(encoding="utf-8"),
                '{"previous":"record"}\n',
            )

    def test_release_semantics_reject_failure_drift_dependency_and_staleness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_attestation_fixture(Path(temporary))

            def failed_runner(
                _selected_plugin: Path,
                command: list[str],
            ) -> subprocess.CompletedProcess[bytes]:
                return fake_unittest_result(command, passed=False)

            failed = attest_tests.create_attestation(
                plugin,
                runner=failed_runner,
            )
            manifest = {
                "generated_at": after_timestamp(
                    failed["completed_at"],
                    seconds=1,
                )
            }
            failures = audit_package.test_attestation_failures(
                failed,
                plugin,
                SCHEMAS / "test-attestation.schema.json",
                manifest,
            )
            self.assertIn(
                "release-test-attestation-failed",
                {item["code"] for item in failures},
            )

            def passed_runner(
                _selected_plugin: Path,
                command: list[str],
            ) -> subprocess.CompletedProcess[bytes]:
                return fake_unittest_result(command)

            valid = attest_tests.create_attestation(
                plugin,
                runner=passed_runner,
            )
            manifest = {
                "generated_at": after_timestamp(
                    valid["completed_at"],
                    seconds=1,
                )
            }
            self.assertEqual(
                audit_package.test_attestation_failures(
                    valid,
                    plugin,
                    SCHEMAS / "test-attestation.schema.json",
                    manifest,
                ),
                [],
            )
            drifted = copy.deepcopy(valid)
            drifted["inputs"]["tests_sha256"] = "0" * 64
            drifted["dependencies"][0]["installed"] = "0.0.0"
            drifted["output"]["sha256"] = "f" * 64
            failures = audit_package.test_attestation_failures(
                drifted,
                plugin,
                SCHEMAS / "test-attestation.schema.json",
                {
                    "generated_at": after_timestamp(
                        valid["completed_at"],
                        hours=25,
                    )
                },
            )
            codes = {item["code"] for item in failures}
            self.assertIn("release-test-attestation-input-drift", codes)
            self.assertIn(
                "release-test-attestation-dependency-mismatch",
                codes,
            )
            self.assertIn("release-test-attestation-output-drift", codes)
            self.assertIn("release-test-attestation-stale", codes)


class RouteVerificationProofTests(unittest.TestCase):
    def test_atomic_route_record_matches_schema_and_live_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin = root / "plugin"
            canonical = plugin / "skills" / "design-dna"
            roots = [root / "codex-skills", root / "claude-skills"]
            expected = [
                roots[0] / "design-dna",
                roots[1] / "design-dna",
            ]
            write_skill(canonical)
            for route in expected:
                write_skill(route)
            output = (
                plugin
                / "maintainer"
                / "attestations"
                / "route-verification.json"
            )
            result = run_detect(canonical, roots, expected, output)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            record = json.loads(output.read_text(encoding="utf-8"))
            schema = json.loads(
                (
                    SCHEMAS / "route-verification.schema.json"
                ).read_text(encoding="utf-8")
            )
            errors = list(
                Draft202012Validator(
                    schema,
                    format_checker=FormatChecker(),
                ).iter_errors(record)
            )
            self.assertEqual(errors, [])
            compatibility = {
                "discovery_roots": [str(path) for path in roots],
                "hosts": {
                    "codex": {
                        "designed": True,
                        "discovery_route": str(expected[0]),
                    },
                    "claude_code": {
                        "designed": True,
                        "discovery_route": str(expected[1]),
                    },
                }
            }
            failures = audit_package.route_verification_failures(
                record,
                plugin,
                SCHEMAS / "route-verification.schema.json",
                {
                    "generated_at": after_timestamp(
                        record["verified_at"],
                        seconds=1,
                    )
                },
                compatibility,
            )
            self.assertEqual(failures, [])

    def test_scan_only_discovery_root_still_catches_an_unexpected_route(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin = root / "plugin"
            canonical = plugin / "skills" / "design-dna"
            installed_root = root / "installed-skills"
            scan_only_root = root / "plugin-cache"
            expected = installed_root / "design-dna"
            output = (
                plugin
                / "maintainer"
                / "attestations"
                / "route-verification.json"
            )
            write_skill(canonical)
            write_skill(expected)
            scan_only_root.mkdir()
            generated = run_detect(
                canonical,
                [installed_root, scan_only_root],
                [expected],
                output,
            )
            self.assertEqual(
                generated.returncode,
                0,
                generated.stdout + generated.stderr,
            )
            record = json.loads(output.read_text(encoding="utf-8"))
            write_skill(scan_only_root / "cached-copy")
            compatibility = {
                "discovery_roots": [
                    str(installed_root),
                    str(scan_only_root),
                ],
                "hosts": {
                    "codex": {
                        "designed": True,
                        "discovery_route": str(expected),
                    }
                },
            }
            failures = audit_package.route_verification_failures(
                record,
                plugin,
                SCHEMAS / "route-verification.schema.json",
                {
                    "generated_at": after_timestamp(
                        record["verified_at"],
                        seconds=1,
                    )
                },
                compatibility,
            )
            self.assertIn(
                "release-duplicate-route-state",
                {item["code"] for item in failures},
            )

    def test_route_proof_rejects_duplicate_deleted_drifted_and_stale_state(self) -> None:
        for mutation in ("duplicate", "deleted", "drifted", "stale"):
            with (
                self.subTest(mutation=mutation),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                plugin = root / "plugin"
                canonical = plugin / "skills" / "design-dna"
                discovery = root / "skills"
                expected = discovery / "design-dna"
                write_skill(canonical)
                write_skill(expected)
                output = (
                    plugin
                    / "maintainer"
                    / "attestations"
                    / "route-verification.json"
                )
                generated = run_detect(
                    canonical,
                    [discovery],
                    [expected],
                    output,
                )
                self.assertEqual(
                    generated.returncode,
                    0,
                    generated.stdout + generated.stderr,
                )
                record = json.loads(output.read_text(encoding="utf-8"))
                compatibility = {
                    "discovery_roots": [str(discovery)],
                    "hosts": {
                        "codex": {
                            "designed": True,
                            "discovery_route": str(expected),
                        }
                    }
                }
                manifest = {
                    "generated_at": after_timestamp(
                        record["verified_at"],
                        seconds=1,
                    )
                }
                expected_code = ""
                if mutation == "duplicate":
                    write_skill(discovery / "old-copy")
                    expected_code = "release-duplicate-route-state"
                elif mutation == "deleted":
                    shutil.rmtree(expected)
                    expected_code = "release-route-deleted"
                elif mutation == "drifted":
                    (expected / "SKILL.md").write_text(
                        (
                            expected / "SKILL.md"
                        ).read_text(encoding="utf-8")
                        + "\ndrift\n",
                        encoding="utf-8",
                    )
                    expected_code = "release-installed-route-drift"
                else:
                    manifest = {
                        "generated_at": after_timestamp(
                            record["verified_at"],
                            hours=25,
                        )
                    }
                    expected_code = "release-route-verification-stale"
                failures = audit_package.route_verification_failures(
                    record,
                    plugin,
                    SCHEMAS / "route-verification.schema.json",
                    manifest,
                    compatibility,
                )
                self.assertIn(
                    expected_code,
                    {item["code"] for item in failures},
                )

    def test_failed_route_scan_does_not_replace_prior_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical = root / "canonical"
            discovery = root / "skills"
            expected = discovery / "design-dna"
            duplicate = discovery / "duplicate"
            output = root / "route-verification.json"
            write_skill(canonical)
            write_skill(expected)
            write_skill(duplicate)
            output.write_text('{"previous":"record"}\n', encoding="utf-8")
            result = run_detect(
                canonical,
                [discovery],
                [expected],
                output,
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertEqual(
                output.read_text(encoding="utf-8"),
                '{"previous":"record"}\n',
            )


class AuditProofModeTests(unittest.TestCase):
    def test_proofs_created_before_manifest_are_accepted_after_manifest_build(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            copied = root / "plugin"
            shutil.copytree(
                PLUGIN,
                copied,
                copy_function=shutil.copyfile,
            )
            attestations = copied / "maintainer" / "attestations"
            if attestations.exists():
                remove_test_tree(attestations)
            attestations.mkdir()

            canonical = copied / "skills" / "design-dna"
            codex_root = root / "codex-skills"
            claude_root = root / "claude-skills"
            scan_only_root = root / "scan-only-cache"
            codex_route = codex_root / "design-dna"
            claude_route = claude_root / "design-dna"
            shutil.copytree(canonical, codex_route)
            shutil.copytree(canonical, claude_route)
            scan_only_root.mkdir()

            matrix_path = copied / "maintainer" / "compatibility" / "matrix.yml"
            matrix = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
            matrix["discovery_roots"] = [
                str(codex_root),
                str(claude_root),
                str(scan_only_root),
            ]
            matrix["hosts"]["codex"]["discovery_route"] = str(codex_route)
            matrix["hosts"]["claude_code"]["discovery_route"] = str(
                claude_route
            )
            matrix_path.write_text(
                yaml.safe_dump(matrix, sort_keys=False),
                encoding="utf-8",
            )

            def runner(
                _selected_plugin: Path,
                command: list[str],
            ) -> subprocess.CompletedProcess[bytes]:
                return fake_unittest_result(command)

            test_record = attest_tests.create_attestation(
                copied,
                runner=runner,
            )
            test_path = attestations / "test-attestation.json"
            attest_tests.atomic_write_json(test_path, test_record)

            route_path = attestations / "route-verification.json"
            routed = run_detect(
                canonical,
                [codex_root, claude_root, scan_only_root],
                [codex_route, claude_route],
                route_path,
            )
            self.assertEqual(
                routed.returncode,
                0,
                routed.stdout + routed.stderr,
            )
            route_record = json.loads(route_path.read_text(encoding="utf-8"))

            manifest_path = copied / "maintainer" / "release-manifest.json"
            environment = os.environ.copy()
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            environment["PYTHONUTF8"] = "1"
            built = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(SCRIPTS / "build_manifest.py"),
                    "--skill-root",
                    str(canonical),
                    "--output",
                    str(manifest_path),
                ],
                text=True,
                encoding="utf-8",
                capture_output=True,
                env=environment,
                timeout=120,
            )
            self.assertEqual(
                built.returncode,
                0,
                built.stdout + built.stderr,
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(
                audit_package.test_attestation_failures(
                    test_record,
                    copied,
                    copied
                    / "maintainer"
                    / "schemas"
                    / "test-attestation.schema.json",
                    manifest,
                ),
                [],
            )
            self.assertEqual(
                audit_package.route_verification_failures(
                    route_record,
                    copied,
                    copied
                    / "maintainer"
                    / "schemas"
                    / "route-verification.schema.json",
                    manifest,
                    matrix,
                ),
                [],
            )

            manifest["generated_at"] = after_timestamp(
                route_record["verified_at"],
                hours=25,
            )
            manifest_path.write_text(
                json.dumps(manifest, indent=2) + "\n",
                encoding="utf-8",
            )
            base_audit = [
                sys.executable,
                "-B",
                str(SCRIPTS / "audit_package.py"),
                "--plugin-root",
                str(copied),
            ]
            dev = subprocess.run(
                base_audit,
                text=True,
                encoding="utf-8",
                capture_output=True,
                env=environment,
                timeout=120,
            )
            dev_payload = json.loads(dev.stdout)
            stale_codes = {
                "release-test-attestation-stale",
                "release-route-verification-stale",
            }
            self.assertTrue(
                stale_codes
                <= {item["code"] for item in dev_payload["warnings"]}
            )
            self.assertTrue(
                stale_codes.isdisjoint(
                    {item["code"] for item in dev_payload["failures"]}
                )
            )
            release = subprocess.run(
                [*base_audit, "--release"],
                text=True,
                encoding="utf-8",
                capture_output=True,
                env=environment,
                timeout=120,
            )
            release_payload = json.loads(release.stdout)
            self.assertTrue(
                stale_codes
                <= {item["code"] for item in release_payload["failures"]}
            )

    def test_missing_proofs_warn_in_dev_and_fail_in_release(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "plugin"
            shutil.copytree(
                PLUGIN,
                copied,
                copy_function=shutil.copyfile,
            )
            attestations = copied / "maintainer" / "attestations"
            if attestations.exists():
                remove_test_tree(attestations)
            environment = os.environ.copy()
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            environment["PYTHONUTF8"] = "1"
            base = [
                sys.executable,
                "-B",
                str(SCRIPTS / "audit_package.py"),
                "--plugin-root",
                str(copied),
            ]
            dev = subprocess.run(
                base,
                text=True,
                encoding="utf-8",
                capture_output=True,
                env=environment,
                timeout=120,
            )
            dev_payload = json.loads(dev.stdout)
            missing = {
                "release-test-attestation-missing",
                "release-route-verification-missing",
            }
            self.assertTrue(
                missing
                <= {item["code"] for item in dev_payload["warnings"]}
            )
            self.assertTrue(
                missing.isdisjoint(
                    {item["code"] for item in dev_payload["failures"]}
                )
            )

            release = subprocess.run(
                [*base, "--release"],
                text=True,
                encoding="utf-8",
                capture_output=True,
                env=environment,
                timeout=120,
            )
            release_payload = json.loads(release.stdout)
            self.assertTrue(
                missing
                <= {item["code"] for item in release_payload["failures"]}
            )


if __name__ == "__main__":
    unittest.main()
