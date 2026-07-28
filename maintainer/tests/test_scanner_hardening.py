from __future__ import annotations

import json
import os
import runpy
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


PLUGIN = Path(__file__).resolve().parents[2]
SCAN = PLUGIN / "skills" / "design-dna" / "scripts" / "scan_project.py"
ACTIVE_EXPIRY = (date.today() + timedelta(days=30)).isoformat()
OVERLONG_EXPIRY = (date.today() + timedelta(days=91)).isoformat()
CURRENT_SHADCN_LIGHT = """\
:root {
  --background: oklch(1 0 0);
  --foreground: oklch(0.145 0 0);
  --card: oklch(1 0 0);
  --card-foreground: oklch(0.145 0 0);
  --popover: oklch(1 0 0);
  --popover-foreground: oklch(0.145 0 0);
  --primary: oklch(0.205 0 0);
  --primary-foreground: oklch(0.985 0 0);
  --secondary: oklch(0.97 0 0);
  --secondary-foreground: oklch(0.205 0 0);
  --muted: oklch(0.97 0 0);
  --muted-foreground: oklch(0.556 0 0);
  --accent: oklch(0.97 0 0);
  --accent-foreground: oklch(0.205 0 0);
  --destructive: oklch(0.577 0.245 27.325);
  --border: oklch(0.922 0 0);
  --input: oklch(0.922 0 0);
  --ring: oklch(0.708 0 0);
}
"""
CURRENT_SHADCN_DARK = """\
.dark {
  --background: oklch(0.145 0 0);
  --foreground: oklch(0.985 0 0);
  --card: oklch(0.205 0 0);
  --card-foreground: oklch(0.985 0 0);
  --popover: oklch(0.205 0 0);
  --popover-foreground: oklch(0.985 0 0);
  --primary: oklch(0.922 0 0);
  --primary-foreground: oklch(0.205 0 0);
  --secondary: oklch(0.269 0 0);
  --secondary-foreground: oklch(0.985 0 0);
  --muted: oklch(0.269 0 0);
  --muted-foreground: oklch(0.708 0 0);
  --accent: oklch(0.269 0 0);
  --accent-foreground: oklch(0.985 0 0);
  --destructive: oklch(0.704 0.191 22.216);
  --border: oklch(1 0 0 / 10%);
  --input: oklch(1 0 0 / 15%);
  --ring: oklch(0.556 0 0);
}
"""


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


