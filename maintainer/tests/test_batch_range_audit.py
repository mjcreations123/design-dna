from __future__ import annotations

import binascii
import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, ValidationError


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
AUDITOR = PACKAGE_ROOT / "skills" / "design-dna" / "scripts" / "batch_range_audit.py"
CONTRACT_SCHEMA = PACKAGE_ROOT / "maintainer" / "schemas" / "batch-range.schema.json"
REPORT_SCHEMA = PACKAGE_ROOT / "maintainer" / "schemas" / "batch-range-audit.schema.json"
SKILL = PACKAGE_ROOT / "skills" / "design-dna" / "SKILL.md"
WORKFLOW = PACKAGE_ROOT / "skills" / "design-dna" / "references" / "workflow.md"
TEMPLATE = PACKAGE_ROOT / "skills" / "design-dna" / "templates" / "batch-range-template.json"
BATCH_GUIDANCE = (
    PACKAGE_ROOT
    / "skills"
    / "design-dna"
    / "references"
    / "quality"
    / "batch-range-evaluation.md"
)
SITE_OBSERVATION_TEMPLATE = (
    PACKAGE_ROOT
    / "skills"
    / "design-dna"
    / "templates"
    / "batch-site-observation-template.md"
)
WHOLE_SYSTEM_TEMPLATE = (
    PACKAGE_ROOT
    / "skills"
    / "design-dna"
    / "templates"
    / "batch-whole-system-review-template.md"
)


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_digest(value: object) -> str:
    return digest(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


def capture_set_digest(pages: list[dict[str, object]]) -> str:
    return canonical_digest([
        {
            "page_id": page["id"],
            "route": page["route"],
            "captures": [
                {
                    "viewport_class": capture["viewport_class"],
                    "capture_mode": capture["capture_mode"],
                    "render_capture_id": capture["render_capture_id"],
                    "render_scenario_id": capture["render_scenario_id"],
                    "render_profile_id": capture["render_profile_id"],
                    "path": capture["path"],
                    "sha256": capture["sha256"],
                }
                for capture in page["captures"]
            ],
        }
        for page in pages
    ])


def png(width: int = 8, height: int = 6, rgb: tuple[int, int, int] = (40, 80, 120)) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF)
        )

    scanline = b"\x00" + bytes(rgb) * width
    pixels = scanline * height
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(pixels))
        + chunk(b"IEND", b"")
    )


