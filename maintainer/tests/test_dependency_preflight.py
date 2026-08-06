from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import re
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker


PLUGIN = Path(__file__).resolve().parents[2]
REQUIREMENTS = PLUGIN / "maintainer" / "requirements-dev.txt"
CI_WORKFLOW = PLUGIN / ".github" / "workflows" / "ci.yml"
IMPORT_NAMES = {
    "attrs": "attrs",
    "jsonschema": "jsonschema",
    "jsonschema-specifications": "jsonschema_specifications",
    "packaging": "packaging",
    "pyyaml": "yaml",
    "referencing": "referencing",
    "rpds-py": "rpds",
    "typing-extensions": "typing_extensions",
}


def normalized_distribution_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).casefold()


class ReleaseDependencyPreflightTests(unittest.TestCase):
    def test_pinned_maintainer_dependencies_are_installed(self) -> None:
        pins: dict[str, tuple[str, str]] = {}
        malformed: list[str] = []
        for raw_line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
            line = raw_line.partition("#")[0].strip()
            if not line:
                continue
            match = re.fullmatch(
                r"([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9._+-]*)",
                line,
            )
            if not match:
                malformed.append(raw_line)
                continue
            distribution, version = match.groups()
            key = normalized_distribution_name(distribution)
            if key in pins:
                malformed.append(f"duplicate requirement: {distribution}")
                continue
            pins[key] = (distribution, version)

        issues = [
            f"requirements-dev.txt entry is not an exact pin: {line!r}"
            for line in malformed
        ]
        if not pins:
            issues.append("requirements-dev.txt contains no pinned dependencies")

        for key, (distribution, expected_version) in sorted(pins.items()):
            module = IMPORT_NAMES.get(key)
            if module is None:
                issues.append(
                    f"preflight has no import-name mapping for {distribution}"
                )
                continue
            try:
                actual_version = importlib.metadata.version(distribution)
            except importlib.metadata.PackageNotFoundError:
                issues.append(
                    f"{distribution}=={expected_version} is not installed"
                )
                continue
            if actual_version != expected_version:
                issues.append(
                    f"{distribution} version is {actual_version}; "
                    f"expected {expected_version}"
                )
            if importlib.util.find_spec(module) is None:
                issues.append(
                    f"{distribution} is installed but import {module!r} "
                    "is unavailable"
                )

        self.assertFalse(
            issues,
            "Release-critical tests require every exact dependency pin from "
            "maintainer/requirements-dev.txt. Install them with "
            "`python -m pip install --require-hashes -r "
            "maintainer/requirements-dev.lock`.\n- "
            + "\n- ".join(issues),
        )

    def test_release_format_checks_do_not_depend_on_optional_extras(self) -> None:
        import sys

        scripts = str(PLUGIN / "maintainer" / "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        from common import strict_format_checker

        checker = strict_format_checker()
        self.assertTrue(checker.conforms("2026-07-28", "date"))
        self.assertFalse(checker.conforms("2026-02-29", "date"))
        self.assertTrue(
            checker.conforms("2026-07-28T12:34:56Z", "date-time")
        )
        self.assertFalse(checker.conforms("not-a-date", "date-time"))
        self.assertTrue(
            checker.conforms("https://example.com/evidence", "uri")
        )
        self.assertFalse(checker.conforms("not a uri", "uri"))

    def test_zero_skip_matrix_provisions_the_browser_before_attestation(self) -> None:
        workflow = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
        job = workflow["jobs"]["test"]
        environment = job["env"]
        self.assertEqual(
            "${{ github.workspace }}/maintainer/node_modules",
            environment["DESIGN_DNA_PLAYWRIGHT_MODULE_DIR"],
        )
        self.assertEqual(
            "${{ runner.temp }}/ms-playwright",
            environment["PLAYWRIGHT_BROWSERS_PATH"],
        )
        steps = job["steps"]

        def index_named(name: str) -> int:
            return next(
                index
                for index, step in enumerate(steps)
                if step.get("name") == name
            )

        setup_node = next(
            step for step in steps if str(step.get("uses", "")).startswith("actions/setup-node@")
        )
        self.assertRegex(
            setup_node["uses"],
            r"^actions/setup-node@[0-9a-f]{40}$",
        )
        self.assertEqual("22", setup_node["with"]["node-version"])
        dependency_step = steps[index_named("Install pinned browser-review dependency")]
        self.assertEqual("maintainer", dependency_step["working-directory"])
        self.assertIn("npm ci", dependency_step["run"])
        linux_browser = index_named("Install Chromium and Linux browser dependencies")
        other_browser = index_named("Install Chromium")
        attestation = index_named(
            "Run and attest unit and adversarial tests with zero unwaived skips"
        )
        self.assertLess(index_named("Install pinned browser-review dependency"), linux_browser)
        self.assertLess(index_named("Install pinned browser-review dependency"), other_browser)
        self.assertLess(linux_browser, attestation)
        self.assertLess(other_browser, attestation)
        package_audit = steps[index_named("Run development audit")]
        retained = steps[
            index_named("Retain matrix test and package-audit evidence")
        ]
        self.assertEqual("bash", package_audit["shell"])
        self.assertIn(
            "design-dna-package-audit.json",
            package_audit["run"],
        )
        self.assertIn(
            "design-dna-test-attestation.json",
            retained["with"]["path"],
        )
        self.assertIn(
            "design-dna-package-audit.json",
            retained["with"]["path"],
        )
        self.assertLess(
            index_named("Run development audit"),
            index_named(
                "Retain matrix test and package-audit evidence"
            ),
        )

    def test_host_discovery_pass_requires_host_native_result_evidence(self) -> None:
        matrix = yaml.safe_load(
            (
                PLUGIN / "maintainer" / "compatibility" / "matrix.yml"
            ).read_text(encoding="utf-8")
        )
        schema = json.loads(
            (
                PLUGIN
                / "maintainer"
                / "schemas"
                / "compatibility.schema.json"
            ).read_text(encoding="utf-8")
        )
        host_record = next(
            record
            for record in matrix["environments"]
            if record["scope"] == "host_runtime"
            and record["host"] == "codex"
        )
        host_record["checks"]["host_discovery"] = "passed"
        host_record["evidence"] = [
            "maintainer/attestations/route-verification.json"
        ]
        errors = list(
            Draft202012Validator(
                schema,
                format_checker=FormatChecker(),
            ).iter_errors(matrix)
        )
        self.assertTrue(
            any(
                "does not contain items matching" in error.message
                for error in errors
            ),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
