from __future__ import annotations

import base64
import json
import os
import runpy
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from jsonschema import Draft202012Validator, FormatChecker, ValidationError


PLUGIN = Path(__file__).resolve().parents[2]
AUDIT = PLUGIN / "skills" / "design-dna" / "scripts" / "font_audit.py"
SCHEMA = PLUGIN / "maintainer" / "schemas" / "font-audit.schema.json"
SCHEMA_DOCUMENT = json.loads(SCHEMA.read_text(encoding="utf-8"))
Draft202012Validator.check_schema(SCHEMA_DOCUMENT)
VALIDATOR = Draft202012Validator(
    SCHEMA_DOCUMENT,
    format_checker=FormatChecker(),
)


def run_audit(
    project: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(AUDIT), str(project), *arguments],
        text=True,
        encoding="utf-8",
        capture_output=True,
        env=environment,
        timeout=120,
    )


def payload(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return json.loads(result.stdout)


class FontAuditSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validator = VALIDATOR

    def test_no_font_project_is_a_valid_non_authorship_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "app.js").write_text(
                "console.log('no font contract');",
                encoding="utf-8",
            )
            result = run_audit(project)
            self.assertEqual(result.returncode, 0, result.stderr)
            result_payload = payload(result)
            self.validator.validate(result_payload)
            self.assertTrue(result_payload["execution_ok"])
            self.assertTrue(result_payload["source_integrity_complete"])
            self.assertEqual(
                result_payload["audit_status"],
                "no-font-evidence",
            )
            self.assertFalse(result_payload["review_required"])
            self.assertFalse(result_payload["font_binaries"])
            self.assertFalse(result_payload["font_faces"])
            self.assertIn(
                "does not identify an AI font",
                result_payload["disclaimer"],
            )
            self.assertEqual(
                result_payload["resource_usage"]["report_bytes"],
                len(result.stdout.rstrip("\n").encode("utf-8")),
            )

    def test_schema_rejects_cross_field_status_contradictions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "app.js").write_text(
                "console.log('no font contract');",
                encoding="utf-8",
            )
            clean = payload(run_audit(project))
            contradictory = json.loads(json.dumps(clean))
            contradictory["audit_status"] = "incomplete"
            with self.assertRaises(ValidationError):
                self.validator.validate(contradictory)
            contradictory = json.loads(json.dumps(clean))
            contradictory["review_required"] = True
            with self.assertRaises(ValidationError):
                self.validator.validate(contradictory)

            contradictory = json.loads(json.dumps(clean))
            contradictory["source_integrity_complete"] = False
            with self.assertRaises(ValidationError):
                self.validator.validate(contradictory)

            self.assertEqual(clean["schema_version"], 2)
            legacy = json.loads(json.dumps(clean))
            legacy["type_watch"] = {"loaded": False}
            with self.assertRaises(ValidationError):
                self.validator.validate(legacy)
            legacy = json.loads(json.dumps(clean))
            legacy["quality_passed"] = True
            with self.assertRaises(ValidationError):
                self.validator.validate(legacy)

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "Brand.woff2").write_bytes(b"wOF2font")
            with_evidence = payload(run_audit(project))
            self.validator.validate(with_evidence)
            contradictory = json.loads(json.dumps(with_evidence))
            contradictory["audit_status"] = "no-font-evidence"
            with self.assertRaises(ValidationError):
                self.validator.validate(contradictory)

    def test_execution_failure_is_schema_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "missing"
            result = run_audit(missing)
            self.assertEqual(result.returncode, 2)
            failure = json.loads(result.stderr)
            self.validator.validate(failure)
            self.assertFalse(failure["execution_ok"])


