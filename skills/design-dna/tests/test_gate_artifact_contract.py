"""Supplementary real font output and immutable sidecars stay in gate validation."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SPEC = importlib.util.spec_from_file_location("gate_extra_contract", SCRIPTS / "gate_artifact_contract.py")
CONTRACT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTRACT)


def actual_font_report(project):
    run = subprocess.run([sys.executable, "-I", "-S", "-B", str(SCRIPTS / "font_audit.py"), str(project)], capture_output=True, text=True, encoding="utf-8", timeout=90)
    if run.returncode:
        raise AssertionError(run.stdout + run.stderr)
    return json.loads(run.stdout)


class GateArtifactContractTests(unittest.TestCase):
    def test_real_font_audit_passes_current_revalidation_and_source_drift_fails(self):
        with tempfile.TemporaryDirectory(prefix="dna-font-record-") as temporary:
            project = Path(temporary)
            (project / "index.html").write_text("<main>Source-bound text</main>", encoding="utf-8")
            report = actual_font_report(project)
            self.assertEqual([], CONTRACT.font_report_failures(report, project=project, rerun_current=True))
            (project / "added.html").write_text("<p>Additional audited source</p>", encoding="utf-8")
            self.assertIn("fresh audit", " | ".join(CONTRACT.font_report_failures(report, project=project, rerun_current=True)))
            # Historical first-screen evidence retains shape/source integrity;
            # current final source counts cannot retroactively replace it.
            self.assertEqual([], CONTRACT.font_report_failures(report))

    def test_font_pass_flag_does_not_replace_a_complete_generated_audit(self):
        self.assertTrue(CONTRACT.font_report_failures({"ok": True, "source_integrity_complete": True, "findings": []}))

    def test_rendered_glyph_records_require_typed_actual_font_data(self):
        row = {"component_id": "heading", "selector": "#heading", "declared_primary_family": "Arial",
            "resolved_alias_families": [], "has_text": True, "pass": True,
            "fonts": [{"familyName": "Arial", "postScriptName": "ArialMT", "glyphCount": 9, "isCustomFont": False}]}
        report = {"complete": True, "findings": [], "records": [row]}
        self.assertEqual([], CONTRACT.rendered_font_failures(report))
        for field, value in (("has_text", "false"), ("component_id", ""), ("declared_primary_family", "Undelivered invented face"), ("fonts", []), ("fonts", [{"familyName": "Arial"}])):
            with self.subTest(field=field, value=value):
                damaged = copy.deepcopy(report)
                damaged["records"][0][field] = value
                self.assertTrue(CONTRACT.rendered_font_failures(damaged))

    def test_only_hash_named_current_content_sidecar_is_a_canonical_extra(self):
        digest = "1" * 64
        expected = f".design-dna/content-transfers/{digest}.json"
        self.assertEqual(expected, CONTRACT.content_artifact_path({"content_transfer": {"path": expected, "sha256": digest}}))
        self.assertEqual(".design-dna/content-transfer.json", CONTRACT.content_artifact_path({"content_transfer": {"path": ".design-dna/content-transfer.json", "sha256": digest}}))
        for path in (".design-dna/unrelated.json", f".design-dna/content-transfers/{'2' * 64}.json", "../external.json"):
            self.assertIsNone(CONTRACT.content_artifact_path({"content_transfer": {"path": path, "sha256": digest}}))

    def test_strict_gate_ledger_accepts_font_and_exact_sidecar_but_not_an_extra_file(self):
        # This is an intentionally incomplete gate fixture. We assert only the
        # exact ledger integration and retain all other strict verifier failures.
        spec = importlib.util.spec_from_file_location("gate_ledger_validator", SCRIPTS / "init_project_state.py")
        validator = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = validator
        self.addCleanup(sys.modules.pop, spec.name, None)
        spec.loader.exec_module(validator)
        with tempfile.TemporaryDirectory(prefix="dna-extra-ledger-") as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            evidence = state / "evidence"
            evidence.mkdir(parents=True)
            manifest = {"manifest_id": "test-manifest", "routes": [], "viewports": []}
            (state / "route-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            content_bytes = b'{"explicitly":"invalid-content-contract-test"}\n'
            digest = hashlib.sha256(content_bytes).hexdigest()
            relative = f".design-dna/content-transfers/{digest}.json"
            content = project / relative
            content.parent.mkdir()
            content.write_bytes(content_bytes)
            mapping = {"schema_version": 2, "construction_authorization": {}, "content_transfer": {"path": relative, "sha256": digest}}
            (state / "visible-decision-sources.json").write_text(json.dumps(mapping), encoding="utf-8")
            (state / "reference-dossier.md").write_text("Explicitly incomplete gate test.\n", encoding="utf-8")
            font = evidence / "font-delivery.json"
            font.write_text(json.dumps(actual_font_report(project)), encoding="utf-8")
            paths = [".design-dna/route-manifest.json", ".design-dna/visible-decision-sources.json", relative, ".design-dna/evidence/font-delivery.json"]
            for name in ("component-census", "style-provenance", "structure-diff", "mechanism-diff", "signature-transfer"):
                path = evidence / (name + ".json")
                path.write_text("{}", encoding="utf-8")
                paths.append(path.relative_to(project).as_posix())
            ledger = [{"path": path, "sha256": hashlib.sha256((project / path).read_bytes()).hexdigest()} for path in paths]
            gate = {"evidence_hashes": ledger, "routes": [], "planned_routes": [], "viewports_checked": [], "route_key": None,
                    "coverage_matrix": [], "states_checked": [], "phase": "maintenance"}
            problems = validator.gate_runtime_evidence_failures(gate, project=project, manifest=manifest, phase="maintenance", require_current_tree=True)
            self.assertTrue(problems, "An incomplete gate must never be blessed by this test.")
            self.assertFalse(any("exact canonical artifact set" in item for item in problems), problems)
            self.assertFalse(any("Gate font artifact:" in item for item in problems), problems)
            self.assertTrue(any("content-transfer artifact" in item for item in problems), problems)
            self.assertFalse(any("First-screen gate route" in item for item in problems), problems)
            gate["evidence_hashes"].append({"path": ".design-dna/extra.json", "sha256": "a" * 64})
            problems = validator.gate_runtime_evidence_failures(gate, project=project, manifest=manifest, phase="maintenance", require_current_tree=True)
            self.assertTrue(any("exact canonical artifact set" in item for item in problems), problems)


if __name__ == "__main__":
    unittest.main()
