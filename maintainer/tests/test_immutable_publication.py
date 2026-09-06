"""Real create-only publication races; all payloads and child suites are synthetic."""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import common
import attest_tests
import test_release_proofs as fixtures


class ImmutablePublicationTests(unittest.TestCase):
    def test_success_is_exact_one_link_ordinary_json_without_temporary_residue(self):
        with tempfile.TemporaryDirectory(prefix="dna-immutable-") as temporary:
            destination = Path(temporary) / "nested/record.json"
            payload = {"writer": "synthetic-success", "value": [1, 2]}
            common.publish_new_json(destination, payload)
            self.assertEqual(payload, json.loads(destination.read_bytes()))
            self.assertTrue(stat.S_ISREG(destination.lstat().st_mode))
            self.assertEqual(1, destination.stat().st_nlink)
            self.assertEqual([], list(destination.parent.glob("*.unpublished.tmp")))

    def test_existing_target_is_untouched_and_validated_temporary_bytes_remain(self):
        with tempfile.TemporaryDirectory(prefix="dna-immutable-") as temporary:
            destination = Path(temporary) / "record.json"
            destination.write_bytes(b"pre-existing owner bytes\n")
            payload = {"writer": "losing-synthetic-publisher"}
            with self.assertRaises(common.ToolFailure) as caught:
                common.publish_new_json(destination, payload)
            self.assertEqual("immutable-publication-exists", caught.exception.issue.code)
            self.assertEqual(b"pre-existing owner bytes\n", destination.read_bytes())
            recovery = Path(caught.exception.recovery_path)
            self.assertEqual(destination.parent, recovery.parent)
            self.assertEqual(payload, json.loads(recovery.read_bytes()))
            self.assertEqual(1, recovery.stat().st_nlink)

    def test_real_attester_does_not_overwrite_a_target_created_during_its_suite(self):
        with tempfile.TemporaryDirectory(prefix="dna-late-attestation-") as temporary:
            plugin = fixtures.make_attestation_fixture(Path(temporary).resolve())
            destination = Path(temporary) / "test-attestation.json"
            diagnostic = Path(temporary) / "rejection.json"
            (plugin / "skills/design-dna/tests/test_late_target.py").write_text(
                "import os,unittest\nfrom pathlib import Path\n"
                "class LateTarget(unittest.TestCase):\n"
                " def test_actual_execution_creates_competing_output(self):\n"
                "  Path(os.environ['IMMUTABLE_TEST_OUTPUT']).write_bytes(b'competing owner bytes')\n",
                encoding="utf-8")
            result = subprocess.run([
                sys.executable, "-I", "-S", "-B",
                str(plugin / "maintainer/scripts/attest_tests.py"),
                "--plugin-root", str(plugin), "--output", str(destination),
                "--diagnostic-output", str(diagnostic),
            ], cwd=plugin, env=dict(os.environ, IMMUTABLE_TEST_OUTPUT=str(destination)),
                capture_output=True, timeout=45, check=False)
            self.assertEqual(2, result.returncode, result.stdout.decode(errors="replace"))
            self.assertEqual(b"competing owner bytes", destination.read_bytes())
            emitted = json.loads(result.stdout)
            self.assertEqual("immutable-publication-exists", emitted["failures"][0]["code"])
            self.assertFalse(json.loads(diagnostic.read_bytes())["release_eligible"])
            recovered = list(destination.parent.glob(".test-attestation.json.*.unpublished.tmp"))
            self.assertEqual(1, len(recovered))
            self.assertEqual("design-dna-test-attestation", json.loads(recovered[0].read_bytes())["record_type"])

    def test_two_real_concurrent_publishers_have_exactly_one_winner(self):
        with tempfile.TemporaryDirectory(prefix="dna-publication-race-") as temporary:
            directory = Path(temporary).resolve()
            destination = directory / "record.json"
            release = directory / "release.flag"
            source = (
                "import json,sys,time\nfrom pathlib import Path\n"
                "sys.path.insert(0,sys.argv[1])\nfrom common import publish_new_json,ToolFailure\n"
                "destination,release,ready=map(Path,sys.argv[2:5]); writer=sys.argv[5]\n"
                "ready.write_text('ready')\ndeadline=time.monotonic()+10\n"
                "while not release.exists():\n"
                " if time.monotonic()>deadline: raise RuntimeError('owned test gate timed out')\n"
                " time.sleep(0.01)\n"
                "try:\n publish_new_json(destination,{'writer':writer}); print(json.dumps({'ok':True,'writer':writer}))\n"
                "except ToolFailure as error:\n"
                " print(json.dumps({'ok':False,'writer':writer,'code':error.issue.code,'recovery':error.recovery_path})); sys.exit(2)\n"
            )
            processes = []
            try:
                for writer in ("one", "two"):
                    ready = directory / (writer + ".ready")
                    processes.append(subprocess.Popen([
                        sys.executable, "-I", "-B", "-c", source,
                        str(SCRIPTS), str(destination), str(release), str(ready), writer,
                    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE))
                deadline = time.monotonic() + 10
                while not all((directory / (writer + ".ready")).is_file() for writer in ("one", "two")):
                    self.assertLess(time.monotonic(), deadline)
                    time.sleep(0.01)
                release.write_text("release", encoding="utf-8")
                records = []
                for process in processes:
                    stdout, stderr = process.communicate(timeout=15)
                    self.assertIn(process.returncode, (0, 2), stderr.decode(errors="replace"))
                    records.append(json.loads(stdout))
                winners = [record for record in records if record["ok"]]
                losers = [record for record in records if not record["ok"]]
                self.assertEqual(1, len(winners))
                self.assertEqual(1, len(losers))
                self.assertEqual(winners[0]["writer"], json.loads(destination.read_bytes())["writer"])
                self.assertEqual("immutable-publication-exists", losers[0]["code"])
                self.assertEqual(losers[0]["writer"], json.loads(Path(losers[0]["recovery"]).read_bytes())["writer"])
                self.assertEqual(1, destination.stat().st_nlink)
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=5)

    def test_posix_link_primitive_never_replaces_an_existing_name(self):
        # On Windows this exercises the link algorithm on the local filesystem;
        # it does not claim native POSIX coverage, which remains a CI obligation.
        with tempfile.TemporaryDirectory(prefix="dna-link-publication-") as temporary:
            source, target = Path(temporary) / "source", Path(temporary) / "target"
            source.write_bytes(b"new")
            target.write_bytes(b"old")
            with patch.object(common.os, "name", "posix"):
                with self.assertRaises(FileExistsError):
                    common._publish_file_no_replace(source, target)
            self.assertEqual(b"old", target.read_bytes())
            self.assertEqual(b"new", source.read_bytes())

    def test_unsupported_no_replace_operation_retains_bytes_without_overwrite_fallback(self):
        with tempfile.TemporaryDirectory(prefix="dna-unsupported-publication-") as temporary:
            destination = Path(temporary) / "record.json"
            payload = {"recoverable": True}
            with patch.object(common, "_publish_file_no_replace", side_effect=OSError("no-replace unsupported")):
                with patch.object(common.os, "replace", side_effect=AssertionError("Overwrite fallback is forbidden")):
                    with self.assertRaises(common.ToolFailure) as caught:
                        common.publish_new_json(destination, payload)
            self.assertEqual("immutable-publication-failed", caught.exception.issue.code)
            self.assertFalse(destination.exists())
            recovery = Path(caught.exception.recovery_path)
            self.assertEqual(payload, json.loads(recovery.read_bytes()))

    def test_generic_mutable_writer_stays_mutable_but_all_immutable_clis_use_new_publisher(self):
        with tempfile.TemporaryDirectory(prefix="dna-mutable-writer-") as temporary:
            target = Path(temporary) / "journal.json"
            target.write_text('{"old": true}', encoding="utf-8")
            attest_tests.atomic_write_json(target, {"new": True})
            self.assertEqual({"new": True}, json.loads(target.read_bytes()))
        for name in ("attest_tests.py", "attest_codex_plugin.py", "attest_install_lifecycle.py", "attest_signatures.py"):
            with self.subTest(name=name):
                tree = ast.parse((SCRIPTS / name).read_text(encoding="utf-8"))
                main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
                calls = [node.func.id for node in ast.walk(main) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
                self.assertIn("publish_new_json", calls)
                self.assertNotIn("atomic_write_json", calls)


if __name__ == "__main__":
    unittest.main()
