from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator


PLUGIN = Path(__file__).resolve().parents[2]
SCRIPTS = PLUGIN / "maintainer" / "scripts"
SCHEMAS = PLUGIN / "maintainer" / "schemas"


def run_script(
    name: str,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPTS / name), *arguments],
        cwd=PLUGIN,
        text=True,
        encoding="utf-8",
        capture_output=True,
        env=environment,
        timeout=120,
    )


def make_sbom_fixture(root: Path) -> Path:
    plugin = root / "plugin"
    skill = plugin / "skills" / "design-dna"
    skill.mkdir(parents=True)
    shutil.copy2(PLUGIN / "skills" / "design-dna" / "release.json", skill)
    (skill / "SKILL.md").write_text(
        "---\nname: design-dna\n"
        "description: Product-tool fixture.\n---\n",
        encoding="utf-8",
    )
    for directory in (".codex-plugin", ".claude-plugin"):
        source = PLUGIN / directory / "plugin.json"
        destination = plugin / directory
        destination.mkdir()
        shutil.copy2(source, destination / "plugin.json")
    maintainer = plugin / "maintainer"
    (maintainer / "schemas").mkdir(parents=True)
    shutil.copy2(
        SCHEMAS / "sbom.schema.json",
        maintainer / "schemas" / "sbom.schema.json",
    )
    shutil.copy2(
        PLUGIN / "maintainer" / "requirements-dev.txt",
        maintainer / "requirements-dev.txt",
    )
    shutil.copy2(
        PLUGIN / "maintainer" / "requirements-dev.lock",
        maintainer / "requirements-dev.lock",
    )
    shutil.copy2(PLUGIN / "LICENSE", plugin / "LICENSE")
    return plugin