def payload(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return json.loads(result.stdout)


class ScannerScopeAndClassificationTests(unittest.TestCase):
    def test_runtime_skill_self_scan_excludes_reference_documentation(self) -> None:
        runtime_skill = PLUGIN / "skills" / "design-dna"
        result = run_scan(
            runtime_skill,
            "--json",
            "--fail-on",
            "high",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result_payload = payload(result)
        self.assertTrue(result_payload["ok"])
        self.assertTrue(result_payload["gate_enforced"])
        self.assertTrue(result_payload["gate_passed"])
        self.assertEqual(result_payload["exit_code"], 0)
        self.assertEqual(result_payload["scan_status"], "scope-limited")
        self.assertFalse(result_payload["scan_complete"])
        self.assertEqual(sum(result_payload["gate_counts"].values()), 0)
        self.assertIn(
            "references/risk-rubric.md",
            result_payload["excluded_default_files"],
        )

    def test_gate_exit_and_json_text_status_cannot_contradict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.html").write_text(
                "<p>Lorem ipsum</p>",
                encoding="utf-8",
            )

            gated = run_scan(project, "--json", "--fail-on", "high")
            self.assertEqual(gated.returncode, 1, gated.stderr)
            gated_payload = payload(gated)
            self.assertFalse(gated_payload["ok"])
            self.assertTrue(gated_payload["gate_enforced"])
            self.assertEqual(gated_payload["gate_threshold"], "high")
            self.assertFalse(gated_payload["gate_passed"])
            self.assertEqual(gated_payload["exit_code"], 1)

            gated_text = run_scan(project, "--fail-on", "high")
            self.assertEqual(gated_text.returncode, 1, gated_text.stderr)
            self.assertIn(
                "QUALITY/POLICY STATUS: FAILED",
                gated_text.stdout,
            )
            self.assertIn(
                "EXIT POLICY: TRIGGERED (--fail-on high; exit 1).",
                gated_text.stdout,
            )

            default = run_scan(project, "--json")
            self.assertEqual(default.returncode, 1, default.stderr)
            default_payload = payload(default)
            self.assertFalse(default_payload["ok"])
            self.assertTrue(default_payload["execution_ok"])
            self.assertFalse(default_payload["quality_passed"])
            self.assertEqual(default_payload["quality_status"], "failed")
            self.assertEqual(default_payload["gate_status"], "failed")
            self.assertEqual(default_payload["gate_threshold"], "high")
            self.assertTrue(default_payload["exit_policy"]["enforced"])
            self.assertTrue(default_payload["exit_policy"]["triggered"])

            advisory = run_scan(
                project,
                "--json",
                "--advisory-exit-zero",
            )
            self.assertEqual(advisory.returncode, 0, advisory.stderr)
            advisory_payload = payload(advisory)
            self.assertFalse(advisory_payload["ok"])
            self.assertTrue(advisory_payload["execution_ok"])
            self.assertFalse(advisory_payload["quality_passed"])
            self.assertFalse(advisory_payload["gate_enforced"])
            self.assertEqual(advisory_payload["gate_threshold"], "none")
            self.assertFalse(advisory_payload["gate_passed"])
            self.assertEqual(advisory_payload["gate_status"], "failed")
            self.assertFalse(advisory_payload["exit_policy"]["enforced"])
            self.assertFalse(advisory_payload["exit_policy"]["triggered"])
            self.assertTrue(
                advisory_payload["exit_policy"]["explicit_advisory_exit_zero"]
            )
            self.assertFalse(
                advisory_payload["exit_policy"]["explicit_fail_on_none"]
            )
            self.assertEqual(advisory_payload["exit_code"], 0)

            explicit_none = run_scan(
                project,
                "--json",
                "--fail-on",
                "none",
            )
            self.assertEqual(explicit_none.returncode, 0, explicit_none.stderr)
            explicit_none_payload = payload(explicit_none)
            self.assertFalse(explicit_none_payload["quality_passed"])
            self.assertFalse(
                explicit_none_payload["exit_policy"][
                    "explicit_advisory_exit_zero"
                ]
            )
            self.assertTrue(
                explicit_none_payload["exit_policy"]["explicit_fail_on_none"]
            )

    def test_common_module_and_server_template_sources_are_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            sources = {
                "config.mjs": "export default { fontFamily: 'Inter' };",
                "config.cjs": "module.exports = { fontFamily: 'Inter' };",
                "page.liquid": (
                    "<style>.title { font-family: Inter; }</style>"
                    '<h1>Made <span style="color: #7c3aed">daily</span></h1>'
                ),
                "page.twig": "<style>.title { font-family: Inter; }</style>",
                "page.php": "<style>.title { font-family: Inter; }</style>",
                "page.erb": "<style>.title { font-family: Inter; }</style>",
                "page.razor": "<style>.title { font-family: Inter; }</style>",
                "page.cshtml": "<style>.title { font-family: Inter; }</style>",
                "page.hbs": "<style>.title { font-family: Inter; }</style>",
                "page.handlebars": (
                    "<style>.title { font-family: Inter; }</style>"
                ),
                "page.njk": "<style>.title { font-family: Inter; }</style>",
                "page.mustache": (
                    "<style>.title { font-family: Inter; }</style>"
                ),
                "page.svg": (
                    '<svg><style>.title { font-family: Inter; }</style></svg>'
                ),
                "page.pug": ".title { font-family: Inter; }",
            }
            for name, content in sources.items():
                (project / name).write_text(content, encoding="utf-8")
            story = project / "stories" / "ignored.liquid"
            story.parent.mkdir()
            story.write_text(
                "<style>.title { font-family: Inter; }</style>",
                encoding="utf-8",
            )

            result = run_scan(project, "--json")
            self.assertEqual(
                result.returncode, 0, result.stdout + result.stderr
            )
            result_payload = payload(result)
            watched_files = {
                item["file"]
                for item in result_payload["findings"]
                if item["rule"] == "unexamined-default-font"
            }
            self.assertEqual(watched_files, set(sources))
            liquid_fragments = [
                item
                for item in result_payload["findings"]
                if item["rule"] == "decorative-headline-span"
                and item["file"] == "page.liquid"
            ]
            self.assertEqual(len(liquid_fragments), 1)
            self.assertEqual(
                liquid_fragments[0]["classification"],
                "advisory",
            )
            self.assertIn(
                "stories/ignored.liquid",
                result_payload["excluded_default_files"],
            )
            coverage = result_payload["source_coverage"]
            self.assertTrue(coverage["bounded"])
            self.assertTrue(
                {
                    ".mjs",
                    ".cjs",
                    ".liquid",
                    ".twig",
                    ".php",
                    ".erb",
                    ".razor",
                    ".cshtml",
                    ".hbs",
                    ".handlebars",
                    ".njk",
                    ".mustache",
                    ".svg",
                    ".pug",
                }.issubset(set(coverage["suffixes"]))
            )
            self.assertIn("dynamically rendered", coverage["note"])

            included = run_scan(
                project,
                "--json",
                "--include",
                "stories/**",
            )
            self.assertEqual(
                included.returncode, 0, included.stdout + included.stderr
            )
            included_files = {
                item["file"]
                for item in payload(included)["findings"]
                if item["rule"] == "unexamined-default-font"
            }
            self.assertIn("stories/ignored.liquid", included_files)

    def test_watched_font_detection_covers_css_font_shorthand_conservatively(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            detected = root / "detected"
            ignored = root / "ignored"
            detected.mkdir()
            ignored.mkdir()
            (detected / "style.css").write_text(
                '.hero { font: italic 700 2rem/1.1 "Inter", sans-serif; }\n',
                encoding="utf-8",
            )
            (ignored / "style.css").write_text(
                '.note::before { content: "font: Inter"; }\n',
                encoding="utf-8",
            )

            found = run_scan(detected, "--json")
            self.assertEqual(found.returncode, 0, found.stderr)
            watched = [
                item
                for item in payload(found)["findings"]
                if item["rule"] == "unexamined-default-font"
            ]
            self.assertEqual(len(watched), 1)
            self.assertIn("font:", watched[0]["matched_signal"])
            self.assertIn("Inter", watched[0]["matched_signal"])

            not_found = run_scan(ignored, "--json")
            self.assertEqual(not_found.returncode, 0, not_found.stderr)
            self.assertFalse(
                any(
                    item["rule"] == "unexamined-default-font"
                    for item in payload(not_found)["findings"]
                )
            )

    def test_default_content_exclusions_can_be_explicitly_included(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            for directory in ("docs", "tests", "stories", "fixtures"):
                target = project / directory / "example.html"
                target.parent.mkdir(parents=True)
                target.write_text(
                    "<p>Lorem ipsum</p>",
                    encoding="utf-8",
                )

            default = run_scan(project, "--json", "--fail-on", "high")
            self.assertEqual(
                default.returncode, 0, default.stdout + default.stderr
            )
            default_payload = payload(default)
            self.assertFalse(
                any(
                    item["rule"] == "placeholder-proof"
                    for item in default_payload["findings"]
                )
            )
            self.assertEqual(
                set(default_payload["excluded_default_files"]),
                {
                    "docs/example.html",
                    "fixtures/example.html",
                    "stories/example.html",
                    "tests/example.html",
                },
            )

            included = run_scan(
                project,
                "--json",
                "--fail-on",
                "high",
                "--include",
                "docs/**",
            )
            self.assertEqual(
                included.returncode, 1, included.stdout + included.stderr
            )
            included_payload = payload(included)
            proof = [
                item
                for item in included_payload["findings"]
                if item["rule"] == "placeholder-proof"
            ]
            self.assertEqual(len(proof), 1)
            self.assertEqual(proof[0]["file"], "docs/example.html")
            self.assertEqual(proof[0]["classification"], "gate")

    def test_content_site_and_structured_content_are_explicit_safe_modes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            docs = project / "docs"
            content = project / "content"
            config = project / "config"
            vendor = project / "vendor"
            for directory in (docs, content, config, vendor):
                directory.mkdir()
            (project / "README.md").write_text(
                "Theme sample: font-family: Inter\n",
                encoding="utf-8",
            )
            (docs / "guide.mdx").write_text(
                "Guide typography uses fontFamily: 'Inter'.\n",
                encoding="utf-8",
            )
            (content / "home.json").write_text(
                '{"proof":"Lorem ipsum"}\n',
                encoding="utf-8",
            )
            (content / "about.yaml").write_text(
                'headline: "Lorem ipsum service"\n',
                encoding="utf-8",
            )
            (content / "secrets.yml").write_text(
                'token: "Lorem ipsum"\n',
                encoding="utf-8",
            )
            (config / "secrets.yml").write_text(
                'password: "Lorem ipsum"\n',
                encoding="utf-8",
            )
            (vendor / "copy.json").write_text(
                '{"proof":"Lorem ipsum"}\n',
                encoding="utf-8",
            )

            default = run_scan(project, "--json")
            self.assertEqual(default.returncode, 0, default.stderr)
            default_payload = payload(default)
            self.assertEqual(default_payload["scan_status"], "scope-limited")
            self.assertFalse(default_payload["documentation_mode"])
            self.assertFalse(default_payload["structured_content_mode"])
            self.assertIn("README.md", default_payload["excluded_default_files"])
            self.assertIn(
                "docs/guide.mdx",
                default_payload["excluded_default_files"],
            )

            content_site = run_scan(project, "--json", "--content-site")
            self.assertEqual(content_site.returncode, 0, content_site.stderr)
            content_payload = payload(content_site)
            self.assertTrue(content_payload["documentation_mode"])
            watched = {
                item["file"]
                for item in content_payload["findings"]
                if item["rule"] == "unexamined-default-font"
            }
            self.assertEqual(watched, {"README.md", "docs/guide.mdx"})

            structured = run_scan(
                project,
                "--json",
                "--content-site",
                "--structured-content",
            )
            self.assertEqual(structured.returncode, 0, structured.stderr)
            structured_payload = payload(structured)
            self.assertTrue(structured_payload["structured_content_mode"])
            self.assertTrue(
                {".json", ".yaml", ".yml"}.issubset(
                    set(structured_payload["source_coverage"]["suffixes"])
                )
            )
            proof_files = {
                item["file"]
                for item in structured_payload["findings"]
                if item["rule"] == "placeholder-proof"
            }
            self.assertEqual(
                proof_files,
                {"content/home.json", "content/about.yaml"},
            )
            self.assertEqual(
                structured_payload["excluded_sensitive_structured_files"],
                ["config/secrets.yml", "content/secrets.yml"],
            )
            self.assertNotIn("vendor/copy.json", proof_files)

            reviewed_sensitive = run_scan(
                project,
                "--json",
                "--structured-content",
                "--include",
                "config/secrets.yml",
            )
            self.assertEqual(
                reviewed_sensitive.returncode,
                0,
                reviewed_sensitive.stdout + reviewed_sensitive.stderr,
            )
            reviewed_payload = payload(reviewed_sensitive)
            self.assertNotIn(
                "config/secrets.yml",
                reviewed_payload["excluded_sensitive_structured_files"],
            )
            self.assertTrue(
                any(
                    item["rule"] == "placeholder-proof"
                    and item["file"] == "config/secrets.yml"
                    for item in reviewed_payload["findings"]
                )
            )

    def test_unsafe_include_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = run_scan(Path(temporary), "--include", "../**", "--json")
            self.assertEqual(result.returncode, 2)
            self.assertIn("project-relative", result.stderr)

    def test_advisory_fragment_does_not_trip_fail_on(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.tsx").write_text(
                '<h1>Better <span className="text-[#7c3aed]">'
                "coffee</span></h1>",
                encoding="utf-8",
            )
            result = run_scan(project, "--json", "--fail-on", "low")
            self.assertEqual(
                result.returncode, 0, result.stdout + result.stderr
            )
            result_payload = payload(result)
            fragments = [
                item
                for item in result_payload["findings"]
                if item["rule"] == "decorative-headline-span"
            ]
            self.assertEqual(len(fragments), 1)
            self.assertEqual(fragments[0]["classification"], "advisory")
            self.assertEqual(sum(result_payload["gate_counts"].values()), 0)

    def test_negative_examples_and_semantic_status_do_not_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.tsx").write_text(
                "<main>\n"
                "  <p>Do not use Lorem ipsum as proof.</p>\n"
                '  <h1>Incidents <span className="status text-rose-600">'
                "Open</span></h1>\n"
                "  <p>Do not add features, testimonials, FAQ, or Get Started.</p>\n"
                "</main>\n",
                encoding="utf-8",
            )
            result = run_scan(project, "--json", "--fail-on", "high")
            self.assertEqual(
                result.returncode, 0, result.stdout + result.stderr
            )
            rules = {item["rule"] for item in payload(result)["findings"]}
            self.assertNotIn("placeholder-proof", rules)
            self.assertNotIn("decorative-headline-span", rules)
            self.assertNotIn("generic-saas-section-cluster", rules)

    def test_visible_proof_is_gate_but_source_only_string_is_advisory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            visible = root / "visible"
            visible.mkdir()
            (visible / "page.tsx").write_text(
                "<p>Lorem ipsum</p>",
                encoding="utf-8",
            )
            visible_result = run_scan(
                visible, "--json", "--fail-on", "high"
            )
            self.assertEqual(
                visible_result.returncode,
                1,
                visible_result.stdout + visible_result.stderr,
            )
            visible_proof = [
                item
                for item in payload(visible_result)["findings"]
                if item["rule"] == "placeholder-proof"
            ]
            self.assertEqual(visible_proof[0]["classification"], "gate")

            source_only = root / "source-only"
            source_only.mkdir()
            (source_only / "copy.ts").write_text(
                'const exampleCopy = "Lorem ipsum";\n',
                encoding="utf-8",
            )
            source_result = run_scan(
                source_only, "--json", "--fail-on", "high"
            )
            self.assertEqual(
                source_result.returncode,
                0,
                source_result.stdout + source_result.stderr,
            )
            source_proof = [
                item
                for item in payload(source_result)["findings"]
                if item["rule"] == "placeholder-proof"
            ]
            self.assertEqual(len(source_proof), 1)
            self.assertEqual(source_proof[0]["classification"], "advisory")

    def test_positive_sibling_after_negated_sibling_gates(self) -> None:
        cases = {
            "same-line": (
                "<p>Do not use Lorem ipsum as proof.</p>"
                "<p>Lorem ipsum</p>"
            ),
            "multiline": """\
<div>
  <p>
    Do not use Lorem ipsum as proof.
  </p>
  <p>
    Lorem ipsum
  </p>
</div>
""",
        }
        for name, source in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                project = Path(temporary)
                (project / "page.tsx").write_text(source, encoding="utf-8")
                result = run_scan(project, "--json", "--fail-on", "high")
                self.assertEqual(
                    result.returncode,
                    1,
                    result.stdout + result.stderr,
                )
                proof = [
                    item
                    for item in payload(result)["findings"]
                    if item["rule"] == "placeholder-proof"
                ]
                self.assertEqual(len(proof), 1)
                self.assertEqual(proof[0]["classification"], "gate")

    def test_negation_is_sentence_local_within_one_text_node(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.html").write_text(
                "<p>Do not use Lorem ipsum as proof. "
                "Lorem ipsum</p>",
                encoding="utf-8",
            )
            result = run_scan(project, "--json", "--fail-on", "high")
            self.assertEqual(
                result.returncode,
                1,
                result.stdout + result.stderr,
            )
            proof = [
                item
                for item in payload(result)["findings"]
                if item["rule"] == "placeholder-proof"
            ]
            self.assertEqual(len(proof), 1)
            self.assertEqual(proof[0]["classification"], "gate")

    def test_multiline_same_sentence_negation_suppresses(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.tsx").write_text(
                """\
<p>
  Do not use
  Lorem ipsum
  as proof.
</p>
""",
                encoding="utf-8",
            )
            result = run_scan(project, "--json", "--fail-on", "high")
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )
            self.assertFalse(
                any(
                    item["rule"] == "placeholder-proof"
                    for item in payload(result)["findings"]
                )
            )

    def test_markup_inside_code_string_remains_advisory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.tsx").write_text(
                'const unusedMarkup = "<p>Lorem ipsum</p>";\n',
                encoding="utf-8",
            )
            result = run_scan(project, "--json", "--fail-on", "high")
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )
            proof = [
                item
                for item in payload(result)["findings"]
                if item["rule"] == "placeholder-proof"
            ]
            self.assertEqual(len(proof), 1)
            self.assertEqual(proof[0]["classification"], "advisory")

    def test_renderable_templates_gate_only_literal_visible_proof(self) -> None:
        visible_sources = {
            "liquid": "<p>Lorem ipsum</p>",
            "twig": "<p>Lorem ipsum</p>",
            "vue": "<template><p>Lorem ipsum</p></template>",
            "svelte": "<p>Lorem ipsum</p>",
            "astro": (
                "---\nconst label = 'reviewed';\n---\n"
                "<p>Lorem ipsum</p>"
            ),
            "mdx": "<p>Lorem ipsum</p>",
        }
        source_only = {
            "liquid": '{% assign demo = "<p>Lorem ipsum</p>" %}',
            "twig": '{% set demo = "<p>Lorem ipsum</p>" %}',
            "vue": (
                '<script>const demo = "<p>Lorem ipsum</p>";'
                "</script>"
            ),
            "svelte": (
                '<script>const demo = "<p>Lorem ipsum</p>";'
                "</script>"
            ),
            "astro": (
                '---\nconst demo = "<p>Lorem ipsum</p>";\n---'
            ),
            "mdx": (
                'export const demo = "<p>Lorem ipsum</p>";'
            ),
        }
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            for suffix, source in visible_sources.items():
                target = project / "visible" / f"page.{suffix}"
                target.parent.mkdir(exist_ok=True)
                target.write_text(source, encoding="utf-8")
                code_target = project / "source-only" / f"page.{suffix}"
                code_target.parent.mkdir(exist_ok=True)
                code_target.write_text(source_only[suffix], encoding="utf-8")
                negative_target = project / "negative" / f"page.{suffix}"
                negative_target.parent.mkdir(exist_ok=True)
                negative_target.write_text(
                    "<p>Do not say Lorem ipsum.</p>",
                    encoding="utf-8",
                )

            result = run_scan(
                project,
                "--content-site",
                "--json",
                "--fail-on",
                "high",
            )
            self.assertEqual(
                result.returncode,
                1,
                result.stdout + result.stderr,
            )
            proof = [
                item
                for item in payload(result)["findings"]
                if item["rule"] == "placeholder-proof"
            ]
            by_file = {item["file"]: item for item in proof}
            for suffix in visible_sources:
                with self.subTest(suffix=suffix):
                    self.assertEqual(
                        by_file[f"visible/page.{suffix}"]["classification"],
                        "gate",
                    )
                    self.assertEqual(
                        by_file[f"source-only/page.{suffix}"][
                            "classification"
                        ],
                        "advisory",
                    )
                    self.assertNotIn(f"negative/page.{suffix}", by_file)


