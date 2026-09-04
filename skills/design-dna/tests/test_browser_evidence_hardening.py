#!/usr/bin/env python3
"""Focused regressions for exact browser/source evidence producers."""

from __future__ import annotations

import json
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
            self.assertIn(f'"{kind}"', text)
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

    def test_interaction_targets_bind_accessible_text_and_semantic_identity(self) -> None:
        helper = (SCRIPTS / "browser_evidence.mjs").read_text(encoding="utf-8")
        census = helper.split("export async function captureInteractionCensus", 1)[1]
        self.assertIn("const semanticKey = `${role.toLowerCase()}|${text.toLowerCase()}`", census)
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
        self.assertEqual(1, payload["schema_version"])
        self.assertEqual("rest", payload["states"][0]["id"])
        self.assertEqual({"type": "none", "target": "document", "value": None}, payload["states"][0]["trigger"])

    def test_visible_decision_template_has_every_category_and_frame_evidence(self) -> None:
        payload = json.loads(
            (SKILL / "templates" / "visible-decision-source-manifest-template.json")
            .read_text(encoding="utf-8")
        )
        expected = [
            "layout", "typeface", "color", "control", "transition",
            "content-pattern", "effect",
        ]
        self.assertEqual(expected, payload["completeness"]["required_categories"])
        self.assertEqual(expected, [row["category"] for row in payload["decisions"]])
        self.assertEqual(
            payload["planned_decision_ids"],
            [row["decision_id"] for row in payload["decisions"]],
        )
        for row in payload["decisions"]:
            self.assertIn("GENERATED_OBSERVER_CAPTURE_OR_STATE_FRAME", row["evidence"]["path"])
            self.assertNotIn("observation.json", row["evidence"]["path"])


if __name__ == "__main__":
    unittest.main()
