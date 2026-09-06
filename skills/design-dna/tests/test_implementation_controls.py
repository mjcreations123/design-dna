"""Regression tests for broad-build prohibition and full component fidelity."""
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"

def module(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

class ImplementationControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.init = module("init_project_state")
        cls.control = module("implementation_control")

    def test_failed_first_screen_allows_only_isolated_proof_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            proof = project / "proof.tsx"
            proof.write_text("<main>source-bound proof</main>", encoding="utf-8")
            gate = project / ".design-dna" / "evidence" / "first-screen-gate.json"
            gate.parent.mkdir(parents=True)
            record = {"run_id": "a" * 32, "checked_at": "2026-09-04T12:00:00Z", "phase": "first-screen", "pass": False, "failures": ["source frame missing"]}
            gate.write_text(json.dumps(record), encoding="utf-8")
            self.control.write_prohibition(project, gate, record, self.init)
            mapping = {"proof_isolation": {"source_files": ["proof.tsx"]}}
            proof.write_text("<main>repaired source-bound proof</main>", encoding="utf-8")
            self.assertEqual([], self.control.prohibition_failures(project, mapping, self.init))
            (project / "catalog.tsx").write_text("<section>invented catalog</section>", encoding="utf-8")
            failures = self.control.prohibition_failures(project, mapping, self.init)
            self.assertTrue(any("catalog.tsx" in item for item in failures), failures)

    def test_precode_baseline_does_not_exempt_mdx_or_tests_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "tests").mkdir()
            (project / "tests" / "served.mdx").write_text("<object data='scene.svg' />", encoding="utf-8")
            _tree, _files, visible, _assets = self.init.construction_source_snapshot(project)
            self.assertEqual(["tests/served.mdx"], [row["path"] for row in visible])

    def test_forged_alias_or_deleted_broad_file_cannot_release_failed_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            outside = project / "broad.tsx"
            outside.write_text("<main>existing broad code</main>", encoding="utf-8")
            gate = project / ".design-dna" / "evidence" / "prebuild-runs" / "failed" / "gate.json"
            gate.parent.mkdir(parents=True)
            record = {"run_id": "b" * 32, "checked_at": "2026-09-04T12:00:00Z", "phase": "first-screen", "pass": False, "failures": ["failed proof"]}
            gate.write_text(json.dumps(record), encoding="utf-8")
            self.control.write_prohibition(project, gate, record, self.init)
            alias = project / ".design-dna" / "evidence" / "first-screen-gate.json"
            alias.write_text(json.dumps({"pass": True, "phase": "first-screen", "checked_at": "2026-09-05T12:00:00Z"}), encoding="utf-8")
            outside.unlink()
            findings = self.control.prohibition_failures(project, {"proof_isolation": {"source_files": ["proof.tsx"]}}, self.init)
            self.assertTrue(any("broad.tsx" in item for item in findings), findings)
            gate.write_text("{}", encoding="utf-8")
            findings = self.control.prohibition_failures(project, {}, self.init)
            self.assertTrue(any("hash drifted" in item for item in findings), findings)

    def test_declared_custom_family_without_delivery_is_high_severity(self):
        font = module("font_audit")
        usage = {"families": ["Missing Product Face", "sans-serif"], "file": "site.css", "line": 1}
        findings = font.collect_findings(binaries=[], faces=[], preloads=[], usages=[usage], delivery_contracts=[], unresolved_font_paths=[])
        self.assertTrue(any(row["id"] == "declared-font-without-delivery" and row["severity"] == "high" for row in findings), findings)

    def test_later_section_geometry_and_route_aliases_cannot_hide_behind_a_hero(self):
        script = f"""
import {{compareComponentGeometry, indistinguishableRouteFindings}} from {json.dumps((SCRIPTS / 'component_geometry.mjs').as_uri())};
const cell = {{route_key:'home',viewport:'wide',state_id:'rest',source_state:{{id:'rest'}}}};
const binding = {{decisions:[{{decision_id:'later',component_id:'later',source_mapping:{{id:'strong-2'}},bindings:[cell],style_provenance:{{tuples:[{{viewport:'wide',state_id:'rest',source_selector:'#later'}}]}}}}]}};
const expected={{left:0,top:900,width:1440,height:500}};
const styles=new Map([['strong-2',{{component_styles:[{{profile:'wide',state_id:'rest',selector:'#later',geometry:expected}}]}}]]);
const check={{...cell,decision_roots:[{{decision_id:'later',roots:[{{geometry:{{...expected,top:1200}}}}]}}]}};
const failed=compareComponentGeometry(binding,[check],styles,['home']);
check.decision_roots[0].roots[0].geometry=expected;
const passing=compareComponentGeometry(binding,[check],styles,['home']);
const aliases=indistinguishableRouteFindings([{{route_key:'home',viewport:'wide',state_id:'rest',rendered_route_identity:'same'}},{{route_key:'catalog',viewport:'wide',state_id:'rest',rendered_route_identity:'same'}}]);
console.log(JSON.stringify({{failed,passing,aliases}}));
"""
        done = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(0, done.returncode, done.stderr)
        result = json.loads(done.stdout)
        self.assertFalse(result["failed"]["complete"])
        self.assertTrue(result["passing"]["complete"])
        self.assertEqual("route-job-indistinguishable", result["aliases"][0]["code"])

    def test_rendered_font_alias_is_resolved_without_accepting_missing_or_unrelated_faces(self):
        script = f"""
import {{chromium}} from {json.dumps((SCRIPTS.parents[2] / 'maintainer/node_modules/playwright/index.mjs').as_uri())};
import {{prepareRenderedFontDelivery,auditRenderedFontDelivery}} from {json.dumps((SCRIPTS / 'rendered_font_delivery.mjs').as_uri())};
const b=await chromium.launch(); const p=await b.newPage(); await prepareRenderedFontDelivery(p);
await p.setContent('<p id="text" style="font-family:sans-serif">Actual glyph family</p>');
const baseline=await auditRenderedFontDelivery(p,[{{component_id:'text',selector:'#text',family:'sans-serif'}}]);
const family=baseline.records[0].fonts[0].familyName;
await p.setContent(`<style>@font-face{{font-family:ProofAlias;src:local("${{family}}")}}#text{{font-family:ProofAlias,sans-serif}}</style><p id="text">Actual glyph family</p>`);
await p.evaluate(()=>document.fonts.ready);
const alias=await auditRenderedFontDelivery(p,[{{component_id:'text',selector:'#text',family:'ProofAlias,sans-serif'}}]);
const missing=await auditRenderedFontDelivery(p,[{{component_id:'text',selector:'#text',family:'Definitely Missing Face,sans-serif'}}]);
const inventedName=family.replaceAll(' ','').split('').join('-');
await p.locator('#text').evaluate((element,name)=>element.style.fontFamily=`"${{name}}",sans-serif`,inventedName);
const punctuationImpostor=await auditRenderedFontDelivery(p,[{{component_id:'text',selector:'#text',family:inventedName+',sans-serif'}}]);
await p.setContent(`<style>@font-face{{font-family:WrongAlias;src:local("${{family}}");unicode-range:U+FFFF}}#text{{font-family:WrongAlias,sans-serif}}</style><p id="text">Actual glyph family</p>`);
await p.evaluate(()=>document.fonts.ready);
const unrelated=await auditRenderedFontDelivery(p,[{{component_id:'text',selector:'#text',family:'WrongAlias,sans-serif'}}]);
console.log(JSON.stringify({{alias,missing,unrelated,punctuationImpostor}}));await b.close();
"""
        done = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(0, done.returncode, done.stderr)
        result = json.loads(done.stdout)
        self.assertTrue(result["alias"]["complete"], result["alias"])
        self.assertFalse(result["missing"]["complete"])
        self.assertFalse(result["unrelated"]["complete"])
        self.assertFalse(result["punctuationImpostor"]["complete"])

if __name__ == "__main__":
    unittest.main()
