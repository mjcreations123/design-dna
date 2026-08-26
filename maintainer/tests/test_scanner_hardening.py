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
                (project / name).write_text(
                    content + "\nTrusted by thousands.\n",
                    encoding="utf-8",
                )
            story = project / "stories" / "ignored.liquid"
            story.parent.mkdir()
            story.write_text(
                "<style>.title { font-family: Inter; }</style>\n"
                "Trusted by thousands.\n",
                encoding="utf-8",
            )

            result = run_scan(project, "--json")
            self.assertEqual(
                result.returncode, 0, result.stdout + result.stderr
            )
            result_payload = payload(result)
            marker_files = {
                item["file"]
                for item in result_payload["findings"]
                if item["rule"] == "claim-needs-provenance"
            }
            self.assertEqual(marker_files, set(sources))
            self.assertFalse(
                any(
                    item["rule"] == "unexamined-default-font"
                    for item in result_payload["findings"]
                )
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
                if item["rule"] == "claim-needs-provenance"
            }
            self.assertIn("stories/ignored.liquid", included_files)

    def test_font_family_names_and_css_shorthand_are_neutral(
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
            self.assertFalse(
                any(
                    item["rule"] == "unexamined-default-font"
                    for item in payload(found)["findings"]
                )
            )

            not_found = run_scan(ignored, "--json")
            self.assertEqual(not_found.returncode, 0, not_found.stderr)
            self.assertFalse(
                any(
                    item["rule"] == "unexamined-default-font"
                    for item in payload(not_found)["findings"]
                )
            )

    def test_portable_aesthetic_ingredients_are_neutral_without_rendered_harm(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.html").write_text(
                """\
<style>
:root {
  --background: oklch(1 0 0);
  --foreground: oklch(.145 0 0);
  --primary: oklch(.205 0 0);
  --secondary: oklch(.97 0 0);
  --muted: oklch(.97 0 0);
  --accent: oklch(.97 0 0);
}
.gradient-one, .gradient-two, .gradient-three {
  background: linear-gradient(90deg, red, blue);
  background-clip: text;
}
.pill { border-radius: 9999px; }
.large-gap { padding-block: 12rem; }
.card:hover { transform: translateY(-.25rem) scale(1.03); }
.hero span { color: #7c3aed; }
</style>
<main>
  <p class="eyebrow">Field note</p>
  <h1 class="hero gradient-one">Build <span style="color:#7c3aed">bold</span>,
    <span style="color:#7c3aed">clear</span>,
    <span style="color:#7c3aed">useful</span>, and
    <span style="color:#7c3aed">alive</span>.</h1>
  <section class="fade-up large-gap">
    <h2 class="gradient-two">Signal console</h2>
    <p>Proposed channel relay module route status system transmission vocabulary,
      with unresolved incidents and unassigned queues.</p>
    <button class="pill">Get Started ✨</button>
    <a href="#details">Learn More 🚀</a>
  </section>
  <section id="details" class="animate-in gradient-three">
    <svg role="img" aria-label="A useful process diagram"></svg>
    <canvas aria-label="Interactive map"></canvas>
  </section>
</main>
<script>const icons = [Sparkles, WandSparkles, Rocket, Zap];</script>
""",
                encoding="utf-8",
            )

            result = run_scan(project, "--json", "--fail-on", "low")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result_payload = payload(result)
            self.assertEqual(result_payload["findings"], [])
            self.assertTrue(
                {
                    "prominent-fragment-context",
                    "prominent-fragment-dynamic-style",
                    "prominent-fragment-selector-context",
                }.isdisjoint(
                    {item["check"] for item in result_payload["manual_review"]}
                )
            )
            self.assertTrue(
                {
                    "sensory-media-strategy",
                    "copy-uniformity-cluster",
                    "over-instrumented-concept-deck",
                    "parallel-route-skeleton",
                }.isdisjoint(
                    {item["check"] for item in result_payload["manual_review"]}
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
                default.returncode, 1, default.stdout + default.stderr
            )
            default_payload = payload(default)
            self.assertEqual(
                default_payload["quality_status"],
                "no-selected-sources",
            )
            self.assertFalse(default_payload["source_gate_passed"])
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
                "Theme sample: font-family: Inter\nTrusted by thousands.\n",
                encoding="utf-8",
            )
            (docs / "guide.mdx").write_text(
                "Guide typography uses fontFamily: 'Inter'.\n"
                "Trusted by thousands.\n",
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
            self.assertEqual(default.returncode, 1, default.stderr)
            default_payload = payload(default)
            self.assertEqual(
                default_payload["scan_status"],
                "no-selected-sources",
            )
            self.assertFalse(default_payload["source_gate_passed"])
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
            scanned_markers = {
                item["file"]
                for item in content_payload["findings"]
                if item["rule"] == "claim-needs-provenance"
            }
            self.assertEqual(scanned_markers, {"README.md", "docs/guide.mdx"})
            self.assertFalse(
                any(
                    item["rule"] == "unexamined-default-font"
                    for item in content_payload["findings"]
                )
            )

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

    def test_single_fragment_is_not_a_source_ingredient_detector(self) -> None:
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
            self.assertFalse(
                any(
                    item["rule"] == "decorative-headline-span"
                    for item in result_payload["findings"]
                )
            )
            self.assertFalse(
                any(
                    str(item["check"]).startswith("prominent-fragment")
                    for item in result_payload["manual_review"]
                )
            )
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


class ScannerPreheadingPublicPurposeTests(unittest.TestCase):
    def preheading_reviews(
        self,
        result: subprocess.CompletedProcess[str],
    ) -> list[dict[str, object]]:
        return [
            item
            for item in payload(result)["manual_review"]
            if item["check"] == "preheading-public-purpose"
        ]

    def test_optical_study_is_a_contextual_manual_review_not_a_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.tsx").write_text(
                """\
<main><section>
<p className="eyebrow">The optical study</p>
<h1>Light, where it earns its place.</h1>
</section></main>
""",
                encoding="utf-8",
            )
            result = run_scan(project, "--json", "--fail-on", "low")
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )
            result_payload = payload(result)
            reviews = self.preheading_reviews(result)
            self.assertEqual(len(reviews), 1)
            self.assertEqual(reviews[0]["file"], "page.tsx")
            self.assertEqual(reviews[0]["line"], 2)
            self.assertEqual(reviews[0]["severity"], "low")
            self.assertIn("not evidence of AI", reviews[0]["reason"])
            self.assertIn("rendered page", reviews[0]["suggestion"])
            example = reviews[0]["evidence"]["examples"][0]
            self.assertEqual(example["path"], "page.tsx")
            self.assertEqual(example["line"], 2)
            self.assertEqual(example["text"], "The optical study")
            self.assertEqual(example["heading"], "Light, where it earns its place.")
            self.assertEqual(example["relationship"], "immediately-precedes-h1")
            self.assertIn("class:eyebrow", example["signals"])
            self.assertTrue(result_payload["review_required"])
            self.assertTrue(result_payload["source_gate_passed"])
            self.assertEqual(sum(result_payload["gate_counts"].values()), 0)
            self.assertNotIn(
                "repeated-decorative-section-label",
                {item["rule"] for item in result_payload["findings"]},
            )

    def test_supported_style_tokens_and_numbered_or_repeated_labels_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.tsx").write_text(
                """\
<main>
<section><span class="hero-kicker">Materials</span><h2>Built to last</h2></section>
<section><small className={'overline'}>Neighborhood</small><h2>Made here</h2></section>
<section><div className={`section-label`}>What follows</div><h2>The work</h2></section>
<section><p>01 / Context</p><h2>Where this begins</h2></section>
<section><p>02 / Context</p><h2>Where this leads</h2></section>
<section><p>Field note</p><h2>First observation</h2></section>
<section><p>Field note</p><h2>Second observation</h2></section>
</main>
""",
                encoding="utf-8",
            )
            result = run_scan(project, "--json", "--fail-on", "low")
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )
            reviews = self.preheading_reviews(result)
            self.assertEqual(len(reviews), 1)
            self.assertEqual(reviews[0]["severity"], "medium")
            examples = reviews[0]["evidence"]["examples"]
            self.assertEqual(len(examples), 7)
            by_text = {item["text"]: item for item in examples}
            self.assertIn("class:kicker", by_text["Materials"]["signals"])
            self.assertIn("class:overline", by_text["Neighborhood"]["signals"])
            self.assertIn("class:section-label", by_text["What follows"]["signals"])
            self.assertIn(
                "numbered-or-sequenced-label",
                by_text["01 / Context"]["signals"],
            )
            field_notes = [item for item in examples if item["text"] == "Field note"]
            self.assertEqual(len(field_notes), 2)
            self.assertTrue(
                all(
                    "repeated-label-pattern" in item["signals"]
                    and item["repeated_count"] == 2
                    for item in field_notes
                )
            )
            self.assertEqual(sum(payload(result)["gate_counts"].values()), 0)

    def test_backend_category_class_and_data_attribute_are_hints_not_exemptions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.tsx").write_text(
                """\
<main><section><div className="hero-copy">
<p className="category" data-category="optical">The optical study</p>
<h2>Light, where it earns its place.</h2>
</div></section></main>
""",
                encoding="utf-8",
            )
            result = run_scan(project, "--json", "--fail-on", "low")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            reviews = self.preheading_reviews(result)
            self.assertEqual(len(reviews), 1)
            example = reviews[0]["evidence"]["examples"][0]
            self.assertEqual(example["text"], "The optical study")
            self.assertEqual(example["class_tokens"], ["category"])
            self.assertEqual(
                example["semantic_hints"],
                ["attribute:data-category", "class-token:category"],
            )
            self.assertIn("semantic-purpose-hint", example["signals"])
            self.assertNotIn(
                "class:unrecognized-preheading-token",
                example["signals"],
            )
            self.assertIn("only a semantic hint", reviews[0]["suggestion"])
            self.assertTrue(payload(result)["source_gate_passed"])
            self.assertEqual(sum(payload(result)["gate_counts"].values()), 0)

    def test_source_and_state_data_attributes_are_review_hints(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.html").write_text(
                """\
<main>
  <section><p data-source="brief">The optical study</p><h2>Light bends here.</h2></section>
  <section><span data-state="internal">Material study</span><h2>Water changes the path.</h2></section>
</main>
""",
                encoding="utf-8",
            )
            result = run_scan(project, "--json", "--fail-on", "low")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            reviews = self.preheading_reviews(result)
            self.assertEqual(len(reviews), 1)
            examples = {
                item["text"]: item for item in reviews[0]["evidence"]["examples"]
            }
            self.assertIn(
                "attribute:data-source",
                examples["The optical study"]["semantic_hints"],
            )
            self.assertIn(
                "attribute:data-state",
                examples["Material study"]["semantic_hints"],
            )
            self.assertTrue(
                all(
                    "semantic-purpose-hint" in item["signals"]
                    for item in examples.values()
                )
            )
            self.assertEqual(sum(payload(result)["gate_counts"].values()), 0)

    def test_form_labels_bound_to_controls_are_not_preheading_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.tsx").write_text(
                """\
<main><section>
  <label class="field-label" for="email">Email address</label>
  <p>We use this only for the requested reply.</p>
  <label className="field-label" htmlFor="phone">Phone number</label>
  <p>Include the area code.</p>
  <label className="field-label">Preferred day <input name="day" /></label>
  <p>Choose any weekday.</p>
</section></main>
""",
                encoding="utf-8",
            )
            result = run_scan(project, "--json", "--fail-on", "low")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(self.preheading_reviews(result), [])
            self.assertEqual(sum(payload(result)["gate_counts"].values()), 0)

    def test_unique_unknown_class_surfaces_without_a_known_style_token(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.tsx").write_text(
                """\
<main><section>
<span className="prelude">The optical study</span>
<h2>Light, where it earns its place.</h2>
</section></main>
""",
                encoding="utf-8",
            )
            result = run_scan(project, "--json", "--fail-on", "low")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            reviews = self.preheading_reviews(result)
            self.assertEqual(len(reviews), 1)
            example = reviews[0]["evidence"]["examples"][0]
            self.assertEqual(example["class_tokens"], ["prelude"])
            self.assertEqual(example["semantic_hints"], [])
            self.assertIn(
                "class:unrecognized-preheading-token",
                example["signals"],
            )
            self.assertEqual(example["relationship"], "immediately-precedes-h2")

    def test_section_leading_label_before_body_paragraph_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.html").write_text(
                """\
<main><section>
<span class="prelude">Our approach</span>
<p>We repair the exact part that failed.</p>
</section></main>
""",
                encoding="utf-8",
            )
            result = run_scan(project, "--json", "--fail-on", "low")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            reviews = self.preheading_reviews(result)
            self.assertEqual(len(reviews), 1)
            example = reviews[0]["evidence"]["examples"][0]
            self.assertEqual(example["target_element"], "p")
            self.assertEqual(
                example["relationship"],
                "section-leading-label-before-p",
            )
            self.assertTrue(example["section_leading"])
            self.assertIn("section-leading-body-label", example["signals"])

    def test_simple_static_wrapper_between_label_and_heading_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.tsx").write_text(
                """\
<main><section>
<span className="prelude">Materials</span>
<div className="heading-frame"><header><h2>Built to last</h2></header></div>
</section></main>
""",
                encoding="utf-8",
            )
            result = run_scan(project, "--json", "--fail-on", "low")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            reviews = self.preheading_reviews(result)
            self.assertEqual(len(reviews), 1)
            example = reviews[0]["evidence"]["examples"][0]
            self.assertEqual(example["wrapper_tags"], ["div", "header"])
            self.assertEqual(
                example["relationship"],
                "precedes-h2-through-static-wrapper",
            )
            self.assertEqual(example["target_text"], "Built to last")

    def test_built_output_html_is_reviewed_only_when_explicitly_included(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            built = project / "dist"
            built.mkdir()
            (project / "source.js").write_text("export const ready = true;\n", encoding="utf-8")
            (built / "index.html").write_text(
                '<main><section><small class="prelude">The optical study</small>'
                '<h1>Light, where it earns its place.</h1></section></main>',
                encoding="utf-8",
            )

            excluded = run_scan(project, "--json", "--fail-on", "low")
            self.assertEqual(excluded.returncode, 0, excluded.stdout + excluded.stderr)
            self.assertEqual(self.preheading_reviews(excluded), [])

            included = run_scan(
                project,
                "--json",
                "--fail-on",
                "low",
                "--built-output",
            )
            self.assertEqual(included.returncode, 0, included.stdout + included.stderr)
            reviews = self.preheading_reviews(included)
            self.assertEqual(len(reviews), 1)
            self.assertEqual(reviews[0]["file"], "dist/index.html")
            self.assertEqual(
                reviews[0]["evidence"]["examples"][0]["text"],
                "The optical study",
            )

    def test_label_without_a_following_public_content_relationship_does_not_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.tsx").write_text(
                """\
<section><p className="eyebrow">Our approach</p></section>
<section><span class="hero-kicker">Materials</span><figure><img alt="" /></figure></section>
<section><small className={'overline'}>Neighborhood</small></section>
""",
                encoding="utf-8",
            )
            result = run_scan(project, "--json", "--fail-on", "low")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(self.preheading_reviews(result), [])
            self.assertFalse(payload(result)["review_required"])
            self.assertEqual(sum(payload(result)["gate_counts"].values()), 0)

    def test_strong_structural_semantics_do_not_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.tsx").write_text(
                """\
<main>
<nav><span className="eyebrow">Home</span><h2>Breadcrumb target</h2></nav>
<section><time className="eyebrow" dateTime="2026-08-23">August 23, 2026</time><h2>News</h2></section>
<section><p className="date eyebrow">August 23, 2026</p><h2>News archive</h2></section>
<section><p className="status eyebrow" role="status">Open</p><h2>Applications</h2></section>
<section><button className="filter kicker" aria-selected="true">Recent</button><h2>Results</h2></section>
<section><button className="overline" role="tab">Details</button><h2>Panel</h2></section>
<section><p className="step eyebrow">Step 2 of 4</p><h2>Address</h2></section>
<fieldset><legend className="overline">Contact details</legend><h2>Application</h2></fieldset>
<section><p>Short introduction</p><p>The body continues here.</p></section>
</main>
""",
                encoding="utf-8",
            )
            result = run_scan(project, "--json", "--fail-on", "low")
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )
            self.assertEqual(self.preheading_reviews(result), [])
            self.assertFalse(payload(result)["review_required"])
            self.assertEqual(sum(payload(result)["gate_counts"].values()), 0)


