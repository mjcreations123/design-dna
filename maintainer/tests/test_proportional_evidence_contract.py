from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator


PLUGIN = Path(__file__).resolve().parents[2]
INIT = PLUGIN / "skills" / "design-dna" / "scripts" / "init_project_state.py"
SCHEMA = PLUGIN / "maintainer" / "schemas" / "project-state.schema.json"


def load_initializer():
    specification = importlib.util.spec_from_file_location(
        "design_dna_proportional_evidence_initializer",
        INIT,
    )
    if specification is None or specification.loader is None:
        raise AssertionError("could not load project-state initializer")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def compact_direction(*extra_sections: str) -> str:
    return "\n".join(
        (
            "<!-- proportional-evidence-v1 -->",
            "## Identity and intent",
            "This build helps local customers compare the approved service options.",
            "## Truth and provenance",
            "Copy and identity come from the owner packet; no unsupported claims are used.",
            "## Responsive, accessible, and functional behavior",
            "Navigation, forms, long content, keyboard input, zoom, and narrow widths were covered.",
            "## Owner and release state",
            "Build ordinary-17 is self-reviewed; owner acceptance remains pending before release.",
            *extra_sections,
            "",
        )
    )


def compact_visual_review(digest: str) -> str:
    return f"""<!-- proportional-evidence-v1 -->
## Rendered review

- Build or artifact ID: ordinary-17
- Final implementation reviewed: yes
- Reviewer relationship: producer-self

| Route/state | Viewport/context | Evidence path and SHA-256 | Observation |
| --- | --- | --- | --- |
| /; default | 390x844; keyboard | evidence/review.png plus sha256:{digest} | Task and navigation remain usable. |

## Findings

| Severity | Confidence | Evidence | User/release impact | Cause | Fix or disposition | Rerun verification | Status | Owner |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| low | high | review.png | Minor spacing issue | Tight label | Adjusted spacing | Rechecked ordinary-17 | verified | reviewer-7 |

## Owner and release state

- Reviewer conclusion: self-reviewed candidate
- Owner disposition: pending
- Release blockers: none within the reviewed scope
"""


class ProportionalEvidenceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_initializer()

    def test_compact_ordinary_project_needs_no_irrelevant_labels(self) -> None:
        body = compact_direction()
        for legacy_label in (
            "Requested visual or experiential qualities in the owner's language",
            "Intentional one-offs and optical exceptions",
            "Candidate identities and directly reviewable proof",
            "Typography register",
        ):
            self.assertNotIn(legacy_label, body)
        self.assertEqual(
            [],
            self.module.substantive_body_failures(
                "direction",
                body,
                required_assurance_profiles={"standard"},
                evidence_contract=self.module.PROPORTIONAL_EVIDENCE_CONTRACT,
            ),
        )
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state_root = project / ".design-dna"
            state_root.mkdir()
            evidence = project / "evidence"
            evidence.mkdir()
            artifact = evidence / "review.png"
            artifact.write_bytes(b"rendered ordinary project")
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            self.assertEqual(
                [],
                self.module.substantive_body_failures(
                    "visual-review",
                    compact_visual_review(digest),
                    project=project,
                    record_path=state_root / "visual-review.md",
                    required_assurance_profiles={"standard"},
                    evidence_contract=(
                        self.module.PROPORTIONAL_EVIDENCE_CONTRACT
                    ),
                ),
            )

    def test_applicable_range_and_cultural_evidence_is_required(self) -> None:
        failures = self.module.substantive_body_failures(
            "direction",
            compact_direction(),
            required_assurance_profiles={"standard", "range-study"},
            required_evidence_capabilities={"range-study", "cultural-context"},
            evidence_contract=self.module.PROPORTIONAL_EVIDENCE_CONTRACT,
        )
        joined = "\n".join(failures)
        self.assertIn("Range-study contract", joined)
        self.assertIn("Cultural context and authority", joined)
        complete = compact_direction(
            "## Range-study contract",
            "Shared navigation and truth rules are bound in route-family.json; bodies differ by purpose.",
            "## Cultural context and authority",
            "Terminology follows the reviewed source packet; independent cultural acceptance is still required.",
        )
        self.assertEqual(
            [],
            self.module.substantive_body_failures(
                "direction",
                complete,
                required_assurance_profiles={"standard", "range-study"},
                required_evidence_capabilities={
                    "range-study",
                    "cultural-context",
                },
                evidence_contract=self.module.PROPORTIONAL_EVIDENCE_CONTRACT,
            ),
        )

    def test_well_formed_project_specific_extension_is_accepted(self) -> None:
        extension = {
            "id": "sonic-wayfinding",
            "purpose": "Bind an optional audio-navigation study unique to this installation.",
            "applies_to": ["sonic-wayfinding"],
            "status": "complete",
            "owner": "experience-lead-7",
            "evidence": ["direction.md#sonic-wayfinding"],
        }
        manifest = json.loads(
            self.module.state_manifest(
                "4.0.0",
                ("direction", "visual-review"),
                ("standard",),
                ("sonic-wayfinding",),
                (extension,),
            )
        )
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        errors = sorted(
            Draft202012Validator(schema).iter_errors(manifest),
            key=lambda error: list(error.absolute_path),
        )
        self.assertEqual([], [error.message for error in errors])
        capabilities, extensions = self.module.validate_evidence_contract(
            manifest["evidence_contract"],
            ("standard",),
        )
        self.assertEqual(("sonic-wayfinding",), capabilities)
        self.assertEqual([extension], extensions)

    def test_omitting_a_universal_anchor_fails(self) -> None:
        body = compact_direction().replace(
            "## Truth and provenance\n"
            "Copy and identity come from the owner packet; no unsupported claims are used.\n",
            "",
        )
        failures = self.module.substantive_body_failures(
            "direction",
            body,
            evidence_contract=self.module.PROPORTIONAL_EVIDENCE_CONTRACT,
        )
        self.assertIn(
            "missing required sections: Truth and provenance",
            failures,
        )

    def test_windows_stage_uses_inherited_project_acl_and_reports_denial(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            with mock.patch.object(
                self.module.tempfile,
                "mkdtemp",
                side_effect=AssertionError(
                    "Windows staging must not use a private tempfile ACL"
                ),
            ):
                stage = self.module.create_transaction_stage_parent(
                    project,
                    ".design-dna-stage-",
                    platform_name="nt",
                )
            self.assertTrue(stage.is_dir())
            self.assertEqual(project, stage.parent)
        denied = PermissionError(13, "Access is denied")
        error = self.module.as_state_error(
            denied,
            code="initialization-failed",
            path=Path("C:/project/.design-dna"),
        )
        self.assertEqual("state-access-denied", error.code)
        self.assertIn("restore inherited permissions", str(error))


if __name__ == "__main__":
    unittest.main()
