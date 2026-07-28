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


PLUGIN = Path(__file__).resolve().parents[2]
SCRIPT = PLUGIN / "maintainer" / "scripts" / "validate_evidence.py"
SCHEMA = (
    PLUGIN
    / "maintainer"
    / "schemas"
    / "evidence-frontmatter.schema.json"
)


def make_directory_link(link: Path, target: Path) -> bool:
    try:
        os.symlink(target, link, target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        if os.name != "nt":
            return False
        created = subprocess.run(
            ["cmd.exe", "/c", "mklink", "/J", str(link), str(target)],
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=30,
        )
        return created.returncode == 0


def copy_validation_fixture(destination: Path) -> None:
    shutil.copytree(
        PLUGIN / "maintainer" / "evidence",
        destination / "maintainer" / "evidence",
    )
    policy_target = (
        destination
        / "skills"
        / "design-dna"
        / "policy"
        / "owner-defaults.yml"
    )
    policy_target.parent.mkdir(parents=True)
    shutil.copy2(
        PLUGIN
        / "skills"
        / "design-dna"
        / "policy"
        / "owner-defaults.yml",
        policy_target,
    )


def run_validation(
    plugin: Path,
    *,
    schema: Path = SCHEMA,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--plugin-root",
            str(plugin),
            "--schema",
            str(schema),
        ],
        text=True,
        encoding="utf-8",
        capture_output=True,
        env=environment,
        timeout=120,
    )


class EvidenceSnapshotTests(unittest.TestCase):
    def assert_reparse_refused(
        self,
        result: subprocess.CompletedProcess[str],
    ) -> None:
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(
            payload["failures"][0]["code"],
            "reparse-point-refused",
        )

    def test_current_registry_and_hash_bound_snapshots_validate(self) -> None:
        result = run_validation(PLUGIN)
        self.assertEqual(
            result.returncode,
            0,
            "Evidence validation requires the pinned maintainer dependencies and "
            f"a clean registry.\n{result.stdout}\n{result.stderr}",
        )

    def test_modified_fast_moving_source_snapshot_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "plugin"
            copy_validation_fixture(copied)
            snapshot = (
                copied
                / "maintainer"
                / "evidence"
                / "snapshots"
                / "EVD-007.json"
            )
            snapshot.write_text(
                snapshot.read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )
            result = run_validation(copied)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(
                any(
                    item["code"] == "source-snapshot-hash-mismatch"
                    for item in payload["failures"]
                )
            )

    def test_reparse_plugin_and_schema_inputs_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            real_plugin = root / "real-plugin"
            copy_validation_fixture(real_plugin)
            plugin_link = root / "plugin-link"
            if not make_directory_link(plugin_link, real_plugin):
                self.skipTest("directory symlink/junction unavailable")
            try:
                self.assert_reparse_refused(run_validation(plugin_link))
            finally:
                os.rmdir(plugin_link)

            schema_source = root / "real-schema"
            schema_source.mkdir()
            shutil.copy2(SCHEMA, schema_source / SCHEMA.name)
            schema_link = root / "schema-link"
            if not make_directory_link(schema_link, schema_source):
                self.skipTest("directory symlink/junction unavailable")
            try:
                self.assert_reparse_refused(
                    run_validation(
                        real_plugin,
                        schema=schema_link / SCHEMA.name,
                    )
                )
            finally:
                os.rmdir(schema_link)

    def test_reparse_evidence_cards_and_snapshots_are_rejected(self) -> None:
        for directory_name in ("cards", "snapshots"):
            with (
                self.subTest(directory=directory_name),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                copied = root / "plugin"
                copy_validation_fixture(copied)
                evidence_root = copied / "maintainer" / "evidence"
                linked_directory = evidence_root / directory_name
                real_directory = root / f"real-{directory_name}"
                linked_directory.rename(real_directory)
                if not make_directory_link(linked_directory, real_directory):
                    self.skipTest("directory symlink/junction unavailable")
                try:
                    self.assert_reparse_refused(run_validation(copied))
                finally:
                    os.rmdir(linked_directory)

    def test_reparse_internal_evaluation_artifact_parent_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            copied = root / "plugin"
            copy_validation_fixture(copied)
            real_artifacts = root / "real-artifacts"
            real_artifacts.mkdir()
            artifact = real_artifacts / "evaluation.json"
            artifact.write_text('{"result":"bound"}\n', encoding="utf-8")
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            artifact_link = copied / "artifacts"
            if not make_directory_link(artifact_link, real_artifacts):
                self.skipTest("directory symlink/junction unavailable")
            card = (
                copied
                / "maintainer"
                / "evidence"
                / "cards"
                / "EVD-001.md"
            )
            card_text = card.read_text(encoding="utf-8")
            card_text = card_text.replace(
                'source_type: "research"\n',
                'source_type: "internal_evaluation"\n'
                "evaluation_hosts:\n"
                '  - "codex"\n'
                '  - "claude_code"\n'
                "evaluation_projects:\n"
                '  - "project-a"\n'
                '  - "project-b"\n'
                'artifact_path: "artifacts/evaluation.json"\n'
                f'artifact_sha256: "{digest}"\n',
                1,
            )
            self.assertIn(
                'source_type: "internal_evaluation"',
                card_text,
            )
            card.write_text(card_text, encoding="utf-8")
            try:
                self.assert_reparse_refused(run_validation(copied))
            finally:
                os.rmdir(artifact_link)


if __name__ == "__main__":
    unittest.main()
