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


def release_case(
    case_id: str,
    *,
    mode: str,
    scope: str,
    stratum: str,
    adversarial: bool = False,
) -> dict[str, object]:
    return {
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


class ReleaseCoverageTests(unittest.TestCase):
    def representative_cases(self) -> list[dict[str, object]]:
        return [
            release_case(
                "implicit-case",
                mode="persuade",
                scope="new-build",
                stratum="static-site",
                adversarial=True,
            ),
            release_case(
                "experience-case",
                mode="experience",
                scope="new-build",
                stratum="static-site",
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
            ),
        ]

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
                    "conclusion": {"decision": "pass"},
                    "comparative_analysis": comparison_for(metadata),
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
            matched[0][1]["cross_case_analysis"] = {
                "schema_version": 1,
                "builds": cross_case_builds,
                "dimensions": [
                    {
                        "dimension": dimension,
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
                    for dimension in sorted(audit_package.CROSS_CASE_DIMENSIONS)
                ],
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
                if dimension["dimension"] == "card_grammar":
                    dimension["outcome"] = "repeated-cluster-risk"
            matched[0][1]["cross_case_analysis"]["repeated_clusters"] = [{
                "id": "same-card-stack",
                "dimensions": ["card_grammar"],
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
