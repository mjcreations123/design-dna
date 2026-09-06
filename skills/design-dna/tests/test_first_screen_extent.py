"""A source-bound primary region may be tall; a later/unbound region may not."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("extent_phase", SCRIPTS / "construction_phase.py")
PHASE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PHASE)


def node_json(program):
    result = subprocess.run(["node", "--input-type=module", "-e", program], capture_output=True, text=True, encoding="utf-8", timeout=90)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return json.loads(result.stdout)


class FirstScreenExtentTests(unittest.TestCase):
    def fixture(self, height=1800, tag="main"):
        record = {"path": ".design-dna/references/source-styles.json", "sha256": "a" * 64}
        mapping = {"proof_isolation": {"primary_route_key": "home", "region_component_id": "hero", "decision_ids": ["hero-layout"]},
                   "planned_decision_ids": ["hero-layout"], "decisions": [{"decision_id": "hero-layout", "component_id": "hero", "category": "layout",
                       "source_mapping": {"id": "strong-1", "source_selector": "#hero"}, "style_provenance": {"record": record},
                       "bindings": [{"route_key": "home", "viewport": "wide", "state_id": "rest", "source_state": {"id": "rest"}}]}]}
        styles = {record["path"]: {"component_styles": [{"selector": "#hero", "profile": "wide", "state_id": "rest",
            "geometry": {"left": 0, "top": 0, "width": 1440, "height": height}, "content_facts": {"tag": tag, "parent_selector": None}, "properties": {"margin": "0px"}}]}}
        return mapping, styles

    def test_tall_scope_requires_exact_source_extent_in_both_languages(self):
        mapping, styles = self.fixture()
        authority = PHASE.derive_first_screen_region_authority(mapping, styles, "home", "wide", "rest", 900)
        scope = {"document_height": 1800, "viewport_height": 900, "substantial_regions": [{"top": 0, "bottom": 1800, "width": 1440, "height": 1800, "component_id": "hero", "component_key": "component:hero"}],
                 "beyond_first_screen_regions": [], "source_extent": authority, "outside_primary_components": [],
                 "extra_primary_regions": [], "unplanned_decision_ids": [], "unsourced_visible_parts": [], "wrapper_inherited_visible_parts": [], "reused_decision_ids": []}
        self.assertFalse(PHASE.first_screen_scope_pass(scope))
        self.assertTrue(PHASE.first_screen_scope_pass(scope, authority))
        for defect in ("too-long", "too-short", "second", "unplanned"):
            mutated = copy.deepcopy(scope)
            if defect == "too-long": mutated["document_height"] += 100
            elif defect == "too-short": mutated["substantial_regions"][0]["height"] = 900
            elif defect == "second": mutated["substantial_regions"].append({"top": 900, "bottom": 1800})
            else: mutated["unplanned_decision_ids"] = ["future"]
            self.assertFalse(PHASE.first_screen_scope_pass(mutated, authority), defect)
        result = node_json(f"import {{deriveFirstScreenRegionAuthority,proofRegionScopePass}} from {json.dumps((SCRIPTS / 'construction_phase.mjs').as_uri())}; const a=deriveFirstScreenRegionAuthority({json.dumps(mapping)},{json.dumps(styles)},'home','wide','rest',900);console.log(JSON.stringify({{authority:a,pass:proofRegionScopePass({json.dumps(scope)},a)}}));")
        self.assertEqual(authority, result["authority"])
        self.assertTrue(result["pass"])

    def test_document_alias_or_sequential_page_wrapper_cannot_authorize_a_full_page(self):
        for tag in ("body", "html", "main", "div", "nested-div"):
            mapping, styles = self.fixture(3600, "div" if tag == "nested-div" else tag)
            if tag in {"main", "div", "nested-div"}:
                if tag == "nested-div":
                    styles[next(iter(styles))]["component_styles"].append({"selector": "#bridge", "profile": "wide", "state_id": "rest",
                        "geometry": {"left": 0, "top": 0, "width": 1440, "height": 3600}, "content_facts": {"tag": "article", "parent_selector": "#hero"}})
                for selector, top, height in (("#opening", 0, 900), ("#later", 900, 2700)):
                    styles[next(iter(styles))]["component_styles"].append({"selector": selector, "profile": "wide", "state_id": "rest",
                        "geometry": {"left": 0, "top": top, "width": 1440, "height": height},
                        "content_facts": {"tag": "section", "parent_selector": "#bridge" if tag == "nested-div" else "#hero"}})
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                PHASE.derive_first_screen_region_authority(mapping, styles, "home", "wide", "rest", 900)
            result = node_json(f"import {{deriveFirstScreenRegionAuthority}} from {json.dumps((SCRIPTS / 'construction_phase.mjs').as_uri())};let blocked=false;try{{deriveFirstScreenRegionAuthority({json.dumps(mapping)},{json.dumps(styles)},'home','wide','rest',900)}}catch{{blocked=true}}console.log(JSON.stringify(blocked));")
            self.assertTrue(result)

    def test_one_exact_source_bound_nested_region_is_not_a_later_section(self):
        mapping, styles = self.fixture()
        child = copy.deepcopy(mapping["decisions"][0])
        child.update({"decision_id": "nested-layout", "component_id": "nested"})
        child["source_mapping"]["source_selector"] = "#nested"
        mapping["decisions"].append(child)
        mapping["proof_isolation"]["decision_ids"].append("nested-layout")
        styles[next(iter(styles))]["component_styles"].append({"selector": "#nested", "profile": "wide", "state_id": "rest",
            "geometry": {"left": 0, "top": 0, "width": 1440, "height": 1800}, "content_facts": {"tag": "article", "parent_selector": "#hero"}})
        authority = PHASE.derive_first_screen_region_authority(mapping, styles, "home", "wide", "rest", 900)
        self.assertEqual(["nested"], authority["nested_region_component_ids"])
        result = node_json(f"import {{deriveFirstScreenRegionAuthority}} from {json.dumps((SCRIPTS / 'construction_phase.mjs').as_uri())}; console.log(JSON.stringify(deriveFirstScreenRegionAuthority({json.dumps(mapping)},{json.dumps(styles)},'home','wide','rest',900)));")
        self.assertEqual(authority, result)

    def test_real_responsive_hero_and_pinned_runway_preserve_scope_and_initial_geometry(self):
        program = f"""
