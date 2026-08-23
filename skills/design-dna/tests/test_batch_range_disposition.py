#!/usr/bin/env python3
"""Focused regressions for Batch Study protocol and human disposition split."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


SKILL = Path(__file__).resolve().parents[1]
AUDITOR_PATH = SKILL / "scripts" / "batch_range_audit.py"


def load_auditor():
    specification = importlib.util.spec_from_file_location(
        "design_dna_batch_range_disposition",
        AUDITOR_PATH,
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


AUDITOR = load_auditor()


def finding(
    *,
    disposition: str = "open",
    severity: str = "medium",
    impact: str = "bounded",
) -> dict[str, object]:
    return {
        "id": "cluster-one",
        "severity": severity,
        "impact": impact,
        "disposition": disposition,
    }


class BatchRangeDispositionTests(unittest.TestCase):
    def test_final_human_record_binds_exact_capture_set_and_distinct_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence_path = root / "reviews" / "human-disposition.md"
            evidence_path.parent.mkdir(parents=True)
            evidence_payload = b"The reviewed capture set has no material open cluster.\n"
            evidence_path.write_bytes(evidence_payload)
            capture_set = "a" * 64
            record = {
                "status": "no-material-cluster-observed",
                "reviewer_id": "context-reviewer",
                "decided_at": "2026-08-09T20:00:00Z",
                "capture_set_sha256": capture_set,
                "evidence": {
                    "path": "reviews/human-disposition.md",
                    "sha256": hashlib.sha256(evidence_payload).hexdigest(),
                },
                "rationale": "The frozen rendered evidence shows no open material contextual cluster.",
                "finding_ids": [],
            }
            normalized = AUDITOR.validate_human_contextual_disposition(
                record,
                root,
                AUDITOR.EvidenceBudget(),
                expected_capture_set_sha256=capture_set,
                study_frozen_at=AUDITOR.utc_datetime("2026-08-08T12:00:00Z"),
                whole_review_frozen_at="2026-08-09T19:00:00Z",
                finding_records=[],
                reserved_evidence_paths=set(),
                reserved_evidence_hashes=set(),
            )

            self.assertEqual("no-material-cluster-observed", normalized["status"])
            self.assertEqual(capture_set, normalized["capture_set_sha256"])
            self.assertEqual("reviews/human-disposition.md", normalized["evidence"]["path"])

    def test_human_disposition_evidence_must_not_reuse_a_study_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            capture_path = root / "captures" / "wide.png"
            capture_path.parent.mkdir(parents=True)
            payload = b"frozen-existing-study-artifact"
            capture_path.write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            record = {
                "status": "no-material-cluster-observed",
                "reviewer_id": "context-reviewer",
                "decided_at": "2026-08-09T20:00:00Z",
                "capture_set_sha256": "a" * 64,
                "evidence": {"path": "captures/wide.png", "sha256": digest},
                "rationale": "The final human decision is recorded after the frozen whole-system review.",
                "finding_ids": [],
            }

            with self.assertRaises(AUDITOR.AuditError) as raised:
                AUDITOR.validate_human_contextual_disposition(
                    record,
                    root,
                    AUDITOR.EvidenceBudget(),
                    expected_capture_set_sha256="a" * 64,
                    study_frozen_at=AUDITOR.utc_datetime("2026-08-08T12:00:00Z"),
                    whole_review_frozen_at="2026-08-09T19:00:00Z",
                    finding_records=[],
                    reserved_evidence_paths={"captures/wide.png"},
                    reserved_evidence_hashes={digest},
                )

            self.assertEqual("human-disposition-evidence-not-separate", raised.exception.code)

    def test_no_finding_disposition_absent_keeps_protocol_separate(self) -> None:
        human_ready, gaps = AUDITOR.assess_human_contextual_readiness(None, [])
        fields = AUDITOR.batch_readiness_fields(
            comparison_ready=True,
            human_contextual_ready=human_ready,
            disposition=None,
        )

        self.assertFalse(human_ready)
        self.assertEqual(
            {"human-contextual-disposition-missing"},
            {gap["code"] for gap in gaps},
        )
        self.assertTrue(fields["comparison_ready"])
        self.assertFalse(fields["human_contextual_ready"])
        self.assertFalse(fields["final_ready"])
        self.assertEqual(
            "human-contextual-disposition-required",
            fields["decision_status"],
        )

    def test_open_material_finding_blocks_human_closure_not_protocol_coverage(self) -> None:
        disposition = {
            "status": "no-material-cluster-observed",
            "finding_ids": [],
        }
        human_ready, gaps = AUDITOR.assess_human_contextual_readiness(
            disposition,
            [finding(disposition="open", severity="low", impact="material")],
        )
        fields = AUDITOR.batch_readiness_fields(
            comparison_ready=True,
            human_contextual_ready=human_ready,
            disposition=disposition,
        )

        self.assertFalse(human_ready)
        self.assertIn(
            "material-contextual-findings-open",
            {gap["code"] for gap in gaps},
        )
        self.assertTrue(fields["comparison_ready"])
        self.assertFalse(fields["final_ready"])

    def test_resolved_or_explicitly_accepted_material_findings_can_close_human_boundary(self) -> None:
        resolved_disposition = {
            "status": "no-material-cluster-observed",
            "finding_ids": [],
        }
        resolved_ready, resolved_gaps = AUDITOR.assess_human_contextual_readiness(
            resolved_disposition,
            [finding(disposition="resolved", severity="high", impact="material")],
        )
        accepted_disposition = {
            "status": "accepted-contextual-risk",
            "finding_ids": ["cluster-one"],
        }
        accepted_ready, accepted_gaps = AUDITOR.assess_human_contextual_readiness(
            accepted_disposition,
            [
                finding(
                    disposition="accepted-contextual-risk",
                    severity="medium",
                    impact="bounded",
                )
            ],
        )

        self.assertTrue(resolved_ready, resolved_gaps)
        self.assertTrue(accepted_ready, accepted_gaps)
        self.assertTrue(
            AUDITOR.batch_readiness_fields(
                comparison_ready=True,
                human_contextual_ready=resolved_ready,
                disposition=resolved_disposition,
            )["final_ready"]
        )
        self.assertTrue(
            AUDITOR.batch_readiness_fields(
                comparison_ready=True,
                human_contextual_ready=accepted_ready,
                disposition=accepted_disposition,
            )["final_ready"]
        )

    def test_release_blocking_contextual_finding_cannot_close_as_accepted_risk(self) -> None:
        disposition = {
            "status": "accepted-contextual-risk",
            "finding_ids": ["cluster-one"],
        }
        human_ready, gaps = AUDITOR.assess_human_contextual_readiness(
            disposition,
            [
                finding(
                    disposition="accepted-contextual-risk",
                    severity="low",
                    impact="release-blocking",
                )
            ],
        )

        self.assertFalse(human_ready)
        self.assertIn(
            "release-blocking-contextual-findings-unresolved",
            {gap["code"] for gap in gaps},
        )

    def test_cli_requires_final_readiness_not_only_protocol_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "contract.json").write_text("{}", encoding="utf-8")
            report = {
                "coverage_status": "complete",
                "comparison_ready": True,
                "human_contextual_ready": False,
                "final_ready": False,
                "human_contextual_disposition": None,
                "decision_status": "human-contextual-disposition-required",
                "data_handling": {},
            }
            with (
                mock.patch.object(AUDITOR, "validate_contract", return_value=(report, [])),
                redirect_stdout(io.StringIO()),
            ):
                exit_code = AUDITOR.main([
                    str(root),
                    "--contract",
                    "contract.json",
                    "--output",
                    "report.json",
                ])

            self.assertEqual(1, exit_code)

    def test_no_automatic_aesthetic_claim_survives_any_ready_state(self) -> None:
        disposition = {
            "status": "accepted-contextual-risk",
            "finding_ids": ["cluster-one"],
        }
        human_ready, gaps = AUDITOR.assess_human_contextual_readiness(
            disposition,
            [
                finding(
                    disposition="accepted-contextual-risk",
                    severity="medium",
                    impact="bounded",
                )
            ],
        )
        fields = AUDITOR.batch_readiness_fields(
            comparison_ready=True,
            human_contextual_ready=human_ready,
            disposition=disposition,
        )

        self.assertTrue(human_ready, gaps)
        self.assertTrue(fields["final_ready"])
        self.assertFalse(fields["automatic_aesthetic_pass"])
        self.assertEqual(
            "final-human-contextual-disposition-recorded",
            fields["decision_status"],
        )


if __name__ == "__main__":
    unittest.main()
