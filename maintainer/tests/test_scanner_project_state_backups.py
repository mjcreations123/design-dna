from __future__ import annotations

import json
import os
import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PLUGIN = Path(__file__).resolve().parents[2]
SCAN = PLUGIN / "skills" / "design-dna" / "scripts" / "scan_project.py"


def run_scan(project: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(SCAN), str(project), *arguments],
        text=True,
        encoding="utf-8",
        capture_output=True,
        env=environment,
        timeout=120,
    )


def stdout_payload(
    result: subprocess.CompletedProcess[str],
) -> dict[str, object]:
    return json.loads(result.stdout)


class ScannerProjectStateBackupTests(unittest.TestCase):
    def test_initializer_evidence_peers_are_excluded_without_hiding_near_match(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "page.html").write_text(
                "<main>Project source</main>\n",
                encoding="utf-8",
            )
            for name in (
                ".design-dna.backup-20260802-055834-001852",
                ".design-dna.failed-20260802-055834-001852-2",
            ):
                evidence = project / name
                evidence.mkdir()
                (evidence / "page.html").write_text(
                    "<p>Lorem ipsum</p>\n",
                    encoding="utf-8",
                )

            ordinary = project / ".design-dna.backup-client-copy"
            ordinary.mkdir()
            (ordinary / "page.html").write_text(
                "<p>Lorem ipsum</p>\n",
                encoding="utf-8",
            )

            result = run_scan(project, "--json", "--advisory-exit-zero")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = stdout_payload(result)
            self.assertTrue(report["execution_ok"])
            self.assertEqual(report["scan_scope"]["eligible_file_count"], 2)
            self.assertEqual(report["scan_scope"]["scanned_file_count"], 2)
            self.assertEqual(
                {
                    finding["file"]
                    for finding in report["findings"]
                    if finding["rule"] == "placeholder-proof"
                },
                {".design-dna.backup-client-copy/page.html"},
            )
            self.assertTrue(
                {
                    ".design-dna.backup-YYYYMMDD-HHMMSS-ffffff[-N]",
                    ".design-dna.failed-YYYYMMDD-HHMMSS-ffffff[-N]",
                }.issubset(report["source_coverage"]["always_excluded_directories"])
            )

    def test_inaccessible_initializer_backup_is_pruned_before_descent(self) -> None:
        scanner = runpy.run_path(str(SCAN))
        iter_files = scanner["iter_files"]
        scanner_os = iter_files.__globals__["os"]
        backup_name = ".design-dna.backup-20260802-055834-001852"

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            source = project / "src"
            source.mkdir()
            page = source / "page.tsx"
            page.write_text("export default function Page() {}\n", encoding="utf-8")

            for include_built_output in (False, True):
                with self.subTest(include_built_output=include_built_output):
                    root_dirs_after_pruning: list[str] = []

                    def simulated_walk(
                        root: Path,
                        *,
                        topdown: bool,
                        followlinks: bool,
                        onerror,
                    ):
                        self.assertTrue(topdown)
                        self.assertFalse(followlinks)
                        dirs = [backup_name, "src"]
                        yield str(root), dirs, []
                        root_dirs_after_pruning.extend(dirs)
                        if backup_name in dirs:
                            onerror(
                                PermissionError(
                                    13,
                                    "Access is denied",
                                    str(project / backup_name),
                                )
                            )
                            return
                        yield str(source), [], [page.name]

                    with mock.patch.object(scanner_os, "walk", simulated_walk):
                        selected = list(
                            iter_files(
                                project,
                                {".tsx"},
                                include_built_output=include_built_output,
                            )
                        )

                    self.assertEqual(root_dirs_after_pruning, ["src"])
                    self.assertEqual(selected, [page])


if __name__ == "__main__":
    unittest.main()
