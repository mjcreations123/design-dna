from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


PLUGIN = Path(__file__).resolve().parents[2]
SCAN = PLUGIN / "skills" / "design-dna" / "scripts" / "scan_project.py"
RESULT_SCHEMA = (
    PLUGIN / "maintainer" / "schemas" / "scan-result.schema.json"
)
ACTIVE_EXPIRY = (date.today() + timedelta(days=30)).isoformat()


def run_scan(project: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(SCAN), str(project), *arguments],
        text=True,
        encoding="utf-8",
        capture_output=True,
        env=environment,
        timeout=120,
    )


def stdout_payload(
    result: subprocess.CompletedProcess[str],
) -> dict[str, object]:
    return json.loads(result.stdout)


class ScannerV3FillerTests(unittest.TestCase):
    def test_labels_and_html_entities_cannot_hide_visible_filler(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.html").write_text(
                "<p>Placeholder: Lorem ipsum</p>\n"
                "<p>Sample: Lorem&nbsp;ipsum</p>\n"
                "<p>Example: L&#111;rem&#32;ipsum</p>\n",
                encoding="utf-8",
            )

            result = run_scan(project, "--json", "--fail-on", "high")
            self.assertEqual(result.returncode, 1, result.stderr)
            findings = [
                item
                for item in stdout_payload(result)["findings"]
                if item["rule"] == "placeholder-proof"
            ]
            self.assertEqual(len(findings), 3)
            self.assertTrue(
                all(item["classification"] == "gate" for item in findings)
            )
            self.assertEqual({item["line"] for item in findings}, {1, 2, 3})

    def test_explicit_instruction_remains_a_negative_example(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.html").write_text(
                "<p>Do not use L&#111;rem&nbsp;ipsum as final copy.</p>",
                encoding="utf-8",
            )
            result = run_scan(project, "--json", "--fail-on", "high")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(
                any(
                    item["rule"] == "placeholder-proof"
                    for item in stdout_payload(result)["findings"]
                )
            )


