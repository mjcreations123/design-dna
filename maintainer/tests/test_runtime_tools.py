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
    def test_initializes_and_validates_transactionally(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            result = run_script(INIT, "--project", str(project), "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            state = project / ".design-dna"
            self.assertEqual(
                sorted(path.name for path in state.iterdir()),
                [".gitignore", "direction.md", "evidence", "state.json", "visual-review.md"],
            )
            check = run_script(INIT, "--project", str(project), "--check-state", "--json")
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

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
            original = asset_path.read_text(encoding="utf-8")
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
                    "    content_job: \"\"\n",
                    "    content_job: \"\"\n    mystery: \"value\"\n",
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
                    '      treatment: "pending"\n',
                    '      treatment: "informative"\n',
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
                "    usage_locations: []\n",
                "    usage_locations:\n"
                "      - \"homepage\"\n"
                "      - \"menu\"\n",
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

            reviewed_generated_media = (
                original.replace(
                    '      used: false\n',
                    '      used: true\n',
                    1,
                )
                .replace(
                    '      tool_or_model: ""\n',
                    '      tool_or_model: "Owner-recorded generation service"\n',
                    1,
                )
                .replace(
                    "      source_inputs: []\n",
                    '      source_inputs:\n'
                    '        - "Owner-approved source asset"\n',
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

            public_generated_media = reviewed_generated_media.replace(
                'classification: "internal"\n',
                'classification: "public"\n',
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
                    "      disclosure_required: false\n",
                    "      disclosure_required: true\n",
                    1,
                )
                .replace(
                    '      disclosure_text: ""\n',
                    '      disclosure_text: "Synthetic concept image."\n',
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
            source.write_text('<h1><span className="text-purple-500">Better</span> coffee</h1>', encoding="utf-8")
            first = run_script(SCAN, str(project), "--json")
            self.assertEqual(first.returncode, 0)
            findings = json.loads(first.stdout)["findings"]
            self.assertTrue(any(item["rule"] == "decorative-headline-span" for item in findings))
            headline_finding = next(
                item
                for item in findings
                if item["rule"] == "decorative-headline-span"
            )
            allowlist = project / "allow.json"
            allowlist.write_text(json.dumps({
                "schema_version": 1,
                "allow": [{
                    "rule": "decorative-headline-span",
                    "path": "page.tsx",
                    "fingerprint": headline_finding["fingerprint"],
                    "reason": "Approved semantic brand emphasis.",
                    "owner": "Design system owner",
                    "expires": ACTIVE_EXPIRY,
                }],
            }), encoding="utf-8")
            second = run_script(SCAN, str(project), "--allowlist", str(allowlist), "--json")
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertFalse(any(item["rule"] == "decorative-headline-span" for item in json.loads(second.stdout)["findings"]))


class AuditGateTests(unittest.TestCase):
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
        rubric = {
            "project_specificity": 2,
            "direction": 2,
            "task_hierarchy": 2,
            "contemporary_fit": 2,
            "typography": 2,
            "composition_density": 2,
            "media_icons": 2,
            "copy_ia": 2,
            "distinctiveness_without_novelty_tax": 2,
            "functional_completeness": 2,
            "responsive_adaptation": 2,
            "accessibility_baseline": 2,
            "truth_provenance": 2,
            "system_code": 2,
            "performance_resilience": 2,
            "residue": 2,
            "cultural_representational_fit": 2,
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
