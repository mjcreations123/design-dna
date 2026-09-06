"""Exact platform applicability for native release tests, separate from skips."""
from __future__ import annotations

import hashlib
import json
import re
import unittest


MARKER = "DESIGN_DNA_TEST_APPLICABILITY "
WINDOWS_NATIVE_TEST_IDS = tuple(sorted(
    "test_maintainer_tools.EvalRunnerV3Tests." + name for name in (
        "test_windows_assignment_failure_never_releases_driver",
        "test_windows_job_termination_fallback_is_measured_and_verified",
        "test_windows_job_termination_is_verified_without_taskkill",
        "test_windows_unverified_tree_termination_fails_with_exact_evidence",
    )
))
POLICY = {"schema_version": 1, "native_platform": "Windows", "test_ids": WINDOWS_NATIVE_TEST_IDS,
          "reason": "Exercises native Windows Job Object assignment, suspension and verified process-tree termination APIs; required on every Windows matrix entry."}
POLICY_SHA256 = hashlib.sha256(json.dumps(POLICY, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def select_suite(suite, system):
    if system not in {"Windows", "Linux", "Darwin"}:
        raise ValueError("Release test applicability requires a supported exact host platform.")
    discovered, excluded = [], []
    def select(node):
        if isinstance(node, unittest.TestSuite):
            return unittest.TestSuite(selected for child in node if (selected := select(child)) is not None)
        identity = node.id()
        discovered.append(identity)
        if identity in WINDOWS_NATIVE_TEST_IDS and system != "Windows":
            excluded.append(identity)
            return None
        return node
    return select(suite), discovered, excluded


def make_report(system, discovered, excluded, results):
    if any(discovered.count(identity) != 1 for identity in WINDOWS_NATIVE_TEST_IDS):
        raise ValueError("Every native Windows release test must occur exactly once in canonical discovery.")
    return {"schema_version": 1, "policy_sha256": POLICY_SHA256, "platform": system,
            "discovered_tests": len(discovered), "selected_tests": len(discovered) - len(excluded),
            "executed_tests": sum(result.testsRun for result in results),
            "not_applicable_test_ids": sorted(excluded),
            "executed_native_test_ids": sorted({identity for result in results for identity in result.native_executed})}


def extract_report(stdout, stderr):
    rows = [line[len(MARKER):] for line in (stdout + "\n" + stderr).splitlines() if line.startswith(MARKER)]
    if len(rows) != 1:
        raise ValueError("Release output needs exactly one final platform-applicability report.")
    value = json.loads(rows[0])
    if not isinstance(value, dict):
        raise ValueError("Platform applicability report must be an object.")
    return value


def validate_test_applicability(record, *, expected_platform=None, tests_run, passed, stdout="", stderr=""):
    fields = {"schema_version", "policy_sha256", "platform", "discovered_tests", "selected_tests", "executed_tests", "not_applicable_test_ids", "executed_native_test_ids"}
    if (not isinstance(record, dict) or set(record) != fields or record.get("schema_version") != 1
        or record.get("policy_sha256") != POLICY_SHA256 or record.get("platform") not in {"Windows", "Linux", "Darwin"}):
        return ["Test platform-applicability policy is missing, stale or malformed."]
    failures = []
    system = record["platform"]
    if expected_platform is not None and system != expected_platform:
        failures.append("Test platform applicability does not match the attested host platform.")
    expected_excluded = list(WINDOWS_NATIVE_TEST_IDS) if system != "Windows" else []
    if record.get("not_applicable_test_ids") != expected_excluded:
        failures.append("Only the four exact native Windows tests may be non-applicable outside Windows; none may be excluded on Windows.")
    count_fields = ("discovered_tests", "selected_tests", "executed_tests")
    if any(type(record.get(key)) is not int or record[key] < 1 for key in count_fields):
        failures.append("Test applicability counts must be positive integers.")
    elif (record["executed_tests"] != tests_run or record["discovered_tests"] != record["selected_tests"] + len(expected_excluded)
          or passed and record["executed_tests"] != record["selected_tests"]):
        failures.append("Test applicability discovery, selection and execution counts do not reconcile.")
    executed = record.get("executed_native_test_ids")
    if (not isinstance(executed, list) or not all(isinstance(identity, str) for identity in executed)
        or executed != sorted(set(executed)) or not set(executed).issubset(WINDOWS_NATIVE_TEST_IDS)
        or system != "Windows" and executed or passed and system == "Windows" and executed != list(WINDOWS_NATIVE_TEST_IDS)):
        failures.append("Every passing Windows run must execute all native Windows tests; other platforms cannot claim that coverage.")
    elif len(executed) > tests_run:
        failures.append("Native Windows execution count exceeds the complete executed test count.")
    observed = sorted({match.group(1) for match in re.finditer(r"(?m)^test_[^\r\n]*\(([A-Za-z0-9_.]+)\)\s+\.\.\.\s+(?!skipped\b)", stdout + "\n" + stderr)
                       if match.group(1) in WINDOWS_NATIVE_TEST_IDS})
    if executed != observed:
        failures.append("Native Windows test execution does not match the retained verbose result identities.")
    try:
        if extract_report(stdout, stderr) != record:
            failures.append("Attested applicability differs from the runner's retained report.")
    except (ValueError, TypeError) as exc:
        failures.append(str(exc))
    return failures
