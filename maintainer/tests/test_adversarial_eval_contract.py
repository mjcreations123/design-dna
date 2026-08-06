from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator


PLUGIN = Path(__file__).resolve().parents[2]
SCRIPTS = PLUGIN / "maintainer" / "scripts"

sys.path.insert(0, str(SCRIPTS))
try:
    import audit_package
    import run_evals
finally:
    sys.path.pop(0)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def rubric_score(
    value: int,
    *,
    path: str = "evidence/render.png",
    sha256: str = "2" * 64,
) -> dict[str, object]:
    return {
        "value": value,
        "rationale": "The bound rendered evidence supports this dimension score.",
        "evidence": [{"path": path, "sha256": sha256}],
    }


def schema_review(
    owner_disposition: dict[str, object],
    *,
    decision: str = "pass",
) -> dict[str, object]:
    rubric_dimensions = (
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
    return {
        "schema_version": 3,
        "case_id": "owner-review",
        "run_id": "suite:codex:owner-review:skill:1",
        "build": {
            "identity": "build-42",
            "host": "codex",
            "skill_version": "3.0.0",
            "content_sha256": "1" * 64,
            "captured_at": "2026-07-29T12:00:00Z",
            "producer_id": "producer-42",
        },
        "blinded_variant": "variant-a",
        "reviewer": {
            "id": "reviewer-42",
            "lens": "perception",
            "independent": True,
            "process": {
                "id": "review-process-42",
                "method": "separate-person",
                "performed_at": "2026-07-29T12:00:00Z",
                "evidence_path": "evidence/process.txt",
            },
        },
        "contexts": [{
            "route": "/",
            "state": "default",
            "viewport": {
                "width": 1440,
                "height": 900,
                "device_pixel_ratio": 1,
            },
            "browser": "Chromium",
            "environment": {
                "input_modalities": ["keyboard", "pointer"],
                "zoom_percent": 100,
                "text_scale_percent": 100,
                "reduced_motion": "no-preference",
                "forced_colors": "none",
                "contrast_preference": "no-preference",
                "theme": "light",
                "locale": "en-US",
                "direction": "ltr",
            },
            "checks": [{
                "id": "visual-layout",
                "status": "passed",
                "method": "Reviewed the rendered desktop candidate.",
                "evidence": [{
                    "path": "evidence/render.png",
                    "sha256": "2" * 64,
                }],
            }],
            "render_evidence": {
                "path": "evidence/render.png",
                "sha256": "2" * 64,
                "media_type": "image/png",
                "pixel_width": 1440,
                "pixel_height": 900,
            },
        }],
        "rubric": {
            dimension: rubric_score(2) for dimension in rubric_dimensions
        },
        "critical_blockers": [],
        "findings": [],
        "owner_disposition": owner_disposition,
        "evidence_paths": [
            "evidence/process.txt",
            "evidence/render.png",
            "evidence/owner.txt",
        ],
        "checks": {
            "tested": ["Rendered visual review"],
            "unperformed": [],
        },
        "conclusion": {
            "decision": decision,
            "rationale": "The recorded review supports this disposition.",
        },
    }


def release_case(
    case_id: str,
    *,
    mode: str,
    scope: str,
    stratum: str,
    adversarial: bool = False,
    expressive: bool = False,
    quiet: bool = False,
    generated_media: bool = False,
) -> dict[str, object]:
    case = {
        "id": case_id,
        "task": f"Build the {case_id} fixture.",
        "adversarial": adversarial,
        "review_requirements": [
            f"Inspect the rendered {case_id} result after revision."
        ],
        "release_coverage": {
            "high_value": True,
            "representative": True,
            "primary_mode": mode,
            "scope": scope,
            "project_stratum": stratum,
        },
    }
    if expressive:
        case["release_coverage"]["expressive_perception_gate"] = True
    if quiet:
        case["release_coverage"]["quiet_perception_gate"] = True
    if generated_media:
        case["release_coverage"]["generated_media_capability_gate"] = True
        case["capability_contract"] = {
            "image_generation": "required-when-host-declared-available"
        }
    return case


def run_record(
    case: dict[str, object],
    variant: str,
    number: int,
    workspace_sha256: str,
    *,
    implicit_bound: bool = False,
) -> dict[str, object]:
    return {
        "case": case["id"],
        "variant": variant,
        "run_id": f"suite:codex:{case['id']}:{variant}:{number}",
        "passed": True,
        "workspace_sha256": workspace_sha256,
        "invocation_mode": "implicit" if implicit_bound else "explicit",
        "host_native_evidence_status": "bound" if implicit_bound else "bound",
        "review_contract": run_evals.case_review_contract(case),
    }


def coverage_runs(
    cases: list[dict[str, object]],
) -> list[tuple[Path, dict[str, object]]]:
    records: list[tuple[Path, dict[str, object]]] = []
    for case_index, case in enumerate(cases):
        for variant in ("skill", "baseline"):
            for number in range(1, 4):
                variant_offset = 0 if variant == "skill" else 20
                hash_digit = (
                    case_index + variant_offset + (number if variant == "skill" else 1)
                ) % 16
                workspace_hash = f"{hash_digit:x}" * 64
                implicit = (
                    case["id"] == "implicit-case"
                    and variant == "skill"
                    and number == 1
                )
                run = run_record(
                    case,
                    variant,
                    number,
                    workspace_hash,
                    implicit_bound=implicit,
                )
                records.append((Path(f"{run['run_id']}.json"), run))
    return records


def comparison_for(case_metadata: dict[str, object]) -> dict[str, object]:
    observations = []
    for variant in ("skill", "baseline"):
        for record in case_metadata[f"{variant}_run_artifacts"]:
            run_evidence = [{
                "path": (
                    "evidence/runs/"
                    + digest(str(record["run_id"]))[:16]
                    + ".png"
                ),
                "sha256": digest(str(record["run_id"])),
            }]
            observations.append({
                "variant": variant,
                "run_id": record["run_id"],
                "workspace_sha256": record["workspace_sha256"],
                "basis": "rendered",
                "observation": (
                    f"Reviewed {variant} run {record['run_id']} for repeated quality."
                ),
                "evidence": run_evidence,
            })
    evidence = [{"path": "evidence/comparison.json", "sha256": "a" * 64}]
    return {
        "schema_version": 1,
        "skill_runs": deepcopy(case_metadata["skill_run_artifacts"]),
        "baseline_runs": deepcopy(case_metadata["baseline_run_artifacts"]),
        "criteria": [
            {
                "dimension": "project_specificity",
                "outcome": "skill-stronger",
                "rationale": (
                    "The skill variants preserve more task-specific content and hierarchy."
                ),
                "evidence": evidence,
            },
            {
                "dimension": "distinctiveness_without_novelty_tax",
                "outcome": "skill-stronger",
                "rationale": (
                    "The skill variants vary their composition without breaking conventions."
                ),
                "evidence": evidence,
            },
            {
                "dimension": "copy_ia",
                "outcome": "mixed",
                "rationale": (
                    "Both variants are usable, while the skill variants use more concrete labels."
                ),
                "evidence": evidence,
            },
        ],
        "convergence": {
            "artifact_identity": case_metadata["skill_artifact_identity"],
            "artifact_identity_interpretation": (
                "Artifact hash identity is interpreted alongside the rendered "
                "per-run observations, not as proof of quality by itself."
            ),
            "quality_consistency": "consistent",
            "summary": (
                "Repeated skill outputs remain strong while retaining meaningful variation."
            ),
            "run_observations": observations,
        },
        "evidence": evidence,
    }


class ReviewContractTests(unittest.TestCase):
    def test_runner_and_auditor_compute_the_same_immutable_contract(self) -> None:
        case = release_case(
            "specificity-case",
            mode="persuade",
            scope="new-build",
            stratum="static-site",
            adversarial=True,
        )
        runner_contract = run_evals.case_review_contract(case)
        auditor_contract = audit_package.case_review_contract(case)
        self.assertEqual(runner_contract, auditor_contract)
        self.assertTrue(runner_contract["adversarial_required"])
        self.assertRegex(
            runner_contract["requirements"][0]["id"],
            r"^requirement-01-[0-9a-f]{16}$",
        )

        changed = deepcopy(case)
        changed["review_requirements"].append("Inspect aggregate heading cadence.")
        self.assertNotEqual(
            runner_contract["sha256"],
            run_evals.case_review_contract(changed)["sha256"],
        )

    def test_release_closure_is_required_exact_and_verified(self) -> None:
        case = release_case(
            "closure-case",
            mode="operate",
            scope="redesign",
            stratum="established-interface",
        )
        contract = run_evals.case_review_contract(case)
        review = {
            "reviewer": {"lens": "perception"},
            "conclusion": {"decision": "pass"},
        }
        missing, qualified = audit_package.review_contract_closure_failures(
            review,
            contract,
            "review.json",
        )
        self.assertFalse(qualified)
        self.assertIn(
            "release-review-requirement-closure-missing",
            {item["code"] for item in missing},
        )

        requirement = contract["requirements"][0]
        review["requirement_closure"] = {
            "contract_sha256": contract["sha256"],
            "adversarial": False,
            "requirements": [{
                "id": requirement["id"],
                "status": "not-applicable",
                "rationale": "The reviewer considered this requirement inapplicable.",
                "finding_ids": [],
                "evidence": [{"path": "evidence/review.txt", "sha256": "a" * 64}],
            }],
        }
        failures, qualified = audit_package.review_contract_closure_failures(
            review,
            contract,
            "review.json",
        )
        self.assertFalse(qualified)
        self.assertIn(
            "release-review-requirement-unverified",
            {item["code"] for item in failures},
        )

        review["requirement_closure"]["requirements"][0]["status"] = "verified"
        review["requirement_closure"]["contract_sha256"] = "f" * 64
        failures, qualified = audit_package.review_contract_closure_failures(
            review,
            contract,
            "review.json",
        )
        self.assertFalse(qualified)
        self.assertIn(
            "release-review-contract-unbound",
            {item["code"] for item in failures},
        )

        review["requirement_closure"]["contract_sha256"] = contract["sha256"]
        failures, qualified = audit_package.review_contract_closure_failures(
            review,
            contract,
            "review.json",
        )
        self.assertEqual(failures, [])
        self.assertTrue(qualified)

    def test_expressive_release_contract_requires_both_absolute_scores(
        self,
    ) -> None:
        case = release_case(
            "showcase-floor",
            mode="experience",
            scope="new-build",
            stratum="static-site",
            expressive=True,
        )
        contract = run_evals.case_review_contract(case)
        requirement = contract["requirements"][0]
        review = {
            "reviewer": {"lens": "perception"},
            "rubric": {
                "direction": rubric_score(2),
                "distinctiveness_without_novelty_tax": rubric_score(3),
            },
            "conclusion": {"decision": "pass"},
            "requirement_closure": {
                "contract_sha256": contract["sha256"],
                "adversarial": False,
                "requirements": [{
                    "id": requirement["id"],
                    "status": "verified",
                    "rationale": "The exact requirement was verified.",
                    "finding_ids": [],
                    "evidence": [{
                        "path": "evidence/showcase.txt",
                        "sha256": "a" * 64,
                    }],
                }],
            },
        }
        failures, qualified = audit_package.review_contract_closure_failures(
            review,
            contract,
            "showcase.json",
        )
        self.assertFalse(qualified)
        self.assertIn(
            "release-expressive-perception-floor-unmet",
            {item["code"] for item in failures},
        )

        review["rubric"]["direction"]["value"] = 3
        failures, qualified = audit_package.review_contract_closure_failures(
            review,
            contract,
            "showcase.json",
        )
        self.assertEqual(failures, [])
        self.assertTrue(qualified)

    def test_quiet_release_contract_requires_specificity_without_volume(
        self,
    ) -> None:
        case = release_case(
            "quiet-floor",
            mode="persuade",
            scope="new-build",
            stratum="static-site",
            quiet=True,
        )
        contract = run_evals.case_review_contract(case)
        requirement = contract["requirements"][0]
        review = {
            "reviewer": {"lens": "perception"},
            "rubric": {
                "direction": rubric_score(3),
                "project_specificity": rubric_score(2),
                "distinctiveness_without_novelty_tax": rubric_score(3),
            },
            "conclusion": {"decision": "pass"},
            "requirement_closure": {
                "contract_sha256": contract["sha256"],
                "adversarial": False,
                "requirements": [{
                    "id": requirement["id"],
                    "status": "verified",
                    "rationale": (
                        "The quiet result was reviewed for authored restraint."
                    ),
                    "finding_ids": [],
                    "evidence": [{
                        "path": "evidence/quiet.txt",
                        "sha256": "a" * 64,
                    }],
                }],
            },
        }
        failures, qualified = audit_package.review_contract_closure_failures(
            review,
            contract,
            "quiet.json",
        )
        self.assertFalse(qualified)
        self.assertIn(
            "release-quiet-perception-floor-unmet",
            {item["code"] for item in failures},
        )

        review["rubric"]["project_specificity"]["value"] = 3
        failures, qualified = audit_package.review_contract_closure_failures(
            review,
            contract,
            "quiet.json",
        )
        self.assertEqual(failures, [])
        self.assertTrue(qualified)

    def test_generated_media_contract_requires_an_honest_capability_branch(
        self,
    ) -> None:
        case = release_case(
            "generated-media-floor",
            mode="persuade",
            scope="new-build",
            stratum="static-site",
            generated_media=True,
        )
        contract = run_evals.case_review_contract(case)
        requirement = contract["requirements"][0]
        review = {
            "reviewer": {"lens": "perception"},
            "conclusion": {"decision": "pass"},
            "requirement_closure": {
                "contract_sha256": contract["sha256"],
                "adversarial": False,
                "requirements": [{
                    "id": requirement["id"],
                    "status": "verified",
                    "rationale": "The exact conditional requirement was verified.",
                    "finding_ids": [],
                    "evidence": [{
                        "path": "evidence/capability.txt",
                        "sha256": "a" * 64,
                    }],
                }],
            },
        }
        failures, qualified = audit_package.review_contract_closure_failures(
            review,
            contract,
            "generated.json",
        )
        self.assertFalse(qualified)
        self.assertIn(
            "release-generated-media-capability-disposition-missing",
            {item["code"] for item in failures},
        )

        review["capability_disposition"] = {
            "image_generation": {
                "status": "unavailable",
                "rationale": "The bound host record reports no image generator.",
                "availability_evidence": [{
                    "path": "evidence/capability.txt",
                    "sha256": "a" * 64,
                }],
                "generated_artifacts": [],
                "inspection_evidence": [],
            }
        }
        failures, qualified = audit_package.review_contract_closure_failures(
            review,
            contract,
            "generated.json",
        )
        self.assertEqual(failures, [])
        self.assertTrue(qualified)

        image_generation = review["capability_disposition"]["image_generation"]
        image_generation["status"] = "available"
        failures, qualified = audit_package.review_contract_closure_failures(
            review,
            contract,
            "generated.json",
        )
        self.assertFalse(qualified)
        self.assertIn(
            "release-generated-media-artifact-evidence-missing",
            {item["code"] for item in failures},
        )

    def test_capability_disposition_schema_separates_available_and_unavailable(
        self,
    ) -> None:
        schema = json.loads(
            (PLUGIN / "maintainer" / "schemas" / "design-review.schema.json")
            .read_text(encoding="utf-8")
        )
        disposition_schema = {
            "$schema": schema["$schema"],
            "$defs": schema["$defs"],
            "$ref": "#/$defs/capability_disposition",
        }
        validator = Draft202012Validator(disposition_schema)
        evidence = [{
            "path": "evidence/capability.txt",
            "sha256": "a" * 64,
        }]
        unavailable = {
            "image_generation": {
                "status": "unavailable",
                "rationale": "The bound host record reports no image generator.",
                "availability_evidence": evidence,
                "generated_artifacts": [],
                "inspection_evidence": [],
            }
        }
        self.assertEqual(list(validator.iter_errors(unavailable)), [])

        available = deepcopy(unavailable)
        available["image_generation"]["status"] = "available"
        self.assertTrue(list(validator.iter_errors(available)))
        available["image_generation"]["generated_artifacts"] = [{
            "path": "evidence/concept.webp",
            "sha256": "b" * 64,
        }]
        available["image_generation"]["inspection_evidence"] = [{
            "path": "evidence/contact-sheet.png",
            "sha256": "c" * 64,
        }]
        self.assertEqual(list(validator.iter_errors(available)), [])

    def test_masked_layout_schema_requires_complete_hash_bound_record(
        self,
    ) -> None:
        schema = json.loads(
            (PLUGIN / "maintainer" / "schemas" / "design-review.schema.json")
            .read_text(encoding="utf-8")
        )
        comparison_schema = {
            "$schema": schema["$schema"],
            "$defs": schema["$defs"],
            "$ref": "#/$defs/masked_layout_comparison",
        }
        validator = Draft202012Validator(comparison_schema)
        coverage = []
        for index in range(4):
            source_hashes = [
                digest(f"source:{index}:mobile"),
                digest(f"source:{index}:desktop"),
            ]
            masked_hashes = [
                digest(f"masked:{index}:mobile"),
                digest(f"masked:{index}:desktop"),
            ]
            coverage.append({
                "case_id": f"case-{index}",
                "run_id": f"suite:codex:case-{index}:skill:1",
                "build_identity": digest(f"build:{index}"),
                "source_render_sha256s": source_hashes,
                "masked_render_sha256s": masked_hashes,
                "evidence": [
                    {
                        "path": f"evidence/masked-{index}-mobile.png",
                        "sha256": masked_hashes[0],
                    },
                    {
                        "path": f"evidence/masked-{index}-desktop.png",
                        "sha256": masked_hashes[1],
                    },
                ],
            })
        comparison = {
            "method": (
                "Replaced copy, logos, and dominant media with neutral blocks "
                "while preserving responsive layout geometry."
            ),
            "masking": {
                "copy": "replaced-with-neutral-placeholder",
                "logos": "masked",
                "dominant_media": "replaced-with-neutral-placeholder",
            },
            "layout_geometry_preserved": True,
            "coverage": coverage,
            "observations": [{
                "case_ids": [record["case_id"] for record in coverage],
                "outcome": "meaningful-structural-difference",
                "assessment": (
                    "The masked renders retain different organization and "
                    "attention paths across the counted cases."
                ),
                "cluster_id": None,
                "evidence": coverage[0]["evidence"],
            }],
            "limitations": [
                "Masking does not establish authorship or complete design quality."
            ],
            "authorship_inference": "not-performed",
            "evidence": [{
                "path": "evidence/masked-comparison.json",
                "sha256": digest("masked-comparison"),
            }],
        }
        self.assertEqual(list(validator.iter_errors(comparison)), [])

        missing_logo_treatment = deepcopy(comparison)
        del missing_logo_treatment["masking"]["logos"]
        self.assertTrue(list(validator.iter_errors(missing_logo_treatment)))

        incomplete_coverage = deepcopy(comparison)
        incomplete_coverage["coverage"].pop()
        self.assertTrue(list(validator.iter_errors(incomplete_coverage)))

        authorship_claim = deepcopy(comparison)
        authorship_claim["authorship_inference"] = "human-authored"
        self.assertTrue(list(validator.iter_errors(authorship_claim)))

    def test_schema_v3_requires_finding_lifecycle_evidence(self) -> None:
        schema = json.loads(
            (PLUGIN / "maintainer" / "schemas" / "design-review.schema.json")
            .read_text(encoding="utf-8")
        )
        finding_schema = {
            "$schema": schema["$schema"],
            "$defs": schema["$defs"],
            "$ref": "#/$defs/lifecycle_finding",
        }
        validator = Draft202012Validator(finding_schema)
        finding = {
            "id": "generic-hero",
            "status": "verified",
            "severity": "medium",
            "dimension": "project_specificity",
            "observation": "The hero is generic.",
            "cause": "No project-specific premise was expressed.",
            "recommendation": "Rebuild the hero around the supplied service constraint.",
            "evidence_path": "evidence/hero.png",
            "resolution": None,
            "verification": None,
        }
        self.assertTrue(list(validator.iter_errors(finding)))

        evidence = [{"path": "evidence/hero.png", "sha256": "a" * 64}]
        finding["resolution"] = {
            "summary": "Rebuilt the hierarchy around the supplied service constraint.",
            "owner_id": "builder-alpha",
            "decided_at": "2026-07-28T12:00:00Z",
            "evidence": evidence,
        }
        finding["verification"] = {
            "method": "Independent rendered comparison at mobile and desktop widths.",
            "verifier_id": "reviewer-beta",
            "performed_at": "2026-07-28T12:30:00Z",
            "evidence": evidence,
        }
        self.assertEqual(list(validator.iter_errors(finding)), [])

        finding["status"] = "open"
        self.assertTrue(list(validator.iter_errors(finding)))

    def test_unresolved_medium_finding_cannot_pass(self) -> None:
        payload = {
            "schema_version": 3,
            "evidence_paths": [],
            "findings": [{
                "id": "generic-hero",
                "status": "open",
                "severity": "medium",
                "dimension": "project_specificity",
                "observation": "The hero is generic.",
                "cause": "No project-specific premise was expressed.",
                "recommendation": "Revise the hierarchy.",
                "resolution": None,
                "verification": None,
            }],
            "critical_blockers": [],
            "checks": {"tested": [], "unperformed": []},
            "rubric": {},
            "conclusion": {"decision": "pass", "rationale": "Passed."},
        }
        with tempfile.TemporaryDirectory() as temporary:
            failures = audit_package.review_semantic_failures(
                payload,
                Path(temporary),
                "review.json",
                release_mode=False,
            )
        self.assertIn("review-false-pass", {item["code"] for item in failures})

    def test_owner_disposition_schema_binds_decision_shape_and_rejection(
        self,
    ) -> None:
        schema = json.loads(
            (PLUGIN / "maintainer" / "schemas" / "design-review.schema.json")
            .read_text(encoding="utf-8")
        )
        validator = Draft202012Validator(schema)
        accepted = {
            "status": "accepted",
            "claim_scope": "standard",
            "reviewer_relationship": "accountable-owner",
            "decision_owner_id": "owner-alex-morgan",
            "candidate_id": "build-42",
            "reviewed_at": "2026-07-29T13:00:00Z",
            "rationale": "The accountable owner accepted this exact rendered build.",
            "evidence": [{
                "path": "evidence/owner.txt",
                "sha256": "3" * 64,
            }],
        }
        review = schema_review(accepted)
        self.assertEqual(list(validator.iter_errors(review)), [])

        bare_numeric_score = deepcopy(review)
        bare_numeric_score["rubric"]["typography"] = 2
        self.assertTrue(list(validator.iter_errors(bare_numeric_score)))

        unbound_score = deepcopy(review)
        del unbound_score["rubric"]["typography"]["evidence"]
        self.assertTrue(list(validator.iter_errors(unbound_score)))

        developer_compatible = deepcopy(review)
        del developer_compatible["owner_disposition"]
        self.assertEqual(
            list(validator.iter_errors(developer_compatible)),
            [],
        )

        no_evidence = deepcopy(review)
        no_evidence["owner_disposition"]["evidence"] = []
        self.assertTrue(list(validator.iter_errors(no_evidence)))

        rejected_pass = deepcopy(review)
        rejected_pass["owner_disposition"]["status"] = "rejected"
        self.assertTrue(list(validator.iter_errors(rejected_pass)))

        rejected_revise = deepcopy(rejected_pass)
        rejected_revise["conclusion"]["decision"] = "revise"
        self.assertEqual(list(validator.iter_errors(rejected_revise)), [])

        pending_with_evidence = deepcopy(review)
        pending_with_evidence["owner_disposition"].update({
            "status": "pending",
            "reviewer_relationship": "not-reviewed",
            "reviewed_at": None,
        })
        self.assertEqual(
            list(validator.iter_errors(pending_with_evidence)),
            [],
        )

        not_required_without_evidence = deepcopy(review)
        not_required_without_evidence["owner_disposition"].update({
            "status": "not-required",
            "evidence": [],
        })
        self.assertTrue(
            list(validator.iter_errors(not_required_without_evidence))
        )

        standard_not_required = deepcopy(review)
        standard_not_required["owner_disposition"]["status"] = (
            "not-required"
        )
        self.assertEqual(
            list(validator.iter_errors(standard_not_required)),
            [],
        )

        premium_not_required = deepcopy(review)
        premium_not_required["owner_disposition"].update({
            "status": "not-required",
            "claim_scope": "premium-showcase-sale-readiness",
        })
        self.assertTrue(list(validator.iter_errors(premium_not_required)))

    def test_owner_disposition_release_enforcement_fails_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = Path(temporary)
            evidence = plugin / "evidence" / "owner.txt"
            evidence.parent.mkdir(parents=True)
            evidence.write_text(
                (
                    "status: accepted\n"
                    "decision_owner_id: owner-alex-morgan\n"
                    "candidate_id: build-42\n"
                    "reviewed_at: 2026-07-26T13:00:00Z\n"
                ),
                encoding="utf-8",
            )
            evidence_hash = hashlib.sha256(evidence.read_bytes()).hexdigest()
            accepted = {
                "build": {
                    "identity": "build-42",
                    "captured_at": "2026-07-26T12:00:00Z",
                },
                "owner_disposition": {
                    "status": "accepted",
                    "claim_scope": "standard",
                    "reviewer_relationship": "accountable-owner",
                    "decision_owner_id": "owner-alex-morgan",
                    "candidate_id": "build-42",
                    "reviewed_at": "2026-07-26T13:00:00Z",
                    "rationale": "The owner accepted the exact rendered candidate.",
                    "evidence": [{
                        "path": "evidence/owner.txt",
                        "sha256": evidence_hash,
                    }],
                },
                "conclusion": {
                    "decision": "pass",
                    "rationale": "The review passed.",
                },
            }
            evidence_keys = {"evidence/owner.txt"}
            self.assertEqual(
                audit_package.review_owner_disposition_failures(
                    accepted,
                    plugin,
                    "review.json",
                    evidence_keys,
                    release_mode=True,
                ),
                [],
            )

            missing = {"build": {"identity": "build-42"}}
            self.assertEqual(
                audit_package.review_owner_disposition_failures(
                    missing,
                    plugin,
                    "review.json",
                    set(),
                    release_mode=False,
                ),
                [],
            )
            self.assertIn(
                "release-owner-disposition-missing",
                {
                    item["code"]
                    for item in audit_package.review_owner_disposition_failures(
                        missing,
                        plugin,
                        "review.json",
                        set(),
                        release_mode=True,
                    )
                },
            )

            pending = deepcopy(accepted)
            pending["owner_disposition"].update({
                "status": "pending",
                "reviewer_relationship": "not-reviewed",
                "reviewed_at": None,
            })
            pending_failures = (
                audit_package.review_owner_disposition_failures(
                    pending,
                    plugin,
                    "review.json",
                    evidence_keys,
                    release_mode=True,
                )
            )
            pending_codes = {item["code"] for item in pending_failures}
            self.assertIn(
                "release-owner-disposition-pending",
                pending_codes,
            )
            self.assertFalse(
                {
                    "review-owner-evidence-content-invalid",
                    "review-owner-evidence-format-invalid",
                    "review-owner-evidence-unattributed",
                }
                & pending_codes,
            )

            generic_owner = deepcopy(accepted)
            generic_owner["owner_disposition"]["decision_owner_id"] = (
                "accountable-owner"
            )
            self.assertIn(
                "review-owner-identity-invalid",
                {
                    item["code"]
                    for item in audit_package.review_owner_disposition_failures(
                        generic_owner,
                        plugin,
                        "review.json",
                        evidence_keys,
                        release_mode=True,
                    )
                },
            )

            rejected_pass = deepcopy(accepted)
            rejected_pass["owner_disposition"]["status"] = "rejected"
            self.assertIn(
                "review-owner-rejection-false-pass",
                {
                    item["code"]
                    for item in audit_package.review_owner_disposition_failures(
                        rejected_pass,
                        plugin,
                        "review.json",
                        evidence_keys,
                        release_mode=False,
                    )
                },
            )

            mismatched_candidate = deepcopy(accepted)
            mismatched_candidate["owner_disposition"]["candidate_id"] = (
                "build-41"
            )
            self.assertIn(
                "review-owner-candidate-mismatch",
                {
                    item["code"]
                    for item in audit_package.review_owner_disposition_failures(
                        mismatched_candidate,
                        plugin,
                        "review.json",
                        evidence_keys,
                        release_mode=True,
                    )
                },
            )

            before_build = deepcopy(accepted)
            before_build["owner_disposition"]["reviewed_at"] = (
                "2026-07-26T11:59:59Z"
            )
            self.assertIn(
                "review-owner-review-before-build",
                {
                    item["code"]
                    for item in audit_package.review_owner_disposition_failures(
                        before_build,
                        plugin,
                        "review.json",
                        evidence_keys,
                        release_mode=True,
                    )
                },
            )

            future_review = deepcopy(accepted)
            future_review["owner_disposition"]["reviewed_at"] = (
                "2099-07-29T13:00:00Z"
            )
            self.assertIn(
                "review-owner-review-in-future",
                {
                    item["code"]
                    for item in audit_package.review_owner_disposition_failures(
                        future_review,
                        plugin,
                        "review.json",
                        evidence_keys,
                        release_mode=True,
                    )
                },
            )

            empty_evidence = plugin / "evidence" / "empty.txt"
            empty_evidence.write_bytes(b"")
            empty_record = deepcopy(accepted)
            empty_record["owner_disposition"]["evidence"] = [{
                "path": "evidence/empty.txt",
                "sha256": hashlib.sha256(b"").hexdigest(),
            }]
            self.assertIn(
                "review-owner-evidence-content-invalid",
                {
                    item["code"]
                    for item in audit_package.review_owner_disposition_failures(
                        empty_record,
                        plugin,
                        "review.json",
                        evidence_keys | {"evidence/empty.txt"},
                        release_mode=True,
                    )
                },
            )

            binary_evidence = plugin / "evidence" / "owner.png"
            binary_evidence.write_bytes(b"not-a-decision-record")
            binary_record = deepcopy(accepted)
            binary_record["owner_disposition"]["evidence"] = [{
                "path": "evidence/owner.png",
                "sha256": hashlib.sha256(
                    binary_evidence.read_bytes()
                ).hexdigest(),
            }]
            self.assertIn(
                "review-owner-evidence-format-invalid",
                {
                    item["code"]
                    for item in audit_package.review_owner_disposition_failures(
                        binary_record,
                        plugin,
                        "review.json",
                        evidence_keys | {"evidence/owner.png"},
                        release_mode=True,
                    )
                },
            )

            irrelevant_evidence = plugin / "evidence" / "irrelevant.txt"
            irrelevant_evidence.write_text(
                "The page looks fine.\n",
                encoding="utf-8",
            )
            irrelevant_record = deepcopy(accepted)
            irrelevant_record["owner_disposition"]["evidence"] = [{
                "path": "evidence/irrelevant.txt",
                "sha256": hashlib.sha256(
                    irrelevant_evidence.read_bytes()
                ).hexdigest(),
            }]
            self.assertIn(
                "review-owner-evidence-unattributed",
                {
                    item["code"]
                    for item in audit_package.review_owner_disposition_failures(
                        irrelevant_record,
                        plugin,
                        "review.json",
                        evidence_keys | {"evidence/irrelevant.txt"},
                        release_mode=True,
                    )
                },
            )

            premium_not_required = deepcopy(accepted)
            premium_not_required["owner_disposition"].update({
                "status": "not-required",
                "claim_scope": "premium-showcase-sale-readiness",
            })
            self.assertIn(
                "release-owner-not-required-ineligible",
                {
                    item["code"]
                    for item in audit_package.review_owner_disposition_failures(
                        premium_not_required,
                        plugin,
                        "review.json",
                        evidence_keys,
                        release_mode=True,
                    )
                },
            )

            not_required_evidence = (
                plugin / "evidence" / "not-required.txt"
            )
            not_required_evidence.write_text(
                (
                    "status: not-required\n"
                    "decision_owner_id: owner-alex-morgan\n"
                    "candidate_id: build-42\n"
                    "reviewed_at: 2026-07-26T13:00:00Z\n"
                ),
                encoding="utf-8",
            )
            standard_not_required = deepcopy(accepted)
            standard_not_required["owner_disposition"].update({
                "status": "not-required",
                "evidence": [{
                    "path": "evidence/not-required.txt",
                    "sha256": hashlib.sha256(
                        not_required_evidence.read_bytes()
                    ).hexdigest(),
                }],
            })
            self.assertEqual(
                audit_package.review_owner_disposition_failures(
                    standard_not_required,
                    plugin,
                    "review.json",
                    evidence_keys | {"evidence/not-required.txt"},
                    release_mode=True,
                ),
                [],
            )

            drifted = deepcopy(accepted)
            drifted["owner_disposition"]["evidence"][0]["sha256"] = "f" * 64
            self.assertIn(
                "review-owner-evidence-hash-mismatch",
                {
                    item["code"]
                    for item in audit_package.review_owner_disposition_failures(
                        drifted,
                        plugin,
                        "review.json",
                        evidence_keys,
                        release_mode=True,
                    )
                },
            )


class ReleaseCoverageTests(unittest.TestCase):
    def representative_cases(self) -> list[dict[str, object]]:
        cases = [
            release_case(
                "implicit-case",
                mode="persuade",
                scope="new-build",
                stratum="static-site",
                adversarial=True,
                expressive=True,
            ),
            release_case(
                "experience-case",
                mode="experience",
                scope="new-build",
                stratum="static-site",
                expressive=True,
            ),
            release_case(
                "framework-case",
                mode="operate",
                scope="component",
                stratum="framework-application-data",
            ),
            release_case(
                "read-case",
                mode="read",
                scope="new-build",
                stratum="static-site",
                quiet=True,
            ),
        ]
        cases[1]["release_coverage"]["route_family_showcase_gate"] = True
        cases[-1]["release_coverage"]["cultural_context_gate"] = True
        return cases

    def test_behavioral_release_requires_diverse_representative_strata(self) -> None:
        failures, details = audit_package.release_behavioral_coverage_failures(
            "codex",
            coverage_runs(self.representative_cases()),
        )
        self.assertEqual(failures, [])
        self.assertEqual(len(details["qualified_cases"]), 4)
        self.assertIn(
            "framework-application-data",
            details["project_strata"],
        )

    def test_behavioral_release_requires_two_expressive_cases(self) -> None:
        cases = self.representative_cases()
        cases[1]["release_coverage"].pop("expressive_perception_gate")
        failures, details = audit_package.release_behavioral_coverage_failures(
            "codex",
            coverage_runs(cases),
        )
        self.assertEqual(details["expressive_perception_cases"], ["implicit-case"])
        self.assertIn(
            "release-expressive-behavioral-coverage-incomplete",
            {item["code"] for item in failures},
        )

    def test_behavioral_release_requires_a_quiet_specific_case(self) -> None:
        cases = self.representative_cases()
        cases[-1]["release_coverage"].pop("quiet_perception_gate")
        failures, details = audit_package.release_behavioral_coverage_failures(
            "codex",
            coverage_runs(cases),
        )
        self.assertEqual(details["quiet_perception_cases"], [])
        self.assertIn(
            "release-quiet-behavioral-coverage-incomplete",
            {item["code"] for item in failures},
        )

    def test_identical_hashes_require_context_but_do_not_punish_determinism(
        self,
    ) -> None:
        cases = self.representative_cases()
        records = coverage_runs(cases)
        for _path, run in records:
            if run["case"] == "framework-case" and run["variant"] == "skill":
                run["workspace_sha256"] = "f" * 64
        failures, details = audit_package.release_behavioral_coverage_failures(
            "codex",
            records,
        )
        self.assertEqual(failures, [])
        metadata = details["cases"]["framework-case"]
        self.assertEqual(metadata["skill_artifact_identity"], "identical")
        review = {"comparative_analysis": comparison_for(metadata)}
        shared_render = [{
            "path": "evidence/runs/shared-identical.png",
            "sha256": "c" * 64,
        }]
        for observation in review["comparative_analysis"]["convergence"][
            "run_observations"
        ]:
            if observation["variant"] == "skill":
                observation["evidence"] = shared_render
        self.assertEqual(
            audit_package.representative_comparison_failures(
                review,
                metadata,
                "review.json",
            ),
            [],
        )
        review["comparative_analysis"]["convergence"][
            "artifact_identity"
        ] = "distinct"
        codes = {
            item["code"]
            for item in audit_package.representative_comparison_failures(
                review,
                metadata,
                "review.json",
            )
        }
        self.assertIn(
            "release-convergence-artifact-identity-mismatch",
            codes,
        )

    def test_two_repetitions_do_not_qualify(self) -> None:
        records = [
            pair
            for pair in coverage_runs(self.representative_cases())
            if not str(pair[1]["run_id"]).endswith(":3")
        ]
        failures, details = audit_package.release_behavioral_coverage_failures(
            "codex",
            records,
        )
        self.assertIn(
            "release-behavioral-case-coverage-incomplete",
            {item["code"] for item in failures},
        )
        self.assertEqual(details["qualified_cases"], [])

    def test_three_cases_do_not_meet_the_four_case_floor(self) -> None:
        cases = self.representative_cases()[:3]
        failures, details = audit_package.release_behavioral_coverage_failures(
            "codex",
            coverage_runs(cases),
        )
        self.assertEqual(len(details["qualified_cases"]), 3)
        self.assertIn(
            "release-behavioral-case-coverage-incomplete",
            {item["code"] for item in failures},
        )

    def test_missing_implicit_adversarial_and_framework_are_rejected(
        self,
    ) -> None:
        records = coverage_runs(self.representative_cases())
        for _path, run in records:
            run["invocation_mode"] = "explicit"
            contract = run["review_contract"]
            contract["adversarial_required"] = False
            coverage = contract["release_coverage"]
            if coverage["project_stratum"] == "framework-application-data":
                coverage["project_stratum"] = "established-interface"
        failures, _details = audit_package.release_behavioral_coverage_failures(
            "codex",
            records,
        )
        codes = {item["code"] for item in failures}
        self.assertIn("release-implicit-discovery-coverage-missing", codes)
        self.assertIn("release-behavioral-adversarial-coverage-missing", codes)
        self.assertIn("release-framework-application-coverage-missing", codes)

    def test_all_four_primary_modes_are_required(self) -> None:
        records = coverage_runs(self.representative_cases())
        for _path, run in records:
            if run["case"] == "read-case":
                run["review_contract"]["release_coverage"][
                    "primary_mode"
                ] = "operate"
        failures, _details = audit_package.release_behavioral_coverage_failures(
            "codex",
            records,
        )
        self.assertIn(
            "release-behavioral-mode-coverage-incomplete",
            {item["code"] for item in failures},
        )

    def test_comparison_binds_every_counted_run(self) -> None:
        failures, details = audit_package.release_behavioral_coverage_failures(
            "codex",
            coverage_runs(self.representative_cases()),
        )
        self.assertEqual(failures, [])
        metadata = details["cases"]["implicit-case"]
        review = {"comparative_analysis": comparison_for(metadata)}
        self.assertEqual(
            audit_package.representative_comparison_failures(
                review,
                metadata,
                "review.json",
            ),
            [],
        )

        review["comparative_analysis"]["baseline_runs"].pop()
        codes = {
            item["code"]
            for item in audit_package.representative_comparison_failures(
                review,
                metadata,
                "review.json",
            )
        }
        self.assertIn("release-comparative-run-binding-mismatch", codes)

        review = {"comparative_analysis": comparison_for(metadata)}
        review["comparative_analysis"]["criteria"][0][
            "outcome"
        ] = "baseline-stronger"
        codes = {
            item["code"]
            for item in audit_package.representative_comparison_failures(
                review,
                metadata,
                "review.json",
            )
        }
        self.assertIn("release-core-comparison-regression", codes)

        review = {"comparative_analysis": comparison_for(metadata)}
        observations = review["comparative_analysis"]["convergence"][
            "run_observations"
        ]
        observations[1]["evidence"] = observations[0]["evidence"]
        codes = {
            item["code"]
            for item in audit_package.representative_comparison_failures(
                review,
                metadata,
                "review.json",
            )
        }
        self.assertIn(
            "release-comparison-render-reused-across-workspaces",
            codes,
        )

        review = {"comparative_analysis": comparison_for(metadata)}
        review["comparative_analysis"]["convergence"][
            "run_observations"
        ][0]["workspace_sha256"] = "f" * 64
        codes = {
            item["code"]
            for item in audit_package.representative_comparison_failures(
                review,
                metadata,
                "review.json",
            )
        }
        self.assertIn(
            "release-comparison-observation-workspace-mismatch",
            codes,
        )

        review = {"comparative_analysis": comparison_for(metadata)}
        observation = review["comparative_analysis"]["convergence"][
            "run_observations"
        ][0]
        observation["evidence"] = []
        codes = {
            item["code"]
            for item in audit_package.representative_comparison_failures(
                review,
                metadata,
                "review.json",
            )
        }
        self.assertIn("release-comparison-run-evidence-missing", codes)

        observation["evidence"] = [{
            "path": "evidence/source.txt",
            "sha256": "b" * 64,
        }]
        observation["basis"] = "source-only"
        codes = {
            item["code"]
            for item in audit_package.representative_comparison_failures(
                review,
                metadata,
                "review.json",
            )
        }
        self.assertIn("release-comparative-visual-basis-incomplete", codes)

    def test_render_observation_and_cluster_verification_are_hash_bound(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = Path(temporary)
            evidence_path = plugin / "evidence" / "record.txt"
            evidence_path.parent.mkdir(parents=True)
            evidence_path.write_text("verified evidence", encoding="utf-8")
            evidence_hash = hashlib.sha256(
                evidence_path.read_bytes()
            ).hexdigest()
            reference = {
                "path": "evidence/record.txt",
                "sha256": evidence_hash,
            }
            payload = {
                "schema_version": 3,
                "evidence_paths": ["evidence/record.txt"],
                "comparative_analysis": {
                    "evidence": [reference],
                    "criteria": [],
                    "convergence": {
                        "run_observations": [{
                            "variant": "skill",
                            "run_id": "suite:codex:case:skill:1",
                            "workspace_sha256": "a" * 64,
                            "basis": "rendered",
                            "observation": "Inspected the rendered output.",
                            "evidence": [reference],
                        }],
                    },
                },
                "cross_case_analysis": {
                    "evidence": [reference],
                    "dimensions": [],
                    "repeated_clusters": [{
                        "id": "same-card-stack",
                        "status": "resolved",
                        "evidence": [reference],
                        "resolution": {
                            "cause_addressed": (
                                "Task-derived grouping replaced the shared recipe."
                            ),
                            "evidence": [{
                                "path": "evidence/record.txt",
                                "sha256": "0" * 64,
                            }],
                        },
                        "verification": {"evidence": [reference]},
                    }],
                },
                "findings": [],
                "critical_blockers": [],
                "checks": {"tested": [], "unperformed": []},
                "rubric": {},
                "conclusion": {"decision": "revise", "rationale": "Test."},
            }
            failures = audit_package.review_semantic_failures(
                payload,
                plugin,
                "review.json",
                release_mode=False,
            )
            codes = {item["code"] for item in failures}
            self.assertIn("release-comparison-render-format-invalid", codes)
            self.assertIn("review-closure-evidence-hash-mismatch", codes)

    def test_masked_layout_evidence_references_are_hash_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = Path(temporary)
            evidence_path = plugin / "evidence" / "masked-layout.txt"
            evidence_path.parent.mkdir(parents=True)
            evidence_path.write_text("masked comparison", encoding="utf-8")
            evidence_hash = hashlib.sha256(
                evidence_path.read_bytes()
            ).hexdigest()
            reference = {
                "path": "evidence/masked-layout.txt",
                "sha256": evidence_hash,
            }
            payload = {
                "schema_version": 3,
                "evidence_paths": ["evidence/masked-layout.txt"],
                "cross_case_analysis": {
                    "evidence": [reference],
                    "masked_layout_comparison": {
                        "evidence": [reference],
                        "coverage": [{
                            "masked_render_sha256s": [evidence_hash],
                            "evidence": [{
                                "path": "evidence/masked-layout.txt",
                                "sha256": "0" * 64,
                            }],
                        }],
                        "observations": [{"evidence": [reference]}],
                    },
                    "dimensions": [],
                    "repeated_clusters": [],
                },
                "findings": [],
                "critical_blockers": [],
                "checks": {"tested": [], "unperformed": []},
                "rubric": {},
                "conclusion": {"decision": "revise", "rationale": "Test."},
            }
            failures = audit_package.review_semantic_failures(
                payload,
                plugin,
                "review.json",
                release_mode=False,
            )
            masked_failures = [
                item for item in failures
                if "masked_layout_comparison/coverage/0/evidence/0"
                in item["path"]
            ]
            self.assertEqual(len(masked_failures), 1)
            self.assertEqual(
                masked_failures[0]["code"],
                "review-closure-evidence-hash-mismatch",
            )

            payload["cross_case_analysis"]["masked_layout_comparison"][
                "coverage"
            ][0]["evidence"][0]["sha256"] = evidence_hash
            failures = audit_package.review_semantic_failures(
                payload,
                plugin,
                "review.json",
                release_mode=False,
            )
            masked_format_failures = [
                item for item in failures
                if item["code"]
                == "release-cross-case-masked-render-format-invalid"
            ]
            self.assertEqual(len(masked_format_failures), 1)

    def test_rendered_coverage_cannot_mix_builds_or_skip_closure(self) -> None:
        failures, coverage = audit_package.release_behavioral_coverage_failures(
            "codex",
            coverage_runs(self.representative_cases()),
        )
        self.assertEqual(failures, [])
        with tempfile.TemporaryDirectory() as temporary:
            plugin = Path(temporary)
            matched = []
            contexts = {}
            closure_paths = set()
            evidence_keys = set()
            cross_case_builds = []
            for index, case_id in enumerate(coverage["qualified_cases"]):
                metadata = coverage["cases"][case_id]
                run_id = metadata["skill_run_artifacts"][0]["run_id"]
                build_identity = f"{index + 1:x}" * 64
                perception_path = (
                    plugin / "maintainer" / "evals" / "reviews"
                    / f"{case_id}-perception.json"
                )
                implementation_path = (
                    plugin / "maintainer" / "evals" / "reviews"
                    / f"{case_id}-implementation.json"
                )
                perception = {
                    "case_id": case_id,
                    "run_id": run_id,
                    "build": {"identity": build_identity},
                    "reviewer": {
                        "lens": "perception",
                        "independent": True,
                        "process": {
                            "id": f"perception-process-{index}",
                            "method": "separate-agent",
                            "evidence_path": f"evidence/perception-{index}.log",
                        },
                    },
                    "rubric": {
                        "direction": rubric_score(3),
                        "project_specificity": rubric_score(3),
                        "distinctiveness_without_novelty_tax": rubric_score(3),
                    },
                    "conclusion": {"decision": "pass"},
                    "comparative_analysis": comparison_for(metadata),
                }
                if metadata.get("route_family_showcase_gate") is True:
                    perception["route_family_analysis"] = {
                        "declared_route_count": 2,
                        "verified_route_count": 2,
                        "routes": [
                            {
                                "path": "/",
                                "direct_entry_status": "passed",
                                "capture_status": "matched",
                            },
                            {
                                "path": "/second/",
                                "direct_entry_status": "passed",
                                "capture_status": "matched",
                            },
                        ],
                        "repeated_clusters": [],
                        "conclusion": {
                            "unique_direct_routes": True,
                            "matched_capture_coverage": True,
                            "unresolved_repeated_skeleton": False,
                            "decision": "pass",
                        },
                    }
                if metadata.get("cultural_context_gate") is True:
                    perception["cultural_context_review"] = {
                        "status": "accepted",
                        "authority": {
                            "reviewer_id": "fixture-reviewer",
                            "relationship": "owner-authorized-cultural-reviewer",
                            "independent_of_producer": True,
                            "reviewed_at": "2026-07-30T12:00:00Z",
                            "evidence": [{
                                "path": "evidence/cultural-review.txt",
                                "sha256": "c" * 64,
                            }],
                        },
                        "open_questions": [],
                    }
                implementation = {
                    "case_id": case_id,
                    "run_id": run_id,
                    "build": {"identity": build_identity},
                    "reviewer": {
                        "lens": "implementation",
                        "independent": False,
                        "process": {
                            "id": f"implementation-process-{index}",
                            "method": "self-review",
                            "evidence_path": f"evidence/implementation-{index}.log",
                        },
                    },
                    "conclusion": {"decision": "pass"},
                }
                matched.extend([
                    (perception_path, perception),
                    (implementation_path, implementation),
                ])
                contexts[perception_path] = [
                    {"kind": "mobile", "sha256": f"{index + 8:x}" * 64},
                    {"kind": "desktop", "sha256": f"{index + 11:x}" * 64},
                ]
                cross_case_builds.append({
                    "case_id": case_id,
                    "run_id": run_id,
                    "build_identity": build_identity,
                    "render_sha256s": [
                        f"{index + 8:x}" * 64,
                        f"{index + 11:x}" * 64,
                    ],
                })
                closure_paths.add(perception_path)
                evidence_keys.update({
                    perception_path.relative_to(plugin).as_posix().casefold(),
                    implementation_path.relative_to(plugin).as_posix().casefold(),
                })

            cross_evidence = [{
                "path": "evidence/cross-case.json",
                "sha256": "e" * 64,
            }]
            masked_coverage = []
            for index, record in enumerate(cross_case_builds):
                masked_hashes = [
                    digest(f"masked:{record['case_id']}:mobile"),
                    digest(f"masked:{record['case_id']}:desktop"),
                ]
                masked_coverage.append({
                    "case_id": record["case_id"],
                    "run_id": record["run_id"],
                    "build_identity": record["build_identity"],
                    "source_render_sha256s": record["render_sha256s"],
                    "masked_render_sha256s": masked_hashes,
                    "evidence": [
                        {
                            "path": f"evidence/masked-{index}-mobile.png",
                            "sha256": masked_hashes[0],
                        },
                        {
                            "path": f"evidence/masked-{index}-desktop.png",
                            "sha256": masked_hashes[1],
                        },
                    ],
                })
            matched[0][1]["cross_case_analysis"] = {
                "schema_version": 1,
                "builds": cross_case_builds,
                "dimensions": [
                    {
                        "dimension": dimension,
                        "applicability": "applicable",
                        "outcome": "task-derived-difference",
                        "assessment": (
                            f"The compared builds use task-derived {dimension} "
                            "rather than a repeated house-style default."
                        ),
                        "task_derived_differences": [
                            f"Each task produces a distinct {dimension} relationship."
                        ],
                        "counterevidence": [
                            f"Shared {dimension} conventions remain functional, not stylistic."
                        ],
                        "evidence": cross_evidence,
                    }
                    for dimension in (
                        "rendered_geometry",
                        "typography_system",
                        "component_card_grammar",
                    )
                ],
                "masked_layout_comparison": {
                    "method": (
                        "Replaced copy, logos, and dominant media with neutral "
                        "blocks while preserving each responsive composition."
                    ),
                    "masking": {
                        "copy": "replaced-with-neutral-placeholder",
                        "logos": "masked",
                        "dominant_media": "replaced-with-neutral-placeholder",
                    },
                    "layout_geometry_preserved": True,
                    "coverage": masked_coverage,
                    "observations": [{
                        "case_ids": [
                            record["case_id"] for record in cross_case_builds
                        ],
                        "outcome": "meaningful-structural-difference",
                        "assessment": (
                            "The masked responsive renders retain materially "
                            "different organization and attention paths."
                        ),
                        "cluster_id": None,
                        "evidence": masked_coverage[0]["evidence"],
                    }],
                    "limitations": [
                        "Masking cannot establish authorship or overall design quality."
                    ],
                    "authorship_inference": "not-performed",
                    "evidence": cross_evidence,
                },
                "repeated_clusters": [],
                "conclusion": {
                    "unresolved_repeated_cluster": False,
                    "rationale": (
                        "No unresolved repeated visual-language cluster remains "
                        "across the unrelated representative cases."
                    ),
                },
                "evidence": cross_evidence,
            }
            failures, details = (
                audit_package.release_representative_review_failures(
                    "codex",
                    coverage,
                    matched,
                    contexts,
                    closure_paths,
                    evidence_keys,
                    plugin,
                )
            )
            self.assertEqual(failures, [])
            self.assertEqual(
                len(details["qualified_case_build_families"]),
                4,
            )
            self.assertEqual(details["quiet_perception_cases"], ["read-case"])

            masked_comparison = matched[0][1]["cross_case_analysis"][
                "masked_layout_comparison"
            ]
            del matched[0][1]["cross_case_analysis"][
                "masked_layout_comparison"
            ]
            failures, _details = (
                audit_package.release_representative_review_failures(
                    "codex",
                    coverage,
                    matched,
                    contexts,
                    closure_paths,
                    evidence_keys,
                    plugin,
                )
            )
            self.assertIn(
                "release-cross-case-masked-comparison-missing",
                {item["code"] for item in failures},
            )
            matched[0][1]["cross_case_analysis"][
                "masked_layout_comparison"
            ] = masked_comparison

            removed_masked_case = masked_comparison["coverage"].pop()
            failures, _details = (
                audit_package.release_representative_review_failures(
                    "codex",
                    coverage,
                    matched,
                    contexts,
                    closure_paths,
                    evidence_keys,
                    plugin,
                )
            )
            self.assertIn(
                "release-cross-case-masked-coverage-incomplete",
                {item["code"] for item in failures},
            )
            masked_comparison["coverage"].append(removed_masked_case)

            masked_case = masked_comparison["coverage"][0]
            removed_masked_hash = masked_case["masked_render_sha256s"].pop()
            failures, _details = (
                audit_package.release_representative_review_failures(
                    "codex",
                    coverage,
                    matched,
                    contexts,
                    closure_paths,
                    evidence_keys,
                    plugin,
                )
            )
            self.assertIn(
                "release-cross-case-masked-render-evidence-incomplete",
                {item["code"] for item in failures},
            )
            masked_case["masked_render_sha256s"].append(removed_masked_hash)

            removed_observed_case = masked_comparison["observations"][0][
                "case_ids"
            ].pop()
            failures, _details = (
                audit_package.release_representative_review_failures(
                    "codex",
                    coverage,
                    matched,
                    contexts,
                    closure_paths,
                    evidence_keys,
                    plugin,
                )
            )
            self.assertIn(
                "release-cross-case-masked-observations-incomplete",
                {item["code"] for item in failures},
            )
            masked_comparison["observations"][0]["case_ids"].append(
                removed_observed_case
            )

            capability_evidence = [{
                "path": "evidence/image-capability.txt",
                "sha256": "f" * 64,
            }]
            matched[0][1]["capability_disposition"] = {
                "image_generation": {
                    "status": "available",
                    "rationale": (
                        "The bound host record declares image generation available."
                    ),
                    "availability_evidence": capability_evidence,
                    "generated_artifacts": [{
                        "path": "evidence/concept.webp",
                        "sha256": "d" * 64,
                    }],
                    "inspection_evidence": [{
                        "path": "evidence/contact-sheet.png",
                        "sha256": "e" * 64,
                    }],
                }
            }
            failures, capability_details = (
                audit_package.release_representative_review_failures(
                    "codex",
                    coverage,
                    matched,
                    contexts,
                    closure_paths,
                    evidence_keys,
                    plugin,
                )
            )
            self.assertTrue(
                capability_details["image_generation_available_claimed"]
            )
            self.assertIn(
                "release-generated-media-capability-coverage-missing",
                {item["code"] for item in failures},
            )

            generated_case_id = matched[0][1]["case_id"]
            coverage["cases"][generated_case_id][
                "generated_media_capability_gate"
            ] = True
            failures, capability_details = (
                audit_package.release_representative_review_failures(
                    "codex",
                    coverage,
                    matched,
                    contexts,
                    closure_paths,
                    evidence_keys,
                    plugin,
                )
            )
            self.assertNotIn(
                "release-generated-media-capability-coverage-missing",
                {item["code"] for item in failures},
            )
            self.assertEqual(
                capability_details["generated_media_capability_cases"],
                [generated_case_id],
            )
            coverage["cases"][generated_case_id][
                "generated_media_capability_gate"
            ] = False

            image_generation = matched[0][1]["capability_disposition"][
                "image_generation"
            ]
            image_generation["status"] = "unavailable"
            image_generation["generated_artifacts"] = []
            image_generation["inspection_evidence"] = []
            failures, capability_details = (
                audit_package.release_representative_review_failures(
                    "codex",
                    coverage,
                    matched,
                    contexts,
                    closure_paths,
                    evidence_keys,
                    plugin,
                )
            )
            self.assertFalse(
                capability_details["image_generation_available_claimed"]
            )
            self.assertNotIn(
                "release-generated-media-capability-coverage-missing",
                {item["code"] for item in failures},
            )
            del matched[0][1]["capability_disposition"]

            closure_paths.remove(matched[0][0])
            failures, _details = (
                audit_package.release_representative_review_failures(
                    "codex",
                    coverage,
                    matched,
                    contexts,
                    closure_paths,
                    evidence_keys,
                    plugin,
                )
            )
            self.assertIn(
                "release-rendered-case-coverage-incomplete",
                {item["code"] for item in failures},
            )

            closure_paths.add(matched[0][0])
            original_identity = matched[1][1]["build"]["identity"]
            matched[1][1]["build"]["identity"] = "f" * 64
            failures, _details = (
                audit_package.release_representative_review_failures(
                    "codex",
                    coverage,
                    matched,
                    contexts,
                    closure_paths,
                    evidence_keys,
                    plugin,
                )
            )
            self.assertIn(
                "release-rendered-case-coverage-incomplete",
                {item["code"] for item in failures},
            )
            matched[1][1]["build"]["identity"] = original_identity

            removed_build = matched[0][1]["cross_case_analysis"][
                "builds"
            ].pop()
            failures, _details = (
                audit_package.release_representative_review_failures(
                    "codex",
                    coverage,
                    matched,
                    contexts,
                    closure_paths,
                    evidence_keys,
                    plugin,
                )
            )
            self.assertIn(
                "release-cross-case-build-coverage-incomplete",
                {item["code"] for item in failures},
            )
            matched[0][1]["cross_case_analysis"]["builds"].append(
                removed_build
            )

            for dimension in matched[0][1]["cross_case_analysis"][
                "dimensions"
            ]:
                if dimension["dimension"] == "component_card_grammar":
                    dimension["outcome"] = "repeated-cluster-risk"
            matched[0][1]["cross_case_analysis"]["repeated_clusters"] = [{
                "id": "same-card-stack",
                "dimensions": ["component_card_grammar"],
                "severity": "medium",
                "status": "unresolved",
                "cause": (
                    "A shared component recipe overrode task-derived grouping."
                ),
                "rationale": (
                    "The same floating card stack recurs without task-derived cause."
                ),
                "resolution": None,
                "verification": None,
                "evidence": cross_evidence,
            }]
            matched[0][1]["cross_case_analysis"]["conclusion"][
                "unresolved_repeated_cluster"
            ] = True
            failures, _details = (
                audit_package.release_representative_review_failures(
                    "codex",
                    coverage,
                    matched,
                    contexts,
                    closure_paths,
                    evidence_keys,
                    plugin,
                )
            )
            self.assertIn(
                "release-cross-case-house-style-unresolved",
                {item["code"] for item in failures},
            )

            cluster = matched[0][1]["cross_case_analysis"][
                "repeated_clusters"
            ][0]
            cluster["status"] = "resolved"
            matched[0][1]["cross_case_analysis"]["conclusion"][
                "unresolved_repeated_cluster"
            ] = False
            failures, _details = (
                audit_package.release_representative_review_failures(
                    "codex",
                    coverage,
                    matched,
                    contexts,
                    closure_paths,
                    evidence_keys,
                    plugin,
                )
            )
            self.assertIn(
                "release-cross-case-resolution-unverified",
                {item["code"] for item in failures},
            )

            cluster["resolution"] = {
                "cause_addressed": (
                    "Each build now derives grouping from its task-specific "
                    "content model instead of the shared recipe."
                ),
                "summary": (
                    "Replaced the repeated stack with task-specific grouping "
                    "and hierarchy in every affected final build."
                ),
                "owner_id": "builder-alpha",
                "decided_at": "2026-07-28T13:00:00Z",
                "evidence": cross_evidence,
            }
            cluster["verification"] = {
                "method": (
                    "Independent comparison of the final counted responsive renders."
                ),
                "verifier_id": "reviewer-beta",
                "performed_at": "2026-07-28T13:30:00Z",
                "evidence": cross_evidence,
            }
            failures, _details = (
                audit_package.release_representative_review_failures(
                    "codex",
                    coverage,
                    matched,
                    contexts,
                    closure_paths,
                    evidence_keys,
                    plugin,
                )
            )
            self.assertEqual(failures, [])


class BehavioralFixtureContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_path = (
            PLUGIN
            / "maintainer"
            / "evals"
            / "fixtures"
            / "behavioral-cases.json"
        )
        cls.payload = json.loads(cls.fixture_path.read_text(encoding="utf-8"))
        cls.cases = {
            case["id"]: case
            for case in cls.payload["cases"]
        }

    def test_behavioral_fixture_validates_with_capability_and_expressive_fields(
        self,
    ) -> None:
        schema = json.loads(
            (PLUGIN / "maintainer" / "evals" / "schema.json").read_text(
                encoding="utf-8"
            )
        )
        errors = list(Draft202012Validator(schema).iter_errors(self.payload))
        self.assertEqual(errors, [], "\n".join(error.message for error in errors))
        failures, count = audit_package.validate_fixtures(
            self.fixture_path.parent,
            PLUGIN / "maintainer" / "evals" / "schema.json",
        )
        self.assertEqual(failures, [])
        self.assertEqual(count, len(self.payload["cases"]))

        expressive = {
            case_id
            for case_id, case in self.cases.items()
            if case.get("release_coverage", {}).get(
                "expressive_perception_gate"
            ) is True
        }
        self.assertTrue({
            "maximal-cultural-experience",
            "owner-plain-boring-existing-site-repair",
        } <= expressive)
        quiet = {
            case_id
            for case_id, case in self.cases.items()
            if case.get("release_coverage", {}).get(
                "quiet_perception_gate"
            ) is True
        }
        self.assertIn("quiet-current-architecture-studio", quiet)
        generated_media = {
            case_id
            for case_id, case in self.cases.items()
            if case.get("release_coverage", {}).get(
                "generated_media_capability_gate"
            ) is True
        }
        self.assertIn("generated-concept-media-truth", generated_media)

    def test_natural_high_value_prompts_do_not_leak_review_recipe(self) -> None:
        ids = {
            "quiet-current-architecture-studio",
            "maximal-cultural-experience",
            "owner-plain-boring-existing-site-repair",
        }
        for case_id in ids:
            task = self.cases[case_id]["task"]
            requirements = " ".join(self.cases[case_id]["review_requirements"])
            with self.subTest(case=case_id):
                self.assertLessEqual(len(task.split()), 55)
                self.assertNotIn("exactly three", task.casefold())
                self.assertNotIn("1440 by 900", task.casefold())
                self.assertNotIn("contact sheet", task.casefold())
                self.assertGreaterEqual(len(requirements.split()), 75)

        showcase = self.cases["maximal-cultural-experience"]
        showcase_requirements = " ".join(
            showcase["review_requirements"]
        ).casefold()
        for fixed_recipe in (
            "exactly three directions",
            "candidate-a.html",
            "candidate-b.html",
            "1440 by 900",
            "opening model",
            "bounded aesthetic risk",
            "golden route",
        ):
            self.assertNotIn(fixed_recipe, showcase_requirements)
        self.assertIn("in proportion to uncertainty", showcase_requirements)
        self.assertIn("no universal concept count", showcase_requirements)
        self.assertTrue(
            self.cases["quiet-current-architecture-studio"][
                "release_coverage"
            ]["high_value"]
        )

    def test_missing_adversarial_lifecycles_are_present_and_bounded(self) -> None:
        ids = {
            "maintained-component-migration-handoff",
            "assisted-heating-service-completion",
            "complaint-dispute-appeal-lifecycle",
            "lower-impact-media-measurement-lifecycle",
        }
        self.assertTrue(ids <= set(self.cases))
        for case_id in ids:
            case = self.cases[case_id]
            with self.subTest(case=case_id):
                self.assertTrue(case["adversarial"])
                self.assertGreaterEqual(len(case["review_requirements"]), 6)
                if "input_dir" in case:
                    self.assertTrue(
                        (
                            PLUGIN
                            / "maintainer"
                            / "evals"
                            / "fixtures"
                            / case["input_dir"]
                        ).is_dir()
                    )

    def test_generated_media_contract_has_real_file_and_unavailable_branches(
        self,
    ) -> None:
        for case_id in (
            "generated-concept-media-truth",
            "lower-impact-media-measurement-lifecycle",
        ):
            case = self.cases[case_id]
            requirements = " ".join(case["review_requirements"]).casefold()
            with self.subTest(case=case_id):
                self.assertEqual(
                    case["capability_contract"]["image_generation"],
                    "required-when-host-declared-available",
                )
                if case_id == "generated-concept-media-truth":
                    self.assertTrue(
                        case["release_coverage"][
                            "generated_media_capability_gate"
                        ]
                    )
                self.assertIn("actual decodable local", requirements)
                self.assertIn("provenance", requirements)
                self.assertIn("contact sheet", requirements)
                self.assertIn("responsive crop", requirements)
                self.assertIn("unavailable", requirements)
                self.assertNotIn(
                    "may be represented only by a clearly labeled local placeholder",
                    case["task"].casefold(),
                )


class FrameworkFixtureContractTests(unittest.TestCase):
    def test_svelte_fixture_contains_the_required_app_shell_and_base_config(self) -> None:
        fixture = (
            PLUGIN
            / "maintainer"
            / "evals"
            / "fixtures"
            / "inputs"
            / "svelte-dirty-preferences"
        )
        app_shell = (fixture / "src" / "app.html").read_text(encoding="utf-8")
        config = json.loads((fixture / "jsconfig.json").read_text(encoding="utf-8"))
        self.assertIn("%sveltekit.head%", app_shell)
        self.assertIn("%sveltekit.body%", app_shell)
        self.assertEqual(config["extends"], "./.svelte-kit/tsconfig.json")

    def test_next_fixture_package_and_lock_use_the_same_patched_version(self) -> None:
        fixture = (
            PLUGIN
            / "maintainer"
            / "evals"
            / "fixtures"
            / "inputs"
            / "next-rtl-support"
        )
        package = json.loads((fixture / "package.json").read_text(encoding="utf-8"))
        lock = json.loads((fixture / "package-lock.json").read_text(encoding="utf-8"))
        expected = package["dependencies"]["next"]
        self.assertEqual(expected, "14.2.35")
        self.assertEqual(lock["packages"][""]["dependencies"]["next"], expected)
        self.assertEqual(lock["packages"]["node_modules/next"]["version"], expected)


if __name__ == "__main__":
    unittest.main()
