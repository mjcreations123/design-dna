"""Exercise ordinary installed paths and exact parser dependency resolution."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SKILL = Path(__file__).resolve().parents[1]
REPO = SKILL.parents[1]
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "Node.js is required")
class RuntimePortabilityTests(unittest.TestCase):
    def test_commands_start_from_encoded_installation_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="dna portable ") as temporary:
            scripts = Path(temporary) / "skill space # % unicode-é" / "scripts"
            shutil.copytree(SKILL / "scripts", scripts)
            for name in (
                "check_style_provenance.mjs", "match_typeface.mjs",
                "check_signature_transfer.mjs", "extract_reference_styles.mjs",
                "compare_structure.mjs", "compare_mechanisms.mjs",
                "scan_build_components.mjs", "observe_reference.mjs",
                "record_reference.mjs",
            ):
                with self.subTest(command=name):
                    run = subprocess.run(
                        [NODE, str(scripts / name), "--help"], cwd=temporary,
                        text=True, encoding="utf-8", capture_output=True, timeout=30,
                    )
                    self.assertEqual(0, run.returncode, run.stdout + run.stderr)
                    self.assertIn(name, run.stdout)

    def test_installed_parser_uses_shared_exact_dependency_bundle(self) -> None:
        modules = REPO / "maintainer" / "node_modules"
        if not (modules / "@babel" / "parser" / "package.json").is_file():
            self.skipTest("Install pinned maintainer dependencies to exercise parser")
        with tempfile.TemporaryDirectory(prefix="dna parser ") as temporary:
            scripts = Path(temporary) / "installed # skill" / "scripts"
            shutil.copytree(SKILL / "scripts", scripts)
            env = os.environ.copy()
            env.pop("DESIGN_DNA_BABEL_PARSER_MODULE_DIR", None)
            env["DESIGN_DNA_PLAYWRIGHT_MODULE_DIR"] = str(modules)
            program = (
                "import {resolveBabelParser} from "
                + json.dumps((scripts / "babel_parser_resolver.mjs").as_uri())
                + "; const parser=resolveBabelParser(import.meta.url);"
                + "console.log(parser.parse('const p=<main/>;', {plugins:['jsx']}).type);"
            )
            run = subprocess.run(
                [NODE, "--input-type=module", "-e", program], cwd=temporary,
                env=env, text=True, encoding="utf-8", capture_output=True, timeout=30,
            )
            self.assertEqual(0, run.returncode, run.stdout + run.stderr)
            self.assertEqual("File", run.stdout.strip())
            env["DESIGN_DNA_BABEL_PARSER_MODULE_DIR"] = str(Path(temporary) / "missing" / "node_modules")
            refused = subprocess.run(
                [NODE, "--input-type=module", "-e", program], cwd=temporary,
                env=env, text=True, encoding="utf-8", capture_output=True, timeout=30,
            )
            self.assertNotEqual(0, refused.returncode)
            self.assertIn("babel-parser-unavailable", refused.stderr)

    def test_declared_and_installed_parser_versions_agree(self) -> None:
        declared = json.loads((REPO / "maintainer" / "package.json").read_text(encoding="utf-8"))
        lock = json.loads((REPO / "maintainer" / "package-lock.json").read_text(encoding="utf-8"))
        self.assertEqual("7.28.5", declared["devDependencies"]["@babel/parser"])
        self.assertEqual("7.28.5", lock["packages"]["node_modules/@babel/parser"]["version"])
        self.assertEqual(">=6.0.0", lock["packages"]["node_modules/@babel/parser"]["engines"]["node"])


if __name__ == "__main__":
    unittest.main()
