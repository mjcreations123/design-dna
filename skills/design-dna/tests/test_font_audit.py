"""Regression coverage for static public-root font audit resolution."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = SKILL_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import font_audit  # noqa: E402


class StaticPublicRootResolutionTests(unittest.TestCase):
    def stylesheet_source(self, root: Path, source_file: Path) -> dict[str, object]:
        contracts = font_audit.parse_delivery_contracts(
            source_file,
            root,
            source_file.read_text(encoding="utf-8"),
        )
        self.assertEqual(len(contracts), 1)
        return contracts[0]["sources"][0]

    def test_site_public_root_wins_over_repository_asset(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_file = root / "site" / "about" / "index.html"
            source_file.parent.mkdir(parents=True)
            source_file.write_text("<link rel=\"stylesheet\" href=\"/assets/site.css\">", encoding="utf-8")
            (root / "site" / "assets").mkdir()
            (root / "site" / "assets" / "site.css").write_text("body {}", encoding="utf-8")
            (root / "assets").mkdir()
            (root / "assets" / "site.css").write_text("body {}", encoding="utf-8")

            resolved = self.stylesheet_source(root, source_file)

            self.assertEqual(resolved["kind"], "local-file")
            self.assertEqual(resolved["resolved_path"], "site/assets/site.css")
            self.assertTrue(resolved["exists"])

    def test_missing_site_public_asset_remains_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_file = root / "site" / "index.html"
            source_file.parent.mkdir(parents=True)
            source_file.write_text("<link rel=\"stylesheet\" href=\"/assets/site.css\">", encoding="utf-8")
            # An unrelated repository-level match must not mask a broken URL
            # when the static public root is site/.
            (root / "assets").mkdir()
            (root / "assets" / "site.css").write_text("body {}", encoding="utf-8")

            resolved = self.stylesheet_source(root, source_file)

            self.assertEqual(resolved["resolved_path"], "site/assets/site.css")
            self.assertFalse(resolved["exists"])

    def test_repository_root_resolution_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_file = root / "index.html"
            source_file.write_text("<link rel=\"stylesheet\" href=\"/assets/site.css\">", encoding="utf-8")
            (root / "assets").mkdir()
            (root / "assets" / "site.css").write_text("body {}", encoding="utf-8")

            resolved = self.stylesheet_source(root, source_file)

            self.assertEqual(resolved["resolved_path"], "assets/site.css")
            self.assertTrue(resolved["exists"])


if __name__ == "__main__":
    unittest.main()
