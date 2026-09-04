from __future__ import annotations

import binascii
import hashlib
import importlib.util
import json
import struct
import tempfile
import unittest
import zlib
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


def write_png(path: Path, width: int, height: int) -> str:
    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = binascii.crc32(kind)
        checksum = binascii.crc32(data, checksum) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    row = b"\x00" + (b"\x24\x68\xac" * width)
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(row * height))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def compact_direction(
    *extra_sections: str,
    include_reference_logic: bool = True,
) -> str:
    sections = [
        "<!-- proportional-evidence-v1 -->",
        "## Identity and intent",
        "This build helps local customers compare the approved service options.",
        "## Truth and provenance",
        "Copy and identity come from the owner packet; no unsupported claims are used.",
        "## Material, media, and public-copy boundary",
        "- Physical or sensory subject: no",
        "- Explicit owner request for photos or rich media: no",
        "- Material and media posture: inherited-system",
        "- Project-specific basis: The approved service system already defines the identity and comparison behavior for this bounded route.",
        "- Media roles and truth boundary: Existing approved identity assets may orient the visitor; they must not imply unapproved services or outcomes.",
        "- Asset manifest and readiness: Not applicable because this bounded inherited-system fixture introduces no new material assets.",
        "- Deliberately media-light rationale: Not applicable because the fixture preserves an inherited system rather than selecting a media-light direction.",
        "- Media-light exception basis: Not applicable because no physical or sensory media-light exception is used.",
        "- Media-light exception approval: Not applicable because no physical or sensory media-light exception is used.",
        "- Media-light exception evidence: Not applicable because no physical or sensory media-light exception is used.",
        "- Owner-rejection disposition: not-applicable because no accountable owner has rejected this exact fixture candidate.",
        "- Protected facts and functions: Approved service names, eligibility constraints, comparison behavior, and keyboard access must survive.",
        "- Public-copy boundary: Internal record labels, implementation stages, and evidence vocabulary remain outside visitor-facing copy.",
        "## Responsive, accessible, and functional behavior",
        "Navigation, forms, long content, keyboard input, zoom, and narrow widths were covered.",
        "## Owner and release state",
        "Build ordinary-17 is self-reviewed; owner acceptance remains pending before release.",
    ]
    if include_reference_logic:
        sections.extend((
            "## Reference-sourced organizing logic",
            "- Project evidence: The approved service packet binds reference selection to the real customer comparison task and truthful service constraints.",
            "- Organizing logic: Selected reference ranks 1 and 2 map their adjacent comparison relationship and constraint-reveal sequence to this candidate.",
            "## Observable consequential design decisions",
            "| Decision | Selected source rank and project-fit reason | Observable consequence | Verification |",
            "| --- | --- | --- | --- |",
            "| Keep the choice comparison adjacent to its constraints. | The approved packet treats eligibility and scope as part of each choice. | A visitor can compare an option and its constraint without crossing an unrelated section. | Inspect the rendered choice sequence with long approved copy at narrow and wide widths. |",
        ))
    sections.extend((*extra_sections, ""))
    return "\n".join(sections)


