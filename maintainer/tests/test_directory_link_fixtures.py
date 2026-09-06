"""Verify portable security-test links and non-following fixture cleanup."""
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest

from directory_link_fixtures import make_directory_link, remove_directory_link


class DirectoryLinkFixtureTests(unittest.TestCase):
    def test_real_directory_link_and_windows_junction_cleanup_preserve_target(self):
        cases = (False, True) if os.name == "nt" else (False,)
        for force_junction in cases:
            with self.subTest(force_junction=force_junction), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target, link = root / "target", root / "link"
                target.mkdir()
                marker = target / "retained.txt"
                marker.write_text("target must survive", encoding="utf-8")
                kind = make_directory_link(link, target, force_junction=force_junction)
                self.assertEqual(marker.read_text(encoding="utf-8"), (link / marker.name).read_text(encoding="utf-8"))
                if force_junction: self.assertEqual("junction", kind)
                remove_directory_link(link)
                self.assertFalse(link.exists())
                self.assertEqual("target must survive", marker.read_text(encoding="utf-8"))

    def test_symlink_cleanup_uses_unlink_not_directory_removal(self):
        calls = []
        link = SimpleNamespace(lstat=lambda: SimpleNamespace(st_mode=stat.S_IFLNK),
                               unlink=lambda: calls.append("unlink"))
        remove_directory_link(link)
        self.assertEqual(["unlink"], calls)

    def test_cleanup_refuses_an_ordinary_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            ordinary = Path(directory) / "ordinary"
            ordinary.mkdir()
            with self.assertRaises(AssertionError): remove_directory_link(ordinary)
            self.assertTrue(ordinary.is_dir())

    def test_link_creation_refuses_existing_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, link = root / "target", root / "existing"
            target.mkdir()
            link.mkdir()
            with self.assertRaises(AssertionError): make_directory_link(link, target)
            self.assertTrue(link.is_dir())


if __name__ == "__main__": unittest.main()