import fs from 'node:fs';import os from 'node:os';import path from 'node:path';import {{createHash}} from 'node:crypto';
import {{chromium}} from {json.dumps((SCRIPTS.parents[2] / 'maintainer/node_modules/playwright/index.mjs').as_uri())};
import {{installDomInspection}} from {json.dumps((SCRIPTS / 'browser_evidence.mjs').as_uri())};
import {{firstScreenRegionAuthority,firstScreenScopePass,captureState}} from {json.dumps((SCRIPTS / 'scan_build_components.mjs').as_uri())};
import {{mergeDecisionRootSamples}} from {json.dumps((SCRIPTS / 'construction_phase.mjs').as_uri())};
const project=fs.mkdtempSync(path.join(os.tmpdir(),'dna-primary-extent-'));fs.mkdirSync(path.join(project,'.design-dna/references'),{{recursive:true}});
const browser=await chromium.launch();const results=[];
try {{
for (const mode of ['responsive','pinned','nested','collapsed']) for (const profile of ['wide','narrow']) {{
 const viewport=profile==='wide'?{{width:1440,height:900}}:{{width:390,height:844}};
 const context=await browser.newContext({{viewport}});await installDomInspection(context);const page=await context.newPage();
 const height=mode==='collapsed'?1400:mode==='pinned'?(profile==='wide'?2700:2500):(profile==='wide'?900:1500);
 const nested=mode==='nested';
 const html=`<html><head><style>body{{margin:0 0 ${{mode==='collapsed'?20:0}}px;font-family:sans-serif}}#hero{{height:${{height}}px;margin-bottom:${{mode==='collapsed'?30:0}}px}}#scene{{position:${{mode==='pinned'?'sticky':'relative'}};top:0;height:${{mode==='pinned'?'100vh':'100%'}}}}h1{{margin:0}}article{{height:100%}}</style></head><body id="body"><div id="mount"><main id="hero" data-design-dna-component="hero" data-design-dna-decision-id="hero-layout">${{nested?'<article id="nested" data-design-dna-component="nested" data-design-dna-decision-id="nested-layout">':''}}<div id="scene" data-design-dna-component="scene" data-design-dna-decision-id="scene-layout"><h1 id="title" data-design-dna-component="title" data-design-dna-decision-id="title-copy">Measured synthetic source hero</h1></div>${{nested?'</article>':''}}</main></div></body></html>`;
 await context.route('https://extent-fixture.test/**',route=>route.fulfill({{status:200,contentType:'text/html',body:html}}));await page.goto('https://extent-fixture.test/');
 const styles=await page.evaluate((profile)=>({{component_styles:[...document.querySelectorAll('[id]')].map(element=>{{const r=element.getBoundingClientRect(),p=element.parentElement?.getBoundingClientRect()||{{left:0,top:0}},style=getComputedStyle(element);return {{selector:'#'+element.id,profile,state_id:'rest',geometry:{{left:Math.round(r.left-p.left),top:Math.round(r.top-p.top),width:Math.round(r.width),height:Math.round(r.height)}},content_facts:{{tag:element.tagName.toLowerCase(),role:element.getAttribute('role'),parent_selector:element.parentElement?.id?'#'+element.parentElement.id:null,parent_tag:element.parentElement?.tagName.toLowerCase()}},properties:{{margin:style.margin,padding:style.padding}}}}}})}}),profile);
 const record={{path:'.design-dna/references/source-styles.json',sha256:createHash('sha256').update(JSON.stringify(styles)).digest('hex')}};fs.writeFileSync(path.join(project,record.path),JSON.stringify(styles));
 const ids=['hero','scene','title',...(nested?['nested']:[])];
 const decisions=ids.map(id=>({{decision_id:id==='title'?'title-copy':id+'-layout',component_id:id,category:id==='title'?'typeface':'layout',source_mapping:{{id:'strong-1',source_selector:'#'+id}},style_provenance:{{record}},bindings:[{{route_key:'home',viewport:profile,state_id:'rest',source_state:{{id:'rest'}}}}]}}));
 const mapping={{proof_isolation:{{primary_route_key:'home',region_component_id:'hero',decision_ids:decisions.map(row=>row.decision_id)}},planned_decision_ids:decisions.map(row=>row.decision_id),decisions}};
 const authority=firstScreenRegionAuthority(project,mapping,'home',profile,'rest',viewport.height);
 const state={{id:'rest',kind:'rest',trigger:{{type:'none',target:'document',value:null}},expectation:'The measured primary region and its exact source runway'}};
 const capture=await captureState(page,state,true,authority);const roots=mergeDecisionRootSamples(capture.snapshots.map(row=>row.decision_roots));
 const positive=capture.covered===1&&capture.scroll.complete&&capture.snapshots.every(row=>firstScreenScopePass(row.implementation_scope,authority));
 const sceneSamples=capture.snapshots.flatMap(row=>row.decision_roots.filter(root=>root.decision_id==='scene-layout').flatMap(row=>row.roots.map(root=>root.geometry.top)));
 await page.evaluate(()=>{{const extra=document.createElement('div');extra.id='unplanned';extra.textContent='Unbound overlay';extra.style.cssText='position:absolute;top:60px;left:0';document.querySelector('#hero').append(extra);}});const unbound=await captureState(page,state,true,authority);
 await page.evaluate(()=>{{document.querySelector('#unplanned').remove();const extra=document.createElement('div');extra.id='duplicate';extra.dataset.designDnaComponent='scene';extra.dataset.designDnaDecisionId='scene-layout';extra.style.cssText='position:absolute;top:80px;left:0;width:100px;height:20px';document.querySelector('#hero').append(extra);}});const duplicate=await captureState(page,state,true,authority);
 await page.evaluate(()=>document.querySelector('#duplicate').remove());
 await page.evaluate(()=>{{document.body.style.paddingBottom='100px';}});const overshoot=await captureState(page,state,true,authority);
 await page.evaluate(()=>{{document.body.style.paddingBottom='0px';const extra=document.createElement('section');extra.textContent='Future region';extra.style.height='100px';extra.dataset.designDnaComponent='future';extra.dataset.designDnaDecisionId='future';document.body.append(extra);}});const second=await captureState(page,state,true,authority);
 fs.appendFileSync(path.join(project,record.path),' ');let driftBlocked=false;try{{firstScreenRegionAuthority(project,mapping,'home',profile,'rest',viewport.height)}}catch{{driftBlocked=true}}
 results.push({{mode,profile,positive,authority,scope:capture.snapshots[0].implementation_scope,samples:capture.snapshots.length,traversed:capture.scroll.surfaces.length,sceneSamples,roots,
 overshoot:firstScreenScopePass(overshoot.snapshots[0].implementation_scope,authority),second:firstScreenScopePass(second.snapshots[0].implementation_scope,authority),
 unbound:firstScreenScopePass(unbound.snapshots[0].implementation_scope,authority),duplicate:firstScreenScopePass(duplicate.snapshots[0].implementation_scope,authority),driftBlocked}});await context.close();
}}
console.log(JSON.stringify(results));
}} finally {{await browser.close();fs.rmSync(project,{{recursive:true,force:true}})}}
"""
        results = node_json(program)
        self.assertEqual(8, len(results))
        for result in results:
            with self.subTest(mode=result["mode"], profile=result["profile"]):
                self.assertTrue(result["positive"], result)
                self.assertTrue(PHASE.first_screen_scope_pass(result["scope"], result["authority"]))
                self.assertFalse(result["overshoot"])
                self.assertFalse(result["second"])
                self.assertFalse(result["unbound"])
                self.assertFalse(result["duplicate"])
                self.assertTrue(result["driftBlocked"])
                if result["scope"]["document_height"] > result["scope"]["viewport_height"]:
                    self.assertGreater(result["samples"], 1)
                    self.assertGreater(result["traversed"], 0)
                scene = next(row for row in result["roots"] if row["decision_id"] == "scene-layout")
                self.assertEqual(1, len(scene["roots"]))
                self.assertEqual(result["sceneSamples"][0], scene["roots"][0]["geometry"]["top"])
                if result["mode"] == "pinned": self.assertGreater(max(result["sceneSamples"]), 0)
                if result["mode"] == "collapsed":
                    self.assertLess(result["scope"]["document_height"], result["authority"]["document_height_ceiling"])

    def test_bound_nested_standard_ast_does_not_weaken_the_internal_static_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "proof.tsx"
            file.write_text('<main data-design-dna-component="hero" data-design-dna-proof-status="internal-unverified"><article data-design-dna-component="nested" /></main>', encoding="utf-8")
            command = ["node", str(SCRIPTS / "proof_isolation_ast.mjs"), "--file", str(file), "--strict-component-maps",
                       "--required-component", "hero", "--required-component", "nested", "--allow-bound-nested-regions"]
            standard = subprocess.run(command, capture_output=True, text=True, timeout=15)
            self.assertEqual(0, standard.returncode, standard.stdout + standard.stderr)
            internal = subprocess.run([*command, "--require-proof-label"], capture_output=True, text=True, timeout=15)
            self.assertNotEqual(0, internal.returncode)
            self.assertIn("proof-region-count", internal.stdout)

    def test_repeated_scroll_sample_is_not_a_duplicate_but_simultaneous_roots_are(self):
        first = [{"decision_id": "hero", "roots": [{"component_id": "hero", "geometry": {"top": 0}}]}]
        later = [{"decision_id": "hero", "roots": [{"component_id": "hero", "geometry": {"top": 900}}]}]
        self.assertEqual(first, PHASE.merge_decision_root_samples([first, later]))
        duplicate = [{"decision_id": "hero", "roots": first[0]["roots"] + later[0]["roots"]}]
        self.assertEqual(duplicate, PHASE.merge_decision_root_samples([first, duplicate]))
        result = node_json(f"import {{mergeDecisionRootSamples}} from {json.dumps((SCRIPTS / 'construction_phase.mjs').as_uri())};console.log(JSON.stringify([mergeDecisionRootSamples({json.dumps([first,later])}),mergeDecisionRootSamples({json.dumps([first,duplicate])})]));")
        self.assertEqual([first, duplicate], result)


if __name__ == "__main__": unittest.main()
