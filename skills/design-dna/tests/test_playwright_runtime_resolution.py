from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
RESOLVER = SCRIPTS / "playwright_resolver.mjs"
PREFLIGHT = SCRIPTS / "browser_preflight.mjs"
NODE = shutil.which("node")


def write_fake_playwright(
    node_modules: Path,
    version: str,
    *,
    executable_path: str = "",
) -> None:
    package = node_modules / "playwright"
    package.mkdir(parents=True)
    (package / "package.json").write_text(
        json.dumps(
            {
                "name": "playwright",
                "version": version,
                "main": "index.js",
            }
        ),
        encoding="utf-8",
    )
    (package / "index.js").write_text(
        "module.exports = { chromium: { executablePath: () => "
        + json.dumps(executable_path)
        + ", launch: async () => { throw new Error('not launched'); } } };\n",
        encoding="utf-8",
    )


def install_shaped_scripts(root: Path) -> Path:
    scripts = root / "home" / ".agents" / "skills" / "design-dna" / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(RESOLVER, scripts / RESOLVER.name)
    shutil.copy2(PREFLIGHT, scripts / PREFLIGHT.name)
    return scripts / PREFLIGHT.name


def source_package_shaped_resolver(root: Path) -> Path:
    scripts = root / "package" / "skills" / "design-dna" / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(RESOLVER, scripts / RESOLVER.name)
    maintainer = root / "package" / "maintainer"
    maintainer.mkdir()
    (maintainer / "package-lock.json").write_text("{}\n", encoding="utf-8")
    return scripts / RESOLVER.name


