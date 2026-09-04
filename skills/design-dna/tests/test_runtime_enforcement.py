#!/usr/bin/env python3
"""Behavioral regressions for the fail-closed runtime evidence chain."""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
NODE = shutil.which("node")


def script_hash(name: str) -> str:
    return hashlib.sha256((SCRIPTS / name).read_bytes()).hexdigest()


def node_module(module: str, expression: str) -> dict:
    uri = (SCRIPTS / module).resolve().as_uri()
    code = f'import * as m from {json.dumps(uri)}; const value = ({expression}); process.stdout.write(JSON.stringify(value));'
    done = subprocess.run([NODE, "--input-type=module", "-e", code], capture_output=True, text=True, encoding="utf-8")
    if done.returncode:
        raise AssertionError(done.stderr or done.stdout)
    return json.loads(done.stdout)


def write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def write_png(path: Path) -> tuple[int, str]:
    data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return len(data), hashlib.sha256(data).hexdigest()


class GateManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("gate_runtime", SCRIPTS / "gate.py")
        cls.gate = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(cls.gate)
        cls.validator = cls.gate.load_validator()

    def valid_manifest(self) -> dict:
        return {
            "schema_version": 2,
            "manifest_id": "manifest-identity-123",
            "viewports": [
                {"name": "wide", "width": 1440, "height": 900},
                {"name": "narrow", "width": 390, "height": 844},
            ],
            "routes": [
                {"key": "home", "url": "http://127.0.0.1:9000/", "mapped_reference_rank": 1,
                 "mapped_reference_id": "strong-1",
                 "mapped_reference_observation": ".design-dna/references/strong-1-observation.json",
                 "mapped_reference_sha256": "0" * 64,
                 "states": [{"id": "rest", "kind": "rest",
                             "trigger": {"type": "none", "target": "document", "value": None},
                             "expectation": "initial settled route",
                             "mapped_reference_state_id": "rest"}]},
            ],
        }

    def materialize_manifest(self, project: Path, payload: dict) -> Path:
        state_contract = write_json(
            project / ".design-dna" / "references" / "strong-1-state-contract.json",
            {
                "schema_version": 1,
                "reference_id": "strong-1",
                "states": [{
                    "id": "rest",
                    "url": "https://reference.test/",
                    "kind": "rest",
                    "trigger": {"type": "none", "target": "document", "value": None},
                    "expectation": "Initial settled reference route.",
                }],
            },
        )
        frame_dir = project / ".design-dna" / "references" / "strong-1-frames"
        frame_bytes, frame_sha = write_png(frame_dir / "state.png")
        frame = {
            "seq": 1,
            "kind": "state",
            "file": "state.png",
            "bytes": frame_bytes,
            "sha256": frame_sha,
        }
        bound_frame = {
            "file": "strong-1-frames/state.png",
            "bytes": frame_bytes,
            "sha256": frame_sha,
        }
        navigation = {
            "requested_normalized_url": "https://reference.test/",
            "final_normalized_url": "https://reference.test/",
            "response_final_normalized_url": "https://reference.test/",
            "redirect_count": 0,
            "final_status": 200,
        }
        rendered_qa_by_viewport = {
            profile: {
                "profile": profile,
                "pages": [{
                    "url": "https://reference.test/",
                    "evidence": bound_frame,
                    "clipping": [], "collisions": [], "fixed_rail_overlaps": [],
                    "hidden_controls": [], "control_visibility": [],
                    "dead_controls": [], "semantic_issues": [], "overlays": [],
                    "keyboard_paths": [],
                    "keyboard": {"complete": True, "missing": []},
                    "semantic_equivalence": {"complete": True, "mismatches": []},
                    "state_semantics": {
                        "required": False, "complete": True,
                        "target": None, "attributes": None,
                    },
                    "reduced_motion": {
                        "navigation": navigation, "animations": [],
                        "evidence": bound_frame,
                        "honors_preference": True, "complete": True,
                    },
                    "deep_link": {
                        "navigation": navigation, "evidence": bound_frame,
                        "complete": True,
                    },
                    "reload": {
                        "navigation": navigation, "before": bound_frame,
                        "after": bound_frame, "stable_pixels": True,
                        "complete": True,
                    },
                    "dead_end": {
                        "same_origin_destinations": ["https://reference.test/"],
                        "is_dead_end": False, "terminal_signal": False,
                        "problem": False,
                    },
                }],
                "totals": {"pages": 1, "issues": 0, "controls": 0, "overlays": 0},
                "truncated": False, "missing": [], "complete": True,
            }
            for profile in ("wide", "narrow")
        }
        observation = write_json(project / ".design-dna" / "references" / "strong-1-observation.json", {
                "tool": "observe_reference.mjs",
                "schema_version": self.gate.packaged_schema_version(SCRIPTS / "observe_reference.mjs"),
                "producer_script_sha256": script_hash("observe_reference.mjs"),
                "runtime_identity": {"observe_reference.mjs": script_hash("observe_reference.mjs")},
                "id": "strong-1",
                "url": "https://reference.test/",
                "frame_dir": "strong-1-frames",
                "frames": [frame],
                "state_contract": {
                    "file": state_contract.name,
                    "sha256": hashlib.sha256(state_contract.read_bytes()).hexdigest(),
                },
                "discovery_metadata": {
                    profile: {
                        "discovered_urls": ["https://reference.test/"],
                        "visited_urls": ["https://reference.test/"],
                        "source_state_ids": ["rest"],
                    }
                    for profile in ("wide", "narrow")
                },
                "interaction_census_by_viewport": {
                    profile: {
                        "profile": profile,
                        "pages": [{
                            "url": "https://reference.test/",
                            "targets": [],
                            "dom_code_inventory": {
                                "routes_discovered": [],
                                "controls_discovered": [],
                                "state_hooks": [],
                                "animation_hooks": [],
                                "assets": [],
                                "scripts": [],
                                "inline_handlers": [],
                                "live_target_ids": [],
                                "live_source_state_ids": ["rest"],
                                "unreconciled_controls": [],
                                "complete": True,
                            },
                        }],
                        "page_states": [{
                            "source_state_id": "rest",
                            "kind": "rest",
                            "trigger": {"type": "none", "target": "document", "value": None},
                            "page_url": "https://reference.test/",
                            "disposition": "observed-rest",
                            "trigger_evidence": {
                                "before_sha256": "0" * 64,
                                "after_sha256": "0" * 64,
                                "settled_sha256": "0" * 64,
                                "changed_properties": [],
                                "change_classification": {
                                    "cosmetic": [], "structural_semantic": [], "diagnostic": [],
                                },
                                "behavior": "settled rest state",
                            },
                            "evidence": {
                                "before": bound_frame,
                                "after": bound_frame,
                                "settled": bound_frame,
                            },
                        }],
                        "repeat_classes": [],
                        "pointer_follow": [],
                        "blocked_side_effects": [],
                        "totals": {
                            "targets_discovered": 0,
                            "inputs_discovered": 0,
                            "inputs_exercised": 0,
                            "inputs_blocked": 0,
                        },
                        "truncated": False,
                        "missing": [],
                        "complete": True,
                    }
                    for profile in ("wide", "narrow")
                },
                "rendered_qa_by_viewport": rendered_qa_by_viewport,
                "states_by_viewport": {"wide": {"rest": {}}, "narrow": {"rest": {}}},
            })
        digest = hashlib.sha256(observation.read_bytes()).hexdigest()
        for route in payload["routes"]:
            route["mapped_reference_sha256"] = digest
        return write_json(project / ".design-dna" / "route-manifest.json", payload)

    def load(self, payload: dict, selected=(1,)) -> dict:
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            file = self.materialize_manifest(project, payload)
            return self.gate.load_route_manifest(file, list(selected), project)

    def test_route_slug_cannot_collide_by_tail_or_host(self) -> None:
        values = {
            self.gate.route_slug("https://one.example/section/foo"),
            self.gate.route_slug("https://one.example/foo"),
            self.gate.route_slug("https://two.example/foo"),
        }
        self.assertEqual(3, len(values))

    def test_manifest_requires_both_wide_and_narrow(self) -> None:
        payload = self.valid_manifest()
        payload["viewports"] = [{"name": "wide", "width": 1440, "height": 900}]
        with self.assertRaisesRegex(ValueError, "narrow"):
            self.load(payload)

    def test_manifest_refuses_duplicate_normalized_urls(self) -> None:
        payload = self.valid_manifest()
        duplicate = dict(payload["routes"][0])
        duplicate["key"] = "other"
        payload["routes"].append(duplicate)
        with self.assertRaisesRegex(ValueError, "duplicates"):
            self.load(payload)

    def test_manifest_refuses_unselected_mapping(self) -> None:
        payload = self.valid_manifest()
        payload["routes"][0]["mapped_reference_rank"] = 2
        with self.assertRaisesRegex(ValueError, "not a selected"):
            self.load(payload)

    def test_unicode_route_paths_decode_but_encoded_path_escapes_fail(self) -> None:
        self.assertEqual(
            "/שלום/",
            self.validator.normalize_safe_route_path(
                "/%D7%A9%D7%9C%D7%95%D7%9D/"
            ),
        )
        self.assertEqual(
            "/é/",
            self.validator.normalize_safe_route_path("/e%CC%81/"),
        )
        for unsafe in ("/a%2Fb", "/a%5Cb", "/%2E%2E/secret", "/bad%FF", "/two%20words"):
            with self.subTest(unsafe=unsafe):
                self.assertIsNone(self.validator.normalize_safe_route_path(unsafe))
        payload = self.valid_manifest()
        payload["routes"][0]["url"] = (
            "http://127.0.0.1:9000/%D7%A9%D7%9C%D7%95%D7%9D/"
        )
        self.assertFalse(
            any(
                "encoded separators" in failure
                for failure in self.validator.route_manifest_payload_failures(payload)
            )
        )
        payload["routes"][0]["url"] = "http://127.0.0.1:9000/a%2Fb"
        self.assertTrue(
            any(
                "encoded separators" in failure
                for failure in self.validator.route_manifest_payload_failures(payload)
            )
        )

    def test_skip_extract_is_not_a_supported_gate_bypass(self) -> None:
        done = subprocess.run([
            sys.executable, "-B", str(SCRIPTS / "gate.py"), "--project", ".",
            "--build-id", "build-identity-123", "--route-manifest", "missing.json", "--skip-extract", "--dry-run",
        ], capture_output=True, text=True, encoding="utf-8")
        self.assertNotEqual(0, done.returncode)
        self.assertIn("unrecognized arguments", done.stderr.lower())

    def test_first_screen_phase_selects_one_planned_route_and_preserves_final_record(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest = self.valid_manifest()
            second_route = dict(manifest["routes"][0])
            second_route.update({"key": "about", "url": "http://127.0.0.1:9000/about"})
            manifest["routes"].append(second_route)
            manifest_path = self.materialize_manifest(root, manifest)
            refs = root / ".design-dna" / "references"
            write_json(refs / "strong-1-styles.json", {"tool": "extract_reference_styles.mjs", "schema_version": 2,
                                                       "viewports_measured": [{"width": 1440}, {"width": 390}]})
            observation = refs / "strong-1-observation.json"
            observation_sha = hashlib.sha256(observation.read_bytes()).hexdigest()
            frame = refs / "strong-1-frames" / "state.png"
            frame_sha = hashlib.sha256(frame.read_bytes()).hexdigest()
            categories = [
                "layout", "typeface", "color", "control", "transition",
                "content-pattern", "effect",
            ]
            visible = write_json(root / ".design-dna" / "visible-decision-sources.json", {
                "schema_version": 1,
                "record_type": "design-dna-visible-decision-source-manifest",
                "created_at": "2026-09-04T11:00:00Z",
                "proof_build_id": "build-identity-123",
                "route_manifest": {
                    "manifest_id": manifest["manifest_id"],
                    "path": ".design-dna/route-manifest.json",
                    "sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                },
                "source_observations": [{
                    "id": "strong-1",
                    "path": ".design-dna/references/strong-1-observation.json",
                    "sha256": observation_sha,
                }],
                "planned_decision_ids": [f"source-{category}" for category in categories],
                "decisions": [{
                    "decision_id": f"source-{category}",
                    "category": category,
                    "planned_surface": f"The {category} treatment across the complete primary composition.",
                    "route_keys": ["home", "about"],
                    "state_ids": ["rest"],
                    "source_reference_id": "strong-1",
                    "source_component_or_behavior": f"The measured reference {category} relationship captured before coding.",
                    "evidence": {
                        "path": ".design-dna/references/strong-1-frames/state.png",
                        "sha256": frame_sha,
                    },
                    "disposition": "required",
                } for category in categories],
                "completeness": {
                    "required_categories": categories,
                    "covered_categories": categories,
                    "placeholders_allowed": False,
                    "generic_scaffold_allowed": False,
                    "fallback_design_allowed": False,
                    "unsourced_decisions": [],
                },
            })
            (root / ".design-dna" / "reference-dossier.md").write_text(
                "## Selected synthesis\n\n- Selected positive ranks: 1\n\n"
                "## Route manifest\n\n"
                f"- Route manifest: .design-dna/route-manifest.json plus sha256:{hashlib.sha256(manifest_path.read_bytes()).hexdigest()}\n"
                "- First-screen proof build ID and primary route key: build_id=build-identity-123; route_key=home\n\n"
                "## Preimplementation visible decisions\n\n"
                f"- Visible decision source manifest: .design-dna/visible-decision-sources.json plus sha256:{hashlib.sha256(visible.read_bytes()).hexdigest()}\n",
                encoding="utf-8")
            final_record = write_json(root / ".design-dna" / "evidence" / "gate.json", {"sentinel": True})
            done = subprocess.run([
                sys.executable, "-B", str(SCRIPTS / "gate.py"), "--project", str(root),
                "--build-id", "build-identity-123", "--route-manifest", str(manifest_path),
                "--phase", "first-screen", "--route-key", "home", "--dry-run",
            ], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(0, done.returncode, done.stdout + done.stderr)
            payload = json.loads(done.stdout)
            self.assertEqual("first-screen", payload["phase"])
            self.assertEqual(["home"], [route["key"] for route in payload["active_routes"]])
            self.assertEqual({"sentinel": True}, json.loads(final_record.read_text(encoding="utf-8")))

    def test_failed_first_screen_run_writes_only_first_screen_record(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest_path = self.materialize_manifest(root, self.valid_manifest())
            final_record = write_json(root / ".design-dna" / "evidence" / "gate.json", {"sentinel": True})
            done = subprocess.run([
                sys.executable, "-B", str(SCRIPTS / "gate.py"), "--project", str(root),
                "--build-id", "build-identity-123", "--route-manifest", str(manifest_path),
                "--phase", "first-screen", "--route-key", "home",
            ], capture_output=True, text=True, encoding="utf-8")
            self.assertNotEqual(0, done.returncode)
            first = json.loads((root / ".design-dna" / "evidence" / "first-screen-gate.json").read_text(encoding="utf-8"))
            self.assertEqual("first-screen", first["phase"])
            self.assertEqual({"sentinel": True}, json.loads(final_record.read_text(encoding="utf-8")))

    def test_dom_discovered_control_omitted_from_live_census_fails_closed(self) -> None:
        target = "1" * 24
        census = {
            "profile": "wide",
            "pages": [{
                "url": "https://reference.test/",
                "targets": [],
                "dom_code_inventory": {
                    "routes_discovered": [],
                    "controls_discovered": [target],
                    "state_hooks": [],
                    "animation_hooks": [],
                    "assets": [],
                    "scripts": [],
                    "inline_handlers": [],
                    "live_target_ids": [],
                    "live_source_state_ids": ["rest"],
                    "unreconciled_controls": [target],
                    "complete": False,
                },
            }],
            "page_states": [{"source_state_id": "rest"}],
            "repeat_classes": [],
            "pointer_follow": [],
            "blocked_side_effects": [],
            "totals": {
                "targets_discovered": 0,
                "inputs_discovered": 0,
                "inputs_exercised": 0,
                "inputs_blocked": 0,
            },
            "truncated": False,
            "missing": [],
            "complete": True,
        }
        failures = self.validator.interaction_census_failures(
            census,
            expected_profile="wide",
            expected_state_ids={"rest"},
            expected_urls={"https://reference.test/"},
        )
        self.assertTrue(any("DOM/code-discovered" in failure for failure in failures))

    def test_saturation_only_dead_control_and_false_repeat_equivalence_fail(self) -> None:
        target_id = "2" * 24
        frame = {"file": "frame.png", "bytes": 10, "sha256": "a" * 64}
        input_record = {
            "input_kind": "hover",
            "input_value": None,
            "safety": "safe",
            "status": "exercised",
            "source_state_id": None,
            "before_sha256": "b" * 64,
            "after_sha256": "c" * 64,
            "settled_sha256": "c" * 64,
            "changed_properties": [
                {"component_key": "class:role-card", "property": "filter", "before": "none", "after": "saturate(1.08)"},
            ],
            "change_classification": {
                "cosmetic": [
                    {"component_key": "class:role-card", "property": "filter", "before": "none", "after": "saturate(1.08)"}
                ],
                "structural_semantic": [],
                "diagnostic": [
                    {"component_key": "class:role-card", "property": "hovered", "before": False, "after": True}
                ],
            },
            "behavior": "filter saturation changed on hover without a state or action result",
            "evidence": {"before": frame, "after": frame, "settled": frame},
            "disposition": "sourceable-observed-behavior",
        }
        census = {
            "profile": "wide",
            "pages": [{
                "url": "https://reference.test/",
                "targets": [{
                    "target_id": target_id,
                    "page_url": "https://reference.test/",
                    "selector": '[data-dna-interaction-id="1"]',
                    "tag": "button",
                    "role": "button",
                    "text": "Change view",
                    "semantic_key": "button|change view",
                    "class_signature": ["role-card"],
                    "repeat_class": "button|button|role-card",
                    "repeat_index": 1,
                    "repeat_count": 1,
                    "kind": "control",
                    "semantic_state": {
                        "aria_expanded": None,
                        "aria_pressed": None,
                        "aria_controls": None,
                        "aria_haspopup": None,
                        "disabled": False,
                    },
                    "source_state_ids": [],
                    "inputs": [input_record],
                }],
                "dom_code_inventory": {
                    "routes_discovered": [],
                    "controls_discovered": [target_id],
                    "state_hooks": [],
                    "animation_hooks": [],
                    "assets": [],
                    "scripts": [],
                    "inline_handlers": [],
                    "live_target_ids": [target_id],
                    "live_source_state_ids": ["rest"],
                    "unreconciled_controls": [],
                    "complete": True,
                },
            }],
            "page_states": [{
                "source_state_id": "rest",
                "kind": "rest",
                "trigger": {"type": "none", "target": "document", "value": None},
                "page_url": "https://reference.test/",
                "disposition": "observed-rest",
                "trigger_evidence": {
                    "before_sha256": "d" * 64,
                    "after_sha256": "d" * 64,
                    "settled_sha256": "d" * 64,
                    "changed_properties": [],
                    "change_classification": {
                        "cosmetic": [], "structural_semantic": [], "diagnostic": []
                    },
                    "behavior": "settled rest state",
                },
                "evidence": {"before": frame, "after": frame, "settled": frame},
            }],
            "repeat_classes": [{
                "repeat_class": "button|button|role-card",
                "target_ids": [target_id],
                "input_kinds": ["hover"],
                "equivalent": False,
                "behavior_signatures": ["hover:filter-only"],
                "evidence": [frame],
            }],
            "pointer_follow": [],
            "blocked_side_effects": [],
            "totals": {
                "targets_discovered": 1,
                "inputs_discovered": 1,
                "inputs_exercised": 1,
                "inputs_blocked": 0,
            },
            "truncated": False,
            "missing": [],
            "complete": True,
        }
        failures = self.validator.interaction_census_failures(
            census,
            expected_profile="wide",
            expected_state_ids={"rest"},
            expected_urls={"https://reference.test/"},
        )
        self.assertTrue(any("visually/semantically dead" in failure for failure in failures), failures)
        self.assertTrue(any("incomplete or gameable" in failure for failure in failures), failures)

    def test_prebuild_chain_binds_immutable_gate_manifest_dossier_and_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw).resolve()
            authorization_id = "1" * 32
            run_root = (
                project / ".design-dna" / "evidence" / "prebuild-runs" / authorization_id
            )
            manifest = write_json(run_root / "route-manifest.json", {"immutable": True})
            dossier = run_root / "reference-dossier.md"
            dossier.write_text("# dossier\n\n- First-screen gate: pending\n", encoding="utf-8")
            visible = write_json(
                project / ".design-dna" / "visible-decision-sources.json",
                {"immutable": "visible-source"},
            )
            visible_snapshot = write_json(
                run_root / "visible-decision-sources.json",
                {"immutable": "visible-source"},
            )
            manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
            dossier_sha = hashlib.sha256(dossier.read_bytes()).hexdigest()
            visible_sha = hashlib.sha256(visible.read_bytes()).hexdigest()
            dossier_core = self.validator.dossier_core_sha256(dossier)
            runtime = self.validator.packaged_gate_runtime_identity()
            gate = {
                "tool": "gate.py",
                "schema_version": 2,
                "phase": "first-screen",
                "pass": True,
                "project": str(project),
                "authorization_id": authorization_id,
                "route_key": "home",
                "build_id": "proof-build-123",
                "build_tree_sha256_before": "2" * 64,
                "build_tree_sha256_after": "2" * 64,
                "build_stable": True,
                "manifest_id": "manifest-identity-123",
                "route_manifest_sha256": manifest_sha,
                "dossier_core_sha256": dossier_core,
                "producer_script_sha256": runtime["gate.py"],
                "runtime_identity": runtime,
                "manifest_snapshot": {
                    "path": manifest.relative_to(project).as_posix(),
                    "sha256": manifest_sha,
                },
                "dossier_snapshot": {
                    "path": dossier.relative_to(project).as_posix(),
                    "sha256": dossier_sha,
                },
                "visible_decision_source_manifest": {
                    "path": ".design-dna/visible-decision-sources.json",
                    "sha256": visible_sha,
                },
                "visible_decision_snapshot": {
                    "path": visible_snapshot.relative_to(project).as_posix(),
                    "sha256": visible_sha,
                },
                "evidence_hashes": [
                    {"path": visible.relative_to(project).as_posix(), "sha256": visible_sha},
                    {"path": manifest.relative_to(project).as_posix(), "sha256": manifest_sha},
                    {"path": dossier.relative_to(project).as_posix(), "sha256": dossier_sha},
                    {"path": visible_snapshot.relative_to(project).as_posix(), "sha256": visible_sha},
                ],
            }
            gate_path = write_json(run_root / "gate.json", gate)
            gate_sha = hashlib.sha256(gate_path.read_bytes()).hexdigest()
            auth = {
                "schema_version": 1,
                "record_type": "design-dna-prebuild-authorization",
                "authorization_id": authorization_id,
                "authorized_at": "2026-09-04T12:00:00Z",
                "project": str(project),
                "manifest_id": "manifest-identity-123",
                "manifest_sha256": manifest_sha,
                "route_key": "home",
                "proof_build_id": "proof-build-123",
                "proof_tree_sha256": "2" * 64,
                "dossier_core_sha256": dossier_core,
                "visible_decision_source_manifest": {
                    "path": ".design-dna/visible-decision-sources.json",
                    "sha256": visible_sha,
                },
                "visible_decision_snapshot": {
                    "path": visible_snapshot.relative_to(project).as_posix(),
                    "sha256": visible_sha,
                },
                "first_screen_gate": {
                    "path": gate_path.relative_to(project).as_posix(),
                    "sha256": gate_sha,
                },
                "previous_authorization": None,
                "producer_script_sha256": runtime["gate.py"],
                "runtime_identity": runtime,
            }
            write_json(
                project / ".design-dna" / "evidence" / "prebuild-authorizations" / "001.json",
                auth,
            )
            failures, records = self.validator.prebuild_authorization_chain(project)
            self.assertEqual([], failures)
            self.assertEqual(1, len(records))
            visible.write_text('{"changed": true}\n', encoding="utf-8")
            failures, _records = self.validator.prebuild_authorization_chain(project)
            self.assertTrue(any("visible-decision" in failure for failure in failures), failures)
            visible.write_bytes(visible_snapshot.read_bytes())
            dossier.write_text("tampered\n", encoding="utf-8")
            failures, _records = self.validator.prebuild_authorization_chain(project)
            self.assertTrue(any("snapshot" in failure or "ledger" in failure for failure in failures))

    def test_claimed_passing_interaction_diff_cannot_hide_behavior_mismatch(self) -> None:
        def census(after: str) -> dict:
            return {
                "complete": True,
                "truncated": False,
                "missing": [],
                "totals": {"targets_discovered": 1},
                "pointer_follow": [],
                "pages": [{
                    "targets": [{
                        "target_id": "1" * 24,
                        "repeat_class": "button|button|primary",
                        "repeat_index": 1,
                        "class_signature": ["primary"],
                        "tag": "button",
                        "role": "button",
                        "inputs": [{
                            "status": "exercised",
                            "input_kind": "click",
                            "input_value": None,
                            "source_state_id": "rest",
                            "before_sha256": "a" * 64,
                            "settled_sha256": "b" * 64,
                            "changed_properties": [{
                                "property": "background_color",
                                "before": "black",
                                "after": after,
                            }],
                            "disposition": "sourceable-observed-behavior",
                        }],
                    }],
                }],
            }

        source = census("white")
        build = census("red")
        claimed = {
            "pass": True,
            "failures": [],
            "target_transfers": [],
        }
        recomputed = self.validator.recompute_interaction_transfer(
            build,
            source,
            [{"id": "rest", "mapped_reference_state_id": "rest"}],
        )
        self.assertFalse(recomputed["pass"])
        self.assertNotEqual(claimed, recomputed)
        self.assertTrue(any("does not exactly match" in item for item in recomputed["failures"]))

    def test_interaction_frame_ledger_refuses_linked_external_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            record = root / "mechanism-diff.json"
            directory = root / "mechanism-diff-interaction-frames"
            directory.mkdir()
            outside = root / "outside.png"
            size, digest = write_png(outside)
            link = directory / "linked.png"
            try:
                os.symlink(outside, link)
            except OSError as exc:
                link.write_bytes(outside.read_bytes())
                simulated_reparse = exc
            else:
                simulated_reparse = None
            payload = {
                "interaction_frame_directory": directory.name,
                "evidence": {
                    "file": f"{directory.name}/linked.png",
                    "bytes": size,
                    "sha256": digest,
                },
            }
            if simulated_reparse is None:
                failures, bindings = self.validator.generated_interaction_frame_bindings(
                    payload,
                    record_path=record,
                )
            else:
                original = self.validator.is_reparse
                with patch.object(
                    self.validator,
                    "is_reparse",
                    side_effect=lambda path: Path(path) == link or original(Path(path)),
                ):
                    failures, bindings = self.validator.generated_interaction_frame_bindings(
                        payload,
                        record_path=record,
                    )
            self.assertEqual([], bindings)
            self.assertTrue(any("link/reparse" in failure for failure in failures), failures)


@unittest.skipIf(NODE is None, "node is required")
class PureRuntimeBehaviorTests(unittest.TestCase):
    def test_component_identity_keeps_every_class_and_bem_element(self) -> None:
        value = node_module("scan_build_components.mjs", 'm.classKeys("card card__title card--loud utility")')
        self.assertEqual(["class:card", "class:card--loud", "class:card__title", "class:utility"], value)

    def test_responsive_omission_must_match_the_exact_source_control(self) -> None:
        candidates = [
            {"target": "#view-toggle", "semantic_key": "button|change view"},
            {"target": "#menu", "semantic_key": "button|menu"},
        ]
        wide = {"pages": [{"targets": [
            {"semantic_key": "button|change view", "source_state_ids": []},
            {"semantic_key": "button|menu", "source_state_ids": []},
        ]}]}
        narrow = {"pages": [{"targets": [
            {"semantic_key": "button|menu", "source_state_ids": []},
            {"semantic_key": "button|unrelated", "source_state_ids": []},
        ]}]}
        value = node_module(
            "scan_build_components.mjs",
            "m.reconcileResponsiveHiddenControls(" +
            f"{json.dumps(candidates)}, {json.dumps(narrow)}, {json.dumps(wide)}, " +
            '"rest", "narrow")',
        )
        self.assertEqual(["button|menu"], [row["semantic_key"] for row in value])
        # The wide source omits no menu control at narrow; an unrelated equal
        # target count therefore cannot excuse the missing menu.
        self.assertEqual("#menu", value[0]["target"])

    def test_style_extractor_requires_two_stable_exact_loads(self) -> None:
        value = node_module("extract_reference_styles.mjs", "m.REQUIRED_SERVED_RELOADS")
        self.assertEqual(2, value)

    def test_short_or_low_fps_reference_recording_is_refused(self) -> None:
        short = node_module("record_reference.mjs", "m.recordingSettingsError({ seconds: 30, fps: 15 })")
        sparse = node_module("record_reference.mjs", "m.recordingSettingsError({ seconds: 90, fps: 6 })")
        valid = node_module("record_reference.mjs", "m.recordingSettingsError({ seconds: 90, fps: 15 })")
        self.assertIn("at least 90", short)
        self.assertIn("at least 15", sparse)
        self.assertIsNone(valid)

    def test_painted_box_is_not_equivalent_to_media(self) -> None:
        value = node_module("structure_probe.mjs", "m.gridAgreement([[2]], [[3]])")
        self.assertEqual(0, value)

    def test_one_structural_failure_cannot_be_outvoted(self) -> None:
        grid = [[0 for _ in range(24)] for _ in range(16)]
        common = {
            "grid": grid, "edges": {"top": [], "right": [], "bottom": [], "left": []}, "corners": [0, 0, 0, 0],
            "type": {"scale": 4, "display": {"leading": 1, "x_ratio": .6, "advance": 7, "transform": "none"},
                     "body": {"x_ratio": .6}},
        }
        build = {**common, "dominant": {"kind": "box", "tag": "div", "area_share": .8}}
        reference = {**common, "dominant": {"kind": "media", "tag": "img", "area_share": .8}}
        expression = f"m.diffStructure({json.dumps(build)}, {json.dumps(reference)})"
        value = node_module("structure_probe.mjs", expression)
        self.assertFalse(value["pass"])
        self.assertEqual(3, value["passed"])

    def test_every_mapped_mechanism_including_ambient_and_transition_is_required(self) -> None:
        source = {"mechanisms": [{"type": "pinned", "held_px": 900}, {"type": "at-rest", "w": 800, "h": 600},
                                  {"type": "page-transition"}],
                  "score": {"type_instances": {"pinned": 1, "at-rest": 1, "page-transition": 1}}}
        build = {"mechanisms": [{"type": "pinned", "held_px": 900}, {"type": "page-transition"}],
                 "score": {"type_instances": {"pinned": 1, "page-transition": 1}}}
        value = node_module("compare_mechanisms.mjs", f"m.diffSheets({json.dumps(build)}, [{json.dumps(source)}])")
        self.assertFalse(value["pass"])
        self.assertIn("at-rest", value["missing"])

    def test_state_transition_is_weighted_and_cannot_be_ignored(self) -> None:
        weight = node_module(
            "observe_reference.mjs",
            "m.mechanismWeight({type:'state-transition',changed_properties:3,duration_ms:120})",
        )
        self.assertEqual(1320, weight)
        source = {"mechanisms": [{"type": "state-transition", "changed_properties": 3, "duration_ms": 120}],
                  "score": {"type_instances": {"state-transition": 1}}}
        build = {"mechanisms": [], "score": {"type_instances": {}}}
        result = node_module("compare_mechanisms.mjs", f"m.diffSheets({json.dumps(build)}, [{json.dumps(source)}])")
        self.assertFalse(result["pass"])
        self.assertIn("state-transition", result["missing"])

    def test_reference_moving_media_cannot_be_replaced_by_a_static_image(self) -> None:
        source = {"mechanisms": [{"type": "at-rest", "tag": "video", "w": 1280, "h": 720,
                                  "autoplay": True, "loop": True}],
                  "score": {"type_instances": {"at-rest": 1}}}
        static_build = {"mechanisms": [], "score": {"type_instances": {}}}
        result = node_module(
            "compare_mechanisms.mjs",
            f"m.diffSheets({json.dumps(static_build)}, [{json.dumps(source)}])",
        )
        self.assertFalse(result["pass"])
        self.assertIn("at-rest", result["missing"])

    def test_union_of_multiple_sources_is_refused(self) -> None:
        empty = {"mechanisms": [], "score": {"type_instances": {}}}
        value = node_module("compare_mechanisms.mjs", f"m.diffSheets({json.dumps(empty)}, [{json.dumps(empty)}, {json.dumps(empty)}])")
        self.assertFalse(value["pass"])
        self.assertIn("Exactly one mapped", value["verdict"])

    def test_mechanism_instance_count_and_dominant_weight_are_exact(self) -> None:
        source = {"mechanisms": [{"type": "pinned", "held_px": 1000},
                                  {"type": "at-rest", "w": 10, "h": 10}],
                  "score": {"type_instances": {"pinned": 1, "at-rest": 1}}}
        wrong_count = {"mechanisms": source["mechanisms"],
                       "score": {"type_instances": {"pinned": 2, "at-rest": 1}}}
        count = node_module("compare_mechanisms.mjs", f"m.diffSheets({json.dumps(wrong_count)}, [{json.dumps(source)}])")
        self.assertFalse(count["pass"])
        self.assertEqual("pinned", count["instance_count_mismatches"][0]["type"])
        wrong_dominant = {"mechanisms": [{"type": "pinned", "held_px": 1000},
                                          {"type": "at-rest", "w": 2000, "h": 2000}],
                          "score": {"type_instances": {"pinned": 1, "at-rest": 1}}}
        dominant = node_module("compare_mechanisms.mjs", f"m.diffSheets({json.dumps(wrong_dominant)}, [{json.dumps(source)}])")
        self.assertFalse(dominant["pass"])
        self.assertFalse(dominant["loudest_type_match"])

    def test_absent_behavior_and_unbound_click_state_fail(self) -> None:
        state = {"trigger": {"type": "click", "target": "#buy", "value": None}}
        source_state = {"trigger": {"type": "click", "target": "#source-buy", "value": None}}
        source = {"type": "click", "target": "#source-buy", "target_component_keys": ["class:buy"],
                  "before_sha256": "1" * 64, "after_sha256": "2" * 64, "settled_sha256": "2" * 64,
                  "changed_properties": [{"component_key": "class:buy", "property": "opacity", "before": "0", "after": "1"}],
                  "duration_ms": 100, "settled": True,
                  "mechanism": {"type": "state-transition"}, "mechanism_count": 1}
        absent = {**source, "target": "#wrong", "after_sha256": "1" * 64, "settled_sha256": "1" * 64,
                  "changed_properties": [], "mechanism": None, "mechanism_count": 0}
        result = node_module(
            "compare_mechanisms.mjs",
            f"m.diffTriggerEvidence({json.dumps(absent)}, {json.dumps(source)}, {json.dumps(state)}, {json.dumps(source_state)})",
        )
        self.assertFalse(result["pass"])
        self.assertTrue(any("target" in item for item in result["failures"]))
        self.assertTrue(any("before/after" in item or "visual change" in item for item in result["failures"]))

    def test_generic_hover_cannot_stand_in_for_pointer_follow(self) -> None:
        source = {"mechanisms": [{"type": "pointer-follow", "moved_px": 40}],
                  "score": {"type_instances": {"pointer-follow": 1}}}
        build = {"mechanisms": [{"type": "hover-transition", "responded": 1, "ms": 120}],
                 "score": {"type_instances": {"hover-transition": 1}}}
        result = node_module("compare_mechanisms.mjs", f"m.diffSheets({json.dumps(build)}, [{json.dumps(source)}])")
        self.assertFalse(result["pass"])
        self.assertIn("pointer-follow", result["missing"])

    def test_interaction_transfer_compares_behavior_not_reference_domain_text(self) -> None:
        frame = {"sha256": "a" * 64, "bytes": 10}
        def census(url: str) -> dict:
            evidence = {
                "input_kind": "navigation", "input_value": url, "status": "exercised",
                "source_state_id": None, "before_sha256": "1" * 64,
                "after_sha256": "2" * 64, "settled_sha256": "2" * 64,
                "changed_properties": [{"property": "opacity", "before": "0", "after": "1"}],
                "disposition": "sourceable-observed-behavior",
                "evidence": {"before": frame, "after": frame, "settled": frame},
            }
            return {"complete": True, "truncated": False, "missing": [],
                    "pages": [{"targets": [{"target_id": "target", "repeat_class": "a|a|link",
                                              "repeat_index": 1, "class_signature": ["link"],
                                              "tag": "a", "role": "a", "inputs": [evidence]}]}],
                    "totals": {"targets_discovered": 1}, "pointer_follow": []}
        source = census("https://reference.test/work")
        build = census("http://127.0.0.1:9000/projects")
        result = node_module(
            "compare_mechanisms.mjs",
            f"m.diffInteractionCensus({json.dumps(build)}, {json.dumps(source)}, [])",
        )
        self.assertTrue(result["pass"], result)
        build["pages"][0]["targets"][0]["inputs"][0]["changed_properties"][0]["after"] = "0.5"
        mismatch = node_module(
            "compare_mechanisms.mjs",
            f"m.diffInteractionCensus({json.dumps(build)}, {json.dumps(source)}, [])",
        )
        self.assertFalse(mismatch["pass"])

    def test_scroll_coverage_counts_only_ticks_where_reveal_changes(self) -> None:
        ticks = []
        for index, opacity in enumerate([0, 0, .5, 1, 1]):
            ticks.append({
                "y": index * 100, "docH": 2000, "inner": None,
                "els": {"one": {"top": 500 - index * 100, "left": 0, "h": 100, "w": 200,
                                  "op": opacity, "tf": "", "pos": "static", "src": "", "txt": "Hello",
                                  "tag": "section", "cls": "hero", "parent": None}},
            })
        expression = (
            "(() => { const result = m.deriveMechanisms(" + json.dumps(ticks) + "); "
            "return { active: [...result.activeTicks], scrollTicks: result.scrollTicks }; })()"
        )
        value = node_module("observe_reference.mjs", expression)
        self.assertEqual([2, 3], value["active"])
        self.assertEqual(4, value["scrollTicks"])

    def test_typeface_matcher_uses_full_texture_not_two_axes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            observation = write_json(root / "strong-1-observation.json", {
                "tool": "observe_reference.mjs", "schema_version": 5,
                "producer_script_sha256": script_hash("observe_reference.mjs"), "id": "strong-1",
                "runtime_identity": {"structure_probe.mjs": script_hash("structure_probe.mjs"),
                                     "browser_evidence.mjs": script_hash("browser_evidence.mjs"),
                                     "playwright_resolver.mjs": script_hash("playwright_resolver.mjs")},
                "first_screen": {"type": {"display": {
                    "family": "Target", "weight": "400", "x_ratio": .6, "advance": 7,
                    "i_ratio": .3, "lower_advance": 13, "upper_advance": 17,
                    "digit_advance": 6, "punct_advance": 5,
                }}},
            })
            measured = write_json(root / "measured.json", [
                {"family": "Two Axis Decoy", "weight": "400", "x_ratio": .6, "advance": 7,
                 "i_ratio": .65, "lower_advance": 20, "upper_advance": 25, "digit_advance": 10,
                 "punct_advance": 9, "font_fingerprint": {"raster": "1" * 16, "probe_width": 100, "ink": 100}},
                {"family": "Full Texture Match", "weight": "400", "x_ratio": .61, "advance": 7.1,
                 "i_ratio": .31, "lower_advance": 13.1, "upper_advance": 17.1, "digit_advance": 6.1,
                 "punct_advance": 5.1, "font_fingerprint": {"raster": "2" * 16, "probe_width": 100, "ink": 100}},
            ])
            out = root / "match.json"
            done = subprocess.run([
                NODE, str(SCRIPTS / "match_typeface.mjs"), "--observation", str(observation),
                "--measured", str(measured), "--out", str(out),
            ], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(0, done.returncode, done.stdout + done.stderr)
            record = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual("Full Texture Match", record["results"][0]["chosen"]["family"])
        self.assertGreaterEqual(len(record["results"][0]["axes"]), 7)


@unittest.skipIf(NODE is None, "node is required")
class SignatureTransferBehaviorTests(unittest.TestCase):
    BUILD_ID = "build-identity-123"
    RUN_ID = "test-run-identity"

    def run_signature(self, signature: str, source_mechanism: dict, *, fake_tested_report: bool = False,
                      fake_truthy_status: bool = False) -> tuple[int, dict]:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = root / ".design-dna"
            refs = state / "references"
            trigger_evidence = {
                "type": "none", "target": "document", "target_component_keys": ["hero"],
                "before_sha256": "1" * 64, "after_sha256": "1" * 64,
                "settled_sha256": "1" * 64, "changed_properties": [], "duration_ms": 0,
                "settled": True, "mechanism": None, "mechanism_count": 0,
            }
            source_cell = {
                "id": "rest", "kind": "rest",
                "trigger": {"type": "none", "target": "document", "value": None},
                "expectation": "initial settled route", "trigger_evidence": trigger_evidence,
                "structure": {"dominant": {}, "grid": [], "edges": {}, "corners": [], "type": {}},
                "mechanisms": [source_mechanism],
                "score": {"type_instances": {source_mechanism["type"]: 1}, "scroll_coverage": .05},
            }
            observation = write_json(refs / "strong-1-observation.json", {
                "tool": "observe_reference.mjs", "schema_version": 5,
                "producer_script_sha256": script_hash("observe_reference.mjs"), "id": "strong-1",
                "url": "https://reference.test/",
                "runtime_identity": {"structure_probe.mjs": script_hash("structure_probe.mjs"),
                                     "browser_evidence.mjs": script_hash("browser_evidence.mjs"),
                                     "playwright_resolver.mjs": script_hash("playwright_resolver.mjs")},
                "states_by_viewport": {"wide": {"rest": source_cell}, "narrow": {"rest": source_cell}},
                "mechanisms_by_viewport": {
                    "wide": {"mechanisms": [source_mechanism], "score": {"scroll_coverage": .05}},
                    "narrow": {"mechanisms": [source_mechanism], "score": {"scroll_coverage": .05}},
                },
            })
            observation_sha = hashlib.sha256(observation.read_bytes()).hexdigest()
            manifest = write_json(state / "route-manifest.json", {
                "schema_version": 2, "manifest_id": "manifest-identity-123",
                "viewports": [{"name": "wide", "width": 1440, "height": 900},
                              {"name": "narrow", "width": 390, "height": 844}],
                "routes": [{"key": "home", "url": "http://127.0.0.1:9000/",
                            "mapped_reference_rank": 1, "mapped_reference_id": "strong-1",
                            "mapped_reference_observation": ".design-dna/references/strong-1-observation.json",
                            "mapped_reference_sha256": observation_sha,
                            "states": [{"id": "rest", "kind": "rest",
                                        "trigger": {"type": "none", "target": "document", "value": None},
                                        "expectation": "initial settled route",
                                        "mapped_reference_state_id": "rest"}]}],
            })
            manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
            dossier = state / "reference-dossier.md"
            dossier.write_text(
                "## Strong references\n\n| Rank | Observed evidence | Signature |\n| --- | --- | --- |\n" +
                f"| 1 | .design-dna/references/strong-1-observation.json sha256:{observation_sha} | {signature} |\n\n" +
                "## Selected synthesis\n\n- Selected positive ranks: 1\n\n" +
                "## Signature transfer\n\n| Rank | Signature | The build part that carries it |\n| --- | --- | --- |\n" +
                f"| 1 | {signature} | hero |\n\n" +
                "## Component sources\n\n| Component | Source rank |\n| --- | --- |\n| hero | 1 |\n",
                encoding="utf-8",
            )
            probe = {"route_key": "home", "viewport": "wide", "requested_url": "http://127.0.0.1:9000/",
                     "final_url": "http://127.0.0.1:9000/", "status": 200, "document_sha256": "2" * 64,
                     "resources": [], "sha256": "3" * 64}
            served = {"algorithm": "sha256-response-bodies-v1",
                      "probes": [probe, {**probe, "viewport": "narrow"}],
                      "reload_counts": {"home/wide": 2, "home/narrow": 2},
                      "inconsistent_reloads": [], "sha256": "4" * 64, "complete": True}
            def identity(tool: str) -> dict:
                return {"tool": tool, "schema_version": 3, "producer_script_sha256": script_hash(tool),
                        "build_id": self.BUILD_ID, "run_id": self.RUN_ID,
                        "manifest_id": "manifest-identity-123", "manifest_sha256": manifest_sha,
                        "served_content_identity": served}
            def mechanism_cell(viewport: str, width: int) -> dict:
                return {
                    "route_key": "home", "viewport": viewport, "width": width, "state_id": "rest",
                    "state_trigger": {"type": "none", "target": "document", "value": None},
                    "mapped_reference_state_id": "rest", "state_contract_match": True,
                    "mapped_reference": {"rank": 1, "id": "strong-1",
                                         "observation": ".design-dna/references/strong-1-observation.json",
                                         "sha256": observation_sha},
                    "source_mapping": {"rank": 1, "id": "strong-1",
                                       "observation": ".design-dna/references/strong-1-observation.json",
                                       "sha256": observation_sha, "state_id": "rest"},
                    "pass": True, "complete": True, "build_loudest": source_mechanism["type"],
                    "loudest_type_match": True, "loudest_magnitude_relative_delta": 0,
                    "loudest_magnitude_tolerance": .25,
                    "build_mechanisms": [{**source_mechanism, "components": ["hero"]}],
                    "state_application": {"trigger_evidence": trigger_evidence},
                    "trigger_diff": {"pass": True},
                    "evidence_frames": {phase: {"sha256": digit * 64, "bytes": 10}
                                        for phase, digit in (("before", "5"), ("after", "6"), ("settled", "7"))},
                }
            mechanism_cells = [mechanism_cell("wide", 1440), mechanism_cell("narrow", 390)]
            mechanism = write_json(root / "mechanism.json", {
                **identity("compare_mechanisms.mjs"), "pass": True,
                "runtime_identity": {"observe_reference.mjs": script_hash("observe_reference.mjs")},
                "checks": mechanism_cells,
                "interaction_transfer": {"complete": True, "missing": [], "cells": mechanism_cells,
                                         "responsive_transformations": [{"route_key": "home", "state_id": "rest", "complete": True}]},
            })
            if fake_truthy_status:
                fake = json.loads(mechanism.read_text(encoding="utf-8"))
                fake["pass"] = "yes"
                write_json(mechanism, fake)
            structure = write_json(root / "structure.json", {
                **identity("compare_structure.mjs"), "pass": True,
                "runtime_identity": {"structure_probe.mjs": script_hash("structure_probe.mjs")},
                "routes": [{"route_key": "home", "viewport": name, "state_id": "rest", "width": width,
                            "mapped_reference": {"rank": 1, "id": "strong-1",
                                                 "observation": ".design-dna/references/strong-1-observation.json",
                                                 "sha256": observation_sha}, "pass": True}
                           for name, width in (("wide", 1440), ("narrow", 390))],
            })
            styles = write_json(root / "styles.json", {
                **identity("check_style_provenance.mjs"), "ok": True,
                "runtime_identity": {"extract_reference_styles.mjs": script_hash("extract_reference_styles.mjs")},
            })
            census_cells = [{"route_key": "home", "viewport": name, "state_id": "rest",
                             "mapped_reference_state_id": "rest",
                             "source_mapping": {"rank": 1, "id": "strong-1",
                                                "observation": ".design-dna/references/strong-1-observation.json",
                                                "sha256": observation_sha, "state_id": "rest"},
                             "trigger": {"type": "none", "target": "document", "value": None},
                             "complete": True}
                            for name in ("wide", "narrow")]
            census = write_json(root / "census.json", {
                **identity("scan_build_components.mjs"), "pass": True,
                "names": ["hero"], "census": [{"name": "hero", "routes": ["home"]}],
                "interaction_inventory": {"complete": True, "missing": [], "cells": census_cells},
            })
            if fake_tested_report:
                fake = json.loads(census.read_text(encoding="utf-8"))
                fake["interaction_inventory"]["cells"] = fake["interaction_inventory"]["cells"][:1]
                write_json(census, fake)
            out = root / "signature.json"
            done = subprocess.run([
                NODE, str(SCRIPTS / "check_signature_transfer.mjs"), "--dossier", str(dossier),
                "--manifest", str(manifest),
                "--observation", str(observation), "--mechanism-diff", str(mechanism),
                "--structure-diff", str(structure), "--style-provenance", str(styles), "--census", str(census),
                "--build-id", self.BUILD_ID, "--run-id", self.RUN_ID, "--out", str(out),
            ], capture_output=True, text=True, encoding="utf-8")
            if out.exists():
                return done.returncode, json.loads(out.read_text(encoding="utf-8"))
            return done.returncode, json.loads(done.stdout)

    def test_motion_signature_must_name_the_dominant_mechanism(self) -> None:
        code, record = self.run_signature("motion: buttons glow on hover across the route", {"type": "at-rest", "w": 900, "h": 700})
        self.assertEqual(1, code)
        self.assertFalse(record["pass"])
        self.assertIn("dominant measured mechanism is at-rest", record["verdict"])

    def test_static_signature_allows_only_incidental_low_weight_motion(self) -> None:
        code, record = self.run_signature("static: editorial type occupies a strict left rail", {"type": "hover-transition", "responded": 1, "ms": 120})
        self.assertEqual(0, code, record["verdict"])
        self.assertTrue(record["pass"])

    def test_fake_passing_report_with_missing_interaction_cell_is_refused(self) -> None:
        code, record = self.run_signature(
            "static: editorial type occupies a strict left rail",
            {"type": "hover-transition", "responded": 1, "ms": 120},
            fake_tested_report=True,
        )
        self.assertEqual(2, code)
        self.assertEqual("interaction-inventory-coverage", record["error"]["code"])

    def test_truthy_string_cannot_impersonate_a_passing_report(self) -> None:
        code, record = self.run_signature(
            "static: editorial type occupies a strict left rail",
            {"type": "hover-transition", "responded": 1, "ms": 120},
            fake_truthy_status=True,
        )
        self.assertEqual(2, code)
        self.assertEqual("evidence-invalid", record["error"]["code"])


if __name__ == "__main__":
    unittest.main()
