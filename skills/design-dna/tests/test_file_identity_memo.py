#!/usr/bin/env python3
"""The validator reads each bound file once per top-level validation and never
remembers a digest across validations."""

from __future__ import annotations

import importlib.util
import os
import tempfile
import time
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]


def load_initializer():
    spec = importlib.util.spec_from_file_location("init_project_state", SKILL / "scripts" / "init_project_state.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


INITIALIZER = load_initializer()


def rewrite_same_size_restoring_mtime(path: Path, data: bytes) -> None:
    observed = path.stat()
    path.write_bytes(data)
    os.utime(path, ns=(observed.st_atime_ns, observed.st_mtime_ns))
    assert path.stat().st_size == observed.st_size
    assert path.stat().st_mtime_ns == observed.st_mtime_ns


class FileIdentityScopeTests(unittest.TestCase):
    def test_outside_a_validation_every_call_reads_current_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "frame.png"
            path.write_bytes(b"A" * 64)
            first = INITIALIZER.file_sha256(path)
            rewrite_same_size_restoring_mtime(path, b"B" * 64)
            second = INITIALIZER.file_sha256(path)
            self.assertNotEqual(first[1], second[1])

    def test_inside_one_validation_an_unchanged_file_is_read_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "frame.png"
            path.write_bytes(b"A" * 64)
            opens = 0
            original_open = Path.open

            def counting_open(self, *args, **kwargs):
                nonlocal opens
                mode = args[0] if args else kwargs.get("mode", "r")
                if self == path and "r" in str(mode) and "w" not in str(mode):
                    opens += 1
                return original_open(self, *args, **kwargs)

            Path.open = counting_open  # type: ignore[assignment]
            try:
                with INITIALIZER._validation_hash_scope():
                    first = INITIALIZER.file_sha256(path)
                    self.assertEqual(first, INITIALIZER.file_sha256(path))
                    self.assertEqual(1, opens)
                    # A change with a new size or mtime inside the call is re-read.
                    time.sleep(0.01)
                    path.write_bytes(b"C" * 65)
                    changed = INITIALIZER.file_sha256(path)
                    self.assertEqual(65, changed[0])
                    self.assertNotEqual(first[1], changed[1])
                    self.assertEqual(2, opens)
                # The scope is gone: the next validation reads again.
                INITIALIZER.file_sha256(path)
                self.assertEqual(3, opens)
            finally:
                Path.open = original_open  # type: ignore[assignment]

    def test_nested_scopes_share_one_table_and_release_at_the_outermost(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "frame.png"
            path.write_bytes(b"A" * 64)
            with INITIALIZER._validation_hash_scope():
                INITIALIZER.file_sha256(path)
                outer = INITIALIZER._VALIDATION_HASH_SCOPE.get()
                with INITIALIZER._validation_hash_scope():
                    self.assertIs(outer, INITIALIZER._VALIDATION_HASH_SCOPE.get())
                self.assertIs(outer, INITIALIZER._VALIDATION_HASH_SCOPE.get())
            self.assertIsNone(INITIALIZER._VALIDATION_HASH_SCOPE.get())

    def test_missing_file_still_raises_the_typed_read_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(INITIALIZER.StateError):
                INITIALIZER.file_sha256(Path(temporary) / "absent.png")
            with INITIALIZER._validation_hash_scope():
                with self.assertRaises(INITIALIZER.StateError):
                    INITIALIZER.file_sha256(Path(temporary) / "absent.png")


if __name__ == "__main__":
    unittest.main()
