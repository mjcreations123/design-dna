from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from maintainer.tests.test_rendered_review_harness import (
    NODE,
    PACKAGE_ROOT,
    available_browser_executable,
    available_playwright_module_dir,
    browser_arguments,
    browser_environment,
    capture_profile,
    capture_scenario,
    make_site,
    run_harness,
    write_capture_manifest,
)


COMPARATOR = (
    PACKAGE_ROOT / "skills" / "design-dna" / "scripts" / "compare_render_reviews.mjs"
)
COMPARISON_SCHEMA = (
    PACKAGE_ROOT / "maintainer" / "schemas" / "render-comparison.schema.json"
)


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def normalized_path_hash(value: Path) -> str:
    normalized = str(value.resolve())
    if sys.platform == "win32":
        normalized = normalized.lower()
    return hashlib.sha256(normalized.encode()).hexdigest()


def parse_single_json_line(raw: str) -> dict[str, object]:
    lines = [line for line in raw.splitlines() if line.strip()]
    if len(lines) != 1:
        raise AssertionError(f"Expected one JSON line, received {len(lines)}: {raw!r}")
    payload = json.loads(lines[0])
    if not isinstance(payload, dict):
        raise AssertionError("Expected a JSON object.")
    return payload


def run_comparator(
    baseline: Path,
    candidate: Path,
    output: Path,
    comparison_id: str,
    module_dir: Path,
    browser: Path,
    comparator: Path = COMPARATOR,
    cwd: Path = PACKAGE_ROOT,
) -> subprocess.CompletedProcess[str]:
    assert NODE is not None
    environment = os.environ.copy()
    environment.update(browser_environment(module_dir))
    return subprocess.run(
        [
            NODE,
            str(comparator),
            str(baseline),
            str(candidate),
            "--output",
            str(output),
            "--comparison-id",
            comparison_id,
            "--masks",
            "none",
            "--browser-executable",
            str(browser),
        ],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        timeout=180,
        check=False,
    )


def resign_render_package(output: Path) -> None:
    report_path = output / "render-review.json"
    marker_path = output / ".design-dna-render-review.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    path_hash = normalized_path_hash(output)
    report["output_identity"]["path_sha256"] = path_hash
    marker["output_identity"] = report["output_identity"]
    marker["build_id_sha256"] = hashlib.sha256(
        report["build"]["id"].encode()
    ).hexdigest()

    for _ in range(10):
        report_payload = json_bytes(report)
        report["artifacts"]["report"]["bytes"] = len(report_payload)
        marker["report"]["bytes"] = len(report_payload)
        marker["report"]["sha256"] = sha256_bytes(report_payload)
        marker_payload = json_bytes(marker)
        report["artifacts"]["marker"]["bytes"] = len(marker_payload)
        next_report_payload = json_bytes(report)
        if (
            len(next_report_payload) == report["artifacts"]["report"]["bytes"]
            and len(marker_payload) == report["artifacts"]["marker"]["bytes"]
        ):
            report_payload = next_report_payload
            marker["report"]["bytes"] = len(report_payload)
            marker["report"]["sha256"] = sha256_bytes(report_payload)
            marker_payload = json_bytes(marker)
            break
    else:
        raise AssertionError("Could not stabilize copied render evidence.")

    report_path.write_bytes(report_payload)
    marker_path.write_bytes(marker_payload)


def copy_and_rebind(source: Path, destination: Path) -> Path:
    shutil.copytree(source, destination)
    resign_render_package(destination)
    return destination


def mutate_report(output: Path, mutator) -> None:
    report_path = output / "render-review.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    mutator(report)
    report_path.write_bytes(json_bytes(report))
    resign_render_package(output)


