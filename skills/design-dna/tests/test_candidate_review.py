"""Candidate-specific review provenance; fixtures do not claim aesthetic quality."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SPEC = importlib.util.spec_from_file_location("candidate_review", SCRIPTS / "candidate_review.py")
review = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(review)


def write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class CandidateReviewTests(unittest.TestCase):
    """Synthetic already-validated observation shapes isolate review invariants."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="dna-candidate-review-")
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        state = self.project / ".design-dna"
        state.mkdir()
        self.brief = state / "brief.md"
        self.requirements = {
            "organization": "Arc Camera Supply is an equipment retailer.",
            "audience": "Photographers need to compare camera equipment.",
            "visitor-jobs": "Visitors compare two camera bodies before selection.",
            "content": "Product specifications and truthful pricing are required.",
            "route-jobs": "Direct product entry must explain a single camera.",
            "media": "Product photographs explain controls and camera dimensions.",
            "access": "All comparison actions support keyboard and narrow touch use.",
            "quality": "The product photograph dominates a carefully grouped comparison.",
        }
        self.brief.write_text("\n".join(self.requirements.values()), encoding="utf-8")
        self.observation_file = state / "references/strong-1-observation.json"
        self.observation_file.parent.mkdir()
        self.frames = {}
        states = {}
        for profile in ("wide", "narrow"):
            frame_file = self.observation_file.parent / (profile + ".png")
            # A deterministic valid 1x1 PNG is enough for this record-boundary
            # fixture. Real source raster/quality validation belongs to the callback.
            import base64
            frame_file.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII="))
            binding = self.bind(frame_file)
            state_row = {"id": "rest", "evidence_frames": {"settled": {"file": frame_file.name, "bytes": binding["bytes"], "sha256": binding["sha256"]}},
                "structure": {"dominant": {"tag": "img", "area_share": 0.72 if profile == "wide" else 0.54},
                    "product_relationship": "camera above measurement labels", "headline_size": 64 if profile == "wide" else 34},
                "review_facts": {key: f"Arc camera {key} source measurement at {profile} width" for key in self.requirements}}
            states[profile] = {"rest": state_row}
            self.frames[profile] = {"state_id": "rest", "state_sha256": review.canonical_sha(state_row), "capture": binding}
        self.observation = {"id": "strong-1", "url": "https://example.test/arc-camera/", "tool": "observe_reference.mjs", "schema_version": 5,
            "observed_at": "2026-09-04T00:00:00Z",
            "source_kind": "public-source", "source_study": {"status": "complete", "eligible_for_source_selection": True},
            "states_by_viewport": states}
        write(self.observation_file, self.observation)
        judgments = [{"dimension": key, "brief_excerpt": requirement, "fit": "compatible",
            "reason": f"The Arc camera {key} requirement is supported by the measured product comparison relationship shown in both source captures.",
            "observations": [self.evidence(profile, f"/states_by_viewport/{profile}/rest/review_facts/{key}",
                f"The {profile} source capture exposes the Arc camera {key} information alongside its corresponding product comparison context.") for profile in ("wide", "narrow")]}
            for key, requirement in self.requirements.items()]
        signature = [self.evidence(profile, f"/states_by_viewport/{profile}/rest/structure",
            f"The camera photograph dominates the {profile} opening while measurement labels remain grouped beside the pictured physical controls.") for profile in ("wide", "narrow")]
        experience = {"kind": "composition", "description": "A large isolated camera photograph anchors adjacent physical measurements, making equipment comparison the immediately recognizable opening experience.",
            "signature_evidence": signature,
            "supporting_relationships": [
                {"relationship": "The broad image area keeps physical camera controls legible while adjacent specifications align with their pictured positions.", "evidence": signature[0]},
                {"relationship": "The narrow arrangement places measurements below the product photograph while preserving the same visual comparison hierarchy.", "evidence": signature[1]},
            ],
            "planned_carriers": [{"route_key": "camera", "component_id": "camera-comparison", "transfer_relationship": "The camera route opening preserves the source photograph scale and the associated spatial relationship of physical measurements.", "source_evidence": signature}],
            "deletion_effect": "Removing the camera comparison carrier eliminates the dominant product measurement relationship; isolated source colors would not preserve the experience."}
        self.payload = {"schema_version": 1, "record_type": review.RECORD_TYPE, "candidate_id": "strong-1", "brief": self.bind(self.brief),
            "source": {"id": "strong-1", "url": self.observation["url"], "observation": self.bind(self.observation_file), "states": self.frames},
            "reviewer": {"identity": "independent-source-reviewer", "kind": "independent-agent", "producer_identity": "site-producer", "evidence": {}},
            "reviewed_at": "2026-09-04T01:00:00Z", "judgments": judgments, "dominant_experience": experience, "concerns": [],
            "decision": {"status": "selected", "reason": "The complete camera composition and comparison behavior satisfy the specified product-entry job without introducing a separate producer-created section system."},
            "assurance": {"scope": "attributable-review-evidence-only", "automatic_beauty_verdict": False, "owner_approval": False, "independent_identity_authenticated": False}}
        self.rebind_review()

    def bind(self, file: Path) -> dict:
        data = file.read_bytes()
        return {"path": file.relative_to(self.project).as_posix(), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

    def evidence(self, profile: str, pointer: str, fact: str) -> dict:
        return {"viewport": profile, "state_id": "rest", "capture": self.frames[profile]["capture"], "pointer": pointer,
            "value_sha256": review.canonical_sha(review._pointer(self.observation, pointer)), "observed_fact": fact}

    def rebind_review(self) -> None:
        payload = self.payload
        reviewer = payload["reviewer"]
        original = {"reviewer_identity": reviewer["identity"], "reviewer_kind": reviewer["kind"], "producer_identity": reviewer["producer_identity"],
            "reviewed_at": payload["reviewed_at"], "candidate_id": payload["candidate_id"], "brief_sha256": payload["brief"]["sha256"],
            "observation_sha256": payload["source"]["observation"]["sha256"], "judgments": payload["judgments"],
            "dominant_experience": payload["dominant_experience"], "concerns": payload["concerns"], "decision": payload["decision"]}
        file = self.project / ".design-dna/reviews/original-review.json"
        write(file, original)
        reviewer["evidence"] = self.bind(file)

    def check(self, **overrides) -> list[str]:
        return review.candidate_review_failures(self.project, self.payload, **{
            "brief_path": self.brief, "observation_path": self.observation_file, "candidate_id": "strong-1",
            "validate_observation": lambda value: ["generated source has unresolved render defects"] if value.get("defects") else [], **overrides})

    def test_attributable_complete_specific_review_can_support_selection(self) -> None:
        self.assertEqual([], self.check())

    def test_review_evidence_cannot_alias_external_hardlinked_bytes(self) -> None:
        evidence = self.project / self.payload["reviewer"]["evidence"]["path"]
        with tempfile.TemporaryDirectory(prefix="dna-review-external-") as external:
            os.link(evidence, Path(external) / "aliased-review.json")
            self.assertIn("hardlink", " ".join(self.check()).lower())

    def test_hydrated_cloud_file_is_allowed_but_junction_tag_is_not(self) -> None:
        for tag, blocked in ((0x9000001A, False), (0xA0000003, True), (0xA000000C, True), (0, True)):
            info = SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_file_attributes=0x400, st_reparse_tag=tag)
            with self.subTest(tag=hex(tag)), patch.object(Path, "lstat", return_value=info):
                errors = self.check()
                self.assertEqual(blocked, bool(errors), errors)

    def test_self_review_is_honest_but_not_relabelled_independent(self) -> None:
        self.payload["reviewer"].update(identity="site-producer", kind="producer-self-review")
        self.rebind_review()
        self.assertEqual([], self.check())
        self.payload["reviewer"]["kind"] = "independent-agent"
        self.rebind_review()
        self.assertIn("mislabels producer self-review", " ".join(self.check()))

    def test_generic_passflags_and_prose_do_not_qualify(self) -> None:
        for row in self.payload["judgments"]:
            row["reason"] = "Looks good."
            for observation in row["observations"]:
                observation["observed_fact"] = "Pass."
        self.rebind_review()
        self.assertIn("generic", " ".join(self.check()))

    def test_complete_source_with_mismatched_audience_is_rejected(self) -> None:
        row = next(row for row in self.payload["judgments"] if row["dimension"] == "audience")
        row["fit"] = "mismatch"
        row["reason"] = "The reference targets professional equipment technicians, while this brief serves first-time camera buyers who need introductory explanations."
        self.rebind_review()
        self.assertIn("mismatch audience", " ".join(self.check()))

    def test_rejection_record_is_not_selected_reference(self) -> None:
        self.payload["decision"]["status"] = "rejected"
        self.rebind_review()
        self.assertIn("Rejected or blocked", " ".join(self.check()))
        self.assertEqual([], self.check(require_selected=False))

    def test_unresolved_negative_quality_cannot_be_hidden_by_selected_decision(self) -> None:
        self.payload["concerns"] = [{"description": "The dominant product image is visibly clipped in the narrow capture, obscuring controls that the comparison job needs.",
            "status": "unresolved", "resolution": "", "evidence": self.payload["dominant_experience"]["signature_evidence"][1]}]
        self.rebind_review()
        self.assertIn("unresolved negative", " ".join(self.check()))

    def test_full_source_validator_failure_is_not_overridden_by_review(self) -> None:
        self.assertIn("observer incomplete", " ".join(self.check(validate_observation=lambda value: ["observer incomplete"])))

    def test_bool_source_pass_cannot_replace_generated_source_validator(self) -> None:
        self.assertIn("pass flag", " ".join(self.check(validate_observation=True)))

    def test_current_brief_drift_reopens_review(self) -> None:
        self.brief.write_text(self.brief.read_text() + "\nAudience changed.", encoding="utf-8")
        self.assertIn("bytes drifted", " ".join(self.check()))

    def test_fake_brief_excerpt_cannot_supply_fit_evidence(self) -> None:
        self.payload["judgments"][0]["brief_excerpt"] = "An invented organization that does not appear in the brief."
        self.rebind_review()
        self.assertIn("real current brief requirement", " ".join(self.check()))

    def test_original_reviewer_artifact_must_match_exact_candidate_review(self) -> None:
        self.payload["judgments"][0]["fit"] = "not-applicable"
        self.assertIn("original attributable reviewer", " ".join(self.check()))

    def test_missing_narrow_review_is_not_supported_by_wide_screenshot(self) -> None:
        self.payload["judgments"][0]["observations"] = self.payload["judgments"][0]["observations"][:1]
        self.rebind_review()
        self.assertIn("wide/narrow", " ".join(self.check()))

    def test_measured_value_hash_cannot_point_to_another_source_fact(self) -> None:
        self.payload["judgments"][0]["observations"][0]["value_sha256"] = "a" * 64
        self.rebind_review()
        self.assertIn("exact measured source fact", " ".join(self.check()))

    def test_generic_type_token_is_not_dominant_composition_evidence(self) -> None:
        for row in self.payload["dominant_experience"]["signature_evidence"]:
            profile = row["viewport"]
            row["pointer"] = f"/states_by_viewport/{profile}/rest/structure/headline_size"
            row["value_sha256"] = review.canonical_sha(review._pointer(self.observation, row["pointer"]))
        self.rebind_review()
        self.assertIn("not a color/font/card token", " ".join(self.check()))

    def test_source_without_planned_signature_carrier_is_not_selected(self) -> None:
        self.payload["dominant_experience"]["planned_carriers"] = []
        self.rebind_review()
        self.assertIn("no planned route/component carrier", " ".join(self.check()))

    def test_a_different_source_cannot_reuse_this_reviews_identity(self) -> None:
        self.payload["source"]["url"] = "https://example.test/mismatched-source/"
        self.rebind_review()
        self.assertIn("source identity differs", " ".join(self.check()))

    def test_repeated_fit_rationale_is_not_eight_distinct_brief_judgments(self) -> None:
        reason = self.payload["judgments"][0]["reason"]
        for row in self.payload["judgments"]:
            row["reason"] = reason
        self.rebind_review()
        self.assertIn("repeats generic rationale", " ".join(self.check()))

    def test_record_cannot_claim_automatic_beauty_or_owner_approval(self) -> None:
        self.payload["assurance"]["owner_approval"] = True
        self.assertIn("must not claim", " ".join(self.check()))

    def test_review_cannot_predate_the_generated_source_capture(self) -> None:
        self.payload["reviewed_at"] = "2026-09-03T23:00:00Z"
        self.rebind_review()
        self.assertIn("predates the generated", " ".join(self.check()))

    def test_initializer_creates_only_blocked_non_overwriting_scaffold(self) -> None:
        command = [sys.executable, "-B", str(SCRIPTS / "init_project_state.py"), "--project", str(self.project),
            "--init-candidate-review", "strong-1", "--candidate-brief", str(self.brief)]
        created = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=45)
        self.assertEqual(0, created.returncode, created.stdout + created.stderr)
        result = json.loads(created.stdout)
        self.assertEqual("blocked-pending-review", result["status"])
        self.assertFalse(result["eligible_for_source_selection"])
        scaffold = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
        self.assertTrue(review.candidate_review_failures(self.project, scaffold, brief_path=self.brief,
            observation_path=self.observation_file, candidate_id="strong-1", validate_observation=lambda value: []))
        repeated = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=45)
        self.assertNotEqual(0, repeated.returncode)
        self.assertEqual(scaffold, json.loads(Path(result["path"]).read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