class ScannerDecorativeSectionLabelTests(unittest.TestCase):
    def label_findings(
        self,
        result: subprocess.CompletedProcess[str],
    ) -> list[dict[str, object]]:
        return [
            item
            for item in payload(result)["findings"]
            if item["rule"] == "repeated-decorative-section-label"
        ]

    def test_four_decorative_section_labels_are_advisory_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.tsx").write_text(
                """\
<section><p className="eyebrow">Our approach</p></section>
<section><span class="hero-kicker">Materials</span></section>
<section><small className={'overline'}>Neighborhood</small></section>
<section><div className={`section-label`}>What follows</div></section>
""",
                encoding="utf-8",
            )
            result = run_scan(project, "--json", "--fail-on", "low")
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )
            findings = self.label_findings(result)
            self.assertEqual(len(findings), 1)
            self.assertTrue(
                all(item["classification"] == "advisory" for item in findings)
            )
            self.assertEqual(findings[0]["matched_signal"]["count"], 4)
            self.assertEqual(len(findings[0]["matched_signal"]["labels"]), 4)
            self.assertEqual(sum(payload(result)["gate_counts"].values()), 0)

    def test_label_threshold_is_scoped_per_renderable_route(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            for index in range(4):
                (project / f"route-{index}.html").write_text(
                    '<main><p class="eyebrow">One useful label</p></main>',
                    encoding="utf-8",
                )
            result = run_scan(project, "--json", "--fail-on", "low")
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )
            self.assertEqual(self.label_findings(result), [])

    def test_below_threshold_does_not_trigger(self) -> None:
        for count in (1, 3):
            with self.subTest(count=count), tempfile.TemporaryDirectory() as temporary:
                project = Path(temporary)
                (project / "page.tsx").write_text(
                    "\n".join(
                        f'<p className="eyebrow">Detail {index}</p>'
                        for index in range(count)
                    ),
                    encoding="utf-8",
                )
                result = run_scan(project, "--json", "--fail-on", "low")
                self.assertEqual(
                    result.returncode,
                    0,
                    result.stdout + result.stderr,
                )
                self.assertEqual(self.label_findings(result), [])
                self.assertEqual(sum(payload(result)["gate_counts"].values()), 0)

    def test_obvious_semantic_labels_and_statuses_do_not_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.tsx").write_text(
                """\
<p className="status eyebrow" role="status">Open</p>
<span className="priority-kicker">High</span>
<div className="taxonomy overline">Topics</div>
<p className="step section-label">Step 2 of 4</p>
""",
                encoding="utf-8",
            )
            result = run_scan(project, "--json", "--fail-on", "low")
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )
            self.assertEqual(self.label_findings(result), [])
            self.assertEqual(sum(payload(result)["gate_counts"].values()), 0)


