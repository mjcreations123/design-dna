"""Regression coverage for the owner-scoped named-pattern release gate."""

from __future__ import annotations

import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from copy import deepcopy
from pathlib import Path
from unittest import mock


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = SKILL_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import init_project_state  # noqa: E402
import owner_pattern_audit  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def write_png(path: Path, width: int, height: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = b"\x00" + (b"\x22\x66\xaa" * width)
    raw = row * height
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(raw, 9))
        + png_chunk(b"IEND", b"")
    )
    path.write_bytes(payload)


def contract_payload() -> dict[str, object]:
    signal_text = (
        "A precisely scoped failed relationship with enough explanatory detail "
        "to change a consequential design decision."
    )
    return {
        "schema_version": 1,
        "contract_id": "test-owner-pattern-contract",
        "status": "active",
        "owner": {"id": "test-owner", "display_name": "Test Owner"},
        "scope": "Every public website produced inside this bounded test scope.",
        "authority": {
            "adopted_at": "2026-08-24",
            "source_kind": "accountable owner instruction",
            "source_url": "https://example.com/owner-source",
            "source_author": "Accountable Test Owner",
            "owner_instruction": "Close every named failed relationship before implementation and release.",
        },
        "semantics": {
            "unit": "failed-relationship",
            "authorship_boundary": "This checks owner-named failures and makes no authorship inference.",
            "ingredient_boundary": "A meaningful ingredient is distinct from the purposeless relationship named here.",
        },
        "signals": [
            {
                "id": "decorative-numbering-without-sequence",
                "label": "Decorative numbering without a real sequence",
                "failure_definition": signal_text,
                "direction_requirement": signal_text,
                "final_requirement": signal_text,
            },
            {
                "id": "depth-without-information",
                "label": "Layered depth without information or interaction",
                "failure_definition": signal_text,
                "direction_requirement": signal_text,
                "final_requirement": signal_text,
            },
        ],
        "release_policy": {
            "direction_disposition": "controlled",
            "final_disposition": "absent",
            "require_wide_and_narrow_rendered_evidence": True,
            "wide_min_css_width": 1024,
            "narrow_max_css_width": 480,
            "unresolved_blocks": True,
            "exception_model": "none-failure-states-only",
            "required_capture_mode": "full-page",
        },
    }


def file_ref(project: Path, path: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(project).as_posix(),
        "sha256": sha256(path),
    }


class OwnerPatternAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.contract = self.root / "owner-pattern-contract.json"
        write_json(self.contract, contract_payload())

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def review(self) -> dict[str, object]:
        return json.loads(
            (self.project / ".design-dna" / "owner-pattern-review.json").read_text(
                encoding="utf-8"
            )
        )

    def save_review(self, payload: dict[str, object]) -> None:
        write_json(
            self.project / ".design-dna" / "owner-pattern-review.json",
            payload,
        )

    def complete_direction(self, payload: dict[str, object]) -> None:
        direction_path = self.project / ".design-dna" / "direction.md"
        direction_path.write_text(
            "# Direction\n\nProject-derived organizing logic and exact decisions.\n",
            encoding="utf-8",
        )
        payload["status"] = "direction-ready"
        payload["project"] = {
            "id": "fixture-site",
            "scope": "The complete bounded public route family in this fixture.",
        }
        direction = payload["direction"]
        direction["status"] = "passed"
        direction["reviewed_at"] = "2026-08-24"
        direction["reviewer"] = "producer-self-review"
        direction["evidence"] = file_ref(self.project, direction_path)
        for item in direction["signals"]:
            item["disposition"] = "controlled"
            item["decision"] = "The direction does not use the failed relationship as visual scaffolding."
            item["failure_prevention"] = "The content model and rendered hierarchy carry the role directly instead."
            item["project_basis"] = "The fixture brief requires clear content relationships without decorative substitution."

    def complete_final(self, payload: dict[str, object]) -> tuple[Path, Path]:
        wide = self.project / "evidence" / "wide.png"
        narrow = self.project / "evidence" / "narrow.png"
        write_png(wide, 1200, 800)
        write_png(narrow, 400, 800)
        visual_review = self.project / ".design-dna" / "visual-review.md"
        visual_review.write_text(
            "# Visual review\n\n- Build or artifact ID: final-build-1\n",
            encoding="utf-8",
        )
        payload["status"] = "reviewed"
        final = payload["final"]
        final["status"] = "passed"
        final["reviewed_at"] = "2026-08-24"
        final["reviewer"] = "producer-self-review"
        final["build_id"] = "final-build-1"
        final["visual_review"] = file_ref(self.project, visual_review)
        for item in final["signals"]:
            item["disposition"] = "absent"
            item["observation"] = "The exact failed relationship is absent across the reviewed route evidence."
            item["evidence"] = [
                {
                    **file_ref(self.project, wide),
                    "viewport": "wide",
                    "css_width": 1200,
                    "route_or_state": "/ default wide",
                    "build_id": "final-build-1",
                    "capture_mode": "full-page",
                },
                {
                    **file_ref(self.project, narrow),
                    "viewport": "narrow",
                    "css_width": 400,
                    "route_or_state": "/ default narrow",
                    "build_id": "final-build-1",
                    "capture_mode": "full-page",
                },
            ]
        return wide, narrow

    def test_review_is_fail_closed_across_state_prebuild_and_ready(self) -> None:
        initialized = owner_pattern_audit.initialize_review(
            self.project,
            self.contract,
        )
        self.assertTrue(initialized["ok"])
        state = owner_pattern_audit.audit_project(
            self.project,
            phase="state",
            contract_file=self.contract,
        )
        self.assertTrue(state["ready"])
        prebuild = owner_pattern_audit.audit_project(
            self.project,
            phase="prebuild",
            contract_file=self.contract,
        )
        self.assertFalse(prebuild["ready"])

        payload = self.review()
        self.complete_direction(payload)
        self.save_review(payload)
        prebuild = owner_pattern_audit.audit_project(
            self.project,
            phase="prebuild",
            contract_file=self.contract,
        )
        self.assertTrue(prebuild["ready"], prebuild)
        ready = owner_pattern_audit.audit_project(
            self.project,
            phase="ready",
            contract_file=self.contract,
        )
        self.assertFalse(ready["ready"])

        payload = self.review()
        wide, _ = self.complete_final(payload)
        self.save_review(payload)
        ready = owner_pattern_audit.audit_project(
            self.project,
            phase="ready",
            contract_file=self.contract,
        )
        self.assertTrue(ready["ready"], ready)

        wide.write_bytes(wide.read_bytes() + b"drift")
        drifted = owner_pattern_audit.audit_project(
            self.project,
            phase="ready",
            contract_file=self.contract,
        )
        self.assertFalse(drifted["ready"])
        self.assertIn(
            "evidence-digest-mismatch",
            {item["code"] for item in drifted["gaps"]},
        )

    def test_contract_byte_drift_and_missing_signal_fail(self) -> None:
        owner_pattern_audit.initialize_review(self.project, self.contract)
        payload = self.review()
        payload["direction"]["signals"].pop()
        self.save_review(payload)
        report = owner_pattern_audit.audit_project(
            self.project,
            phase="state",
            contract_file=self.contract,
        )
        self.assertFalse(report["ready"])
        self.assertIn(
            "direction-signal-set",
            {item["code"] for item in report["findings"]},
        )

        payload = self.review()
        payload["direction"]["signals"] = owner_pattern_audit.initialized_review(
            contract_payload(),
            sha256(self.contract),
        )["direction"]["signals"]
        self.save_review(payload)
        contract = contract_payload()
        contract["scope"] = "A materially changed and newly reviewed owner scope for this fixture."
        write_json(self.contract, contract)
        drifted = owner_pattern_audit.audit_project(
            self.project,
            phase="state",
            contract_file=self.contract,
        )
        self.assertFalse(drifted["ready"])
        self.assertIn(
            "review-contract-drift",
            {item["code"] for item in drifted["findings"]},
        )

    def test_ready_rejects_capture_laundering_and_incomplete_pngs(self) -> None:
        owner_pattern_audit.initialize_review(self.project, self.contract)
        payload = self.review()
        self.complete_direction(payload)
        _, narrow = self.complete_final(payload)
        self.save_review(payload)
        self.assertTrue(
            owner_pattern_audit.audit_project(
                self.project,
                phase="ready",
                contract_file=self.contract,
            )["ready"]
        )
        valid = deepcopy(payload)

        payload["final"]["signals"][0]["evidence"][0]["build_id"] = "other-build"
        self.save_review(payload)
        wrong_build = owner_pattern_audit.audit_project(
            self.project,
            phase="ready",
            contract_file=self.contract,
        )
        self.assertFalse(wrong_build["ready"])
        self.assertIn(
            "capture-build-drift",
            {item["code"] for item in wrong_build["gaps"]},
        )

        payload = deepcopy(valid)
        wide = payload["final"]["signals"][0]["evidence"][0]
        narrow_record = payload["final"]["signals"][0]["evidence"][1]
        narrow_record["path"] = wide["path"]
        narrow_record["sha256"] = wide["sha256"]
        self.save_review(payload)
        reused = owner_pattern_audit.audit_project(
            self.project,
            phase="ready",
            contract_file=self.contract,
        )
        self.assertFalse(reused["ready"])
        self.assertIn(
            "final-signal-render-reuse",
            {item["code"] for item in reused["gaps"]},
        )

        payload = deepcopy(valid)
        narrow.write_bytes(narrow.read_bytes() + b"not-a-png-chunk")
        for signal in payload["final"]["signals"]:
            signal["evidence"][1]["sha256"] = sha256(narrow)
        self.save_review(payload)
        incomplete = owner_pattern_audit.audit_project(
            self.project,
            phase="ready",
            contract_file=self.contract,
        )
        self.assertFalse(incomplete["ready"])
        self.assertIn(
            "rendered-evidence-png-structure",
            {item["code"] for item in incomplete["gaps"]},
        )

    def test_initializer_integration_is_explicit_trigger_only(self) -> None:
        state_root = self.project / ".design-dna"
        state_root.mkdir()
        paired = {
            "scope": {
                "trigger": [init_project_state.OWNER_PATTERN_TRIGGER],
            },
        }
        write_json(state_root / "project-contrast.json", paired)
        write_json(state_root / "direction-challenge.json", paired)
        owner_pattern_audit.initialize_review(self.project, self.contract)
        with mock.patch.dict(
            os.environ,
            {owner_pattern_audit.CONTRACT_ENV: str(self.contract)},
            clear=False,
        ):
            failures = init_project_state.owner_pattern_contract_failures(
                self.project,
                phase="state",
            )
            self.assertEqual(failures, [])
            write_json(
                state_root / "direction-challenge.json",
                {"scope": {"trigger": []}},
            )
            failures = init_project_state.owner_pattern_contract_failures(
                self.project,
                phase="state",
            )
            self.assertTrue(any("inconsistent paired triggers" in item for item in failures))

    def test_cli_trigger_populates_both_records_and_blocks_missing_review(self) -> None:
        project = self.root / "cli-project"
        project.mkdir()
        initializer = SCRIPTS_ROOT / "init_project_state.py"
        environment = {
            **os.environ,
            owner_pattern_audit.CONTRACT_ENV: str(self.contract),
        }
        initialized = subprocess.run(
            [
                sys.executable,
                "-B",
                str(initializer),
                "--project",
                str(project),
                "--profile",
                "showcase",
                "--trigger",
                init_project_state.OWNER_PATTERN_TRIGGER,
                "--json",
            ],
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        for name in ("project-contrast.json", "direction-challenge.json"):
            payload = json.loads(
                (project / ".design-dna" / name).read_text(encoding="utf-8")
            )
            self.assertIn(
                init_project_state.OWNER_PATTERN_TRIGGER,
                payload["scope"]["trigger"],
            )
        checked = subprocess.run(
            [
                sys.executable,
                "-B",
                str(initializer),
                "--project",
                str(project),
                "--check-state",
                "--json",
            ],
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )
        self.assertEqual(checked.returncode, 1)
        checked_payload = json.loads(checked.stdout)
        self.assertTrue(
            any(
                "owner-pattern-review-missing" in failure
                for failure in checked_payload["failures"]
            )
        )


if __name__ == "__main__":
    unittest.main()
