from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PLUGIN = Path(__file__).resolve().parents[2]
SCRIPTS = PLUGIN / "maintainer" / "scripts"


def run_script(name: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name), *arguments],
        text=True,
        encoding="utf-8",
        capture_output=True,
        env=environment,
        timeout=120,
    )


def write_skill(path: Path, marker: str = "current") -> None:
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text(
        "---\n"
        "name: design-dna\n"
        "description: Test Design DNA route.\n"
        "---\n\n"
        f"# Design DNA\n\n{marker}\n",
        encoding="utf-8",
    )


def create_directory_alias(target: Path, alias: Path) -> None:
    """Create a directory alias without silently skipping the reparse test."""
    try:
        os.symlink(target, alias, target_is_directory=True)
        return
    except (OSError, NotImplementedError) as symlink_error:
        if os.name != "nt":
            raise AssertionError(
                f"directory symlink creation failed: {symlink_error}"
            ) from symlink_error

    junction = subprocess.run(
        [
            "cmd.exe",
            "/d",
            "/c",
            "mklink",
            "/J",
            str(alias),
            str(target),
        ],
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=30,
    )
    if junction.returncode != 0 or not alias.is_dir():
        raise AssertionError(
            "directory alias creation failed via both symlink and junction: "
            f"{junction.stdout}{junction.stderr}"
        )