class ScannerV3CoverageTests(unittest.TestCase):
    def test_zero_eligible_and_zero_selected_sources_are_nonpasses(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            empty = Path(temporary) / "empty"
            excluded = Path(temporary) / "excluded"
            empty.mkdir()
            excluded.mkdir()
            (excluded / "README.md").write_text(
                "Project notes only.",
                encoding="utf-8",
            )

            no_eligible = run_scan(empty, "--json")
            self.assertEqual(no_eligible.returncode, 1, no_eligible.stderr)
            no_eligible_payload = stdout_payload(no_eligible)
            self.assertEqual(
                no_eligible_payload["quality_status"],
                "no-eligible-sources",
            )
            self.assertFalse(no_eligible_payload["source_gate_passed"])
            self.assertEqual(
                no_eligible_payload["scan_scope"]["scanned_file_count"],
                0,
            )

            no_selected = run_scan(excluded, "--json")
            self.assertEqual(no_selected.returncode, 1, no_selected.stderr)
            no_selected_payload = stdout_payload(no_selected)
            self.assertEqual(
                no_selected_payload["quality_status"],
                "no-selected-sources",
            )
            self.assertFalse(no_selected_payload["source_gate_passed"])
            self.assertEqual(
                no_selected_payload["scan_scope"]["eligible_file_count"],
                1,
            )

    def test_skipped_acknowledgement_is_content_bound_and_never_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            source = project / "page.tsx"
            source.write_bytes(b"\xff\xfe\xfd")

            initial = run_scan(project, "--json", "--advisory-exit-zero")
            self.assertEqual(initial.returncode, 0, initial.stderr)
            skipped = stdout_payload(initial)["skipped_sources"][0]
            acknowledgement = {
                "path": skipped["file"],
                "sha256": skipped["sha256"],
                "size_bytes": skipped["size_bytes"],
                "reason": "Reviewed exact source bytes outside this scanner.",
                "owner": "Repository owner",
                "expires": ACTIVE_EXPIRY,
            }
            allowlist = project / "allow.json"
            allowlist.write_text(
                json.dumps({
                    "schema_version": 1,
                    "allow": [],
                    "acknowledge_skipped": [acknowledgement],
                }),
                encoding="utf-8",
            )

            acknowledged = run_scan(
                project,
                "--allowlist",
                str(allowlist),
                "--json",
            )
            self.assertEqual(acknowledged.returncode, 1, acknowledged.stderr)
            acknowledged_payload = stdout_payload(acknowledged)
            self.assertFalse(acknowledged_payload["source_gate_passed"])
            self.assertEqual(
                acknowledged_payload["quality_status"],
                "acknowledged-incomplete",
            )
            self.assertEqual(
                acknowledged_payload["acknowledged_skipped_files"],
                ["page.tsx"],
            )

            source.write_bytes(b"\xff\xfe\xfc")
            changed = run_scan(
                project,
                "--allowlist",
                str(allowlist),
                "--json",
            )
            self.assertEqual(changed.returncode, 1, changed.stderr)
            changed_payload = stdout_payload(changed)
            self.assertEqual(changed_payload["quality_status"], "incomplete")
            self.assertEqual(
                changed_payload["unacknowledged_skipped_files"],
                ["page.tsx"],
            )

    def test_common_web_suffixes_are_selected(self) -> None:
        suffixes = (
            "less",
            "styl",
            "stylus",
            "ejs",
            "jinja",
            "jinja2",
            "j2",
            "gohtml",
            "tmpl",
            "tpl",
        )
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            for suffix in suffixes:
                (project / f"source.{suffix}").write_text(
                    "body { color: #123456; }\n",
                    encoding="utf-8",
                )
            result = run_scan(project, "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            result_payload = stdout_payload(result)
            self.assertEqual(
                result_payload["scan_scope"]["scanned_file_count"],
                len(suffixes),
            )
            for suffix in suffixes:
                self.assertIn(
                    f".{suffix}",
                    result_payload["source_coverage"]["suffixes"],
                )

    def test_built_output_is_explicit_and_vendor_stays_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            dist = project / "dist"
            dependency = project / "node_modules" / "package"
            dist.mkdir()
            dependency.mkdir(parents=True)
            (dist / "page.html").write_text(
                "<p>Lorem ipsum</p>",
                encoding="utf-8",
            )
            (dependency / "page.html").write_text(
                "<p>Lorem ipsum</p>",
                encoding="utf-8",
            )

            normal = run_scan(project, "--json")
            self.assertEqual(normal.returncode, 1, normal.stderr)
            self.assertEqual(
                stdout_payload(normal)["quality_status"],
                "no-eligible-sources",
            )

            built = run_scan(project, "--built-output", "--json")
            self.assertEqual(built.returncode, 1, built.stderr)
            built_payload = stdout_payload(built)
            self.assertTrue(built_payload["built_output_mode"])
            self.assertEqual(
                built_payload["scan_scope"]["eligible_file_count"],
                1,
            )
            self.assertEqual(
                {
                    item["file"]
                    for item in built_payload["findings"]
                    if item["rule"] == "placeholder-proof"
                },
                {"dist/page.html"},
            )
            self.assertEqual(
                set(
                    built_payload["source_coverage"][
                        "dependency_vendor_exclusions"
                    ]
                ),
                {"node_modules", "vendor"},
            )


class ScannerV3FalsePositiveTests(unittest.TestCase):
    def test_cream_and_sage_prose_is_not_a_palette_signal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.html").write_text(
                "<h1>Ice cream and sage advice</h1>",
                encoding="utf-8",
            )
            (project / "style.css").write_text(
                "h1 { font-family: Georgia, serif; }",
                encoding="utf-8",
            )
            result = run_scan(project, "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(
                any(
                    item["rule"] == "cream-serif-sage-cluster"
                    for item in stdout_payload(result)["findings"]
                )
            )

    def test_fade_names_are_neutral_at_every_count(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            for route in ("one", "two", "three"):
                (project / f"{route}.tsx").write_text(
                    '<section className="fade-up">Route</section>',
                    encoding="utf-8",
                )
            first = run_scan(project, "--json")
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertFalse(
                any(
                    item["rule"] == "stock-fade-up"
                    for item in stdout_payload(first)["findings"]
                )
            )

            (project / "repeated.tsx").write_text(
                '<div className="fade-up"></div>\n'
                '<div className="fade-up"></div>\n'
                '<div className="fade-up"></div>\n',
                encoding="utf-8",
            )
            repeated = run_scan(project, "--json")
            self.assertEqual(repeated.returncode, 0, repeated.stderr)
            fade_findings = [
                item
                for item in stdout_payload(repeated)["findings"]
                if item["rule"] == "stock-fade-up"
            ]
            self.assertEqual(fade_findings, [])

    def test_hidden_reveal_content_prompts_fail_open_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "style.css").write_text(
                ".reveal { opacity: 0; transform: translateY(1rem); }\n"
                ".reveal.is-visible { opacity: 1; transform: none; }\n",
                encoding="utf-8",
            )
            hidden = run_scan(project, "--json")
            self.assertEqual(hidden.returncode, 0, hidden.stderr)
            hidden_findings = [
                item
                for item in stdout_payload(hidden)["findings"]
                if item["rule"] == "deferred-content-visibility"
            ]
            self.assertEqual(len(hidden_findings), 1)
            self.assertEqual(hidden_findings[0]["severity"], "medium")
            self.assertEqual(hidden_findings[0]["owner_policy"], "require")

            (project / "style.css").write_text(
                ".reveal { opacity: 1; transform: none; }\n"
                ".reveal.is-visible { animation: reveal-in 600ms both; }\n",
                encoding="utf-8",
            )
            visible = run_scan(project, "--json")
            self.assertEqual(visible.returncode, 0, visible.stderr)
            self.assertFalse(
                any(
                    item["rule"] == "deferred-content-visibility"
                    for item in stdout_payload(visible)["findings"]
                )
            )

    def test_semantic_hover_motion_is_not_generic_lift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "style.css").write_text(
                ".site-nav a:hover::after { transform: scaleX(1); }\n"
                ".button:hover::after { transform: scaleX(1); }\n"
                ".text-link:hover span { transform: translateX(.35rem); }\n"
                ".symptom:hover::before { transform: translateX(0); }\n"
                ".turn-arrow:hover { transform: rotate(6deg); }\n",
                encoding="utf-8",
            )
            (project / "page.html").write_text(
                '<a class="hover:scale-100 hover:shadow-none '
                'hover:-translate-y-0 hover:scale-x-100">Route</a>\n',
                encoding="utf-8",
            )

            result = run_scan(project, "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(
                any(
                    item["rule"] == "generic-hover-lift"
                    for item in stdout_payload(result)["findings"]
                )
            )

    def test_repeated_css_hover_lift_scale_and_glow_are_neutral(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "style.css").write_text(
                ".card:hover { transform: translateY(-.25rem); }\n"
                ".tile:hover { box-shadow: 0 .75rem 2rem rgb(0 0 0 / .2); }\n"
                ".control:hover { transform: scale(1.03); }\n",
                encoding="utf-8",
            )

            result = run_scan(project, "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            findings = [
                item
                for item in stdout_payload(result)["findings"]
                if item["rule"] == "generic-hover-lift"
            ]
            self.assertEqual(findings, [])

    def test_repeated_tailwind_hover_lift_scale_and_glow_are_neutral(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.html").write_text(
                '<article class="hover:-translate-y-1">Lift</article>\n'
                '<button class="hover:scale-105">Grow</button>\n'
                '<a class="hover:shadow-lg">Glow</a>\n',
                encoding="utf-8",
            )

            result = run_scan(project, "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            findings = [
                item
                for item in stdout_payload(result)["findings"]
                if item["rule"] == "generic-hover-lift"
            ]
            self.assertEqual(findings, [])


class ScannerV3SchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        schema = json.loads(RESULT_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        cls.validator = Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        )

    def test_success_and_incomplete_results_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.html").write_text(
                "<main>Reviewed content</main>",
                encoding="utf-8",
            )
            success = run_scan(project, "--json")
            self.assertEqual(success.returncode, 0, success.stderr)
            self.validator.validate(stdout_payload(success))

            (project / "broken.tsx").write_bytes(b"\xff")
            incomplete = run_scan(
                project,
                "--json",
                "--advisory-exit-zero",
            )
            self.assertEqual(incomplete.returncode, 0, incomplete.stderr)
            self.validator.validate(stdout_payload(incomplete))

    def test_execution_failure_validates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "missing"
            result = run_scan(missing, "--json")
            self.assertEqual(result.returncode, 2)
            self.validator.validate(json.loads(result.stderr))


if __name__ == "__main__":
    unittest.main()
