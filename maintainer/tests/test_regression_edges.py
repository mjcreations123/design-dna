from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[2]
MAINTAINER_SCRIPTS = PLUGIN / "maintainer" / "scripts"
RUNTIME_SCRIPTS = PLUGIN / "skills" / "design-dna" / "scripts"


def run_path(script: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(script), *arguments],
        text=True,
        encoding="utf-8",
        capture_output=True,
        env=environment,
        timeout=120,
    )


class ScannerRegressionTests(unittest.TestCase):
    def test_single_fragment_and_font_family_name_are_neutral(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "style.css").write_text(
                "/* .tagline span:nth-child(2) { color: red; } */\n"
                ".hero-poster span:nth-child(2) { color: #fff; }\n",
                encoding="utf-8",
            )
            (project / "tailwind.config.js").write_text(
                "export default { theme: { fontFamily: { sans: ['Inter', "
                "'sans-serif'] } } };\n",
                encoding="utf-8",
            )
            result = run_path(
                RUNTIME_SCRIPTS / "scan_project.py",
                str(project),
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            rules = {item["rule"] for item in payload["findings"]}
            self.assertNotIn("decorative-display-fragment", rules)
            self.assertNotIn("unexamined-default-font", rules)
            self.assertTrue(
                any(
                    item["check"] == "prominent-fragment-selector-context"
                    for item in payload["manual_review"]
                )
            )

    def test_expired_allowlist_is_reported_and_does_not_suppress(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.html").write_text(
                "<p>Trusted by thousands.</p>",
                encoding="utf-8",
            )
            initial = run_path(
                RUNTIME_SCRIPTS / "scan_project.py",
                str(project),
                "--json",
            )
            self.assertEqual(
                initial.returncode,
                0,
                initial.stdout + initial.stderr,
            )
            claim_finding = next(
                item
                for item in json.loads(initial.stdout)["findings"]
                if item["rule"] == "claim-needs-provenance"
            )
            allowlist = project / "allow.json"
            allowlist.write_text(
                json.dumps({
                    "schema_version": 1,
                    "allow": [{
                        "rule": "claim-needs-provenance",
                        "path": "page.html",
                        "fingerprint": claim_finding["fingerprint"],
                        "reason": "Previously approved sourced claim.",
                        "owner": "Content owner",
                        "expires": "2000-01-01",
                    }],
                }),
                encoding="utf-8",
            )
            result = run_path(
                RUNTIME_SCRIPTS / "scan_project.py",
                str(project),
                "--allowlist",
                str(allowlist),
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(len(payload["expired_allowlist_entries"]), 1)
            self.assertTrue(
                any(
                    item["rule"] == "claim-needs-provenance"
                    for item in payload["findings"]
                )
            )


class ProjectStateRegressionTests(unittest.TestCase):
    def test_incremental_initialization_unions_records_and_preserves_existing_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            first = run_path(
                RUNTIME_SCRIPTS / "init_project_state.py",
                "--project",
                str(project),
                "--json",
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            direction = project / ".design-dna" / "direction.md"
            original = direction.read_text(encoding="utf-8") + "\nOwner note.\n"
            direction.write_text(original, encoding="utf-8")
            second = run_path(
                RUNTIME_SCRIPTS / "init_project_state.py",
                "--project",
                str(project),
                "--record",
                "assets",
                "--json",
            )
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            state = json.loads(
                (project / ".design-dna" / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                state["records"],
                ["direction", "visual-review", "assets"],
            )
            self.assertEqual(direction.read_text(encoding="utf-8"), original)
            self.assertTrue((project / ".design-dna" / "assets.yml").is_file())

    def test_force_refresh_keeps_recoverable_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            initial = run_path(
                RUNTIME_SCRIPTS / "init_project_state.py",
                "--project",
                str(project),
                "--json",
            )
            self.assertEqual(initial.returncode, 0, initial.stdout + initial.stderr)
            direction = project / ".design-dna" / "direction.md"
            direction.write_text(
                direction.read_text(encoding="utf-8") + "\nRecover this note.\n",
                encoding="utf-8",
            )
            refreshed = run_path(
                RUNTIME_SCRIPTS / "init_project_state.py",
                "--project",
                str(project),
                "--force",
                "--json",
            )
            self.assertEqual(
                refreshed.returncode,
                0,
                refreshed.stdout + refreshed.stderr,
            )
            backups = list(project.glob(".design-dna.backup-*"))
            self.assertEqual(len(backups), 1)
            self.assertIn(
                "Recover this note.",
                (backups[0] / "direction.md").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "# BEGIN DESIGN DNA RECOVERY PRIVACY GUARD",
                (backups[0] / ".gitignore").read_text(encoding="utf-8"),
            )
            self.assertNotIn(
                "Recover this note.",
                direction.read_text(encoding="utf-8"),
            )


class MaintainerBoundaryTests(unittest.TestCase):
    def test_all_version_schemas_use_strict_semver_prerelease_rules(self) -> None:
        schemas = PLUGIN / "maintainer" / "schemas"
        records = [
            (
                schemas / "compatibility.schema.json",
                lambda value: value["$defs"]["semver"]["pattern"],
                "",
            ),
            (
                schemas / "design-review.schema.json",
                lambda value: value["properties"]["build"]["properties"][
                    "skill_version"
                ]["pattern"],
                "",
            ),
            (
                schemas / "eval-result.schema.json",
                lambda value: value["properties"]["package"]["properties"]["version"][
                    "pattern"
                ],
                "",
            ),
            (
                schemas / "manifest.schema.json",
                lambda value: value["properties"]["version"]["pattern"],
                "",
            ),
            (
                schemas / "plugin.schema.json",
                lambda value: value["properties"]["version"]["pattern"],
                "",
            ),
            (
                schemas / "project-state.schema.json",
                lambda value: value["properties"]["created_with"]["pattern"],
                "design-dna ",
            ),
            (
                schemas / "release.schema.json",
                lambda value: value["properties"]["version"]["pattern"],
                "",
            ),
        ]
        for path, selector, prefix in records:
            with self.subTest(schema=path.name):
                payload = json.loads(path.read_text(encoding="utf-8"))
                pattern = selector(payload)
                self.assertIsNone(re.fullmatch(pattern, prefix + "2.0.0-01"))
                self.assertIsNotNone(re.fullmatch(pattern, prefix + "2.0.0-01a"))

    def test_link_checker_catches_html_srcset_and_unsafe_scheme(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "present.png").write_bytes(b"png")
            (root / "index.html").write_text(
                '<a href="missing.html">Missing</a>'
                '<img srcset="present.png 1x, missing-2x.png 2x" alt="">'
                '<a href="javascript:alert(1)">Unsafe</a>',
                encoding="utf-8",
            )
            result = run_path(
                MAINTAINER_SCRIPTS / "check_links.py",
                str(root),
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            codes = {
                item["code"] for item in json.loads(result.stdout)["failures"]
            }
            self.assertIn("missing-link", codes)
            self.assertIn("missing-image", codes)
            self.assertIn("unsafe-link-scheme", codes)

    def test_route_detector_finds_design_dna_in_a_renamed_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical = root / "canonical"
            discovery = root / "skills"
            expected = discovery / "design-dna"
            renamed = discovery / "friendly-name"
            canonical.mkdir()
            expected.mkdir(parents=True)
            renamed.mkdir(parents=True)
            skill = (
                "---\nname: design-dna\n"
                "description: Test Design DNA route.\n---\n\n# Test\n"
            )
            (canonical / "SKILL.md").write_text(skill, encoding="utf-8")
            (expected / "SKILL.md").write_text(skill, encoding="utf-8")
            (renamed / "SKILL.md").write_text(skill, encoding="utf-8")
            result = run_path(
                MAINTAINER_SCRIPTS / "detect_routes.py",
                "--canonical",
                str(canonical),
                "--root",
                str(discovery),
                "--expected",
                str(expected),
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(
                any(
                    item["code"] == "unexpected-discovery-candidate"
                    and Path(item["path"]) == renamed
                    for item in payload["failures"]
                )
            )


if __name__ == "__main__":
    unittest.main()