class RouteIntegrityTests(unittest.TestCase):
    def test_detector_discovery_scan_has_a_fail_closed_entry_bound(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        try:
            import detect_routes
        finally:
            sys.path.pop(0)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "skills"
            root.mkdir()
            for name in ("one.txt", "two.txt", "three.txt"):
                (root / name).write_text(name, encoding="utf-8")
            with mock.patch.object(detect_routes, "MAX_DISCOVERY_ENTRIES", 2):
                with self.assertRaises(detect_routes.ToolFailure) as caught:
                    detect_routes.discover(root)
            self.assertEqual(
                "discovery-limit-exceeded",
                caught.exception.issue.code,
            )

    def test_detector_requires_explicit_roots_and_expected_routes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            canonical = Path(temporary) / "canonical"
            write_skill(canonical)
            no_roots = run_script(
                "detect_routes.py",
                "--canonical",
                str(canonical),
            )
            self.assertEqual(no_roots.returncode, 2)
            self.assertEqual(
                json.loads(no_roots.stdout)["failures"][0]["code"],
                "discovery-roots-required",
            )

            discovery = Path(temporary) / "skills"
            discovery.mkdir()
            no_expected = run_script(
                "detect_routes.py",
                "--canonical",
                str(canonical),
                "--root",
                str(discovery),
            )
            self.assertEqual(no_expected.returncode, 2)
            self.assertEqual(
                json.loads(no_expected.stdout)["failures"][0]["code"],
                "expected-routes-required",
            )

    def test_detector_requires_exactly_one_current_route_per_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical = root / "canonical"
            discovery = root / "skills"
            expected = discovery / "design-dna"
            renamed = discovery / "friendly-name"
            write_skill(canonical)
            write_skill(expected)
            write_skill(renamed)
            result = run_script(
                "detect_routes.py",
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

    def test_absent_optional_discovery_root_is_recorded_not_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical = root / "canonical"
            discovery = root / "skills"
            absent_cache = root / "plugins" / "cache"
            expected = discovery / "design-dna"
            write_skill(canonical)
            write_skill(expected)
            result = run_script(
                "detect_routes.py",
                "--canonical",
                str(canonical),
                "--root",
                str(discovery),
                "--root",
                str(absent_cache),
                "--expected",
                str(expected),
            )
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )
            payload = json.loads(result.stdout)
            self.assertEqual(payload["failures"], [])
            self.assertEqual(
                "not-verified",
                payload["scan_scope"]["activation_state"],
            )
            self.assertEqual(
                "not-inspected",
                payload["scan_scope"]["project_admin_session_routes"],
            )
            self.assertIn(
                "optional-discovery-root-absent",
                {item["code"] for item in payload["warnings"]},
            )

    def test_detector_fails_closed_on_malformed_or_duplicate_frontmatter(self) -> None:
        invalid_documents = {
            "malformed": (
                "---\n"
                "name: [design-dna\n"
                "description: Broken YAML.\n"
                "---\n"
            ),
            "duplicate": (
                "---\n"
                "name: unrelated-skill\n"
                "name: design-dna\n"
                "description: Duplicate identity.\n"
                "---\n"
            ),
            "unclosed": (
                "---\n"
                "name: design-dna\n"
                "description: Missing closing delimiter.\n"
            ),
        }
        for label, document in invalid_documents.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                canonical = root / "canonical"
                discovery = root / "skills"
                expected = discovery / "design-dna"
                suspect = discovery / "suspect"
                write_skill(canonical)
                write_skill(expected)
                suspect.mkdir(parents=True)
                (suspect / "SKILL.md").write_text(document, encoding="utf-8")
                result = run_script(
                    "detect_routes.py",
                    "--canonical",
                    str(canonical),
                    "--root",
                    str(discovery),
                    "--expected",
                    str(expected),
                )
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertEqual(
                    json.loads(result.stdout)["failures"][0]["code"],
                    "invalid-skill-frontmatter",
                )

    def test_detector_warns_on_an_invalid_unrelated_skill(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical = root / "canonical"
            discovery = root / "skills"
            expected = discovery / "design-dna"
            unrelated = discovery / "web-3d"
            write_skill(canonical)
            write_skill(expected)
            unrelated.mkdir(parents=True)
            (unrelated / "SKILL.md").write_text(
                "---\n"
                "name: web-3d\n"
                "description: Add 3D to a website: product views.\n"
                "---\n",
                encoding="utf-8",
            )
            result = run_script(
                "detect_routes.py",
                "--canonical",
                str(canonical),
                "--root",
                str(discovery),
                "--expected",
                str(expected),
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["failures"], [])
            self.assertIn(
                "unrelated-invalid-skill-entry",
                {item["code"] for item in payload["warnings"]},
            )

    def test_detector_requires_an_exact_string_scalar_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical = root / "canonical"
            discovery = root / "skills"
            expected = discovery / "design-dna"
            write_skill(canonical)
            write_skill(expected)
            entry = expected / "SKILL.md"
            entry.write_text(
                entry.read_text(encoding="utf-8").replace(
                    "name: design-dna",
                    "name: Design-DNA",
                    1,
                ),
                encoding="utf-8",
            )
            result = run_script(
                "detect_routes.py",
                "--canonical",
                str(canonical),
                "--root",
                str(discovery),
                "--expected",
                str(expected),
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn(
                "expected-route-missing",
                {
                    item["code"]
                    for item in json.loads(result.stdout)["failures"]
                },
            )

            entry.write_text(
                "---\n"
                "name:\n"
                "  - design-dna\n"
                "description: Non-scalar identity.\n"
                "---\n",
                encoding="utf-8",
            )
            result = run_script(
                "detect_routes.py",
                "--canonical",
                str(canonical),
                "--root",
                str(discovery),
                "--expected",
                str(expected),
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertEqual(
                json.loads(result.stdout)["failures"][0]["code"],
                "invalid-skill-name",
            )

    def test_detector_validates_canonical_skill_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical = root / "canonical"
            discovery = root / "skills"
            expected = discovery / "design-dna"
            write_skill(canonical)
            write_skill(expected)
            canonical_entry = canonical / "SKILL.md"
            canonical_entry.write_text(
                canonical_entry.read_text(encoding="utf-8").replace(
                    "name: design-dna",
                    "name: another-skill",
                    1,
                ),
                encoding="utf-8",
            )
            result = run_script(
                "detect_routes.py",
                "--canonical",
                str(canonical),
                "--root",
                str(discovery),
                "--expected",
                str(expected),
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertEqual(
                json.loads(result.stdout)["failures"][0]["code"],
                "canonical-skill-identity-invalid",
            )

    def test_canonical_inside_discovery_is_unexpected_unless_declared_expected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            discovery = root / "skills"
            canonical = discovery / "canonical-copy"
            expected = discovery / "design-dna"
            write_skill(canonical)
            write_skill(expected)
            result = run_script(
                "detect_routes.py",
                "--canonical",
                str(canonical),
                "--root",
                str(discovery),
                "--expected",
                str(expected),
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertTrue(
                any(
                    item["code"] == "unexpected-discovery-candidate"
                    and Path(item["path"]) == canonical
                    for item in json.loads(result.stdout)["failures"]
                )
            )

            sole_discovery = root / "sole-skills"
            expected_canonical = sole_discovery / "design-dna"
            write_skill(expected_canonical)
            result = run_script(
                "detect_routes.py",
                "--canonical",
                str(expected_canonical),
                "--root",
                str(sole_discovery),
                "--expected",
                str(expected_canonical),
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_sync_refuses_a_sibling_route_without_changing_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            discovery = root / "skills"
            target = discovery / "design-dna"
            duplicate = discovery / "old-copy"
            backups = root / "backups"
            write_skill(source, "new")
            write_skill(target, "old")
            write_skill(duplicate, "duplicate")
            backups.mkdir()

            result = run_script(
                "sync_skill.py",
                "--source",
                str(source),
                "--target",
                str(target),
                "--discovery-root",
                str(discovery),
                "--backup-root",
                str(backups),
                "--replace",
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertEqual(
                json.loads(result.stdout)["failures"][0]["code"],
                "discovery-candidate-collision",
            )
            self.assertIn(
                "old",
                (target / "SKILL.md").read_text(encoding="utf-8"),
            )
            self.assertEqual(list(backups.iterdir()), [])

    def test_detector_skips_only_in_root_alias_whose_target_is_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical = root / "canonical"
            discovery = root / "skills"
            expected = discovery / "design-dna"
            version = discovery / "vendor" / "1.0.0"
            alias = discovery / "vendor" / "latest"
            write_skill(canonical)
            write_skill(expected)
            version.mkdir(parents=True)
            (version / "SKILL.md").write_text(
                "---\nname: unrelated-skill\n"
                "description: An unrelated cached plugin skill.\n---\n",
                encoding="utf-8",
            )
            create_directory_alias(version, alias)

            result = run_script(
                "detect_routes.py",
                "--canonical",
                str(canonical),
                "--root",
                str(discovery),
                "--expected",
                str(expected),
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(
                any(
                    item["code"] == "reparse-alias-skipped"
                    and Path(item["path"]) == alias
                    for item in payload["warnings"]
                )
            )


if __name__ == "__main__":
    unittest.main()