def write_ref(project: Path, relative: str, payload: bytes) -> dict[str, str]:
    target = project.joinpath(*relative.split("/"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return {"path": relative, "sha256": digest(payload)}


def make_contract(
    project: Path,
    statuses: tuple[str, str, str] = ("built", "built", "built"),
) -> dict[str, object]:
    sites: list[dict[str, object]] = []
    for index, status in enumerate(statuses):
        letter = chr(ord("a") + index)
        site_id = f"site-{letter}"
        brief = write_ref(
            project,
            f"briefs/{site_id}.md",
            f"Frozen independent brief for {site_id}.\n".encode(),
        )
        source_packet = write_ref(
            project,
            f"source-packets/{site_id}.json",
            (
                '{"site":"'
                + site_id
                + '","sources":["owner-brief","subject-research"]}\n'
            ).encode(),
        )
        if status == "built":
            public_root = project / "builds" / site_id
            public_root.mkdir(parents=True)
            public_payload = f"<!doctype html><title>{site_id}</title><main>Fixture</main>\n".encode()
            (public_root / "index.html").write_bytes(public_payload)
            manifest_files = [
                {
                    "path": "index.html",
                    "bytes": len(public_payload),
                    "sha256": digest(public_payload),
                }
            ]
            capture_dimensions = {"wide": (11, 7), "narrow": (5, 9)}
            captures = [
                {
                    "viewport_class": viewport,
                    "capture_mode": "viewport",
                    "render_capture_id": f"home-{viewport}",
                    "render_scenario_id": "home",
                    "render_profile_id": viewport,
                    **write_ref(
                        project,
                        f"render-reports/{site_id}/screenshots/{site_id}-home-{viewport}.png",
                        png(*capture_dimensions[viewport], rgb=(40 + index * 20, 80, 120)),
                    ),
                }
                for viewport in ("wide", "narrow")
            ]
            pages = [
                {
                    "id": "home",
                    "mask_label": "Page 1",
                    "route": "/",
                    "captures": captures,
                }
            ]
            render_report_payload = (
                json.dumps(
                    {
                        "schema_version": 3,
                        "execution_ok": True,
                        "build": {"id": f"fixture-build-{site_id}"},
                        "source_snapshot": {
                            "manifest": {
                                "algorithm": "sha256",
                                "manifest_sha256": canonical_digest(manifest_files),
                                "file_count": len(manifest_files),
                                "total_bytes": sum(item["bytes"] for item in manifest_files),
                                "files": manifest_files,
                            }
                        },
                        "captures": [
                            {
                                "id": capture["render_capture_id"],
                                "scenario_id": capture["render_scenario_id"],
                                "profile_id": capture["render_profile_id"],
                                "route_label": "/",
                                "capture_status": "complete",
                                "requested_url": "http://127.0.0.1:4173/",
                                "final_url": "http://127.0.0.1:4173/",
                                "http_status": 200,
                                "viewport": {
                                    "width": capture_dimensions[capture["viewport_class"]][0],
                                    "height": capture_dimensions[capture["viewport_class"]][1],
                                    "device_scale_factor": 1,
                                },
                                "screenshot": {
                                    "path": "screenshots/" + Path(capture["path"]).name,
                                    "sha256": capture["sha256"],
                                    "pixel_width": capture_dimensions[capture["viewport_class"]][0],
                                    "pixel_height": capture_dimensions[capture["viewport_class"]][1],
                                },
                            }
                            for capture in captures
                        ],
                    },
                    indent=2,
                )
                + "\n"
            ).encode()
            render_report = write_ref(
                project,
                f"render-reports/{site_id}/render-review.json",
                render_report_payload,
            )
            site_capture_set = capture_set_digest(pages)
            review = {
                "status": "complete",
                "reviewer_id": f"reviewer-{letter}",
                "sibling_output_seen_before_observation": False,
                "diagnostic_material_seen_before_observation": False,
                "observed_at": "2026-08-08T16:00:00Z",
                "frozen_at": "2026-08-08T17:00:00Z",
                "capture_set_sha256": site_capture_set,
                "evidence": write_ref(
                    project,
                    f"reviews/{site_id}-unprimed.md",
                    f"Unprimed observations for {site_id}.\n".encode(),
                ),
            }
            build_root: str | None = f"builds/{site_id}"
            public_root_value: str | None = f"builds/{site_id}"
            blocker = None
            isolation = {
                "status": "attested",
                "source_packet": source_packet,
                "producer_context_id": f"fixture-build-context-{site_id}",
                "sibling_output_exposure": {
                    "state": "not-exposed",
                    "timing": "through-unprimed-review",
                    "details": (
                        "The producer recorded no sibling implementation output "
                        "before this site's unprimed review."
                    ),
                },
                "allowed_shared_tooling": [
                    {
                        "name": "fixture-capture-runner",
                        "purpose": "Capture the declared routes at the study's matched viewport classes.",
                        "constraint": "The runner supplies no page markup, copy, composition, or design tokens.",
                    }
                ],
                "shared_artifacts_or_exceptions": [],
                "attested_by": f"producer-{letter}",
                "attested_at": "2026-08-08T15:00:00Z",
            }
        elif status == "planned":
            captures = []
            pages = [
                {
                    "id": "home",
                    "mask_label": "Page 1",
                    "route": "/",
                    "captures": captures,
                }
            ]
            render_report = None
            review = {
                "status": "not-run",
                "reviewer_id": None,
                "sibling_output_seen_before_observation": None,
                "diagnostic_material_seen_before_observation": None,
                "observed_at": None,
                "frozen_at": None,
                "capture_set_sha256": None,
                "evidence": None,
            }
            build_root = f"builds/{site_id}"
            public_root_value = None
            blocker = None
            isolation = {
                "status": "pending",
                "source_packet": source_packet,
                "producer_context_id": f"fixture-build-context-{site_id}",
                "sibling_output_exposure": {
                    "state": "not-started",
                    "timing": "not-applicable",
                    "details": "Implementation has not started, so exposure has not yet been assessed.",
                },
                "allowed_shared_tooling": [],
                "shared_artifacts_or_exceptions": [],
                "attested_by": None,
                "attested_at": None,
            }
        else:
            captures = []
            pages = [
                {
                    "id": "home",
                    "mask_label": "Page 1",
                    "route": "/",
                    "captures": captures,
                }
            ]
            render_report = None
            review = {
                "status": "not-run",
                "reviewer_id": None,
                "sibling_output_seen_before_observation": None,
                "diagnostic_material_seen_before_observation": None,
                "observed_at": None,
                "frozen_at": None,
                "capture_set_sha256": None,
                "evidence": None,
            }
            build_root = None
            public_root_value = None
            blocker = {
                "code": "required-source-missing",
                "summary": "The brief requires source material that is not available or safe to invent.",
                "unblock_condition": "The accountable owner supplies the required source material and usage authority.",
                "evidence": [
                    write_ref(
                        project,
                        f"blocks/{site_id}.md",
                        f"Documented input gap for {site_id}.\n".encode(),
                    )
                ],
            }
            isolation = {
                "status": "pending",
                "source_packet": source_packet,
                "producer_context_id": f"fixture-build-context-{site_id}",
                "sibling_output_exposure": {
                    "state": "not-started",
                    "timing": "not-applicable",
                    "details": "Implementation did not start because the declared blocker remains unresolved.",
                },
                "allowed_shared_tooling": [],
                "shared_artifacts_or_exceptions": [],
                "attested_by": None,
                "attested_at": None,
            }
        sites.append(
            {
                "id": site_id,
                "mask_label": f"Specimen {letter.upper()}",
                "status": (
                    status
                    if status in {"planned", "built"}
                    else "correctly_blocked"
                ),
                "independence_basis": (
                    f"The subject, audience, task, content, and source material for {site_id} "
                    "were selected independently."
                ),
                "brief": brief,
                "implementation_isolation": isolation,
                "build_root": build_root,
                "public_root": public_root_value,
                "render_report": render_report,
                "pages": pages,
                "unprimed_review": review,
                "blocker": blocker,
            }
        )
    whole_review = write_ref(
        project,
        "reviews/masked-whole-system.md",
        b"Masked whole-system observations recorded before unmasking.\n",
    )
    finding_evidence = write_ref(
        project,
        "reviews/finding-one.md",
        b"Context-specific observation evidence for the first site.\n",
    )
    whole_capture_set = canonical_digest([
        {
            "site_id": site["id"],
            "capture_set_sha256": site["unprimed_review"]["capture_set_sha256"],
        }
        for site in sites
        if site["status"] == "built"
    ])
    return {
        "schema_version": 1,
        "classification": "internal",
        "study": {
            "id": "portable-range-study",
            "title": "Portable controlled range fixture",
            "frozen_at": "2026-08-08T12:00:00Z",
            "viewport_classes": [
                {
                    "id": "wide",
                    "role": "wide",
                    "width": 11,
                    "height": 7,
                    "basis": "A content-derived wide state selected for this fixture.",
                    "required": True,
                },
                {
                    "id": "narrow",
                    "role": "narrow",
                    "width": 5,
                    "height": 9,
                    "basis": "A content-derived narrow state selected for this fixture.",
                    "required": True,
                },
            ],
            "review_protocol": {
                "site_observation": "unprimed-before-diagnostics",
                "whole_system_comparison": "masked",
                "automatic_aesthetic_pass": False,
            },
        },
        "data_handling": {
            "status": "resolved",
            "capture_authorization": {
                "status": "authorized",
                "basis": "The fixture owner authorized matched captures for this internal evaluation.",
            },
            "contact_sheet_authorization": {
                "status": "authorized",
                "basis": "The fixture owner authorized an internal neutral-label contact sheet.",
            },
            "classification": "internal",
            "recipients": ["fixture-review-team"],
            "access_scope": "Access is limited to the named fixture review team inside this test project.",
            "retention": {
                "mode": "dated",
                "owner": "fixture-evidence-owner",
                "delete_or_review_on": "2027-08-08",
                "reason": "Review or remove the fixture evidence on the declared date.",
            },
            "transformations": [],
        },
        "sites": sites,
        "whole_system_review": {
            "status": "complete",
            "masked": True,
            "reviewer_id": "masked-reviewer",
            "site_identity_revealed_before_observation": False,
            "diagnostic_material_seen_before_observation": False,
            "observed_at": "2026-08-08T18:00:00Z",
            "frozen_at": "2026-08-08T19:00:00Z",
            "capture_set_sha256": whole_capture_set,
            "evidence": whole_review,
        },
        "contextual_findings": [
            {
                "id": "finding-one",
                "site_ids": ["site-a"],
                "routes": [{"site_id": "site-a", "route": "/"}],
                "context": "The first brief asks a specific audience to complete its primary task quickly.",
                "observation": "The unprimed reviewer lost that task beneath a competing block in the rendered page.",
                "evidence": [finding_evidence],
                "disposition": "open",
            }
        ],
    }


def write_contract(project: Path, contract: dict[str, object]) -> Path:
    path = project / ".design-dna" / "batch-range.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    return path


def mutate_render_report(
    project: Path,
    site: dict[str, object],
    mutate: object,
) -> dict[str, object]:
    reference = site["render_report"]
    path = project.joinpath(*str(reference["path"]).split("/"))
    report = json.loads(path.read_text(encoding="utf-8"))
    mutate(report)
    payload = (json.dumps(report, indent=2) + "\n").encode()
    path.write_bytes(payload)
    reference["sha256"] = digest(payload)
    return report


def refresh_review_capture_bindings(contract: dict[str, object]) -> None:
    built = []
    for site in contract["sites"]:
        if site["status"] != "built":
            continue
        site_digest = capture_set_digest(site["pages"])
        site["unprimed_review"]["capture_set_sha256"] = site_digest
        built.append({"site_id": site["id"], "capture_set_sha256": site_digest})
    contract["whole_system_review"]["capture_set_sha256"] = canonical_digest(built)


def run_audit(project: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-B", str(AUDITOR), str(project), *arguments],
        cwd=PACKAGE_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        timeout=30,
        check=False,
    )


def stderr_payload(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return json.loads(result.stderr.strip())


class BatchRangeAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract_schema = json.loads(CONTRACT_SCHEMA.read_text(encoding="utf-8"))
        cls.report_schema = json.loads(REPORT_SCHEMA.read_text(encoding="utf-8"))
        cls.contract_validator = Draft202012Validator(
            cls.contract_schema,
            format_checker=FormatChecker(),
        )
        cls.report_validator = Draft202012Validator(
            cls.report_schema,
            format_checker=FormatChecker(),
        )

    def test_complete_batch_verifies_evidence_without_aesthetic_pass(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-batch-range-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            self.contract_validator.validate(contract)
            write_contract(project, contract)
            result = run_audit(
                project,
                "--output",
                "records/report.json",
                "--atlas",
                "records/masked-atlas.png",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertTrue(summary["execution_ok"])
            self.assertTrue(summary["comparison_ready"])
            self.assertFalse(summary["automatic_aesthetic_pass"])
            self.assertEqual(
                summary["decision_status"],
                "human-contextual-review-required",
            )
            report = json.loads((project / "records" / "report.json").read_text(encoding="utf-8"))
            self.report_validator.validate(report)
            self.assertEqual(report["summary"]["built_site_count"], 3)
            self.assertEqual(report["summary"]["verified_capture_count"], 6)
            self.assertEqual(report["correctly_blocked"], [])
            self.assertFalse(report["automatic_aesthetic_pass"])
            self.assertFalse(
                report["whole_system_review"][
                    "diagnostic_material_seen_before_observation"
                ]
            )
            serialized = json.dumps(report).casefold()
            self.assertNotIn('"ai_score":', serialized)
            self.assertNotIn('"aesthetic_score":', serialized)
            self.assertNotIn('"score":', serialized)
            self.assertTrue(
                any(
                    "separable bytes" in limitation
                    for limitation in report["limitations"]
                )
            )
            self.assertIn(report["atlas"]["status"], {"created", "pillow-unavailable"})
            if report["atlas"]["status"] == "created":
                atlas = project / "records" / "masked-atlas.png"
                self.assertTrue(atlas.is_file())
                self.assertEqual(digest(atlas.read_bytes()), report["atlas"]["sha256"])

    def test_runtime_router_and_workflow_expose_protocol_not_a_recipe(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        workflow = WORKFLOW.read_text(encoding="utf-8")
        template = TEMPLATE.read_text(encoding="utf-8").casefold()
        self.assertIn("| Batch Study |", skill)
        self.assertIn(
            "[Batch Study evaluation](references/quality/batch-range-evaluation.md)",
            skill,
        )
        self.assertIn("[batch study](templates/batch-range-template.json)", skill)
        self.assertIn(
            "[batch site observation](templates/batch-site-observation-template.md)",
            skill,
        )
        self.assertIn(
            "[batch whole-system review](templates/batch-whole-system-review-template.md)",
            skill,
        )
        self.assertIn("For an explicit Batch Study", workflow)
        self.assertIn("mechanically verifiable evidence and timing fields only", workflow)
        self.assertIn("cannot prove that a human followed the protocol", workflow)
        self.assertIn('"automatic_aesthetic_pass": false', template)
        template_payload = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        self.contract_validator.validate(template_payload)
        self.assertTrue(
            all(site["status"] == "planned" for site in template_payload["sites"])
        )
        self.assertTrue(
            all(
                page["captures"] == []
                for site in template_payload["sites"]
                for page in site["pages"]
            )
        )
        self.assertEqual(template_payload["data_handling"]["status"], "pending")
        self.assertFalse(
            template_payload["whole_system_review"][
                "diagnostic_material_seen_before_observation"
            ]
        )
        self.assertTrue(
            all(
                site["implementation_isolation"]["status"] == "pending"
                for site in template_payload["sites"]
            )
        )
        for fixed_field in (
            '"font"',
            '"palette"',
            '"style"',
            '"novelty_quota"',
            '"aesthetic_score"',
            '"ai_score"',
        ):
            with self.subTest(field=fixed_field):
                self.assertNotIn(fixed_field, template)

        guidance = BATCH_GUIDANCE.read_text(encoding="utf-8")
        site_observation = SITE_OBSERVATION_TEMPLATE.read_text(encoding="utf-8")
        whole_system = WHOLE_SYSTEM_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("Compare derivation rather than ingredients", guidance)
        self.assertIn("revise at the\nearliest shared decision", guidance)
        self.assertIn("Do not treat a palette swap, font swap", guidance)
        self.assertIn("before seeing sibling implementations", site_observation)
        self.assertIn("Do not infer\nauthorship", site_observation)
        self.assertIn("first phase is durably frozen", guidance)
        self.assertIn("non-empty distinct per-site", guidance)
        self.assertIn("diagnostic material or the site-identity map", guidance)
        self.assertIn("Different hues, fonts, photos, or effects", whole_system)
        self.assertIn("Automatic aesthetic pass: false", whole_system)
        self.assertIn(
            "whole_system_review.diagnostic_material_seen_before_observation",
            whole_system,
        )

    def test_whole_system_diagnostic_priming_blocks_comparison_readiness(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-batch-whole-primed-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            contract["whole_system_review"][
                "diagnostic_material_seen_before_observation"
            ] = True
            self.contract_validator.validate(contract)
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 1, result.stderr)
            report = json.loads(
                (project / ".design-dna" / "batch-range-audit.json").read_text(
                    encoding="utf-8"
                )
            )
            self.report_validator.validate(report)
            self.assertFalse(report["comparison_ready"])
            self.assertTrue(
                report["whole_system_review"][
                    "diagnostic_material_seen_before_observation"
                ]
            )
            self.assertIn(
                "masked-whole-system-review-incomplete",
                {gap["code"] for gap in report["gaps"]},
            )

    def test_empty_review_evidence_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-batch-empty-review-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            contract["sites"][0]["unprimed_review"]["evidence"] = write_ref(
                project,
                "reviews/site-a-empty.md",
                b"",
            )
            self.contract_validator.validate(contract)
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(
                stderr_payload(result)["error"]["code"],
                "review-evidence-empty",
            )

        with tempfile.TemporaryDirectory(prefix="design-dna-batch-empty-whole-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            contract["whole_system_review"]["evidence"] = write_ref(
                project,
                "reviews/empty-whole-system.md",
                b"",
            )
            self.contract_validator.validate(contract)
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(
                stderr_payload(result)["error"]["code"],
                "review-evidence-empty",
            )

    def test_per_site_review_evidence_must_be_distinct(self) -> None:
        mutations = {
            "same-reference": lambda contract, project: contract["sites"][1][
                "unprimed_review"
            ].update(
                {"evidence": contract["sites"][0]["unprimed_review"]["evidence"]}
            ),
            "same-bytes": lambda contract, project: contract["sites"][1][
                "unprimed_review"
            ].update(
                {
                    "evidence": write_ref(
                        project,
                        "reviews/site-b-duplicate-bytes.md",
                        b"Unprimed observations for site-a.\n",
                    )
                }
            ),
            "whole-reuses-site": lambda contract, project: contract[
                "whole_system_review"
            ].update(
                {"evidence": contract["sites"][0]["unprimed_review"]["evidence"]}
            ),
        }
        expected_codes = {
            "same-reference": "duplicate-review-evidence-path",
            "same-bytes": "duplicate-review-evidence-bytes",
            "whole-reuses-site": "duplicate-review-evidence-path",
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory(
                prefix="design-dna-batch-duplicate-review-"
            ) as temporary:
                project = Path(temporary)
                contract = make_contract(project)
                mutate(contract, project)
                self.contract_validator.validate(contract)
                write_contract(project, contract)
                result = run_audit(project)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(
                    stderr_payload(result)["error"]["code"],
                    expected_codes[name],
                )

    def test_correctly_blocked_is_separate_and_not_missing_capture_failure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-batch-block-") as temporary:
            project = Path(temporary)
            contract = make_contract(project, ("built", "built", "blocked"))
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 1, result.stderr)
            report = json.loads((project / ".design-dna" / "batch-range-audit.json").read_text(encoding="utf-8"))
            self.report_validator.validate(report)
            self.assertEqual(report["summary"]["built_site_count"], 2)
            self.assertEqual(report["summary"]["correctly_blocked_site_count"], 1)
            self.assertEqual(
                report["correctly_blocked"][0]["blocker"]["classification"],
                "declared-correctly-blocked",
            )
            codes = {item["code"] for item in report["gaps"]}
            self.assertIn("fewer-than-three-built-sites", codes)
            self.assertNotIn("required-capture-missing", codes)

    def test_planned_is_honest_incomplete_coverage_and_creates_no_build_root(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-batch-planned-") as temporary:
            project = Path(temporary)
            contract = make_contract(project, ("planned", "built", "built"))
            planned_root = project / "builds" / "site-a"
            self.assertFalse(planned_root.exists())
            self.contract_validator.validate(contract)
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertTrue(json.loads(result.stdout)["execution_ok"])
            report = json.loads(
                (project / ".design-dna" / "batch-range-audit.json").read_text(
                    encoding="utf-8"
                )
            )
            self.report_validator.validate(report)
            self.assertEqual(report["summary"]["planned_site_count"], 1)
            self.assertEqual(report["summary"]["built_site_count"], 2)
            self.assertEqual(report["summary"]["correctly_blocked_site_count"], 0)
            self.assertEqual(report["planned_sites"][0]["status"], "planned")
            self.assertEqual(report["planned_sites"][0]["pages"][0]["status"], "planned")
            self.assertEqual(report["planned_sites"][0]["pages"][0]["captures"], [])
            self.assertNotIn("site-a", {site["id"] for site in report["built_sites"]})
            self.assertNotIn("site-a", {site["id"] for site in report["correctly_blocked"]})
            codes = {item["code"] for item in report["gaps"]}
            self.assertIn("site-planned", codes)
            self.assertIn("fewer-than-three-built-sites", codes)
            self.assertNotIn("required-capture-missing", codes)
            self.assertFalse(report["comparison_ready"])
            self.assertFalse(planned_root.exists())

    def test_planned_forbids_capture_review_evidence_and_blocker(self) -> None:
        mutations = {
            "capture": lambda contract, project: contract["sites"][0]["pages"][0][
                "captures"
            ].append(
                {
                    "viewport_class": "wide",
                    **write_ref(project, "captures/planned.png", png()),
                }
            ),
            "complete-review": lambda contract, project: contract["sites"][0].update(
                {
                    "unprimed_review": {
                        "status": "complete",
                        "reviewer_id": "reviewer-a",
                        "diagnostic_material_seen_before_observation": False,
                        "evidence": write_ref(
                            project,
                            "reviews/planned.md",
                            b"Review evidence must not predate the build.\n",
                        ),
                    }
                }
            ),
            "blocker": lambda contract, project: contract["sites"][0].update(
                {
                    "blocker": {
                        "code": "not-a-planned-state",
                        "summary": "A planned case cannot simultaneously claim a blocking condition.",
                        "unblock_condition": "Remove the blocker or classify the case as correctly blocked.",
                        "evidence": [
                            write_ref(project, "blocks/planned.md", b"Invalid mixed lifecycle.\n")
                        ],
                    }
                }
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory(
                prefix="design-dna-batch-planned-invalid-"
            ) as temporary:
                project = Path(temporary)
                contract = make_contract(project, ("planned", "built", "built"))
                mutate(contract, project)
                with self.assertRaises(ValidationError):
                    self.contract_validator.validate(contract)
                write_contract(project, contract)
                result = run_audit(project)
                self.assertEqual(result.returncode, 2)
                expected_code = (
                    "planned-case-has-captures"
                    if name == "capture"
                    else "invalid-contract"
                )
                self.assertEqual(
                    stderr_payload(result)["error"]["code"],
                    expected_code,
                )

    def test_built_captures_require_resolved_data_handling_and_authorized_atlas(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-batch-data-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            contract["data_handling"] = {
                "status": "pending",
                "capture_authorization": {"status": "pending", "basis": None},
                "contact_sheet_authorization": {"status": "pending", "basis": None},
                "classification": "confidential",
                "recipients": [],
                "access_scope": None,
                "retention": {
                    "mode": "pending",
                    "owner": None,
                    "delete_or_review_on": None,
                    "reason": "The accountable owner has not set retention or deletion terms yet.",
                },
                "transformations": [
                    {
                        "id": "private-copy-exclusion",
                        "kind": "exclusion",
                        "scope": "site-a:/",
                        "description": "A private account panel is excluded from the saved evaluation capture.",
                        "coverage_impact": "The comparison cannot support findings about that excluded account state.",
                    }
                ],
            }
            self.contract_validator.validate(contract)
            write_contract(project, contract)
            atlas = project / "records" / "unauthorized-atlas.png"
            result = run_audit(
                project,
                "--atlas",
                "records/unauthorized-atlas.png",
            )
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertTrue(json.loads(result.stdout)["execution_ok"])
            report = json.loads(
                (project / ".design-dna" / "batch-range-audit.json").read_text(
                    encoding="utf-8"
                )
            )
            self.report_validator.validate(report)
            codes = {gap["code"] for gap in report["gaps"]}
            self.assertIn("data-handling-unresolved", codes)
            self.assertIn("contact-sheet-authorization-unresolved", codes)
            self.assertEqual(report["atlas"]["status"], "authorization-unavailable")
            self.assertFalse(atlas.exists())
            self.assertEqual(
                report["data_handling"]["transformations"][0]["coverage_impact"],
                "The comparison cannot support findings about that excluded account state.",
            )
            self.assertTrue(
                any(
                    "does not inspect pixels" in limitation
                    for limitation in report["limitations"]
                )
            )

    def test_built_implementation_isolation_must_be_attested_and_uncompromised(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-batch-isolation-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            isolation = contract["sites"][0]["implementation_isolation"]
            isolation.update(
                {
                    "status": "pending",
                    "sibling_output_exposure": {
                        "state": "not-started",
                        "timing": "not-applicable",
                        "details": "The implementation attestation has not yet been completed for this built case.",
                    },
                    "attested_by": None,
                    "attested_at": None,
                }
            )
            self.contract_validator.validate(contract)
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 1, result.stderr)
            report = json.loads(
                (project / ".design-dna" / "batch-range-audit.json").read_text(
                    encoding="utf-8"
                )
            )
            self.report_validator.validate(report)
            self.assertIn(
                "implementation-isolation-pending",
                {gap["code"] for gap in report["gaps"]},
            )
            self.assertEqual(
                report["built_sites"][0]["implementation_isolation"]["status"],
                "pending",
            )

        with tempfile.TemporaryDirectory(prefix="design-dna-batch-exposure-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            contract["sites"][0]["implementation_isolation"][
                "sibling_output_exposure"
            ] = {
                "state": "exposed",
                "timing": "before-unprimed-review",
                "details": "Sibling output was opened before the first unprimed observation was recorded.",
            }
            self.contract_validator.validate(contract)
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 1, result.stderr)
            report = json.loads(
                (project / ".design-dna" / "batch-range-audit.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertIn(
                "implementation-isolation-compromised",
                {gap["code"] for gap in report["gaps"]},
            )

    def test_isolation_evidence_and_context_are_not_replaced_by_unique_brief_bytes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-batch-isolation-required-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            del contract["sites"][0]["implementation_isolation"]
            with self.assertRaises(ValidationError):
                self.contract_validator.validate(contract)
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(stderr_payload(result)["error"]["code"], "invalid-contract")

        with tempfile.TemporaryDirectory(prefix="design-dna-batch-isolation-duplicate-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            contract["sites"][1]["implementation_isolation"][
                "producer_context_id"
            ] = contract["sites"][0]["implementation_isolation"]["producer_context_id"]
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(
                stderr_payload(result)["error"]["code"],
                "duplicate-producer-context-id",
            )

        with tempfile.TemporaryDirectory(prefix="design-dna-batch-source-tamper-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            source_ref = contract["sites"][0]["implementation_isolation"]["source_packet"]
            source_path = project.joinpath(*source_ref["path"].split("/"))
            source_path.write_bytes(source_path.read_bytes() + b"tamper")
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(
                stderr_payload(result)["error"]["code"],
                "evidence-hash-mismatch",
            )

    def test_independence_basis_rejects_id_only_boilerplate(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-batch-independence-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            contract["sites"][0]["independence_basis"] = (
                "Site A is independent from Site B because Site A is separate from Site B only."
            )
            self.contract_validator.validate(contract)
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(
                stderr_payload(result)["error"]["code"],
                "independence-basis-boilerplate",
            )

    def test_missing_declared_viewport_is_coverage_gap(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-batch-gap-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            contract["sites"][0]["pages"][0]["captures"] = contract["sites"][0]["pages"][0]["captures"][:1]
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 1, result.stderr)
            report = json.loads((project / ".design-dna" / "batch-range-audit.json").read_text(encoding="utf-8"))
            self.report_validator.validate(report)
            page = report["built_sites"][0]["pages"][0]
            self.assertEqual(page["status"], "incomplete")
            self.assertEqual(page["missing_required_viewports"], ["narrow"])
            self.assertFalse(report["comparison_ready"])

    def test_tampered_capture_hash_fails_before_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-batch-tamper-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            write_contract(project, contract)
            capture = project.joinpath(*contract["sites"][0]["pages"][0]["captures"][0]["path"].split("/"))
            capture.write_bytes(capture.read_bytes() + b"tamper")
            result = run_audit(project)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(stderr_payload(result)["error"]["code"], "capture-hash-mismatch")
            self.assertFalse((project / ".design-dna" / "batch-range-audit.json").exists())

    def test_capture_must_decode_and_atlas_uses_the_hashed_bytes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-batch-decode-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            capture_record = contract["sites"][0]["pages"][0]["captures"][0]
            capture = project.joinpath(*capture_record["path"].split("/"))
            truncated = capture.read_bytes()[:-12]
            capture.write_bytes(truncated)
            capture_record["sha256"] = digest(truncated)
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(
                stderr_payload(result)["error"]["code"],
                "capture-media-unreadable",
            )
            self.assertFalse(
                (project / ".design-dna" / "batch-range-audit.json").exists()
            )

        auditor_source = AUDITOR.read_text(encoding="utf-8")
        self.assertIn("Image.open(io.BytesIO(payload))", auditor_source)
        self.assertNotIn("Image.open(source)", auditor_source)

    def test_capture_dimensions_must_match_the_declared_viewport_class(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-batch-dimensions-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            contract["study"]["viewport_classes"][0]["width"] = 12
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(
                stderr_payload(result)["error"]["code"],
                "render-capture-viewport-mismatch",
            )

    def test_full_page_capture_binds_viewport_width_and_document_extent(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-batch-full-page-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            site = contract["sites"][0]
            capture = site["pages"][0]["captures"][0]
            capture_path = project.joinpath(*capture["path"].split("/"))
            payload = png(11, 14)
            capture_path.write_bytes(payload)
            capture["sha256"] = digest(payload)
            capture["capture_mode"] = "full-page"

            def update(report: dict[str, object]) -> None:
                rendered = report["captures"][0]
                rendered["screenshot"]["sha256"] = capture["sha256"]
                rendered["screenshot"]["pixel_height"] = 14

            mutate_render_report(project, site, update)
            refresh_review_capture_bindings(contract)
            self.contract_validator.validate(contract)
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(
                (project / ".design-dna" / "batch-range-audit.json").read_text(
                    encoding="utf-8"
                )
            )
            self.report_validator.validate(report)
            first = report["built_sites"][0]["pages"][0]["captures"][0]
            self.assertEqual(first["capture_mode"], "full-page")
            self.assertEqual((first["width"], first["height"]), (11, 14))

        with tempfile.TemporaryDirectory(prefix="design-dna-batch-short-full-page-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            site = contract["sites"][0]
            capture = site["pages"][0]["captures"][0]
            capture_path = project.joinpath(*capture["path"].split("/"))
            payload = png(11, 6)
            capture_path.write_bytes(payload)
            capture["sha256"] = digest(payload)
            capture["capture_mode"] = "full-page"

            def update_short(report: dict[str, object]) -> None:
                rendered = report["captures"][0]
                rendered["screenshot"]["sha256"] = capture["sha256"]
                rendered["screenshot"]["pixel_height"] = 6

            mutate_render_report(project, site, update_short)
            refresh_review_capture_bindings(contract)
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(
                stderr_payload(result)["error"]["code"],
                "capture-dimensions-mismatch",
            )

    def test_capture_is_bound_to_render_route_and_public_build(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-batch-wrong-route-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            site = contract["sites"][0]

            def wrong_route(report: dict[str, object]) -> None:
                report["captures"][0]["route_label"] = "/other/"

            mutate_render_report(project, site, wrong_route)
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(
                stderr_payload(result)["error"]["code"],
                "render-capture-binding-mismatch",
            )

        with tempfile.TemporaryDirectory(prefix="design-dna-batch-build-drift-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            public_file = project / "builds" / "site-a" / "index.html"
            public_file.write_bytes(public_file.read_bytes() + b"drift")
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(
                stderr_payload(result)["error"]["code"],
                "render-build-drift",
            )

    def test_review_exposure_and_chronology_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-batch-sibling-primed-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            contract["sites"][0]["unprimed_review"][
                "sibling_output_seen_before_observation"
            ] = True
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 1, result.stderr)
            report = json.loads(
                (project / ".design-dna" / "batch-range-audit.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertIn(
                "unprimed-review-incomplete",
                {gap["code"] for gap in report["gaps"]},
            )

        chronology_cases = {
            "future-study": (
                lambda contract: contract["study"].update(
                    {"frozen_at": "2999-01-01T00:00:00Z"}
                ),
                "study-freeze-in-future",
            ),
            "attestation-before-freeze": (
                lambda contract: contract["sites"][0]["implementation_isolation"].update(
                    {"attested_at": "2026-08-08T11:00:00Z"}
                ),
                "isolation-attestation-before-freeze",
            ),
            "whole-before-site-freeze": (
                lambda contract: contract["whole_system_review"].update(
                    {"observed_at": "2026-08-08T16:30:00Z"}
                ),
                "whole-review-before-site-reviews-frozen",
            ),
        }
        for name, (mutate, expected) in chronology_cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory(
                prefix="design-dna-batch-chronology-"
            ) as temporary:
                project = Path(temporary)
                contract = make_contract(project)
                mutate(contract)
                write_contract(project, contract)
                result = run_audit(project)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(stderr_payload(result)["error"]["code"], expected)

    def test_site_review_must_bind_the_complete_capture_set(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-batch-review-binding-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            contract["sites"][0]["pages"][0]["captures"][0][
                "capture_mode"
            ] = "full-page"
            self.contract_validator.validate(contract)
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 1, result.stderr)
            report = json.loads(
                (project / ".design-dna" / "batch-range-audit.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertIn(
                "unprimed-review-incomplete",
                {gap["code"] for gap in report["gaps"]},
            )
            refresh_review_capture_bindings(contract)
            write_contract(project, contract)
            repaired = run_audit(project)
            self.assertEqual(repaired.returncode, 0, repaired.stderr)

    def test_no_atlas_run_releases_capture_payloads_but_keeps_counts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-batch-no-atlas-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(
                (project / ".design-dna" / "batch-range-audit.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(report["summary"]["verified_capture_count"], 6)
            self.assertEqual(report["atlas"]["status"], "not-requested")
            source = AUDITOR.read_text(encoding="utf-8")
            self.assertIn("if atlas_requested:", source)
            self.assertIn("re-reads, re-hashes, and decodes one capture at a time", source)

    def test_script_neutral_independence_basis_is_not_english_scored(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-batch-hebrew-basis-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            contract["sites"][0]["independence_basis"] = (
                "הנושא, הקהל, המשימה, מבנה התוכן וחומרי המקור נבחרו בנפרד "
                "ולא נגזרו מאתר אחר במחקר המבוקר."
            )
            self.contract_validator.validate(contract)
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_expired_retention_refuses_comparison_and_new_atlas(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-batch-retention-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            contract["data_handling"]["retention"]["delete_or_review_on"] = "2001-01-01"
            write_contract(project, contract)
            atlas = project / "records" / "expired-atlas.png"
            result = run_audit(
                project,
                "--atlas",
                "records/expired-atlas.png",
            )
            self.assertEqual(result.returncode, 1, result.stderr)
            report = json.loads(
                (project / ".design-dna" / "batch-range-audit.json").read_text(
                    encoding="utf-8"
                )
            )
            self.report_validator.validate(report)
            self.assertTrue(report["data_handling"]["retention"]["expired"])
            self.assertFalse(report["comparison_ready"])
            self.assertFalse(atlas.exists())
            self.assertTrue(
                {"retention-review-expired", "contact-sheet-retention-expired"}
                <= {gap["code"] for gap in report["gaps"]}
            )

    def test_atomic_outputs_do_not_reuse_declared_dot_tmp_siblings(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-batch-atomic-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            report_tmp = write_ref(project, "records/report.json.tmp", b"declared report sibling\n")
            atlas_tmp = write_ref(project, "records/atlas.png.tmp", b"declared atlas sibling\n")
            contract["contextual_findings"][0]["evidence"].extend([report_tmp, atlas_tmp])
            write_contract(project, contract)
            result = run_audit(
                project,
                "--output",
                "records/report.json",
                "--atlas",
                "records/atlas.png",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                (project / "records" / "report.json.tmp").read_bytes(),
                b"declared report sibling\n",
            )
            self.assertEqual(
                (project / "records" / "atlas.png.tmp").read_bytes(),
                b"declared atlas sibling\n",
            )
            source = AUDITOR.read_text(encoding="utf-8")
            self.assertIn("tempfile.mkstemp", source)
            self.assertNotIn('str(path) + ".tmp"', source)

    def test_undeclared_viewport_class_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-batch-viewport-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            contract["sites"][0]["pages"][0]["captures"][0]["viewport_class"] = "phone"
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(stderr_payload(result)["error"]["code"], "undeclared-viewport-class")

    def test_duplicate_normalized_route_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-batch-route-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            contract["sites"][0]["pages"].append(
                {
                    "id": "duplicate-home",
                    "mask_label": "Page 2",
                    "route": "//".replace("//", "/"),
                    "captures": [],
                }
            )
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(stderr_payload(result)["error"]["code"], "duplicate-page-route")

    def test_duplicate_site_and_overlapping_build_roots_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-batch-site-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            contract["sites"][1]["id"] = "site-a"
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(stderr_payload(result)["error"]["code"], "duplicate-site-id")

        with tempfile.TemporaryDirectory(prefix="design-dna-batch-roots-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            nested = project / "builds" / "site-a" / "nested"
            nested.mkdir()
            contract["sites"][1]["build_root"] = "builds/site-a/nested"
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(stderr_payload(result)["error"]["code"], "build-roots-overlap")

        with tempfile.TemporaryDirectory(prefix="design-dna-batch-planned-roots-") as temporary:
            project = Path(temporary)
            contract = make_contract(project, ("planned", "planned", "built"))
            contract["sites"][0]["build_root"] = "future/shared"
            contract["sites"][1]["build_root"] = "future/shared/nested"
            self.assertFalse((project / "future").exists())
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(stderr_payload(result)["error"]["code"], "build-roots-overlap")
            self.assertFalse((project / "future").exists())

    def test_parent_and_absolute_artifact_paths_are_rejected(self) -> None:
        for unsafe in ("../outside.md", "C:/outside.md", "/outside.md"):
            with self.subTest(unsafe=unsafe), tempfile.TemporaryDirectory(
                prefix="design-dna-batch-path-"
            ) as temporary:
                project = Path(temporary)
                contract = make_contract(project)
                contract["sites"][0]["brief"]["path"] = unsafe
                write_contract(project, contract)
                result = run_audit(project)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(stderr_payload(result)["error"]["code"], "invalid-portable-path")

    def test_contract_schema_and_runtime_reject_score_fields(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-batch-score-") as temporary:
            project = Path(temporary)
            contract = make_contract(project)
            contract["ai_score"] = 0
            with self.assertRaises(ValidationError):
                self.contract_validator.validate(contract)
            write_contract(project, contract)
            result = run_audit(project)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(stderr_payload(result)["error"]["code"], "invalid-contract")


if __name__ == "__main__":
    unittest.main()
