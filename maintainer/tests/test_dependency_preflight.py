from __future__ import annotations

import importlib.metadata
import importlib.util
import re
import unittest
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[2]
REQUIREMENTS = PLUGIN / "maintainer" / "requirements-dev.txt"
IMPORT_NAMES = {
    "attrs": "attrs",
    "jsonschema": "jsonschema",
    "jsonschema-specifications": "jsonschema_specifications",
    "packaging": "packaging",
    "pyyaml": "yaml",
    "referencing": "referencing",
    "rpds-py": "rpds",
    "typing-extensions": "typing_extensions",
}


def normalized_distribution_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).casefold()


class ReleaseDependencyPreflightTests(unittest.TestCase):
    def test_pinned_maintainer_dependencies_are_installed(self) -> None:
        pins: dict[str, tuple[str, str]] = {}
        malformed: list[str] = []
        for raw_line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
            line = raw_line.partition("#")[0].strip()
            if not line:
                continue
            match = re.fullmatch(
                r"([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9._+-]*)",
                line,
            )
            if not match:
                malformed.append(raw_line)
                continue
            distribution, version = match.groups()
            key = normalized_distribution_name(distribution)
            if key in pins:
                malformed.append(f"duplicate requirement: {distribution}")
                continue
            pins[key] = (distribution, version)

        issues = [
            f"requirements-dev.txt entry is not an exact pin: {line!r}"
            for line in malformed
        ]
        if not pins:
            issues.append("requirements-dev.txt contains no pinned dependencies")

        for key, (distribution, expected_version) in sorted(pins.items()):
            module = IMPORT_NAMES.get(key)
            if module is None:
                issues.append(
                    f"preflight has no import-name mapping for {distribution}"
                )
                continue
            try:
                actual_version = importlib.metadata.version(distribution)
            except importlib.metadata.PackageNotFoundError:
                issues.append(
                    f"{distribution}=={expected_version} is not installed"
                )
                continue
            if actual_version != expected_version:
                issues.append(
                    f"{distribution} version is {actual_version}; "
                    f"expected {expected_version}"
                )
            if importlib.util.find_spec(module) is None:
                issues.append(
                    f"{distribution} is installed but import {module!r} "
                    "is unavailable"
                )

        self.assertFalse(
            issues,
            "Release-critical tests require every exact dependency pin from "
            "maintainer/requirements-dev.txt. Install them with "
            "`python -m pip install -r maintainer/requirements-dev.txt`.\n- "
            + "\n- ".join(issues),
        )

    def test_release_format_checks_do_not_depend_on_optional_extras(self) -> None:
        import sys

        scripts = str(PLUGIN / "maintainer" / "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        from common import strict_format_checker

        checker = strict_format_checker()
        self.assertTrue(checker.conforms("2026-07-28", "date"))
        self.assertFalse(checker.conforms("2026-02-29", "date"))
        self.assertTrue(
            checker.conforms("2026-07-28T12:34:56Z", "date-time")
        )
        self.assertFalse(checker.conforms("not-a-date", "date-time"))
        self.assertTrue(
            checker.conforms("https://example.com/evidence", "uri")
        )
        self.assertFalse(checker.conforms("not a uri", "uri"))


if __name__ == "__main__":
    unittest.main()