class SbomTests(unittest.TestCase):
    def test_generates_schema_valid_inventory_and_detects_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_sbom_fixture(Path(temporary))
            output = plugin / "maintainer" / "sbom.spdx.json"
            generated = run_script(
                "build_sbom.py",
                "--plugin-root",
                str(plugin),
                "--output",
                str(output),
                "--created-at",
                "2026-07-28T16:00:00Z",
            )
            self.assertEqual(
                generated.returncode,
                0,
                generated.stdout + generated.stderr,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            schema = json.loads(
                (SCHEMAS / "sbom.schema.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                list(Draft202012Validator(schema).iter_errors(payload)),
                [],
            )
            self.assertEqual(payload["spdxVersion"], "SPDX-2.3")
            self.assertGreaterEqual(len(payload["packages"]), 2)
            python_packages = [
                package
                for package in payload["packages"]
                if package["SPDXID"].startswith("SPDXRef-Package-pypi-")
            ]
            self.assertTrue(python_packages)
            self.assertTrue(
                all(package.get("checksums") for package in python_packages)
            )
            self.assertEqual(
                len(payload["packages"]) - 1,
                len(payload["relationships"]),
            )
            checked = run_script(
                "build_sbom.py",
                "--plugin-root",
                str(plugin),
                "--output",
                str(output),
                "--check",
            )
            self.assertEqual(
                checked.returncode,
                0,
                checked.stdout + checked.stderr,
            )

            requirements = plugin / "maintainer" / "requirements-dev.txt"
            requirements.write_text(
                requirements.read_text(encoding="utf-8")
                + "example-package==1.2.3\n",
                encoding="utf-8",
            )
            lock = plugin / "maintainer" / "requirements-dev.lock"
            lock.write_text(
                lock.read_text(encoding="utf-8")
                + "example-package==1.2.3 "
                + "--hash=sha256:"
                + ("a" * 64)
                + "\n",
                encoding="utf-8",
            )
            drifted = run_script(
                "build_sbom.py",
                "--plugin-root",
                str(plugin),
                "--output",
                str(output),
                "--check",
            )
            self.assertEqual(drifted.returncode, 2)
            self.assertEqual(
                json.loads(drifted.stdout)["failures"][0]["code"],
                "sbom-drift",
            )

    def test_inventories_locked_npm_packages_and_rejects_loose_pins(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = make_sbom_fixture(Path(temporary))
            lock = {
                "name": "design-dna-maintainer",
                "lockfileVersion": 3,
                "packages": {
                    "": {"name": "design-dna-maintainer"},
                    "node_modules/playwright": {"version": "1.61.1"},
                    "node_modules/playwright/node_modules/helper": {
                        "version": "2.0.0"
                    },
                },
            }
            (plugin / "maintainer" / "package-lock.json").write_text(
                json.dumps(lock, indent=2) + "\n",
                encoding="utf-8",
            )
            output = plugin / "maintainer" / "sbom.spdx.json"
            result = run_script(
                "build_sbom.py",
                "--plugin-root",
                str(plugin),
                "--output",
                str(output),
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            packages = json.loads(output.read_text(encoding="utf-8"))[
                "packages"
            ]
            self.assertIn("playwright", {item["name"] for item in packages})
            self.assertIn("helper", {item["name"] for item in packages})

            (plugin / "maintainer" / "requirements-dev.txt").write_text(
                "unpinned>=1\n",
                encoding="utf-8",
            )
            rejected = run_script(
                "build_sbom.py",
                "--plugin-root",
                str(plugin),
                "--output",
                str(output),
            )
            self.assertEqual(rejected.returncode, 2)
            self.assertEqual(
                json.loads(rejected.stdout)["failures"][0]["code"],
                "sbom-requirement-not-pinned",
            )

    def test_refuses_output_outside_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin = make_sbom_fixture(root)
            rejected = run_script(
                "build_sbom.py",
                "--plugin-root",
                str(plugin),
                "--output",
                str(root / "outside.spdx.json"),
            )
            self.assertEqual(rejected.returncode, 2)
            self.assertEqual(
                json.loads(rejected.stdout)["failures"][0]["code"],
                "sbom-output-outside-package",
            )


class ReleaseArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPTS))
        cls.module = importlib.import_module("package_release")
        sys.path.pop(0)

    def make_repository(self, root: Path) -> Path:
        repository = root / "repository"
        repository.mkdir()

        def git(*arguments: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                ["git", "-C", str(repository), *arguments],
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=30,
            )

        self.assertEqual(git("init").returncode, 0)
        self.assertEqual(
            git("config", "user.name", "Design DNA Test").returncode,
            0,
        )
        self.assertEqual(
            git("config", "user.email", "test@example.invalid").returncode,
            0,
        )
        (repository / "file.txt").write_text("stable\n", encoding="utf-8")
        self.assertEqual(git("add", "file.txt").returncode, 0)
        committed = git("commit", "-m", "Stable fixture")
        self.assertEqual(
            committed.returncode,
            0,
            committed.stdout + committed.stderr,
        )
        tagged = git("tag", "-a", "v1.2.3", "-m", "v1.2.3")
        self.assertEqual(tagged.returncode, 0, tagged.stdout + tagged.stderr)
        return repository

    def test_git_archive_is_repeatable_and_annotated_tag_is_verified(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = self.make_repository(root)
            commit = self.module.resolved_commit(repository, "v1.2.3")
            self.module.validate_release_ref(
                repository,
                "v1.2.3",
                "1.2.3",
                commit,
            )
            first = root / "first.zip"
            second = root / "second.zip"
            self.module.git_archive(
                repository,
                "v1.2.3",
                first,
                "design-dna-1.2.3",
            )
            self.module.git_archive(
                repository,
                "v1.2.3",
                second,
                "design-dna-1.2.3",
            )
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(
                    archive.namelist(),
                    [
                        "design-dna-1.2.3/",
                        "design-dna-1.2.3/file.txt",
                    ],
                )

            (repository / "file.txt").write_text("dirty\n", encoding="utf-8")
            with self.assertRaises(self.module.ToolFailure) as raised:
                self.module.ensure_clean_worktree(repository)
            self.assertEqual(
                raised.exception.issue.code,
                "release-package-worktree-dirty",
            )

    def test_unsafe_or_lightweight_release_ref_is_rejected(self) -> None:
        with self.assertRaises(self.module.ToolFailure):
            self.module.validate_ref("--output=elsewhere")
        with self.assertRaises(self.module.ToolFailure):
            self.module.validate_ref("tag/../escape")
        with tempfile.TemporaryDirectory() as temporary:
            repository = self.make_repository(Path(temporary))
            subprocess.run(
                ["git", "-C", str(repository), "tag", "v1.2.4"],
                check=True,
                capture_output=True,
                text=True,
            )
            commit = self.module.resolved_commit(repository, "v1.2.4")
            with self.assertRaises(self.module.ToolFailure) as raised:
                self.module.validate_release_ref(
                    repository,
                    "v1.2.4",
                    "1.2.4",
                    commit,
                )
            self.assertEqual(
                raised.exception.issue.code,
                "release-package-tag-not-annotated",
            )

    def test_release_tree_rejects_symlink_git_modes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = self.make_repository(Path(temporary))
            blob = subprocess.run(
                ["git", "-C", str(repository), "hash-object", "-w", "--stdin"],
                input="file.txt",
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=True,
            ).stdout.strip()
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repository),
                    "update-index",
                    "--add",
                    "--cacheinfo",
                    f"120000,{blob},linked-file",
                ],
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(repository), "commit", "-m", "Unsafe link"],
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=True,
            )
            with self.assertRaises(self.module.ToolFailure) as raised:
                self.module.git_tree_records(repository, "HEAD")
            self.assertEqual(
                raised.exception.issue.code,
                "release-package-git-mode-unsafe",
            )

    def test_archive_parity_rejects_an_untracked_extra_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = self.make_repository(root)
            archive_path = root / "release.zip"
            self.module.git_archive(
                repository,
                "v1.2.3",
                archive_path,
                "design-dna-1.2.3",
            )
            with zipfile.ZipFile(
                archive_path,
                mode="a",
                compression=zipfile.ZIP_DEFLATED,
            ) as archive:
                archive.writestr(
                    "design-dna-1.2.3/untracked.txt",
                    "not in git\n",
                )
            with self.assertRaises(self.module.ToolFailure) as raised:
                self.module.validate_archive_against_git(
                    repository,
                    "v1.2.3",
                    archive_path,
                    "design-dna-1.2.3",
                )
            self.assertEqual(
                raised.exception.issue.code,
                "release-package-archive-extra",
            )

    def test_packaged_ref_must_match_clean_head_even_outside_release_mode(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = self.make_repository(Path(temporary))
            old_commit = self.module.resolved_commit(repository, "HEAD")
            (repository / "second.txt").write_text("new head\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(repository), "add", "second.txt"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(repository), "commit", "-m", "Second"],
                check=True,
                capture_output=True,
                text=True,
            )
            with self.assertRaises(self.module.ToolFailure) as raised:
                self.module.validate_ref_matches_head(
                    repository,
                    old_commit,
                    old_commit,
                )
            self.assertEqual(
                raised.exception.issue.code,
                "release-package-ref-not-head",
            )

    def test_release_validator_must_be_absolute_existing_and_external(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin = root / "plugin"
            plugin.mkdir()
            external = root / "external" / "validate_plugin.py"
            external.parent.mkdir()
            external.write_text("# reviewed fixture\n", encoding="utf-8")

            self.assertEqual(
                self.module.validated_codex_validator(
                    plugin,
                    external,
                    release=True,
                ),
                external,
            )
            self.assertIsNone(
                self.module.validated_codex_validator(
                    plugin,
                    None,
                    release=False,
                )
            )

            cases = (
                (
                    None,
                    "release-package-codex-validator-required",
                ),
                (
                    Path("relative-validator.py"),
                    "release-package-codex-validator-path-not-absolute",
                ),
                (
                    root / "missing" / "validate_plugin.py",
                    "release-package-codex-validator-unavailable",
                ),
            )
            for selected, code in cases:
                with self.subTest(code=code):
                    with self.assertRaises(self.module.ToolFailure) as raised:
                        self.module.validated_codex_validator(
                            plugin,
                            selected,
                            release=True,
                        )
                    self.assertEqual(raised.exception.issue.code, code)

            internal = plugin / "validate_plugin.py"
            internal.write_text("# package-owned fixture\n", encoding="utf-8")
            with self.assertRaises(self.module.ToolFailure) as raised:
                self.module.validated_codex_validator(
                    plugin,
                    internal,
                    release=True,
                )
            self.assertEqual(
                raised.exception.issue.code,
                "release-package-codex-validator-not-external",
            )

    def test_strict_release_preflight_forwards_home_and_validator(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin = root / "plugin"
            home = root / "home"
            validator = root / "external" / "validate_plugin.py"
            previous = root / "v1.2.2.manifest-identity.json"
            home.mkdir()
            validator.parent.mkdir()
            validator.write_text("# reviewed fixture\n", encoding="utf-8")
            commands: list[list[str]] = []

            def passing_child(
                command: list[str],
                **_kwargs: object,
            ) -> subprocess.CompletedProcess[str]:
                commands.append(command)
                return subprocess.CompletedProcess(command, 0, "", "")

            with mock.patch.object(
                self.module.subprocess,
                "run",
                side_effect=passing_child,
            ):
                self.module.run_validation(
                    plugin,
                    release=True,
                    previous_manifest=previous,
                    home=home,
                    codex_validator=validator,
                )

            self.assertEqual(len(commands), 3)
            audit = commands[2]
            self.assertEqual(
                audit,
                [
                    sys.executable,
                    "-B",
                    str(plugin / "maintainer" / "scripts" / "audit_package.py"),
                    "--plugin-root",
                    str(plugin),
                    "--home",
                    str(home),
                    "--codex-validator",
                    str(validator),
                    "--release",
                ],
            )

            with self.assertRaises(self.module.ToolFailure) as raised:
                self.module.run_validation(
                    plugin,
                    release=True,
                    previous_manifest=previous,
                    home=home,
                    codex_validator=None,
                )
            self.assertEqual(
                raised.exception.issue.code,
                "release-package-codex-validator-required",
            )


if __name__ == "__main__":
    unittest.main()
