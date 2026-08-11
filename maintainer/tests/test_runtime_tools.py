from __future__ import annotations

import binascii
import hashlib
import importlib.util
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch


PLUGIN = Path(__file__).resolve().parents[2]
INIT = PLUGIN / "skills" / "design-dna" / "scripts" / "init_project_state.py"
SCAN = PLUGIN / "skills" / "design-dna" / "scripts" / "scan_project.py"
MAINTAINER_SCRIPTS = PLUGIN / "maintainer" / "scripts"
ACTIVE_EXPIRY = (date.today() + timedelta(days=30)).isoformat()


def run_script(script: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(script), *arguments],
        text=True, encoding="utf-8", capture_output=True, env=environment,
    )


def make_directory_link(link: Path, target: Path) -> bool:
    try:
        os.symlink(target, link, target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        if os.name != "nt":
            return False
        completed = subprocess.run(
            ["cmd.exe", "/c", "mklink", "/J", str(link), str(target)],
            text=True, capture_output=True,
        )
        return completed.returncode == 0


def load_initializer():
    spec = importlib.util.spec_from_file_location(
        "design_dna_state_initializer_tests",
        INIT,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("could not load project-state initializer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def file_snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def load_audit():
    sys.path.insert(0, str(MAINTAINER_SCRIPTS))
    try:
        import audit_package
    finally:
        sys.path.remove(str(MAINTAINER_SCRIPTS))
    return audit_package


def write_png(path: Path, width: int, height: int) -> str:
    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = binascii.crc32(kind)
        crc = binascii.crc32(data, crc) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    row = b"\x00" + b"\x30\x60\x90" * width
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0),
        )
        + chunk(b"IDAT", zlib.compress(row * height))
        + chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


class InitializerTests(unittest.TestCase):
    def test_showcase_initializes_the_optional_taste_calibration_record(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            result = run_script(
                INIT,
                "--project",
                str(project),
                "--profile",
                "showcase",
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            state_root = project / ".design-dna"
            state = json.loads((state_root / "state.json").read_text(encoding="utf-8"))
            self.assertIn("taste-calibration", state["records"])
            self.assertTrue((state_root / "taste-calibration.md").is_file())
            check = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

    def test_initializes_and_validates_transactionally(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            result = run_script(INIT, "--project", str(project), "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["assurance_profile"], "standard")
            state = project / ".design-dna"
            self.assertEqual(
                sorted(path.name for path in state.iterdir()),
                [".gitignore", "direction.md", "evidence", "state.json", "visual-review.md"],
            )
            check = run_script(INIT, "--project", str(project), "--check-state", "--json")
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            readiness = run_script(
                INIT,
                "--project",
                str(project),
                "--check-ready",
                "--json",
            )
            self.assertEqual(readiness.returncode, 1)
            self.assertIn(
                "remains draft",
                " ".join(json.loads(readiness.stdout)["failures"]),
            )

    def test_malformed_state_fails_strict_check(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            self.assertEqual(run_script(INIT, "--project", str(project)).returncode, 0)
            (project / ".design-dna" / "state.json").write_text(
                '{"schema_version":1,"created_with":"unterminated"', encoding="utf-8"
            )
            check = run_script(INIT, "--project", str(project), "--check-state", "--json")
            self.assertEqual(check.returncode, 1)
            self.assertTrue(json.loads(check.stdout)["failures"])

    def test_migration_persists_inferred_assurance_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            initialized = run_script(
                INIT,
                "--project",
                str(project),
                "--profile",
                "showcase",
            )
            self.assertEqual(
                initialized.returncode,
                0,
                initialized.stdout + initialized.stderr,
            )
            state_path = project / ".design-dna" / "state.json"
            legacy = json.loads(state_path.read_text(encoding="utf-8"))
            legacy.pop("assurance_profiles")
            legacy["schema_version"] = 1
            legacy["assurance_profile"] = "showcase"
            state_path.write_text(
                json.dumps(legacy, indent=2) + "\n",
                encoding="utf-8",
            )
            before = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(before.returncode, 1)
            migrated = run_script(
                INIT,
                "--project",
                str(project),
                "--migrate",
                "--json",
            )
            self.assertEqual(
                migrated.returncode,
                0,
                migrated.stdout + migrated.stderr,
            )
            current = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(current["assurance_profiles"], ["showcase"])
            self.assertNotIn("assurance_profile", current)

    def test_migration_withdraws_stale_completion_against_current_profile(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            initialized = run_script(
                INIT,
                "--project",
                str(project),
                "--record",
                "direction",
            )
            self.assertEqual(
                initialized.returncode,
                0,
                initialized.stdout + initialized.stderr,
            )
            proof = project / "legacy-proof.txt"
            proof.write_text("legacy proof\n", encoding="utf-8")
            proof_digest = hashlib.sha256(proof.read_bytes()).hexdigest()
            record = project / ".design-dna" / "direction.md"
            legacy = record.read_text(encoding="utf-8").replace(
                'record_status: "draft"\n',
                (
                    'record_status: "complete"\n'
                    f'record_body_sha256: "{"0" * 64}"\n'
                    'binding_kind: "artifact"\n'
                    'binding_id: "legacy-build-1"\n'
                    'binding_path: "legacy-proof.txt"\n'
                    f'binding_sha256: "{proof_digest}"\n'
                    'completion_owner: "legacy-reviewer"\n'
                    'completed_at: "2026-07-28T12:00:00+00:00"\n'
                    'unresolved_high: "0"\n'
                    'unresolved_medium: "0"\n'
                    'limitations: "No limitations were recorded in the legacy contract."\n'
                ),
                1,
            )
            record.write_text(legacy, encoding="utf-8", newline="\n")

            migrated = run_script(
                INIT,
                "--project",
                str(project),
                "--migrate",
                "--json",
            )
            self.assertEqual(
                migrated.returncode,
                0,
                migrated.stdout + migrated.stderr,
            )
            current = record.read_text(encoding="utf-8")
            self.assertIn('record_status: "draft"', current)
            self.assertNotIn("binding_id:", current)
            report = json.loads(
                (
                    project
                    / ".design-dna"
                    / "migration-report.json"
                ).read_text(encoding="utf-8")
            )
            downgrade = report["completion_downgrades"][0]
            self.assertEqual(downgrade["record"], "direction")
            self.assertEqual(
                downgrade["source_body_sha256"],
                hashlib.sha256(
                    legacy.split("\n---\n", 1)[1].encode("utf-8")
                ).hexdigest(),
            )
            self.assertEqual(
                downgrade["prior_binding_id"],
                "legacy-build-1",
            )
            self.assertTrue(downgrade["reasons"])

    def test_existing_files_preserved_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            self.assertEqual(run_script(INIT, "--project", str(project)).returncode, 0)
            direction = project / ".design-dna" / "direction.md"
            original = direction.read_text(encoding="utf-8") + "\nOWNER CONTENT\n"
            direction.write_text(original, encoding="utf-8")
            self.assertEqual(run_script(INIT, "--project", str(project)).returncode, 0)
            self.assertEqual(direction.read_text(encoding="utf-8"), original)

    def test_explicit_records_override_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            result = run_script(
                INIT, "--project", str(project), "--record", "direction-proof",
                "--record", "user-validation", "--json",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            state = project / ".design-dna"
            self.assertTrue((state / "direction-proof.md").is_file())
            self.assertTrue((state / "user-validation.md").is_file())
            self.assertFalse((state / "direction.md").exists())
            self.assertFalse((state / "visual-review.md").exists())
            manifest = json.loads((state / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["records"], ["direction-proof", "user-validation"])
            self.assertEqual(
                manifest["assurance_profiles"],
                ["high-risk"],
                "A direction proof must not escalate an explicit custom record set "
                "into a showcase profile.",
            )

    def test_showcase_profile_initializes_exploration_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            result = run_script(
                INIT,
                "--project",
                str(project),
                "--profile",
                "showcase",
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            state = project / ".design-dna"
            exploration = state / "exploration.md"
            self.assertTrue(exploration.is_file())
            text = exploration.read_text(encoding="utf-8")
            self.assertIn("# Creative exploration", text)
            self.assertIn("## Evidence and candidate reasoning", text)
            self.assertIn("## Decision and limits", text)
            self.assertNotIn("__DESIGN_DNA_VERSION__", text)
            manifest = json.loads(
                (state / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest["records"],
                [
                    "exploration",
                    "taste-calibration",
                    "direction",
                    "direction-proof",
                    "visual-review",
                ],
            )
            self.assertEqual(manifest["assurance_profiles"], ["showcase"])
            state_schema = json.loads(
                (
                    PLUGIN
                    / "maintainer"
                    / "schemas"
                    / "project-state.schema.json"
                ).read_text(encoding="utf-8")
            )
            self.assertIn(
                "exploration",
                state_schema["properties"]["records"]["items"]["enum"],
            )
            checked = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(
                checked.returncode,
                0,
                checked.stdout + checked.stderr,
            )

    def test_batch_study_profile_initializes_protocol_and_readiness_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            result = run_script(
                INIT,
                "--project",
                str(project),
                "--profile",
                "batch-study",
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            state = project / ".design-dna"
            contract_path = state / "batch-range.json"
            self.assertTrue(contract_path.is_file())
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            self.assertEqual(len(contract["sites"]), 3)
            self.assertTrue(
                all(site["status"] == "planned" for site in contract["sites"])
            )
            self.assertTrue(
                all(
                    page["captures"] == []
                    for site in contract["sites"]
                    for page in site["pages"]
                )
            )
            self.assertTrue(
                all(
                    not project.joinpath(*site["build_root"].split("/")).exists()
                    for site in contract["sites"]
                )
            )
            self.assertEqual(
                contract["study"]["review_protocol"],
                {
                    "site_observation": "unprimed-before-diagnostics",
                    "whole_system_comparison": "masked",
                    "automatic_aesthetic_pass": False,
                },
            )
            self.assertTrue(
                all(
                    viewport["width"] is None
                    for viewport in contract["study"]["viewport_classes"]
                )
            )
            self.assertEqual(contract["data_handling"]["status"], "pending")
            self.assertEqual(
                contract["data_handling"]["capture_authorization"]["status"],
                "pending",
            )
            self.assertEqual(
                contract["data_handling"]["contact_sheet_authorization"]["status"],
                "pending",
            )
            self.assertTrue(
                all(
                    site["implementation_isolation"]["status"] == "pending"
                    and site["implementation_isolation"]["source_packet"]["path"]
                    and site["implementation_isolation"]["producer_context_id"]
                    for site in contract["sites"]
                )
            )
            manifest = json.loads(
                (state / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest["assurance_profiles"],
                ["standard", "batch-study"],
            )
            self.assertEqual(
                manifest["records"],
                [
                    "exploration",
                    "direction",
                    "direction-proof",
                    "batch-range",
                    "visual-review",
                ],
            )
            self.assertEqual(
                manifest["evidence_contract"]["applicable_capabilities"],
                ["batch-study"],
            )
            self.assertIn(
                "## Batch Study protocol",
                (state / "direction.md").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "frozen source packets",
                (state / "direction.md").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "capture/contact-sheet authorization",
                (state / "direction.md").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "## Batch Study review",
                (state / "visual-review.md").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "do not establish pixel redaction",
                (state / "visual-review.md").read_text(encoding="utf-8"),
            )

            for viewport in contract["study"]["viewport_classes"]:
                viewport["width"] = 1200 if viewport["role"] == "wide" else 480
                viewport["height"] = 800
            for site in contract["sites"]:
                site["independence_basis"] = (
                    "This case has its own audience, task, subject research, "
                    f"content constraints, and delivery context for {site['id']}."
                )
                brief_path = project.joinpath(*site["brief"]["path"].split("/"))
                brief_path.parent.mkdir(parents=True, exist_ok=True)
                brief_bytes = f"Frozen independent brief for {site['id']}.\n".encode()
                brief_path.write_bytes(brief_bytes)
                site["brief"]["sha256"] = hashlib.sha256(brief_bytes).hexdigest()
                source_ref = site["implementation_isolation"]["source_packet"]
                source_path = project.joinpath(*source_ref["path"].split("/"))
                source_path.parent.mkdir(parents=True, exist_ok=True)
                source_bytes = (
                    f'{{"site":"{site["id"]}","sources":["owner-brief"]}}\n'
                ).encode()
                source_path.write_bytes(source_bytes)
                source_ref["sha256"] = hashlib.sha256(source_bytes).hexdigest()
            contract_path.write_text(
                json.dumps(contract, indent=2) + "\n",
                encoding="utf-8",
            )

            checked = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            readiness = run_script(
                INIT,
                "--project",
                str(project),
                "--check-ready",
                "--json",
            )
            self.assertEqual(readiness.returncode, 1)
            failures = "\n".join(json.loads(readiness.stdout)["failures"])
            self.assertIn("remains draft", failures)
            self.assertIn("batch study", failures.casefold())
            self.assertIn("site-planned", failures)
            self.assertNotIn("Invalid Batch Study readiness evidence", failures)
            self.assertTrue(
                all(
                    not project.joinpath(*site["build_root"].split("/")).exists()
                    for site in contract["sites"]
                )
            )

            contract["sites"] = []
            contract_path.write_text(
                json.dumps(contract, indent=2) + "\n",
                encoding="utf-8",
            )
            malformed = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(malformed.returncode, 1)
            malformed_failures = "\n".join(
                json.loads(malformed.stdout)["failures"]
            )
            self.assertIn("too-few-sites", malformed_failures)

    def test_assurance_profiles_accumulate_and_every_added_record_is_ready_gated(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            for profile in ("showcase", "high-risk"):
                result = run_script(
                    INIT,
                    "--project",
                    str(project),
                    "--profile",
                    profile,
                    "--json",
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    result.stdout + result.stderr,
                )
            added_asset = run_script(
                INIT,
                "--project",
                str(project),
                "--record",
                "assets",
                "--json",
            )
            self.assertEqual(
                added_asset.returncode,
                0,
                added_asset.stdout + added_asset.stderr,
            )
            state = json.loads(
                (
                    project / ".design-dna" / "state.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(
                state["assurance_profiles"],
                ["showcase", "high-risk", "asset-led"],
            )
            self.assertEqual(
                set(state["records"]),
                {
                    "exploration",
                    "taste-calibration",
                    "direction",
                    "direction-proof",
                    "visual-review",
                    "claims",
                    "user-validation",
                    "assets",
                },
            )
            readiness = run_script(
                INIT,
                "--project",
                str(project),
                "--check-ready",
                "--json",
            )
            self.assertEqual(readiness.returncode, 1)
            failures = json.loads(readiness.stdout)["failures"]
            self.assertTrue(
                any("asset" in failure.casefold() for failure in failures)
            )
            self.assertTrue(
                any("direction.md" in failure for failure in failures)
            )

    def test_empty_record_inventory_cannot_pass_state_or_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            initialized = run_script(
                INIT,
                "--project",
                str(project),
                "--json",
            )
            self.assertEqual(
                initialized.returncode,
                0,
                initialized.stdout + initialized.stderr,
            )
            state_path = project / ".design-dna" / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["records"] = []
            state_path.write_text(
                json.dumps(state, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            for operation in ("--check-state", "--check-ready"):
                with self.subTest(operation=operation):
                    checked = run_script(
                        INIT,
                        "--project",
                        str(project),
                        operation,
                        "--json",
                    )
                    self.assertEqual(
                        checked.returncode,
                        1,
                        checked.stdout + checked.stderr,
                    )
                    self.assertTrue(
                        any(
                            "nonempty" in failure
                            for failure in json.loads(
                                checked.stdout
                            )["failures"]
                        )
                    )

    def test_stronger_capability_applies_to_listed_standalone_record_only(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            initialized = run_script(
                INIT,
                "--project",
                str(project),
                "--record",
                "direction",
                "--json",
            )
            self.assertEqual(
                initialized.returncode,
                0,
                initialized.stdout + initialized.stderr,
            )
            state_path = project / ".design-dna" / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["assurance_profiles"] = ["asset-led"]
            state_path.write_text(
                json.dumps(state, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            downgraded = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(
                downgraded.returncode,
                1,
                downgraded.stdout + downgraded.stderr,
            )
            self.assertTrue(
                any(
                    "omit capabilities implied by the listed records"
                    in failure
                    for failure in json.loads(
                        downgraded.stdout
                    )["failures"]
                )
            )

            state["assurance_profiles"] = ["showcase"]
            state_path.write_text(
                json.dumps(state, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            checked = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(
                checked.returncode,
                0,
                checked.stdout + checked.stderr,
            )
            readiness = run_script(
                INIT,
                "--project",
                str(project),
                "--check-ready",
                "--json",
            )
            self.assertEqual(
                readiness.returncode,
                1,
                readiness.stdout + readiness.stderr,
            )
            failures = json.loads(readiness.stdout)["failures"]
            self.assertEqual(len(failures), 1)
            self.assertIn(
                "Listed showcase record remains draft: direction.md",
                failures[0],
            )
            self.assertFalse(
                any("exploration" in failure for failure in failures)
            )

            initializer = load_initializer()
            direction = (
                project / ".design-dna" / "direction.md"
            ).read_text(encoding="utf-8")
            required = initializer.required_labels_for_record(
                "direction",
                direction,
                required_assurance_profiles=("showcase",),
            )
            self.assertNotIn(
                "Creative-exploration record, candidate IDs, and "
                "source-packet version",
                required,
            )
            self.assertEqual(
                (),
                required,
                "A profile must not reintroduce a fixed aesthetic evidence label.",
            )
            help_result = run_script(INIT, "--help")
            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            self.assertIn(
                "every record listed in state.json",
                " ".join(help_result.stdout.split()),
            )

    def test_quick_profile_and_handoff_record_are_available(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            quick_project = Path(temporary) / "quick"
            quick_project.mkdir()
            quick = run_script(
                INIT,
                "--project",
                str(quick_project),
                "--profile",
                "quick",
                "--json",
            )
            self.assertEqual(quick.returncode, 0, quick.stdout + quick.stderr)
            quick_manifest = json.loads(
                (
                    quick_project / ".design-dna" / "state.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(
                quick_manifest["records"],
                ["direction", "visual-review"],
            )
            self.assertEqual(
                quick_manifest["assurance_profiles"],
                ["quick"],
            )

            handoff_project = Path(temporary) / "handoff"
            handoff_project.mkdir()
            handoff = run_script(
                INIT,
                "--project",
                str(handoff_project),
                "--record",
                "handoff",
                "--json",
            )
            self.assertEqual(
                handoff.returncode,
                0,
                handoff.stdout + handoff.stderr,
            )
            handoff_path = (
                handoff_project / ".design-dna" / "handoff.md"
            )
            self.assertTrue(handoff_path.is_file())
            self.assertIn(
                'record_status: "draft"',
                handoff_path.read_text(encoding="utf-8"),
            )
            state_schema = json.loads(
                (
                    PLUGIN
                    / "maintainer"
                    / "schemas"
                    / "project-state.schema.json"
                ).read_text(encoding="utf-8")
            )
            self.assertIn(
                "handoff",
                state_schema["properties"]["records"]["items"]["enum"],
            )

    def test_claim_ledger_is_selectable_and_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            created = run_script(
                INIT,
                "--project",
                str(project),
                "--record",
                "claims",
                "--json",
            )
            self.assertEqual(
                created.returncode,
                0,
                created.stdout + created.stderr,
            )
            state = project / ".design-dna"
            claims = state / "claims.md"
            self.assertTrue(claims.is_file())
            text = claims.read_text(encoding="utf-8")
            self.assertIn("# Claim ledger", text)
            self.assertIn("Calculators and derived outputs", text)
            self.assertNotIn("__DESIGN_DNA_VERSION__", text)
            manifest = json.loads(
                (state / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["records"], ["claims"])
            state_schema = json.loads(
                (
                    PLUGIN
                    / "maintainer"
                    / "schemas"
                    / "project-state.schema.json"
                ).read_text(encoding="utf-8")
            )
            self.assertIn(
                "claims",
                state_schema["properties"]["records"]["items"]["enum"],
            )
            checked = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(
                checked.returncode,
                0,
                checked.stdout + checked.stderr,
            )

    def test_user_validation_requires_privacy_controls_and_ignore_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            created = run_script(
                INIT,
                "--project",
                str(project),
                "--record",
                "user-validation",
                "--json",
            )
            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
            state = project / ".design-dna"
            research = state / "user-validation.md"
            ignore_path = state / ".gitignore"
            original = research.read_text(encoding="utf-8")
            self.assertIn('research_data_owner: "pending"\n', original)
            self.assertTrue(
                ignore_path.read_text(encoding="utf-8").endswith(
                    "# Design DNA privacy safeguards\n"
                    "/user-validation.md\n"
                    "/evidence/research/\n"
                    "/*.[Rr][Ee][Ss][Tt][Rr][Ii][Cc][Tt][Ee][Dd].*\n"
                )
            )
            checked = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertTrue(
                any(
                    "privacy controls remain pending" in warning
                    for warning in json.loads(checked.stdout)["warnings"]
                )
            )
            self.assertTrue(
                any(
                    "Git tracking for restricted research" in warning
                    for warning in json.loads(checked.stdout)["warnings"]
                )
            )

            research.write_text(
                original.replace(
                    'retention_rule: "pending"\n',
                    "",
                    1,
                ),
                encoding="utf-8",
                newline="\n",
            )
            checked = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(checked.returncode, 1, checked.stdout + checked.stderr)
            self.assertTrue(
                any(
                    "retention_rule" in failure
                    for failure in json.loads(checked.stdout)["failures"]
                )
            )

            research.write_text(original, encoding="utf-8", newline="\n")
            ignore_path.write_text(
                ignore_path.read_text(encoding="utf-8")
                + "!/user-validation.md\n",
                encoding="utf-8",
                newline="\n",
            )
            checked = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(checked.returncode, 1, checked.stdout + checked.stderr)
            self.assertTrue(
                any(
                    "privacy-safeguard block" in failure
                    for failure in json.loads(checked.stdout)["failures"]
                )
            )

    def test_user_validation_rejects_quoted_empty_privacy_controls(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            created = run_script(
                INIT,
                "--project",
                str(project),
                "--record",
                "user-validation",
                "--json",
            )
            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
            research = project / ".design-dna" / "user-validation.md"
            text = research.read_text(encoding="utf-8")
            replacements = {
                'research_data_owner: "pending"': 'research_data_owner: ""',
                'collection_basis: "pending"': 'collection_basis: ""',
                'access_scope: "need-to-know project team"': 'access_scope: ""',
                (
                    'storage_location: "project-local restricted record; '
                    'do not commit"'
                ): 'storage_location: ""',
                'retention_rule: "pending"': 'retention_rule: ""',
                'deletion_owner: "pending"': 'deletion_owner: ""',
                'deletion_status: "pending"': 'deletion_status: "completed"',
            }
            for source, replacement in replacements.items():
                self.assertIn(source, text)
                text = text.replace(source, replacement, 1)
            research.write_text(text, encoding="utf-8", newline="\n")

            checked = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(checked.returncode, 1, checked.stdout + checked.stderr)
            self.assertTrue(
                any(
                    "has an empty value" in failure
                    for failure in json.loads(checked.stdout)["failures"]
                )
            )

    def test_user_validation_rejects_restricted_files_tracked_by_git(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            initialized = subprocess.run(
                ["git", "init", str(project)],
                text=True,
                encoding="utf-8",
                capture_output=True,
            )
            self.assertEqual(
                initialized.returncode,
                0,
                initialized.stdout + initialized.stderr,
            )
            created = run_script(
                INIT,
                "--project",
                str(project),
                "--record",
                "user-validation",
                "--json",
            )
            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
            state = project / ".design-dna"
            research_evidence = state / "evidence" / "research" / "participant.txt"
            research_evidence.parent.mkdir(parents=True, exist_ok=True)
            research_evidence.write_text("restricted observation\n", encoding="utf-8")
            restricted_root = state / "notes.restricted.txt"
            restricted_root.write_text("restricted note\n", encoding="utf-8")
            restricted_uppercase = state / "case.RESTRICTED.txt"
            restricted_uppercase.write_text(
                "case-variant restricted note\n",
                encoding="utf-8",
            )
            for relative in (
                ".design-dna/notes.restricted.txt",
                ".design-dna/case.RESTRICTED.txt",
            ):
                ignored = subprocess.run(
                    [
                        "git",
                        "-C",
                        str(project),
                        "check-ignore",
                        "--quiet",
                        "--",
                        relative,
                    ],
                    text=True,
                    encoding="utf-8",
                    capture_output=True,
                )
                self.assertEqual(
                    ignored.returncode,
                    0,
                    ignored.stdout + ignored.stderr,
                )
            tracked = subprocess.run(
                [
                    "git",
                    "-C",
                    str(project),
                    "add",
                    "-f",
                    "--",
                    ".design-dna/user-validation.md",
                    ".design-dna/evidence/research/participant.txt",
                    ".design-dna/notes.restricted.txt",
                    ".design-dna/case.RESTRICTED.txt",
                ],
                text=True,
                encoding="utf-8",
                capture_output=True,
            )
            self.assertEqual(
                tracked.returncode,
                0,
                tracked.stdout + tracked.stderr,
            )

            checked = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(checked.returncode, 1, checked.stdout + checked.stderr)
            failures = "\n".join(json.loads(checked.stdout)["failures"])
            self.assertIn("already tracked by Git", failures)
            self.assertIn(".design-dna/user-validation.md", failures)
            self.assertIn(
                ".design-dna/evidence/research/participant.txt",
                failures,
            )
            self.assertIn(".design-dna/notes.restricted.txt", failures)
            self.assertIn(".design-dna/case.RESTRICTED.txt", failures)

    def test_state_link_attack_is_rejected_when_links_are_available(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project, outside = root / "project", root / "outside"
            project.mkdir()
            outside.mkdir()
            link = project / ".design-dna"
            if not make_directory_link(link, outside):
                self.skipTest("directory symlink/junction unavailable")
            try:
                result = run_script(INIT, "--project", str(project), "--json")
                self.assertEqual(result.returncode, 2)
                self.assertEqual(list(outside.iterdir()), [])
                self.assertEqual(json.loads(result.stderr)["error"]["code"], "reparse-point-refused")
            finally:
                if link.exists():
                    os.rmdir(link)

    def test_assets_manifest_validates_complete_nested_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            created = run_script(
                INIT,
                "--project",
                str(project),
                "--record",
                "assets",
                "--json",
            )
            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
            asset_path = project / ".design-dna" / "assets.yml"
            initialized = asset_path.read_text(encoding="utf-8")
            self.assertIn("assets: []\n", initialized)
            self.assertNotIn("ASSET-001", initialized)
            source_asset = project / "assets" / "owner-supplied-hero.jpg"
            source_asset.parent.mkdir()
            source_asset.write_bytes(b"owner supplied hero fixture")
            source_digest = hashlib.sha256(
                source_asset.read_bytes()
            ).hexdigest()
            original = f"""schema_version: 2
created_with: "design-dna 2.2.0"
classification: "internal"
assets:
  - id: "ASSET-001"
    asset_type: "image"
    usage_locations:
      - "homepage"
    content_job: "Establish the real service environment."
    publication_status: "internal-only"
    source_url: ""
    source_path: "assets/owner-supplied-hero.jpg"
    source_sha256: "{source_digest}"
    creator: "Accountable asset owner"
    origin: "owner-supplied"
    obtained_date: "2026-07-28"
    license_or_terms: ""
    attribution_required: false
    attribution_text: ""
    modification_limits: ""
    modifications: "Responsive crops only."
    factual_status: "pending"
    depicts_or_claim: "Recorded service environment; public truth review pending."
    privacy_review: "pending"
    privacy_review_owner: ""
    privacy_review_date: ""
    privacy_review_reason: ""
    owner_approval: "pending"
    owner_approval_owner: ""
    owner_approval_date: ""
    owner_approval_reason: ""
    concept_disclosure:
      decision: "pending"
      reason: ""
      text: ""
    migration_review:
      required: false
      source_schema_version: "2"
      reason: ""
      unresolved_fields: []
    generated:
      used: false
      authorization_basis: ""
      tool_or_model: ""
      prompt_or_digest: ""
      generated_at: ""
      source_inputs: []
      rejected_outputs: []
      contact_sheet_path: ""
      contact_sheet_sha256: ""
      artifact_inspection: ""
      responsive_crop_evidence: []
    generated_media_provenance:
      applicability: "pending"
      jurisdiction: ""
      roles: []
      transformation_chain: []
      credential_detected: "pending"
      credential_validated: "pending"
      credential_preserved: "pending"
      visible_disclosure_basis: ""
      visible_disclosure_text: ""
      legal_review_status: "pending"
      legal_review_owner: ""
      legal_review_date: ""
      legal_review_reason: ""
    art_direction:
      subject: "Real service environment"
      crop_or_safe_zone: "Keep the service subject visible."
      lighting_palette_perspective: "Natural owner-approved capture."
      set_consistency_notes: "Use only with the approved documentary set."
    delivery:
      source_dimensions: "2400 x 1600"
      output_dimensions:
        - "1200 x 800"
      formats:
        - "webp"
      responsive_behavior: "Use focal-point crops without hiding the subject."
      intrinsic_dimensions_reserved: true
    accessibility:
      treatment: "informative"
      alt_text: "The recorded service environment."
      caption_or_transcript: ""
    replacement:
      status: "not-needed"
      owner: ""
      due_date: ""
"""
            asset_path.write_text(original, encoding="utf-8", newline="\n")
            self.assertIn('    privacy_review: "pending"\n', original)
            self.assertIn('    privacy_review_owner: ""\n', original)
            self.assertIn(
                '    generated_media_provenance:\n'
                '      applicability: "pending"\n',
                original,
            )
            self.assertIn(
                '      credential_detected: "pending"\n',
                original,
            )
            self.assertIn(
                '      legal_review_status: "pending"\n',
                original,
            )
            valid = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(valid.returncode, 0, valid.stdout + valid.stderr)

            art_start = original.index("    art_direction:\n")
            art_end = original.index("    delivery:\n", art_start)
            without_art_direction = original[:art_start] + original[art_end:]
            asset_path.write_text(
                without_art_direction,
                encoding="utf-8",
                newline="\n",
            )
            optional_art_direction = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(
                optional_art_direction.returncode,
                0,
                optional_art_direction.stdout + optional_art_direction.stderr,
            )

            project_defined_art_direction = (
                original[:art_start]
                + "    art_direction:\n"
                + '      material_relationship: "Let the approved steel surface remain visibly cool beside the warm product."\n'
                + '      removal_condition: "Remove the treatment if it hides the service action."\n'
                + original[art_end:]
            )
            asset_path.write_text(
                project_defined_art_direction,
                encoding="utf-8",
                newline="\n",
            )
            extensible_art_direction = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(
                extensible_art_direction.returncode,
                0,
                extensible_art_direction.stdout + extensible_art_direction.stderr,
            )
            asset_path.write_text(original, encoding="utf-8", newline="\n")

            not_ready = run_script(
                INIT,
                "--project",
                str(project),
                "--check-ready",
                "--json",
            )
            self.assertEqual(
                not_ready.returncode,
                1,
                not_ready.stdout + not_ready.stderr,
            )
            self.assertTrue(
                any(
                    "owner_approval" in failure
                    for failure in json.loads(not_ready.stdout)["failures"]
                )
            )

            exact_before_merge = asset_path.read_bytes()
            merged = run_script(
                INIT,
                "--project",
                str(project),
                "--record",
                "assets",
                "--json",
            )
            self.assertEqual(
                merged.returncode,
                0,
                merged.stdout + merged.stderr,
            )
            self.assertEqual(exact_before_merge, asset_path.read_bytes())

            source_asset.write_bytes(b"tampered owner supplied hero fixture")
            tampered_source = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(
                tampered_source.returncode,
                1,
                tampered_source.stdout + tampered_source.stderr,
            )
            self.assertTrue(
                any(
                    "source_path/source_sha256" in failure
                    for failure in json.loads(
                        tampered_source.stdout
                    )["failures"]
                )
            )
            source_asset.write_bytes(b"owner supplied hero fixture")

            mutations = {
                "duplicate nested key": original.replace(
                    "      used: false\n",
                    "      used: false\n      used: false\n",
                    1,
                ),
                "unknown nested key": original.replace(
                    "      tool_or_model: \"\"\n",
                    "      tool_or_model: \"\"\n      mystery: \"value\"\n",
                    1,
                ),
                "missing nested key": original.replace(
                    "      tool_or_model: \"\"\n",
                    "",
                    1,
                ),
                "wrong scalar type": original.replace(
                    "    attribution_required: false\n",
                    "    attribution_required: \"false\"\n",
                    1,
                ),
                "wrong nesting": original.replace(
                    "    generated:\n",
                    "    generated: []\n",
                    1,
                ),
                "unknown asset field": original.replace(
                    '    content_job: "Establish the real service environment."\n',
                    '    content_job: "Establish the real service environment."\n'
                    '    mystery: "value"\n',
                    1,
                ),
                "real row without content evidence": original.replace(
                    '    content_job: "Establish the real service environment."\n',
                    '    content_job: ""\n',
                    1,
                ),
                "real row without source evidence": original.replace(
                    '    source_path: "assets/owner-supplied-hero.jpg"\n',
                    '    source_path: ""\n',
                    1,
                ),
                "malformed source URL is controlled": original.replace(
                    '    source_url: ""\n',
                    '    source_url: "https://[invalid"\n',
                    1,
                ),
                "source URL with invalid port": original.replace(
                    '    source_url: ""\n',
                    '    source_url: "https://example.com:not-a-port/media"\n',
                    1,
                ),
                "source URL with backslash": original.replace(
                    '    source_url: ""\n',
                    '    source_url: "https://example.com\\\\media"\n',
                    1,
                ),
                "real row without usage location": original.replace(
                    '    usage_locations:\n      - "homepage"\n',
                    "    usage_locations: []\n",
                    1,
                ),
                "unsupported privacy status": original.replace(
                    '    privacy_review: "pending"\n',
                    '    privacy_review: "skipped"\n',
                    1,
                ),
                "completed privacy review without attribution": original.replace(
                    '    privacy_review: "pending"\n',
                    '    privacy_review: "not-required"\n',
                    1,
                ),
                "invalid privacy review date": original.replace(
                    '    privacy_review_date: ""\n',
                    '    privacy_review_date: "next Tuesday"\n',
                    1,
                ),
                "completed owner approval without attribution": original.replace(
                    '    owner_approval: "pending"\n',
                    '    owner_approval: "approved"\n',
                    1,
                ),
                "generated media without source inputs": (
                    original.replace(
                        '      used: false\n',
                        '      used: true\n',
                        1,
                    ).replace(
                        '      tool_or_model: ""\n',
                        '      tool_or_model: "Recorded service"\n',
                        1,
                    )
                ),
                "generated origin without generation record": original.replace(
                    '    origin: "owner-supplied"\n',
                    '    origin: "generated"\n',
                    1,
                ),
                "attribution required without text": original.replace(
                    "    attribution_required: false\n",
                    "    attribution_required: true\n",
                    1,
                ),
                "licensed origin without terms": original.replace(
                    '    origin: "owner-supplied"\n',
                    '    origin: "licensed"\n',
                    1,
                ),
                "informative asset without alt text": original.replace(
                    '      alt_text: "The recorded service environment."\n',
                    '      alt_text: ""\n',
                    1,
                ),
                "replacement required without owner and due date": (
                    original.replace(
                        '      status: "not-needed"\n',
                        '      status: "required"\n',
                        1,
                    )
                ),
                "unsupported generated-media applicability": original.replace(
                    '      applicability: "pending"\n',
                    '      applicability: "exempt"\n',
                    1,
                ),
                "applicable generated media without context": original.replace(
                    '      applicability: "pending"\n',
                    '      applicability: "applicable"\n',
                    1,
                ),
                "unsupported generated-media role": original.replace(
                    "      roles: []\n",
                    '      roles:\n        - "consumer"\n',
                    1,
                ),
                "duplicate generated-media role": original.replace(
                    "      roles: []\n",
                    '      roles:\n'
                    '        - "publisher"\n'
                    '        - "publisher"\n',
                    1,
                ),
                "empty transformation step": original.replace(
                    "      transformation_chain: []\n",
                    '      transformation_chain:\n        - ""\n',
                    1,
                ),
                "unsupported credential detected state": original.replace(
                    '      credential_detected: "pending"\n',
                    '      credential_detected: "present"\n',
                    1,
                ),
                "unsupported credential validated state": original.replace(
                    '      credential_validated: "pending"\n',
                    '      credential_validated: "trusted"\n',
                    1,
                ),
                "unsupported credential preserved state": original.replace(
                    '      credential_preserved: "pending"\n',
                    '      credential_preserved: "maybe"\n',
                    1,
                ),
                "validated credential without detected credential": (
                    original.replace(
                        '      credential_validated: "pending"\n',
                        '      credential_validated: "validated"\n',
                        1,
                    )
                ),
                "preserved credential without validated credential": (
                    original.replace(
                        '      credential_preserved: "pending"\n',
                        '      credential_preserved: "preserved"\n',
                        1,
                    )
                ),
                "disclosure text without basis": original.replace(
                    '      visible_disclosure_text: ""\n',
                    '      visible_disclosure_text: "Created with generative AI."\n',
                    1,
                ),
                "unsupported generated-media legal status": original.replace(
                    '      legal_review_status: "pending"\n',
                    '      legal_review_status: "waived"\n',
                    1,
                ),
                "completed generated-media legal review without attribution": (
                    original.replace(
                        '      legal_review_status: "pending"\n',
                        '      legal_review_status: "approved"\n',
                        1,
                    )
                ),
                "invalid generated-media legal review date": original.replace(
                    '      legal_review_date: ""\n',
                    '      legal_review_date: "tomorrow"\n',
                    1,
                ),
                "unknown top-level field": original + "unexpected: true\n",
                "duplicate top-level key": original + "assets: []\n",
            }
            for label, mutated in mutations.items():
                with self.subTest(label=label):
                    asset_path.write_text(mutated, encoding="utf-8", newline="\n")
                    checked = run_script(
                        INIT,
                        "--project",
                        str(project),
                        "--check-state",
                        "--json",
                    )
                    self.assertEqual(
                        checked.returncode,
                        1,
                        checked.stdout + checked.stderr,
                    )
                    failures = json.loads(checked.stdout)["failures"]
                    self.assertTrue(
                        any("Invalid assets.yml" in item for item in failures),
                        failures,
                    )

            expanded = original.replace(
                "    usage_locations:\n"
                '      - "homepage"\n',
                "    usage_locations:\n"
                '      - "homepage"\n'
                '      - "menu"\n',
                1,
            )
            asset_path.write_text(expanded, encoding="utf-8", newline="\n")
            checked = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)

            review_dir = project / "evidence" / "generated-media"
            review_dir.mkdir(parents=True)
            contact_sheet = review_dir / "contact-sheet.html"
            contact_sheet.write_text(
                "<!doctype html><title>Generated media review</title>",
                encoding="utf-8",
            )
            contact_digest = hashlib.sha256(
                contact_sheet.read_bytes()
            ).hexdigest()
            crop = review_dir / "homepage-375.png"
            crop.write_bytes(b"\x89PNG\r\n\x1a\ngenerated-crop")
            crop_digest = hashlib.sha256(crop.read_bytes()).hexdigest()
            reviewed_generated_media = (
                original.replace(
                    '      used: false\n',
                    '      used: true\n',
                    1,
                )
                .replace(
                    '      authorization_basis: ""\n',
                    '      authorization_basis: "Owner approved this fictional concept use."\n',
                    1,
                )
                .replace(
                    '      tool_or_model: ""\n',
                    '      tool_or_model: "Owner-recorded generation service"\n',
                    1,
                )
                .replace(
                    '      prompt_or_digest: ""\n',
                    '      prompt_or_digest: "sha256:'
                    + ("1" * 64)
                    + '"\n',
                    1,
                )
                .replace(
                    '      generated_at: ""\n',
                    '      generated_at: "2026-07-28T12:00:00+00:00"\n',
                    1,
                )
                .replace(
                    "      source_inputs: []\n",
                    '      source_inputs:\n'
                    '        - "text:Owner-approved source direction"\n',
                    1,
                )
                .replace(
                    "      rejected_outputs: []\n",
                    '      rejected_outputs:\n'
                    '        - "Rejected output 01: geometry artifact"\n',
                    1,
                )
                .replace(
                    '      contact_sheet_path: ""\n',
                    '      contact_sheet_path: "evidence/generated-media/contact-sheet.html"\n',
                    1,
                )
                .replace(
                    '      contact_sheet_sha256: ""\n',
                    f'      contact_sheet_sha256: "{contact_digest}"\n',
                    1,
                )
                .replace(
                    '      artifact_inspection: ""\n',
                    '      artifact_inspection: "Inspected anatomy, geometry, text, provenance, and documentary-proof risk."\n',
                    1,
                )
                .replace(
                    "      responsive_crop_evidence: []\n",
                    '      responsive_crop_evidence:\n'
                    f'        - "evidence/generated-media/homepage-375.png plus sha256:{crop_digest}"\n',
                    1,
                )
                .replace(
                    '      decision: "pending"\n',
                    '      decision: "required"\n',
                    1,
                )
                .replace(
                    '      reason: ""\n',
                    '      reason: "The realistic fictional scene could be mistaken for documentary proof."\n',
                    1,
                )
                .replace(
                    '      text: ""\n',
                    '      text: "Created with generative AI."\n',
                    1,
                )
                .replace(
                    '      applicability: "pending"\n',
                    '      applicability: "applicable"\n',
                    1,
                )
                .replace(
                    '      jurisdiction: ""\n',
                    '      jurisdiction: "EU"\n',
                    1,
                )
                .replace(
                    "      roles: []\n",
                    '      roles:\n'
                    '        - "provider"\n'
                    '        - "deployer"\n'
                    '        - "publisher"\n',
                    1,
                )
                .replace(
                    "      transformation_chain: []\n",
                    '      transformation_chain:\n'
                    '        - "ASSET-001 source capture"\n'
                    '        - "Owner-approved crop and export"\n',
                    1,
                )
                .replace(
                    '      credential_detected: "pending"\n',
                    '      credential_detected: "detected"\n',
                    1,
                )
                .replace(
                    '      credential_validated: "pending"\n',
                    '      credential_validated: "validated"\n',
                    1,
                )
                .replace(
                    '      credential_preserved: "pending"\n',
                    '      credential_preserved: "preserved"\n',
                    1,
                )
                .replace(
                    '      visible_disclosure_basis: ""\n',
                    '      visible_disclosure_basis: "Applicable owner policy"\n',
                    1,
                )
                .replace(
                    '      visible_disclosure_text: ""\n',
                    '      visible_disclosure_text: "Created with generative AI."\n',
                    1,
                )
                .replace(
                    '      legal_review_status: "pending"\n',
                    '      legal_review_status: "approved"\n',
                    1,
                )
                .replace(
                    '      legal_review_owner: ""\n',
                    '      legal_review_owner: "Qualified reviewer"\n',
                    1,
                )
                .replace(
                    '      legal_review_date: ""\n',
                    '      legal_review_date: "2026-07-28"\n',
                    1,
                )
                .replace(
                    '      legal_review_reason: ""\n',
                    '      legal_review_reason: "Qualified review completed for the intended public use."\n',
                    1,
                )
            )
            asset_path.write_text(
                reviewed_generated_media,
                encoding="utf-8",
                newline="\n",
            )
            checked = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)

            generated_evidence_mutations = {
                "missing generation authorization": (
                    reviewed_generated_media.replace(
                        '      authorization_basis: "Owner approved this fictional concept use."\n',
                        '      authorization_basis: ""\n',
                        1,
                    )
                ),
                "placeholder prompt evidence": (
                    reviewed_generated_media.replace(
                        '      prompt_or_digest: "sha256:'
                        + ("1" * 64)
                        + '"\n',
                        '      prompt_or_digest: "pending"\n',
                        1,
                    )
                ),
                "raw prompt is not a digest binding": (
                    reviewed_generated_media.replace(
                        '      prompt_or_digest: "sha256:'
                        + ("1" * 64)
                        + '"\n',
                        '      prompt_or_digest: "A realistic workshop scene"\n',
                        1,
                    )
                ),
                "uppercase prompt digest is noncanonical": (
                    reviewed_generated_media.replace(
                        '      prompt_or_digest: "sha256:'
                        + ("1" * 64)
                        + '"\n',
                        '      prompt_or_digest: "sha256:'
                        + ("A" * 64)
                        + '"\n',
                        1,
                    )
                ),
                "placeholder disclosure reason": (
                    reviewed_generated_media.replace(
                        '      reason: "The realistic fictional scene could be mistaken for documentary proof."\n',
                        '      reason: "pending"\n',
                        1,
                    )
                ),
                "invalid credential result without detected credential": (
                    reviewed_generated_media.replace(
                        '      credential_detected: "detected"\n',
                        '      credential_detected: "unknown"\n',
                        1,
                    ).replace(
                        '      credential_validated: "validated"\n',
                        '      credential_validated: "invalid"\n',
                        1,
                    )
                ),
                "detected credential marked validation not applicable": (
                    reviewed_generated_media.replace(
                        '      credential_validated: "validated"\n',
                        '      credential_validated: "not-applicable"\n',
                        1,
                    ).replace(
                        '      credential_preserved: "preserved"\n',
                        '      credential_preserved: "not-applicable"\n',
                        1,
                    )
                ),
                "tampered contact sheet binding": (
                    reviewed_generated_media.replace(
                        f'      contact_sheet_sha256: "{contact_digest}"\n',
                        f'      contact_sheet_sha256: "{"0" * 64}"\n',
                        1,
                    )
                ),
                "tampered responsive crop binding": (
                    reviewed_generated_media.replace(
                        f'        - "evidence/generated-media/homepage-375.png plus sha256:{crop_digest}"\n',
                        '        - "evidence/generated-media/homepage-375.png plus sha256:'
                        + ("0" * 64)
                        + '"\n',
                        1,
                    )
                ),
            }
            for label, mutated in generated_evidence_mutations.items():
                with self.subTest(label=label):
                    asset_path.write_text(
                        mutated,
                        encoding="utf-8",
                        newline="\n",
                    )
                    rejected = run_script(
                        INIT,
                        "--project",
                        str(project),
                        "--check-state",
                        "--json",
                    )
                    self.assertEqual(
                        rejected.returncode,
                        1,
                        rejected.stdout + rejected.stderr,
                    )

            lean_internal_generated_media = (
                reviewed_generated_media.replace(
                    '      source_inputs:\n'
                    '        - "text:Owner-approved source direction"\n',
                    "      source_inputs: []\n",
                    1,
                )
                .replace(
                    '      rejected_outputs:\n'
                    '        - "Rejected output 01: geometry artifact"\n',
                    "      rejected_outputs: []\n",
                    1,
                )
                .replace(
                    '      contact_sheet_path: "evidence/generated-media/contact-sheet.html"\n',
                    '      contact_sheet_path: ""\n',
                    1,
                )
                .replace(
                    f'      contact_sheet_sha256: "{contact_digest}"\n',
                    '      contact_sheet_sha256: ""\n',
                    1,
                )
                .replace(
                    '      responsive_crop_evidence:\n'
                    f'        - "evidence/generated-media/homepage-375.png plus sha256:{crop_digest}"\n',
                    "      responsive_crop_evidence: []\n",
                    1,
                )
            )
            asset_path.write_text(
                lean_internal_generated_media,
                encoding="utf-8",
                newline="\n",
            )
            checked = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)

            lean_public_generated_media = lean_internal_generated_media.replace(
                '    publication_status: "internal-only"\n',
                '    publication_status: "public"\n',
                1,
            )
            asset_path.write_text(
                lean_public_generated_media,
                encoding="utf-8",
                newline="\n",
            )
            blocked = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(blocked.returncode, 1, blocked.stdout + blocked.stderr)
            self.assertTrue(
                any(
                    "contact_sheet" in failure
                    or "responsive_crop_evidence" in failure
                    for failure in json.loads(blocked.stdout)["failures"]
                )
            )

            public_generated_media = reviewed_generated_media.replace(
                '    publication_status: "internal-only"\n',
                '    publication_status: "public"\n',
                1,
            )
            asset_path.write_text(
                public_generated_media,
                encoding="utf-8",
                newline="\n",
            )
            checked = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)

            for legal_status in ("changes-required", "rejected"):
                with self.subTest(
                    label=f"public generated legal {legal_status}"
                ):
                    asset_path.write_text(
                        public_generated_media.replace(
                            '      legal_review_status: "approved"\n',
                            f'      legal_review_status: "{legal_status}"\n',
                            1,
                        ),
                        encoding="utf-8",
                        newline="\n",
                    )
                    blocked = run_script(
                        INIT,
                        "--project",
                        str(project),
                        "--check-state",
                        "--json",
                    )
                    self.assertEqual(
                        blocked.returncode,
                        1,
                        blocked.stdout + blocked.stderr,
                    )
                    self.assertTrue(
                        any(
                            "legal_review_status" in failure
                            for failure in json.loads(
                                blocked.stdout
                            )["failures"]
                        )
                    )

            ready_public_generated_media = (
                public_generated_media.replace(
                    '    license_or_terms: ""\n',
                    '    license_or_terms: "Recorded generated-media usage terms permit this concept use."\n',
                    1,
                )
                .replace(
                    '    factual_status: "pending"\n',
                    '    factual_status: "concept"\n',
                    1,
                )
                .replace(
                    '    privacy_review: "pending"\n',
                    '    privacy_review: "not-required"\n',
                    1,
                )
                .replace(
                    '    privacy_review_owner: ""\n',
                    '    privacy_review_owner: "Accountable privacy reviewer"\n',
                    1,
                )
                .replace(
                    '    privacy_review_date: ""\n',
                    '    privacy_review_date: "2026-07-28"\n',
                    1,
                )
                .replace(
                    '    privacy_review_reason: ""\n',
                    '    privacy_review_reason: "The concept image contains no identifiable person or private data."\n',
                    1,
                )
                .replace(
                    '    owner_approval: "pending"\n',
                    '    owner_approval: "approved"\n',
                    1,
                )
                .replace(
                    '    owner_approval_owner: ""\n',
                    '    owner_approval_owner: "Accountable project owner"\n',
                    1,
                )
                .replace(
                    '    owner_approval_date: ""\n',
                    '    owner_approval_date: "2026-07-28"\n',
                    1,
                )
                .replace(
                    '    owner_approval_reason: ""\n',
                    '    owner_approval_reason: "Approved for the recorded public concept use."\n',
                    1,
                )
            )
            asset_path.write_text(
                ready_public_generated_media,
                encoding="utf-8",
                newline="\n",
            )
            ready = run_script(
                INIT,
                "--project",
                str(project),
                "--check-ready",
                "--json",
            )
            self.assertEqual(ready.returncode, 0, ready.stdout + ready.stderr)

            missing_image_delivery = ready_public_generated_media.replace(
                '      formats:\n        - "webp"\n',
                "      formats: []\n",
                1,
            )
            asset_path.write_text(
                missing_image_delivery,
                encoding="utf-8",
                newline="\n",
            )
            delivery_blocked = run_script(
                INIT,
                "--project",
                str(project),
                "--check-ready",
                "--json",
            )
            self.assertEqual(
                delivery_blocked.returncode,
                1,
                delivery_blocked.stdout + delivery_blocked.stderr,
            )
            self.assertTrue(
                any(
                    "image readiness requires formats" in failure
                    for failure in json.loads(
                        delivery_blocked.stdout
                    )["failures"]
                )
            )

            public_owner_asset_without_rights = (
                original.replace(
                    '    publication_status: "internal-only"\n',
                    '    publication_status: "public"\n',
                    1,
                )
                .replace(
                    '    factual_status: "pending"\n',
                    '    factual_status: "approved"\n',
                    1,
                )
                .replace(
                    '    privacy_review: "pending"\n',
                    '    privacy_review: "not-required"\n',
                    1,
                )
                .replace(
                    '    privacy_review_owner: ""\n',
                    '    privacy_review_owner: "Privacy reviewer"\n',
                    1,
                )
                .replace(
                    '    privacy_review_date: ""\n',
                    '    privacy_review_date: "2026-07-28"\n',
                    1,
                )
                .replace(
                    '    privacy_review_reason: ""\n',
                    '    privacy_review_reason: "No identifiable person or private data."\n',
                    1,
                )
                .replace(
                    '    owner_approval: "pending"\n',
                    '    owner_approval: "approved"\n',
                    1,
                )
                .replace(
                    '    owner_approval_owner: ""\n',
                    '    owner_approval_owner: "Asset owner"\n',
                    1,
                )
                .replace(
                    '    owner_approval_date: ""\n',
                    '    owner_approval_date: "2026-07-28"\n',
                    1,
                )
                .replace(
                    '    owner_approval_reason: ""\n',
                    '    owner_approval_reason: "Approved for public use."\n',
                    1,
                )
            )
            asset_path.write_text(
                public_owner_asset_without_rights,
                encoding="utf-8",
                newline="\n",
            )
            rights_blocked = run_script(
                INIT,
                "--project",
                str(project),
                "--check-ready",
                "--json",
            )
            self.assertEqual(
                rights_blocked.returncode,
                1,
                rights_blocked.stdout + rights_blocked.stderr,
            )
            self.assertTrue(
                any(
                    "planned/public use requires recorded rights" in failure
                    for failure in json.loads(
                        rights_blocked.stdout
                    )["failures"]
                )
            )
            asset_path.write_text(
                ready_public_generated_media,
                encoding="utf-8",
                newline="\n",
            )

            provenance_start = public_generated_media.index(
                "    generated_media_provenance:\n"
            )
            provenance_end = public_generated_media.index(
                "    art_direction:\n",
                provenance_start,
            )
            public_without_provenance = (
                public_generated_media[:provenance_start]
                + public_generated_media[provenance_end:]
            )
            asset_path.write_text(
                public_without_provenance,
                encoding="utf-8",
                newline="\n",
            )
            checked = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(checked.returncode, 1, checked.stdout + checked.stderr)
            self.assertTrue(
                any(
                    "requires generated_media_provenance" in failure
                    for failure in json.loads(checked.stdout)["failures"]
                )
            )

            conflicting_disclosure = (
                reviewed_generated_media.replace(
                    '      text: "Created with generative AI."\n',
                    '      text: "Synthetic concept image."\n',
                    1,
                )
            )
            asset_path.write_text(
                conflicting_disclosure,
                encoding="utf-8",
                newline="\n",
            )
            checked = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(checked.returncode, 1, checked.stdout + checked.stderr)
            self.assertTrue(
                any(
                    "must match" in failure
                    for failure in json.loads(checked.stdout)["failures"]
                )
            )

            attributed_review = (
                original.replace(
                    '    privacy_review: "pending"\n',
                    '    privacy_review: "not-required"\n',
                    1,
                )
                .replace(
                    '    privacy_review_owner: ""\n',
                    '    privacy_review_owner: "Motty"\n',
                    1,
                )
                .replace(
                    '    privacy_review_date: ""\n',
                    '    privacy_review_date: "2026-07-28"\n',
                    1,
                )
                .replace(
                    '    privacy_review_reason: ""\n',
                    '    privacy_review_reason: "Abstract artwork depicts no person or private data."\n',
                    1,
                )
            )
            asset_path.write_text(
                attributed_review,
                encoding="utf-8",
                newline="\n",
            )
            checked = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)

            generated_media_block = (
                "    generated_media_provenance:\n"
                '      applicability: "pending"\n'
                '      jurisdiction: ""\n'
                "      roles: []\n"
                "      transformation_chain: []\n"
                '      credential_detected: "pending"\n'
                '      credential_validated: "pending"\n'
                '      credential_preserved: "pending"\n'
                '      visible_disclosure_basis: ""\n'
                '      visible_disclosure_text: ""\n'
                '      legal_review_status: "pending"\n'
                '      legal_review_owner: ""\n'
                '      legal_review_date: ""\n'
                '      legal_review_reason: ""\n'
            )
            legacy_without_generated_media = original.replace(
                generated_media_block,
                "",
                1,
            )
            self.assertNotIn(
                "generated_media_provenance",
                legacy_without_generated_media,
            )
            asset_path.write_text(
                legacy_without_generated_media,
                encoding="utf-8",
                newline="\n",
            )
            checked = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)

            legacy_without_review_attribution = original
            for line in (
                '    privacy_review_owner: ""\n',
                '    privacy_review_date: ""\n',
                '    privacy_review_reason: ""\n',
            ):
                legacy_without_review_attribution = (
                    legacy_without_review_attribution.replace(line, "", 1)
                )
            asset_path.write_text(
                legacy_without_review_attribution,
                encoding="utf-8",
                newline="\n",
            )
            checked = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)

    def test_printed_asset_example_is_complete_valid_and_release_blocked(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            printed = run_script(INIT, "--print-asset-example")
            self.assertEqual(
                printed.returncode,
                0,
                printed.stdout + printed.stderr,
            )
            self.assertEqual("", printed.stderr)
            self.assertNotIn("__DESIGN_DNA_VERSION__", printed.stdout)
            self.assertIn('    factual_status: "placeholder"\n', printed.stdout)
            self.assertIn('    privacy_review: "pending"\n', printed.stdout)
            self.assertIn('    owner_approval: "pending"\n', printed.stdout)

            created = run_script(
                INIT,
                "--project",
                str(project),
                "--record",
                "assets",
                "--json",
            )
            self.assertEqual(
                created.returncode,
                0,
                created.stdout + created.stderr,
            )
            asset_path = project / ".design-dna" / "assets.yml"
            asset_path.write_text(
                printed.stdout,
                encoding="utf-8",
                newline="\n",
            )
            checked = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(
                checked.returncode,
                0,
                checked.stdout + checked.stderr,
            )

    def test_schema_one_asset_manifest_migrates_without_inventing_evidence(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            created = run_script(
                INIT,
                "--project",
                str(project),
                "--record",
                "assets",
            )
            self.assertEqual(
                created.returncode,
                0,
                created.stdout + created.stderr,
            )
            printed = run_script(INIT, "--print-asset-example")
            self.assertEqual(printed.returncode, 0, printed.stderr)
            legacy = printed.stdout.replace(
                "schema_version: 2\n",
                "schema_version: 1\n",
                1,
            )
            for line in (
                '    asset_type: "image"\n',
                '    publication_status: "planned-public"\n',
                '    source_sha256: ""\n',
                '      authorization_basis: ""\n',
                '      prompt_or_digest: ""\n',
                '      generated_at: ""\n',
                "      rejected_outputs: []\n",
                '      contact_sheet_path: ""\n',
                '      contact_sheet_sha256: ""\n',
                '      artifact_inspection: ""\n',
                "      responsive_crop_evidence: []\n",
            ):
                legacy = legacy.replace(line, "", 1)
            for block in (
                (
                    "    concept_disclosure:\n"
                    '      decision: "pending"\n'
                    '      reason: ""\n'
                    '      text: ""\n'
                ),
                (
                    "    migration_review:\n"
                    "      required: false\n"
                    '      source_schema_version: "2"\n'
                    '      reason: ""\n'
                    "      unresolved_fields: []\n"
                ),
            ):
                legacy = legacy.replace(block, "", 1)
            asset_path = project / ".design-dna" / "assets.yml"
            generated_start = legacy.index("    generated:\n")
            generated_end = legacy.index(
                "    art_direction:\n",
                generated_start,
            )
            malformed_legacy = (
                legacy[:generated_start]
                + '    generated: "not-a-mapping"\n'
                + legacy[generated_end:]
            )
            asset_path.write_text(
                malformed_legacy,
                encoding="utf-8",
                newline="\n",
            )
            malformed_before = asset_path.read_bytes()
            malformed_migration = run_script(
                INIT,
                "--project",
                str(project),
                "--migrate",
                "--json",
            )
            self.assertEqual(
                malformed_migration.returncode,
                2,
                malformed_migration.stdout + malformed_migration.stderr,
            )
            self.assertEqual(
                json.loads(malformed_migration.stderr)["error"]["code"],
                "asset-migration-invalid",
            )
            self.assertEqual(malformed_before, asset_path.read_bytes())

            source_hash = hashlib.sha256(
                legacy.encode("utf-8")
            ).hexdigest()
            asset_path.write_text(
                legacy,
                encoding="utf-8",
                newline="\n",
            )
            before = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(before.returncode, 1)
            migrated = run_script(
                INIT,
                "--project",
                str(project),
                "--migrate",
                "--json",
            )
            self.assertEqual(
                migrated.returncode,
                0,
                migrated.stdout + migrated.stderr,
            )
            current = asset_path.read_text(encoding="utf-8")
            self.assertIn("schema_version: 2", current)
            self.assertIn("migration_review:", current)
            self.assertIn("required: true", current)
            checked = run_script(
                INIT,
                "--project",
                str(project),
                "--check-state",
                "--json",
            )
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            readiness = run_script(
                INIT,
                "--project",
                str(project),
                "--check-ready",
                "--json",
            )
            self.assertEqual(readiness.returncode, 1)
            self.assertIn("migration review", readiness.stdout)
            report = json.loads(
                (
                    project
                    / ".design-dna"
                    / "migration-report.json"
                ).read_text(encoding="utf-8")
            )
            migration = report["asset_manifest_migrations"][0]
            self.assertEqual(
                migration["source_manifest_sha256"],
                source_hash,
            )
            self.assertEqual(migration["target_schema_version"], 2)
            self.assertEqual(
                migration["unresolved_asset_ids"],
                ["ASSET-001"],
            )

            second_legacy = legacy.replace(
                '  - id: "ASSET-001"\n',
                '  - id: "ASSET-002"\n',
                1,
            )
            self.assertNotEqual(second_legacy, legacy)
            second_source_hash = hashlib.sha256(
                second_legacy.encode("utf-8")
            ).hexdigest()
            asset_path.write_text(
                second_legacy,
                encoding="utf-8",
                newline="\n",
            )
            migrated_again = run_script(
                INIT,
                "--project",
                str(project),
                "--migrate",
                "--json",
            )
            self.assertEqual(
                migrated_again.returncode,
                0,
                migrated_again.stdout + migrated_again.stderr,
            )
            report_after_second_migration = json.loads(
                (
                    project
                    / ".design-dna"
                    / "migration-report.json"
                ).read_text(encoding="utf-8")
            )
            migrations = report_after_second_migration[
                "asset_manifest_migrations"
            ]
            self.assertEqual(len(migrations), 2)
            self.assertEqual(
                [item["source_manifest_sha256"] for item in migrations],
                [source_hash, second_source_hash],
            )
            self.assertEqual(
                migrations[0],
                migration,
                "A later migration must append rather than rewrite history.",
            )

    def test_missing_or_invalid_release_metadata_fails_before_state_check(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            copied = (
                root
                / "package"
                / "skills"
                / "design-dna"
                / "scripts"
                / "init_project_state.py"
            )
            copied.parent.mkdir(parents=True)
            shutil.copy2(INIT, copied)
            release_path = copied.parents[1] / "release.json"
            project = root / "project"
            project.mkdir()
            payloads = (
                ("missing", None),
                ("invalid-json", "{"),
                (
                    "invalid-shape",
                    json.dumps({
                        "package": "design-dna",
                        "version": "unknown",
                        "state_schema_version": 1,
                    }),
                ),
            )
            for label, release_text in payloads:
                with self.subTest(label=label):
                    if release_path.exists():
                        release_path.unlink()
                    if release_text is not None:
                        release_path.write_text(release_text, encoding="utf-8")
                    checked = run_script(
                        copied,
                        "--project",
                        str(project),
                        "--check-state",
                        "--json",
                    )
                    self.assertEqual(
                        checked.returncode,
                        2,
                        checked.stdout + checked.stderr,
                    )
                    error = json.loads(checked.stderr)["error"]
                    self.assertEqual(
                        error["code"],
                        "package-release-unavailable",
                    )
                    self.assertNotIn("unknown", checked.stdout)

    def test_state_error_after_move_restores_prior_and_quarantines_candidate(self) -> None:
        initializer = load_initializer()
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            initial = run_script(INIT, "--project", str(project), "--json")
            self.assertEqual(initial.returncode, 0, initial.stdout + initial.stderr)
            state_root = project / ".design-dna"
            (state_root / "direction.md").write_text(
                (state_root / "direction.md").read_text(encoding="utf-8")
                + "\nPrior owner content.\n",
                encoding="utf-8",
            )
            # A rollback must restore owner bytes exactly, including CRLF.
            (state_root / ".gitignore").write_bytes(
                (
                    "\r\n".join(initializer.STATE_PRIVACY_IGNORE_LINES)
                    + "\r\n"
                ).encode("utf-8")
            )
            before = file_snapshot(state_root)
            version = initializer.release_version(INIT.parents[1])
            with (
                patch.object(
                    initializer,
                    "validate_state_in_place",
                    return_value=([], []),
                ),
                patch.object(
                    initializer,
                    "validate_state",
                    return_value=(["forced post-install failure"], []),
                ),
            ):
                with self.assertRaises(initializer.StateError) as raised:
                    initializer.install_transaction(
                        project,
                        INIT.parents[1],
                        ("direction", "visual-review"),
                        force=False,
                        dry_run=False,
                        version=version,
                    )
            self.assertEqual(raised.exception.code, "installed-state-invalid")
            self.assertEqual(
                raised.exception.details["rollback"]["status"],
                "completed",
            )
            self.assertEqual(file_snapshot(state_root), before)
            failed = list(project.glob(".design-dna.failed-*"))
            self.assertEqual(len(failed), 1)
            self.assertTrue(failed[0].is_dir())
            self.assertEqual(list(project.glob(".design-dna.backup-*")), [])

    def test_final_rename_oserror_uses_same_rollback_path(self) -> None:
        initializer = load_initializer()
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            initial = run_script(INIT, "--project", str(project), "--json")
            self.assertEqual(initial.returncode, 0, initial.stdout + initial.stderr)
            state_root = project / ".design-dna"
            before = file_snapshot(state_root)
            version = initializer.release_version(INIT.parents[1])
            original_rename = Path.rename

            def fail_final_rename(source: Path, target: Path):
                if (
                    source.name == ".design-dna"
                    and source.parent.name.startswith(".design-dna-stage-")
                    and Path(target) == state_root
                ):
                    raise OSError("simulated final rename failure")
                return original_rename(source, target)

            with patch.object(Path, "rename", fail_final_rename):
                with self.assertRaises(initializer.StateError) as raised:
                    initializer.install_transaction(
                        project,
                        INIT.parents[1],
                        ("direction", "visual-review"),
                        force=False,
                        dry_run=False,
                        version=version,
                    )
            self.assertEqual(raised.exception.code, "initialization-failed")
            self.assertEqual(
                raised.exception.details["rollback"]["status"],
                "completed",
            )
            self.assertEqual(file_snapshot(state_root), before)
            self.assertEqual(len(list(project.glob(".design-dna.failed-*"))), 1)

    def test_rollback_failure_preserves_backup_and_candidate_structurally(self) -> None:
        initializer = load_initializer()
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            initial = run_script(INIT, "--project", str(project), "--json")
            self.assertEqual(initial.returncode, 0, initial.stdout + initial.stderr)
            state_root = project / ".design-dna"
            version = initializer.release_version(INIT.parents[1])
            original_rename = Path.rename

            def fail_backup_restore(source: Path, target: Path):
                if (
                    source.name.startswith(".design-dna.backup-")
                    and Path(target) == state_root
                ):
                    raise OSError("simulated backup restore failure")
                return original_rename(source, target)

            with (
                patch.object(
                    initializer,
                    "validate_state_in_place",
                    return_value=([], []),
                ),
                patch.object(
                    initializer,
                    "validate_state",
                    return_value=(["forced post-install failure"], []),
                ),
                patch.object(Path, "rename", fail_backup_restore),
            ):
                with self.assertRaises(initializer.StateError) as raised:
                    initializer.install_transaction(
                        project,
                        INIT.parents[1],
                        ("direction", "visual-review"),
                        force=False,
                        dry_run=False,
                        version=version,
                    )
            error = raised.exception
            self.assertEqual(error.code, "rollback-failed")
            self.assertEqual(error.details["primary"]["code"], "installed-state-invalid")
            self.assertEqual(error.details["rollback"]["status"], "incomplete")
            self.assertTrue(error.details["rollback"]["errors"])
            self.assertEqual(len(list(project.glob(".design-dna.backup-*"))), 1)
            self.assertEqual(len(list(project.glob(".design-dna.failed-*"))), 1)
            self.assertFalse(state_root.exists())
            json.dumps(initializer.error_record(error))

    def test_staging_cleanup_failure_never_masks_success_or_primary_error(self) -> None:
        initializer = load_initializer()
        version = initializer.release_version(INIT.parents[1])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            success_project = root / "success"
            success_project.mkdir()
            real_rmtree = shutil.rmtree

            def fail_stage_cleanup(path: Path, *args, **kwargs):
                if Path(path).name.startswith(".design-dna-stage-"):
                    raise OSError("simulated staging cleanup failure")
                return real_rmtree(path, *args, **kwargs)

            with patch.object(initializer.shutil, "rmtree", fail_stage_cleanup):
                actions = initializer.install_transaction(
                    success_project,
                    INIT.parents[1],
                    ("direction", "visual-review"),
                    force=False,
                    dry_run=False,
                    version=version,
                )
            self.assertTrue((success_project / ".design-dna").is_dir())
            self.assertTrue(
                any(
                    item["action"] == "staging-cleanup-preserved"
                    for item in actions
                )
            )
            for stage in success_project.glob(".design-dna-stage-*"):
                real_rmtree(stage)

            failure_project = root / "failure"
            failure_project.mkdir()
            initial = run_script(
                INIT,
                "--project",
                str(failure_project),
                "--json",
            )
            self.assertEqual(initial.returncode, 0, initial.stdout + initial.stderr)
            before = file_snapshot(failure_project / ".design-dna")
            with (
                patch.object(
                    initializer,
                    "validate_state_in_place",
                    return_value=([], []),
                ),
                patch.object(
                    initializer,
                    "validate_state",
                    return_value=(["forced post-install failure"], []),
                ),
                patch.object(initializer.shutil, "rmtree", fail_stage_cleanup),
            ):
                with self.assertRaises(initializer.StateError) as raised:
                    initializer.install_transaction(
                        failure_project,
                        INIT.parents[1],
                        ("direction", "visual-review"),
                        force=False,
                        dry_run=False,
                        version=version,
                    )
            self.assertEqual(raised.exception.code, "installed-state-invalid")
            self.assertEqual(
                raised.exception.details["cleanup"]["code"],
                "staging-cleanup-failed",
            )
            self.assertEqual(
                file_snapshot(failure_project / ".design-dna"),
                before,
            )
            for stage in failure_project.glob(".design-dna-stage-*"):
                real_rmtree(stage)


class ScannerTests(unittest.TestCase):
    def test_reports_candidates_and_honors_documented_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            source = project / "page.tsx"
            source.write_text(
                "<p>Trusted by thousands.</p>\n"
                "<p>Industry-leading service.</p>\n"
                "<p>Five-star rated care.</p>\n",
                encoding="utf-8",
            )
            first = run_script(SCAN, str(project), "--json")
            self.assertEqual(first.returncode, 0)
            findings = json.loads(first.stdout)["findings"]
            self.assertTrue(any(item["rule"] == "claim-needs-provenance" for item in findings))
            claim_finding = next(
                item
                for item in findings
                if item["rule"] == "claim-needs-provenance"
            )
            allowlist = project / "allow.json"
            allowlist.write_text(json.dumps({
                "schema_version": 1,
                "allow": [{
                    "rule": "claim-needs-provenance",
                    "path": "page.tsx",
                    "fingerprint": claim_finding["fingerprint"],
                    "reason": "Approved claim with documented evidence.",
                    "owner": "Content owner",
                    "expires": ACTIVE_EXPIRY,
                }],
            }), encoding="utf-8")
            second = run_script(SCAN, str(project), "--allowlist", str(allowlist), "--json")
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertEqual(
                sum(
                    item["rule"] == "claim-needs-provenance"
                    for item in json.loads(second.stdout)["findings"]
                ),
                2,
            )


class AuditGateTests(unittest.TestCase):
    @staticmethod
    def bind_owner_acceptance(
        payload: dict[str, object],
        plugin: Path,
    ) -> None:
        relative = "evidence/owner-acceptance.txt"
        evidence = plugin / relative
        evidence.parent.mkdir(parents=True, exist_ok=True)
        candidate_id = str(payload["build"]["identity"])
        evidence.write_text(
            (
                "status: accepted\n"
                "decision_owner_id: owner-alex-morgan\n"
                f"candidate_id: {candidate_id}\n"
                "reviewed_at: 2026-07-26T13:00:00Z\n"
            ),
            encoding="utf-8",
        )
        digest = hashlib.sha256(evidence.read_bytes()).hexdigest()
        payload["owner_disposition"] = {
            "status": "accepted",
            "claim_scope": "standard",
            "reviewer_relationship": "accountable-owner",
            "decision_owner_id": "owner-alex-morgan",
            "candidate_id": candidate_id,
            "reviewed_at": "2026-07-26T13:00:00Z",
            "rationale": (
                "The accountable owner accepted the exact rendered candidate."
            ),
            "evidence": [{"path": relative, "sha256": digest}],
        }
        evidence_paths = payload["evidence_paths"]
        if relative not in evidence_paths:
            evidence_paths.append(relative)

    def review_payload(
        self,
        *,
        lens: str,
        process_path: str,
        process_id: str,
        contexts: list[dict[str, object]],
        evidence_paths: list[str],
        independent: bool,
    ) -> dict[str, object]:
        rubric_evidence = contexts[0]["render_evidence"]
        rubric = {
            dimension: {
                "value": 2,
                "rationale": (
                    "The bound rendered context supports this dimension score."
                ),
                "evidence": [{
                    "path": rubric_evidence["path"],
                    "sha256": rubric_evidence["sha256"],
                }],
            }
            for dimension in (
                "project_specificity",
                "direction",
                "task_hierarchy",
                "contemporary_fit",
                "typography",
                "composition_density",
                "media_icons",
                "copy_ia",
                "distinctiveness_without_novelty_tax",
                "functional_completeness",
                "responsive_adaptation",
                "accessibility_baseline",
                "truth_provenance",
                "system_code",
                "performance_resilience",
                "residue",
                "cultural_representational_fit",
            )
        }
        return {
            "schema_version": 3,
            "case_id": "coffee-shop",
            "run_id": "suite:codex:coffee-shop:skill:1",
            "build": {
                "identity": "a" * 64,
                "host": "codex",
                "skill_version": "2.0.0",
                "content_sha256": "b" * 64,
                "captured_at": "2026-07-26T12:00:00Z",
                "producer_id": "builder-alpha",
            },
            "blinded_variant": "variant-b",
            "reviewer": {
                "id": (
                    "reviewer-perception"
                    if lens == "perception"
                    else "reviewer-implementation"
                ),
                "lens": lens,
                "independent": independent,
                "process": {
                    "id": process_id,
                    "method": (
                        "separate-person" if independent else "self-review"
                    ),
                    "performed_at": "2026-07-26T12:30:00Z",
                    "evidence_path": process_path,
                },
            },
            "contexts": contexts,
            "rubric": rubric,
            "critical_blockers": [],
            "findings": [],
            "motion_assessment": {
                "classification": "none",
                "rationale": "This static review fixture declares no motion.",
            },
            "evidence_paths": evidence_paths,
            "checks": {"tested": ["rendered review"], "unperformed": []},
            "conclusion": {
                "decision": "pass",
                "rationale": "All declared checks passed with bound evidence.",
            },
        }

    @staticmethod
    def environment() -> dict[str, object]:
        return {
            "input_modalities": ["keyboard", "pointer", "screen-reader"],
            "zoom_percent": 200,
            "text_scale_percent": 200,
            "reduced_motion": "reduce",
            "forced_colors": "active",
            "contrast_preference": "more",
            "theme": "high-contrast",
            "locale": "en-US",
            "direction": "ltr",
        }

    def test_png_decoder_and_perception_release_evidence(self) -> None:
        audit = load_audit()
        with tempfile.TemporaryDirectory() as temporary:
            plugin = Path(temporary)
            mobile = plugin / "evidence" / "mobile.png"
            desktop = plugin / "evidence" / "desktop.png"
            mobile_hash = write_png(mobile, 390, 844)
            desktop_hash = write_png(desktop, 1280, 800)
            process = plugin / "evidence" / "perception.log"
            process.write_text(
                "reviewer-perception process-perception separate-person\n",
                encoding="utf-8",
            )
            contexts = []
            for route, width, height, path, digest in (
                ("/", 390, 844, "evidence/mobile.png", mobile_hash),
                ("/", 1280, 800, "evidence/desktop.png", desktop_hash),
            ):
                contexts.append({
                    "route": route,
                    "state": "loaded",
                    "viewport": {
                        "width": width,
                        "height": height,
                        "device_pixel_ratio": 1,
                    },
                    "browser": "Chromium 130",
                    "environment": self.environment(),
                    "checks": [{
                        "id": "visual-layout",
                        "status": "passed",
                        "method": "Rendered route inspection",
                        "evidence": [{"path": path, "sha256": digest}],
                    }],
                    "render_evidence": {
                        "path": path,
                        "sha256": digest,
                        "media_type": "image/png",
                        "pixel_width": width,
                        "pixel_height": height,
                    },
                })
            payload = self.review_payload(
                lens="perception",
                process_path="evidence/perception.log",
                process_id="process-perception",
                contexts=contexts,
                evidence_paths=[
                    "evidence/mobile.png",
                    "evidence/desktop.png",
                    "evidence/perception.log",
                ],
                independent=True,
            )
            self.bind_owner_acceptance(payload, plugin)
            verified: list[dict[str, object]] = []
            failures = audit.review_semantic_failures(
                payload,
                plugin,
                "review.json",
                release_mode=True,
                verified_contexts_out=verified,
            )
            self.assertEqual(failures, [])
            self.assertEqual(
                {record["kind"] for record in verified},
                {"mobile", "desktop"},
            )
            corrupt = bytearray(mobile.read_bytes())
            corrupt[-5] ^= 0xFF
            mobile.write_bytes(corrupt)
            codes = {
                item["code"]
                for item in audit.review_semantic_failures(
                    payload,
                    plugin,
                    "review.json",
                    release_mode=True,
                )
            }
            self.assertIn("review-render-image-invalid", codes)

    def test_accessibility_score_requires_structured_check_evidence(self) -> None:
        audit = load_audit()
        with tempfile.TemporaryDirectory() as temporary:
            plugin = Path(temporary)
            image = plugin / "evidence" / "desktop.png"
            image_hash = write_png(image, 1280, 800)
            process = plugin / "evidence" / "implementation.log"
            process.write_text(
                "reviewer-implementation process-implementation self-review\n",
                encoding="utf-8",
            )
            base_context = {
                "route": "/menu",
                "state": "loaded",
                "viewport": {
                    "width": 1280,
                    "height": 800,
                    "device_pixel_ratio": 1,
                },
                "browser": "Chromium 130",
                "environment": self.environment(),
                "checks": [{
                    "id": "visual-layout",
                    "status": "passed",
                    "method": "Rendered route inspection",
                    "evidence": [{
                        "path": "evidence/desktop.png",
                        "sha256": image_hash,
                    }],
                }],
                "render_evidence": {
                    "path": "evidence/desktop.png",
                    "sha256": image_hash,
                    "media_type": "image/png",
                    "pixel_width": 1280,
                    "pixel_height": 800,
                },
            }
            evidence_paths = [
                "evidence/desktop.png",
                "evidence/implementation.log",
            ]
            payload = self.review_payload(
                lens="implementation",
                process_path="evidence/implementation.log",
                process_id="process-implementation",
                contexts=[base_context],
                evidence_paths=evidence_paths,
                independent=False,
            )
            self.bind_owner_acceptance(payload, plugin)
            failures = audit.review_semantic_failures(
                payload,
                plugin,
                "review.json",
                release_mode=True,
            )
            self.assertIn(
                "release-accessibility-evidence-incomplete",
                {item["code"] for item in failures},
            )

            checks = []
            for check_id in sorted(audit.REQUIRED_IMPLEMENTATION_CHECKS):
                relative = f"evidence/{check_id}.json"
                method = f"Verified {check_id} with an attributable test"
                record = {
                    "schema_version": 1,
                    "check_id": check_id,
                    "route": "/menu",
                    "state": "loaded",
                    "method": method,
                    "result": "passed",
                    "observed_at": "2026-07-26T12:20:00Z",
                    "executor_id": "accessibility-specialist",
                    "observations": [f"{check_id} completed without a blocker."],
                }
                path = plugin / relative
                path.write_text(
                    json.dumps(record, sort_keys=True),
                    encoding="utf-8",
                )
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                checks.append({
                    "id": check_id,
                    "status": "passed",
                    "method": method,
                    "evidence": [{"path": relative, "sha256": digest}],
                })
                evidence_paths.append(relative)
            base_context["checks"] = checks
            payload["evidence_paths"] = evidence_paths
            failures = audit.review_semantic_failures(
                payload,
                plugin,
                "review.json",
                release_mode=True,
            )
            self.assertEqual(failures, [])

    def test_release_review_lenses_and_host_status_cannot_be_self_asserted(self) -> None:
        audit = load_audit()
        perception_path = Path("perception.json")
        implementation_path = Path("implementation.json")
        perception = {
            "build": {"producer_id": "builder-alpha"},
            "reviewer": {
                "id": "reviewer-perception",
                "lens": "perception",
                "independent": True,
                "process": {
                    "id": "process-perception",
                    "method": "separate-person",
                    "evidence_path": "evidence/perception.log",
                },
            },
        }
        implementation = {
            "build": {"producer_id": "builder-alpha"},
            "reviewer": {
                "id": "reviewer-implementation",
                "lens": "implementation",
                "independent": False,
                "process": {
                    "id": "process-implementation",
                    "method": "self-review",
                    "evidence_path": "evidence/implementation.log",
                },
            },
        }
        matched = [
            (perception_path, perception),
            (implementation_path, implementation),
        ]
        render_contexts = {
            perception_path: [
                {"path": "evidence/mobile.png", "kind": "mobile"},
                {"path": "evidence/desktop.png", "kind": "desktop"},
            ]
        }
        failures = audit.release_rendered_review_failures(
            "codex",
            matched,
            render_contexts,
            {"perception.json", "implementation.json"},
            {"perception.json", "implementation.json"},
        )
        self.assertEqual(failures, [])
        implementation["reviewer"]["process"]["id"] = "process-perception"
        implementation["reviewer"]["process"]["evidence_path"] = (
            "evidence/perception.log"
        )
        failures = audit.release_rendered_review_failures(
            "codex",
            matched,
            render_contexts,
            {"perception.json", "implementation.json"},
            {"perception.json", "implementation.json"},
        )
        self.assertIn(
            "release-review-processes-not-distinct",
            {item["code"] for item in failures},
        )
        host_failures = audit.release_host_completion_failures(
            "claude_code",
            {
                "static_validation": "passed",
                "installed_sync": "passed",
                "isolated_behavioral_eval": "blocked_not_authenticated",
                "rendered_eval": "passed",
            },
        )
        self.assertIn(
            "release-host-eval-incomplete",
            {item["code"] for item in host_failures},
        )
        self.assertTrue(
            any(
                "limitation cannot replace" in item["message"]
                for item in host_failures
            )
        )
        discovery_failures = audit.release_host_discovery_failures(
            "claude_code",
            {
                "environments": [
                    {
                        "scope": "host_runtime",
                        "host": "claude_code",
                        "checks": {"host_discovery": "blocked"},
                    }
                ]
            },
        )
        self.assertIn(
            "release-host-discovery-incomplete",
            {item["code"] for item in discovery_failures},
        )
        self.assertEqual(
            audit.release_host_discovery_failures(
                "codex",
                {
                    "environments": [
                        {
                            "scope": "host_runtime",
                            "host": "codex",
                            "checks": {"host_discovery": "passed"},
                        }
                    ]
                },
            ),
            [],
        )

    def test_mock_host_native_evidence_can_never_qualify_release(self) -> None:
        audit = load_audit()
        with tempfile.TemporaryDirectory() as temporary:
            results = Path(temporary)
            evidence_dir = results / "host-evidence"
            evidence_dir.mkdir()
            session_nonce = "b" * 64
            run_nonce = "c" * 64
            run_id = "suite:codex:coffee-shop:skill:1"
            challenge_id = hashlib.sha256(
                f"{session_nonce}\0{run_nonce}\0{run_id}".encode("utf-8")
            ).hexdigest()
            started_at = "2026-07-26T11:59:59+00:00"
            observed_at = "2026-07-26T12:00:00+00:00"
            finished_at = "2026-07-26T12:00:01+00:00"
            challenge_relative = "host-evidence/challenge.json"
            challenge = {
                "schema_version": 2,
                "challenge_id": challenge_id,
                "session_nonce": session_nonce,
                "run_nonce": run_nonce,
                "issued_at": started_at,
                "host": "codex",
                "case": "coffee-shop",
                "variant": "skill",
                "run": 1,
                "run_id": run_id,
                "skill_loaded": True,
                "skill_content_sha256": "a" * 64,
            }
            challenge_path = results / challenge_relative
            challenge_path.write_text(
                json.dumps(challenge, sort_keys=True),
                encoding="utf-8",
            )
            challenge_digest = hashlib.sha256(
                challenge_path.read_bytes()
            ).hexdigest()
            relative = "host-evidence/response.json"
            evidence = {
                "schema_version": 2,
                "challenge_id": challenge_id,
                "challenge_sha256": challenge_digest,
                "session_nonce": session_nonce,
                "run_nonce": run_nonce,
                "host": "codex",
                "case": "coffee-shop",
                "variant": "skill",
                "run": 1,
                "run_id": run_id,
                "skill_loaded": True,
                "skill_content_sha256": "a" * 64,
                "method": "host-adapter-event",
                "source_id": "mock-host-adapter-test",
                "source_version": "1.0.0",
                "observed_at": observed_at,
            }
            evidence_path = results / relative
            evidence_path.write_text(
                json.dumps(evidence, sort_keys=True),
                encoding="utf-8",
            )
            digest = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
            run = {
                "host": "codex",
                "case": "coffee-shop",
                "variant": "skill",
                "run": 1,
                "run_id": run_id,
                "started_at": started_at,
                "finished_at": finished_at,
                "skill_content_sha256": "a" * 64,
                "host_native_challenge": {
                    "path": challenge_relative,
                    "sha256": challenge_digest,
                    "challenge_id": challenge_id,
                    "session_nonce": session_nonce,
                    "run_nonce": run_nonce,
                    "issued_at": started_at,
                },
                "host_native_evidence_status": "bound",
                "host_native_evidence": {
                    "path": relative,
                    "sha256": digest,
                    "challenge_id": challenge_id,
                    "challenge_sha256": challenge_digest,
                    "session_nonce": session_nonce,
                    "run_nonce": run_nonce,
                    "method": "host-adapter-event",
                    "source_id": "mock-host-adapter-test",
                    "source_version": "1.0.0",
                    "observed_at": observed_at,
                    "captured_at": observed_at,
                },
            }
            failures = audit.eval_host_native_evidence_failures(
                run,
                "run",
                session_nonce=session_nonce,
                result_path=results / "result.json",
                required=True,
                release_mode=True,
                trusted_adapters={
                    (
                        "codex",
                        "mock-host-adapter-test",
                        "1.0.0",
                        "host-adapter-event",
                    )
                },
            )
            self.assertIn(
                "release-host-native-test-identity",
                {item["code"] for item in failures},
            )
            for timestamp, expected_code in (
                (
                    "2000-01-01T00:00:00+00:00",
                    "eval-host-native-evidence-stale",
                ),
                (
                    "2099-01-01T00:00:00+00:00",
                    "eval-host-native-evidence-future",
                ),
            ):
                with self.subTest(observed_at=timestamp):
                    evidence["observed_at"] = timestamp
                    evidence_path.write_text(
                        json.dumps(evidence, sort_keys=True),
                        encoding="utf-8",
                    )
                    record = run["host_native_evidence"]
                    self.assertIsInstance(record, dict)
                    record["sha256"] = hashlib.sha256(
                        evidence_path.read_bytes()
                    ).hexdigest()
                    record["observed_at"] = timestamp
                    record["captured_at"] = timestamp
                    failures = audit.eval_host_native_evidence_failures(
                        run,
                        "run",
                        session_nonce=session_nonce,
                        result_path=results / "result.json",
                        required=True,
                    )
                    self.assertIn(
                        expected_code,
                        {item["code"] for item in failures},
                        failures,
                    )

    def test_eval_replay_detection_spans_result_files(self) -> None:
        audit = load_audit()
        challenge = {
            "challenge_id": "1" * 64,
            "run_nonce": "2" * 64,
            "sha256": "3" * 64,
        }
        evidence = {"sha256": "4" * 64}
        first = {
            "session_nonce": "5" * 64,
            "runs": [
                {
                    "host_native_challenge": challenge,
                    "host_native_evidence": evidence,
                }
            ],
        }
        second = json.loads(json.dumps(first))
        failures = audit.eval_replay_failures([
            (Path("first.json"), first),
            (Path("second.json"), second),
        ])
        self.assertTrue(
            {
                "eval-session-nonce-replayed",
                "eval-host-native-challenge-cross-result-replay",
                "eval-host-native-run-nonce-cross-result-replay",
                "eval-host-native-challenge-digest-cross-result-replay",
                "eval-host-native-evidence-cross-result-replay",
            }.issubset({item["code"] for item in failures}),
            failures,
        )


@unittest.skipUnless(
    importlib.util.find_spec("yaml") and importlib.util.find_spec("jsonschema"),
    "maintainer dependencies are not installed",
)
class AuditResidueTests(unittest.TestCase):
    def test_dev_audit_detects_runtime_cache_residue_omitted_by_manifests(self) -> None:
        sys.path.insert(0, str(MAINTAINER_SCRIPTS))
        try:
            from audit_package import runtime_cache_failures
        finally:
            sys.path.remove(str(MAINTAINER_SCRIPTS))

        with tempfile.TemporaryDirectory() as temporary:
            plugin = Path(temporary) / "plugin"
            skill = plugin / "skills" / "design-dna"
            cache = skill / "scripts" / "__pycache__"
            cache.mkdir(parents=True)
            (cache / "ignored.pyc").write_bytes(b"cache")
            loose = skill / "compiled.pyo"
            loose.write_bytes(b"compiled")
            failures = runtime_cache_failures(skill, label_root=plugin)
            self.assertEqual(
                {item["code"] for item in failures},
                {"runtime-cache-residue"},
            )
            self.assertEqual(
                {item["path"] for item in failures},
                {
                    "skills/design-dna/scripts/__pycache__",
                    "skills/design-dna/compiled.pyo",
                },
            )


if __name__ == "__main__":
    unittest.main()
