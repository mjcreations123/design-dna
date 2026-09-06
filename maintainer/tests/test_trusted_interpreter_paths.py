"""Trusted interpreter aliases do not weaken project or validator link checks."""
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from directory_link_fixtures import make_directory_link, remove_directory_link

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load(name):
    spec = importlib.util.spec_from_file_location("trusted_path_" + name, SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TrustedInterpreterPathTests(unittest.TestCase):
    def test_real_directory_alias_of_intrinsic_python_is_canonicalized_only_for_host_identity(self):
        attest = load("attest_codex_plugin")
        evaluate = load("run_evals")
        with tempfile.TemporaryDirectory(prefix="dna-host-interpreter-") as temporary:
            root = Path(temporary).resolve()
            real = root / "actual"
            real.mkdir()
            binary = real / ("python.exe" if os.name == "nt" else "python")
            binary.write_bytes(b"intrinsically selected interpreter identity fixture\n")
            alias = root / "host-interpreter-alias"
            make_directory_link(alias, real)
            try:
                invocation = alias / binary.name
                with patch.object(sys, "executable", str(invocation)):
                    self.assertEqual(hashlib.sha256(binary.read_bytes()).hexdigest(), attest.current_python_sha256())
                    with patch.object(evaluate.shutil, "which", return_value=str(invocation)):
                        identity = evaluate.driver_identity(str(invocation), {})
                    self.assertEqual(str(binary), identity["resolved"])
                    self.assertEqual(str(invocation), identity["requested"])
                # The same actual linked input remains forbidden as validator
                # evidence or as an unrelated externally selected driver.
                with self.assertRaises(attest.ToolFailure):
                    attest.stable_file(invocation)
                with patch.object(evaluate.shutil, "which", return_value=str(invocation)), self.assertRaises(evaluate.ToolFailure):
                    evaluate.driver_identity(str(invocation), {})
            finally:
                remove_directory_link(alias)
