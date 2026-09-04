from __future__ import annotations

import copy
import hashlib
import json
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


MAINTAINER = Path(__file__).resolve().parents[1]
SCRIPT = MAINTAINER / "scripts" / "manage_install.py"
SCHEMA = MAINTAINER / "schemas" / "install-operation.schema.json"
RUNTIME_SCRIPTS = MAINTAINER.parent / "skills" / "design-dna" / "scripts"


class ManageInstallTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="design-dna-install-test-")
        self.root = Path(self.temporary.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.source = self.root / "canonical" / "design-dna"
        self.source.mkdir(parents=True)
        self.write_skill(self.source, marker="canonical-v1")
        self.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def write_skill(path: Path, *, marker: str, declared_name: str = "design-dna") -> None:
        path.mkdir(parents=True, exist_ok=True)
        (path / "SKILL.md").write_text(
            "---\n"
            f"name: {declared_name}\n"
            "description: Test-only Design DNA fixture.\n"
            "---\n"
            "# Design DNA\n"
            f"\n{marker}\n",
            encoding="utf-8",
        )
        references = path / "references"
        references.mkdir(exist_ok=True)
        (references / "rules.md").write_text(f"# Rules\n\n{marker}\n", encoding="utf-8")

    def command(
        self,
        operation: str,
        *,
        host: str = "codex",
        extra: list[str] | None = None,
        environment_overrides: dict[str, str] | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        command = [
            sys.executable,
            "-B",
            str(SCRIPT),
            operation,
            "--host",
            host,
            "--home",
            str(self.home),
            "--source",
            str(self.source),
        ]
        if extra:
            command.extend(extra)
        environment = dict(os.environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        if environment_overrides:
            environment.update(environment_overrides)
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            self.fail(
                f"Manager did not emit one JSON value.\n"
                f"exit={completed.returncode}\nstdout={completed.stdout!r}\nstderr={completed.stderr!r}\n{exc}"
            )
        self.assertEqual("", completed.stderr)
        self.assertEqual(1, len(completed.stdout.splitlines()))
        return completed, payload

    def hard_exit(
        self,
        operation: str,
        point: str,
        *,
        host: str = "codex",
        extra: list[str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            "-B",
            str(SCRIPT),
            operation,
            "--host",
            host,
            "--home",
            str(self.home),
            "--source",
            str(self.source),
            "--simulate-hard-exit-at",
            point,
        ]
        if extra:
            command.extend(extra)
        environment = dict(os.environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )
        self.assertEqual(86, completed.returncode)
        self.assertEqual("", completed.stdout)
        self.assertEqual("", completed.stderr)
        return completed

    def assert_no_transaction_residue(self, backup_root: Path) -> None:
        if not backup_root.exists():
            return
        residue = [
            entry.name
            for entry in backup_root.iterdir()
            if entry.name.startswith((".pending-", ".stage-"))
        ]
        self.assertEqual([], residue)

    def assert_valid_schema(self, payload: object) -> None:
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is not available")
        jsonschema.Draft202012Validator(self.schema).validate(payload)

    @property
    def codex_target(self) -> Path:
        return self.home / ".agents" / "skills" / "design-dna"

    @property
    def claude_target(self) -> Path:
        return self.home / ".claude" / "skills" / "design-dna"

    @property
    def codex_backups(self) -> Path:
        return self.home / ".design-dna" / "backups" / "codex"

    def install_codex(self) -> dict[str, object]:
        completed, payload = self.command("install")
        self.assertEqual(0, completed.returncode, payload)
        self.assertTrue(payload["ok"])
        return payload

    @staticmethod
    def write_browser_runtime(path: Path) -> None:
        scripts = path / "scripts"
        scripts.mkdir(exist_ok=True)
        for name in ("playwright_resolver.mjs", "browser_preflight.mjs"):
            shutil.copy2(RUNTIME_SCRIPTS / name, scripts / name)

    @staticmethod
    def write_fake_playwright(project: Path) -> None:
        package = project / "node_modules" / "playwright"
        package.mkdir(parents=True)
        (package / "package.json").write_text(
            '{"name":"playwright","version":"fixture-1","main":"index.js"}\n',
            encoding="utf-8",
        )
        (package / "index.js").write_text(
            "module.exports={chromium:{executablePath:()=>'',launch:async()=>({"
            "version:()=> 'fixture-browser',newPage:async()=>({goto:async()=>{},close:async()=>{}}),close:async()=>{}})}};\n",
            encoding="utf-8",
        )

    @unittest.skipIf(shutil.which("node") is None, "node is required")
    def test_doctor_browser_project_checks_each_current_installed_runtime(self) -> None:
        self.write_browser_runtime(self.source)
        self.install_codex()
        project = self.root / "browser-project"
        project.mkdir()
        self.write_fake_playwright(project)

        completed, payload = self.command(
            "doctor",
            extra=["--browser-project", str(project)],
            environment_overrides={
                "DESIGN_DNA_BROWSER_EXECUTABLE": str(Path(sys.executable).resolve()),
                "NODE_PATH": "",
            },
        )

        self.assertEqual(0, completed.returncode, payload)
        preflight = payload["hosts"][0]["browser_preflight"]
        self.assertEqual("passed", preflight["status"])
        self.assertEqual("browser-preflight-passed", preflight["code"])
        self.assertTrue(preflight["launch_checked"])
        self.assertEqual("project-local-node-modules", preflight["details"]["playwright_source"])
        self.assertEqual("fixture-browser", preflight["details"]["browser_launch_version"])
        self.assert_valid_schema(payload)

    @unittest.skipIf(shutil.which("node") is None, "node is required")
    def test_doctor_browser_project_reports_missing_module_without_fallback(self) -> None:
        self.write_browser_runtime(self.source)
        self.install_codex()
        project = self.root / "browser-project"
        project.mkdir()

        completed, payload = self.command(
            "doctor",
            extra=["--browser-project", str(project)],
            environment_overrides={
                "DESIGN_DNA_BROWSER_EXECUTABLE": str(Path(sys.executable).resolve()),
                "NODE_PATH": "",
            },
        )

        self.assertEqual(1, completed.returncode, payload)
        preflight = payload["hosts"][0]["browser_preflight"]
        self.assertEqual("blocked", preflight["status"])
        self.assertEqual("playwright-unavailable", preflight["code"])
        self.assert_valid_schema(payload)

    def test_browser_project_is_refused_for_mutating_commands(self) -> None:
        project = self.root / "browser-project"
        project.mkdir()
        completed, payload = self.command(
            "sync",
            extra=["--browser-project", str(project)],
        )
        self.assertEqual(2, completed.returncode, payload)
        self.assertEqual(
            "browser-project-only-for-doctor",
            payload["errors"][0]["code"],
        )
        self.assert_valid_schema(payload)

    def test_doctor_install_and_schema_validated_healthy_state(self) -> None:
        before, before_payload = self.command("doctor")
        self.assertEqual(1, before.returncode)
        self.assertFalse(before_payload["ok"])
        self.assertEqual("install-needed", before_payload["hosts"][0]["status"])
        self.assertEqual([], before_payload["hosts"][0]["discovery_candidates"])
        self.assertEqual(
            "not-verified",
            before_payload["hosts"][0]["visibility_scope"]["activation_state"],
        )
        self.assert_valid_schema(before_payload)

        installed = self.install_codex()
        self.assertEqual("installed", installed["changes"][0]["action"])
        self.assertEqual(str(self.codex_target), installed["hosts"][0]["expected_route"])
        self.assertTrue(installed["hosts"][0]["target"]["parity"])
        self.assert_valid_schema(installed)

        after, after_payload = self.command("doctor")
        self.assertEqual(0, after.returncode)
        self.assertTrue(after_payload["ok"])
        self.assertEqual("healthy", after_payload["hosts"][0]["status"])
        self.assertEqual([str(self.codex_target)], [
            route["path"]
            for route in after_payload["hosts"][0]["discovery_candidates"]
        ])
        self.assert_valid_schema(after_payload)

    def test_unrelated_invalid_skill_may_reference_design_dna_in_its_body(self) -> None:
        unrelated = self.home / ".agents" / "skills" / "web-3d" / "SKILL.md"
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text(
            "---\n"
            "name: [web-3d\n"
            "description: Deliberately malformed unrelated fixture.\n"
            "---\n"
            "This skill can be paired with design-dna for overall art direction.\n",
            encoding="utf-8",
        )

        completed, payload = self.command("doctor")
        self.assertEqual(1, completed.returncode, payload)
        self.assertEqual("install-needed", payload["hosts"][0]["status"])
        self.assertEqual([], payload["hosts"][0]["discovery_candidates"])
        self.assertEqual([], payload["errors"])

    def test_source_frontmatter_requires_one_top_level_scalar_name(self) -> None:
        invalid_entries = {
            "nested-name": (
                "---\n"
                "metadata:\n"
                "  name: design-dna\n"
                "description: Test-only nested name.\n"
                "---\n"
            ),
            "duplicate-name": (
                "---\n"
                "name: design-dna\n"
                "name: design-dna\n"
                "description: Test-only duplicate name.\n"
                "---\n"
            ),
        }
        for label, text in invalid_entries.items():
            with self.subTest(label=label):
                (self.source / "SKILL.md").write_text(text, encoding="utf-8")
                completed, payload = self.command("doctor")
                self.assertEqual(2, completed.returncode, payload)
                self.assertFalse(payload["ok"])
                self.assertIn(
                    payload["errors"][0]["code"],
                    {"invalid-skill-frontmatter", "invalid-skill-name"},
                )
                self.assertFalse(self.codex_target.exists())

    def test_dry_run_reports_plan_without_writing_any_host_or_backup_path(self) -> None:
        completed, payload = self.command("install", extra=["--dry-run"])
        self.assertEqual(0, completed.returncode)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["dry_run"])
        self.assertEqual("install", payload["changes"][0]["action"])
        self.assertFalse(payload["changes"][0]["executed"])
        self.assertFalse(self.codex_target.exists())
        self.assertFalse((self.home / ".agents").exists())
        self.assertFalse((self.home / ".design-dna").exists())
        self.assert_valid_schema(payload)

    def test_update_is_explicit_recoverable_and_idempotent_when_current(self) -> None:
        self.install_codex()
        prior_marker = "locally-modified-before-update"
        (self.codex_target / "references" / "rules.md").write_text(
            prior_marker,
            encoding="utf-8",
        )

        completed, payload = self.command("update")
        self.assertEqual(0, completed.returncode, payload)
        self.assertEqual("updated", payload["changes"][0]["action"])
        self.assertTrue(payload["hosts"][0]["target"]["parity"])
        backup_id = payload["changes"][0]["backup_id"]
        backup = self.codex_backups / backup_id
        self.assertIn(
            prior_marker,
            (backup / "skill" / "references" / "rules.md").read_text(encoding="utf-8"),
        )
        self.assert_valid_schema(json.loads((backup / "operation.json").read_text(encoding="utf-8")))
        backup_count = len(list(self.codex_backups.iterdir()))

        current, current_payload = self.command("update")
        self.assertEqual(0, current.returncode)
        self.assertEqual("already-current", current_payload["changes"][0]["action"])
        self.assertFalse(current_payload["changes"][0]["executed"])
        self.assertEqual(backup_count, len(list(self.codex_backups.iterdir())))
        self.assert_valid_schema(current_payload)

    def test_doctor_rejects_backup_metadata_outside_the_full_schema(self) -> None:
        self.install_codex()
        (self.codex_target / "references" / "rules.md").write_text(
            "changed before backup\n",
            encoding="utf-8",
        )
        updated, payload = self.command("update")
        self.assertEqual(0, updated.returncode, payload)
        metadata_path = (
            self.codex_backups
            / payload["changes"][0]["backup_id"]
            / "operation.json"
        )
        original = json.loads(metadata_path.read_text(encoding="utf-8"))
        mutations = (
            ("unknown field", {"unexpected": True}),
            ("invalid timestamp", {"created_at": "not-a-date"}),
            ("unsupported reason", {"reason": "mystery"}),
        )
        for label, changed_fields in mutations:
            with self.subTest(label=label):
                changed = dict(original)
                changed.update(changed_fields)
                metadata_path.write_text(
                    json.dumps(changed, indent=2) + "\n",
                    encoding="utf-8",
                )
                completed, doctor = self.command("doctor")
                self.assertEqual(2, completed.returncode, doctor)
                self.assertEqual(
                    "invalid-backup-record",
                    doctor["errors"][0]["code"],
                )
                self.assert_valid_schema(doctor)
                metadata_path.write_text(
                    json.dumps(original, indent=2) + "\n",
                    encoding="utf-8",
                )

    def test_operation_schema_rejects_contradictory_success_and_execution(self) -> None:
        installed = self.install_codex()
        validator = __import__("jsonschema").Draft202012Validator(self.schema)

        success_with_error = copy.deepcopy(installed)
        success_with_error["errors"] = [
            {"code": "fabricated-error", "message": "Contradiction."}
        ]
        self.assertFalse(validator.is_valid(success_with_error))

        simulated_dry_run = copy.deepcopy(installed)
        simulated_dry_run["dry_run"] = True
        self.assertFalse(validator.is_valid(simulated_dry_run))

        incomplete_rollback = copy.deepcopy(installed)
        incomplete_rollback["changes"][0]["action"] = "rolled-back"
        self.assertFalse(validator.is_valid(incomplete_rollback))

    def test_update_requires_an_existing_target(self) -> None:
        completed, payload = self.command("update")
        self.assertEqual(2, completed.returncode)
        self.assertFalse(payload["ok"])
        self.assertEqual("update-target-missing", payload["errors"][0]["code"])
        self.assertFalse(self.codex_target.exists())
        self.assert_valid_schema(payload)

    def test_single_external_route_is_reported_and_direct_install_is_refused(self) -> None:
        duplicate_roots = [
            self.home / ".codex" / "skills" / "legacy-design-dna",
            self.home / ".codex" / "plugins" / "cache" / "vendor" / "bundle" / "skills" / "dna",
        ]
        for duplicate in duplicate_roots:
            with self.subTest(duplicate=duplicate):
                if (self.home / ".codex").exists():
                    shutil.rmtree(self.home / ".codex")
                self.write_skill(duplicate, marker="unexpected-route")
                doctor, doctor_payload = self.command("doctor")
                self.assertEqual(1, doctor.returncode)
                self.assertEqual(
                    "external-candidate-stale",
                    doctor_payload["hosts"][0]["status"],
                )
                self.assertEqual(
                    [],
                    doctor_payload["hosts"][0]["collision_candidates"],
                )
                self.assert_valid_schema(doctor_payload)

                install, install_payload = self.command("install")
                self.assertEqual(2, install.returncode)
                self.assertEqual(
                    "external-discovery-candidate",
                    install_payload["errors"][0]["code"],
                )
                self.assertFalse(self.codex_target.exists())
                self.assert_valid_schema(install_payload)

    def test_claude_plugin_cache_route_is_detected_before_direct_install(
        self,
    ) -> None:
        cached = (
            self.home
            / ".claude"
            / "plugins"
            / "cache"
            / "marketplace"
            / "design-dna"
            / "3.0.0"
            / "skills"
            / "design-dna"
        )
        self.write_skill(cached, marker="cached-plugin-route")
        doctor, doctor_payload = self.command("doctor", host="claude")
        self.assertEqual(1, doctor.returncode)
        self.assertEqual(
            "external-candidate-stale",
            doctor_payload["hosts"][0]["status"],
        )
        self.assertEqual(
            [str(cached)],
            [
                route["path"]
                for route in doctor_payload["hosts"][0]["discovery_candidates"]
            ],
        )
        self.assertNotIn("active_routes", doctor_payload["hosts"][0])
        self.assertEqual(
            "unmanaged-filesystem-candidate",
            doctor_payload["hosts"][0]["discovery_candidates"][0][
                "candidate_kind"
            ],
        )
        self.assertEqual(
            "not-verified",
            doctor_payload["hosts"][0]["visibility_scope"]["activation_state"],
        )
        self.assertEqual(
            "not-inspected",
            doctor_payload["hosts"][0]["visibility_scope"][
                "project_admin_session_routes"
            ],
        )
        install, install_payload = self.command("install", host="claude")
        self.assertEqual(2, install.returncode)
        self.assertEqual(
            "external-discovery-candidate",
            install_payload["errors"][0]["code"],
        )
        self.assertEqual(
            "not-verified",
            install_payload["errors"][0]["details"]["activation_state"],
        )
        self.assertFalse(self.claude_target.exists())
        self.assert_valid_schema(doctor_payload)
        self.assert_valid_schema(install_payload)

    def test_claude_config_dir_is_independent_from_selected_home(self) -> None:
        claude_config = self.root / "separate-claude-config"
        completed, payload = self.command(
            "sync",
            host="all",
            environment_overrides={"CLAUDE_CONFIG_DIR": str(claude_config)},
        )
        self.assertEqual(0, completed.returncode, payload)
        custom_target = claude_config / "skills" / "design-dna"
        self.assertTrue(self.codex_target.is_dir())
        self.assertTrue(custom_target.is_dir())
        self.assertFalse(self.claude_target.exists())
        self.assertEqual(
            [str(self.codex_target), str(custom_target)],
            [host["expected_route"] for host in payload["hosts"]],
        )
        self.assertEqual(
            [
                str(claude_config / "skills"),
                str(claude_config / "plugins" / "cache"),
            ],
            payload["hosts"][1]["discovery_roots"],
        )
        self.assertEqual(
            str(
                self.home
                / ".design-dna"
                / "backups"
                / "claude-configs"
                / hashlib.sha256(
                    os.path.normcase(
                        os.path.abspath(str(claude_config))
                    ).encode("utf-8")
                ).hexdigest()[:16]
            ),
            payload["hosts"][1]["backup_root"],
        )
        self.assert_valid_schema(payload)

    def test_claude_config_dir_plugin_cache_is_scanned_and_blocks_duplicate(
        self,
    ) -> None:
        claude_config = self.root / "separate-claude-config"
        cached = (
            claude_config
            / "plugins"
            / "cache"
            / "marketplace"
            / "design-dna"
            / "3.0.0"
            / "skills"
            / "design-dna"
        )
        self.write_skill(cached, marker="custom-config-plugin-route")
        environment = {"CLAUDE_CONFIG_DIR": str(claude_config)}
        doctor, doctor_payload = self.command(
            "doctor",
            host="claude",
            environment_overrides=environment,
        )
        self.assertEqual(1, doctor.returncode, doctor_payload)
        self.assertEqual(
            [str(cached)],
            [
                route["path"]
                for route in doctor_payload["hosts"][0]["discovery_candidates"]
            ],
        )
        install, install_payload = self.command(
            "install",
            host="claude",
            environment_overrides=environment,
        )
        self.assertEqual(2, install.returncode, install_payload)
        self.assertEqual(
            "external-discovery-candidate",
            install_payload["errors"][0]["code"],
        )
        self.assertFalse((claude_config / "skills" / "design-dna").exists())
        self.assertFalse(self.claude_target.exists())
        self.assert_valid_schema(doctor_payload)
        self.assert_valid_schema(install_payload)

    def test_empty_claude_config_dir_fails_closed(self) -> None:
        completed, payload = self.command(
            "doctor",
            host="claude",
            environment_overrides={"CLAUDE_CONFIG_DIR": "   "},
        )
        self.assertEqual(2, completed.returncode, payload)
        self.assertEqual(
            "invalid-claude-config-dir",
            payload["errors"][0]["code"],
        )
        self.assertFalse(self.claude_target.exists())
        self.assert_valid_schema(payload)

    def test_claude_config_dir_does_not_change_a_codex_only_operation(
        self,
    ) -> None:
        completed, payload = self.command(
            "install",
            host="codex",
            environment_overrides={"CLAUDE_CONFIG_DIR": "   "},
        )
        self.assertEqual(0, completed.returncode, payload)
        self.assertEqual(
            str(self.codex_target),
            payload["hosts"][0]["expected_route"],
        )
        self.assertTrue(self.codex_target.is_dir())
        self.assertFalse(self.claude_target.exists())
        self.assert_valid_schema(payload)

    def test_sync_handles_mixed_missing_stale_and_current_hosts(self) -> None:
        self.install_codex()
        first, first_payload = self.command("sync", host="all")
        self.assertEqual(0, first.returncode, first_payload)
        self.assertEqual(
            ["already-current", "installed"],
            [change["action"] for change in first_payload["changes"]],
        )
        self.assertTrue(self.codex_target.is_dir())
        self.assertTrue(self.claude_target.is_dir())

        (self.codex_target / "references" / "rules.md").write_text(
            "stale-codex",
            encoding="utf-8",
        )
        second, second_payload = self.command("sync", host="all")
        self.assertEqual(0, second.returncode, second_payload)
        self.assertEqual(
            ["updated", "already-current"],
            [change["action"] for change in second_payload["changes"]],
        )
        self.assertTrue(all(host["target"]["parity"] for host in second_payload["hosts"]))
        self.assert_valid_schema(first_payload)
        self.assert_valid_schema(second_payload)

    def test_uninstall_can_reduce_two_routes_to_one_external_route(self) -> None:
        self.install_codex()
        external = self.home / ".codex" / "skills" / "external-design-dna"
        self.write_skill(external, marker="externally-managed")
        before, before_payload = self.command("doctor")
        self.assertEqual(1, before.returncode)
        self.assertEqual("candidate-collision", before_payload["hosts"][0]["status"])
        self.assertEqual(
            2,
            len(before_payload["hosts"][0]["collision_candidates"]),
        )

        removed, removed_payload = self.command("uninstall")
        self.assertEqual(0, removed.returncode, removed_payload)
        self.assertFalse(self.codex_target.exists())
        self.assertTrue(external.is_dir())
        self.assertEqual(
            "external-candidate-stale",
            removed_payload["hosts"][0]["status"],
        )
        self.assertEqual(
            [],
            removed_payload["hosts"][0]["collision_candidates"],
        )
        self.assert_valid_schema(removed_payload)

    def test_mutating_operations_refuse_a_concurrent_manager_lock(self) -> None:
        module_name = "design_dna_manage_install_lock_test_module"
        specification = importlib.util.spec_from_file_location(module_name, SCRIPT)
        self.assertIsNotNone(specification)
        self.assertIsNotNone(specification.loader)
        module = importlib.util.module_from_spec(specification)
        sys.modules[module_name] = module
        try:
            specification.loader.exec_module(module)
            backup_base = self.home / ".design-dna" / "backups"
            with module.operation_lock(backup_base, self.home):
                completed, payload = self.command("sync")
            self.assertEqual(2, completed.returncode)
            self.assertEqual("operation-locked", payload["errors"][0]["code"])
            self.assertFalse(self.codex_target.exists())
            self.assert_valid_schema(payload)
        finally:
            sys.modules.pop(module_name, None)

    def test_uninstall_is_recoverable_and_rollback_restores_exact_tree(self) -> None:
        installed = self.install_codex()
        installed_hash = installed["source"]["sha256"]
        sibling = self.codex_target.parent / "keep-me.txt"
        sibling.write_text("unrelated", encoding="utf-8")

        removed, removed_payload = self.command("uninstall")
        self.assertEqual(0, removed.returncode, removed_payload)
        self.assertEqual("uninstalled", removed_payload["changes"][0]["action"])
        self.assertFalse(self.codex_target.exists())
        self.assertTrue(sibling.is_file())
        backup_id = removed_payload["changes"][0]["backup_id"]
        backup = self.codex_backups / backup_id
        self.assertTrue((backup / "skill" / "SKILL.md").is_file())
        self.assert_valid_schema(removed_payload)

        restored, restored_payload = self.command("rollback")
        self.assertEqual(0, restored.returncode, restored_payload)
        self.assertEqual("rolled-back", restored_payload["changes"][0]["action"])
        self.assertEqual(installed_hash, restored_payload["changes"][0]["installed_sha256"])
        self.assertTrue(restored_payload["changes"][0]["canonical_parity"])
        self.assertTrue(self.codex_target.is_dir())
        self.assertTrue(sibling.is_file())
        metadata = json.loads((backup / "operation.json").read_text(encoding="utf-8"))
        self.assertEqual("restored", metadata["status"])
        self.assertFalse((backup / "skill").exists())
        self.assert_valid_schema(metadata)
        self.assert_valid_schema(restored_payload)

    def test_rollback_refuses_ambiguity_and_accepts_an_exact_backup_id(self) -> None:
        self.install_codex()
        (self.codex_target / "references" / "rules.md").write_text("first-drift", encoding="utf-8")
        first_update, first_payload = self.command("update")
        self.assertEqual(0, first_update.returncode)
        first_id = first_payload["changes"][0]["backup_id"]

        (self.codex_target / "references" / "rules.md").write_text("second-drift", encoding="utf-8")
        second_update, second_payload = self.command("update")
        self.assertEqual(0, second_update.returncode)
        second_id = second_payload["changes"][0]["backup_id"]
        self.assertNotEqual(first_id, second_id)

        ambiguous, ambiguous_payload = self.command("rollback")
        self.assertEqual(2, ambiguous.returncode)
        self.assertEqual("ambiguous-rollback", ambiguous_payload["errors"][0]["code"])
        self.assertTrue(self.codex_target.is_dir())

        selected, selected_payload = self.command("rollback", extra=["--backup-id", first_id])
        self.assertEqual(0, selected.returncode, selected_payload)
        self.assertEqual(first_id, selected_payload["changes"][0]["backup_id"])
        self.assertFalse(selected_payload["changes"][0]["canonical_parity"])
        self.assertIn(
            "first-drift",
            (self.codex_target / "references" / "rules.md").read_text(encoding="utf-8"),
        )
        self.assert_valid_schema(selected_payload)

    def test_mid_update_commit_failure_restores_prior_install_and_cleans_staging(self) -> None:
        self.install_codex()
        prior_marker = "must-survive-failed-update"
        (self.codex_target / "references" / "rules.md").write_text(prior_marker, encoding="utf-8")

        completed, payload = self.command("update", extra=["--simulate-commit-failure"])
        self.assertEqual(2, completed.returncode)
        self.assertEqual("update-commit-failed", payload["errors"][0]["code"])
        self.assertIn(
            prior_marker,
            (self.codex_target / "references" / "rules.md").read_text(encoding="utf-8"),
        )
        if self.codex_backups.exists():
            residue = [
                entry.name
                for entry in self.codex_backups.iterdir()
                if entry.name.startswith((".pending-", ".stage-"))
            ]
            self.assertEqual([], residue)
        self.assert_valid_schema(payload)

    def test_recover_after_hard_exit_immediately_after_install_target_rename(self) -> None:
        self.hard_exit("install", "install-after-new-target")
        self.assertTrue(self.codex_target.is_dir())
        self.assertTrue(any(entry.name.startswith(".stage-") for entry in self.codex_backups.iterdir()))

        planned, planned_payload = self.command("recover", extra=["--dry-run"])
        self.assertEqual(0, planned.returncode, planned_payload)
        self.assertEqual(["removed-empty-stage"], planned_payload["changes"][0]["recovery_actions"])
        self.assertFalse(planned_payload["changes"][0]["executed"])
        self.assert_valid_schema(planned_payload)

        recovered, recovered_payload = self.command("recover")
        self.assertEqual(0, recovered.returncode, recovered_payload)
        self.assertEqual("recovered", recovered_payload["changes"][0]["action"])
        self.assertEqual(["removed-empty-stage"], recovered_payload["changes"][0]["recovery_actions"])
        self.assertTrue(recovered_payload["hosts"][0]["target"]["parity"])
        self.assert_no_transaction_residue(self.codex_backups)
        self.assert_valid_schema(recovered_payload)

        repeated, repeated_payload = self.command("recover")
        self.assertEqual(0, repeated.returncode, repeated_payload)
        self.assertEqual([], repeated_payload["changes"])
        self.assert_valid_schema(repeated_payload)

    def test_recover_after_hard_exit_between_update_target_renames_restores_prior_tree(self) -> None:
        self.install_codex()
        prior_marker = "must-survive-interrupted-update"
        (self.codex_target / "references" / "rules.md").write_text(prior_marker, encoding="utf-8")

        self.hard_exit("update", "update-before-new-target")
        self.assertFalse(self.codex_target.exists())

        recovered, payload = self.command("recover")
        self.assertEqual(0, recovered.returncode, payload)
        actions = payload["changes"][0]["recovery_actions"]
        self.assertEqual(["restored-pending-target", "removed-stage"], actions)
        self.assertIn(
            prior_marker,
            (self.codex_target / "references" / "rules.md").read_text(encoding="utf-8"),
        )
        self.assertFalse(payload["hosts"][0]["target"]["parity"])
        self.assert_no_transaction_residue(self.codex_backups)
        self.assert_valid_schema(payload)

        synchronized, synchronized_payload = self.command("sync")
        self.assertEqual(0, synchronized.returncode, synchronized_payload)
        self.assertTrue(synchronized_payload["hosts"][0]["target"]["parity"])

    def test_recover_after_hard_exit_after_update_target_rename_finalizes_backup(self) -> None:
        self.install_codex()
        prior_marker = "recoverable-update-prior"
        (self.codex_target / "references" / "rules.md").write_text(prior_marker, encoding="utf-8")

        self.hard_exit("update", "update-after-new-target")
        self.assertTrue(self.codex_target.is_dir())

        recovered, payload = self.command("recover")
        self.assertEqual(0, recovered.returncode, payload)
        self.assertEqual(
            ["finalized-pending-backup", "removed-empty-stage"],
            payload["changes"][0]["recovery_actions"],
        )
        self.assertTrue(payload["hosts"][0]["target"]["parity"])
        self.assertEqual(1, len(payload["hosts"][0]["available_backups"]))
        backup_id = payload["hosts"][0]["available_backups"][0]["backup_id"]
        self.assertIn(
            prior_marker,
            (self.codex_backups / backup_id / "skill" / "references" / "rules.md").read_text(
                encoding="utf-8"
            ),
        )
        self.assert_no_transaction_residue(self.codex_backups)
        self.assert_valid_schema(payload)

    def test_recover_after_hard_exit_after_uninstall_target_rename_restores_install(self) -> None:
        self.install_codex()
        self.hard_exit("uninstall", "uninstall-after-target")
        self.assertFalse(self.codex_target.exists())

        recovered, payload = self.command("recover")
        self.assertEqual(0, recovered.returncode, payload)
        self.assertEqual(
            ["restored-pending-target"],
            payload["changes"][0]["recovery_actions"],
        )
        self.assertTrue(payload["hosts"][0]["target"]["parity"])
        self.assert_no_transaction_residue(self.codex_backups)
        self.assert_valid_schema(payload)

    def test_recover_after_hard_exit_after_rollback_target_rename_repairs_metadata(self) -> None:
        self.install_codex()
        prior_marker = "rollback-selection"
        (self.codex_target / "references" / "rules.md").write_text(prior_marker, encoding="utf-8")
        updated, updated_payload = self.command("update")
        self.assertEqual(0, updated.returncode, updated_payload)
        selected_id = updated_payload["changes"][0]["backup_id"]

        self.hard_exit(
            "rollback",
            "rollback-after-restored-target",
            extra=["--backup-id", selected_id],
        )
        self.assertIn(
            prior_marker,
            (self.codex_target / "references" / "rules.md").read_text(encoding="utf-8"),
        )

        recovered, payload = self.command("recover")
        self.assertEqual(0, recovered.returncode, payload)
        self.assertEqual(
            ["finalized-pending-backup", "repaired-consumed-backup"],
            payload["changes"][0]["recovery_actions"],
        )
        selected_metadata = json.loads(
            (self.codex_backups / selected_id / "operation.json").read_text(encoding="utf-8")
        )
        self.assertEqual("restored", selected_metadata["status"])
        self.assertFalse((self.codex_backups / selected_id / "skill").exists())
        self.assert_no_transaction_residue(self.codex_backups)
        self.assert_valid_schema(selected_metadata)
        self.assert_valid_schema(payload)

    def test_all_host_recovery_is_transaction_locked_and_idempotent(self) -> None:
        self.hard_exit("install", "install-after-new-target", host="codex")
        self.hard_exit("install", "install-after-new-target", host="claude")

        recovered, payload = self.command("recover", host="all")
        self.assertEqual(0, recovered.returncode, payload)
        self.assertEqual(["codex", "claude"], [change["host"] for change in payload["changes"]])
        self.assertTrue(all(host["target"]["parity"] for host in payload["hosts"]))
        self.assert_no_transaction_residue(self.codex_backups)
        self.assert_no_transaction_residue(
            self.home / ".design-dna" / "backups" / "claude"
        )
        self.assert_valid_schema(payload)

        repeated, repeated_payload = self.command("recover", host="all")
        self.assertEqual(0, repeated.returncode, repeated_payload)
        self.assertEqual([], repeated_payload["changes"])
        self.assertTrue(all(host["target"]["parity"] for host in repeated_payload["hosts"]))
        self.assert_valid_schema(repeated_payload)

    def test_unsafe_backup_containment_and_source_overlap_are_refused(self) -> None:
        unsafe_backup = self.home / ".agents" / "skills" / "backups"
        completed, payload = self.command(
            "install",
            extra=["--backup-root", str(unsafe_backup)],
        )
        self.assertEqual(2, completed.returncode)
        self.assertEqual("unsafe-backup-root", payload["errors"][0]["code"])
        self.assertFalse(self.codex_target.exists())

        overlapping_source = self.home / ".agents" / "skills" / "canonical-source"
        self.write_skill(overlapping_source, marker="unsafe-source")
        old_source = self.source
        self.source = overlapping_source
        try:
            overlap, overlap_payload = self.command("doctor")
        finally:
            self.source = old_source
        self.assertEqual(2, overlap.returncode)
        self.assertEqual("overlapping-source-discovery", overlap_payload["errors"][0]["code"])
        self.assert_valid_schema(payload)
        self.assert_valid_schema(overlap_payload)

    def test_reparse_point_in_source_is_refused_when_platform_can_create_one(self) -> None:
        external = self.root / "external"
        external.mkdir()
        link = self.source / "linked"
        try:
            os.symlink(external, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            flagged = self.source / "simulated-redirect"
            flagged.mkdir()
            module_name = "design_dna_manage_install_test_module"
            specification = importlib.util.spec_from_file_location(module_name, SCRIPT)
            self.assertIsNotNone(specification)
            self.assertIsNotNone(specification.loader)
            module = importlib.util.module_from_spec(specification)
            sys.modules[module_name] = module
            try:
                specification.loader.exec_module(module)
                real_is_reparse = module.is_reparse

                def simulated_is_reparse(path: Path) -> bool:
                    if module.path_key(path) == module.path_key(flagged):
                        return True
                    return real_is_reparse(path)

                with mock.patch.object(module, "is_reparse", side_effect=simulated_is_reparse):
                    with self.assertRaises(module.ManagerError) as raised:
                        module.validate_design_dna_tree(self.source)
                self.assertEqual("reparse-point-refused", raised.exception.code)
                self.assertEqual(str(flagged), raised.exception.path)
            finally:
                sys.modules.pop(module_name, None)
            return
        completed, payload = self.command("doctor")
        self.assertEqual(2, completed.returncode)
        self.assertEqual("reparse-point-refused", payload["errors"][0]["code"])
        self.assert_valid_schema(payload)

    def test_all_hosts_install_to_only_the_two_supported_direct_routes(self) -> None:
        completed, payload = self.command("install", host="all")
        self.assertEqual(0, completed.returncode, payload)
        self.assertTrue(self.codex_target.is_dir())
        self.assertTrue(self.claude_target.is_dir())
        self.assertEqual(
            [str(self.codex_target), str(self.claude_target)],
            [host["expected_route"] for host in payload["hosts"]],
        )
        self.assertEqual(["installed", "installed"], [change["action"] for change in payload["changes"]])
        self.assertFalse((self.home / ".codex" / "skills" / "design-dna").exists())
        self.assert_valid_schema(payload)

    def test_all_hosts_reverse_the_first_commit_if_the_second_commit_fails(self) -> None:
        completed, payload = self.command(
            "install",
            host="all",
            extra=["--simulate-commit-failure"],
        )
        self.assertEqual(2, completed.returncode)
        self.assertEqual("install-commit-failed", payload["errors"][0]["code"])
        self.assertFalse(self.codex_target.exists())
        self.assertFalse(self.claude_target.exists())
        failed_backups = self.home / ".design-dna" / "backups" / "codex"
        self.assertTrue(any(failed_backups.iterdir()))
        self.assert_valid_schema(payload)

    def test_invalid_cli_arguments_still_emit_the_operation_json_contract(self) -> None:
        command = [sys.executable, "-B", str(SCRIPT), "not-a-command"]
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        self.assertEqual(2, completed.returncode)
        self.assertEqual("", completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual("invalid", payload["operation"])
        self.assertEqual("invalid-arguments", payload["errors"][0]["code"])
        self.assert_valid_schema(payload)


if __name__ == "__main__":
    unittest.main()