def run_preflight(script: Path, project: Path, *arguments: str, environment: dict[str, str] | None = None) -> tuple[int, dict[str, object]]:
    assert NODE is not None
    child_environment = os.environ.copy()
    child_environment.pop("DESIGN_DNA_PLAYWRIGHT_MODULE_DIR", None)
    child_environment.pop("NODE_PATH", None)
    child_environment.update(environment or {})
    completed = subprocess.run(
        [NODE, str(script), *arguments],
        cwd=project,
        env=child_environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=False,
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise AssertionError(
            f"Expected one JSON response, got stdout={completed.stdout!r}, stderr={completed.stderr!r}"
        )
    return completed.returncode, json.loads(lines[0])


@unittest.skipIf(NODE is None, "node is required")
class PlaywrightRuntimeResolutionTests(unittest.TestCase):
    def test_installed_shaped_skill_discovers_project_local_playwright(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-project-local-") as temporary:
            root = Path(temporary)
            preflight = install_shaped_scripts(root)
            project = root / "project"
            project.mkdir()
            write_fake_playwright(project / "node_modules", "project-local-1")

            code, payload = run_preflight(
                preflight,
                project,
                "--browser-executable",
                str(Path(sys.executable).resolve()),
            )

        self.assertEqual(0, code, payload)
        self.assertTrue(payload["ok"])
        self.assertEqual("project-local-node-modules", payload["playwright"]["source"])
        self.assertEqual("project-local-1", payload["playwright"]["version"])
        self.assertEqual(str(project.resolve()), payload["project_root"])

    def test_explicit_module_directory_wins_over_project_local_module(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-explicit-module-") as temporary:
            root = Path(temporary)
            preflight = install_shaped_scripts(root)
            project = root / "project"
            project.mkdir()
            write_fake_playwright(project / "node_modules", "project-local-1")
            explicit_modules = root / "explicit" / "node_modules"
            write_fake_playwright(explicit_modules, "explicit-1")

            code, payload = run_preflight(
                preflight,
                project,
                "--browser-executable",
                str(Path(sys.executable).resolve()),
                environment={"DESIGN_DNA_PLAYWRIGHT_MODULE_DIR": str(explicit_modules.resolve())},
            )

        self.assertEqual(0, code, payload)
        self.assertEqual("environment-module-directory", payload["playwright"]["source"])
        self.assertEqual("explicit-1", payload["playwright"]["version"])

    def test_project_local_module_uses_its_existing_bundled_executable_without_a_flag(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-automatic-browser-") as temporary:
            root = Path(temporary)
            preflight = install_shaped_scripts(root)
            project = root / "project"
            project.mkdir()
            write_fake_playwright(
                project / "node_modules",
                "project-local-1",
                executable_path=str(Path(sys.executable).resolve()),
            )

            code, payload = run_preflight(preflight, project)

        self.assertEqual(0, code, payload)
        self.assertEqual("project-local-node-modules", payload["playwright"]["source"])
        self.assertEqual("playwright", payload["browser"]["source"])
        self.assertEqual(
            hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
            payload["browser"]["sha256"],
        )

    def test_invalid_explicit_module_directory_is_not_bypassed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-invalid-explicit-") as temporary:
            root = Path(temporary)
            preflight = install_shaped_scripts(root)
            project = root / "project"
            project.mkdir()
            write_fake_playwright(project / "node_modules", "project-local-1")
            missing = root / "missing-node-modules"

            code, payload = run_preflight(
                preflight,
                project,
                "--browser-executable",
                str(Path(sys.executable).resolve()),
                environment={"DESIGN_DNA_PLAYWRIGHT_MODULE_DIR": str(missing.resolve())},
            )

        self.assertEqual(3, code, payload)
        self.assertFalse(payload["ok"])
        self.assertEqual("playwright-module-directory-invalid", payload["error"]["code"])

    def test_blank_explicit_module_directory_is_not_ignored(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-blank-explicit-") as temporary:
            root = Path(temporary)
            preflight = install_shaped_scripts(root)
            project = root / "project"
            project.mkdir()
            write_fake_playwright(project / "node_modules", "project-local-1")

            code, payload = run_preflight(
                preflight,
                project,
                "--browser-executable",
                str(Path(sys.executable).resolve()),
                environment={"DESIGN_DNA_PLAYWRIGHT_MODULE_DIR": ""},
            )

        self.assertEqual(3, code, payload)
        self.assertFalse(payload["ok"])
        self.assertEqual("playwright-module-directory-invalid", payload["error"]["code"])

    def test_browser_executable_alone_cannot_bypass_missing_playwright(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-no-module-") as temporary:
            root = Path(temporary)
            preflight = install_shaped_scripts(root)
            project = root / "project"
            project.mkdir()

            code, payload = run_preflight(
                preflight,
                project,
                "--browser-executable",
                str(Path(sys.executable).resolve()),
            )

        self.assertEqual(3, code, payload)
        self.assertFalse(payload["ok"])
        self.assertEqual("playwright-unavailable", payload["error"]["code"])

    def test_node_path_is_not_treated_as_a_global_module_discovery_route(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-no-global-module-") as temporary:
            root = Path(temporary)
            preflight = install_shaped_scripts(root)
            project = root / "project"
            project.mkdir()
            global_modules = root / "ambient" / "node_modules"
            write_fake_playwright(global_modules, "ambient-should-not-load")

            code, payload = run_preflight(
                preflight,
                project,
                "--browser-executable",
                str(Path(sys.executable).resolve()),
                environment={"NODE_PATH": str(global_modules.resolve())},
            )

        self.assertEqual(3, code, payload)
        self.assertFalse(payload["ok"])
        self.assertEqual("playwright-unavailable", payload["error"]["code"])

    def test_source_checkout_uses_only_its_recognized_maintainer_modules(self) -> None:
        with tempfile.TemporaryDirectory(prefix="design-dna-source-package-") as temporary:
            root = Path(temporary)
            resolver = source_package_shaped_resolver(root)
            project = root / "project"
            project.mkdir()
            write_fake_playwright(
                root / "package" / "maintainer" / "node_modules",
                "source-package-1",
            )
            program = (
                "import { resolvePlaywright } from "
                + json.dumps(resolver.as_uri())
                + "; const value = resolvePlaywright(); "
                + "process.stdout.write(JSON.stringify({source:value.source,version:value.dependency.version}));"
            )
            child_environment = os.environ.copy()
            child_environment.pop("DESIGN_DNA_PLAYWRIGHT_MODULE_DIR", None)
            child_environment.pop("NODE_PATH", None)
            completed = subprocess.run(
                [NODE, "--input-type=module", "--eval", program],
                cwd=project,
                env=child_environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="strict",
                check=False,
            )

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(
            {
                "source": "source-package-maintainer-node-modules",
                "version": "source-package-1",
            },
            json.loads(completed.stdout),
        )

    def test_all_browser_runtime_loaders_use_the_shared_resolver(self) -> None:
        loaders = [
            "record_reference.mjs",
            "observe_reference.mjs",
            "extract_reference_styles.mjs",
            "match_typeface.mjs",
            "scan_build_components.mjs",
            "compare_structure.mjs",
            "compare_mechanisms.mjs",
            "rendered_review.mjs",
            "compare_render_reviews.mjs",
        ]
        for name in loaders:
            with self.subTest(loader=name):
                source = (SCRIPTS / name).read_text(encoding="utf-8")
                self.assertIn('from "./playwright_resolver.mjs"', source)
                self.assertIn("resolvePlaywright", source)
                self.assertIn("discoverBrowserExecutable", source)
                self.assertIn("browserExecutableIdentity", source)
                self.assertNotIn("createRequire", source)
                self.assertNotIn("chromium.executablePath()", source)


if __name__ == "__main__":
    unittest.main()