class ScannerNorthlinePatternTests(unittest.TestCase):
    def test_northline_shaped_routes_require_adversarial_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            texture = " ".join(
                [
                    (
                        "The walkthrough explains the work in concrete terms "
                        "so the reader can decide what happens next."
                    )
                ]
                * 45
            )
            (project / "index.html").write_text(
                f"""\
<main>
<!-- ACT 1 - wide architectural opening -->
<section><p class="eyebrow">Level 2 installation</p><h1>Plan the run.</h1>
<p>Sample site. Not a real company. Every figure is a placeholder.</p>
<p>{texture}</p>
<figure><img src="garage.webp" alt="Garage at dusk"><figcaption>Generated image.</figcaption></figure></section>
<!-- ACT 2 - technical panel -->
<section><p class="eyebrow">Question one</p><h2>What can the panel take?</h2>
<p>Choose 100A, 150A, or 200A. A 48A charger uses a 60A circuit.</p>
<input aria-label="Service"><output>60A</output><figure><svg></svg></figure></section>
<!-- ACT 3 - THE SIGNATURE MOMENT -->
<section><p class="eyebrow">Question two</p><h2>How far is the run?</h2>
<p>Allow 15 minutes for video, 40 minutes off, and 30 miles per hour parked.</p>
<input aria-label="Distance"><dl><dt>Run</dt><dd>28 ft</dd></dl></section>
<!-- ACT 4 - tabular document -->
<section><p class="eyebrow">The arithmetic</p><h2>Here is the range.</h2>
<p>A sample job is $900 to $2,600, with a 3 year warranty and a 30 mile radius.</p>
<dl><dt>Estimate</dt><dd>$1,010 to $2,180</dd></dl></section>
<section><p class="eyebrow">The cheap move</p><h2>Prepare first.</h2>
<p>The cheapest charger is the one you do not install yet.</p><ol><li>Plan</li></ol>
<img src="panel.webp" alt="Open panel"><img src="conduit.webp" alt="Conduit"></section>
<section><p class="eyebrow">Last step</p><h2>Book the walkthrough.</h2>
<p>Use hello@example.com or (000) 000-0000 for your service area and licence number.</p>
<form><input name="email"><button>Request walkthrough</button></form></section>
</main>
""",
                encoding="utf-8",
            )
            (project / "buildings.html").write_text(
                f"""\
<main>
<section><p class="eyebrow">Building charging</p><h1>Share the feeder.</h1><p>{texture}</p></section>
<section><p class="eyebrow">The arithmetic</p><h2>Size the load.</h2>
<p>Use 100A, 200A, or 400A for 4, 8, or 16 cars over 12 hours.</p>
<input aria-label="Cars"><output>20A</output><figure><svg></svg></figure></section>
<section><p class="eyebrow">The awkward question</p><h2>Who pays?</h2>
<p>Compare $14 to $30 per month with $280 to $520 per space.</p>
<dl><dt>Option</dt><dd>Shared</dd></dl></section>
<section><p class="eyebrow">The cheap move</p><h2>Prepare in phases.</h2>
<p>Plan for 3 years, not 3 days.</p><ol><li>Survey</li><li>Prepare</li></ol></section>
<section><p class="eyebrow">Next step</p><h2>Book the survey.</h2>
<p>Sample website concept with placeholders for your service area, hello@example.com,
(000) 000-0000, and electrical licence number.</p>
<form><input name="email"><button>Request survey</button></form></section>
</main>
""",
                encoding="utf-8",
            )
            result = run_scan(project, "--json", "--fail-on", "high")
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )
            result_payload = payload(result)
            rules = {item["rule"] for item in result_payload["findings"]}
            self.assertIn("repeated-decorative-section-label", rules)
            self.assertIn("rhetorical-label-cluster", rules)
            self.assertIn("presentation-script-comment-cluster", rules)
            checks = {
                item["check"] for item in result_payload["manual_review"]
            }
            self.assertTrue(
                {
                    "quantitative-claim-density",
                    "copy-uniformity-cluster",
                    "parallel-route-skeleton",
                    "generated-media-authenticity",
                    "concept-material-balance",
                }.issubset(checks)
            )
            self.assertTrue(result_payload["source_gate_passed"])
            self.assertTrue(result_payload["review_required"])
            self.assertEqual(result_payload["design_review_status"], "pending")
            self.assertGreater(result_payload["manual_review_count"], 0)
            self.assertGreater(result_payload["unresolved_advisory_count"], 0)

    def test_claim_language_is_advisory_not_a_confirmed_truth_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.html").write_text(
                "<main><p>Trusted by thousands.</p>"
                "<p>Industry-leading service.</p></main>",
                encoding="utf-8",
            )
            result = run_scan(project, "--json", "--fail-on", "high")
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )
            result_payload = payload(result)
            claims = [
                item
                for item in result_payload["findings"]
                if item["rule"] == "claim-needs-provenance"
            ]
            self.assertEqual(len(claims), 2)
            self.assertTrue(
                all(item["classification"] == "advisory" for item in claims)
            )
            self.assertFalse(
                any(
                    item["rule"] == "placeholder-proof"
                    for item in result_payload["findings"]
                )
            )
            self.assertTrue(result_payload["source_gate_passed"])
            self.assertTrue(result_payload["review_required"])

    def test_counterexamples_do_not_create_northline_cluster_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.html").write_text(
                """\
<header><img class="brand-logo" src="logo.png" alt="Brand"></header>
<main>
<!-- ACT 1 -->
<!-- ACT 2 -->
<!-- ACT 3 -->
<section><p class="step eyebrow" role="status">Step 1 of 4</p><h1>Profile</h1></section>
<section><p class="step eyebrow">Step 2 of 4</p><h2>Address</h2></section>
</main>
""",
                encoding="utf-8",
            )
            (project / "other.html").write_text(
                """\
<header><p>Shared header</p></header><main>
<section><h1>Reference</h1></section>
<section><table><tr><td>One</td></tr></table></section>
<section><figure>Diagram</figure></section>
<section><p>Closing note</p></section>
</main><footer>Shared footer</footer>
""",
                encoding="utf-8",
            )
            (project / "values.css").write_text(
                ".box { width: 48px; min-height: 60px; }",
                encoding="utf-8",
            )
            (project / "values.js").write_text(
                'const note = "/* ACT 4 */"; const amps = 60;',
                encoding="utf-8",
            )
            result = run_scan(project, "--json")
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )
            result_payload = payload(result)
            self.assertNotIn(
                "rhetorical-label-cluster",
                {item["rule"] for item in result_payload["findings"]},
            )
            self.assertNotIn(
                "presentation-script-comment-cluster",
                {item["rule"] for item in result_payload["findings"]},
            )
            checks = {
                item["check"] for item in result_payload["manual_review"]
            }
            self.assertNotIn("quantitative-claim-density", checks)
            self.assertNotIn("copy-uniformity-cluster", checks)
            self.assertNotIn("parallel-route-skeleton", checks)
            self.assertNotIn("media-authenticity-and-provenance", checks)
            self.assertFalse(result_payload["review_required"])
            self.assertEqual(
                result_payload["design_review_status"],
                "not-triggered-by-source",
            )


class ScannerShadcnTokenTests(unittest.TestCase):
    def shadcn_findings(
        self,
        result: subprocess.CompletedProcess[str],
    ) -> list[dict[str, object]]:
        return [
            item
            for item in payload(result)["findings"]
            if item["rule"] == "untouched-shadcn-token"
        ]

    def test_current_exact_and_default_like_oklch_clusters_are_advisory(
        self,
    ) -> None:
        palettes = {
            "exact-light": (CURRENT_SHADCN_LIGHT, "light"),
            "exact-dark": (CURRENT_SHADCN_DARK, "dark"),
            "default-like": (
                (
                    CURRENT_SHADCN_LIGHT
                    .replace(
                        "--destructive: oklch(0.577 0.245 27.325);",
                        "--destructive: oklch(0.62 0.2 24);",
                    )
                    .replace(
                        "--ring: oklch(0.708 0 0);",
                        "--ring: oklch(0.64 0.04 250);",
                    )
                ),
                "light",
            ),
        }
        for name, (css, profile) in palettes.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                project = Path(temporary)
                (project / "theme.css").write_text(css, encoding="utf-8")
                result = run_scan(project, "--json", "--fail-on", "low")
                self.assertEqual(
                    result.returncode,
                    0,
                    result.stdout + result.stderr,
                )
                findings = self.shadcn_findings(result)
                self.assertEqual(len(findings), 1)
                self.assertEqual(findings[0]["classification"], "advisory")
                self.assertEqual(
                    findings[0]["matched_signal"]["profile"],
                    profile,
                )
                self.assertGreaterEqual(
                    findings[0]["matched_signal"]["matched_count"],
                    15,
                )
                self.assertEqual(sum(payload(result)["gate_counts"].values()), 0)

    def test_project_specific_oklch_palette_does_not_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "theme.css").write_text(
                """\
:root {
  --background: oklch(0.97 0.02 85);
  --foreground: oklch(0.22 0.04 245);
  --card: oklch(0.94 0.03 80);
  --card-foreground: oklch(0.24 0.05 245);
  --popover: oklch(0.99 0.01 88);
  --popover-foreground: oklch(0.2 0.05 245);
  --primary: oklch(0.54 0.18 252);
  --primary-foreground: oklch(0.98 0.01 90);
  --secondary: oklch(0.82 0.08 165);
  --secondary-foreground: oklch(0.26 0.06 180);
  --muted: oklch(0.9 0.03 90);
  --muted-foreground: oklch(0.48 0.05 245);
  --accent: oklch(0.72 0.15 45);
  --accent-foreground: oklch(0.2 0.05 35);
  --destructive: oklch(0.58 0.23 25);
  --border: oklch(0.78 0.05 90);
  --input: oklch(0.84 0.04 90);
  --ring: oklch(0.54 0.18 252);
}
""",
                encoding="utf-8",
            )
            result = run_scan(project, "--json")
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )
            self.assertEqual(self.shadcn_findings(result), [])

    def test_library_marker_alone_does_not_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "theme.css").write_text(
                '@import "tailwindcss";\n'
                '@import "shadcn/tailwind.css";\n'
                ".button { color: oklch(0.55 0.2 250); }\n",
                encoding="utf-8",
            )
            result = run_scan(project, "--json")
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )
            self.assertEqual(self.shadcn_findings(result), [])

    def test_isolated_legitimate_oklch_variables_do_not_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "theme.css").write_text(
                """\
:root {
  --background: oklch(1 0 0);
  --foreground: oklch(0.145 0 0);
  --primary: oklch(0.205 0 0);
  --primary-foreground: oklch(0.985 0 0);
  --ring: oklch(0.708 0 0);
}
""",
                encoding="utf-8",
            )
            result = run_scan(project, "--json")
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )
            self.assertEqual(self.shadcn_findings(result), [])

    def test_legacy_hsl_cluster_still_triggers_as_advisory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "legacy.css").write_text(
                """\
:root {
  --background: 0 0% 100%;
  --foreground: 222.2 84% 4.9%;
  --primary: 222.2 47.4% 11.2%;
  --secondary: 210 40% 96.1%;
  --muted: 210 40% 96.1%;
  --accent: 210 40% 96.1%;
}
""",
                encoding="utf-8",
            )
            result = run_scan(project, "--json", "--fail-on", "low")
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )
            findings = self.shadcn_findings(result)
            self.assertEqual(len(findings), 6)
            self.assertTrue(
                all(item["classification"] == "advisory" for item in findings)
            )
            self.assertEqual(sum(payload(result)["gate_counts"].values()), 0)