class FontAuditInventoryTests(unittest.TestCase):
    def test_generated_build_directories_are_ignored_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            app = project / "app"
            fonts = project / "public" / "fonts"
            app.mkdir()
            fonts.mkdir(parents=True)
            (fonts / "Brand.woff2").write_bytes(b"wOF2brand")
            (fonts / "Brand-OFL.txt").write_text(
                "Brand.woff2 is licensed under the SIL Open Font License 1.1",
                encoding="utf-8",
            )
            (app / "styles.css").write_text(
                """\
@font-face {
  font-family: "Brand";
  src: url("/fonts/Brand.woff2") format("woff2");
  font-weight: 400;
  font-style: normal;
}
body { font-family: "Brand", sans-serif; font-weight: 400; }
""",
                encoding="utf-8",
            )

            excluded_names = (
                ".ViNeXt",
                "DiSt",
                ".Design-DNA.Backup-20260728-120000-000001",
                ".design-dna.failed-20260728-120000-000002",
                ".design-dna-migrate-fixture",
                ".design-dna-stage-fixture",
                ".design-dna.unallocated-stage",
            )
            for generated_name in excluded_names:
                generated = project / generated_name
                generated.mkdir()
                (generated / "generated.woff2").write_bytes(b"wOF2generated")
                (generated / "generated.css").write_text(
                    """\
@font-face {
  font-family: "Generated Copy";
  src: url("C:/outside/generated.woff2") format("woff2");
}
""",
                    encoding="utf-8",
                )

            result = run_audit(project)
            self.assertEqual(result.returncode, 0, result.stderr)
            result_payload = payload(result)
            VALIDATOR.validate(result_payload)

            reported_ignores = set(
                result_payload["scan_scope"]["ignored_directories"]
            )
            self.assertTrue({".vinext", "dist"}.issubset(reported_ignores))
            self.assertTrue(
                {
                    ".design-dna.backup-*",
                    ".design-dna.failed-*",
                    ".design-dna-migrate-*",
                    ".design-dna-stage-*",
                    ".design-dna.unallocated-stage",
                }.issubset(reported_ignores)
            )
            self.assertEqual(
                [item["path"] for item in result_payload["font_binaries"]],
                ["public/fonts/Brand.woff2"],
            )
            self.assertEqual(
                [item["file"] for item in result_payload["font_faces"]],
                ["app/styles.css"],
            )
            reported_paths = {
                str(item["file"]).casefold()
                for item in result_payload["findings"]
            }
            excluded_prefixes = tuple(
                f"{name.casefold()}/" for name in excluded_names
            )
            self.assertFalse(
                any(
                    path.startswith(excluded_prefixes)
                    for path in reported_paths
                )
            )

    def test_excluded_state_roots_are_pruned_before_inaccessible_descent(
        self,
    ) -> None:
        module = runpy.run_path(str(AUDIT))
        function_globals = module["enumerate_project"].__globals__
        audit_os = function_globals["os"]

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            included = project / "src"
            included.mkdir()
            (included / "styles.css").write_text(
                "body { font-family: serif; }",
                encoding="utf-8",
            )

            excluded_names = [
                ".design-dna.backup-20260728-120000-000001",
                ".design-dna.failed-20260728-120000-000002",
                ".design-dna-migrate-fixture",
                ".design-dna-stage-fixture",
                ".design-dna.unallocated-stage",
            ]

            def guarded_walk(
                root: Path,
                *,
                topdown: bool,
                followlinks: bool,
                onerror: object,
            ) -> object:
                self.assertTrue(topdown)
                self.assertFalse(followlinks)
                directories = [*excluded_names, "src"]
                yield str(root), directories, []
                unpruned = [
                    name for name in excluded_names if name in directories
                ]
                if unpruned:
                    error = PermissionError(
                        13,
                        "Access is denied",
                        str(project / unpruned[0]),
                    )
                    onerror(error)
                    return
                yield str(included), [], ["styles.css"]

            with patch.object(audit_os, "walk", guarded_walk):
                sources, fonts, evidence = module["enumerate_project"](
                    project,
                    module["ResourceBudget"](),
                )

            self.assertEqual(sources, [included / "styles.css"])
            self.assertEqual(fonts, [])
            self.assertEqual(evidence, [])

            def included_failure_walk(
                root: Path,
                *,
                topdown: bool,
                followlinks: bool,
                onerror: object,
            ) -> object:
                directories = ["private-source"]
                yield str(root), directories, []
                error = PermissionError(
                    13,
                    "Access is denied",
                    str(project / directories[0]),
                )
                onerror(error)

            with patch.object(audit_os, "walk", included_failure_walk):
                with self.assertRaisesRegex(
                    module["AuditError"],
                    "tree-enumeration-failed",
                ):
                    module["enumerate_project"](
                        project,
                        module["ResourceBudget"](),
                    )

    def test_family_names_are_inventory_data_not_quality_signals(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            reports = []
            for directory, family in (
                ("familiar", "Inter"),
                ("invented", "Copper Finch Text"),
            ):
                project = base / directory
                fonts = project / "fonts"
                fonts.mkdir(parents=True)
                (fonts / "face.woff2").write_bytes(b"wOF2font-payload")
                (fonts / "OFL.txt").write_text(
                    "SIL Open Font License 1.1",
                    encoding="utf-8",
                )
                (project / "styles.css").write_text(
                    '@font-face {\n'
                    f'  font-family: "{family}";\n'
                    '  src: url("./fonts/face.woff2") format("woff2");\n'
                    '  font-weight: 400;\n'
                    '}\n'
                    f'body {{ font-family: "{family}"; font-weight: 400; }}\n',
                    encoding="utf-8",
                )
                result = run_audit(project)
                self.assertEqual(result.returncode, 0, result.stderr)
                report = payload(result)
                VALIDATOR.validate(report)
                self.assertEqual(report["schema_version"], 2)
                self.assertNotIn("type_watch", report)
                self.assertEqual(report["font_faces"][0]["family"], family)
                reports.append(report)

            self.assertEqual(
                reports[0]["audit_status"],
                reports[1]["audit_status"],
            )
            self.assertEqual(reports[0]["counts"], reports[1]["counts"])
            self.assertEqual(
                [item["id"] for item in reports[0]["findings"]],
                [item["id"] for item in reports[1]["findings"]],
            )

    def test_broken_contracts_are_reported_independently_of_family_name(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            missing_contracts = []
            for directory, family in (
                ("familiar", "Inter"),
                ("invented", "Copper Finch Text"),
            ):
                project = base / directory
                project.mkdir()
                (project / "styles.css").write_text(
                    '@font-face {\n'
                    f'  font-family: "{family}";\n'
                    '  src: url("./fonts/missing.woff2") format("woff2");\n'
                    '}\n'
                    f'body {{ font-family: "{family}"; }}\n',
                    encoding="utf-8",
                )
                result = run_audit(project)
                self.assertEqual(result.returncode, 0, result.stderr)
                report = payload(result)
                VALIDATOR.validate(report)
                missing = next(
                    item
                    for item in report["findings"]
                    if item["id"] == "missing-local-font-file"
                )
                missing_contracts.append({
                    key: missing[key]
                    for key in (
                        "id",
                        "severity",
                        "confidence",
                        "message",
                        "suggestion",
                    )
                })

            self.assertEqual(missing_contracts[0], missing_contracts[1])

    def test_removed_type_watch_argument_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "styles.css").write_text(
                "body { font-family: Example; }",
                encoding="utf-8",
            )
            result = run_audit(project, "--type-watch", "legacy.yml")
            self.assertEqual(result.returncode, 2)
            self.assertIn("unrecognized arguments", result.stderr)

    def test_inventory_contracts_sources_preload_and_license(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            fonts = project / "fonts"
            fonts.mkdir()
            (fonts / "Acme.woff2").write_bytes(b"wOF2font-payload")
            (fonts / "OFL.txt").write_text(
                "SIL Open Font License 1.1",
                encoding="utf-8",
            )
            face = """\
@font-face {
  font-family: "Acme";
  src: local("Acme"),
       url("./fonts/Acme.woff2") format("woff2"),
       url("https://cdn.example.com/acme.woff2") format("woff2"),
       url("data:font/woff2;base64,AAAA") format("woff2");
  font-weight: 100 900;
  font-style: normal;
  font-display: swap;
  unicode-range: U+0000-00FF;
}
"""
            (project / "styles.css").write_text(
                face
                + face
                + ':root { --brand-stack: "Acme", sans-serif; }\n'
                + "body { font-family: var(--brand-stack); "
                + "font-weight: 650; }\n",
                encoding="utf-8",
            )
            (project / "index.html").write_text(
                '<link rel="preload" as="font" '
                'href="/fonts/Acme.woff2" type="font/woff2" crossorigin>',
                encoding="utf-8",
            )
            result = run_audit(project)
            self.assertEqual(result.returncode, 0, result.stderr)
            result_payload = payload(result)
            VALIDATOR.validate(result_payload)

            self.assertEqual(len(result_payload["font_binaries"]), 1)
            binary = result_payload["font_binaries"][0]
            self.assertEqual(binary["path"], "fonts/Acme.woff2")
            self.assertEqual(binary["size_bytes"], len(b"wOF2font-payload"))
            self.assertEqual(len(binary["sha256"]), 64)
            self.assertEqual(
                binary["container_signature"]["detected"],
                "woff2",
            )
            self.assertTrue(
                binary["container_signature"]["matches_extension"]
            )

            self.assertEqual(len(result_payload["font_faces"]), 2)
            first = result_payload["font_faces"][0]
            self.assertEqual(first["family"], "Acme")
            self.assertEqual(
                (first["weight"]["minimum"], first["weight"]["maximum"]),
                (100, 900),
            )
            self.assertTrue(first["weight"]["variable"])
            self.assertEqual(first["display"], "swap")
            self.assertEqual(first["unicode_range"], "U+0000-00FF")
            self.assertEqual(
                [source["kind"] for source in first["sources"]],
                ["local-name", "local-file", "remote-url", "data-url"],
            )
            self.assertTrue(first["sources"][1]["exists"])
            self.assertEqual(first["sources"][1]["format"], "woff2")

            self.assertEqual(len(result_payload["preloads"]), 1)
            preload = result_payload["preloads"][0]
            self.assertTrue(preload["source"]["exists"])
            self.assertTrue(preload["crossorigin"])
            self.assertEqual(
                result_payload["declared_stacks"][0]["families"],
                ["Acme", "sans-serif"],
            )
            self.assertEqual(
                result_payload["declared_weights"][0]["normalized"],
                650,
            )
            self.assertTrue(
                result_payload["license_provenance"][
                    "explicit_evidence_found"
                ]
            )
            ids = [item["id"] for item in result_payload["findings"]]
            self.assertIn("duplicate-font-face", ids)
            self.assertNotIn("undeclared-font-weight", ids)
            self.assertNotIn("missing-font-license-provenance-evidence", ids)

    def test_license_evidence_is_bound_per_font_binary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            fonts = project / "fonts"
            fonts.mkdir()
            (fonts / "A.woff2").write_bytes(b"wOF2font-a")
            (fonts / "B.woff2").write_bytes(b"wOF2font-b")
            (fonts / "A-OFL.txt").write_text(
                "SIL Open Font License 1.1",
                encoding="utf-8",
            )
            (fonts / "B-LICENSE.txt").write_text(
                "This unrelated placeholder is not provenance evidence.",
                encoding="utf-8",
            )

            result = run_audit(project)
            self.assertEqual(result.returncode, 0, result.stderr)
            result_payload = payload(result)
            VALIDATOR.validate(result_payload)
            by_path = {
                item["path"]: item
                for item in result_payload["font_binaries"]
            }
            self.assertEqual(
                by_path["fonts/A.woff2"]["provenance"]["status"],
                "resolved",
            )
            self.assertEqual(
                by_path["fonts/B.woff2"]["provenance"]["status"],
                "unresolved",
            )
            self.assertEqual(
                result_payload["license_provenance"]["resolved_font_paths"],
                ["fonts/A.woff2"],
            )
            self.assertEqual(
                result_payload["license_provenance"]["unresolved_font_paths"],
                ["fonts/B.woff2"],
            )
            unresolved_findings = [
                item
                for item in result_payload["findings"]
                if item["id"]
                == "missing-font-license-provenance-evidence"
            ]
            self.assertEqual(
                [item["file"] for item in unresolved_findings],
                ["fonts/B.woff2"],
            )

    def test_missing_files_mismatches_and_likely_unused_are_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "styles.css").write_text(
                """\
@font-face {
  font-family: "Acme";
  src: url("./missing.woff2") format("woff2");
  font-weight: 400;
  font-style: normal;
}
@font-face {
  font-family: "Orphan";
  src: url("data:font/woff2;base64,AAAA") format("woff2");
  font-weight: 400;
  font-style: normal;
}
.title {
  font-family: "Acme", sans-serif;
  font-weight: 700;
  font-style: italic;
}
""",
                encoding="utf-8",
            )
            (project / "index.html").write_text(
                '<link rel="preload" as="font" href="/fonts/missing.woff2">',
                encoding="utf-8",
            )

            result = run_audit(project)
            self.assertEqual(result.returncode, 0, result.stderr)
            result_payload = payload(result)
            VALIDATOR.validate(result_payload)
            self.assertTrue(result_payload["execution_ok"])
            self.assertTrue(result_payload["review_required"])
            ids = {item["id"] for item in result_payload["findings"]}
            self.assertTrue({
                "missing-local-font-file",
                "missing-preloaded-font-file",
                "undeclared-font-weight",
                "undeclared-font-style",
                "likely-unused-font-family",
            }.issubset(ids))
            self.assertEqual(
                result_payload["source_summary"]["missing_local_file"],
                2,
            )
            mismatch = next(
                item
                for item in result_payload["findings"]
                if item["id"] == "undeclared-font-weight"
            )
            self.assertEqual(
                mismatch["confidence"],
                "paired-static-declaration",
            )

    def test_cross_file_custom_property_resolves_only_when_referenced(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "faces.css").write_text(
                """\
@font-face {
  font-family: "Cross File Used";
  src: url("data:font/woff2;base64,AAAA") format("woff2");
  font-weight: 400;
}
@font-face {
  font-family: "Token Only";
  src: url("data:font/woff2;base64,AAAA") format("woff2");
  font-weight: 400;
}
""",
                encoding="utf-8",
            )
            (project / "tokens.css").write_text(
                """\
:root {
  --font-base: "Cross File Used", serif;
  --font-alias: var(--font-base);
  --font-never-read: "Token Only", serif;
}
""",
                encoding="utf-8",
            )
            (project / "component.css").write_text(
                """\
.title {
  font-family: var(--font-alias);
  font-weight: 400;
}
""",
                encoding="utf-8",
            )

            result = run_audit(project)
            self.assertEqual(result.returncode, 0, result.stderr)
            result_payload = payload(result)
            VALIDATOR.validate(result_payload)
            unused = {
                item["evidence"]["family"]
                for item in result_payload["findings"]
                if item["id"] == "likely-unused-font-family"
            }
            self.assertEqual(unused, {"Token Only"})
            component_stack = next(
                stack
                for stack in result_payload["declared_stacks"]
                if stack["file"] == "component.css"
            )
            self.assertEqual(
                component_stack["families"],
                ["Cross File Used", "serif"],
            )


class FontAuditParsingSafetyTests(unittest.TestCase):
    def test_signed_remote_and_large_data_urls_are_redacted(self) -> None:
        decoded = b"x" * (2 * 1024 * 1024 + 1)
        encoded = base64.b64encode(decoded).decode("ascii")
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "styles.css").write_text(
                '@font-face { font-family: "Private"; src: '
                'url("https://alice:password@cdn.example.com/font.woff2'
                '?token=TOPSECRET#fragment") format("woff2"), '
                f'url("data:font/woff2;base64,{encoded}") '
                'format("woff2"); }\n',
                encoding="utf-8",
            )
            result = run_audit(project)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("alice", result.stdout)
            self.assertNotIn("password", result.stdout)
            self.assertNotIn("TOPSECRET", result.stdout)
            self.assertNotIn(encoded[:256], result.stdout)
            result_payload = payload(result)
            VALIDATOR.validate(result_payload)
            remote, data = result_payload["font_faces"][0]["sources"]
            self.assertEqual(
                remote["value"],
                "https://cdn.example.com/font.woff2",
            )
            self.assertEqual(len(remote["locator_sha256"]), 64)
            self.assertEqual(data["value"], "data:font/woff2;base64")
            self.assertEqual(
                data["data_summary"]["decoded_length"],
                len(decoded),
            )
            self.assertFalse(
                data["data_summary"]["hashed_within_limit"]
            )
            self.assertIsNone(data["data_summary"]["sha256"])
            self.assertLess(
                result_payload["resource_usage"]["report_bytes"],
                result_payload["resource_limits"]["max_report_bytes"],
            )
            leaked_remote = json.loads(json.dumps(result_payload))
            leaked_remote["font_faces"][0]["sources"][0]["value"] = (
                "https://alice:password@cdn.example.com/font.woff2"
                "?token=TOPSECRET#fragment"
            )
            with self.assertRaises(ValidationError):
                VALIDATOR.validate(leaked_remote)
            leaked_data = json.loads(json.dumps(result_payload))
            leaked_data["font_faces"][0]["sources"][1]["value"] = (
                "data:font/woff2;base64,AAAA"
            )
            with self.assertRaises(ValidationError):
                VALIDATOR.validate(leaked_data)

    def test_next_font_fontsource_tailwind_css_import_and_google_link(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            fonts = project / "fonts"
            fonts.mkdir()
            (fonts / "Brand.woff2").write_bytes(b"wOF2brand")
            (project / "app.tsx").write_text(
                'import { Inter as BrandSans } from "next/font/google";\n'
                'import localFont from "next/font/local";\n'
                'import "@fontsource/roboto/400.css";\n'
                "const inter = BrandSans({ subsets: ['latin'] });\n"
                "const brand = localFont({ src: ["
                "{ path: './fonts/Brand.woff2', weight: '400', "
                "style: 'normal' }] });\n",
                encoding="utf-8",
            )
            (project / "tailwind.config.ts").write_text(
                "export default { theme: { extend: { fontFamily: { "
                "sans: ['Inter', 'sans-serif'], "
                "brand: ['Brand', 'sans-serif'] } } } };",
                encoding="utf-8",
            )
            (project / "styles.css").write_text(
                '@import url("https://fonts.googleapis.com/css2?'
                'family=DM+Sans:wght@400;700&display=swap");',
                encoding="utf-8",
            )
            (project / "index.html").write_text(
                '<link rel="stylesheet" href="https://fonts.googleapis.com/'
                'css2?family=Source+Serif+4&display=swap">',
                encoding="utf-8",
            )
            result = run_audit(project)
            self.assertEqual(result.returncode, 0, result.stderr)
            result_payload = payload(result)
            VALIDATOR.validate(result_payload)
            kinds = {
                item["kind"]
                for item in result_payload["delivery_contracts"]
            }
            self.assertTrue({
                "next-font-google",
                "next-font-local",
                "fontsource-import",
                "theme-font-family",
                "google-fonts-stylesheet",
            }.issubset(kinds))
            local_contract = next(
                item
                for item in result_payload["delivery_contracts"]
                if item["kind"] == "next-font-local"
            )
            self.assertTrue(local_contract["complete"])
            self.assertEqual(
                local_contract["sources"][0]["resolved_path"],
                "fonts/Brand.woff2",
            )
            self.assertTrue(local_contract["sources"][0]["exists"])
            google_contract = next(
                item
                for item in result_payload["delivery_contracts"]
                if item["kind"] == "next-font-google"
            )
            self.assertEqual(google_contract["family"], "Inter")
            self.assertEqual(
                google_contract["details"]["binding"],
                "BrandSans",
            )
            google_families = {
                family
                for item in result_payload["delivery_contracts"]
                for family in item["details"].get("families", [])
            }
            self.assertIn("DM Sans", google_families)
            self.assertIn("Source Serif 4", google_families)
            self.assertTrue(
                any(
                    item["source_kind"] == "js-theme-font-family"
                    for item in result_payload["declared_stacks"]
                )
            )

    def test_non_utf8_and_oversized_sources_are_structured_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "invalid.css").write_bytes(b"\xff\xfe")
            (project / "oversized.css").write_bytes(
                b"x" * (5 * 1024 * 1024 + 1)
            )
            result = run_audit(project)
            self.assertEqual(result.returncode, 1, result.stderr)
            result_payload = payload(result)
            VALIDATOR.validate(result_payload)
            self.assertTrue(result_payload["execution_ok"])
            self.assertFalse(result_payload["ok"])
            self.assertFalse(result_payload["source_integrity_complete"])
            self.assertEqual(result_payload["audit_status"], "incomplete")
            self.assertTrue(result_payload["review_required"])
            self.assertEqual(
                {
                    item["reason"]
                    for item in result_payload["skipped_sources"]
                },
                {
                    "source-is-not-valid-utf8",
                    "source-exceeds-per-file-byte-limit",
                },
            )
            self.assertFalse(result_payload["completeness"]["complete"])

    def test_resource_budgets_fail_closed_deterministically(self) -> None:
        module = runpy.run_path(str(AUDIT))
        function_globals = module["ResourceBudget"].add_entry.__globals__
        with patch.dict(
            function_globals,
            {
                "MAX_TOTAL_ENTRIES": 1,
                "MAX_TOTAL_SOURCE_BYTES": 4,
            },
        ):
            budget = module["ResourceBudget"]()
            budget.add_entry()
            with self.assertRaises(module["AuditError"]):
                budget.add_entry()
            source_budget = module["ResourceBudget"]()
            self.assertTrue(source_budget.reserve_source(3))
            self.assertFalse(source_budget.reserve_source(2))
            self.assertIn(
                "total-source-bytes",
                source_budget.exceeded,
            )
        with patch.dict(
            function_globals,
            {
                "MAX_TOTAL_FONT_BYTES": 4,
                "MAX_FONT_BYTES": 4,
            },
        ):
            font_budget = module["ResourceBudget"]()
            self.assertTrue(font_budget.reserve_font(3))
            self.assertFalse(font_budget.reserve_font(2))
            self.assertIn("total-font-bytes", font_budget.exceeded)
        with patch.object(
            function_globals["time"],
            "monotonic",
            side_effect=[0.0, 31.0],
        ), patch.dict(
            function_globals,
            {"MAX_AUDIT_SECONDS": 30.0},
        ):
            timed_budget = module["ResourceBudget"]()
            with self.assertRaises(module["AuditError"]):
                timed_budget.check_time()
        with patch.dict(
            module["encode_bounded_report"].__globals__,
            {"MAX_REPORT_BYTES": 10},
        ):
            report_budget = module["ResourceBudget"]()
            with self.assertRaises(module["AuditError"]):
                module["encode_bounded_report"](
                    {
                        "resource_usage": {"report_bytes": 0},
                        "payload": "bounded-report-check",
                    },
                    budget=report_budget,
                )

    def test_dynamic_next_local_font_contract_is_structured_incomplete(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "app.tsx").write_text(
                'import localFont from "next/font/local";\n'
                "const fontPath = chooseFontAtRuntime();\n"
                "const brand = localFont({ src: fontPath });\n"
                'export const Links = () => <link rel="stylesheet" '
                'href="{{themeUrl}}" />;\n',
                encoding="utf-8",
            )
            (project / "styles.css").write_text(
                "@import url(var(--font-sheet));\n",
                encoding="utf-8",
            )
            result = run_audit(project)
            self.assertEqual(result.returncode, 1, result.stderr)
            result_payload = payload(result)
            VALIDATOR.validate(result_payload)
            self.assertEqual(result_payload["audit_status"], "incomplete")
            self.assertFalse(result_payload["source_integrity_complete"])
            self.assertEqual(
                result_payload["completeness"]["dynamic_contract_count"],
                3,
            )
            contracts = result_payload["delivery_contracts"]
            self.assertEqual(
                {
                    contract["kind"]
                    for contract in contracts
                    if not contract["complete"]
                },
                {
                    "next-font-local",
                    "stylesheet-link",
                    "css-import",
                },
            )
            self.assertTrue(
                all(
                    not contract["static"] and not contract["complete"]
                    for contract in contracts
                )
            )
            self.assertTrue(
                any(
                    finding["id"]
                    == "dynamic-or-incomplete-font-contract"
                    for finding in result_payload["findings"]
                )
            )

    def test_comments_quoted_remote_data_and_traversal_are_classified(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            styles = project / "assets" / "styles"
            styles.mkdir(parents=True)
            (styles / "fonts.css").write_text(
                """\
/* @font-face {
  font-family: "Commented";
  src: url("../../../../outside.woff2");
} */
@font-face {
  font-family: "Live";
  src: url("../../../../outside.woff2") format("woff2"),
       url("https://cdn.example.com/font(1).woff2") format("woff2"),
       url("data:font/woff2;base64,AAAA,BBBB") format("woff2");
}
""",
                encoding="utf-8",
            )
            result = run_audit(project)
            self.assertEqual(result.returncode, 0, result.stderr)
            result_payload = payload(result)
            VALIDATOR.validate(result_payload)
            self.assertEqual(len(result_payload["font_faces"]), 1)
            self.assertEqual(
                [source["kind"] for source in result_payload["font_faces"][0]["sources"]],
                ["unsafe-local-path", "remote-url", "data-url"],
            )
            self.assertEqual(
                result_payload["source_summary"]["unsafe_reference"],
                1,
            )
            unsafe = [
                item
                for item in result_payload["findings"]
                if item["id"] == "unsafe-font-source-reference"
            ]
            self.assertEqual(len(unsafe), 1)
            self.assertNotIn(
                "Commented",
                {
                    face["family"]
                    for face in result_payload["font_faces"]
                },
            )

    def test_font_container_mismatch_is_reported_from_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "wrong.woff2").write_bytes(b"OTTOpayload")
            result = run_audit(project)
            self.assertEqual(result.returncode, 0, result.stderr)
            result_payload = payload(result)
            VALIDATOR.validate(result_payload)
            mismatch = next(
                item
                for item in result_payload["findings"]
                if item["id"] == "font-container-signature-mismatch"
            )
            self.assertEqual(mismatch["confidence"], "exact-bytes")
            self.assertEqual(
                result_payload["font_binaries"][0][
                    "container_signature"
                ]["detected"],
                "opentype-cff",
            )

    def test_reparse_root_or_nested_path_fails_closed_when_supported(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            target = base / "target"
            target.mkdir()
            (target / "styles.css").write_text(
                "body { font-family: serif; }",
                encoding="utf-8",
            )
            root_link = base / "root-link"
            try:
                root_link.symlink_to(target, target_is_directory=True)
            except OSError:
                module = runpy.run_path(str(AUDIT))
                fake = SimpleNamespace(
                    st_mode=stat.S_IFLNK,
                    st_file_attributes=0,
                    st_reparse_tag=0,
                )
                with patch.object(Path, "lstat", return_value=fake):
                    self.assertTrue(module["is_reparse"](Path("symlink")))
                return
            result = run_audit(root_link)
            self.assertEqual(result.returncode, 2)
            failure = json.loads(result.stderr)
            VALIDATOR.validate(failure)
            self.assertIn("reparse", failure["error"]["message"].casefold())

    def test_windows_junction_signature_is_treated_as_reparse(self) -> None:
        module = runpy.run_path(str(AUDIT))
        fake = SimpleNamespace(
            st_mode=stat.S_IFDIR,
            st_file_attributes=0x400,
            st_reparse_tag=0xA0000003,
        )
        with patch.object(Path, "lstat", return_value=fake):
            self.assertTrue(module["is_reparse"](Path("junction")))

    def test_actual_windows_junction_root_fails_closed(self) -> None:
        if os.name != "nt":
            module = runpy.run_path(str(AUDIT))
            fake = SimpleNamespace(
                st_mode=stat.S_IFDIR,
                st_file_attributes=0x400,
                st_reparse_tag=0xA0000003,
            )
            with patch.object(Path, "lstat", return_value=fake):
                self.assertTrue(module["is_reparse"](Path("junction")))
            return
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            target = base / "target"
            junction = base / "junction"
            target.mkdir()
            created = subprocess.run(
                [
                    "cmd.exe",
                    "/d",
                    "/c",
                    "mklink",
                    "/J",
                    str(junction),
                    str(target),
                ],
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=30,
            )
            if created.returncode != 0:
                module = runpy.run_path(str(AUDIT))
                fake = SimpleNamespace(
                    st_mode=stat.S_IFDIR,
                    st_file_attributes=0x400,
                    st_reparse_tag=0xA0000003,
                )
                with patch.object(Path, "lstat", return_value=fake):
                    self.assertTrue(module["is_reparse"](Path("junction")))
                return
            try:
                result = run_audit(junction)
                self.assertEqual(result.returncode, 2)
                failure = json.loads(result.stderr)
                VALIDATOR.validate(failure)
                self.assertIn(
                    "reparse",
                    failure["error"]["message"].casefold(),
                )
            finally:
                junction.rmdir()

    def test_unstable_source_read_is_refused(self) -> None:
        module = runpy.run_path(str(AUDIT))
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "styles.css"
            source.write_text(
                "body { font-family: serif; }",
                encoding="utf-8",
            )
            actual = source.stat()
            changed = SimpleNamespace(
                st_dev=actual.st_dev,
                st_ino=actual.st_ino,
                st_size=actual.st_size,
                st_mtime_ns=actual.st_mtime_ns + 1,
            )
            with patch.object(Path, "stat", side_effect=[actual, changed]):
                with self.assertRaises(module["AuditError"]):
                    module["stable_read_bytes"](
                        source,
                        maximum=1024,
                    )


if __name__ == "__main__":
    unittest.main()
