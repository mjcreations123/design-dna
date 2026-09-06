#!/usr/bin/env python3
"""Focused regressions for exact browser/source evidence producers."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
NODE = shutil.which("node")


def node_value(module: str, expression: str):
    uri = (SCRIPTS / module).resolve().as_uri()
    code = (
        f'import * as m from {json.dumps(uri)}; '
        f'const value = await ({expression}); process.stdout.write(JSON.stringify(value));'
    )
    done = subprocess.run(
        [NODE, "--input-type=module", "-e", code],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if done.returncode:
        raise AssertionError(done.stderr or done.stdout)
    return json.loads(done.stdout)


@unittest.skipIf(NODE is None, "node is required")
class BrowserEvidenceBehaviorTests(unittest.TestCase):
    def test_credential_bearing_urls_are_refused(self) -> None:
        value = node_value(
            "browser_evidence.mjs",
            "(() => { try { m.normalizeHttpUrl('https://user:secret@example.test/'); return null; } "
            "catch (error) { return error.message; } })()",
        )
        self.assertIn("credential-bearing", value)

    def test_state_transition_has_measured_weight_and_first_screen_visibility(self) -> None:
        value = node_value(
            "observe_reference.mjs",
            "(() => { const mechanism={type:'state-transition',changed_properties:4,duration_ms:350}; "
            "return {weight:m.mechanismWeight(mechanism), first:m.firstScreenSheet({mechanisms:[mechanism],score:{}},900).mechanisms}; })()",
        )
        self.assertEqual(1650, value["weight"])
        self.assertEqual("state-transition", value["first"][0]["type"])

    def test_observer_merges_authored_state_mechanisms_into_profile_sheet(self) -> None:
        text = (SCRIPTS / "observe_reference.mjs").read_text(encoding="utf-8")
        self.assertIn("...Object.values(statesByViewport.wide).map", text)
        self.assertIn("...Object.values(statesByViewport.narrow).map", text)

    def test_exact_navigation_binds_every_redirect_status(self) -> None:
        expression = """(async () => {
          const firstResponse = {status:()=>301,statusText:()=>"Moved",url:()=>"https://example.test/old"};
          const first = {method:()=>"GET",url:()=>"https://example.test/old",redirectedFrom:()=>null,response:async()=>firstResponse};
          const finalResponse = {status:()=>200,statusText:()=>"OK",url:()=>"https://example.test/final",
            request:()=>final};
          const final = {method:()=>"GET",url:()=>"https://example.test/final",redirectedFrom:()=>first,response:async()=>finalResponse};
          const page = {goto:async()=>finalResponse,url:()=>"https://example.test/final",waitForTimeout:async()=>{}};
          try { await m.navigateExact(page,"https://example.test/old"); return {unexpected:true}; }
          catch (error) { return {code:error.code,statuses:error.navigation.redirect_chain.map(x=>x.status),
            requested:error.navigation.requested_normalized_url,final:error.navigation.final_normalized_url}; }
        })()"""
        value = node_value("browser_evidence.mjs", expression)
        self.assertEqual("navigation-final-url", value["code"])
        self.assertEqual([301, 200], value["statuses"])
        self.assertEqual("https://example.test/old", value["requested"])
        self.assertEqual("https://example.test/final", value["final"])

    def test_non_2xx_navigation_is_refused(self) -> None:
        expression = """(async () => {
          const response = {status:()=>404,statusText:()=>"Missing",url:()=>"https://example.test/",
            request:()=>request};
          const request = {method:()=>"GET",url:()=>"https://example.test/",redirectedFrom:()=>null,response:async()=>response};
          const page = {goto:async()=>response,url:()=>"https://example.test/",waitForTimeout:async()=>{}};
          try { await m.navigateExact(page,"https://example.test/"); return null; }
          catch (error) { return {code:error.code,status:error.navigation.final_status}; }
        })()"""
        self.assertEqual(
            {"code": "navigation-status", "status": 404},
            node_value("browser_evidence.mjs", expression),
        )

    def test_served_content_hash_uses_response_bytes_and_canonical_reload(self) -> None:
        expression = """(async () => {
          async function probe(resourceBody) {
            let listener; const main = {};
            const page = {on:(name,fn)=>{listener=fn},off:()=>{},url:()=>"https://example.test/",mainFrame:()=>main};
            const tracker = m.beginServedContentCapture(page,"https://example.test/");
            const make = (url,type,body) => { const request={url:()=>url,method:()=>"GET",resourceType:()=>type,
              isNavigationRequest:()=>type==="document",frame:()=>main}; return {request:()=>request,url:()=>url,status:()=>200,
              finished:async()=>{},body:async()=>Buffer.from(body)}; };
            listener(make("https://example.test/","document","<html>same</html>"));
            listener(make("https://example.test/app.js","script",resourceBody));
            tracker.setFinalResponse({final_normalized_url:"https://example.test/",final_status:200});
            return tracker.finish({route_key:"home",viewport:"wide"});
          }
          const a=await probe("const a=1"), b=await probe("const a=1"), c=await probe("const a=2");
          const stable=m.aggregateServedContent([a,b]), changed=m.aggregateServedContent([a,c]);
          return {resourceA:a.resources[0].sha256,resourceC:c.resources[0].sha256,
            stableComplete:stable.complete,stableProbes:stable.probes.length,stableReloads:stable.reload_counts["home/wide"],
            changedComplete:changed.complete};
        })()"""
        value = node_value("browser_evidence.mjs", expression)
        self.assertNotEqual(value["resourceA"], value["resourceC"])
        self.assertTrue(value["stableComplete"])
        self.assertEqual(1, value["stableProbes"])
        self.assertEqual(2, value["stableReloads"])
        self.assertFalse(value["changedComplete"])

    def test_state_contract_requires_exact_mapping_and_programmatic_driver(self) -> None:
        rest = {
            "id": "rest",
            "kind": "rest",
            "trigger": {"type": "none", "target": "document", "value": None},
            "expectation": "Initial settled route.",
            "mapped_reference_state_id": "rest",
        }
        valid = node_value(
            "browser_evidence.mjs",
            f'm.validateManifestState({json.dumps(rest)},{{requireMappedReference:true}})',
        )
        broken = dict(rest)
        broken.pop("mapped_reference_state_id")
        invalid = node_value(
            "browser_evidence.mjs",
            f'm.validateManifestState({json.dumps(broken)},{{requireMappedReference:true}})',
        )
        self.assertIsNone(valid)
        self.assertIn("mapped_reference_state_id", invalid)

    def test_ambient_appearance_is_source_only_and_waits_for_real_visibility(self) -> None:
        state = {
            "id": "newsletter-appearance",
            "kind": "system",
            "trigger": {
                "type": "ambient",
                "target": "#newsletter-modal",
                "value": None,
                "wait_ms": 100,
            },
            "expectation": "The newsletter dialog appears without visitor input after the observed delay.",
        }
        rejected = node_value(
            "browser_evidence.mjs",
            f"m.validateManifestState({json.dumps(state)})",
        )
        self.assertIn("source-observation-only", rejected)
        self.assertIsNone(node_value(
            "browser_evidence.mjs",
            f"m.validateManifestState({json.dumps(state)},{{sourceOnly:true}})",
        ))
        broken = json.loads(json.dumps(state))
        broken["trigger"]["wait_ms"] = 99
        self.assertIn("wait_ms", node_value(
            "browser_evidence.mjs",
            f"m.validateManifestState({json.dumps(broken)},{{sourceOnly:true}})",
        ))
        expression = f"""(async () => {{
          const state = {json.dumps(state)};
          let phase = 0, appearanceFrames = 0;
          const rows = (opacity) => [{{key:'page',tag:'div',properties:{{opacity,display:'block',visibility:'visible'}}}}];
          const target = {{
            isVisible: async () => phase > 0,
            evaluate: async (fn) => String(fn).includes('transitionDuration') ? 0 : ({{
              aria_hidden: null, hidden: false, inert: false, hidden_ancestor: false,
              disabled: false, disabled_ancestor: false, pointer_events_none: false,
              in_viewport: true, hit_target: true,
              display: 'block', visibility: 'visible', opacity: '1', width: 320, height: 180,
              target_identity: {{ tag: 'div', role: 'dialog', accessible_name: 'Newsletter', class_signature: [],
                rect: {{ left: 0, top: 0, width: 320, height: 180 }}, semantic_key: 'dialog|newsletter' }},
            }}),
          }};
          const locator = {{ count: async () => phase, first: () => target }};
          const page = {{
            locator: (selector) => {{ if (selector !== '#newsletter-modal') throw new Error('wrong selector'); return locator; }},
            evaluate: async () => rows(phase ? '1' : '0'),
            waitForTimeout: async () => {{ phase = 1; }},
          }};
          const result = await m.applyManifestState(page, state, {{ sourceOnly: true,
            onAmbientAppearance: async () => {{ appearanceFrames += 1; }} }});
          return {{ appearanceFrames, evidence: result.trigger_evidence }};
        }})()"""
        result = node_value("browser_evidence.mjs", expression)
        self.assertEqual(1, result["appearanceFrames"])
        self.assertTrue(result["evidence"]["appearance_observed"])
        self.assertEqual(100, result["evidence"]["wait_ms"])
        self.assertNotEqual(
            result["evidence"]["before_sha256"], result["evidence"]["settled_sha256"]
        )

    def test_ambient_appearance_timeout_names_the_exact_source_recovery(self) -> None:
        state = {
            "id": "newsletter-appearance",
            "kind": "system",
            "trigger": {
                "type": "ambient",
                "target": "#newsletter-modal",
                "value": None,
                "wait_ms": 100,
            },
            "expectation": "Newsletter dialog appears without visitor input after the observed delay.",
        }
        expression = f"""(async () => {{
          const state = {json.dumps(state)};
          const page = {{
            locator: () => ({{ count: async () => 0 }}),
            evaluate: async () => [{{key:'page',tag:'div',properties:{{opacity:'1'}}}}],
            waitForTimeout: async (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
          }};
          try {{ await m.applyManifestState(page, state, {{sourceOnly:true}}); return null; }}
          catch (error) {{ return error.message; }}
        }})()"""
        message = node_value("browser_evidence.mjs", expression)
        self.assertIn("did not appear visibly", message)
        self.assertIn("100ms", message)
        self.assertIn("do not add an invented ambient state", message)

    def test_transient_fixed_surface_is_retained_at_mutation_callback_time(self) -> None:
        module_root = SKILL.parents[1] / "maintainer" / "node_modules"
        if not module_root.is_dir():
            self.skipTest("the maintained Playwright runtime is unavailable")
        watcher = (SCRIPTS / "source_surface_watch.mjs").resolve().as_uri()
        resolver = (SCRIPTS / "playwright_resolver.mjs").resolve().as_uri()
        program = f"""
          import {{ resolvePlaywright, discoverBrowserExecutable }} from {json.dumps(resolver)};
          import {{ startSourceSurfaceWatch, drainSourceSurfaceWatch, stopSourceSurfaceWatch }} from {json.dumps(watcher)};
          const loaded = resolvePlaywright({{ moduleUrl: import.meta.url }});
          const browserEntry = discoverBrowserExecutable(loaded.playwright);
          const browser = await loaded.playwright.chromium.launch({{ executablePath: browserEntry.file || browserEntry.path || browserEntry }});
          try {{
            const page = await browser.newPage({{ viewport: {{ width: 900, height: 600 }} }});
            await page.setContent('<main>clean</main>');
            const watch = await startSourceSurfaceWatch(page, {{ baseline: {{ video_t_s: 0 }}, captureEvidence: async (label) => ({{ label, video_t_s: 0 }}) }});
            await page.evaluate(() => {{
              const node = document.createElement('div');
              node.id = 'survey';
              node.style.cssText = 'position:fixed;inset:0;z-index:9999;background:#000';
              document.body.append(node); node.remove();
            }});
            await page.waitForTimeout(30);
            const report = await drainSourceSurfaceWatch(watch); await stopSourceSurfaceWatch(watch);
            const secondWatch = await startSourceSurfaceWatch(page); await stopSourceSurfaceWatch(secondWatch);
            const output = {{ kinds: report.events.map((event) => event.kind),
              callbacks: report.events.filter((event) => event.evidence.callback).length,
              added: report.mutation_batches.flatMap((batch) => batch.records.flatMap((record) => record.added || [])).length,
              removed: report.mutation_batches.flatMap((batch) => batch.records.flatMap((record) => record.removed || [])).length }};
            process.stdout.write(JSON.stringify(output));
          }} finally {{ await browser.close(); }}
        """
        env = os.environ.copy()
        env["DESIGN_DNA_PLAYWRIGHT_MODULE_DIR"] = str(module_root)
        done = subprocess.run(
            [NODE, "--input-type=module", "-e", program], capture_output=True,
            text=True, encoding="utf-8", env=env,
        )
        if done.returncode:
            self.fail(done.stderr or done.stdout)
        result = json.loads(done.stdout)
        self.assertIn("surface-node-added", result["kinds"])
        self.assertIn("surface-node-removed", result["kinds"])
        self.assertGreaterEqual(result["callbacks"], 2)
        self.assertGreaterEqual(result["added"], 1)
        self.assertGreaterEqual(result["removed"], 1)

    def test_css_transition_and_waapi_surface_activity_are_retained(self) -> None:
        module_root = SKILL.parents[1] / "maintainer" / "node_modules"
        if not module_root.is_dir():
            self.skipTest("the maintained Playwright runtime is unavailable")
        watcher = (SCRIPTS / "source_surface_watch.mjs").resolve().as_uri()
        resolver = (SCRIPTS / "playwright_resolver.mjs").resolve().as_uri()
        program = f"""
          import {{ resolvePlaywright, discoverBrowserExecutable }} from {json.dumps(resolver)};
          import {{ startSourceSurfaceWatch, drainSourceSurfaceWatch, stopSourceSurfaceWatch }} from {json.dumps(watcher)};
          const loaded = resolvePlaywright({{ moduleUrl: import.meta.url }});
          const entry = discoverBrowserExecutable(loaded.playwright);
          const browser = await loaded.playwright.chromium.launch({{ executablePath: entry.file || entry.path || entry }});
          try {{
            const page = await browser.newPage({{ viewport: {{ width: 900, height: 600 }} }});
            await page.setContent('<main>clean</main>');
            const watch = await startSourceSurfaceWatch(page, {{ baseline: {{ video_t_s: 0 }}, captureEvidence: async (label) => ({{ label, video_t_s: 0 }}) }});
            await page.evaluate(async () => {{
              const style = document.createElement('style');
              style.textContent = '#gate{{position:fixed;inset:0;z-index:9;opacity:1;transition:opacity 100ms linear}}#gate.fade{{opacity:.2}}';
              document.head.append(style);
              const node = document.createElement('div'); node.id = 'gate'; document.body.append(node);
              node.animate([{{transform:'scale(1)'}}, {{transform:'scale(.99)'}}], {{duration:80}});
              await new Promise(requestAnimationFrame); await new Promise(requestAnimationFrame); node.classList.add('fade');
            }});
            await page.waitForTimeout(180);
            const report = await drainSourceSurfaceWatch(watch); await stopSourceSurfaceWatch(watch);
            process.stdout.write(JSON.stringify({{ kinds: report.events.map((event) => event.kind), animation: report.animation_events.map((event) => event.event_type) }}));
          }} finally {{ await browser.close(); }}
        """
        env = os.environ.copy()
        env["DESIGN_DNA_PLAYWRIGHT_MODULE_DIR"] = str(module_root)
        done = subprocess.run([NODE, "--input-type=module", "-e", program], capture_output=True, text=True, encoding="utf-8", env=env)
        if done.returncode:
            self.fail(done.stderr or done.stdout)
        result = json.loads(done.stdout)
        self.assertIn("surface-waapi-active", result["kinds"])
        self.assertIn("surface-css-animation-event", result["kinds"])
        self.assertIn("transitionrun", result["animation"])

    def test_closed_shadow_transient_surface_is_retained_at_attach_time(self) -> None:
        module_root = SKILL.parents[1] / "maintainer" / "node_modules"
        if not module_root.is_dir():
            self.skipTest("the maintained Playwright runtime is unavailable")
        watcher = (SCRIPTS / "source_surface_watch.mjs").resolve().as_uri()
        resolver = (SCRIPTS / "playwright_resolver.mjs").resolve().as_uri()
        program = f"""
          import {{ resolvePlaywright, discoverBrowserExecutable }} from {json.dumps(resolver)};
          import {{ startSourceSurfaceWatch, drainSourceSurfaceWatch, stopSourceSurfaceWatch }} from {json.dumps(watcher)};
          const loaded = resolvePlaywright({{ moduleUrl: import.meta.url }});
          const entry = discoverBrowserExecutable(loaded.playwright);
          const browser = await loaded.playwright.chromium.launch({{ executablePath: entry.file || entry.path || entry }});
          try {{
            const page = await browser.newPage({{ viewport: {{ width: 900, height: 600 }} }});
            await page.setContent('<main>clean</main>');
            const watch = await startSourceSurfaceWatch(page, {{ baseline: {{ video_t_s: 0 }}, captureEvidence: async (label) => ({{ label, video_t_s: 0 }}) }});
            await page.evaluate(() => {{
              const host = document.createElement('div'); document.body.append(host);
              const root = host.attachShadow({{ mode: 'closed' }});
              const node = document.createElement('div'); node.id = 'survey';
              node.style.cssText = 'position:fixed;inset:0;z-index:99'; root.append(node); node.remove();
            }});
            await page.waitForTimeout(30);
            const report = await drainSourceSurfaceWatch(watch); await stopSourceSurfaceWatch(watch);
            process.stdout.write(JSON.stringify({{ kinds: report.events.map((event) => event.kind), ids: report.events.map((event) => event.surface?.id) }}));
          }} finally {{ await browser.close(); }}
        """
        env = os.environ.copy()
        env["DESIGN_DNA_PLAYWRIGHT_MODULE_DIR"] = str(module_root)
        done = subprocess.run([NODE, "--input-type=module", "-e", program], capture_output=True, text=True, encoding="utf-8", env=env)
        if done.returncode:
            self.fail(done.stderr or done.stdout)
        result = json.loads(done.stdout)
        self.assertIn("surface-node-added", result["kinds"])
        self.assertIn("surface-node-removed", result["kinds"])
        self.assertIn("survey", result["ids"])

    def test_declared_ambient_modal_is_grouped_at_its_owning_root(self) -> None:
        module_root = SKILL.parents[1] / "maintainer" / "node_modules"
        if not module_root.is_dir():
            self.skipTest("the maintained Playwright runtime is unavailable")
        watcher = (SCRIPTS / "source_surface_watch.mjs").resolve().as_uri()
        resolver = (SCRIPTS / "playwright_resolver.mjs").resolve().as_uri()
        program = f"""
          import {{ resolvePlaywright, discoverBrowserExecutable }} from {json.dumps(resolver)};
          import {{ startSourceSurfaceWatch, drainSourceSurfaceWatch, stopSourceSurfaceWatch }} from {json.dumps(watcher)};
          const loaded = resolvePlaywright({{ moduleUrl: import.meta.url }});
          const entry = discoverBrowserExecutable(loaded.playwright);
          const browser = await loaded.playwright.chromium.launch({{ executablePath: entry.file || entry.path || entry }});
          const finish = (value, code = 0) => process.stdout.write(JSON.stringify(value), () => {{
            browser.close().catch(() => {{}}); setTimeout(() => process.exit(code), 20);
          }});
          try {{
            const page = await browser.newPage({{ viewport: {{ width: 900, height: 600 }} }});
            await page.setContent('<main>clean</main>');
            const exact = '[role="dialog"][data-ff-el="modal"]';
            const watch = await startSourceSurfaceWatch(page, {{ ambientSelectors: [exact], baseline: {{ video_t_s: 0 }},
              captureEvidence: async (label) => ({{ label, video_t_s: 0 }}) }});
            await page.evaluate(() => {{
              const modal = document.createElement('div');
              modal.setAttribute('role', 'dialog'); modal.setAttribute('data-ff-el', 'modal');
              modal.style.cssText = 'position:fixed;inset:0;z-index:99';
              for (let index = 0; index < 48; index += 1) {{ const child = document.createElement('div'); child.className = 'modal-member'; modal.append(child); }}
              document.body.append(modal);
            }});
            await page.waitForTimeout(30);
            const report = await drainSourceSurfaceWatch(watch); await stopSourceSurfaceWatch(watch);
            finish({{ events: report.events.map((event) => ({{ kind:event.kind, selector:event.selector,
              declared_ambient:event.declared_ambient, root:event.surface?.data_ff_el,
              members:event.detail?.member_events?.length }})) }});
          }} catch (error) {{ finish({{ error: String(error?.message || error) }}, 1); }}
        """
        env = os.environ.copy()
        env["DESIGN_DNA_PLAYWRIGHT_MODULE_DIR"] = str(module_root)
        done = subprocess.run([NODE, "--input-type=module", "-e", program], capture_output=True,
                              text=True, encoding="utf-8", env=env, timeout=60)
        if done.returncode:
            self.fail(done.stderr or done.stdout)
        result = json.loads(done.stdout)
        self.assertNotIn("error", result)
        added = [event for event in result["events"] if event["kind"] == "surface-node-added"]
        self.assertEqual(1, len(added), result)
        self.assertEqual('[role="dialog"][data-ff-el="modal"]', added[0]["selector"])
        self.assertTrue(added[0]["declared_ambient"])
        self.assertEqual("modal", added[0]["root"])
        self.assertEqual(49, added[0]["members"])
        self.assertLessEqual(len(result["events"]), 2, result)

    def test_hidden_lexical_dialogs_do_not_become_early_candidates_before_visibility(self) -> None:
        """Static cart/mobile dialog markup is not an autonomous appearance."""
        module_root = SKILL.parents[1] / "maintainer" / "node_modules"
        if not module_root.is_dir():
            self.skipTest("the maintained Playwright runtime is unavailable")
        watcher = (SCRIPTS / "source_surface_watch.mjs").resolve().as_uri()
        resolver = (SCRIPTS / "playwright_resolver.mjs").resolve().as_uri()
        program = f"""
          import {{ resolvePlaywright, discoverBrowserExecutable }} from {json.dumps(resolver)};
          import {{ armEarlySourceSurfaceWatch, adoptEarlySourceSurfaceWatch, startSourceSurfaceWatch,
            drainSourceSurfaceWatch, stopSourceSurfaceWatch }} from {json.dumps(watcher)};
          const loaded = resolvePlaywright({{ moduleUrl: import.meta.url }});
          const entry = discoverBrowserExecutable(loaded.playwright);
          const browser = await loaded.playwright.chromium.launch({{ executablePath: entry.file || entry.path || entry }});
          const finish = (value, code = 0) => process.stdout.write(JSON.stringify(value), () => {{
            browser.close().catch(() => {{}}); setTimeout(() => process.exit(code), 20);
          }});
          try {{
            const page = await browser.newPage({{ viewport: {{ width: 900, height: 600 }} }});
            const html = `<main>Farm source fixture</main>
              <aside id="cart" role="dialog" aria-modal="true" style="visibility:hidden;position:fixed;inset:0;z-index:99">Cart</aside>
              <aside id="mobile-menu" role="dialog" aria-modal="true" style="visibility:hidden;position:fixed;inset:0;z-index:98">Menu</aside>`;
            const early = await armEarlySourceSurfaceWatch(page, {{ baseline: {{ video_t_s: 0 }},
              captureEvidence: async (label) => ({{ label, video_t_s: 0 }}) }});
            await page.goto('data:text/html,' + encodeURIComponent(html));
            await page.waitForTimeout(100);
            const initialWatch = await adoptEarlySourceSurfaceWatch(page, early, {{ baseline: {{ video_t_s: 1 }},
              captureEvidence: async (label) => ({{ label, video_t_s: 1 }}) }});
            await page.waitForTimeout(100);
            const initial = await drainSourceSurfaceWatch(initialWatch); await stopSourceSurfaceWatch(initialWatch);
            const shownWatch = await startSourceSurfaceWatch(page, {{ ambientSelectors: ['#cart'], baseline: {{ video_t_s: 2 }},
              captureEvidence: async (label) => ({{ label, video_t_s: 2 }}) }});
            await page.evaluate(() => {{ document.querySelector('#cart').style.visibility = 'visible'; }});
            await page.waitForTimeout(100);
            const shown = await drainSourceSurfaceWatch(shownWatch); await stopSourceSurfaceWatch(shownWatch);
            finish({{
              initialEvents: initial.events.map((event) => ({{ kind:event.kind, id:event.surface?.id, selector:event.selector }})),
              initialInventories: initial.animation_samples.map((sample) => sample.candidate_inventory),
              shownEvents: shown.events.map((event) => ({{ kind:event.kind, id:event.surface?.id, selector:event.selector }})),
            }});
          }} catch (error) {{ finish({{ error: String(error?.message || error), code:error?.code || null }}, 1); }}
        """
        env = os.environ.copy()
        env["DESIGN_DNA_PLAYWRIGHT_MODULE_DIR"] = str(module_root)
        done = subprocess.run([NODE, "--input-type=module", "-e", program], capture_output=True,
                              text=True, encoding="utf-8", env=env, timeout=60)
        if done.returncode:
            self.fail(done.stderr or done.stdout)
        result = json.loads(done.stdout)
        self.assertNotIn("error", result)
        self.assertEqual([], result["initialEvents"])
        self.assertTrue(all(inventory == [] for inventory in result["initialInventories"]), result)
        appeared = [event for event in result["shownEvents"] if event["kind"] == "autonomous-surface-appeared"]
        self.assertEqual([{"kind": "autonomous-surface-appeared", "id": "cart", "selector": "#cart"}], appeared)
        self.assertNotIn("mobile-menu", [event["id"] for event in result["shownEvents"]])

    def test_early_watcher_ignores_unsettled_dialog_markup_hidden_before_dom_ready(self) -> None:
        """A streamed, unstyled setup dialog is not a visitor-facing transient."""
        module_root = SKILL.parents[1] / "maintainer" / "node_modules"
        if not module_root.is_dir():
            self.skipTest("the maintained Playwright runtime is unavailable")
        watcher = (SCRIPTS / "source_surface_watch.mjs").resolve().as_uri()
        resolver = (SCRIPTS / "playwright_resolver.mjs").resolve().as_uri()
        program = f"""
          import http from 'node:http';
          import {{ resolvePlaywright, discoverBrowserExecutable }} from {json.dumps(resolver)};
          import {{ armEarlySourceSurfaceWatch, adoptEarlySourceSurfaceWatch,
            drainSourceSurfaceWatch, stopSourceSurfaceWatch }} from {json.dumps(watcher)};
          const server = http.createServer((request, response) => {{
            response.writeHead(200, {{ 'content-type': 'text/html' }});
            response.write('<main>streaming source fixture</main><div id="setup-dialog" role="dialog" aria-modal="true" style="position:fixed;inset:0;z-index:99">setup</div>');
            setTimeout(() => response.end('<style>#setup-dialog{{visibility:hidden;opacity:0}}</style>'), 120);
          }});
          await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
          const loaded = resolvePlaywright({{ moduleUrl: import.meta.url }});
          const entry = discoverBrowserExecutable(loaded.playwright);
          const browser = await loaded.playwright.chromium.launch({{ executablePath: entry.file || entry.path || entry }});
          const finish = (value, code = 0) => process.stdout.write(JSON.stringify(value), () => {{
            browser.close().catch(() => {{}}); server.close(); setTimeout(() => process.exit(code), 20);
          }});
          let early = null; let watch = null;
          try {{
            const page = await browser.newPage({{ viewport: {{ width: 900, height: 600 }} }});
            const captureEvidence = async (label) => ({{ label, video_t_s: 0 }});
            early = await armEarlySourceSurfaceWatch(page, {{ baseline: {{ video_t_s: 0 }}, captureEvidence }});
            await page.goto(`http://127.0.0.1:${{server.address().port}}/`, {{ waitUntil: 'domcontentloaded' }});
            watch = await adoptEarlySourceSurfaceWatch(page, early, {{ baseline: {{ video_t_s: 1 }}, captureEvidence }}); early = null;
            await page.waitForTimeout(100);
            const report = await drainSourceSurfaceWatch(watch); await stopSourceSurfaceWatch(watch); watch = null;
            const computed = await page.evaluate(() => {{ const style = getComputedStyle(document.querySelector('#setup-dialog')); return {{ visibility: style.visibility, opacity: style.opacity }}; }});
            finish({{ events: report.events, inventories: report.animation_samples.map((sample) => sample.candidate_inventory), computed }});
          }} catch (error) {{ finish({{ error: String(error?.message || error), code: error?.code || null }}, 1); }}
          finally {{ if (watch) await stopSourceSurfaceWatch(watch).catch(() => {{}}); if (early) await stopSourceSurfaceWatch(early).catch(() => {{}}); }}
        """
        env = os.environ.copy()
        env["DESIGN_DNA_PLAYWRIGHT_MODULE_DIR"] = str(module_root)
        done = subprocess.run([NODE, "--input-type=module", "-e", program], capture_output=True,
                              text=True, encoding="utf-8", env=env, timeout=60)
        if done.returncode:
            self.fail(done.stderr or done.stdout)
        result = json.loads(done.stdout)
        self.assertNotIn("error", result)
        self.assertEqual({"visibility": "hidden", "opacity": "0"}, result["computed"])
        self.assertEqual([], result["events"])
        self.assertTrue(all(inventory == [] for inventory in result["inventories"]), result)

    def test_identical_magnetic_anchors_keep_distinct_hover_identity_without_weakening_loop_guard(self) -> None:
        module_root = SKILL.parents[1] / "maintainer" / "node_modules"
        if not module_root.is_dir():
            self.skipTest("the maintained Playwright runtime is unavailable")
        observer = (SCRIPTS / "observe_reference.mjs").resolve().as_uri()
        resolver = (SCRIPTS / "playwright_resolver.mjs").resolve().as_uri()
        controller = (SCRIPTS / "source_study_controller.mjs").resolve().as_uri()
        program = f"""
          import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path';
          import {{ hoverTargetIdentity }} from {json.dumps(observer)};
          import {{ resolvePlaywright, discoverBrowserExecutable }} from {json.dumps(resolver)};
          import {{ createSourceStudyController }} from {json.dumps(controller)};
          const loaded = resolvePlaywright({{ moduleUrl: import.meta.url }});
          const entry = discoverBrowserExecutable(loaded.playwright);
          const browser = await loaded.playwright.chromium.launch({{ executablePath: entry.file || entry.path || entry }});
          const root = fs.mkdtempSync(path.join(os.tmpdir(), 'dna-hover-identity-'));
          try {{
            const page = await browser.newPage();
            await page.setContent('<nav>' + Array.from({{length:6}}, () => '<a class="magnetic">Shop</a>').join('') + '</nav>');
            const anchors = await page.locator('a').all();
            const identities = await Promise.all(anchors.map((anchor) => anchor.evaluate(hoverTargetIdentity)));
            const study = createSourceStudyController({{ output_dir: root, id: 'distinct-targets', producer: 'fixture.mjs',
              limits: {{ max_consecutive_target_repeats: 3, max_total_target_visits_per_key: 12, max_repeated_target_edge_visits: 6 }} }});
            for (const identity of identities) study.markTarget(`wide|primary-hover|fixture|${{identity}}`);
            const target_count = study.state.counters.targets;
            study.terminate('fixture-finished', 'Synthetic controller cleanup.');
            const repeated = createSourceStudyController({{ output_dir: path.join(root, 'repeat'), id: 'same-target', producer: 'fixture.mjs',
              limits: {{ max_consecutive_target_repeats: 3, max_total_target_visits_per_key: 12, max_repeated_target_edge_visits: 6 }} }});
            let loop_code = null;
            try {{ for (let index = 0; index < 4; index += 1) repeated.markTarget(`wide|primary-hover|fixture|${{identities[0]}}`); }}
            catch (error) {{ loop_code = error.code || null; }}
            process.stdout.write(JSON.stringify({{ identities, target_count, loop_code }}));
          }} finally {{ await browser.close(); fs.rmSync(root, {{ recursive:true, force:true }}); }}
        """
        env = os.environ.copy()
        env["DESIGN_DNA_PLAYWRIGHT_MODULE_DIR"] = str(module_root)
        done = subprocess.run([NODE, "--input-type=module", "-e", program], capture_output=True,
                              text=True, encoding="utf-8", env=env, timeout=60)
        if done.returncode:
            self.fail(done.stderr or done.stdout)
        result = json.loads(done.stdout)
        self.assertEqual(6, len(set(result["identities"])), result)
        self.assertNotIn("a|||", result["identities"])
        self.assertEqual(6, result["target_count"])
        self.assertEqual("source-study-repeated-target-loop", result["loop_code"])
        observer_text = (SCRIPTS / "observe_reference.mjs").read_text(encoding="utf-8")
        self.assertIn("hover-discovery:wide-primary", observer_text)
        self.assertIn("hover-preflight:wide-primary", observer_text)
        self.assertIn("for (const [candidateOrdinal, { frame, el }] of targets.entries())", observer_text)

    def test_early_to_normal_surface_watch_has_one_timestamp_lineage(self) -> None:
        module_root = SKILL.parents[1] / "maintainer" / "node_modules"
        if not module_root.is_dir():
            self.skipTest("the maintained Playwright runtime is unavailable")
        watcher = (SCRIPTS / "source_surface_watch.mjs").resolve().as_uri()
        resolver = (SCRIPTS / "playwright_resolver.mjs").resolve().as_uri()
        program = f"""
          import {{ resolvePlaywright, discoverBrowserExecutable }} from {json.dumps(resolver)};
          import {{ armEarlySourceSurfaceWatch, adoptEarlySourceSurfaceWatch, drainSourceSurfaceWatch, stopSourceSurfaceWatch }} from {json.dumps(watcher)};
          const loaded = resolvePlaywright({{ moduleUrl: import.meta.url }});
          const entry = discoverBrowserExecutable(loaded.playwright);
          const browser = await loaded.playwright.chromium.launch({{ executablePath: entry.file || entry.path || entry }});
          const finish = (value, code = 0) => process.stdout.write(JSON.stringify(value), () => {{
            browser.close().catch(() => {{}}); setTimeout(() => process.exit(code), 20);
          }});
          try {{
            const page = await browser.newPage({{ viewport: {{ width: 900, height: 600 }} }});
            const exact = '#newsletter';
            const early = await armEarlySourceSurfaceWatch(page, {{ ambientSelectors:[exact], baseline:{{ video_t_s:0 }},
              captureEvidence:async (label) => ({{ label, video_t_s:0 }}) }});
            await page.goto(`data:text/html,<main>first visit</main><script>setTimeout(() => {{ const modal=document.createElement('div'); modal.id='newsletter'; modal.setAttribute('role','dialog'); modal.style.cssText='position:fixed;inset:0;z-index:9'; document.body.append(modal); }}, 10)</script>`);
            await page.waitForTimeout(35);
            const watch = await adoptEarlySourceSurfaceWatch(page, early, {{ ambientSelectors:[exact], baseline:{{ video_t_s:1 }},
              captureEvidence:async (label) => ({{ label, video_t_s:1 }}) }});
            await page.waitForTimeout(20);
            const report = await drainSourceSurfaceWatch(watch); await stopSourceSurfaceWatch(watch);
            finish({{ early:report.early_watch, events:report.events.map((event) => ({{ id:event.event_id, elapsed:event.elapsed_ms,
              phase:event.detail.watch_phase, selector:event.selector }})), gaps:report.sample_gap_failures }});
          }} catch (error) {{ finish({{ error:String(error?.message || error) }}, 1); }}
        """
        env = os.environ.copy()
        env["DESIGN_DNA_PLAYWRIGHT_MODULE_DIR"] = str(module_root)
        done = subprocess.run([NODE, "--input-type=module", "-e", program], capture_output=True,
                              text=True, encoding="utf-8", env=env, timeout=60)
        if done.returncode:
            self.fail(done.stderr or done.stdout)
        result = json.loads(done.stdout)
        self.assertNotIn("error", result)
        self.assertEqual({"from": "early", "to": "normal", "gap_ms": 0, "atomic": True}, result["early"]["handoff"])
        self.assertTrue(result["events"])
        self.assertEqual(len({item["id"] for item in result["events"]}), len(result["events"]))
        self.assertTrue(all(item["selector"] == "#newsletter" for item in result["events"]))
        self.assertTrue(any(item["phase"] == "early" for item in result["events"]))
        self.assertEqual([], result["gaps"])

    def test_multiple_sequential_early_normal_watches_do_not_reuse_or_lose_a_watch(self) -> None:
        module_root = SKILL.parents[1] / "maintainer" / "node_modules"
        if not module_root.is_dir():
            self.skipTest("the maintained Playwright runtime is unavailable")
        watcher = (SCRIPTS / "source_surface_watch.mjs").resolve().as_uri()
        resolver = (SCRIPTS / "playwright_resolver.mjs").resolve().as_uri()
        program = f"""
          import {{ resolvePlaywright, discoverBrowserExecutable }} from {json.dumps(resolver)};
          import {{ armEarlySourceSurfaceWatch, adoptEarlySourceSurfaceWatch, drainSourceSurfaceWatch, stopSourceSurfaceWatch }} from {json.dumps(watcher)};
          const loaded = resolvePlaywright({{ moduleUrl: import.meta.url }});
          const entry = discoverBrowserExecutable(loaded.playwright);
          const browser = await loaded.playwright.chromium.launch({{ executablePath: entry.file || entry.path || entry }});
          const finish = (value, code = 0) => process.stdout.write(JSON.stringify(value), () => {{
            browser.close().catch(() => {{}}); setTimeout(() => process.exit(code), 20);
          }});
          try {{
            const page = await browser.newPage({{ viewport: {{ width: 900, height: 600 }} }});
            async function pass(name) {{
              const selector = `#${{name}}-modal`;
              const early = await armEarlySourceSurfaceWatch(page, {{ ambientSelectors:[selector], baseline:{{ video_t_s:0 }},
                captureEvidence:async (label) => ({{ label, video_t_s:0 }}) }});
              await page.goto(`data:text/html,<main>${{name}}</main><script>setTimeout(() => {{ const modal=document.createElement('div'); modal.id='${{name}}-modal'; modal.setAttribute('role','dialog'); modal.style.cssText='position:fixed;inset:0;z-index:9'; document.body.append(modal); }}, 10)</script>`);
              await page.waitForTimeout(35);
              const watch = await adoptEarlySourceSurfaceWatch(page, early, {{ ambientSelectors:[selector], baseline:{{ video_t_s:1 }},
                captureEvidence:async (label) => ({{ label, video_t_s:1 }}) }});
              await page.waitForTimeout(20);
              const report = await drainSourceSurfaceWatch(watch); await stopSourceSurfaceWatch(watch);
              return {{ selector, ids:report.events.map((event) => event.event_id), selectors:report.events.map((event) => event.selector), handoff:report.early_watch?.handoff }};
            }}
            const first = await pass('first'); const second = await pass('second');
            finish({{ first, second }});
          }} catch (error) {{ finish({{ error:String(error?.message || error), code:error?.code || null }}, 1); }}
        """
        env = os.environ.copy()
        env["DESIGN_DNA_PLAYWRIGHT_MODULE_DIR"] = str(module_root)
        done = subprocess.run([NODE, "--input-type=module", "-e", program], capture_output=True,
                              text=True, encoding="utf-8", env=env, timeout=60)
        if done.returncode:
            self.fail(done.stderr or done.stdout)
        result = json.loads(done.stdout)
        self.assertNotIn("error", result)
        self.assertEqual({"from": "early", "to": "normal", "gap_ms": 0, "atomic": True}, result["first"]["handoff"])
        self.assertEqual({"from": "early", "to": "normal", "gap_ms": 0, "atomic": True}, result["second"]["handoff"])
        self.assertTrue(result["first"]["ids"])
        self.assertTrue(result["second"]["ids"])
        self.assertTrue(all(value == "#first-modal" for value in result["first"]["selectors"]))
        self.assertTrue(all(value == "#second-modal" for value in result["second"]["selectors"]))
        self.assertFalse(set(result["first"]["ids"]) & set(result["second"]["ids"]))

    def test_document_replacement_is_typed_capture_integrity_not_raw_evaluate_error(self) -> None:
        module_root = SKILL.parents[1] / "maintainer" / "node_modules"
        if not module_root.is_dir():
            self.skipTest("the maintained Playwright runtime is unavailable")
        watcher = (SCRIPTS / "source_surface_watch.mjs").resolve().as_uri()
        resolver = (SCRIPTS / "playwright_resolver.mjs").resolve().as_uri()
        program = f"""
          import {{ resolvePlaywright, discoverBrowserExecutable }} from {json.dumps(resolver)};
          import {{ startSourceSurfaceWatch, drainSourceSurfaceWatch, stopSourceSurfaceWatch }} from {json.dumps(watcher)};
          const loaded = resolvePlaywright({{ moduleUrl: import.meta.url }});
          const entry = discoverBrowserExecutable(loaded.playwright);
          const browser = await loaded.playwright.chromium.launch({{ executablePath: entry.file || entry.path || entry }});
          const finish = (value, code = 0) => process.stdout.write(JSON.stringify(value), () => {{
            browser.close().catch(() => {{}}); setTimeout(() => process.exit(code), 20);
          }});
          try {{
            const page = await browser.newPage(); await page.setContent('<main>before</main>');
            const watch = await startSourceSurfaceWatch(page, {{ baseline:{{ video_t_s:0 }}, captureEvidence:async () => ({{ video_t_s:0 }}) }});
            await page.goto('data:text/html,<main>after</main>');
            let result;
            try {{ await drainSourceSurfaceWatch(watch); result = {{ unexpected:true }}; }}
            catch (error) {{ result = {{ code:error.code, message:String(error.message), integrity:error.capture_integrity }}; }}
            await stopSourceSurfaceWatch(watch); finish(result);
          }} catch (error) {{ finish({{ error:String(error?.message || error) }}, 1); }}
        """
        env = os.environ.copy()
        env["DESIGN_DNA_PLAYWRIGHT_MODULE_DIR"] = str(module_root)
        done = subprocess.run([NODE, "--input-type=module", "-e", program], capture_output=True,
                              text=True, encoding="utf-8", env=env, timeout=60)
        if done.returncode:
            self.fail(done.stderr or done.stdout)
        result = json.loads(done.stdout)
        self.assertEqual("source-surface-watch-document-replaced", result["code"])
        self.assertIn("expected", result["message"])
        self.assertNotIn("page.evaluate", result["message"])
        self.assertTrue(result["integrity"]["expected_document_url"])
        self.assertTrue(result["integrity"]["current_document_url"].startswith("data:text/html,"))

    def test_one_navigation_early_watch_covers_the_final_redirect_document(self) -> None:
        module_root = SKILL.parents[1] / "maintainer" / "node_modules"
        if not module_root.is_dir():
            self.skipTest("the maintained Playwright runtime is unavailable")
        watcher = (SCRIPTS / "source_surface_watch.mjs").resolve().as_uri()
        resolver = (SCRIPTS / "playwright_resolver.mjs").resolve().as_uri()
        program = f"""
          import http from 'node:http';
          import {{ resolvePlaywright, discoverBrowserExecutable }} from {json.dumps(resolver)};
          import {{ armEarlySourceSurfaceWatch, adoptEarlySourceSurfaceWatch, drainSourceSurfaceWatch, stopSourceSurfaceWatch }} from {json.dumps(watcher)};
          const server = http.createServer((request, response) => {{
            if (request.url === '/redirect') {{ response.writeHead(302, {{ location:'/landing' }}); response.end(); return; }}
            response.writeHead(200, {{ 'content-type':'text/html' }});
            response.end(`<main>landing</main><script>setTimeout(() => {{ const modal=document.createElement('div'); modal.id='newsletter'; modal.setAttribute('role','dialog'); modal.style.cssText='position:fixed;inset:0;z-index:9'; document.body.append(modal); }}, 10)</script>`);
          }});
          await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
          const port = server.address().port;
          const loaded = resolvePlaywright({{ moduleUrl: import.meta.url }});
          const entry = discoverBrowserExecutable(loaded.playwright);
          const browser = await loaded.playwright.chromium.launch({{ executablePath: entry.file || entry.path || entry }});
          const finish = (value, code = 0) => process.stdout.write(JSON.stringify(value), () => {{
            browser.close().catch(() => {{}}); server.close(); setTimeout(() => process.exit(code), 20);
          }});
          try {{
            const page = await browser.newPage(); const selector='#newsletter';
            const early = await armEarlySourceSurfaceWatch(page, {{ ambientSelectors:[selector], baseline:{{ video_t_s:0 }}, captureEvidence:async () => ({{ video_t_s:0 }}) }});
            await page.goto(`http://127.0.0.1:${{port}}/redirect`); await page.waitForTimeout(35);
            const watch = await adoptEarlySourceSurfaceWatch(page, early, {{ ambientSelectors:[selector], baseline:{{ video_t_s:1 }}, captureEvidence:async () => ({{ video_t_s:1 }}) }});
            await page.waitForTimeout(40);
            const report = await drainSourceSurfaceWatch(watch); await stopSourceSurfaceWatch(watch);
            finish({{ url:page.url(), handoff:report.early_watch?.handoff, selectors:report.events.map((event) => event.selector) }});
          }} catch (error) {{ finish({{ error:String(error?.message || error), code:error?.code || null }}, 1); }}
        """
        env = os.environ.copy()
        env["DESIGN_DNA_PLAYWRIGHT_MODULE_DIR"] = str(module_root)
        done = subprocess.run([NODE, "--input-type=module", "-e", program], capture_output=True,
                              text=True, encoding="utf-8", env=env, timeout=60)
        if done.returncode:
            self.fail(done.stderr or done.stdout)
        result = json.loads(done.stdout)
        self.assertNotIn("error", result)
        self.assertTrue(result["url"].endswith("/landing"))
        self.assertEqual({"from": "early", "to": "normal", "gap_ms": 0, "atomic": True}, result["handoff"])
        self.assertTrue(result["selectors"])
        self.assertTrue(all(value == "#newsletter" for value in result["selectors"]))

    def test_ambient_target_rejects_disabled_pointer_occluded_and_shadow_hidden_presence(self) -> None:
        resolver_uri = (SCRIPTS / "playwright_resolver.mjs").resolve().as_uri()
        evidence_uri = (SCRIPTS / "browser_evidence.mjs").resolve().as_uri()
        script = f"""
          import * as resolver from {json.dumps(resolver_uri)};
          import * as evidence from {json.dumps(evidence_uri)};
          const loaded = resolver.resolvePlaywright({{moduleUrl:{json.dumps(resolver_uri)}}});
          const browserInfo = resolver.discoverBrowserExecutable(loaded.playwright);
          const browser = await loaded.playwright.chromium.launch({{executablePath:browserInfo.file}});
          const context = await browser.newContext({{viewport:{{width:800,height:500}}}});
          const failures = [];
          async function attempt(name, html, selector, reveal) {{
            const page = await context.newPage();
            try {{
              await page.setContent(html);
              await page.evaluate(reveal);
              const state = {{id:name,kind:'system',trigger:{{type:'ambient',target:selector,value:null,wait_ms:350}},expectation:name + ' appears'}};
              try {{ await evidence.applyManifestState(page,state,{{sourceOnly:true}}); failures.push({{name,accepted:true}}); }}
              catch (error) {{ failures.push({{name,accepted:false,message:error.message}}); }}
            }} finally {{ await page.close(); }}
          }}
          try {{
            await attempt('aria-disabled','<div id="target" role="dialog" aria-disabled="true" style="display:none;width:200px;height:100px"></div>','#target',() => setTimeout(() => document.querySelector('#target').style.display='block',20));
            await attempt('pointer-none','<div id="target" role="dialog" style="display:none;pointer-events:none;width:200px;height:100px"></div>','#target',() => setTimeout(() => document.querySelector('#target').style.display='block',20));
            await attempt('occluded','<div id="target" role="dialog" style="display:none;position:fixed;inset:80px;width:200px;height:100px;background:white"></div><div id="cover" style="display:none;position:fixed;inset:0;z-index:5"></div>','#target',() => setTimeout(() => {{document.querySelector('#target').style.display='block';document.querySelector('#cover').style.display='block';}},20));
            await attempt('shadow-hidden','<x-modal id="host" aria-hidden="true"></x-modal>','x-modal #target',() => {{ const root=document.querySelector('#host').attachShadow({{mode:'open'}}); root.innerHTML='<div id="target" role="dialog" style="display:none;width:200px;height:100px"></div>'; setTimeout(()=>root.querySelector('#target').style.display='block',20); }});
            process.stdout.write(JSON.stringify(failures));
          }} finally {{ await context.close(); await browser.close(); }}
        """
        done = subprocess.run(
            [NODE, "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        if done.returncode:
            combined = done.stderr + done.stdout
            if "playwright-unavailable" in combined.lower() or "browser-executable-unavailable" in combined.lower():
                self.skipTest("Real ambient actionability test requires the configured Playwright browser")
            self.fail(combined)
        result = json.loads(done.stdout)
        self.assertEqual(["aria-disabled", "pointer-none", "occluded", "shadow-hidden"], [item["name"] for item in result])
        self.assertTrue(all(not item["accepted"] for item in result), result)
        self.assertTrue(all("did not appear visibly" in item["message"] for item in result), result)

    def test_delayed_dialog_is_continuously_detected_as_an_unbound_build_surface(self) -> None:
        resolver_uri = (SCRIPTS / "playwright_resolver.mjs").resolve().as_uri()
        scanner_uri = (SCRIPTS / "scan_build_components.mjs").resolve().as_uri()
        script = f"""
          import * as resolver from {json.dumps(resolver_uri)};
          import * as scanner from {json.dumps(scanner_uri)};
          const loaded = resolver.resolvePlaywright({{moduleUrl:{json.dumps(resolver_uri)}}});
          const browserInfo = resolver.discoverBrowserExecutable(loaded.playwright);
          const browser = await loaded.playwright.chromium.launch({{executablePath:browserInfo.file}});
          const context = await browser.newContext({{viewport:{{width:900,height:600}}}});
          const page = await context.newPage();
          try {{
            await page.setContent('<main><h1>Settled build</h1></main><div id="late" role="dialog" aria-modal="true" class="newsletter-popup" style="display:none;position:fixed;inset:0;background:white">Late dialog</div>');
            const initial = await page.evaluate(scanner.AUTONOMOUS_MONITOR_START);
            await page.evaluate(() => setTimeout(() => document.querySelector('#late').style.display='block', 180));
            await page.waitForTimeout(550);
            const stopped = await page.evaluate(scanner.AUTONOMOUS_MONITOR_STOP);
            const before = new Set(initial.surfaces.map((surface) => surface.key));
            const late = stopped.final.surfaces.filter((surface) => !before.has(surface.key));
            const rest = {{id:'rest',kind:'rest',trigger:{{type:'none',target:'document',value:null}}}};
            const sourceRest = {{trigger:{{type:'none',target:'document',value:null}}}};
            process.stdout.write(JSON.stringify({{
              late, mutationCount: stopped.mutations.length,
              sourceBound: late.every((surface) => scanner.autonomousSurfaceHasSourceBinding(surface,rest,sourceRest)),
            }}));
          }} finally {{ await context.close(); await browser.close(); }}
        """
        done = subprocess.run(
            [NODE, "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        if done.returncode:
            combined = done.stderr + done.stdout
            if "playwright-unavailable" in combined.lower() or "browser-executable-unavailable" in combined.lower():
                self.skipTest("Real delayed-dialog test requires the configured Playwright browser")
            self.fail(combined)
        result = json.loads(done.stdout)
        self.assertGreaterEqual(result["mutationCount"], 1)
        self.assertEqual(1, len(result["late"]))
        self.assertEqual("dialog", result["late"][0]["role"])
        self.assertFalse(result["sourceBound"])

    def test_first_visit_transient_surface_is_captured_before_scanner_navigation_settles(self) -> None:
        resolver_uri = (SCRIPTS / "playwright_resolver.mjs").resolve().as_uri()
        scanner_uri = (SCRIPTS / "scan_build_components.mjs").resolve().as_uri()
        script = f"""
          import * as resolver from {json.dumps(resolver_uri)};
          import * as scanner from {json.dumps(scanner_uri)};
          const loaded = resolver.resolvePlaywright({{moduleUrl:{json.dumps(resolver_uri)}}});
          const browserInfo = resolver.discoverBrowserExecutable(loaded.playwright);
          const browser = await loaded.playwright.chromium.launch({{executablePath:browserInfo.file}});
          const context = await browser.newContext();
          const callbacks = [];
          await context.exposeBinding('__designDnaAutonomousEarlyCallback', async (_source, event) => callbacks.push(event));
          await context.addInitScript(scanner.AUTONOMOUS_EARLY_INIT);
          const page = await context.newPage();
          try {{
            await page.goto('data:text/html,<main>first visit</main>');
            await page.evaluate(() => setTimeout(() => {{ const dialog=document.createElement('div'); dialog.id='survey'; dialog.setAttribute('role','dialog'); dialog.innerHTML='<button>Continue</button>'; document.body.append(dialog); dialog.remove(); }}, 40));
            await page.waitForTimeout(180);
            const early = await page.evaluate(() => window.__designDnaAutonomousEarlyWatch.events);
            process.stdout.write(JSON.stringify({{callbacks,early}}));
          }} finally {{ await context.close(); await browser.close(); }}
        """
        done = subprocess.run(
            [NODE, "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        if done.returncode:
            combined = done.stderr + done.stdout
            if "playwright-unavailable" in combined.lower() or "browser-executable-unavailable" in combined.lower():
                self.skipTest("Real first-visit monitor test requires the configured Playwright browser")
            self.fail(combined)
        result = json.loads(done.stdout)
        self.assertTrue(result["callbacks"], result)
        candidates = [
            candidate
            for event in result["early"]
            for candidate in [*event.get("added", []), *event.get("removed", [])]
            if candidate.get("id") == "survey"
        ]
        self.assertTrue(candidates, result)

    def test_scanner_monitor_retains_preexisting_hidden_survey_style_class_transient(self) -> None:
        """A pre-existing generic node must not disappear from the audit when it opens then recloses."""
        resolver_uri = (SCRIPTS / "playwright_resolver.mjs").resolve().as_uri()
        scanner_uri = (SCRIPTS / "scan_build_components.mjs").resolve().as_uri()
        script = f"""
          import * as resolver from {json.dumps(resolver_uri)};
          import * as scanner from {json.dumps(scanner_uri)};
          const loaded = resolver.resolvePlaywright({{moduleUrl:{json.dumps(resolver_uri)}}});
          const browserInfo = resolver.discoverBrowserExecutable(loaded.playwright);
          const browser = await loaded.playwright.chromium.launch({{executablePath:browserInfo.file}});
          const context = await browser.newContext({{viewport:{{width:900,height:600}}}});
          const page = await context.newPage();
          try {{
            await page.setContent('<main>Settled build</main><div id="survey" style="display:none;position:fixed;inset:0;z-index:99;background:white"></div>');
            const initial = await page.evaluate(scanner.AUTONOMOUS_MONITOR_START);
            await page.evaluate(async () => {{
              const survey = document.querySelector('#survey');
              survey.classList.add('is-open'); survey.style.display = 'block';
              await new Promise((resolve) => setTimeout(resolve, 90));
              survey.classList.remove('is-open'); survey.style.display = 'none';
            }});
            await page.waitForTimeout(120);
            const stopped = await page.evaluate(scanner.AUTONOMOUS_MONITOR_STOP);
            const changes = stopped.mutations.flatMap((batch) => batch.changes);
            process.stdout.write(JSON.stringify({{
              initialVisible: initial.surfaces.some((surface) => surface.id === 'survey'),
              finalVisible: stopped.final.surfaces.some((surface) => surface.id === 'survey'),
              visibleAtCallback: stopped.mutations.some((batch) => batch.surfaces.some((surface) => surface.id === 'survey')),
              changes: changes.filter((change) => change.target?.id === 'survey').map((change) => ({{
                attribute: change.attribute, candidate: change.target?.candidate,
              }})),
            }}));
          }} finally {{ await context.close(); await browser.close(); }}
        """
        done = subprocess.run(
            [NODE, "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        if done.returncode:
            combined = done.stderr + done.stdout
            if "playwright-unavailable" in combined.lower() or "browser-executable-unavailable" in combined.lower():
                self.skipTest("Real scanner-monitor test requires the configured Playwright browser")
            self.fail(combined)
        result = json.loads(done.stdout)
        self.assertFalse(result["initialVisible"], result)
        self.assertFalse(result["finalVisible"], result)
        self.assertTrue(result["visibleAtCallback"], result)
        self.assertTrue(all(change["candidate"] for change in result["changes"]), result)
        self.assertIn("class", [change["attribute"] for change in result["changes"]])
        self.assertIn("style", [change["attribute"] for change in result["changes"]])

    def test_scanner_monitor_never_injects_audit_identity_into_the_build_dom(self) -> None:
        resolver_uri = (SCRIPTS / "playwright_resolver.mjs").resolve().as_uri()
        scanner_uri = (SCRIPTS / "scan_build_components.mjs").resolve().as_uri()
        script = f"""
          import * as resolver from {json.dumps(resolver_uri)};
          import * as scanner from {json.dumps(scanner_uri)};
          const loaded = resolver.resolvePlaywright({{moduleUrl:{json.dumps(resolver_uri)}}});
          const browserInfo = resolver.discoverBrowserExecutable(loaded.playwright);
          const browser = await loaded.playwright.chromium.launch({{executablePath:browserInfo.file}});
          const context = await browser.newContext({{viewport:{{width:900,height:600}}}});
          const page = await context.newPage();
          try {{
            await page.setContent('<main>Settled build</main><div id="survey" style="display:none;position:fixed;inset:0;z-index:99"></div>');
            await page.evaluate(() => {{
              window.__auditIdentityWrites = [];
              new MutationObserver((records) => {{
                for (const record of records) window.__auditIdentityWrites.push({{
                  attribute: record.attributeName, id: record.target.id || null,
                }});
              }}).observe(document, {{subtree:true, attributes:true,
                attributeFilter:['data-design-dna-autonomous-surface-id']}});
            }});
            await page.evaluate(scanner.AUTONOMOUS_MONITOR_START);
            await page.evaluate(() => {{
              const survey = document.querySelector('#survey');
              survey.classList.add('is-open'); survey.style.display = 'block';
            }});
            await page.waitForTimeout(80);
            await page.evaluate(scanner.AUTONOMOUS_MONITOR_STOP);
            const output = await page.evaluate(() => ({{
              writes: window.__auditIdentityWrites,
              anyAttribute: [...document.querySelectorAll('*')]
                .some((element) => element.hasAttribute('data-design-dna-autonomous-surface-id')),
              documentContainsMarker: document.documentElement.outerHTML.includes('data-design-dna-autonomous-surface-id'),
            }}));
            process.stdout.write(JSON.stringify(output));
          }} finally {{ await context.close(); await browser.close(); }}
        """
        done = subprocess.run(
            [NODE, "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        if done.returncode:
            combined = done.stderr + done.stdout
            if "playwright-unavailable" in combined.lower() or "browser-executable-unavailable" in combined.lower():
                self.skipTest("Real scanner-monitor test requires the configured Playwright browser")
            self.fail(combined)
        result = json.loads(done.stdout)
        self.assertEqual([], result["writes"], result)
        self.assertFalse(result["anyAttribute"], result)
        self.assertFalse(result["documentContainsMarker"], result)

    def test_early_scanner_monitor_captures_closed_shadow_and_detached_frame_surfaces(self) -> None:
        """Both observer blind spots must report before a closed root or frame is no longer inspectable."""
        resolver_uri = (SCRIPTS / "playwright_resolver.mjs").resolve().as_uri()
        evidence_uri = (SCRIPTS / "browser_evidence.mjs").resolve().as_uri()
        scanner_uri = (SCRIPTS / "scan_build_components.mjs").resolve().as_uri()
        script = f"""
          import * as resolver from {json.dumps(resolver_uri)};
          import * as evidence from {json.dumps(evidence_uri)};
          import * as scanner from {json.dumps(scanner_uri)};
          const loaded = resolver.resolvePlaywright({{moduleUrl:{json.dumps(resolver_uri)}}});
          const browserInfo = resolver.discoverBrowserExecutable(loaded.playwright);
          const browser = await loaded.playwright.chromium.launch({{executablePath:browserInfo.file}});
          const context = await browser.newContext({{viewport:{{width:900,height:600}}}});
          const callbacks = [];
          await evidence.installDomInspection(context);
          await context.exposeBinding('__designDnaAutonomousEarlyCallback', async (source, event) => {{
            callbacks.push({{ frameUrl: source.frame?.url?.() || null, event }});
          }});
          await context.addInitScript(scanner.AUTONOMOUS_EARLY_INIT);
          const page = await context.newPage();
          try {{
            await page.setContent('<main>first visit</main><iframe id="transient-frame" srcdoc="<main>frame</main>"></iframe>');
            const child = page.frames().find((frame) => frame !== page.mainFrame());
            if (!child) throw new Error('same-origin child frame was not created');
            await child.waitForLoadState('domcontentloaded');
            await page.evaluate(() => {{
              const host = document.createElement('x-closed-survey'); document.body.append(host);
              const root = host.attachShadow({{mode:'closed'}});
              const survey = document.createElement('div'); survey.id = 'closed-survey';
              survey.style.cssText = 'position:fixed;inset:0;z-index:99'; root.append(survey); survey.remove();
            }});
            await child.evaluate(() => {{
              const survey = document.createElement('div'); survey.id = 'frame-survey';
              survey.style.cssText = 'position:fixed;inset:0;z-index:99'; document.body.append(survey); survey.remove();
            }});
            await page.waitForTimeout(80);
            await page.evaluate(() => document.querySelector('#transient-frame').remove());
            await page.waitForTimeout(80);
            process.stdout.write(JSON.stringify({{ callbacks,
              frameDetached: !page.frames().includes(child),
            }}));
          }} finally {{ await context.close(); await browser.close(); }}
        """
        done = subprocess.run(
            [NODE, "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        if done.returncode:
            combined = done.stderr + done.stdout
            if "playwright-unavailable" in combined.lower() or "browser-executable-unavailable" in combined.lower():
                self.skipTest("Real early-monitor test requires the configured Playwright browser")
            self.fail(combined)
        result = json.loads(done.stdout)
        candidates = [
            candidate
            for callback in result["callbacks"]
            for candidate in [
                *callback["event"].get("added", []),
                *callback["event"].get("removed", []),
            ]
        ]
        observed_ids = {candidate.get("id") for candidate in candidates}
        self.assertTrue(result["frameDetached"], result)
        self.assertIn("closed-survey", observed_ids, result)
        self.assertIn("frame-survey", observed_ids, result)

    def test_autonomous_source_binding_requires_exact_identity_and_programmatic_mapping(self) -> None:
        source_state = {
            "id": "newsletter-appearance",
            "kind": "system",
            "trigger": {
                "type": "ambient",
                "target": "#reference-newsletter",
                "value": None,
                "wait_ms": 1200,
            },
            "trigger_evidence": {
                "target": "#reference-newsletter",
                "appearance_observed": True,
                "target_identity": {
                    "settled": {
                        "tag": "section",
                        "role": "dialog",
                        "accessible_name": "Newsletter sign-up",
                        "semantic_key": "dialog|newsletter sign-up",
                    }
                },
            },
            "evidence_frames": {
                "before": {"file": "before.png"},
                "appearance": {"file": "appearance.png"},
                "settled": {"file": "settled.png"},
            },
        }
        build_state = {
            "id": "newsletter-appearance",
            "kind": "system",
            "trigger": {
                "type": "programmatic",
                "target": "[data-design-dna-state-driver=\"newsletter-appearance\"]",
                "value": None,
            },
        }
        exact_surface = {
            "phase": "post-trigger",
            "tag": "section",
            "role": "dialog",
            "accessible_name": "Newsletter sign-up",
            "semantic_key": "dialog|newsletter sign-up",
        }
        application = {
            "trigger_evidence": {
                "type": "programmatic",
                "settled": True,
                "changed_properties": ["display"],
            }
        }
        expression = f"""(() => {{
          const source = {json.dumps(source_state)};
          const state = {json.dumps(build_state)};
          const exact = {json.dumps(exact_surface)};
          const application = {json.dumps(application)};
          const wrong = (changes) => ({{ ...exact, ...changes }});
          const forged = wrong({{ accessible_name: 'Other dialog', semantic_key: 'dialog|other dialog',
            declared_state_ids: ['newsletter-appearance'], state_driver: 'newsletter-appearance',
            audit_marker: 'data-design-dna-autonomous-surface-id' }});
          return {{
            exact: m.autonomousSurfaceHasSourceBinding(exact, state, source, application),
            missing_source: m.autonomousSurfaceHasSourceBinding(exact, state, null, application),
            wrong_tag: m.autonomousSurfaceHasSourceBinding(wrong({{tag:'article'}}), state, source, application),
            wrong_role: m.autonomousSurfaceHasSourceBinding(wrong({{role:'alertdialog'}}), state, source, application),
            wrong_name: m.autonomousSurfaceHasSourceBinding(wrong({{accessible_name:'Other dialog'}}), state, source, application),
            wrong_semantic: m.autonomousSurfaceHasSourceBinding(wrong({{semantic_key:'dialog|other dialog'}}), state, source, application),
            forged_dom_attribute: m.autonomousSurfaceHasSourceBinding(forged, state, source, application),
            non_programmatic_mapping: m.autonomousSurfaceHasSourceBinding(exact,
              {{...state, trigger:{{...state.trigger, target:'#author-owned-driver'}}}}, source, application),
            unsettled_application: m.autonomousSurfaceHasSourceBinding(exact, state, source,
              {{trigger_evidence:{{...application.trigger_evidence, settled:false}}}}),
          }};
        }})()"""
        result = node_value("scan_build_components.mjs", expression)
        self.assertTrue(result.pop("exact"), result)
        self.assertTrue(all(value is False for value in result.values()), result)

    def test_transform_surface_that_never_reaches_terminal_fails(self) -> None:
        expression = """(async () => {
          let samples=0;
          const page={viewportSize:()=>({width:1000,height:800}),waitForTimeout:async()=>{},
            mouse:{move:async()=>{},wheel:async()=>{}},
            evaluate:async(fn,arg)=>{
              const source=String(fn);
              if (!arg) return [{id:"t",kind:"transform",axis:"wheel",required:true,selector_hint:"div.reel"}];
              if (source.includes("scrollTo({ top: 0")) return null;
              samples+=1; return {x:0,y:0,max_x:0,max_y:0,rect:{left:0,top:0,width:900,height:700},fingerprint:`f${samples}`};
            }};
          return m.traverseScrollSurfaces(page,{maxTicks:3,settleMs:0});
        })()"""
        value = node_value("browser_evidence.mjs", expression)
        self.assertFalse(value["complete"])
        self.assertEqual("tick-cap-before-terminal", value["surfaces"][0]["reason"])

    def test_first_screen_scope_rejects_a_prebuilt_second_section(self) -> None:
        valid = {"document_height": 900, "viewport_height": 900,
                 "substantial_regions": [{"top": 0, "bottom": 900}], "beyond_first_screen_regions": []}
        broad = {"document_height": 1800, "viewport_height": 900,
                 "substantial_regions": [{"top": 0, "bottom": 900}, {"top": 900, "bottom": 1800}],
                 "beyond_first_screen_regions": [{"top": 900, "bottom": 1800}]}
        value = node_value(
            "scan_build_components.mjs",
            f'[m.firstScreenScopePass({json.dumps(valid)}),m.firstScreenScopePass({json.dumps(broad)})]',
        )
        self.assertEqual([True, False], value)


class ProducerContractTests(unittest.TestCase):
    def test_owned_producers_do_not_bypass_exact_navigation(self) -> None:
        for name in (
            "scan_build_components.mjs",
            "extract_reference_styles.mjs",
            "observe_reference.mjs",
            "record_reference.mjs",
        ):
            text = (SCRIPTS / name).read_text(encoding="utf-8")
            self.assertNotIn("page.goto(", text, name)
            self.assertIn("navigateExact", text, name)

    def test_recorder_has_wide_narrow_and_complete_artifact_ledger(self) -> None:
        text = (SCRIPTS / "record_reference.mjs").read_text(encoding="utf-8")
        self.assertIn('{ name: "wide", width: 1440', text)
        self.assertIn('{ name: "narrow", width: 390', text)
        for kind in ("recording", "video", "events-index", "frame", "event-sheet", "cursor-path", "difference-signal"):
            self.assertRegex(text, rf"['\"]{kind}['\"]")
        self.assertIn("while (Date.now() - started < args.seconds * 1000)", text)
        self.assertNotIn("MAX_SPONTANEOUS", text)

    def test_style_extractor_uses_bound_typed_states_not_closed_vocabulary(self) -> None:
        text = (SCRIPTS / "extract_reference_styles.mjs").read_text(encoding="utf-8")
        self.assertNotIn("KNOWN_STATES", text)
        self.assertNotIn('a === "--state"', text)
        self.assertIn("binding.states", text)
        self.assertIn("applyManifestState", text)

    def test_observer_passes_authored_states_to_both_recursive_profiles(self) -> None:
        text = (SCRIPTS / "observe_reference.mjs").read_text(encoding="utf-8")
        self.assertIn('studyRecursiveSite(page, args.url, "wide", stateContract.payload.states,', text)
        self.assertIn('studyRecursiveSite(narrowSitePage, args.url, "narrow", stateContract.payload.states,', text)

    def test_live_study_outputs_generated_quality_and_discovery_evidence(self) -> None:
        for name in ("observe_reference.mjs", "record_reference.mjs"):
            text = (SCRIPTS / name).read_text(encoding="utf-8")
            for field in ("captures_by_viewport", "discovery_metadata", "quality_observations", "defect_observations"):
                self.assertIn(field, text, f"{name}: {field}")

    def test_dom_discovered_control_cannot_be_omitted_from_live_path(self) -> None:
        value = node_value(
            "browser_evidence.mjs",
            "m.interactionReconciliationGaps({domTargetIds:['seen','omitted'],liveTargetIds:['seen'],"
            "authoredStateIds:['rest','menu-open'],boundStateIds:['rest']})",
        )
        self.assertEqual(["omitted"], value["controls"])
        self.assertEqual(["menu-open"], value["states"])

    def test_hover_and_transition_bookkeeping_do_not_fake_rendered_change(self) -> None:
        before = [{"key": "button", "properties": {"hovered": False, "transition_duration": "0.2s", "color": "red", "transform": "none"}}]
        after = [{"key": "button", "properties": {"hovered": True, "transition_duration": "0.4s", "color": "red", "transform": "none"}}]
        value = node_value(
            "browser_evidence.mjs",
            f"m.classifyVisualEvidence({json.dumps(before)},{json.dumps(after)})",
        )
        self.assertEqual([], value["changed_properties"])
        self.assertEqual(2, len(value["change_classification"]["diagnostic"]))

    def test_cosmetic_and_structural_interaction_changes_are_separate(self) -> None:
        before = [{"key": "button", "properties": {"color": "red", "transform": "none", "aria_expanded": "false"}}]
        after = [{"key": "button", "properties": {"color": "blue", "transform": "matrix(1,0,0,1,20,0)", "aria_expanded": "true"}}]
        value = node_value(
            "browser_evidence.mjs",
            f"m.classifyVisualEvidence({json.dumps(before)},{json.dumps(after)})",
        )["change_classification"]
        self.assertEqual(["color"], [row["property"] for row in value["cosmetic"]])
        self.assertEqual({"transform", "aria_expanded"}, {row["property"] for row in value["structural_semantic"]})

    def test_interaction_census_is_uncapped_and_side_effect_aware(self) -> None:
        helper = (SCRIPTS / "browser_evidence.mjs").read_text(encoding="utf-8")
        census = helper.split("export async function captureInteractionCensus", 1)[1]
        self.assertNotIn("targets.slice(", census)
        self.assertNotIn("discovered.slice(", census)
        self.assertIn("truncated: false", census)
        self.assertIn("blocked-requires-safe-owner-handoff", census)
        self.assertIn("distinct_from_hover: true", census)
        self.assertIn("dom_code_inventory", census)

    def test_mutating_census_inputs_require_a_fresh_exact_baseline(self) -> None:
        value = node_value(
            "browser_evidence.mjs",
            "['hover','focus','focus-traversal','keyboard','click','open-close','media-play-pause','input','programmatic']"
            ".map((kind)=>[kind,m.needsFreshCensusBaseline(kind)])",
        )
        self.assertEqual(
            {
                "hover": False,
                "focus": False,
                "focus-traversal": False,
                "keyboard": True,
                "click": True,
                "open-close": True,
                "media-play-pause": True,
                "input": True,
                "programmatic": True,
            },
            dict(value),
        )
        helper = (SCRIPTS / "browser_evidence.mjs").read_text(encoding="utf-8")
        self.assertIn("freshBaselineTarget(page, target", helper)
        self.assertIn("strategy: 'fresh-exact-state'", helper)
        self.assertIn("if (isolated) await isolated.page.close()", helper)

    def test_modal_occlusion_failure_retains_target_overlay_and_full_error(self) -> None:
        target_id = "a" * 24
        raw_error = "locator.hover intercepted by Flodesk modal " + ("detail-" * 200)
        census = {
            "profile": "wide",
            "pages": [{
                "url": "https://example.test/",
                "targets": [{
                    "target_id": target_id,
                    "selector": '[data-dna-interaction-id="7"]',
                    "tag": "a",
                    "role": "a",
                    "text": "Hosting with Heart",
                    "semantic_key": "a|hosting with heart",
                    "class_signature": ["primary-link"],
                    "repeat_class": "a|a|primary-link",
                    "repeat_index": 1,
                    "repeat_count": 1,
                    "kind": "route-link",
                    "semantic_state": {},
                    "source_state_ids": [],
                    "inputs": [],
                }],
            }],
            "totals": {
                "targets_discovered": 1,
                "inputs_discovered": 1,
                "inputs_exercised": 0,
                "inputs_blocked": 0,
            },
            "missing": [{
                "target_id": target_id,
                "input_kind": "hover",
                "input_value": None,
                "source_state_id": "rest",
                "stage": "input-dispatch",
                "code": "target-occluded",
                "reason": raw_error,
                "elapsed_ms_since_census_start": 11130,
                "probe": {
                    "hit_test": {
                        "hits_target": False,
                        "blocking_overlay": {
                            "tag": "div",
                            "role": "dialog",
                            "data_ff_el": "modal",
                            "text": "Stay connected",
                        },
                    },
                },
                "evidence": {"before": {"file": "before.png"}, "after": None, "settled": None},
            }],
        }
        value = node_value(
            "browser_evidence.mjs",
            f"m.interactionCensusDiagnostic({json.dumps(census)},{{phase:'source-state',source_state_id:'rest',pass:2}})",
        )
        self.assertFalse(value["complete"])
        self.assertEqual(1, value["totals"]["inputs_failed"])
        self.assertEqual("target-occluded", value["failures"][0]["code"])
        self.assertEqual("Hosting with Heart", value["failures"][0]["target"]["text"])
        self.assertEqual("modal", value["failures"][0]["probe"]["hit_test"]["blocking_overlay"]["data_ff_el"])
        self.assertEqual(raw_error, value["failures"][0]["reason"])

    def test_only_inert_and_focus_blocked_modal_background_is_not_an_error(self) -> None:
        valid = {
            "target": {
                "inert_ancestor": {"tag": "main"},
                "aria_hidden_ancestor": None,
                "focus_blocked": True,
            },
            "hit_test": {
                "hits_target": False,
                "top": {"tag": "div"},
                "blocking_overlay": {"role": "dialog", "visible": True, "auto_dismissed": False},
            },
        }
        covered_but_live = {
            "target": {
                "inert_ancestor": None,
                "aria_hidden_ancestor": None,
                "focus_blocked": False,
            },
            "hit_test": {
                "hits_target": False,
                "top": {"tag": "div"},
                "blocking_overlay": {"role": "dialog", "visible": True, "auto_dismissed": False},
            },
        }
        aria_hidden_only = {
            "target": {
                "inert_ancestor": None,
                "aria_hidden_ancestor": {"tag": "main"},
                "focus_blocked": False,
            },
            "hit_test": {
                "hits_target": False,
                "top": {"tag": "div"},
                "blocking_overlay": {"role": "dialog", "visible": True, "auto_dismissed": False},
            },
        }
        disabled_dialog = {
            **valid,
            "hit_test": {
                "hits_target": False,
                "top": {"tag": "div"},
                "blocking_overlay": {"role": "dialog", "visible": True, "aria_disabled": "true", "auto_dismissed": False},
            },
        }
        value = node_value(
            "browser_evidence.mjs",
            f"[m.isProvenActiveModalBlock({json.dumps(valid)}),m.isProvenActiveModalBlock({json.dumps(covered_but_live)}),m.isProvenActiveModalBlock({json.dumps(aria_hidden_only)}),m.isProvenActiveModalBlock({json.dumps(disabled_dialog)})]",
        )
        self.assertEqual([True, False, False, False], value)

    def test_real_visible_unnamed_modal_close_is_a_source_failure(self) -> None:
        resolver_uri = (SCRIPTS / "playwright_resolver.mjs").resolve().as_uri()
        evidence_uri = (SCRIPTS / "browser_evidence.mjs").resolve().as_uri()
        script = f"""
          import * as resolver from {json.dumps(resolver_uri)};
          import * as evidence from {json.dumps(evidence_uri)};
          const loaded = resolver.resolvePlaywright({{moduleUrl:{json.dumps(resolver_uri)}}});
          const browserInfo = resolver.discoverBrowserExecutable(loaded.playwright);
          const browser = await loaded.playwright.chromium.launch({{executablePath:browserInfo.file}});
          const context = await browser.newContext({{viewport:{{width:900,height:600}}}});
          await evidence.installDomInspection(context);
          const page = await context.newPage();
          try {{
            await page.setContent('<div role="dialog" aria-modal="true" data-ff-el="modal"><button type="button" data-ff-el="modal-close"></button></div>');
            const census = await evidence.captureInteractionCensus(page, {{
              profile:'wide', pageUrl:'https://fixture.test/', authoredStates:[],
              captureEvidence:async (label)=>({{file:label + '.png',bytes:1,sha256:'a'.repeat(64)}}),
            }});
            process.stdout.write(JSON.stringify({{complete:census.complete,missing:census.missing}}));
          }} finally {{ await context.close(); await browser.close(); }}
        """
        done = subprocess.run(
            [NODE, "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        if done.returncode:
            combined = done.stderr + done.stdout
            if "playwright-unavailable" in combined.lower() or "browser-executable-unavailable" in combined.lower():
                self.skipTest("Real modal census test requires the configured Playwright browser")
            self.fail(combined)
        result = json.loads(done.stdout)
        self.assertFalse(result["complete"])
        failure = next(item for item in result["missing"] if item["code"] == "unlabeled-visible-modal-control")
        self.assertEqual("modal-close", failure["probe"]["control"]["data_ff_el"])
        self.assertIsNone(failure["probe"]["accessible_name"])
        self.assertIsNotNone(failure["evidence"]["before"])

    def test_ambient_state_is_bound_once_without_target_redispatch(self) -> None:
        resolver_uri = (SCRIPTS / "playwright_resolver.mjs").resolve().as_uri()
        evidence_uri = (SCRIPTS / "browser_evidence.mjs").resolve().as_uri()
        script = f"""
          import * as resolver from {json.dumps(resolver_uri)};
          import * as evidence from {json.dumps(evidence_uri)};
          const loaded = resolver.resolvePlaywright({{moduleUrl:{json.dumps(resolver_uri)}}});
          const browserInfo = resolver.discoverBrowserExecutable(loaded.playwright);
          const browser = await loaded.playwright.chromium.launch({{executablePath:browserInfo.file}});
          const context = await browser.newContext({{viewport:{{width:900,height:600}}}});
          await evidence.installDomInspection(context);
          const page = await context.newPage();
          const frame = (name) => ({{file:name + '.png',bytes:1,sha256:'b'.repeat(64)}});
          const rest = {{id:'rest',url:'https://fixture.test/',kind:'rest',trigger:{{type:'none',target:'document',value:null}},expectation:'settled'}};
          const ambient = {{id:'newsletter',url:'https://fixture.test/',kind:'system',trigger:{{type:'ambient',target:'#newsletter',value:null,wait_ms:1200}},expectation:'newsletter dialog appears without input'}};
          try {{
            await page.setContent(`
              <main inert><a href="#background">Background route</a></main>
              <div id="newsletter" role="dialog" aria-modal="true" data-ff-el="modal" style="display:none;position:fixed;inset:0;background:white">
                <button type="button" aria-label="Close newsletter" data-ff-el="modal-close">×</button>
              </div>
            `);
            await page.evaluate(() => setTimeout(() => {{ window.__ambientApplications=(window.__ambientApplications||0)+1; document.querySelector('#newsletter').style.display='block'; }}, 180));
            let appearance = null;
            const application = await evidence.applyManifestState(page, ambient, {{sourceOnly:true,onAmbientAppearance:async()=>{{appearance=frame('appearance')}}}});
            const census = await evidence.captureInteractionCensus(page, {{
              profile:'wide',pageUrl:'https://fixture.test/',authoredStates:[rest,ambient],baselineState:ambient,
              baselineApplication:application,baselineEvidence:{{before:frame('before'),after:appearance,settled:frame('settled')}},
              sourceOnly:true,captureEvidence:async(label)=>frame(label),
            }});
            process.stdout.write(JSON.stringify({{
              complete:census.complete,
              missing:census.missing,
              ambientRows:census.page_states.filter((row)=>row.source_state_id==='newsletter'),
              ambientMissing:census.missing.filter((row)=>row.code==='ambient-ledger-missing'),
              applicationCount:await page.evaluate(()=>window.__ambientApplications),
            }}));
          }} finally {{ await context.close(); await browser.close(); }}
        """
        done = subprocess.run(
            [NODE, "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        if done.returncode:
            combined = done.stderr + done.stdout
            if "playwright-unavailable" in combined.lower() or "browser-executable-unavailable" in combined.lower():
                self.skipTest("Real ambient ledger test requires the configured Playwright browser")
            self.fail(combined)
        result = json.loads(done.stdout)
        self.assertEqual(1, len(result["ambientRows"]))
        self.assertEqual([], result["ambientMissing"])
        self.assertFalse(
            any(item.get("code") == "ambient-ledger-missing" for item in result["missing"]),
            result,
        )
        self.assertEqual(1, result["applicationCount"])

    def test_interaction_targets_bind_accessible_text_and_semantic_identity(self) -> None:
        helper = (SCRIPTS / "browser_evidence.mjs").read_text(encoding="utf-8")
        self.assertIn("const semanticKey = `${role.toLowerCase()}|${text.toLowerCase()}`", helper)
        census = helper.split("export async function captureInteractionCensus", 1)[1]
        self.assertIn("text: target.text, semantic_key: target.semantic_key", census)

    def test_keyboard_activation_is_not_faked_by_tab_traversal(self) -> None:
        helper = (SCRIPTS / "browser_evidence.mjs").read_text(encoding="utf-8")
        census = helper.split("export async function captureInteractionCensus", 1)[1].split(
            "export async function captureRenderedQA", 1
        )[0]
        self.assertIn("exercise('focus-traversal', 'Tab'", census)
        self.assertIn("exercise('keyboard', 'Enter'", census)
        self.assertIn("exercise('keyboard', 'Space'", census)
        self.assertNotIn("exercise('keyboard', 'Tab'", census)

    def test_target_evidence_is_bound_to_frames_not_timestamps_only(self) -> None:
        observer = (SCRIPTS / "observe_reference.mjs").read_text(encoding="utf-8")
        recorder = (SCRIPTS / "record_reference.mjs").read_text(encoding="utf-8")
        self.assertIn("boundEvidenceShot", observer)
        self.assertIn("evidence_frames", observer)
        self.assertIn("mapped.frame = frameFiles[index]", recorder)
        self.assertIn("interaction_census_by_viewport", recorder)

    def test_source_producers_emit_full_rendered_qa(self) -> None:
        helper = (SCRIPTS / "browser_evidence.mjs").read_text(encoding="utf-8")
        self.assertIn("captureRenderedQA", helper)
        for term in ("fixed_rail_overlaps", "hidden_controls", "dead_controls", "initial_focus_inside", "focus_trap", "reduced_motion", "deep_link", "dead_end"):
            self.assertIn(term, helper)
        for name in ("observe_reference.mjs", "record_reference.mjs"):
            self.assertIn("rendered_qa_by_viewport", (SCRIPTS / name).read_text(encoding="utf-8"))

    def test_source_overlay_qa_covers_closed_panels_stacking_and_focus_lifecycle(self) -> None:
        helper = (SCRIPTS / "browser_evidence.mjs").read_text(encoding="utf-8")
        qa = helper.split("export async function captureRenderedQA", 1)[1].split(
            "export async function discoverScrollSurfaces", 1
        )[0]
        self.assertIn('[aria-hidden]', qa)
        self.assertIn('[class*="menu-panel" i]', qa)
        self.assertIn("closed_descendants_inert", qa)
        self.assertIn("stacking_above_background_controls", qa)
        self.assertIn("elementsFromPoint", qa)
        self.assertIn("page.keyboard.press('Escape')", qa)
        self.assertIn("focus_return", qa)
        self.assertNotIn("child.inert || child.getAttribute('aria-hidden') === 'true'", qa)

    def test_overlay_occlusion_is_not_mislabeled_as_body_collision(self) -> None:
        helper = (SCRIPTS / "browser_evidence.mjs").read_text(encoding="utf-8")
        qa = helper.split("export async function captureRenderedQA", 1)[1].split(
            "export async function discoverScrollSurfaces", 1
        )[0]
        self.assertIn("crossesActiveOverlayBoundary", qa)
        self.assertGreaterEqual(
            qa.count("if (crossesActiveOverlayBoundary("),
            2,
            "both collision and fixed-rail loops must defer overlay overlap to overlay QA",
        )

    def test_source_state_semantics_cannot_be_replaced_by_a_visual_toggle(self) -> None:
        helper = (SCRIPTS / "browser_evidence.mjs").read_text(encoding="utf-8")
        qa = helper.split("export async function captureRenderedQA", 1)[1].split(
            "export async function discoverScrollSurfaces", 1
        )[0]
        for field in ("aria_expanded", "aria_pressed", "aria_selected", "aria_checked", "aria_controls"):
            self.assertIn(field, qa)
        self.assertIn("controlled_visible", qa)
        for producer in ("observe_reference.mjs", "record_reference.mjs"):
            self.assertIn("sourceState: state", (SCRIPTS / producer).read_text(encoding="utf-8"))

    def test_later_source_state_cannot_erase_an_earlier_rendered_defect(self) -> None:
        page = {
            "url": "https://example.test/",
            "evidence": {},
            "clipping": [],
            "collisions": [],
            "fixed_rail_overlaps": [],
            "hidden_controls": [],
            "control_visibility": [],
            "dead_controls": [],
            "semantic_issues": [],
            "overlays": [],
            "keyboard_paths": [],
            "keyboard": {"complete": True, "missing": []},
            "semantic_equivalence": {"complete": True, "mismatches": []},
            "state_semantics": {
                "required": False,
                "complete": True,
                "target": None,
                "attributes": None,
            },
            "reduced_motion": {"honors_preference": True},
            "deep_link": {"complete": True},
            "reload": {"complete": True},
            "dead_end": {"problem": False},
        }
        broken = json.loads(json.dumps(page))
        broken["collisions"] = [{"first": "rail", "second": "menu"}]
        value = node_value(
            "browser_evidence.mjs",
            "m.mergeSourceRenderedQA('wide',["
            + json.dumps({"pages": [broken], "missing": [], "complete": True, "truncated": False})
            + ","
            + json.dumps({"pages": [page], "missing": [], "complete": True, "truncated": False})
            + "])",
        )
        self.assertEqual([{"first": "rail", "second": "menu"}], value["pages"][0]["collisions"])
        self.assertEqual(1, value["totals"]["issues"])

    def test_postbuild_rendered_qa_is_live_complete_and_first_screen_cannot_pose_as_final(self) -> None:
        scanner = (SCRIPTS / "scan_build_components.mjs").read_text(encoding="utf-8")
        for field in (
            "clipping", "collisions", "fixed_rail_overlaps", "hidden_controls",
            "dead_controls", "blocked_handoffs", "overlays", "keyboard",
            "reduced_motion", "deep_link", "reload", "dead_ends",
            "semantic_equivalence", "presentation_ready", "presentation_blocker",
        ):
            self.assertIn(field, scanner)
        self.assertIn("first-screen authorization is not post-build multi-route/site QA", scanner)
        self.assertIn("renderedQa.complete", scanner)
        self.assertIn("truncated: false", scanner)

    def test_source_state_template_is_machine_readable(self) -> None:
        payload = json.loads((SKILL / "templates" / "reference-state-contract-template.json").read_text(encoding="utf-8"))
        self.assertEqual(2, payload["schema_version"])
        self.assertEqual("rest", payload["states"][0]["id"])
        self.assertEqual({"type": "none", "target": "document", "value": None}, payload["states"][0]["trigger"])

    def test_consent_disposition_is_constrained_and_evidence_bound(self) -> None:
        expected = [
            "reject", "reject all", "decline", "decline all",
            "only necessary", "necessary only", "essential only",
        ]
        self.assertEqual(expected, node_value("observe_reference.mjs", "m.CONSENT_SAFE_DISPOSITIONS"))
        self.assertEqual(expected, node_value("record_reference.mjs", "m.CONSENT_SAFE_DISPOSITIONS"))
        for name in ("observe_reference.mjs", "record_reference.mjs"):
            self.assertFalse(node_value(name, "m.isConstrainedConsentSignal('Privacy information — Decline')"))
            self.assertTrue(node_value(name, "m.isConstrainedConsentSignal('Cookie preferences — Decline')"))
        for name, function_name in (
            ("observe_reference.mjs", "requireUnblockedConsent"),
            ("record_reference.mjs", "requireSafeConsent"),
        ):
            text = (SCRIPTS / name).read_text(encoding="utf-8")
            section = text.split(f"async function {function_name}", 1)[1].split("\n}\n", 1)[0]
            self.assertIn("generated before/action/after", section)
            self.assertIn("no automatic choice was made", section)
            self.assertIn("action.first().click", section)
            self.assertNotIn("button.click()", section)
        recorder = (SCRIPTS / "record_reference.mjs").read_text(encoding="utf-8")
        self.assertIn("const boundLog = bindVideoEvidence(run.log)", recorder)
        self.assertIn("action: 'consent-disposition'", recorder)

    def test_timing_gap_reconciliation_allows_jitter_but_blocks_a_candidate_lifecycle(self) -> None:
        frame = {"file": "frames/watch.png", "bytes": 10, "sha256": "a" * 64}
        gap = {
            "from_elapsed_ms": 50, "to_elapsed_ms": 245, "gap_ms": 195,
            "maximum_ms": 100, "reason": "timer", "watch_phase": "normal",
        }
        normal = {
            "sample_interval_ms": 50,
            "animation_samples": [
                {"elapsed_ms": 50, "candidate_inventory": []},
                {"elapsed_ms": 245, "candidate_inventory": []},
            ],
            "sample_gap_failures": [gap], "events": [], "mutation_batches": [], "animation_events": [],
        }
        value = node_value(
            "source_surface_watch.mjs",
            "(() => {"
            f"const report={json.dumps(normal)};"
            f"const frame={json.dumps(frame)};"
            "report.gap_reconciliations=m.reconcileSourceTimingGaps({gaps:report.sample_gap_failures,"
            "samples:report.animation_samples,events:report.events,mutationBatches:report.mutation_batches,"
            "animationEvents:report.animation_events,baseline:frame,finalEvidence:frame,watchPhase:'normal'});"
            "return {reconciliation:report.gap_reconciliations[0],failures:m.sourceSurfaceWatchFailures(report)};"
            "})()",
        )
        self.assertFalse(value["reconciliation"]["ambiguous_candidate_lifecycle"])
        self.assertEqual([], value["failures"])
        transient = json.loads(json.dumps(normal))
        transient["events"] = [{
            "event_id": "watch-e1", "kind": "surface-node-added", "elapsed_ms": 120,
            "declared_ambient": True, "selector": '[role="dialog"][data-ff-el="modal"]',
            "surface": {"tag": "div", "role": "dialog", "data_ff_el": "modal", "connected": True},
            "detail": {"group_key": "modal", "member_events": [{"member_id": "modal-root"}]},
            "evidence": {"before": frame, "callback": frame, "after": frame},
        }]
        value = node_value(
            "source_surface_watch.mjs",
            "(() => {"
            f"const report={json.dumps(transient)};"
            f"const frame={json.dumps(frame)};"
            "report.gap_reconciliations=m.reconcileSourceTimingGaps({gaps:report.sample_gap_failures,"
            "samples:report.animation_samples,events:report.events,mutationBatches:report.mutation_batches,"
            "animationEvents:report.animation_events,baseline:frame,finalEvidence:frame,watchPhase:'normal'});"
            "return {reconciliation:report.gap_reconciliations[0],failures:m.sourceSurfaceWatchFailures(report)};"
            "})()",
        )
        self.assertTrue(value["reconciliation"]["ambiguous_candidate_lifecycle"])
        self.assertEqual('[role="dialog"][data-ff-el="modal"]', value["reconciliation"]["selector"])
        self.assertTrue(any("Flodesk modal" in item and '[role="dialog"][data-ff-el="modal"]' in item for item in value["failures"]))

    def test_early_source_watch_fails_closed_without_one_navigation_cdp_support(self) -> None:
        value = node_value(
            "source_surface_watch.mjs",
            "(async () => { const page={exposeBinding:async()=>{},context:()=>null}; "
            "try { await m.armEarlySourceSurfaceWatch(page,{}); return null; } "
            "catch (error) { return {code:error.code,message:error.message}; } })()",
        )
        self.assertEqual("source-surface-watch-cdp-unavailable", value["code"])
        self.assertIn("one-navigation", value["message"])

    def test_source_study_controller_writes_partial_ineligible_artifact_on_no_progress(self) -> None:
        value = node_value(
            "source_study_controller.mjs",
            "(async () => {"
            "const fs=await import('node:fs'); const os=await import('node:os'); const path=await import('node:path');"
            "const dir=fs.mkdtempSync(path.join(os.tmpdir(),'dna-study-no-progress-')); let now=0;"
            "try { const controller=m.createSourceStudyController({output_dir:dir,id:'fixture',producer:'fixture.mjs',now:()=>now,"
            "limits:{max_no_progress_ms:50,max_step_ms:50,max_screenshot_ms:50,max_routes:3,max_targets:3,max_consecutive_target_repeats:2},"
            "partial_evidence:()=>({frames:['captured-frame.png']})}); controller.markFrame({file:'captured-frame.png'}); now=51;"
            "try { controller.assertHealthy(); return {unexpected:true}; } catch (error) { const failure=JSON.parse(fs.readFileSync(error.source_study_failure.file,'utf8'));"
            "return {code:error.code,status:failure.status,eligible:failure.eligible_for_source_selection,frames:failure.partial_evidence.frames,progress:failure.progress.progress_event_count}; }"
            "} finally { fs.rmSync(dir,{recursive:true,force:true}); } })()",
        )
        self.assertEqual("source-study-no-progress", value["code"])
        self.assertEqual("incomplete-not-selection-evidence", value["status"])
        self.assertFalse(value["eligible"])
        self.assertEqual(["captured-frame.png"], value["frames"])
        self.assertGreaterEqual(value["progress"], 3)

    def test_source_study_controller_rejects_forged_completion_and_closes_valid_success(self) -> None:
        value = node_value(
            "source_study_controller.mjs",
            "(async () => {"
            "const fs=await import('node:fs'); const os=await import('node:os'); const path=await import('node:path'); const crypto=await import('node:crypto');"
            "const dir=fs.mkdtempSync(path.join(os.tmpdir(),'dna-study-complete-'));"
            "try { const make=()=>m.createSourceStudyController({output_dir:dir,id:'fixture',producer:'fixture.mjs',partial_evidence:()=>null});"
            "const first=make(); first.markFrame({file:'missing.png'}); let forged; try { first.complete({terminal_success:true,signed_artifacts:[{kind:'frame',file:'missing.png',bytes:9,sha256:'a'.repeat(64),producer:'fixture.mjs'}]}); } catch (error) { forged=error.code; }"
            "const clean=fs.mkdtempSync(path.join(os.tmpdir(),'dna-study-complete-clean-')); const file=path.join(clean,'frame.bin'); fs.writeFileSync(file,'valid-frame'); const meta={kind:'frame',file:'frame.bin',bytes:fs.statSync(file).size,sha256:crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'),producer:'fixture.mjs'};"
            "const second=m.createSourceStudyController({output_dir:clean,id:'fixture',producer:'fixture.mjs',partial_evidence:()=>null}); second.markFrame({file:'frame.bin'}); second.complete({terminal_success:true,signed_artifacts:[meta]}); let closed; try { second.markFrame({file:'later.png'}); } catch (error) { closed=error.code; } fs.rmSync(clean,{recursive:true,force:true}); return {forged,closed};"
            "} finally { fs.rmSync(dir,{recursive:true,force:true}); } })()",
        )
        self.assertEqual("source-study-completion-unproven", value["forged"])
        self.assertEqual("source-study-terminal-closed", value["closed"])

    def test_recorder_rejects_unbounded_or_fractionally_rounded_dwell(self) -> None:
        value = node_value(
            "record_reference.mjs",
            "({max:m.MAX_RECORDING_SECONDS,tooLong:m.recordingSettingsError({seconds:m.MAX_RECORDING_SECONDS+1,fps:15}),"
            "fractional:m.recordingSettingsError({seconds:90.0001,fps:15}),valid:m.recordingSettingsError({seconds:90,fps:15})})",
        )
        self.assertLessEqual(value["max"], 900)
        self.assertIn("must not exceed", value["tooLong"])
        self.assertIn("millisecond-representable", value["fractional"])
        self.assertIsNone(value["valid"])

    def test_bounded_postprocess_requires_real_child_progress_and_kills_silence(self) -> None:
        value = node_value(
            "record_reference.mjs",
            "(async () => {"
            "const fs=await import('node:fs'); const os=await import('node:os'); const path=await import('node:path'); const study=await import(new URL('./skills/design-dna/scripts/source_study_controller.mjs',import.meta.url));"
            "const limits={max_no_progress_ms:50,max_step_ms:1000,max_screenshot_ms:1000,max_total_elapsed_ms:1000,max_progress_events:1000,max_routes:10,max_targets:10,max_target_edges:10,max_consecutive_target_repeats:3,max_total_target_visits_per_key:5,max_repeated_target_edge_visits:5}; const activeLimits={...limits,max_no_progress_ms:200};"
            "const root=fs.mkdtempSync(path.join(os.tmpdir(),'dna-postprocess-')); const child=process.execPath;"
            "try { const active=study.createSourceStudyController({output_dir:path.join(root,'active'),id:'active',producer:'record_reference.mjs',limits:activeLimits,partial_evidence:()=>null});"
            "await m.runBoundedSourceSubprocess({command:child,args:['-e',\"let n=0;const t=setInterval(()=>{process.stdout.write('x');if(++n===8){clearInterval(t)}},15)\"],label:'advancing',sourceStudy:active,timeoutMs:500,heartbeatMs:10});"
            "const journal=fs.readFileSync(active.eventFile,'utf8'); const silent=study.createSourceStudyController({output_dir:path.join(root,'silent'),id:'silent',producer:'record_reference.mjs',limits,partial_evidence:()=>({captured:true})}); let silentCode; try { await m.runBoundedSourceSubprocess({command:child,args:['-e',\"setInterval(()=>{},1000)\"],label:'silent',sourceStudy:silent,timeoutMs:500,heartbeatMs:10}); } catch(error) { silentCode=error.code; }"
            "return {advanced:active.state.status,journalHasChunk:journal.includes('postprocess-chunk'),silentCode,silentStatus:silent.state.status,failure:fs.existsSync(silent.failureFile)};"
            "} finally { fs.rmSync(root,{recursive:true,force:true}); } })()",
        )
        self.assertEqual("active", value["advanced"])
        self.assertTrue(value["journalHasChunk"])
        self.assertEqual("source-study-no-progress", value["silentCode"])
        self.assertEqual("failed", value["silentStatus"])
        self.assertTrue(value["failure"])

    def test_undocumented_late_autonomous_surface_is_a_source_failure(self) -> None:
        report = {
            "events": [
                {"declared_ambient": True, "surface": {"role": "dialog"}},
                {"kind": "surface-node-removed", "declared_ambient": False, "surface": {"role": "dialog", "connected": False}},
            ]
        }
        value = node_value(
            "source_surface_watch.mjs",
            f"(() => {{ const error=m.undocumentedSourceSurfaceError({json.dumps(report)},{{profile:'wide',phase:'post-dwell'}}); return {{code:error?.code||null,message:error?.message||null}}; }})()",
        )
        self.assertEqual("undocumented-autonomous-source-surface", value["code"])
        self.assertIn("undocumented autonomous source surface", value["message"])
        clean = node_value(
            "source_surface_watch.mjs",
            "m.undocumentedSourceSurfaceError({events:[{declared_ambient:true}]},{profile:'wide'}) === null",
        )
        self.assertTrue(clean)
        frame = {"file": "frames/one.png", "bytes": 10, "sha256": "a" * 64}
        event = {
            "event_id": "watch-e1", "kind": "surface-node-removed", "elapsed_ms": 12,
            "declared_ambient": False, "selector": None, "surface": {"connected": False},
            "detail": {"mutation_batch": "watch-m1", "member_events": [{"member_id": "watch-member-1"}]},
            "evidence": {"before": frame, "callback": frame, "after": frame},
        }
        self.assertEqual([], node_value(
            "source_surface_watch.mjs",
            f"m.sourceSurfaceWatchFailures({json.dumps({'sample_interval_ms': 50, 'animation_samples': [], 'sample_gap_failures': [], 'events': [event]})})",
        ))
        event["evidence"]["callback"] = None
        failure = node_value(
            "source_surface_watch.mjs",
            f"m.sourceSurfaceWatchFailures({json.dumps({'sample_interval_ms': 50, 'animation_samples': [], 'sample_gap_failures': [], 'events': [event]})})",
        )
        self.assertTrue(any("evidence contract" in item for item in failure))
        helper = (SCRIPTS / "source_surface_watch.mjs").read_text(encoding="utf-8")
        for marker in (
            "MutationObserver", "setInterval", "document.getAnimations", "autonomous-surface-appeared",
            "final-target-state-diff", "removedNodes", "mutation_batches", "tail_mutations",
            "animationstart", "transitionrun", "surface-waapi-active", "callback_evidence", "exposeBinding",
            "callbackPending", "surface-node-added", "surface-node-removed", "surface-css-animation-event",
        ):
            self.assertIn(marker, helper)
        self.assertNotIn("animation_samples.length >", helper)
        self.assertNotIn("data-design-dna-source-surface", helper)
        for name in ("observe_reference.mjs", "record_reference.mjs"):
            text = (SCRIPTS / name).read_text(encoding="utf-8")
            self.assertIn("startSourceSurfaceWatch", text)
            self.assertIn("undocumentedSourceSurfaceError", text)
        self.assertIn("post-dwell", (SCRIPTS / "record_reference.mjs").read_text(encoding="utf-8"))

    def test_visible_decision_template_has_every_category_and_frame_evidence(self) -> None:
        payload = json.loads(
            (SKILL / "templates" / "visible-decision-source-manifest-template.json")
            .read_text(encoding="utf-8")
        )
        expected = [
            "layout", "typeface", "color", "control", "transition",
            "content-pattern", "effect",
        ]
        self.assertEqual(2, payload["schema_version"])
        self.assertEqual(expected, payload["completeness"]["required_categories"])
        self.assertEqual(
            payload["planned_decision_ids"],
            [row["decision_id"] for row in payload["decisions"]],
        )
        for row in payload["decisions"]:
            self.assertEqual(
                {"decision_id", "category", "component_id", "source_mapping", "bindings",
                 "style_provenance", "asset_role_binding", "dominant_behavior_carrier", "pseudo_bindings", "disposition"},
                set(row),
            )
            for binding in row["bindings"]:
                self.assertIn("GENERATED", binding["evidence"]["path"])
                self.assertNotIn("observation.json", binding["evidence"]["path"])
                self.assertEqual({"route_key", "viewport", "state_id", "component_key", "evidence", "source_state"}, set(binding))
        self.assertIn("construction_authorization", payload)
        self.assertIn("source_contribution_scope", payload)
        self.assertFalse(payload["completeness"]["wrapper_inheritance_allowed"])


if __name__ == "__main__":
    unittest.main()