class ScannerProminentFragmentTests(unittest.TestCase):
    def test_resolves_css_modules_style_objects_and_tailwind_arbitrary_colors(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            source = project / "src"
            source.mkdir()
            (source / "Hero.tsx").write_text(
                '<h1>Better <span className="accentWord">coffee</span></h1>',
                encoding="utf-8",
            )
            (source / "hero.css").write_text(
                ".accentWord { color: #7c3aed; }\n",
                encoding="utf-8",
            )
            (source / "ModuleHero.tsx").write_text(
                "import styles from './Hero.module.css';\n"
                "<h1>Better <span className={styles.moduleHighlight}>"
                "coffee</span></h1>\n",
                encoding="utf-8",
            )
            (source / "Hero.module.css").write_text(
                ".moduleHighlight { color: #0f766e; }\n",
                encoding="utf-8",
            )
            (source / "ObjectHero.tsx").write_text(
                'const accentStyle = { color: "#2563eb" };\n'
                "<h1>Better <span style={accentStyle}>coffee</span></h1>\n",
                encoding="utf-8",
            )
            (source / "TailwindHero.tsx").write_text(
                '<h1>Better <span className="text-[oklch(55%_0.2_290)]">'
                "coffee</span></h1>\n",
                encoding="utf-8",
            )

            result = run_scan(project, "--json", "--fail-on", "low")
            self.assertEqual(
                result.returncode, 0, result.stdout + result.stderr
            )
            fragments = [
                item
                for item in payload(result)["findings"]
                if item["rule"] == "decorative-headline-span"
            ]
            self.assertEqual(
                {item["file"] for item in fragments},
                {
                    "src/Hero.tsx",
                    "src/ModuleHero.tsx",
                    "src/ObjectHero.tsx",
                    "src/TailwindHero.tsx",
                },
            )
            signals = {
                item["file"]: str(item["matched_signal"])
                for item in fragments
            }
            self.assertIn("foreground color declaration", signals["src/Hero.tsx"])
            self.assertIn("CSS Module", signals["src/ModuleHero.tsx"])
            self.assertIn("React style", signals["src/ObjectHero.tsx"])
            self.assertIn("Tailwind", signals["src/TailwindHero.tsx"])
            self.assertTrue(
                all(item["classification"] == "advisory" for item in fragments)
            )

    def test_dynamic_style_is_manual_review_not_a_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.tsx").write_text(
                "<h1>Better <span className={emphasisClass}>"
                "coffee</span></h1>",
                encoding="utf-8",
            )
            result = run_scan(project, "--json", "--fail-on", "low")
            self.assertEqual(
                result.returncode, 0, result.stdout + result.stderr
            )
            result_payload = payload(result)
            self.assertFalse(
                any(
                    item["rule"] == "decorative-headline-span"
                    for item in result_payload["findings"]
                )
            )
            self.assertEqual(len(result_payload["manual_review"]), 1)
            self.assertEqual(
                result_payload["manual_review"][0]["check"],
                "prominent-fragment-dynamic-style",
            )
            self.assertTrue(result_payload["limitations"])

    def test_semantic_css_status_selector_is_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "style.css").write_text(
                ".hero .status span { color: red; }\n",
                encoding="utf-8",
            )
            result = run_scan(project, "--json")
            self.assertEqual(
                result.returncode, 0, result.stdout + result.stderr
            )
            self.assertFalse(
                any(
                    item["rule"] == "decorative-display-fragment"
                    for item in payload(result)["findings"]
                )
            )


