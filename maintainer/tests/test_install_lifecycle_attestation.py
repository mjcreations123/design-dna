from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, ValidationError


PLUGIN = Path(__file__).resolve().parents[2]
SCRIPT_RELATIVE = Path(
    "maintainer/scripts/attest_install_lifecycle.py"
)
SCHEMA_RELATIVE = Path(
    "maintainer/schemas/install-lifecycle-attestation.schema.json"
)
COPIED_FILES = (
    SCRIPT_RELATIVE,
    Path("maintainer/scripts/manage_install.py"),
    Path("maintainer/scripts/cache_preflight.py"),
    Path("maintainer/scripts/common.py"),
    Path("maintainer/schemas/install-operation.schema.json"),
    SCHEMA_RELATIVE,
    Path("maintainer/schemas/release.schema.json"),
)


class InstallLifecycleAttestationTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(
            prefix="design-dna-lifecycle-test-"
        )
        self.fixture = Path(self.temporary.name) / "plugin"
        for relative in COPIED_FILES:
            destination = self.fixture / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(PLUGIN / relative, destination)
        runtime = self.fixture / "skills" / "design-dna"
        (runtime / "references").mkdir(parents=True)
        (runtime / "SKILL.md").write_text(
            "---\n"
            "name: design-dna\n"
            "description: Isolated lifecycle fixture.\n"
            "---\n"
            "# Design DNA\n",
            encoding="utf-8",
            newline="\n",
        )
        (runtime / "references" / "rules.md").write_text(
            "# Rules\n\nCurrent runtime.\n",
            encoding="utf-8",
            newline="\n",
        )
        (runtime / "release.json").write_text(
            json.dumps({
                "package": "design-dna",
                "version": "1.2.3",
                "state_schema_version": 1,
            }, indent=2)
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        (
            self.fixture / "maintainer" / "attestations"
        ).mkdir(parents=True)
        self.output = (
            self.fixture
            / "maintainer"
            / "attestations"
            / "install-lifecycle.json"
        )
        self.schema = json.loads(
            (self.fixture / SCHEMA_RELATIVE).read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(self.schema)
        self.validator = Draft202012Validator(
            self.schema,
            format_checker=FormatChecker(),
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def command(
        self,
        *,
        check: bool = False,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        arguments = [
            sys.executable,
            "-B",
            str(self.fixture / SCRIPT_RELATIVE),
            "--plugin-root",
            str(self.fixture),
            "--output",
            str(self.output),
        ]
        if check:
            arguments.append("--check")
        environment = dict(os.environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            arguments,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
            cwd=self.fixture,
            env=environment,
            timeout=180,
        )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            self.fail(
                f"Invalid command JSON: {exc}\n"
                f"exit={completed.returncode}\n"
                f"stdout={completed.stdout!r}\n"
                f"stderr={completed.stderr!r}"
            )
        self.assertEqual("", completed.stderr)
        return completed, payload

    def create(self) -> dict[str, object]:
        completed, result = self.command()
        self.assertEqual(0, completed.returncode, result)
        self.assertTrue(result["ok"])
        record = json.loads(self.output.read_text(encoding="utf-8"))
        self.validator.validate(record)
        return record

    def test_fresh_dual_host_lifecycle_is_hash_bound_and_replayable(
        self,
    ) -> None:
        record = self.create()
        self.assertEqual(
            [stage["name"] for stage in record["stages"]],
            [
                "install-prior",
                "update-current",
                "rollback-prior",
                "uninstall-prior",
            ],
        )
        self.assertEqual(
            [
                stage["operation"]["changes"][0]["action"]
                for stage in record["stages"]
            ],
            ["installed", "updated", "rolled-back", "uninstalled"],
        )
        self.assertTrue(record["final_state"]["routes_absent"])
        self.assertEqual(
            ["codex", "claude"],
            [
                host["host"]
                for host in record["final_state"]["hosts"]
            ],
        )
        self.assertTrue(
            all(
                host["backup_record_count"] == 3
                and host["available_count"] == 2
                and host["restored_count"] == 1
                and not host["route_exists"]
                for host in record["final_state"]["hosts"]
            )
        )
        serialized = json.dumps(record)
        self.assertNotIn(str(self.fixture), serialized)
        for stage in record["stages"]:
            expected = hashlib.sha256(
                json.dumps(
                    stage["operation"],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            self.assertEqual(expected, stage["semantic_record_sha256"])

        checked, result = self.command(check=True)
        self.assertEqual(0, checked.returncode, result)
        self.assertTrue(result["ok"])
        self.assertTrue(result["check"])

    def test_tampered_record_is_rejected_even_when_live_replay_passes(
        self,
    ) -> None:
        record = self.create()
        record["stages"][1]["operation"]["changes"][0]["action"] = (
            "installed"
        )
        self.output.write_text(
            json.dumps(record, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        completed, result = self.command(check=True)
        self.assertEqual(2, completed.returncode)
        self.assertFalse(result["ok"])
        self.assertEqual(
            "install-lifecycle-attestation-invalid",
            result["failures"][0]["code"],
        )

    def test_runtime_change_invalidates_recorded_attestation(self) -> None:
        self.create()
        runtime_rule = (
            self.fixture
            / "skills"
            / "design-dna"
            / "references"
            / "rules.md"
        )
        runtime_rule.write_text(
            "# Rules\n\nRuntime changed after attestation.\n",
            encoding="utf-8",
            newline="\n",
        )
        completed, result = self.command(check=True)
        self.assertEqual(2, completed.returncode)
        self.assertFalse(result["ok"])
        self.assertEqual(
            "install-lifecycle-attestation-drift",
            result["failures"][0]["code"],
        )

    def test_schema_refuses_extra_fields_and_false_outcomes(self) -> None:
        record = self.create()
        mutated = json.loads(json.dumps(record))
        mutated["unexpected"] = True
        with self.assertRaises(ValidationError):
            self.validator.validate(mutated)
        mutated = json.loads(json.dumps(record))
        mutated["outcome"]["passed"] = False
        with self.assertRaises(ValidationError):
            self.validator.validate(mutated)
        mutated = json.loads(json.dumps(record))
        mutated["stages"][3]["post_state"][0]["exists"] = True
        with self.assertRaises(ValidationError):
            self.validator.validate(mutated)


if __name__ == "__main__":
    unittest.main()