def compact_visual_review(digest: str) -> str:
    return f"""<!-- proportional-evidence-v1 -->
## Rendered review

- Build or artifact ID: ordinary-17
- Final implementation reviewed: yes
- Reviewer relationship: producer-self

| Route/state | Viewport/context | Rendered PNG path and SHA-256 | Observation |
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
            digest = write_png(artifact, 390, 844)
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

            artifact.write_bytes(b"arbitrary bytes renamed as a screenshot")
            fake_digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            fake_failures = self.module.substantive_body_failures(
                "visual-review",
                compact_visual_review(fake_digest),
                project=project,
                record_path=state_root / "visual-review.md",
                required_assurance_profiles={"standard"},
                evidence_contract=self.module.PROPORTIONAL_EVIDENCE_CONTRACT,
            )
            self.assertTrue(
                any("not a decodable PNG" in failure for failure in fake_failures),
                fake_failures,
            )

            mismatched = evidence / "review.jpg"
            mismatch_digest = write_png(mismatched, 390, 844)
            mismatch_body = compact_visual_review(mismatch_digest).replace(
                "evidence/review.png",
                "evidence/review.jpg",
            )
            mismatch_failures = self.module.substantive_body_failures(
                "visual-review",
                mismatch_body,
                project=project,
                record_path=state_root / "visual-review.md",
                required_assurance_profiles={"standard"},
                evidence_contract=self.module.PROPORTIONAL_EVIDENCE_CONTRACT,
            )
            self.assertTrue(
                any("must use a .png extension" in failure for failure in mismatch_failures),
                mismatch_failures,
            )

    def test_standard_direction_requires_logic_while_quick_repairs_are_exempt(self) -> None:
        compact = compact_direction(include_reference_logic=False)
        standard_failures = self.module.substantive_body_failures(
            "direction",
            compact,
            required_assurance_profiles={"standard"},
            evidence_contract=self.module.PROPORTIONAL_EVIDENCE_CONTRACT,
        )
        self.assertIn(
            "missing required sections: Observable consequential design decisions, Reference-sourced organizing logic",
            standard_failures,
        )
        self.assertEqual(
            [],
            self.module.substantive_body_failures(
                "direction",
                compact,
                required_assurance_profiles={"quick"},
                evidence_contract=self.module.PROPORTIONAL_EVIDENCE_CONTRACT,
            ),
        )

        boilerplate = compact_direction(
            "## Reference-sourced organizing logic",
            "- Project evidence: Use a clean modern design for this project.",
            "- Organizing logic: Use a clean modern design for this project.",
            "## Observable consequential design decisions",
            "| Decision | Selected source rank and project-fit reason | Observable consequence | Verification |",
            "| --- | --- | --- | --- |",
            "| Make it clean and modern. | Make it clean and modern. | Make it clean and modern. | Make it clean and modern. |",
            include_reference_logic=False,
        )
        boilerplate_failures = self.module.substantive_body_failures(
            "direction",
            boilerplate,
            required_assurance_profiles={"standard"},
            evidence_contract=self.module.PROPORTIONAL_EVIDENCE_CONTRACT,
        )
        self.assertGreaterEqual(
            sum("generic boilerplate" in failure for failure in boilerplate_failures),
            2,
            boilerplate_failures,
        )

    def test_quick_initializer_omits_the_exempt_direction_scaffold(self) -> None:
        template_root = PLUGIN / "skills" / "design-dna" / "templates"
        quick = self.module.template_text(
            template_root,
            "direction-template.md",
            "test-version",
            ("quick",),
        )
        standard = self.module.template_text(
            template_root,
            "direction-template.md",
            "test-version",
            ("standard",),
        )
        for heading in self.module.REFERENCE_SOURCED_DIRECTION_SECTIONS:
            self.assertNotIn(f"## {heading}", quick)
            self.assertIn(f"## {heading}", standard)
        self.assertNotIn("__REPLACE_WITH_A_CONSEQUENTIAL_DECISION__", quick)
        # The quick initializer retains the optional evidence area, renamed
        # when the source-authority contract replaced the old freeform
        # extension scaffold.  It must not expect an obsolete heading.
        self.assertIn("## Additional source-bound evidence", quick)

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

    def test_batch_study_requires_protocol_evidence_without_a_design_recipe(self) -> None:
        failures = self.module.substantive_body_failures(
            "direction",
            compact_direction(),
            required_assurance_profiles={"standard", "batch-study"},
            required_evidence_capabilities={"batch-study"},
            evidence_contract=self.module.PROPORTIONAL_EVIDENCE_CONTRACT,
        )
        self.assertIn("Batch Study protocol", "\n".join(failures))
        complete = compact_direction(
            "## Batch Study protocol",
            (
                "Three frozen briefs use isolated roots and project-derived "
                "viewport classes; unprimed and masked review remain separate, "
                "with no aesthetic score or novelty quota."
            ),
        )
        self.assertEqual(
            [],
            self.module.substantive_body_failures(
                "direction",
                complete,
                required_assurance_profiles={"standard", "batch-study"},
                required_evidence_capabilities={"batch-study"},
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

    def test_state_schema_binds_direction_contract_to_assurance_profile(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        standard = json.loads(
            self.module.state_manifest(
                "5.1.0",
                ("direction", "visual-review"),
                ("standard",),
            )
        )
        self.assertEqual(
            standard["evidence_contract"]["direction_contract"],
            "reference-sourced-organizing-logic-v1",
        )
        self.assertEqual(
            [],
            list(Draft202012Validator(schema).iter_errors(standard)),
        )

        quick = json.loads(
            self.module.state_manifest(
                "5.1.0",
                ("direction", "visual-review"),
                ("quick",),
            )
        )
        self.assertEqual(
            quick["evidence_contract"]["direction_contract"],
            "quick-repair-exempt",
        )
        self.assertEqual(
            [],
            list(Draft202012Validator(schema).iter_errors(quick)),
        )

        mismatch = json.loads(json.dumps(standard))
        mismatch["evidence_contract"]["direction_contract"] = (
            "quick-repair-exempt"
        )
        self.assertTrue(
            list(Draft202012Validator(schema).iter_errors(mismatch))
        )
        with self.assertRaises(self.module.StateError):
            self.module.validate_evidence_contract(
                mismatch["evidence_contract"],
                ("standard",),
            )
        prior_contract = json.loads(
            json.dumps(standard["evidence_contract"])
        )
        prior_contract["version"] = 1
        del prior_contract["direction_contract"]
        self.assertEqual(
            ((), []),
            self.module.migrate_evidence_contract(
                prior_contract,
                ("standard",),
            ),
        )

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state_root = project / ".design-dna"
            state_root.mkdir()
            legacy_standard = json.loads(json.dumps(standard))
            del legacy_standard["evidence_contract"]
            (state_root / "state.json").write_text(
                json.dumps(legacy_standard),
                encoding="utf-8",
            )
            self.assertEqual(
                [
                    "state.json needs the current reference-sourced direction "
                    "contract before readiness; run --migrate."
                ],
                self.module.readiness_failures(project),
            )

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