class ScannerColorReasoningTests(unittest.TestCase):
    def test_cream_serif_sage_uses_oklch_and_rejects_unrelated_colors(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            good = project / "good"
            bad = project / "bad"
            named_only = project / "named-only"
            utility = project / "utility"
            string_only = project / "string-only"
            good.mkdir()
            bad.mkdir()
            named_only.mkdir()
            utility.mkdir()
            string_only.mkdir()
            (good / "style.css").write_text(
                ":root { --surface: #f3eddf; --accent: #536b55; "
                "--font-display: 'Editorial House', Georgia, serif; }\n",
                encoding="utf-8",
            )
            (bad / "style.css").write_text(
                ":root { --surface: #ffffff; --accent: #ff00ff; "
                "--font-display: 'Editorial House', Georgia, serif; }\n",
                encoding="utf-8",
            )
            (named_only / "style.css").write_text(
                ":root { --surface: #f3eddf; --accent: #536b55; "
                "--typeface: 'Fraunces'; }\n",
                encoding="utf-8",
            )
            (utility / "style.css").write_text(
                ":root { --surface: #f3eddf; --accent: #536b55; }\n",
                encoding="utf-8",
            )
            (utility / "page.html").write_text(
                "<h1 class=font-serif>Editorial role</h1>",
                encoding="utf-8",
            )
            (string_only / "style.css").write_text(
                ":root { --surface: #f3eddf; --accent: #536b55; }\n",
                encoding="utf-8",
            )
            (string_only / "page.astro").write_text(
                'const demo = "<h1 class=font-serif>Editorial role</h1>";',
                encoding="utf-8",
            )
            result = run_scan(project, "--json")
            self.assertEqual(
                result.returncode, 0, result.stdout + result.stderr
            )
            clusters = [
                item
                for item in payload(result)["findings"]
                if item["rule"] == "cream-serif-sage-cluster"
            ]
            self.assertEqual(
                {item["file"] for item in clusters},
                {"good", "utility"},
            )
            good_cluster = next(
                item for item in clusters if item["file"] == "good"
            )
            by_signal = {
                signal["signal"]: signal
                for signal in good_cluster["matched_signals"]
            }
            self.assertIn("cream-color", by_signal)
            self.assertIn("muted-green-color", by_signal)
            self.assertIn("display-serif-role", by_signal)
            for name in ("cream-color", "muted-green-color"):
                self.assertEqual(
                    set(by_signal[name]["oklch"]),
                    {"l", "c", "h"},
                )
            utility_cluster = next(
                item for item in clusters if item["file"] == "utility"
            )
            utility_signal = next(
                signal
                for signal in utility_cluster["matched_signals"]
                if signal["signal"] == "display-serif-role"
            )
            self.assertIn("font-serif", utility_signal["value"])
            self.assertNotIn(
                "named-only",
                {item["file"] for item in clusters},
            )
            self.assertNotIn(
                "string-only",
                {item["file"] for item in clusters},
            )


class ScannerAllowlistAndCompletenessTests(unittest.TestCase):
    def test_fingerprints_bind_signal_payloads_deterministically(self) -> None:
        fingerprint = runpy.run_path(str(SCAN))["finding_fingerprint"]
        base = {
            "rule": "example-rule",
            "severity": "medium",
            "classification": "advisory",
            "file": "src/page.tsx",
            "line": 4,
            "excerpt": "stable excerpt",
        }
        first = fingerprint({
            **base,
            "matched_signal": {"match": "alpha", "basis": "literal"},
        })
        reordered = fingerprint({
            **base,
            "matched_signal": {"basis": "literal", "match": "alpha"},
        })
        changed_single = fingerprint({
            **base,
            "matched_signal": {"match": "beta", "basis": "literal"},
        })
        first_compound = fingerprint({
            **base,
            "matched_signals": [
                {"signal": "cream-color", "value": "#f3eddf"},
                {"signal": "muted-green-color", "value": "#536b55"},
            ],
        })
        changed_compound = fingerprint({
            **base,
            "matched_signals": [
                {"signal": "cream-color", "value": "#f3eddf"},
                {"signal": "muted-green-color", "value": "#4f6b57"},
            ],
        })
        self.assertEqual(first, reordered)
        self.assertNotEqual(first, changed_single)
        self.assertNotEqual(first_compound, changed_compound)

    def test_changed_compound_signal_is_not_suppressed_by_old_fingerprint(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            theme = project / "theme"
            theme.mkdir()
            stylesheet = theme / "style.css"
            stylesheet.write_text(
                ":root { --surface: #f3eddf; --accent: #536b55; "
                "--font-display: Georgia, serif; }\n",
                encoding="utf-8",
            )
            initial = run_scan(project, "--json")
            self.assertEqual(initial.returncode, 0, initial.stderr)
            initial_finding = next(
                item
                for item in payload(initial)["findings"]
                if item["rule"] == "cream-serif-sage-cluster"
            )
            repeated = run_scan(project, "--json")
            repeated_finding = next(
                item
                for item in payload(repeated)["findings"]
                if item["rule"] == "cream-serif-sage-cluster"
            )
            self.assertEqual(
                initial_finding["fingerprint"],
                repeated_finding["fingerprint"],
            )

            allowlist = project / "allow.json"
            allowlist.write_text(
                json.dumps({
                    "schema_version": 1,
                    "allow": [{
                        "rule": initial_finding["rule"],
                        "path": initial_finding["file"],
                        "fingerprint": initial_finding["fingerprint"],
                        "reason": "Reviewed initial palette and type signal.",
                        "owner": "Design owner",
                        "expires": ACTIVE_EXPIRY,
                    }],
                }),
                encoding="utf-8",
            )
            stylesheet.write_text(
                ":root { --surface: #f3eddf; --accent: #536b55; "
                "--font-heading: Georgia, serif; }\n",
                encoding="utf-8",
            )
            changed = run_scan(
                project,
                "--allowlist",
                str(allowlist),
                "--json",
            )
            self.assertEqual(
                changed.returncode,
                0,
                changed.stdout + changed.stderr,
            )
            changed_payload = payload(changed)
            changed_finding = next(
                item
                for item in changed_payload["findings"]
                if item["rule"] == "cream-serif-sage-cluster"
            )
            self.assertNotEqual(
                initial_finding["matched_signals"],
                changed_finding["matched_signals"],
            )
            self.assertNotEqual(
                initial_finding["fingerprint"],
                changed_finding["fingerprint"],
            )
            self.assertEqual(changed_payload["suppressed_count"], 0)

    def test_expiry_values_must_be_exact_schema_date_strings(self) -> None:
        allow_entry = {
            "rule": "generic-gradient-text",
            "path": "page.html",
            "fingerprint": "0" * 64,
            "reason": "Reviewed visual treatment.",
            "owner": "Design owner",
            "expires": ACTIVE_EXPIRY,
        }
        acknowledgement = {
            "path": "src/**",
            "reason": "Reviewed generated sources separately.",
            "owner": "Repository owner",
            "expires": ACTIVE_EXPIRY,
        }
        cases = {
            "allow-integer": {
                "allow": [{**allow_entry, "expires": 20991231}],
                "acknowledge_skipped": [],
            },
            "allow-compact-string": {
                "allow": [{**allow_entry, "expires": "20991231"}],
                "acknowledge_skipped": [],
            },
            "allow-invalid-calendar-date": {
                "allow": [{**allow_entry, "expires": "2099-02-30"}],
                "acknowledge_skipped": [],
            },
            "allow-overlong": {
                "allow": [{**allow_entry, "expires": OVERLONG_EXPIRY}],
                "acknowledge_skipped": [],
            },
            "ack-integer": {
                "allow": [],
                "acknowledge_skipped": [
                    {**acknowledgement, "expires": 20991231}
                ],
            },
            "ack-compact-string": {
                "allow": [],
                "acknowledge_skipped": [
                    {**acknowledgement, "expires": "20991231"}
                ],
            },
            "ack-overlong": {
                "allow": [],
                "acknowledge_skipped": [
                    {**acknowledgement, "expires": OVERLONG_EXPIRY}
                ],
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.html").write_text("<p>Reviewed</p>")
            allowlist = project / "allow.json"
            for label, document in cases.items():
                with self.subTest(case=label):
                    allowlist.write_text(
                        json.dumps({"schema_version": 1, **document}),
                        encoding="utf-8",
                    )
                    result = run_scan(
                        project,
                        "--allowlist",
                        str(allowlist),
                        "--json",
                    )
                    self.assertEqual(result.returncode, 2)
                    self.assertRegex(
                        result.stderr,
                        (
                            r"(must be a YYYY-MM-DD string|invalid allowlist "
                            r"expiry|no more than 90 days)"
                        ),
                    )

    def test_help_and_allowlist_example_declare_runtime_and_schema(self) -> None:
        help_result = subprocess.run(
            [sys.executable, str(SCAN), "--help"],
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=120,
        )
        self.assertEqual(help_result.returncode, 0)
        self.assertIn("Python 3.10+", help_result.stdout)
        self.assertRegex(help_result.stdout, r"dynamically\s+rendered")

        example = subprocess.run(
            [sys.executable, str(SCAN), "--print-allowlist-example"],
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=120,
        )
        self.assertEqual(example.returncode, 0, example.stderr)
        example_payload = json.loads(example.stdout)
        self.assertFalse(example_payload["usable"])
        self.assertTrue(
            any(
                "--emit-allowlist-entry" in step
                for step in example_payload["workflow"]
            )
        )
        template = example_payload["template"]
        self.assertEqual(template["schema_version"], 1)
        self.assertEqual(
            set(template["allow"][0]),
            {
                "rule",
                "path",
                "fingerprint",
                "reason",
                "owner",
                "expires",
            },
        )
        self.assertEqual(
            template["allow"][0]["fingerprint"],
            "REPLACE_WITH_FINGERPRINT_FROM_SCANNER_OUTPUT",
        )
        self.assertEqual(
            set(template["acknowledge_skipped"][0]),
            {"path", "reason", "owner", "expires"},
        )
        expected_expiry = (
            date.today() + timedelta(days=30)
        ).isoformat()
        self.assertEqual(template["allow"][0]["expires"], expected_expiry)
        self.assertEqual(
            template["acknowledge_skipped"][0]["expires"],
            expected_expiry,
        )
        schema = json.loads(
            (
                PLUGIN
                / "maintainer"
                / "schemas"
                / "scan-allowlist.schema.json"
            ).read_text(encoding="utf-8")
        )
        packaged_template = json.loads(
            (
                PLUGIN
                / "skills"
                / "design-dna"
                / "templates"
                / "scan-allowlist.json"
            ).read_text(encoding="utf-8")
        )
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).validate(packaged_template)

    def test_allowlist_schema_matches_runtime_scalar_and_ack_path_rules(
        self,
    ) -> None:
        schema = json.loads(
            (
                PLUGIN
                / "maintainer"
                / "schemas"
                / "scan-allowlist.schema.json"
            ).read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        )
        allow_entry = {
            "rule": "generic-gradient-text",
            "path": "src/page.html",
            "fingerprint": "0" * 64,
            "reason": " a   b ",
            "owner": " Design owner ",
            "expires": ACTIVE_EXPIRY,
        }
        acknowledgement = {
            "path": "generated/**",
            "reason": " a   b ",
            "owner": " Repository owner ",
            "expires": ACTIVE_EXPIRY,
        }
        valid_document = {
            "schema_version": 1,
            "allow": [allow_entry],
            "acknowledge_skipped": [acknowledgement],
        }
        validator.validate(valid_document)

        invalid_documents = {
            "allow-whitespace-path": {
                **valid_document,
                "allow": [{**allow_entry, "path": " \t "}],
            },
            "ack-whitespace-path": {
                **valid_document,
                "acknowledge_skipped": [{
                    **acknowledgement,
                    "path": " \t ",
                }],
            },
            "allow-short-trimmed-reason": {
                **valid_document,
                "allow": [{**allow_entry, "reason": "  four  "}],
            },
            "ack-short-trimmed-reason": {
                **valid_document,
                "acknowledge_skipped": [{
                    **acknowledgement,
                    "reason": "  four  ",
                }],
            },
            "allow-whitespace-owner": {
                **valid_document,
                "allow": [{**allow_entry, "owner": "   "}],
            },
            "ack-whitespace-owner": {
                **valid_document,
                "acknowledge_skipped": [{
                    **acknowledgement,
                    "owner": "   ",
                }],
            },
            "ack-backslash-path": {
                **valid_document,
                "acknowledge_skipped": [{
                    **acknowledgement,
                    "path": r"generated\**",
                }],
            },
            "allow-rooted-path": {
                **valid_document,
                "allow": [{**allow_entry, "path": "/outside/**"}],
            },
            "allow-drive-relative-path": {
                **valid_document,
                "allow": [{**allow_entry, "path": "C:outside/**"}],
            },
            "ack-rooted-path": {
                **valid_document,
                "acknowledge_skipped": [{
                    **acknowledgement,
                    "path": "/outside/**",
                }],
            },
            "ack-drive-relative-path": {
                **valid_document,
                "acknowledge_skipped": [{
                    **acknowledgement,
                    "path": "C:outside/**",
                }],
            },
        }
        for label, document in invalid_documents.items():
            with self.subTest(case=label):
                self.assertTrue(
                    list(validator.iter_errors(document)),
                    f"schema unexpectedly accepted {label}",
                )

    def test_allowlist_paths_are_portably_project_relative(self) -> None:
        allow_entry = {
            "rule": "generic-gradient-text",
            "path": "page.html",
            "fingerprint": "0" * 64,
            "reason": "Reviewed project-specific treatment.",
            "owner": "Design owner",
            "expires": ACTIVE_EXPIRY,
        }
        acknowledgement = {
            "path": "generated/**",
            "reason": "Reviewed generated source separately.",
            "owner": "Repository owner",
            "expires": ACTIVE_EXPIRY,
        }
        cases = (
            ("allow", "/outside/**"),
            ("allow", r"\outside\**"),
            ("allow", "C:outside/**"),
            ("acknowledge_skipped", "/outside/**"),
            ("acknowledge_skipped", r"\outside\**"),
            ("acknowledge_skipped", "C:outside/**"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.html").write_text(
                "<p>Reviewed</p>",
                encoding="utf-8",
            )
            allowlist = project / "allow.json"
            for collection, unsafe_path in cases:
                with self.subTest(
                    collection=collection,
                    path=unsafe_path,
                ):
                    document = {
                        "schema_version": 1,
                        "allow": [],
                        "acknowledge_skipped": [],
                    }
                    if collection == "allow":
                        document["allow"] = [{
                            **allow_entry,
                            "path": unsafe_path,
                        }]
                    else:
                        document["acknowledge_skipped"] = [{
                            **acknowledgement,
                            "path": unsafe_path,
                        }]
                    allowlist.write_text(
                        json.dumps(document),
                        encoding="utf-8",
                    )
                    rejected = run_scan(
                        project,
                        "--allowlist",
                        str(allowlist),
                        "--json",
                    )
                    self.assertEqual(
                        rejected.returncode,
                        2,
                        rejected.stdout + rejected.stderr,
                    )
                    self.assertIn("project-relative", rejected.stderr)

    def test_emits_schema_valid_entry_for_an_actual_finding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.tsx").write_text(
                '<h1>Better <span className="text-violet-600">'
                "coffee</span></h1>",
                encoding="utf-8",
            )
            first = run_scan(project, "--json")
            self.assertEqual(first.returncode, 0, first.stderr)
            finding = next(
                item
                for item in payload(first)["findings"]
                if item["rule"] == "decorative-headline-span"
            )
            emitted = run_scan(
                project,
                "--emit-allowlist-entry",
                finding["fingerprint"],
                "--allowlist-entry-owner",
                "Design system owner",
                "--allowlist-entry-reason",
                "Reviewed semantic campaign emphasis.",
                "--allowlist-entry-days",
                "14",
            )
            self.assertEqual(emitted.returncode, 0, emitted.stderr)
            emitted_payload = json.loads(emitted.stdout)
            schema = json.loads(
                (
                    PLUGIN
                    / "maintainer"
                    / "schemas"
                    / "scan-allowlist.schema.json"
                ).read_text(encoding="utf-8")
            )
            Draft202012Validator(
                schema,
                format_checker=FormatChecker(),
            ).validate(emitted_payload)
            entry = emitted_payload["allow"][0]
            self.assertEqual(entry["fingerprint"], finding["fingerprint"])
            self.assertEqual(entry["path"], finding["file"])
            self.assertEqual(entry["line"], finding["line"])
            self.assertEqual(
                entry["expires"],
                (date.today() + timedelta(days=14)).isoformat(),
            )

            allowlist = project / "allow.json"
            allowlist.write_text(
                json.dumps(emitted_payload),
                encoding="utf-8",
            )
            suppressed = run_scan(
                project,
                "--allowlist",
                str(allowlist),
                "--json",
            )
            self.assertEqual(suppressed.returncode, 0, suppressed.stderr)
            self.assertEqual(payload(suppressed)["suppressed_count"], 1)

    def test_suppression_is_fully_audited_and_global_rule_is_rejected(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.tsx").write_text(
                '<h1>Better <span className="text-violet-600">'
                "coffee</span></h1>",
                encoding="utf-8",
            )
            initial = run_scan(project, "--json")
            self.assertEqual(initial.returncode, 0, initial.stderr)
            initial_finding = next(
                item
                for item in payload(initial)["findings"]
                if item["rule"] == "decorative-headline-span"
            )
            allowlist = project / "allow.json"
            entry = {
                "rule": "decorative-headline-span",
                "path": "page.tsx",
                "fingerprint": initial_finding["fingerprint"],
                "reason": "Approved campaign emphasis with documented meaning.",
                "owner": "Design owner",
                "expires": ACTIVE_EXPIRY,
            }
            allowlist.write_text(
                json.dumps({
                    "schema_version": 1,
                    "allow": [entry],
                    "acknowledge_skipped": [],
                }),
                encoding="utf-8",
            )
            result = run_scan(
                project,
                "--allowlist",
                str(allowlist),
                "--json",
            )
            self.assertEqual(
                result.returncode, 0, result.stdout + result.stderr
            )
            result_payload = payload(result)
            self.assertEqual(result_payload["active_allowlist_entries"], [entry])
            self.assertEqual(result_payload["suppressed_count"], 1)
            self.assertEqual(
                result_payload["allowlist_suppression_counts"],
                [{"entry": entry, "suppressed_count": 1}],
            )
            suppression = result_payload["suppressed_findings"][0]
            self.assertEqual(suppression["rule"], entry["rule"])
            self.assertEqual(suppression["file"], entry["path"])
            self.assertEqual(suppression["suppression"]["owner"], entry["owner"])
            self.assertEqual(
                suppression["suppression"]["reason"], entry["reason"]
            )
            self.assertEqual(
                suppression["suppression"]["expires"], entry["expires"]
            )
            self.assertFalse(
                any(
                    item["rule"] == entry["rule"]
                    for item in result_payload["findings"]
                )
            )

            text_result = run_scan(
                project,
                "--allowlist",
                str(allowlist),
            )
            self.assertEqual(text_result.returncode, 0, text_result.stderr)
            self.assertIn("ALLOWLIST-ACTIVE", text_result.stdout)
            self.assertIn("matches=1", text_result.stdout)
            self.assertIn("ALLOWLIST-SUPPRESSED", text_result.stdout)
            self.assertIn("owner=Design owner", text_result.stdout)
            self.assertIn(entry["fingerprint"], text_result.stdout)

            wildcard = {
                **entry,
                "rule": "*",
                "path": "**",
            }
            allowlist.write_text(
                json.dumps({
                    "schema_version": 1,
                    "allow": [wildcard],
                }),
                encoding="utf-8",
            )
            rejected = run_scan(
                project,
                "--allowlist",
                str(allowlist),
                "--json",
            )
            self.assertEqual(rejected.returncode, 2)
            self.assertIn("global allowlist rule", rejected.stderr)

    def test_allowlist_cannot_drop_an_aggregate_rule_below_its_threshold(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "buttons.html").write_text(
                "\n".join(
                    '<button class="rounded-full">Action</button>'
                    for _ in range(4)
                ),
                encoding="utf-8",
            )
            initial = run_scan(project, "--json")
            self.assertEqual(initial.returncode, 0, initial.stderr)
            first_pill = next(
                item
                for item in payload(initial)["findings"]
                if item["rule"] == "uniform-pill-language"
                and item["line"] == 1
            )
            allowlist = project / "allow.json"
            allowlist.write_text(
                json.dumps({
                    "schema_version": 1,
                    "allow": [{
                        "rule": "uniform-pill-language",
                        "path": "buttons.html",
                        "line": 1,
                        "fingerprint": first_pill["fingerprint"],
                        "reason": "Approved pill control in the primary toolbar.",
                        "owner": "Design system owner",
                        "expires": ACTIVE_EXPIRY,
                    }],
                }),
                encoding="utf-8",
            )
            result = run_scan(
                project,
                "--allowlist",
                str(allowlist),
                "--json",
            )
            self.assertEqual(
                result.returncode, 0, result.stdout + result.stderr
            )
            result_payload = payload(result)
            pills = [
                item
                for item in result_payload["findings"]
                if item["rule"] == "uniform-pill-language"
            ]
            suppressed_pills = [
                item
                for item in result_payload["suppressed_findings"]
                if item["rule"] == "uniform-pill-language"
            ]
            self.assertEqual(len(pills), 3)
            self.assertEqual(len(suppressed_pills), 1)
            self.assertEqual(suppressed_pills[0]["line"], 1)

    def test_owner_policy_contract_is_strict_and_literal_filler_exceptions_are_narrow(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.html").write_text(
                "<p>Lorem ipsum</p>",
                encoding="utf-8",
            )
            bundled_policy = (
                PLUGIN
                / "skills"
                / "design-dna"
                / "policy"
                / "owner-defaults.yml"
            ).read_text(encoding="utf-8")
            permissive_policy = project / "owner.yml"
            permissive_policy.write_text(
                bundled_policy.replace(
                    'release_residue: "prohibit"',
                    'release_residue: "allow"',
                ),
                encoding="utf-8",
            )

            scanned = run_scan(
                project,
                "--owner-policy",
                str(permissive_policy),
                "--json",
            )
            self.assertEqual(scanned.returncode, 1, scanned.stderr)
            proof = next(
                item
                for item in payload(scanned)["findings"]
                if item["rule"] == "placeholder-proof"
            )
            self.assertEqual(proof["owner_policy"], "allow")
            self.assertEqual(proof["classification"], "gate")

            invalid_policies = {
                "missing": (
                    project / "missing.yml",
                    "owner policy does not exist",
                ),
                "inactive": (
                    project / "inactive.yml",
                    "owner-policy status must be active",
                ),
                "missing-default": (
                    project / "missing-default.yml",
                    "owner-policy defaults contract mismatch",
                ),
                "unknown-top-level": (
                    project / "unknown-top-level.yml",
                    "owner-policy top-level contract mismatch",
                ),
                "wrong-schema": (
                    project / "wrong-schema.yml",
                    "owner-policy schema_version must be 1",
                ),
                "invalid-enum": (
                    project / "invalid-enum.yml",
                    (
                        "owner-policy default "
                        "fabricated_proof_or_business_facts must be one of"
                    ),
                ),
                "duplicate-list-item": (
                    project / "duplicate-list-item.yml",
                    (
                        "owner-policy headline_fragment_exceptions items "
                        "must be unique"
                    ),
                ),
                "short-list-item": (
                    project / "short-list-item.yml",
                    (
                        "owner-policy headline_fragment_exceptions items "
                        "must contain at least five characters"
                    ),
                ),
            }
            invalid_policies["inactive"][0].write_text(
                bundled_policy.replace('status: "active"', 'status: "draft"'),
                encoding="utf-8",
            )
            invalid_policies["missing-default"][0].write_text(
                bundled_policy.replace(
                    '  release_residue: "prohibit"\n',
                    "",
                ),
                encoding="utf-8",
            )
            invalid_policies["unknown-top-level"][0].write_text(
                bundled_policy + '\nextra_contract: "unsupported"\n',
                encoding="utf-8",
            )
            invalid_policies["wrong-schema"][0].write_text(
                bundled_policy.replace("schema_version: 1", "schema_version: 2"),
                encoding="utf-8",
            )
            invalid_policies["invalid-enum"][0].write_text(
                bundled_policy.replace(
                    'fabricated_proof_or_business_facts: "prohibit"',
                    'fabricated_proof_or_business_facts: "bananas"',
                ),
                encoding="utf-8",
            )
            invalid_policies["duplicate-list-item"][0].write_text(
                bundled_policy.replace(
                    '  - "complete semantic phrase"\n',
                    (
                        '  - "complete semantic phrase"\n'
                        '  - "complete semantic phrase"\n'
                    ),
                    1,
                ),
                encoding="utf-8",
            )
            invalid_policies["short-list-item"][0].write_text(
                bundled_policy.replace(
                    '  - "complete semantic phrase"',
                    '  - "tiny"',
                    1,
                ),
                encoding="utf-8",
            )
            for label, (policy_path, error_text) in invalid_policies.items():
                with self.subTest(policy=label):
                    rejected = run_scan(
                        project,
                        "--owner-policy",
                        str(policy_path),
                        "--json",
                    )
                    self.assertEqual(rejected.returncode, 2)
                    self.assertIn(error_text, rejected.stderr)

            allowlist = project / "allow.json"
            allowlist.write_text(
                json.dumps({
                    "schema_version": 1,
                    "allow": [{
                        "rule": "placeholder-proof",
                        "path": "page.html",
                        "line": proof["line"],
                        "fingerprint": proof["fingerprint"],
                        "reason": "Approved visible typography specimen.",
                        "owner": "Design owner",
                        "expires": ACTIVE_EXPIRY,
                    }],
                }),
                encoding="utf-8",
            )
            accepted_allowlist = run_scan(
                project,
                "--allowlist",
                str(allowlist),
                "--json",
            )
            self.assertEqual(
                accepted_allowlist.returncode,
                0,
                accepted_allowlist.stdout + accepted_allowlist.stderr,
            )
            accepted_payload = payload(accepted_allowlist)
            self.assertFalse(accepted_payload["findings"])
            self.assertEqual(
                accepted_payload["suppressed_findings"][0]["rule"],
                "placeholder-proof",
            )

            accepted_emitter = run_scan(
                project,
                "--emit-allowlist-entry",
                proof["fingerprint"],
                "--allowlist-entry-owner",
                "Design owner",
                "--allowlist-entry-reason",
                "Approved visible typography specimen.",
            )
            self.assertEqual(
                accepted_emitter.returncode,
                0,
                accepted_emitter.stdout + accepted_emitter.stderr,
            )
            emitted = json.loads(accepted_emitter.stdout)
            self.assertEqual(emitted["allow"][0]["rule"], "placeholder-proof")
            self.assertEqual(
                emitted["allow"][0]["fingerprint"],
                proof["fingerprint"],
            )

    def test_skipped_sources_fail_closed_unless_owner_acknowledged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            source = project / "src"
            source.mkdir()
            (source / "not-utf8.tsx").write_bytes(b"\xff\xfe\xff")
            (source / "oversized.css").write_bytes(
                b"x" * (5 * 1024 * 1024 + 1)
            )

            advisory = run_scan(
                project,
                "--json",
                "--advisory-exit-zero",
            )
            self.assertEqual(
                advisory.returncode, 0, advisory.stdout + advisory.stderr
            )
            advisory_payload = payload(advisory)
            self.assertFalse(advisory_payload["ok"])
            self.assertFalse(advisory_payload["gate_enforced"])
            self.assertFalse(advisory_payload["gate_passed"])
            self.assertEqual(advisory_payload["exit_code"], 0)
            self.assertEqual(advisory_payload["scan_status"], "incomplete")
            self.assertEqual(advisory_payload["gate_status"], "incomplete")
            self.assertEqual(
                advisory_payload["quality_status"],
                "incomplete",
            )
            self.assertTrue(
                advisory_payload["exit_policy"][
                    "explicit_advisory_exit_zero"
                ]
            )
            self.assertEqual(
                set(advisory_payload["unacknowledged_skipped_files"]),
                {"src/not-utf8.tsx", "src/oversized.css"},
            )

            gated = run_scan(project, "--json", "--fail-on", "high")
            self.assertEqual(
                gated.returncode, 1, gated.stdout + gated.stderr
            )

            acknowledgement = {
                "path": "src/**",
                "reason": "Repository owner reviewed these generated sources separately.",
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
                "--fail-on",
                "high",
            )
            self.assertEqual(
                acknowledged.returncode,
                0,
                acknowledged.stdout + acknowledged.stderr,
            )
            acknowledged_payload = payload(acknowledged)
            self.assertEqual(
                acknowledged_payload["scan_status"], "incomplete"
            )
            self.assertEqual(
                acknowledged_payload["gate_status"],
                "acknowledged-incomplete",
            )
            self.assertTrue(acknowledged_payload["ok"])
            self.assertTrue(acknowledged_payload["gate_passed"])
            self.assertEqual(
                set(acknowledged_payload["acknowledged_skipped_files"]),
                {"src/not-utf8.tsx", "src/oversized.css"},
            )
            self.assertEqual(
                acknowledged_payload[
                    "active_skipped_source_acknowledgements"
                ],
                [acknowledgement],
            )
            self.assertTrue(
                all(
                    item["acknowledgement"]["owner"] == "Repository owner"
                    for item in acknowledged_payload["skipped_sources"]
                )
            )
            acknowledged_text = run_scan(
                project,
                "--allowlist",
                str(allowlist),
                "--fail-on",
                "high",
            )
            self.assertEqual(
                acknowledged_text.returncode,
                0,
                acknowledged_text.stdout + acknowledged_text.stderr,
            )
            self.assertIn("SKIP-ACK-ACTIVE", acknowledged_text.stdout)
            self.assertEqual(
                acknowledged_text.stdout.count("SKIPPED-ACKNOWLEDGED"),
                2,
            )

            expired_acknowledgement = {
                **acknowledgement,
                "expires": "2000-01-01",
            }
            allowlist.write_text(
                json.dumps({
                    "schema_version": 1,
                    "allow": [],
                    "acknowledge_skipped": [expired_acknowledgement],
                }),
                encoding="utf-8",
            )
            expired = run_scan(
                project,
                "--allowlist",
                str(allowlist),
                "--json",
                "--fail-on",
                "high",
            )
            self.assertEqual(expired.returncode, 1, expired.stderr)
            expired_payload = payload(expired)
            self.assertEqual(
                expired_payload["expired_skipped_source_acknowledgements"],
                [expired_acknowledgement],
            )
            self.assertEqual(
                set(expired_payload["unacknowledged_skipped_files"]),
                {"src/not-utf8.tsx", "src/oversized.css"},
            )


if __name__ == "__main__":
    unittest.main()
