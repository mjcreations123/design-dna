"""First-screen projection is a fixed subset of a full immutable plan."""
import copy
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


class ConstructionPhaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("phase", SCRIPTS / "construction_phase.py")
        cls.phase = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.phase)

    def plan(self):
        manifest = {"routes": [{"key": "home", "states": [{"id": "rest"}, {"id": "menu"}, {"id": "gallery"}]},
                               {"key": "about", "states": [{"id": "rest"}]}]}
        mapping = {"proof_isolation": {"primary_route_key": "home", "decision_ids": ["hero", "menu"]},
                   "planned_decision_ids": ["hero", "menu", "gallery", "about"], "decisions": [
            {"decision_id": key, "bindings": [{"route_key": route, "state_id": state, "viewport": profile}
                                               for profile in ("wide", "narrow")]}
            for key, route, state in [("hero", "home", "rest"), ("menu", "home", "menu"),
                                      ("gallery", "home", "gallery"), ("about", "about", "rest")]]}
        return manifest, mapping

    def js_routes(self, manifest, mapping, routes):
        script = f"import {{deriveFirstScreenRoutes}} from {json.dumps((SCRIPTS / 'construction_phase.mjs').as_uri())}; console.log(JSON.stringify(deriveFirstScreenRoutes({json.dumps(manifest)},{json.dumps(mapping)},{json.dumps(routes)})))"
        return subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=30)

    def test_full_future_plan_does_not_require_future_implementation_in_proof(self):
        manifest, mapping = self.plan()
        original = copy.deepcopy((manifest, mapping))
        actual = self.phase.derive_first_screen_routes(manifest, mapping, ["home"])
        self.assertEqual(["rest", "menu"], [row["id"] for row in actual[0]["states"]])
        done = self.js_routes(manifest, mapping, ["home"])
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertEqual(actual, json.loads(done.stdout))
        self.assertEqual(original, (manifest, mapping))
        self.assertEqual(2, len(manifest["routes"]))
        self.assertEqual(3, len(manifest["routes"][0]["states"]))

    def test_mutated_unknown_or_wrong_route_projection_fails_in_both_languages(self):
        for mutation in ("unknown", "duplicate", "rest-omitted", "wrong-route"):
            with self.subTest(mutation=mutation):
                manifest, mapping = self.plan()
                routes = ["home"]
                if mutation == "unknown": mapping["proof_isolation"]["decision_ids"].append("unplanned")
                elif mutation == "duplicate": mapping["proof_isolation"]["decision_ids"].append("hero")
                elif mutation == "rest-omitted": mapping["proof_isolation"]["decision_ids"] = ["menu"]
                else: routes = ["about"]
                with self.assertRaises(ValueError): self.phase.derive_first_screen_routes(manifest, mapping, routes)
                self.assertNotEqual(0, self.js_routes(manifest, mapping, routes).returncode)

    def test_pending_navigation_is_exact_source_link_subset_and_never_final_evidence(self):
        manifest, mapping = self.plan()
        route = manifest["routes"][0]
        route["mapped_reference_id"] = "strong-1"
        for decision in mapping["decisions"]:
            decision["source_mapping"] = {"id": "strong-1", "source_selector": "#" + decision["decision_id"]}
        source = {"pages": [{"targets": [
            {"target_id": "one", "selector": '[data-dna-interaction-id="1"]', "source_selector": "#menu", "kind": "route-link",
             "inputs": [{"input_kind": "focus", "status": "exercised"}, {"input_kind": "navigation", "status": "exercised"}]},
            {"target_id": "two", "selector": "#gallery", "kind": "control", "inputs": [{"input_kind": "click", "status": "exercised"}]}]}]}
        build = {"pages": [{"targets": [{"inputs": [{"decision_id": "menu", "input_kind": "navigation", "disposition": "deferred-until-final-gate"}]}]}]}
        original = copy.deepcopy(source)
        actual = self.phase.derive_first_screen_source_census(source, mapping, route, "wide", build)
        self.assertEqual(["focus"], [row["input_kind"] for row in actual["pages"][0]["targets"][0]["inputs"]])
        self.assertEqual(original, source)
        script = f"import {{deriveFirstScreenSourceCensus}} from {json.dumps((SCRIPTS / 'construction_phase.mjs').as_uri())}; console.log(JSON.stringify(deriveFirstScreenSourceCensus({json.dumps(source)},{json.dumps(mapping)},{json.dumps(route)},'wide',{json.dumps(build)})))"
        done = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=30)
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertEqual(actual, json.loads(done.stdout))
        source["pages"][0]["url"] = "https://source.test/"
        repeated_nav = copy.deepcopy(source["pages"][0])
        repeated_nav["url"] = "https://source.test/inner"
        source["pages"].append(repeated_nav)
        projected = self.phase.derive_first_screen_source_census(source, mapping, route, "wide", build, "https://source.test/")
        self.assertEqual(["https://source.test/"], [row["url"] for row in projected["pages"]])
        script = f"import {{deriveFirstScreenSourceCensus}} from {json.dumps((SCRIPTS / 'construction_phase.mjs').as_uri())}; console.log(JSON.stringify(deriveFirstScreenSourceCensus({json.dumps(source)},{json.dumps(mapping)},{json.dumps(route)},'wide',{json.dumps(build)},'https://source.test/')))"
        done = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=30)
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertEqual(projected, json.loads(done.stdout))
        with self.assertRaises(ValueError):
            self.phase.derive_first_screen_source_census(source, mapping, route, "wide", build)
        build["pages"][0]["targets"][0]["inputs"][0]["decision_id"] = "gallery"
        with self.assertRaises(ValueError):
            self.phase.derive_first_screen_source_census(source, mapping, route, "wide", build, "https://source.test/")

    def test_generated_pending_link_validates_only_with_exact_first_screen_authority(self):
        spec = importlib.util.spec_from_file_location("phase_source_fixture", SCRIPTS.parent / "tests/test_source_study_runtime.py")
        fixtures = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixtures)
        helper_type = fixtures.PackagedSourceCaptureTests
        helper_type.setUpClass()
        try:
            value = helper_type().browser_json("""
              const {createHash}=await import('node:crypto'); let sequence=0;
              const future=new URL('/planned-future',page.url()).href;
              await page.evaluate((href)=>{document.body.innerHTML='<main><a id="future" data-design-dna-decision-id="planned-link">Future route</a></main>';document.querySelector('#future').href=href;},future);
              const rest={id:'rest',url:page.url(),kind:'rest',trigger:{type:'none',target:'document',value:null},expectation:'The isolated source-bound first screen'};
              const captureEvidence=async(_label,target=page)=>{const bytes=await target.screenshot();return {file:`memory-${++sequence}.png`,bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')};};
              const census=await m.captureInteractionCensus(page,{authoredStates:[rest],baselineState:rest,plannedDeferredRoutes:[future],captureEvidence});
              return {census,future,url:page.url()};
            """)
        finally:
            helper_type.tearDownClass()
        spec = importlib.util.spec_from_file_location("phase_initializer", SCRIPTS / "init_project_state.py")
        initializer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(initializer)
        options = {"expected_profile": "wide", "expected_state_ids": {"rest"}, "expected_urls": {value["url"]}}
        allowed = initializer.interaction_census_failures(value["census"], planned_route_handoffs={value["future"]}, **options)
        self.assertEqual([], allowed)
        self.assertEqual("#future", value["census"]["pages"][0]["targets"][0]["source_selector"])
        for authority in (None, {value["url"]}):
            failures = initializer.interaction_census_failures(value["census"], planned_route_handoffs=authority, **options)
            self.assertTrue(any("planned route handoff" in failure for failure in failures), failures)

    def ast(self, source, *args):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "proof.tsx"
            file.write_text(source, encoding="utf-8")
            done = subprocess.run(["node", str(SCRIPTS / "proof_isolation_ast.mjs"), "--file", str(file), *args],
                                  capture_output=True, text=True, encoding="utf-8", timeout=30)
            return done, json.loads(done.stdout)

    def test_bound_hidden_menu_and_planned_route_link_are_valid_standard_proof_source(self):
        source = '<main data-design-dna-component="hero"><a data-design-dna-component="menu" href="/about" style={{opacity: 0, visibility: "hidden"}}>About</a></main>'
        done, payload = self.ast(source, "--required-component", "hero", "--required-component", "menu",
                                 "--strict-component-maps", "--other-route", "/about", "--planned-route", "/about")
        self.assertEqual(0, done.returncode, payload)

    def test_route_link_exception_does_not_permit_unplanned_or_internal_proof_navigation(self):
        source = '<main><a href="/about">About</a></main>'
        done, payload = self.ast(source)
        self.assertNotEqual(0, done.returncode)
        self.assertIn("proof-route-link", [row["code"] for row in payload["findings"]])
        done, payload = self.ast(source, "--planned-route", "/catalog")
        self.assertNotEqual(0, done.returncode)

    def test_planned_href_does_not_allow_route_code_or_extra_hidden_component(self):
        for source in ('const route = "/about"; <main data-design-dna-component="hero"/>',
                       '<main data-design-dna-component="hero"><div data-design-dna-component="future" style={{display:"none"}}>Future</div></main>'):
            done, payload = self.ast(source, "--required-component", "hero", "--strict-component-maps",
                                     "--other-route", "/about", "--planned-route", "/about")
            self.assertNotEqual(0, done.returncode, payload)


if __name__ == "__main__": unittest.main()
