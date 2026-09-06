"""Test optimizations must preserve adversarial production-validation semantics."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch

TESTS = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("dossier_cache_subject", TESTS / "test_reference_dossier.py")
SUBJECT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUBJECT)
BENCHMARK_RESULTS = {}


class DossierCacheContractTests(unittest.TestCase):
    def setUp(self):
        SUBJECT._PNG_CACHE.clear()

    @staticmethod
    def restore_bytes(path, data, observed):
        path.write_bytes(data)
        os.utime(path, ns=(observed.st_atime_ns, observed.st_mtime_ns))
        assert path.stat().st_size == observed.st_size
        assert path.stat().st_mtime_ns == observed.st_mtime_ns

    def test_same_size_restored_mtime_cannot_reuse_an_old_sha(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "artifact.bin"
            file.write_bytes(b"abc")
            observed = file.stat()
            first = SUBJECT._cached_file_sha256(file)
            self.restore_bytes(file, b"xyz", observed)
            expected = SUBJECT._ORIGINAL_FILE_SHA256(file)
            self.assertNotEqual(first, expected)
            self.assertEqual(expected, SUBJECT._cached_file_sha256(file))
            self.assertEqual(expected, SUBJECT.INITIALIZER.file_sha256(file))

    def test_same_size_restored_mtime_png_corruption_is_still_decoded_and_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "frame.png"
            SUBJECT.write_png(file)
            observed = file.stat()
            self.assertEqual((8, 8), SUBJECT._cached_verify_png(file))
            corrupt = bytearray(file.read_bytes())
            corrupt[-1] ^= 1
            self.restore_bytes(file, bytes(corrupt), observed)
            for decoder in (SUBJECT._cached_verify_png, SUBJECT._ORIGINAL_VERIFY_PNG):
                with self.subTest(decoder=decoder.__name__), self.assertRaises(SUBJECT.INITIALIZER.StateError) as caught:
                    decoder(file)
                self.assertEqual("render-evidence-image-invalid", caught.exception.code)
                self.assertEqual(file, caught.exception.path)

    def test_byte_key_distinguishes_valid_equal_size_pngs_after_mtime_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            file, other = Path(directory) / "frame.png", Path(directory) / "other.png"
            SUBJECT.write_png(file, width=8, height=8)
            SUBJECT.write_png(other, width=16, height=4)
            a, b = file.read_bytes(), other.read_bytes()
            size = max(len(a), len(b)) + 32
            def pad(data):
                text = b"Note\0" + b"x" * (size - len(data) - 17)
                return data[:-12] + SUBJECT.png_chunk(b"tEXt", text) + data[-12:]
            a, b = pad(a), pad(b)
            self.assertEqual(len(a), len(b))
            file.write_bytes(a)
            observed = file.stat()
            self.assertEqual((8, 8), SUBJECT._cached_verify_png(file))
            self.restore_bytes(file, b, observed)
            self.assertEqual((16, 4), SUBJECT._cached_verify_png(file))
            self.assertEqual(SUBJECT._ORIGINAL_VERIFY_PNG(file), SUBJECT._cached_verify_png(file))

    def test_a_warm_png_decode_still_reads_current_file_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "frame.png"
            SUBJECT.write_png(file)
            original = Path.read_bytes
            reads = []
            def observed_read(path):
                reads.append(path)
                return original(path)
            with patch.object(Path, "read_bytes", observed_read):
                self.assertEqual((8, 8), SUBJECT._cached_verify_png(file))
                self.assertEqual((8, 8), SUBJECT._cached_verify_png(file))
            self.assertEqual([file, file], reads)

    def test_png_errors_preserve_path_and_changed_decoder_is_not_bypassed(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "frame.png"
            SUBJECT.write_png(file)
            SUBJECT._cached_verify_png(file)
            def changed_decoder(path):
                raise SUBJECT.INITIALIZER.StateError("changed-decoder", "new decoder rejects", path=path)
            with patch.object(SUBJECT, "_ORIGINAL_VERIFY_PNG", changed_decoder):
                with self.assertRaises(SUBJECT.INITIALIZER.StateError) as caught:
                    SUBJECT._cached_verify_png(file)
                self.assertEqual("changed-decoder", caught.exception.code)
                self.assertEqual(file, caught.exception.path)
            file.unlink()
            for decoder in (SUBJECT._cached_verify_png, SUBJECT._ORIGINAL_VERIFY_PNG):
                with self.assertRaises(SUBJECT.INITIALIZER.StateError) as caught:
                    decoder(file)
                self.assertEqual("render-evidence-image-invalid", caught.exception.code)
                self.assertEqual(file, caught.exception.path)

    def recording_fixture(self, directory):
        project = SUBJECT.DossierProject(directory)
        project.sequence_block(1)  # Unchanged full 96-second, 15-fps fixture.
        recording = project.captures / "strong-1-recording.json"
        ledger = project.captures / "strong-1-artifacts.json"
        contract = project.captures / "strong-1-state-contract.json"
        payload = json.loads(recording.read_text(encoding="utf-8"))
        ledger_payload = json.loads(ledger.read_text(encoding="utf-8"))
        self.assertEqual(1440, len(payload["profiles"]["wide"]["frames"]["files"]))
        self.assertEqual(1440, len(payload["profiles"]["narrow"]["frames"]["files"]))
        arguments = {"recording": recording, "ledger_payload": ledger_payload, "ledger": ledger,
                     "state_contract": contract, "state_contract_sha256": SUBJECT._ORIGINAL_FILE_SHA256(contract)[1],
                     "expected_reference_id": "strong-1"}
        return payload, arguments

    def test_in_memory_payload_ledger_and_contract_digest_are_revalidated(self):
        with tempfile.TemporaryDirectory() as directory:
            payload, arguments = self.recording_fixture(directory)
            baseline = SUBJECT._cached_recording_failures(payload, **arguments)
            self.assertEqual([], baseline[0])
            changed = copy.deepcopy(payload)
            changed["source_status"] = "partial"
            self.assertTrue(SUBJECT._cached_recording_failures(changed, **arguments)[0])
            changed_ledger = copy.deepcopy(arguments["ledger_payload"])
            changed_ledger["unrecognized"] = True
            self.assertTrue(SUBJECT._cached_recording_failures(payload, **{**arguments, "ledger_payload": changed_ledger})[0])
            self.assertTrue(SUBJECT._cached_recording_failures(payload, **{**arguments, "state_contract_sha256": "0" * 64})[0])
            self.assertEqual(baseline, SUBJECT._cached_recording_failures(payload, **arguments))

    @staticmethod
    def save_recording(payload, arguments):
        recording = arguments["recording"]
        recording.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
        for artifact in arguments["ledger_payload"]["artifacts"]:
            if artifact["file"] == recording.name:
                artifact.update(bytes=recording.stat().st_size, sha256=SUBJECT._ORIGINAL_FILE_SHA256(recording)[1])
        core = {key: value for key, value in arguments["ledger_payload"].items() if key != "sha256"}
        arguments["ledger_payload"]["sha256"] = SUBJECT.INITIALIZER.canonical_json_sha256(core)
        arguments["ledger"].write_text(json.dumps(arguments["ledger_payload"], indent=2) + "\n", encoding="utf-8")

    def test_runtime_dependency_bytes_are_revalidated_after_equal_size_mtime_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            payload, arguments = self.recording_fixture(str(project))
            runtime = root / "runtime"
            runtime.mkdir()
            shutil.copyfile(SUBJECT.SKILL / "scripts/record_reference.mjs", runtime / "record_reference.mjs")
            dependency = runtime / "source_surface_watch.mjs"
            dependency.write_bytes(b"export const fixture=1;\n")
            payload["runtime_identity"][dependency.name] = SUBJECT._ORIGINAL_FILE_SHA256(dependency)[1]
            self.save_recording(payload, arguments)
            with patch.object(SUBJECT.INITIALIZER, "__file__", str(runtime / "init_project_state.py")):
                self.assertEqual([], SUBJECT._cached_recording_failures(payload, **arguments)[0])
                observed = dependency.stat()
                self.restore_bytes(dependency, b"export const fixture=2;\n", observed)
                actual = SUBJECT._cached_recording_failures(payload, **arguments)
                expected = SUBJECT._ORIGINAL_RECORDING_FAILURES(payload, **arguments)
                self.assertEqual(expected, actual)
                self.assertTrue(any("runtime dependency drifted: source_surface_watch.mjs" in failure for failure in actual[0]), actual[0])

    def test_recording_validation_is_uncached_and_measure_cold_warm_cost(self):
        self.assertIs(SUBJECT.INITIALIZER.file_sha256, SUBJECT._ORIGINAL_FILE_SHA256)
        self.assertIs(SUBJECT.INITIALIZER.reference_recording_failures, SUBJECT._ORIGINAL_RECORDING_FAILURES)
        with tempfile.TemporaryDirectory() as directory:
            payload, arguments = self.recording_fixture(directory)
            SUBJECT._PNG_CACHE.clear()
            results, elapsed = [], []
            for _ in range(2):
                start = time.perf_counter()
                results.append(SUBJECT._cached_recording_failures(payload, **arguments))
                elapsed.append(time.perf_counter() - start)
            self.assertEqual([], results[0][0])
            self.assertEqual(results[0], results[1])
            BENCHMARK_RESULTS.update(frame_files=2880, cold_seconds=elapsed[0], warm_seconds=elapsed[1],
                                     png_decode_entries=len(SUBJECT._PNG_CACHE))


if __name__ == "__main__": unittest.main()
