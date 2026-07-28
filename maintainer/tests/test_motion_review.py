from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[2]
SCRIPTS = PLUGIN / "maintainer" / "scripts"
sys.path.insert(0, str(SCRIPTS))
try:
    import audit_package
finally:
    sys.path.remove(str(SCRIPTS))


MOTION_CODE_PREFIXES = (
    "review-temporal-",
    "release-motion-assessment-",
    "release-significant-motion-",
)


def write_evidence(path: Path, payload: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def temporal_record(
    path: str,
    digest: str,
    *,
    media_type: str = "video/webm",
    captured_at: str | None = None,
) -> dict[str, object]:
    return {
        "path": path,
        "sha256": digest,
        "media_type": media_type,
        "duration_ms": 2400,
        "captured_at": captured_at or datetime.now(timezone.utc).isoformat(),
    }


def context(
    *,
    reduced_motion: str,
    route: str = "/menu",
    state: str = "loaded",
    width: int = 1280,
    temporal: dict[str, object] | None = None,
    checks: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "route": route,
        "state": state,
        "viewport": {
            "width": width,
            "height": 800,
            "device_pixel_ratio": 1,
        },
        "browser": "Chromium 130",
        "environment": {
            "input_modalities": ["keyboard", "pointer"],
            "zoom_percent": 100,
            "text_scale_percent": 100,
            "reduced_motion": reduced_motion,
            "forced_colors": "none",
            "contrast_preference": "no-preference",
            "theme": "light",
            "locale": "en-US",
            "direction": "ltr",
        },
        "checks": checks or [{
            "id": "interaction-state",
            "status": "not-performed",
            "method": "No interaction check was required.",
            "evidence": [],
        }],
    }
    if temporal is not None:
        value["temporal_evidence"] = temporal
    return value


def motion_codes(failures: list[dict[str, str]]) -> set[str]:
    return {
        failure["code"]
        for failure in failures
        if failure["code"].startswith(MOTION_CODE_PREFIXES)
    }


class MotionReviewContractTests(unittest.TestCase):
    def significant_payload(
        self,
        normal: dict[str, object],
        reduced: dict[str, object],
        evidence_paths: list[str],
    ) -> dict[str, object]:
        return {
            "motion_assessment": {
                "classification": "significant",
                "rationale": "Scroll-linked transitions materially change the experience.",
                "expected_behaviors": [
                    "Normal and reduced modes preserve content and state continuity."
                ],
            },
            "contexts": [normal, reduced],
            "evidence_paths": evidence_paths,
        }

    def test_significant_release_requires_a_matched_pair_and_bound_check(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = Path(temporary)
            omitted = {
                "contexts": [],
                "evidence_paths": [],
            }
            self.assertIn(
                "release-motion-assessment-missing",
                motion_codes(audit_package.review_semantic_failures(
                    omitted,
                    plugin,
                    "review.json",
                    release_mode=True,
                )),
            )
            self.assertNotIn(
                "release-motion-assessment-missing",
                motion_codes(audit_package.review_semantic_failures(
                    omitted,
                    plugin,
                    "review.json",
                    release_mode=False,
                )),
            )
            normal_path = "evidence/normal.webm"
            reduced_path = "evidence/reduced.webm"
            check_path = "evidence/reduced-motion.json"
            normal_hash = write_evidence(
                plugin / normal_path,
                b"\x1a\x45\xdf\xa3normal motion recording",
            )
            reduced_hash = write_evidence(
                plugin / reduced_path,
                b"\x1a\x45\xdf\xa3reduced motion recording",
            )
            check_method = "Verified the reduced-motion path with automation."
            check_record = {
                "schema_version": 1,
                "check_id": "reduced-motion",
                "route": "/menu",
                "state": "loaded",
                "method": check_method,
                "result": "passed",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "executor_id": "accessibility-specialist",
                "observations": [
                    "Content and state remained complete with movement reduced."
                ],
            }
            check_hash = write_evidence(
                plugin / check_path,
                json.dumps(check_record, sort_keys=True).encode("utf-8"),
            )

            missing = self.significant_payload(
                context(reduced_motion="no-preference"),
                context(reduced_motion="reduce"),
                [],
            )
            missing_codes = motion_codes(audit_package.review_semantic_failures(
                missing,
                plugin,
                "review.json",
                release_mode=True,
            ))
            self.assertIn(
                "release-significant-motion-normal-evidence-missing",
                missing_codes,
            )
            self.assertIn(
                "release-significant-motion-reduced-evidence-missing",
                missing_codes,
            )
            self.assertEqual(
                motion_codes(audit_package.review_semantic_failures(
                    missing,
                    plugin,
                    "review.json",
                    release_mode=False,
                )),
                set(),
            )

            normal = context(
                reduced_motion="no-preference",
                temporal=temporal_record(normal_path, normal_hash),
            )
            reduced = context(
                reduced_motion="reduce",
                temporal=temporal_record(reduced_path, reduced_hash),
            )
            payload = self.significant_payload(
                normal,
                reduced,
                [normal_path, reduced_path, check_path],
            )
            without_check = motion_codes(
                audit_package.review_semantic_failures(
                    payload,
                    plugin,
                    "review.json",
                    release_mode=True,
                )
            )
            self.assertEqual(
                without_check,
                {"release-significant-motion-reduced-check-missing"},
            )

            unmatched = copy.deepcopy(payload)
            unmatched["contexts"][1]["state"] = "menu-open"
            unmatched_codes = motion_codes(
                audit_package.review_semantic_failures(
                    unmatched,
                    plugin,
                    "review.json",
                    release_mode=True,
                )
            )
            self.assertIn(
                "release-significant-motion-context-unmatched",
                unmatched_codes,
            )

            reduced["checks"] = [{
                "id": "reduced-motion",
                "status": "passed",
                "method": check_method,
                "evidence": [{"path": check_path, "sha256": check_hash}],
            }]
            self.assertEqual(
                motion_codes(audit_package.review_semantic_failures(
                    payload,
                    plugin,
                    "review.json",
                    release_mode=True,
                )),
                set(),
            )

    def test_optional_temporal_records_still_validate_for_none_and_minor(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin = Path(temporary)
            path = "evidence/motion.webm"
            digest = write_evidence(
                plugin / path,
                b"\x1a\x45\xdf\xa3optional motion trace",
            )
            payload = {
                "motion_assessment": {
                    "classification": "minor",
                    "rationale": "Only a short state transition is present.",
                },
                "contexts": [context(
                    reduced_motion="no-preference",
                    temporal=temporal_record(path, digest),
                )],
                "evidence_paths": [path],
            }
            self.assertEqual(
                motion_codes(audit_package.review_semantic_failures(
                    payload,
                    plugin,
                    "review.json",
                    release_mode=True,
                )),
                set(),
            )

            mutations = {
                "review-temporal-hash-mismatch": (
                    "sha256",
                    "0" * 64,
                ),
                "review-temporal-format-invalid": (
                    "media_type",
                    "video/mp4",
                ),
                "review-temporal-time-invalid": (
                    "captured_at",
                    "2026-07-28T12:00:00",
                ),
                "review-temporal-evidence-future": (
                    "captured_at",
                    (
                        datetime.now(timezone.utc) + timedelta(days=1)
                    ).isoformat(),
                ),
            }
            for expected_code, (field, value) in mutations.items():
                with self.subTest(expected_code=expected_code):
                    mutated = copy.deepcopy(payload)
                    mutated["contexts"][0]["temporal_evidence"][field] = value
                    self.assertIn(
                        expected_code,
                        motion_codes(
                            audit_package.review_semantic_failures(
                                mutated,
                                plugin,
                                "review.json",
                                release_mode=True,
                            )
                        ),
                    )

            unbound = copy.deepcopy(payload)
            unbound["contexts"][0]["temporal_evidence"]["path"] = "../motion.webm"
            self.assertIn(
                "review-temporal-evidence-unbound",
                motion_codes(audit_package.review_semantic_failures(
                    unbound,
                    plugin,
                    "review.json",
                    release_mode=True,
                )),
            )

            reused = copy.deepcopy(payload)
            reused["motion_assessment"]["classification"] = "none"
            reused["contexts"].append(context(
                reduced_motion="reduce",
                temporal=temporal_record(path, digest),
            ))
            self.assertIn(
                "review-temporal-evidence-reused",
                motion_codes(audit_package.review_semantic_failures(
                    reused,
                    plugin,
                    "review.json",
                    release_mode=False,
                )),
            )


if __name__ == "__main__":
    unittest.main()
