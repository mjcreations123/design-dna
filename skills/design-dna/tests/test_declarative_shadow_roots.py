"""HTTP-parsed closed-root coverage; no synthetic clicks or source rewriting."""
from __future__ import annotations

import http.server
import contextlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest

SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
NODE = shutil.which("node")


@contextlib.contextmanager
def source_workspace(producer):
    retained = os.environ.get("DESIGN_DNA_DSD_RECORDING_OUT") if producer == "record_reference.mjs" else None
    if retained:
        output = Path(retained).resolve()
        output.mkdir(parents=True, exist_ok=False)
        yield str(output)
    else:
        with tempfile.TemporaryDirectory(prefix="dna declarative source ") as temporary:
            yield temporary

BUTTON = '<button style="width:220px;height:80px">Visible closed-root control</button>'
BODIES = {
    "/visible": '<header><h1>Declarative source fixture</h1></header><main id="closed-host"><template shadowrootmode="closed">' + BUTTON + '</template></main>',
    "/empty": '<main id="empty-host"><template shadowrootmode="closed"><style>:host{display:block}</style></template></main>',
    "/hidden": '<main id="hidden-host" style="display:none"><template shadowrootmode="closed">' + BUTTON + '</template></main>',
    "/native": '<input id="ordinary-native-control" value="Ordinary native control">',
    "/mixed": '<main id="declarative"><template shadowrootmode="closed">' + BUTTON + '</template></main><aside id="imperative"></aside><script>document.querySelector("#imperative").attachShadow({mode:"closed"}).innerHTML=' + json.dumps(BUTTON) + ';</script>',
    "/nested": '<main id="outer"><template shadowrootmode="open"><section id="inner"><template shadowrootmode="closed">' + BUTTON + '</template></section></template></main>',
    "/frame": '<iframe id="source-frame" src="/visible" style="width:400px;height:220px"></iframe>',
    "/hidden-frame": '<iframe id="hidden-frame" src="/visible" style="display:none"></iframe>',
    "/below": '<main id="below-host" style="margin-top:2000px"><template shadowrootmode="closed">' + BUTTON + '</template></main>',
    "/text": '<main id="text-host"><template shadowrootmode="closed"><style>:host{display:block;font-size:48px}</style>Clearly visible closed-root text</template></main>',
    "/pseudo": '<main id="pseudo-host"><template shadowrootmode="closed"><style>div::before{content:"Clearly visible pseudo text";font-size:48px}</style><div></div></template></main>',
    "/hidden-text": '<main id="hidden-text-host" style="opacity:0"><template shadowrootmode="closed">Invisible root text</template></main>',
    "/hidden-pseudo": '<main id="hidden-pseudo-host"><template shadowrootmode="closed"><style>div::before{content:"Hidden pseudo";opacity:0}</style><div></div></template></main>',
    "/clearfix": '<main id="clearfix-host"><template shadowrootmode="closed"><style>div::after{content:" ";display:table;clear:both}</style><div></div></template></main>',
    "/timed": '<h1>Timed declarative fixture</h1><timed-closed id="timed-host"><template shadowrootmode="closed"><div id="timed-panel" role="dialog" style="display:none;position:fixed;inset:20px;background:navy">Actually visible timed closed content</div></template></timed-closed><script>customElements.define("timed-closed",class extends HTMLElement{constructor(){super();const root=this.attachInternals().shadowRoot,panel=root.querySelector("#timed-panel");window.timedObservations=[];setTimeout(()=>{panel.style.display="block";window.timedObservations.push({phase:"visible",width:panel.getBoundingClientRect().width,at:performance.now()})},1500);setTimeout(()=>{panel.style.display="none";window.timedObservations.push({phase:"hidden",width:panel.getBoundingClientRect().width,at:performance.now()})},2500)}})</script>',
}
BODIES["/timed-text"] = BODIES["/timed"].replace('role="dialog" ', '').replace('position:fixed;inset:20px;', 'font-size:48px;')
BODIES["/timed-removed"] = BODIES["/timed-text"].replace('panel.style.display="none";', 'this.remove();')


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in BODIES:
            self.send_error(404)
            return
        html = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Closed-root HTTP fixture</title>'
                '<style>body{margin:0;background:#10222d;color:white;font-family:sans-serif}</style></head><body>'
                + BODIES[self.path] + '</body></html>').encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def log_message(self, *_args):
        pass


