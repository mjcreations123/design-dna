from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator, FormatChecker


PLUGIN = Path(__file__).resolve().parents[2]
SCRIPTS = PLUGIN / "maintainer" / "scripts"
MODULE_PATH = SCRIPTS / "attest_codex_plugin.py"
SCHEMA_PATH = (
    PLUGIN
    / "maintainer"
    / "schemas"
    / "codex-plugin-validation-attestation.schema.json"
)

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "design_dna_attest_codex_plugin",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
ATTESTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ATTESTOR)


def fake_validator(
    base: Path,
    *,
    passes: bool = True,
    extra_stdout: bool = False,
    stderr_on_success: bool = False,
    mutate_snapshot: bool = False,
) -> Path:
    path = (
        base
        / "skills"
        / ".system"
        / "plugin-creator"
        / "scripts"
        / "validate_plugin.py"
    )
    path.parent.mkdir(parents=True)
    source = [
        '"""test-only validator fixture"""',
        "import os",
        "import sys",
        "from pathlib import Path",
        "import yaml",
        "if os.getenv('DESIGN_DNA_SECRET_SENTINEL'):",
        "    raise SystemExit('inherited secret')",
        "if yaml.safe_load('value: true') != {'value': True}:",
        "    raise SystemExit('unexpected yaml implementation')",
    ]
    if mutate_snapshot:
        source.extend([
            "target = Path(sys.argv[1]) / 'skills' / 'design-dna' / 'SKILL.md'",
            "target.write_text(target.read_text(encoding='utf-8') + '\\nmutation\\n', encoding='utf-8')",
        ])
    if extra_stdout:
        source.append("print('unexpected additional output')")
    if passes:
        source.append(
            "print(f'Plugin validation passed: {Path(sys.argv[1]).resolve()}')"
        )
        if stderr_on_success:
            source.append("print('unexpected stderr', file=sys.stderr)")
        source.append("raise SystemExit(0)")
    else:
        source.extend([
            "print('Plugin validation failed', file=sys.stderr)",
            "raise SystemExit(1)",
        ])
    path.write_text("\n".join(source) + "\n", encoding="utf-8")
    return path


def write_trust_policy(
    plugin: Path,
    validator_path: Path,
    *,
    reviewed_at: date | None = None,
    review_due: date | None = None,
    duplicate_key: bool = False,
) -> None:
    data = validator_path.read_bytes()
    reviewed = reviewed_at or date.today()
    due = review_due or (reviewed + timedelta(days=90))
    payload = {
        "schema_version": 1,
        "record_type": "design-dna-codex-validator-trust-pin",
        "logical_id": "plugin-creator/validate_plugin.py",
        "path_suffix": (
            "/skills/.system/plugin-creator/scripts/validate_plugin.py"
        ),
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "reviewed_at": reviewed.isoformat(),
        "review_due": due.isoformat(),
        "review_basis": (
            "Reviewed test-only validator bytes for isolated unit coverage."
        ),
        "trust_boundary": (
            "Test-only publisher pin; not a vendor signature or production proof."
        ),
    }
    target = (
        plugin
        / "maintainer"
        / "trust"
        / "codex-plugin-validator.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, indent=2)
    if duplicate_key:
        serialized = serialized.replace(
            '"schema_version": 1,',
            '"schema_version": 1,\n  "schema_version": 1,',
            1,
        )
    target.write_text(serialized + "\n", encoding="utf-8")


def plugin_fixture(
    base: Path,
    validator_path: Path,
    *,
    reviewed_at: date | None = None,
    review_due: date | None = None,
) -> Path:
    plugin = base / "plugin"
    manifest = plugin / ".codex-plugin" / "plugin.json"
    skill = plugin / "skills" / "design-dna" / "SKILL.md"
    manifest.parent.mkdir(parents=True)
    skill.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({
            "name": "design-dna",
            "version": "3.0.0",
            "description": "Test fixture.",
            "author": {"name": "Design DNA tests"},
            "license": "Proprietary",
            "skills": "./skills/",
            "interface": {
                "displayName": "Design DNA",
                "shortDescription": "Test fixture.",
                "longDescription": "Test fixture for validation attestation.",
                "developerName": "Design DNA tests",
                "category": "Productivity",
                "capabilities": ["Write"],
                "defaultPrompt": ["Use Design DNA."],
                "brandColor": "#164E63",
            },
        }, indent=2)
        + "\n",
        encoding="utf-8",
    )
    skill.write_text(
        "---\n"
        "name: design-dna\n"
        "description: Isolated attestation fixture.\n"
        "---\n\n"
        "# Design DNA\n",
        encoding="utf-8",
    )
    for relative in (
        "maintainer/scripts/attest_codex_plugin.py",
        "maintainer/scripts/cache_preflight.py",
        "maintainer/scripts/common.py",
        (
            "maintainer/schemas/"
            "codex-plugin-validation-attestation.schema.json"
        ),
        "maintainer/schemas/codex-validator-trust.schema.json",
    ):
        source = PLUGIN / relative
        target = plugin / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    write_trust_policy(
        plugin,
        validator_path,
        reviewed_at=reviewed_at,
        review_due=review_due,
    )
    return plugin


class CodexPluginAttestationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(
            cls.schema,
            format_checker=FormatChecker(),
        )

    def test_exact_pinned_record_is_schema_valid_private_and_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            validator_path = fake_validator(root / "external")
            plugin = plugin_fixture(root, validator_path)
            os.environ["DESIGN_DNA_SECRET_SENTINEL"] = "never-inherit"
            try:
                record = ATTESTOR.create_attestation(
                    plugin,
                    validator_path,
                )
                expected_inputs = ATTESTOR.input_records(plugin)
                expected_dependencies = ATTESTOR.dependency_records()
            finally:
                os.environ.pop("DESIGN_DNA_SECRET_SENTINEL", None)
        self.validator.validate(record)
        serialized = json.dumps(record)
        self.assertNotIn(str(plugin), serialized)
        self.assertNotIn(str(validator_path), serialized)
        self.assertNotIn("never-inherit", serialized)
        self.assertNotIn("Plugin validation passed", serialized)
        self.assertEqual(record["command"], ATTESTOR.ABSTRACT_COMMAND)
        self.assertEqual(record["inputs"], expected_inputs)
        self.assertEqual(record["dependencies"], expected_dependencies)
        self.assertEqual(
            record["output"],
            {
                "success_marker_observed": True,
                "exact_success_line_observed": True,
                "stderr_empty": True,
                "content_persisted": False,
            },
        )

    def test_unpinned_suffix_shaped_validator_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pinned = fake_validator(root / "pinned")
            unpinned = fake_validator(root / "unpinned", extra_stdout=True)
            plugin = plugin_fixture(root, pinned)
            with self.assertRaises(ATTESTOR.ToolFailure) as raised:
                ATTESTOR.create_attestation(plugin, unpinned)
        self.assertEqual(
            raised.exception.issue.code,
            "codex-plugin-validator-trust-mismatch",
        )

    def test_one_byte_validator_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            validator_path = fake_validator(root / "external")
            plugin = plugin_fixture(root, validator_path)
            validator_path.write_text(
                validator_path.read_text(encoding="utf-8") + "# drift\n",
                encoding="utf-8",
            )
            with self.assertRaises(ATTESTOR.ToolFailure) as raised:
                ATTESTOR.create_attestation(plugin, validator_path)
        self.assertEqual(
            raised.exception.issue.code,
            "codex-plugin-validator-trust-mismatch",
        )

    def test_validator_failure_cannot_create_pass_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            validator_path = fake_validator(
                root / "external",
                passes=False,
            )
            plugin = plugin_fixture(root, validator_path)
            with self.assertRaises(ATTESTOR.ToolFailure) as raised:
                ATTESTOR.create_attestation(plugin, validator_path)
        self.assertEqual(
            raised.exception.issue.code,
            "codex-plugin-validation-failed",
        )
        self.assertNotIn(
            "Plugin validation failed",
            str(raised.exception),
        )

    def test_extra_stdout_and_stderr_are_rejected_without_disclosure(
        self,
    ) -> None:
        for options in (
            {"extra_stdout": True},
            {"stderr_on_success": True},
        ):
            with self.subTest(options=options):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    validator_path = fake_validator(
                        root / "external",
                        **options,
                    )
                    plugin = plugin_fixture(root, validator_path)
                    with self.assertRaises(
                        ATTESTOR.ToolFailure
                    ) as raised:
                        ATTESTOR.create_attestation(
                            plugin,
                            validator_path,
                        )
                self.assertEqual(
                    raised.exception.issue.code,
                    "codex-plugin-validator-output-contract-failed",
                )
                self.assertNotIn("unexpected", str(raised.exception))

    def test_script_directory_yaml_shadow_is_not_imported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            validator_path = fake_validator(root / "external")
            (validator_path.parent / "yaml.py").write_text(
                "raise RuntimeError('shadow imported')\n",
                encoding="utf-8",
            )
            plugin = plugin_fixture(root, validator_path)
            record = ATTESTOR.create_attestation(plugin, validator_path)
        self.assertEqual(record["result"]["status"], "passed")

    def test_non_ascii_private_snapshot_path_uses_utf8_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            unicode_temp = root / "validation-é-Δ"
            unicode_temp.mkdir()
            validator_path = fake_validator(root / "external")
            plugin = plugin_fixture(root, validator_path)
            with mock.patch.object(
                ATTESTOR.tempfile,
                "tempdir",
                str(unicode_temp),
            ):
                record = ATTESTOR.create_attestation(
                    plugin,
                    validator_path,
                )
        self.assertEqual(record["result"]["status"], "passed")

    def test_validator_snapshot_mutation_cannot_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            validator_path = fake_validator(
                root / "external",
                mutate_snapshot=True,
            )
            plugin = plugin_fixture(root, validator_path)
            with self.assertRaises(ATTESTOR.ToolFailure) as raised:
                ATTESTOR.create_attestation(plugin, validator_path)
        self.assertEqual(
            raised.exception.issue.code,
            "codex-plugin-attestation-snapshot-drift",
        )

    def test_arbitrary_external_script_route_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            validator_path = root / "validate_plugin.py"
            validator_path.write_text("raise SystemExit(0)\n", encoding="utf-8")
            trust_policy, trust_digest = ATTESTOR.load_trust_policy(PLUGIN)
            with self.assertRaises(ATTESTOR.ToolFailure) as raised:
                ATTESTOR.validator_record(
                    validator_path,
                    trust_policy,
                    trust_digest,
                )
        self.assertEqual(
            raised.exception.issue.code,
            "codex-plugin-validator-route-invalid",
        )

    def test_trust_policy_date_boundaries_and_duplicate_keys(self) -> None:
        today = date.today()
        valid = {
            "reviewed_at": today.isoformat(),
            "review_due": (today + timedelta(days=90)).isoformat(),
        }
        ATTESTOR.ensure_trust_policy_date(
            valid,
            today,
            require_current=True,
        )
        for reviewed, due, expected in (
            (
                today + timedelta(days=1),
                today + timedelta(days=2),
                "codex-plugin-validator-trust-not-yet-valid",
            ),
            (
                today - timedelta(days=2),
                today - timedelta(days=1),
                "codex-plugin-validator-trust-overdue",
            ),
        ):
            with self.subTest(expected=expected):
                with self.assertRaises(ATTESTOR.ToolFailure) as raised:
                    ATTESTOR.ensure_trust_policy_date(
                        {
                            "reviewed_at": reviewed.isoformat(),
                            "review_due": due.isoformat(),
                        },
                        today,
                        require_current=True,
                    )
                self.assertEqual(raised.exception.issue.code, expected)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            validator_path = fake_validator(root / "external")
            plugin = plugin_fixture(root, validator_path)
            write_trust_policy(
                plugin,
                validator_path,
                reviewed_at=today,
                review_due=today + timedelta(days=181),
            )
            with self.assertRaises(ATTESTOR.ToolFailure) as raised:
                ATTESTOR.load_trust_policy(plugin)
            self.assertEqual(
                raised.exception.issue.code,
                "codex-plugin-validator-trust-date-invalid",
            )
            write_trust_policy(
                plugin,
                validator_path,
                duplicate_key=True,
            )
            with self.assertRaises(ATTESTOR.ToolFailure) as raised:
                ATTESTOR.load_trust_policy(plugin)
            self.assertEqual(
                raised.exception.issue.code,
                "codex-plugin-validator-trust-invalid",
            )

    def test_expired_pin_allows_historical_replay_not_new_evidence(
        self,
    ) -> None:
        today = date.today()
        reviewed = today - timedelta(days=30)
        due = today - timedelta(days=1)
        created_at = datetime.combine(
            reviewed + timedelta(days=1),
            datetime.min.time(),
            tzinfo=timezone.utc,
        ).isoformat().replace("+00:00", "Z")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            validator_path = fake_validator(root / "external")
            plugin = plugin_fixture(
                root,
                validator_path,
                reviewed_at=reviewed,
                review_due=due,
            )
            historical = ATTESTOR.create_attestation(
                plugin,
                validator_path,
                created_at=created_at,
                require_current_trust=False,
            )
            with self.assertRaises(ATTESTOR.ToolFailure) as raised:
                ATTESTOR.create_attestation(plugin, validator_path)
        self.assertEqual(historical["created_at"], created_at)
        self.assertEqual(
            raised.exception.issue.code,
            "codex-plugin-validator-trust-overdue",
        )

    def test_future_timestamp_is_rejected_even_for_replay(self) -> None:
        future = (
            datetime.now(timezone.utc) + timedelta(days=1)
        ).isoformat().replace("+00:00", "Z")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            validator_path = fake_validator(root / "external")
            plugin = plugin_fixture(root, validator_path)
            with self.assertRaises(ATTESTOR.ToolFailure) as raised:
                ATTESTOR.create_attestation(
                    plugin,
                    validator_path,
                    created_at=future,
                    require_current_trust=False,
                )
        self.assertEqual(
            raised.exception.issue.code,
            "codex-plugin-attestation-time-invalid",
        )


if __name__ == "__main__":
    unittest.main()
