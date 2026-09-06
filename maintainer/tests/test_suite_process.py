"""Real bounded timeout, inherited-handle cleanup, and private diagnostic capture."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import attest_tests
import suite_process
import run_evals


class SuiteProcessTests(unittest.TestCase):
    def cleanup_diagnostic(self, diagnostic):
        directory = Path(diagnostic["path"]).parent.resolve()
        self.assertEqual(Path(tempfile.gettempdir()).resolve(), directory.parent)
        self.assertTrue(directory.name.startswith("design-dna-test-run-"))
        for name in ("diagnostic.json", "stdout.raw.log", "stderr.raw.log", "stdout.redacted.log", "stderr.redacted.log"):
            (directory / name).unlink(missing_ok=True)
        directory.rmdir()

    def run_child(self, plugin, source, timeout=2):
        return suite_process.run_spooled_suite([sys.executable, "-I", "-S", "-B", "-c", source], cwd=plugin,
            environment=attest_tests.isolated_subprocess_environment(), timeout=timeout,
            redact=lambda value: attest_tests.redact_known_local_paths(value, plugin), announce=False)

    def test_normal_complete_streams_are_unchanged(self):
        with tempfile.TemporaryDirectory(prefix="dna-suite-complete-") as temporary:
            result = self.run_child(Path(temporary).resolve(), "import sys; sys.stdout.buffer.write(b'exact-out\\n'); sys.stderr.buffer.write(b'exact-err\\n')")
            self.assertEqual(0, result.returncode)
            self.assertEqual(b"exact-out\n", result.stdout)
            self.assertEqual(b"exact-err\n", result.stderr)

    def test_timeout_retains_redacted_partial_output_without_promoting_prior_ok_summary(self):
        with tempfile.TemporaryDirectory(prefix="dna-suite-timeout-") as temporary:
            plugin = Path(temporary).resolve()
            source = "import os,sys,time; print(os.getcwd(),flush=True); print('Ran 999 tests in 0.1s\\n\\nOK',flush=True); print('original partial stderr',file=sys.stderr,flush=True); time.sleep(5)"
            with self.assertRaises(suite_process.SuiteRunUnavailable) as caught:
                self.run_child(plugin, source, timeout=0.5)
            diagnostic = caught.exception.diagnostic
            self.addCleanup(self.cleanup_diagnostic, diagnostic)
            file = Path(diagnostic["path"])
            self.assertEqual(diagnostic["sha256"], hashlib.sha256(file.read_bytes()).hexdigest())
            record = json.loads(file.read_text())
            self.assertEqual("timed-out", record["status"])
            self.assertFalse(record["suite_complete"])
            self.assertFalse(record["release_eligible"])
            self.assertIsNone(record["tests_run"])
            out = (file.parent / record["output"]["stdout"]["path"]).read_text()
            err = (file.parent / record["output"]["stderr"]["path"]).read_text()
            self.assertIn("<PLUGIN_ROOT>", out)
            self.assertNotIn(str(plugin), out + err)
            self.assertIn("Ran 999 tests", out)
            self.assertIn("original partial stderr", err)
            self.assertFalse((plugin / "maintainer/attestations/test-attestation.json").exists())

    def test_owned_descendant_cannot_hold_capture_open_past_timeout(self):
        with tempfile.TemporaryDirectory(prefix="dna-suite-descendant-") as temporary:
            plugin = Path(temporary).resolve()
            marker = plugin / "owned-descendant-ticks.txt"
            descendant = "import time; from pathlib import Path; p=Path(" + repr(str(marker)) + "); " + "\nfor i in range(200):\n p.write_text(str(i)); time.sleep(0.05)\n"
            source = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-I','-S','-B','-c'," + repr(descendant) + "]); print('owned descendant launched',flush=True); time.sleep(10)"
            started = time.monotonic()
            with self.assertRaises(suite_process.SuiteRunUnavailable) as caught:
                self.run_child(plugin, source, timeout=0.8)
            elapsed = time.monotonic() - started
            self.addCleanup(self.cleanup_diagnostic, caught.exception.diagnostic)
            self.assertLess(elapsed, 5, "Inherited output handles must not extend capture to the descendant's ten-second lifetime.")
            self.assertTrue(marker.is_file(), "The real descendant must have executed before cleanup was tested.")
            before = marker.read_text()
            time.sleep(0.2)
            self.assertEqual(before, marker.read_text())
            record = json.loads(Path(caught.exception.diagnostic["path"]).read_text())
            self.assertTrue(record["cleanup"]["attempted"])
            self.assertTrue(record["cleanup"]["verified"])

    def test_platform_containment_exists_before_the_driver_is_released(self):
        with tempfile.TemporaryDirectory(prefix="dna-suite-containment-") as temporary:
            plugin = Path(temporary).resolve()
            if os.name == "nt":
                marker = plugin / "must-not-run.txt"
                source = "from pathlib import Path; Path(" + repr(str(marker)) + ").write_text('unowned driver executed')"
                with patch.object(suite_process._WindowsProcessJob, "assign", side_effect=OSError("injected assignment failure")):
                    with self.assertRaises(suite_process.SuiteRunUnavailable) as caught:
                        self.run_child(plugin, source)
                self.addCleanup(self.cleanup_diagnostic, caught.exception.diagnostic)
                self.assertFalse(marker.exists())
                record = json.loads(Path(caught.exception.diagnostic["path"]).read_text())
                self.assertEqual("unreleased-supervisor", record["cleanup"]["boundary"])
                self.assertTrue(record["cleanup"]["verified"])
                self.assertIn("injected assignment failure", record["reason"])
            else:
                with patch.object(suite_process, "_WindowsProcessJob", side_effect=AssertionError("POSIX must not construct a Windows job")):
                    result = self.run_child(plugin, "import os; print(os.getpid()==os.getpgrp())")
                self.assertEqual(0, result.returncode)
                self.assertEqual(b"True\n", result.stdout)

    def test_parent_exit_does_not_leave_an_owned_descendant_writing(self):
        with tempfile.TemporaryDirectory(prefix="dna-suite-parent-exit-") as temporary:
            plugin = Path(temporary).resolve()
            marker = plugin / "descendant-after-parent.txt"
            descendant = "import time; from pathlib import Path; p=Path(" + repr(str(marker)) + "); " + "\nfor i in range(200):\n p.write_text(str(i)); time.sleep(0.05)\n"
            source = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-I','-S','-B','-c'," + repr(descendant) + "]); time.sleep(0.2); print('parent exited before descendant',flush=True)"
            started = time.monotonic()
            result = self.run_child(plugin, source, timeout=5)
            self.assertEqual(0, result.returncode)
            self.assertIn(b"parent exited before descendant", result.stdout)
            self.assertLess(time.monotonic() - started, 7)
            self.assertTrue(marker.is_file())
            before = marker.read_text()
            time.sleep(0.2)
            self.assertEqual(before, marker.read_text(), "Owned descendants must cease writing before a completed result returns.")

    def test_fast_completed_output_cannot_bypass_the_spool_bound(self):
        with tempfile.TemporaryDirectory(prefix="dna-suite-output-bound-") as temporary:
            with patch.object(suite_process, "MAX_SPOOLED_OUTPUT_BYTES", 1024):
                with self.assertRaises(suite_process.SuiteRunUnavailable) as caught:
                    self.run_child(Path(temporary).resolve(), "print('x'*4096)")
            self.addCleanup(self.cleanup_diagnostic, caught.exception.diagnostic)
            record = json.loads(Path(caught.exception.diagnostic["path"]).read_text())
            self.assertEqual("output-limit", record["status"])
            self.assertFalse(record["release_eligible"])
            self.assertGreater(record["output"]["stdout"]["bytes"], 1024)

    def test_posix_cleanup_checks_group_even_when_parent_already_exited(self):
        # Control-flow regression only on Windows; native POSIX execution is
        # separately exercised by the parent-exit test on the CI matrix.
        class ExitedParent:
            pid = 987654
            def poll(self): return 0
            def wait(self, timeout=None): return 0
        with patch.object(run_evals.os, "name", "posix"), patch.object(run_evals.signal, "SIGKILL", 9, create=True):
            with patch.object(run_evals.os, "killpg", side_effect=[None, None, ProcessLookupError()], create=True) as kill:
                with patch.object(run_evals.time, "sleep"):
                    evidence = run_evals.terminate_process_tree(ExitedParent())
        self.assertTrue(evidence["root_already_exited"])
        self.assertTrue(evidence["verified_empty"])
        self.assertEqual([(987654, 9), (987654, 0), (987654, 0)], [call.args for call in kill.call_args_list])

    def test_posix_unverified_group_never_claims_empty_from_parent_exit(self):
        class ExitedParent:
            pid = 987654
            def poll(self): return 0
            def wait(self, timeout=None): return 0
        with patch.object(run_evals.os, "name", "posix"), patch.object(run_evals.signal, "SIGKILL", 9, create=True):
            with patch.object(run_evals.os, "killpg", return_value=None, create=True):
                with patch.object(run_evals.time, "monotonic", side_effect=[0, 10]):
                    with self.assertRaises(run_evals.ToolFailure) as caught:
                        run_evals.terminate_process_tree(ExitedParent())
        self.assertEqual("process-tree-termination-failed", caught.exception.issue.code)
        self.assertIn('"verified_empty": false', caught.exception.issue.message)

    def test_unverified_writers_keep_private_raw_files_and_only_incomplete_snapshots(self):
        # Failure-retention contract only; no mock claims native containment.
        spool = Path(tempfile.mkdtemp(prefix="design-dna-test-run-")).resolve()
        for stream in ("stdout", "stderr"):
            (spool / (stream + ".raw.log")).write_bytes(b"partial exact bytes\n")
        diagnostic = suite_process._retain(spool, ["synthetic-fixture"], "execution-unavailable",
            "Owned group emptiness could not be verified", 1, 1,
            {"attempted": True, "verified": False, "boundary": "synthetic-unverified-group"},
            lambda value: value, writers_settled=False)
        self.addCleanup(self.cleanup_diagnostic, diagnostic)
        record = json.loads(Path(diagnostic["path"]).read_text())
        self.assertFalse(record["suite_complete"])
        self.assertFalse(record["release_eligible"])
        for stream in ("stdout", "stderr"):
            binding = record["output"][stream]
            self.assertTrue(binding["snapshot_may_have_continued"])
            raw = spool / binding["private_raw_retained_unverified_writers"]
            self.assertEqual(b"partial exact bytes\n", raw.read_bytes())


if __name__ == "__main__":
    unittest.main()