@unittest.skipUnless(NODE, "Node is required for actual closed-root coverage")
class DeclarativeClosedRootTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.origin = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def environment(self):
        environment = os.environ.copy()
        environment.setdefault("DESIGN_DNA_PLAYWRIGHT_MODULE_DIR", str(SKILL.parents[1] / "maintainer/node_modules"))
        return environment

    def browser_json(self, expression):
        program = f"""
          import * as dna from {json.dumps((SCRIPTS / 'browser_evidence.mjs').as_uri())};
          import * as surface from {json.dumps((SCRIPTS / 'source_surface_watch.mjs').as_uri())};
          import {{resolvePlaywright,discoverBrowserExecutable}} from {json.dumps((SCRIPTS / 'playwright_resolver.mjs').as_uri())};
          const loaded=resolvePlaywright({{moduleUrl:import.meta.url}}), executable=discoverBrowserExecutable(loaded.playwright);
          const browser=await loaded.playwright.chromium.launch({{executablePath:executable.file || executable.path || executable,args:['--site-per-process']}});
          const origin={json.dumps(self.origin)};
          try {{const context=await browser.newContext();await dna.installDomInspection(context);const page=await context.newPage();
            const value=await(async()=>{{{expression}}})();console.log(JSON.stringify(value));
          }}finally{{await browser.close();}}
        """
        completed = subprocess.run([NODE, "--input-type=module", "-e", program], env=self.environment(),
                                   capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        return json.loads(completed.stdout)

    def test_http_declarative_material_blocks_public_and_build_censuses(self):
        result = self.browser_json("""
          await dna.navigateExact(page,origin+'/visible');
          const rest={id:'rest',url:page.url(),kind:'rest',trigger:{type:'none',target:'document',value:null},expectation:'HTTP-parsed closed control'};
          const registryCount=await page.evaluate(()=>window.__designDnaCapturedShadowRoots.length);
          const output=[];for(const sourceOnly of [true,false]){const census=await dna.captureInteractionCensus(page,{sourceOnly,authoredStates:[rest],baselineState:rest});output.push({complete:census.complete,missing:census.missing});}
          return {registryCount,output};
        """)
        self.assertEqual(0, result["registryCount"])
        for index, expected in enumerate(("unsupported-source-closed-shadow-root", "unsupported-build-closed-shadow-root")):
            self.assertFalse(result["output"][index]["complete"])
            gap = next(item for item in result["output"][index]["missing"] if item.get("code") == expected)
            self.assertEqual("#closed-host", gap["closed_shadow_root"]["host_selector"])
            self.assertIn("control", gap["closed_shadow_root"]["observed_kinds"])
            self.assertTrue(gap["closed_shadow_root"]["frame_context"]["is_main"])

    def test_timed_closed_content_is_retained_after_it_hides_before_final_census(self):
        result = self.browser_json("""
          await page.goto(origin+'/timed');const before=await dna.discoverUnaddressableClosedRoots(page);
          const watch=await surface.startSourceSurfaceWatch(page);await page.waitForTimeout(2900);
          const after=await dna.discoverUnaddressableClosedRoots(page);let report,code=null;
          try{report=await surface.drainSourceSurfaceWatch(watch);}catch(error){if(!error.surface_watch)throw error;report=error.surface_watch;code=error.code;}finally{await surface.stopSourceSurfaceWatch(watch);}
          return {before,after,code,events:report.events,observed:await page.evaluate(()=>window.timedObservations),nativeRoot:await page.evaluate(()=>document.querySelector('#timed-host').shadowRoot)};
        """)
        self.assertEqual([], result["before"])
        self.assertEqual(1, len(result["after"]))
        self.assertEqual("continuous-watch", result["after"][0]["material_observation"]["kind"])
        self.assertIsNone(result["nativeRoot"])
        self.assertEqual(["visible", "hidden"], [row["phase"] for row in result["observed"]])
        self.assertGreater(result["observed"][0]["width"], 0)
        self.assertEqual(0, result["observed"][1]["width"])
        self.assertTrue(any(row["kind"] == "autonomous-surface-appeared" for row in result["events"]), result)
        # This bounded inventory test did not record screenshots. The retained
        # real events must remain unqualified, never receive fabricated evidence.
        self.assertEqual("source-surface-watch-evidence-incomplete", result["code"])

    def test_early_parser_inventory_precedes_intro_wait_and_survives_handoff(self):
        result = self.browser_json("""
          const early=await surface.armEarlySourceSurfaceWatch(page);await page.goto(origin+'/timed');await page.waitForTimeout(3000);
          const watch=await surface.adoptEarlySourceSurfaceWatch(page,early);let report,code=null;
          try{report=await surface.drainSourceSurfaceWatch(watch);}catch(error){if(!error.surface_watch)throw error;report=error.surface_watch;code=error.code;}finally{await surface.stopSourceSurfaceWatch(watch);}
          return {events:report.events,code,observed:await page.evaluate(()=>window.timedObservations),roots:await dna.discoverUnaddressableClosedRoots(page),listeners:page.listenerCount('domcontentloaded')};
        """)
        self.assertEqual(1, len(result["roots"]))
        self.assertEqual(0, result["listeners"])
        self.assertEqual(["visible", "hidden"], [row["phase"] for row in result["observed"]])
        appeared = [row for row in result["events"] if row["kind"] == "autonomous-surface-appeared"]
        self.assertTrue(appeared, result)
        self.assertTrue(all(row["detail"]["watch_phase"] == "early" for row in appeared))
        self.assertEqual("source-surface-watch-evidence-incomplete", result["code"])

    def test_plain_closed_text_interval_remains_a_material_gap_without_overlay_semantics(self):
        result = self.browser_json("""
          const early=await surface.armEarlySourceSurfaceWatch(page);await page.goto(origin+'/timed-text');await page.waitForTimeout(3000);
          const watch=await surface.adoptEarlySourceSurfaceWatch(page,early);
          const roots=await dna.discoverUnaddressableClosedRoots(page),proof=await dna.discoverUnaddressableClosedRoots(page,{viewportOnly:true});
          const observed=await page.evaluate(()=>window.timedObservations);await surface.stopSourceSurfaceWatch(watch);
          return {roots,proof,observed};
        """)
        self.assertEqual(["visible", "hidden"], [row["phase"] for row in result["observed"]])
        self.assertGreater(result["observed"][0]["width"], 0)
        self.assertEqual(0, result["observed"][1]["width"])
        self.assertEqual([], result["proof"], "An exact current proof state does not inherit prior hidden content")
        self.assertEqual(1, len(result["roots"]))
        root = result["roots"][0]
        self.assertEqual("#timed-host", root["host_selector"])
        self.assertIn("text", root["observed_kinds"])
        self.assertEqual("early", root["material_observation"]["phase"])
        self.assertGreaterEqual(root["material_observation"]["document_elapsed_ms"], 1500)
        self.assertLess(root["material_observation"]["document_elapsed_ms"], 2500)

    def test_observed_closed_material_survives_actual_host_removal(self):
        result = self.browser_json("""
          const early=await surface.armEarlySourceSurfaceWatch(page);await page.goto(origin+'/timed-removed');await page.waitForTimeout(3000);
          const watch=await surface.adoptEarlySourceSurfaceWatch(page,early);
          const roots=await dna.discoverUnaddressableClosedRoots(page),proof=await dna.discoverUnaddressableClosedRoots(page,{viewportOnly:true});
          const hostExists=await page.locator('#timed-host').count(),observed=await page.evaluate(()=>window.timedObservations);
          await surface.stopSourceSurfaceWatch(watch);return {roots,proof,hostExists,observed};
        """)
        self.assertEqual(0, result["hostExists"])
        self.assertEqual([], result["proof"])
        self.assertGreater(result["observed"][0]["width"], 0)
        self.assertEqual(0, result["observed"][1]["width"])
        self.assertEqual(1, len(result["roots"]))
        root = result["roots"][0]
        self.assertEqual("#timed-host", root["host_selector"])
        self.assertTrue(root["frame_context"]["is_main"])
        self.assertEqual("early", root["material_observation"]["phase"])

    def test_empty_hidden_native_and_offscreen_proof_roots_are_not_material(self):
        result = self.browser_json("""
          const result={};for(const name of ['empty','hidden','native','hidden-frame']){await page.goto(origin+'/'+name);result[name]=await dna.discoverUnaddressableClosedRoots(page);}
          await page.goto(origin+'/below');result.belowAll=await dna.discoverUnaddressableClosedRoots(page);result.belowProof=await dna.discoverUnaddressableClosedRoots(page,{viewportOnly:true});return result;
        """)
        for name in ("empty", "hidden", "native", "hidden-frame", "belowProof"):
            self.assertEqual([], result[name], name)
        self.assertEqual(1, len(result["belowAll"]))

    def test_parser_and_javascript_roots_are_unified_without_duplicates(self):
        result = self.browser_json("""
          await page.goto(origin+'/mixed');return {registryCount:await page.evaluate(()=>window.__designDnaCapturedShadowRoots.length),roots:await dna.discoverUnaddressableClosedRoots(page)};
        """)
        self.assertEqual(1, result["registryCount"])
        self.assertEqual(2, len(result["roots"]))
        self.assertEqual({"#declarative", "#imperative"}, {row["host_selector"] for row in result["roots"]})
        self.assertEqual(2, len({row["closed_root_backend_node_id"] for row in result["roots"]}))

    def test_shadow_and_frame_diagnostics_do_not_invent_top_level_selectors(self):
        result = self.browser_json("""
          await page.goto(origin+'/nested');const nested=await dna.discoverUnaddressableClosedRoots(page);
          await page.goto(origin+'/frame');const framed=await dna.discoverUnaddressableClosedRoots(page);return {nested,framed};
        """)
        self.assertEqual(1, len(result["nested"]))
        self.assertIsNone(result["nested"][0]["host_selector"])
        self.assertIsNone(result["nested"][0]["host_local_selector"])
        self.assertIn("shadow root", result["nested"][0]["host_description"])
        self.assertEqual(1, len(result["framed"]))
        framed = result["framed"][0]
        self.assertIsNone(framed["host_selector"])
        self.assertEqual("#closed-host", framed["host_local_selector"])
        self.assertFalse(framed["frame_context"]["is_main"])
        self.assertEqual(self.origin + "/visible", framed["frame_context"]["url"])

    def test_missing_cdp_data_fails_closed_instead_of_returning_empty(self):
        result = self.browser_json("""
          try{await dna.discoverUnaddressableClosedRoots({context:()=>({newCDPSession:async()=>{throw new Error('CDP fixture denial');}})});return {unexpectedSuccess:true};}
          catch(error){return {code:error.code,gap:error.source_harness_gap,message:error.message};}
        """)
        self.assertEqual("closed-shadow-root-discovery-unavailable", result["code"])
        self.assertTrue(result["gap"])
        self.assertIn("CDP fixture denial", result["message"])

    def test_direct_root_text_and_pseudo_material_are_not_silently_empty(self):
        result = self.browser_json("""
          const result={};for(const name of ['text','pseudo','hidden-text','hidden-pseudo','clearfix']){await page.goto(origin+'/'+name);result[name]=await dna.discoverUnaddressableClosedRoots(page);if(name==='clearfix')result.clearfixProof=await dna.discoverUnaddressableClosedRoots(page,{viewportOnly:true});}return result;
        """)
        for name, kind in (("text", "text"), ("pseudo", "pseudo")):
            self.assertEqual(1, len(result[name]))
            self.assertIn(kind, result[name][0]["observed_kinds"])
        self.assertEqual([], result["hidden-text"])
        self.assertEqual([], result["hidden-pseudo"])
        self.assertEqual([], result["clearfix"])
        self.assertEqual([], result["clearfixProof"])

    def test_visible_oopif_is_inspected_while_hidden_and_native_roots_are_excluded(self):
        result = self.browser_json("""
          await context.route('https://outer-dsd.test/**',route=>{const kind=new URL(route.request().url()).pathname.slice(1);return route.fulfill({contentType:'text/html',body:`<h1>Parent</h1><iframe src="https://inner-dsd.test/${kind}" style="${kind==='hidden'?'display:none':'width:400px;height:300px'}"></iframe>`});});
          await context.route('https://inner-dsd.test/**',route=>{const kind=new URL(route.request().url()).pathname.slice(1);return route.fulfill({contentType:'text/html',body:kind==='native'?'<input value="native">':kind==='empty'?'<main><template shadowrootmode="closed"><style>:host{display:block}</style></template></main>':'<div id="closed"><template shadowrootmode="closed"><button style="width:220px;height:80px">Visible cross-site closed control</button></template></div>'});});
          const result={};for(const kind of ['visible','hidden','native','empty']){await page.goto('https://outer-dsd.test/'+kind);result[kind]=await dna.discoverUnaddressableClosedRoots(page);}return result;
        """)
        self.assertEqual(1, len(result["visible"]))
        row = result["visible"][0]
        self.assertIsNone(row["host_selector"])
        self.assertEqual("#closed", row["host_local_selector"])
        self.assertFalse(row["frame_context"]["is_main"])
        self.assertEqual("https://inner-dsd.test/visible", row["frame_context"]["url"])
        for kind in ("hidden", "native", "empty"):
            self.assertEqual([], result[kind], kind)

    def test_uninspectable_visible_oopif_retains_a_typed_frame_gap(self):
        result = self.browser_json("""
          await context.route('https://outer-dsd.test/**',route=>route.fulfill({contentType:'text/html',body:'<iframe src="https://inner-dsd.test/" style="width:400px;height:300px"></iframe>'}));
          await context.route('https://inner-dsd.test/**',route=>route.fulfill({contentType:'text/html',body:'<div><template shadowrootmode="closed"><button>Visible</button></template></div>'}));
          await page.goto('https://outer-dsd.test/');const original=context.newCDPSession.bind(context);context.newCDPSession=async(target)=>{if(target!==page)throw new Error('OOPIF CDP fixture denial');return original(target);};
          try{return {unexpected:await dna.discoverUnaddressableClosedRoots(page)};}catch(error){return {code:error.code,frame:error.frame_context,errors:error.inspection_errors,candidates:error.candidate_frame_urls,diagnostic:error.census_diagnostic};}
        """)
        self.assertEqual("closed-shadow-frame-inspection-unavailable", result["code"])
        self.assertIsNone(result["frame"]["url"])
        self.assertTrue(result["frame"]["id"])
        self.assertTrue(result["frame"]["parent_frame_id"])
        self.assertIn("https://inner-dsd.test/", result["candidates"])
        self.assertIn("OOPIF CDP fixture denial", " ".join(result["errors"]))
        self.assertFalse(result["diagnostic"]["complete"])

    def invoke(self, producer, *, proof=False, hold_sibling=False, startup_failure=None):
        with source_workspace(producer) as temporary:
            output = Path(temporary)
            private_temp = output / "private-process-temp"
            private_temp.mkdir()
            environment = self.environment()
            if startup_failure == "playwright":
                environment["DESIGN_DNA_PLAYWRIGHT_MODULE_DIR"] = str(output / "deliberately-unavailable-modules")
            if startup_failure == "browser":
                environment["DESIGN_DNA_BROWSER_EXECUTABLE"] = str(output / "deliberately-unavailable-browser")
            for key in ("TEMP", "TMP", "TMPDIR"):
                environment[key] = str(private_temp)
            sibling_file = private_temp / "design-dna-source-study-runners-v1" / "runner-1.json"
            sibling_bytes = json.dumps({"schema_version": 1, "pid": os.getpid(), "token": "owned-sibling-fixture",
                                        "id": "unrelated-sibling", "producer": "fixture.mjs"})
            if hold_sibling:
                sibling_file.parent.mkdir()
                sibling_file.write_text(sibling_bytes, encoding="utf-8")
            contract = output / "contract.json"
            contract.write_text(json.dumps({"schema_version": 2, "reference_id": "declarative-source", "states": [
                {"id": "rest", "url": self.origin + "/visible", "kind": "rest", "trigger": {"type": "none", "target": "document", "value": None},
                 "expectation": "The real HTTP-parsed closed control remains an explicit unaddressable harness gap."}]}), encoding="utf-8")
            if startup_failure == "unreadable-contract":
                contract = output / "nonexistent-contract.json"
            elif startup_failure == "invalid-contract":
                contract.write_text('{"schema_version":0}', encoding="utf-8")
            command = [NODE, str(SCRIPTS / producer), "--url", self.origin + "/visible", "--id", "declarative-source", "--out", str(output), "--state-contract", str(contract)]
            if proof:
                command.extend(["--proof-source", "--state", "rest"])
            elif producer == "record_reference.mjs":
                command.extend(["--seconds", "90", "--fps", "15"])
            completed = subprocess.run(command, env=environment, capture_output=True, text=True, encoding="utf-8", timeout=480 if producer == "record_reference.mjs" else 120)
            artifacts = {file.name: json.loads(file.read_text(encoding="utf-8")) for file in output.glob("*.json") if file.name != "contract.json"}
            artifacts["__lease_state__"] = {"output_owned": (output / ".design-dna-source-study-declarative-source.lock.json").exists(),
                "runner_files": sorted(file.name for file in sibling_file.parent.glob("runner-*.json")),
                "sibling_preserved": sibling_file.is_file() and sibling_file.read_text(encoding="utf-8") == sibling_bytes}
            return completed.returncode, json.loads(completed.stdout), artifacts

    def test_proof_observer_rejects_http_declarative_unmeasured_material(self):
        code, result, artifacts = self.invoke("observe_reference.mjs", proof=True)
        self.assertNotEqual(0, code)
        self.assertEqual("proof-closed-shadow-root-unaddressable", result["error"]["code"])
        failure = artifacts["declarative-source-source-study-failure.json"]
        self.assertFalse(failure["eligible_for_source_selection"])
        self.assertEqual("#closed-host", failure["detail"]["closed_shadow_roots"][0]["host_selector"])

    def test_public_observer_cannot_qualify_http_declarative_closed_material(self):
        code, result, artifacts = self.invoke("observe_reference.mjs", hold_sibling=True)
        self.assertNotEqual(0, code)
        self.assertFalse(result["ok"])
        self.assertIn("unsupported-source-closed-shadow-root", json.dumps(artifacts))
        self.assertEqual("unsupported-source-closed-shadow-root", result["error"]["code"])
        self.assertEqual(2, code)
        self.assertFalse(artifacts["__lease_state__"]["output_owned"])
        self.assertEqual(["runner-1.json"], artifacts["__lease_state__"]["runner_files"])
        self.assertTrue(artifacts["__lease_state__"]["sibling_preserved"])

    def test_startup_failure_releases_only_its_own_leases_and_preserves_code(self):
        for mode, expected in (("playwright", "playwright-module-directory-invalid"), ("browser", "browser-executable-invalid"),
                               ("unreadable-contract", "state-contract-unreadable"), ("invalid-contract", "state-contract-invalid")):
            with self.subTest(mode=mode):
                code, result, artifacts = self.invoke("observe_reference.mjs", hold_sibling=True, startup_failure=mode)
                self.assertEqual(2, code)
                self.assertEqual(expected, result["error"]["code"])
                self.assertFalse(artifacts["__lease_state__"]["output_owned"])
                self.assertEqual(["runner-1.json"], artifacts["__lease_state__"]["runner_files"])
                self.assertTrue(artifacts["__lease_state__"]["sibling_preserved"])

    def test_recorder_retains_declarative_gap_at_both_real_ninety_second_profiles(self):
        code, result, artifacts = self.invoke("record_reference.mjs")
        self.assertNotEqual(0, code)
        self.assertFalse(result["ok"])
        recording = artifacts["declarative-source-recording.json"]
        self.assertFalse(recording["eligible_for_source_selection"])
        for profile in ("wide", "narrow"):
            captured = recording["profiles"][profile]
            self.assertGreaterEqual(captured["duration_s"], 90)
            self.assertFalse(captured["coverage"]["complete"])
            self.assertTrue(any(item.get("code") == "unsupported-source-closed-shadow-root" for item in captured["interaction_census"]["missing"]))


if __name__ == "__main__":
    unittest.main()