@unittest.skipUnless(NODE, "Node.js is required for the rendered comparator")
class RenderComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module_dir = available_playwright_module_dir()
        cls.browser = available_browser_executable()
        if cls.module_dir is None:
            raise unittest.SkipTest(
                "Set DESIGN_DNA_PLAYWRIGHT_MODULE_DIR for real browser checks."
            )
        if cls.browser is None:
            raise unittest.SkipTest(
                "Set DESIGN_DNA_BROWSER_EXECUTABLE for real browser checks."
            )

        cls.temporary = tempfile.TemporaryDirectory(
            prefix="design-dna-render-comparison-"
        )
        cls.root = Path(cls.temporary.name)
        manifest = cls.root / "capture-manifest.json"
        profile = capture_profile("comparison-desktop", 1024, 768)
        write_capture_manifest(
            manifest,
            [profile],
            [capture_scenario("comparison-state", [profile["id"]])],
        )

        baseline_site = make_site(cls.root / "baseline-source")
        candidate_site = make_site(cls.root / "candidate-source")
        candidate_css = candidate_site / "styles.css"
        candidate_css.write_text(
            candidate_css.read_text(encoding="utf-8")
            + "\nbody { background: #102f45 !important; }\n",
            encoding="utf-8",
        )
        cls.baseline_output = cls.root / "baseline-review"
        cls.candidate_output = cls.root / "candidate-review"
        for site, output, build_id in (
            (baseline_site, cls.baseline_output, "comparison-baseline"),
            (candidate_site, cls.candidate_output, "comparison-candidate"),
        ):
            result = run_harness(
                *browser_arguments(
                    site,
                    output,
                    cls.browser,
                    build_id,
                    "--capture-manifest",
                    str(manifest),
                ),
                environment=browser_environment(cls.module_dir),
            )
            if result.returncode != 0:
                raise AssertionError(result.stderr)

        incompatible_manifest = cls.root / "incompatible-manifest.json"
        write_capture_manifest(
            incompatible_manifest,
            [profile],
            [
                capture_scenario(
                    "comparison-state",
                    [profile["id"]],
                )
                | {"state_label": "A different reviewed state"}
            ],
        )
        cls.incompatible_output = cls.root / "incompatible-review"
        incompatible = run_harness(
            *browser_arguments(
                candidate_site,
                cls.incompatible_output,
                cls.browser,
                "comparison-incompatible",
                "--capture-manifest",
                str(incompatible_manifest),
            ),
            environment=browser_environment(cls.module_dir),
        )
        if incompatible.returncode != 0:
            raise AssertionError(incompatible.stderr)

        cls.schema = json.loads(COMPARISON_SCHEMA.read_text(encoding="utf-8"))
        cls.validator = Draft202012Validator(
            cls.schema,
            format_checker=FormatChecker(),
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_help_exposes_manual_offline_contract(self) -> None:
        result = subprocess.run(
            [NODE, str(COMPARATOR), "--help"],
            cwd=PACKAGE_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--masks none", result.stdout)
        self.assertIn("human-accept-reject-required", result.stdout)
        self.assertIn("never approves", result.stdout)
        self.assertIn("accesses the network", result.stdout)

    def test_remote_input_is_rejected_without_network_or_browser_loading(self) -> None:
        output = self.root / "remote-input-comparison"
        empty_modules = self.root / "empty-modules"
        empty_modules.mkdir(exist_ok=True)
        environment = os.environ.copy()
        environment.update(
            {
                "DESIGN_DNA_PLAYWRIGHT_MODULE_DIR": str(empty_modules),
                "NODE_PATH": "",
            }
        )
        result = subprocess.run(
            [
                NODE,
                str(COMPARATOR),
                "https://example.invalid/render-review.json",
                str(self.baseline_output / "render-review.json"),
                "--output",
                str(output),
                "--comparison-id",
                "remote-refusal",
                "--masks",
                "none",
            ],
            cwd=PACKAGE_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertFalse(output.exists())
        self.assertEqual(
            parse_single_json_line(result.stderr)["error"]["code"],
            "remote-input-unsupported",
        )

    def test_identical_capture_still_requires_human_decision(self) -> None:
        output = self.root / "identical-comparison"
        result = run_comparator(
            self.baseline_output / "render-review.json",
            self.baseline_output / "render-review.json",
            output,
            "identical",
            self.module_dir,
            self.browser,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = parse_single_json_line(result.stdout)
        self.assertTrue(summary["execution_ok"])
        self.assertTrue(summary["review_required"])
        self.assertFalse(summary["automatic_visual_approval"])
        self.assertEqual(
            summary["decision_status"],
            "human-accept-reject-required",
        )
        self.assertEqual(summary["mismatch_pixels"], 0)

        report_path = output / "render-comparison.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.validator.validate(report)
        self.assertEqual(report["summary"]["changed_capture_count"], 0)
        self.assertEqual(
            report["comparisons"][0]["metrics"]["mismatch_pixel_ratio"],
            0,
        )
        self.assertEqual(report["manual_review"]["status"], "required")
        for name in ("baseline", "actual", "diff"):
            artifact = report["comparisons"][0]["artifacts"][name]
            artifact_path = output / artifact["path"]
            self.assertTrue(artifact_path.is_file())
            self.assertEqual(
                sha256_bytes(artifact_path.read_bytes()),
                artifact["sha256"],
            )
        contact = (output / "comparison.html").read_text(encoding="utf-8")
        self.assertIn("Content-Security-Policy", contact)
        self.assertIn("default-src 'none'", contact)
        self.assertIn("base-uri 'none'", contact)
        marker = json.loads(
            (output / ".design-dna-render-comparison.json").read_text(
                encoding="utf-8"
            )
        )
        report_bytes = report_path.read_bytes()
        self.assertEqual(
            marker["output_identity"]["path_sha256"],
            normalized_path_hash(output),
        )
        self.assertEqual(marker["report"]["bytes"], len(report_bytes))
        self.assertEqual(marker["report"]["sha256"], sha256_bytes(report_bytes))
        serialized = report_path.read_text(encoding="utf-8")
        self.assertNotIn(str(self.baseline_output), serialized)
        self.assertNotIn(str(self.browser.parent), serialized)

    def test_standalone_skill_tree_loads_its_public_schema_and_compares(self) -> None:
        host_root = self.root / "standalone-host"
        standalone_skill = host_root / "skills" / "design-dna"
        shutil.copytree(
            PACKAGE_ROOT / "skills" / "design-dna",
            standalone_skill,
        )
        standalone_comparator = (
            standalone_skill / "scripts" / "compare_render_reviews.mjs"
        )
        self.assertTrue(
            (standalone_skill / "schemas" / "render-review.schema.json").is_file()
        )
        self.assertFalse((host_root / "maintainer").exists())

        output = self.root / "standalone-comparison"
        result = run_comparator(
            self.baseline_output / "render-review.json",
            self.candidate_output / "render-review.json",
            output,
            "standalone-tree",
            self.module_dir,
            self.browser,
            comparator=standalone_comparator,
            cwd=host_root,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(
            (output / "render-comparison.json").read_text(encoding="utf-8")
        )
        self.validator.validate(report)
        self.assertFalse(report["automatic_visual_approval"])
        self.assertEqual(
            report["decision_status"],
            "human-accept-reject-required",
        )

    def test_changed_capture_produces_nonzero_pixel_diff(self) -> None:
        output = self.root / "changed-comparison"
        result = run_comparator(
            self.baseline_output / "render-review.json",
            self.candidate_output / "render-review.json",
            output,
            "changed",
            self.module_dir,
            self.browser,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(
            (output / "render-comparison.json").read_text(encoding="utf-8")
        )
        self.validator.validate(report)
        self.assertEqual(report["summary"]["changed_capture_count"], 1)
        self.assertGreater(report["summary"]["mismatch_pixels"], 0)
        self.assertGreater(report["summary"]["mismatch_pixel_ratio"], 0)
        self.assertFalse(report["automatic_visual_approval"])
        self.assertEqual(
            report["decision_status"],
            "human-accept-reject-required",
        )

    def test_stale_baseline_and_environment_difference_are_reported(self) -> None:
        copied = copy_and_rebind(
            self.baseline_output,
            self.root / "stale-baseline-review",
        )

        def make_stale(report: dict[str, object]) -> None:
            report["execution"]["completed_at"] = "2000-01-01T00:00:00.000Z"
            report["execution"]["browser"]["version"] = "stale-browser-version"

        mutate_report(copied, make_stale)
        output = self.root / "stale-baseline-comparison"
        result = run_comparator(
            copied / "render-review.json",
            self.candidate_output / "render-review.json",
            output,
            "stale-baseline",
            self.module_dir,
            self.browser,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(
            (output / "render-comparison.json").read_text(encoding="utf-8")
        )
        self.validator.validate(report)
        self.assertEqual(report["baseline_freshness"]["status"], "stale")
        self.assertIn(
            "baseline-older-than-30-days-at-candidate-capture",
            report["baseline_freshness"]["warnings"],
        )
        self.assertTrue(
            any(
                item["field"] == "execution.browser.version"
                and item["baseline"] == "stale-browser-version"
                for item in report["compatibility"]["environment_differences"]
            )
        )
        self.assertIn(
            "environment-difference",
            report["compatibility"]["warnings"],
        )

    def test_incompatible_state_contract_fails_closed(self) -> None:
        output = self.root / "incompatible-comparison"
        result = run_comparator(
            self.baseline_output / "render-review.json",
            self.incompatible_output / "render-review.json",
            output,
            "incompatible",
            self.module_dir,
            self.browser,
        )
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertFalse(output.exists())
        payload = parse_single_json_line(result.stderr)
        self.assertEqual(
            payload["error"]["code"],
            "capture-contract-incompatible",
        )
        self.assertFalse(payload["automatic_visual_approval"])

    def test_inconsistent_typography_sampling_evidence_is_rejected(self) -> None:
        copied = copy_and_rebind(
            self.candidate_output,
            self.root / "invalid-typography-sampling-review",
        )

        def invalidate_sampling(report: dict[str, object]) -> None:
            sampling = report["captures"][0]["document"]["typography_sampling"]
            sampling["sampled_count"] += 1

        mutate_report(copied, invalidate_sampling)
        output = self.root / "invalid-typography-sampling-comparison"
        result = run_comparator(
            self.baseline_output / "render-review.json",
            copied / "render-review.json",
            output,
            "invalid-typography-sampling",
            self.module_dir,
            self.browser,
        )
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertFalse(output.exists())
        self.assertEqual(
            parse_single_json_line(result.stderr)["error"]["code"],
            "render-report-invalid",
        )

    def test_tampered_screenshot_is_rejected_before_output(self) -> None:
        copied = copy_and_rebind(
            self.candidate_output,
            self.root / "tampered-review",
        )
        report = json.loads(
            (copied / "render-review.json").read_text(encoding="utf-8")
        )
        screenshot_path = copied / report["captures"][0]["screenshot"]["path"]
        payload = bytearray(screenshot_path.read_bytes())
        payload[-1] ^= 0x01
        screenshot_path.write_bytes(payload)

        output = self.root / "tampered-comparison"
        result = run_comparator(
            self.baseline_output / "render-review.json",
            copied / "render-review.json",
            output,
            "tampered",
            self.module_dir,
            self.browser,
        )
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertFalse(output.exists())
        self.assertEqual(
            parse_single_json_line(result.stderr)["error"]["code"],
            "screenshot-hash-mismatch",
        )

    def test_screenshot_path_escape_is_rejected(self) -> None:
        copied = copy_and_rebind(
            self.candidate_output,
            self.root / "path-escape-review",
        )
        mutate_report(
            copied,
            lambda report: report["captures"][0]["screenshot"].update(
                {"path": "../outside.png"}
            ),
        )

        output = self.root / "path-escape-comparison"
        result = run_comparator(
            self.baseline_output / "render-review.json",
            copied / "render-review.json",
            output,
            "path-escape",
            self.module_dir,
            self.browser,
        )
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertFalse(output.exists())
        self.assertEqual(
            parse_single_json_line(result.stderr)["error"]["code"],
            "screenshot-path-escape",
        )


if __name__ == "__main__":
    unittest.main()