class ScannerEvidenceBoundReviewTests(unittest.TestCase):
    def test_failed_concept_deck_signals_require_manual_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            texture = " ".join(
                ["Coffee, pastries, music, and a room for neighbors to meet."] * 45
            )
            (project / "index.html").write_text(
                f"""\
<main>
<section><p class="eyebrow">Route 001 / proposed</p>
<h1>A system for the handoff.</h1><p>{texture}</p>
<button disabled>Stream not connected</button></section>
<section><p class="eyebrow">Signal status</p>
<h2>Choose a page route</h2><p>Fictional concept with an unassigned channel.</p>
<svg aria-hidden="true"></svg></section>
<section><p class="eyebrow">Relay 002 / illustrative</p>
<h2>Inspect the proposed room</h2><p>Sample schedule with unresolved details.</p></section>
<section><p class="eyebrow">Truth before theater</p>
<h2>Route study</h2><p>Concept build. Visits unavailable.</p></section>
</main>
""",
                encoding="utf-8",
            )
            (project / "styles.css").write_text(
                """\
h1, .hero-title {
  font-stretch: 75%;
  letter-spacing: -0.072em;
  line-height: .84;
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
            checks = {
                item["check"]
                for item in payload(result)["manual_review"]
            }
            self.assertTrue(
                {
                    "public-meta-copy-contamination",
                    "nonfunctional-concept-affordance",
                }.issubset(checks)
            )
            self.assertTrue(
                {
                    "compound-display-compression",
                    "severe-typography-compression",
                }.isdisjoint(checks)
            )
            self.assertTrue(
                {
                    "sensory-media-strategy",
                    "over-instrumented-concept-deck",
                }.isdisjoint(checks)
            )

    def test_readable_photo_led_local_site_avoids_new_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            texture = " ".join(
                ["The cafe serves coffee and breakfast in a bright corner room."] * 30
            )
            (project / "index.html").write_text(
                f"""\
<main>
<section><h1>Coffee and breakfast, seven days a week.</h1>
<p>{texture}</p><img src="interior.webp" alt="Cafe interior"></section>
<section><h2>See the menu</h2><p>Drinks, toast, and pastries.</p></section>
<section><h2>Plan a visit</h2><p>Find current hours and directions.</p></section>
</main>
""",
                encoding="utf-8",
            )
            (project / "styles.css").write_text(
                """\
h1 { letter-spacing: -0.02em; line-height: 1.02; }
body { letter-spacing: normal; line-height: 1.6; }
""",
                encoding="utf-8",
            )
            result = run_scan(project, "--json")
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )
            checks = {
                item["check"]
                for item in payload(result)["manual_review"]
            }
            self.assertTrue(
                {
                    "compound-display-compression",
                    "public-meta-copy-contamination",
                    "sensory-media-strategy",
                    "nonfunctional-concept-affordance",
                    "over-instrumented-concept-deck",
                }.isdisjoint(checks)
            )

    def test_public_internal_method_review_has_no_count_prescription(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "index.html").write_text(
                "<main><p>Project assets are not supplied.</p></main>",
                encoding="utf-8",
            )
            result = run_scan(project, "--json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            reviews = [
                item
                for item in payload(result)["manual_review"]
                if item["check"] == "public-meta-copy-contamination"
            ]
            self.assertEqual(len(reviews), 1)
            self.assertEqual(reviews[0]["evidence"]["match_count"], 1)
            self.assertIn(
                "universal disclosure count",
                reviews[0]["suggestion"].casefold(),
            )

    def test_honest_concept_disclosure_is_not_internal_methodology_leakage(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "index.html").write_text(
                "<main><p>Independent fictional sample website; "
                "illustrative concept only.</p></main>",
                encoding="utf-8",
            )
            result = run_scan(project, "--json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn(
                "public-meta-copy-contamination",
                {item["check"] for item in payload(result)["manual_review"]},
            )

    def test_public_design_process_wording_is_reviewed_without_banning_disclosure(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "index.html").write_text(
                "<header><small>Fictional interaction study</small></header>"
                "<main><p>This puzzle is illustrative and has no live event.</p></main>",
                encoding="utf-8",
            )
            result = run_scan(project, "--json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            reviews = [
                item
                for item in payload(result)["manual_review"]
                if item["check"] == "public-meta-copy-contamination"
            ]
            self.assertEqual(len(reviews), 1)
            self.assertEqual(reviews[0]["evidence"]["match_count"], 1)
            self.assertIn(
                "keep every disclosure",
                reviews[0]["suggestion"].casefold(),
            )

    def test_one_display_compression_control_is_not_a_cluster(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "styles.css").write_text(
                "h1 { letter-spacing: -0.04em; line-height: 1.05; }",
                encoding="utf-8",
            )
            result = run_scan(project, "--json")
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )
            self.assertNotIn(
                "compound-display-compression",
                {
                    item["check"]
                    for item in payload(result)["manual_review"]
                },
            )

    def test_framework_routes_do_not_receive_genre_media_prescriptions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            texture = " ".join(
                ["Coffee, breakfast, pastry, and room details help plan a visit."] * 35
            )
            route = f"""\
<main>
<section><h1>Neighborhood coffee</h1><p>{texture}</p></section>
<section><h2>Breakfast</h2><p>Toast and pastries are described here.</p></section>
<section><h2>Visit</h2><p>Plan a visit to the coffee room.</p></section>
</main>
"""
            extensions = ("astro", "jsx", "svelte", "tsx", "vue")
            for extension in extensions:
                (project / f"page.{extension}").write_text(
                    route,
                    encoding="utf-8",
                )
            result = run_scan(project, "--json")
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )
            self.assertNotIn(
                "sensory-media-strategy",
                {
                    item["check"]
                    for item in payload(result)["manual_review"]
                },
            )

    def test_media_review_follows_actual_references_not_genre_words(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            texture = " ".join(
                ["The menu covers coffee, breakfast, pastry, and lunch."] * 40
            )
            (project / "home.html").write_text(
                """\
<main><section><h1>Coffee shop</h1>
<img src="room.webp" alt="Coffee room"></section></main>
""",
                encoding="utf-8",
            )
            (project / "menu.html").write_text(
                f"""\
<main>
<section><h1>Menu</h1><p>{texture}</p></section>
<section><h2>Breakfast</h2><p>Toast and pastry.</p></section>
<section><h2>Lunch</h2><p>Soup and sandwiches.</p></section>
</main>
""",
                encoding="utf-8",
            )
            result = run_scan(project, "--json")
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )
            media = [
                item
                for item in payload(result)["manual_review"]
                if item["check"] == "media-authenticity-and-provenance"
            ]
            self.assertEqual(
                [item["file"] for item in media],
                ["home.html"],
            )
            self.assertNotIn(
                "sensory-media-strategy",
                {item["check"] for item in payload(result)["manual_review"]},
            )

    def test_typography_values_do_not_create_source_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "styles.css").write_text(
                """\
h1 { letter-spacing: -0.10em; line-height: 1.05; }
.article-copy { letter-spacing: -0.05em; line-height: 1.10; }
""",
                encoding="utf-8",
            )
            result = run_scan(project, "--json")
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )
            self.assertTrue(
                {
                    "compound-display-compression",
                    "severe-typography-compression",
                }.isdisjoint(
                    {item["check"] for item in payload(result)["manual_review"]}
                )
            )

    def test_tailwind_and_inline_typography_values_remain_neutral(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.tsx").write_text(
                """\
export function Page() {
  return <main>
    <h1 className="tracking-[-0.10em] leading-[0.78] [font-stretch:75%]">
      Relay Room
    </h1>
    <p style={{ letterSpacing: "-0.05em", lineHeight: 1.10 }}>
      Comfortable reading should not be compressed into a display gesture.
    </p>
    <h2 style={{ letterSpacing: "-0.08em" }}>Schedule</h2>
  </main>;
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
            self.assertTrue(
                {
                    "compound-display-compression",
                    "severe-typography-compression",
                }.isdisjoint(
                    {item["check"] for item in payload(result)["manual_review"]}
                )
            )

    def test_moderate_inline_typography_avoids_compression_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.tsx").write_text(
                """\
export function Page() {
  return <main>
    <h1 className="tracking-[-0.04em] leading-[1.05]">Coffee today</h1>
    <p style={{ letterSpacing: "-0.01em", lineHeight: 1.5 }}>
      A comfortable paragraph with a conventional reading rhythm.
    </p>
  </main>;
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
            self.assertTrue(
                {
                    item["check"]
                    for item in payload(result)["manual_review"]
                }.isdisjoint({
                    "compound-display-compression",
                    "severe-typography-compression",
                })
            )

    def test_technical_concept_vocabulary_is_not_a_house_style_detector(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            texture = " ".join(
                [
                    "Transmission status signal relay route module system console."
                ]
                * 12
            )
            (project / "index.html").write_text(
                f"""\
<main>
<section><p class="eyebrow">Route 001 / proposed</p>
<h1>A system for listening.</h1><p>Concept site. {texture}</p></section>
<section><p class="eyebrow">Signal status</p>
<svg aria-hidden="true"></svg><p>Sample route with unresolved details.</p></section>
<section><p class="eyebrow">Relay 002 / illustrative</p>
<button disabled>Stream not connected</button></section>
<section><p class="eyebrow">System handoff</p>
<p>Inspect the proposed room.</p></section>
</main>
""",
                encoding="utf-8",
            )
            (project / "styles.css").write_text(
                "h1 { letter-spacing: -0.10em; line-height: .78; }",
                encoding="utf-8",
            )
            result = run_scan(project, "--json")
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )
            checks = {
                item["check"]
                for item in payload(result)["manual_review"]
            }
            self.assertNotIn("over-instrumented-concept-deck", checks)
            self.assertIn("public-meta-copy-contamination", checks)
            self.assertIn("nonfunctional-concept-affordance", checks)
            self.assertNotIn("compound-display-compression", checks)
            self.assertNotIn("severe-typography-compression", checks)

    def test_compact_legitimate_status_interface_avoids_concept_deck_prompt(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "index.html").write_text(
                """\
<main>
<section aria-labelledby="service-title"><h1 id="service-title">Service health</h1>
<p role="status">All systems operational</p></section>
<section><h2>API</h2><p>Requests are processing normally.</p>
<svg aria-label="API response-time history"></svg></section>
<section><h2>Notifications</h2><p>Email delivery is operational.</p></section>
<section><h2>Recent incidents</h2><p>No incidents reported.</p></section>
</main>
""",
                encoding="utf-8",
            )
            (project / "styles.css").write_text(
                "h1 { letter-spacing: -0.03em; line-height: 1; }"
                " body { letter-spacing: normal; line-height: 1.6; }",
                encoding="utf-8",
            )
            result = run_scan(project, "--json")
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )
            self.assertNotIn(
                "over-instrumented-concept-deck",
                {
                    item["check"]
                    for item in payload(result)["manual_review"]
                },
            )

    def test_evidence_bound_reviews_survive_aesthetic_detector_removal(self) -> None:
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
            self.assertTrue(
                {
                    "repeated-decorative-section-label",
                    "rhetorical-label-cluster",
                    "presentation-script-comment-cluster",
                }.isdisjoint(rules)
            )
            checks = {
                item["check"] for item in result_payload["manual_review"]
            }
            self.assertTrue(
                {
                    "generated-media-authenticity",
                }.issubset(checks)
            )
            self.assertNotIn("quantitative-claim-density", checks)
            self.assertTrue(
                {
                    "copy-uniformity-cluster",
                    "parallel-route-skeleton",
                    "concept-material-balance",
                    "over-instrumented-concept-deck",
                }.isdisjoint(checks)
            )
            self.assertTrue(result_payload["source_gate_passed"])
            self.assertTrue(result_payload["review_required"])
            self.assertEqual(result_payload["design_review_status"], "pending")
            self.assertGreater(result_payload["manual_review_count"], 0)
            self.assertEqual(result_payload["unresolved_advisory_count"], 0)

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

    def test_current_exact_and_default_like_oklch_clusters_are_neutral(
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
                self.assertEqual(findings, [], profile)
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

    def test_legacy_hsl_cluster_is_also_neutral(self) -> None:
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
            self.assertEqual(findings, [])
            self.assertEqual(sum(payload(result)["gate_counts"].values()), 0)


class ScannerProminentFragmentTests(unittest.TestCase):
    def test_source_scanner_does_not_resolve_styled_fragments_as_ingredients(
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
            self.assertTrue(
                {
                    "prominent-fragment-context",
                    "prominent-fragment-dynamic-style",
                    "prominent-fragment-selector-context",
                }.isdisjoint(
                    {item["check"] for item in payload(result)["manual_review"]}
                )
            )
            self.assertFalse(
                any(
                    item["rule"] == "decorative-headline-span"
                    for item in payload(result)["findings"]
                )
            )

    def test_dynamic_fragment_style_is_not_a_source_ingredient_detector(self) -> None:
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
            self.assertFalse(
                any(
                    str(item["check"]).startswith("prominent-fragment")
                    for item in result_payload["manual_review"]
                )
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
    def test_palette_and_type_recipe_is_neutral_by_itself(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "style.css").write_text(
                ":root { --surface: #f3eddf; --accent: #536b55; "
                "--font-display: Georgia, serif; }\n",
                encoding="utf-8",
            )
            result = run_scan(project, "--json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            rules = {item["rule"] for item in payload(result)["findings"]}
            self.assertNotIn("cream-serif-sage-cluster", rules)
            self.assertFalse(any("cream-serif-sage" in rule for rule in rules))

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

    def test_changed_evidence_signal_is_not_suppressed_by_old_fingerprint(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            page = project / "page.html"
            page.write_text("<p>Trusted by thousands.</p>\n", encoding="utf-8")
            initial = run_scan(project, "--json")
            self.assertEqual(initial.returncode, 0, initial.stderr)
            initial_findings = [
                item for item in payload(initial)["findings"]
                if item["rule"] == "claim-needs-provenance"
            ]
            self.assertEqual(len(initial_findings), 1)
            initial_finding = initial_findings[0]
            repeated = run_scan(project, "--json")
            repeated_finding = next(
                item for item in payload(repeated)["findings"]
                if item["rule"] == "claim-needs-provenance"
                and item["line"] == initial_finding["line"]
            )
            self.assertEqual(
                initial_finding["fingerprint"], repeated_finding["fingerprint"]
            )

            allowlist = project / "allow.json"
            allowlist.write_text(
                json.dumps({
                    "schema_version": 1,
                    "allow": [{
                        "rule": initial_finding["rule"],
                        "path": initial_finding["file"],
                        "line": initial_finding["line"],
                        "fingerprint": initial_finding["fingerprint"],
                        "reason": "Reviewed initial rendered treatment.",
                        "owner": "Design owner",
                        "expires": ACTIVE_EXPIRY,
                    }],
                }),
                encoding="utf-8",
            )
            page.write_text(
                "<p>Industry-leading service.</p>\n",
                encoding="utf-8",
            )
            changed = run_scan(
                project, "--allowlist", str(allowlist), "--json"
            )
            self.assertEqual(changed.returncode, 0, changed.stdout + changed.stderr)
            changed_payload = payload(changed)
            changed_finding = next(
                item for item in changed_payload["findings"]
                if item["rule"] == "claim-needs-provenance"
                and item["line"] == initial_finding["line"]
            )
            self.assertNotEqual(
                initial_finding["matched_signal"], changed_finding["matched_signal"]
            )
            self.assertNotEqual(
                initial_finding["fingerprint"], changed_finding["fingerprint"]
            )
            self.assertEqual(changed_payload["suppressed_count"], 0)

    def test_expiry_values_must_be_exact_schema_date_strings(self) -> None:
        allow_entry = {
            "rule": "claim-needs-provenance",
            "path": "page.html",
            "fingerprint": "0" * 64,
            "reason": "Reviewed visual treatment.",
            "owner": "Design owner",
            "expires": ACTIVE_EXPIRY,
        }
        acknowledgement = {
            "path": "src/**",
            "sha256": "0" * 64,
            "size_bytes": 123,
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
            {
                "path",
                "sha256",
                "size_bytes",
                "reason",
                "owner",
                "expires",
            },
        )
        expected_expiry = (
            date.today() + timedelta(days=30)
        ).isoformat()
        self.assertEqual(template["allow"][0]["expires"], expected_expiry)
        self.assertEqual(
            template["acknowledge_skipped"][0]["expires"],
            expected_expiry,
        )
        packaged_example = json.loads(
            (
                PLUGIN
                / "skills"
                / "design-dna"
                / "templates"
                / "scan-allowlist.example.json"
            ).read_text(encoding="utf-8")
        )
        for collection in ("allow", "acknowledge_skipped"):
            self.assertEqual(
                "REPLACE_WITH_DATE_WITHIN_90_DAYS",
                packaged_example[collection][0]["expires"],
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
            "rule": "claim-needs-provenance",
            "path": "src/page.html",
            "fingerprint": "0" * 64,
            "reason": " a   b ",
            "owner": " Design owner ",
            "expires": ACTIVE_EXPIRY,
        }
        acknowledgement = {
            "path": "generated/**",
            "sha256": "0" * 64,
            "size_bytes": 123,
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
            "rule": "claim-needs-provenance",
            "path": "page.html",
            "fingerprint": "0" * 64,
            "reason": "Reviewed project-specific treatment.",
            "owner": "Design owner",
            "expires": ACTIVE_EXPIRY,
        }
        acknowledgement = {
            "path": "generated/**",
            "sha256": "0" * 64,
            "size_bytes": 123,
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

    def test_retired_aesthetic_rules_cannot_be_allowlisted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.html").write_text(
                "<main><p>Reviewed content.</p></main>",
                encoding="utf-8",
            )
            allowlist = project / "allow.json"
            allowlist.write_text(
                json.dumps({
                    "schema_version": 1,
                    "allow": [{
                        "rule": "repeated-gradient-text",
                        "path": "page.html",
                        "fingerprint": "0" * 64,
                        "reason": "Stale aesthetic exception.",
                        "owner": "Design owner",
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
            self.assertEqual(result.returncode, 2)
            self.assertIn("unknown allowlist rule", result.stderr)

    def test_emits_schema_valid_entry_for_an_actual_finding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.tsx").write_text(
                "<main><p>Trusted by thousands.</p></main>\n",
                encoding="utf-8",
            )
            first = run_scan(project, "--json")
            self.assertEqual(first.returncode, 0, first.stderr)
            finding = next(
                item
                for item in payload(first)["findings"]
                if item["rule"] == "claim-needs-provenance"
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
                "<p>Trusted by thousands.</p>\n"
                "<p>Industry-leading service.</p>\n"
                "<p>Five-star rated care.</p>\n",
                encoding="utf-8",
            )
            initial = run_scan(project, "--json")
            self.assertEqual(initial.returncode, 0, initial.stderr)
            initial_finding = next(
                item
                for item in payload(initial)["findings"]
                if item["rule"] == "claim-needs-provenance"
            )
            allowlist = project / "allow.json"
            entry = {
                "rule": "claim-needs-provenance",
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
            self.assertEqual(
                sum(
                    item["rule"] == entry["rule"]
                    for item in result_payload["findings"]
                ),
                2,
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

    def test_allowlist_suppresses_only_the_exact_evidence_fingerprint(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "buttons.html").write_text(
                "<p>Trusted by thousands.</p>\n"
                "<p>Industry-leading service.</p>\n"
                "<p>Five-star rated care.</p>\n",
                encoding="utf-8",
            )
            initial = run_scan(project, "--json")
            self.assertEqual(initial.returncode, 0, initial.stderr)
            first_claim = next(
                item
                for item in payload(initial)["findings"]
                if item["rule"] == "claim-needs-provenance"
                and item["line"] == 1
            )
            allowlist = project / "allow.json"
            allowlist.write_text(
                json.dumps({
                    "schema_version": 1,
                    "allow": [{
                        "rule": "claim-needs-provenance",
                        "path": "buttons.html",
                        "line": 1,
                        "fingerprint": first_claim["fingerprint"],
                        "reason": "Approved claim with documented evidence.",
                        "owner": "Content owner",
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
            claims = [
                item
                for item in result_payload["findings"]
                if item["rule"] == "claim-needs-provenance"
            ]
            suppressed_claims = [
                item
                for item in result_payload["suppressed_findings"]
                if item["rule"] == "claim-needs-provenance"
            ]
            self.assertEqual(len(claims), 2)
            self.assertEqual(len(suppressed_claims), 1)
            self.assertEqual(suppressed_claims[0]["line"], 1)

    def test_owner_policy_contract_is_extensible_and_literal_filler_exceptions_are_narrow(
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
            project_policy = project / ".design-dna" / "owner-policy.yml"
            project_policy.parent.mkdir()
            project_policy.write_text(
                permissive_policy.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            auto_discovered = run_scan(project, "--json")
            self.assertEqual(auto_discovered.returncode, 1, auto_discovered.stderr)
            auto_proof = next(
                item
                for item in payload(auto_discovered)["findings"]
                if item["rule"] == "placeholder-proof"
            )
            self.assertEqual(auto_proof["owner_policy"], "allow")
            self.assertEqual(
                payload(auto_discovered)["owner_policy"],
                "project:/.design-dna/owner-policy.yml",
            )
            auto_payload = payload(auto_discovered)
            self.assertEqual(auto_payload["project"], "project:/")
            self.assertFalse(
                Path(auto_payload["owner_policy"]).is_absolute()
            )
            self.assertNotIn("type_watch", auto_payload)

            invalid_policies = {
                "missing": (
                    project / "missing.yml",
                    "owner policy does not exist",
                ),
                "inactive": (
                    project / "inactive.yml",
                    "owner-policy status must be active",
                ),
                "unknown-top-level": (
                    project / "unknown-top-level.yml",
                    "owner-policy top-level contract mismatch",
                ),
                "wrong-schema": (
                    project / "wrong-schema.yml",
                    "owner-policy schema_version must be 2",
                ),
                "invalid-enum": (
                    project / "invalid-enum.yml",
                    (
                        "owner-policy default "
                        "truth_and_claims must be one of"
                    ),
                ),
                "invalid-id": (
                    project / "invalid-id.yml",
                    "is not a portable concern ID",
                ),
            }
            invalid_policies["inactive"][0].write_text(
                bundled_policy.replace('status: "active"', 'status: "draft"'),
                encoding="utf-8",
            )
            invalid_policies["unknown-top-level"][0].write_text(
                bundled_policy + '\nextra_contract: "unsupported"\n',
                encoding="utf-8",
            )
            invalid_policies["wrong-schema"][0].write_text(
                bundled_policy.replace("schema_version: 2", "schema_version: 1"),
                encoding="utf-8",
            )
            invalid_policies["invalid-enum"][0].write_text(
                bundled_policy.replace(
                    'truth_and_claims: "prohibit"',
                    'truth_and_claims: "bananas"',
                ),
                encoding="utf-8",
            )
            invalid_policies["invalid-id"][0].write_text(
                bundled_policy.replace(
                    '  truth_and_claims: "prohibit"\n',
                    '  Bad-Key: "prohibit"\n',
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

    def test_skipped_sources_fail_closed_even_when_owner_acknowledged(self) -> None:
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

            acknowledgements = [
                {
                    "path": item["file"],
                    "sha256": item["sha256"],
                    "size_bytes": item["size_bytes"],
                    "reason": (
                        "Repository owner reviewed this generated source "
                        "separately."
                    ),
                    "owner": "Repository owner",
                    "expires": ACTIVE_EXPIRY,
                }
                for item in advisory_payload["skipped_sources"]
            ]
            allowlist = project / "allow.json"
            allowlist.write_text(
                json.dumps({
                    "schema_version": 1,
                    "allow": [],
                    "acknowledge_skipped": acknowledgements,
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
                1,
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
            self.assertFalse(acknowledged_payload["ok"])
            self.assertFalse(acknowledged_payload["gate_passed"])
            self.assertFalse(acknowledged_payload["source_gate_passed"])
            self.assertEqual(
                set(acknowledged_payload["acknowledged_skipped_files"]),
                {"src/not-utf8.tsx", "src/oversized.css"},
            )
            self.assertEqual(
                acknowledged_payload[
                    "active_skipped_source_acknowledgements"
                ],
                acknowledgements,
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
                1,
                acknowledged_text.stdout + acknowledged_text.stderr,
            )
            self.assertIn("SKIP-ACK-ACTIVE", acknowledged_text.stdout)
            self.assertEqual(
                acknowledged_text.stdout.count("SKIPPED-ACKNOWLEDGED"),
                2,
            )

            expired_acknowledgements = [
                {**entry, "expires": "2000-01-01"}
                for entry in acknowledgements
            ]
            allowlist.write_text(
                json.dumps({
                    "schema_version": 1,
                    "allow": [],
                    "acknowledge_skipped": expired_acknowledgements,
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
                expired_acknowledgements,
            )
            self.assertEqual(
                set(expired_payload["unacknowledged_skipped_files"]),
                {"src/not-utf8.tsx", "src/oversized.css"},
            )


if __name__ == "__main__":
    unittest.main()
