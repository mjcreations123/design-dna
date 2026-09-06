#!/usr/bin/env python3
"""Focused regressions for the pre-code source-fidelity boundary."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
INIT = SKILL / "scripts" / "init_project_state.py"


def load_initializer():
    spec = importlib.util.spec_from_file_location("construction_initializer", INIT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


class ConstructionJournalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.init = load_initializer()

    def base(self, root: Path) -> tuple[Path, Path, Path, dict[str, object]]:
        state = root / ".design-dna"
        manifest = write_json(state / "route-manifest.json", {
            "schema_version": 2,
            "manifest_id": "construction-manifest-001",
            "viewports": [
                {"name": "wide", "width": 1440, "height": 900},
                {"name": "narrow", "width": 390, "height": 844},
            ],
            "routes": [],
        })
        dossier = state / "reference-dossier.md"
        dossier.write_text("# Reference dossier\n\n- Pre-code journal: pending\n", encoding="utf-8")
        visible_payload: dict[str, object] = {
            "schema_version": 2,
            "record_type": "design-dna-visible-decision-source-manifest",
            "created_at": "2026-09-04T12:00:00Z",
            "proof_build_id": "construction-proof-001",
            "route_manifest": {
                "manifest_id": "construction-manifest-001",
                "path": ".design-dna/route-manifest.json",
                "sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            },
            "source_observations": [{
                "id": "strong-1",
                "path": ".design-dna/references/strong-1-observation.json",
                "sha256": "0" * 64,
            }],
            "construction_authorization": {
                "journal_id": None, "entry_path": None, "entry_sha256": None,
            },
            "proof_isolation": {
                "primary_route_key": "home", "source_files": ["proof.tsx"],
                "region_component_id": "home-hero",
            },
            "planned_decision_ids": [], "decisions": [],
            "source_contribution_scope": [],
            "completeness": {
                "required_categories": [], "covered_categories": [],
                "placeholders_allowed": False, "generic_scaffold_allowed": False,
                "fallback_design_allowed": False, "wrapper_inheritance_allowed": False,
                "unsourced_decisions": [],
            },
        }
        visible = write_json(state / "visible-decision-sources.json", visible_payload)
        dossier.write_text(dossier.read_text(encoding="utf-8") +
                           "- Visible decision source manifest: .design-dna/visible-decision-sources.json plus sha256:" +
                           hashlib.sha256(visible.read_bytes()).hexdigest() + "\n", encoding="utf-8")
        return manifest, dossier, visible, visible_payload

    def test_fresh_precode_entry_is_create_only_and_core_bound(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest, dossier, visible, payload = self.base(root)
            action = self.init.begin_construction_journal(
                root, manifest_path=manifest, dossier_path=dossier,
                visible_path=visible, visible_payload=payload,
            )
            self.assertEqual("began-construction", action["action"])
            current = json.loads(visible.read_text(encoding="utf-8"))
            failures = self.init.construction_authorization_failures(
                root, current, route_manifest_path=manifest, dossier_path=dossier,
            )
            self.assertEqual([], failures, failures)
            chain_failures, records = self.init.construction_journal_chain(root)
            self.assertEqual([], chain_failures)
            self.assertEqual(1, len(records))
            self.assertEqual("pre-code-baseline", records[0][1]["entry_kind"])
            self.assertEqual(
                self.init.construction_binding_core_sha256(current),
                records[0][1]["visible_decision_core_sha256"],
            )

    def test_existing_visible_source_is_honestly_legacy_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "site.html").write_text("<main><h1>Already built</h1></main>", encoding="utf-8")
            manifest, dossier, visible, payload = self.base(root)
            self.init.begin_construction_journal(
                root, manifest_path=manifest, dossier_path=dossier,
                visible_path=visible, visible_payload=payload,
            )
            current = json.loads(visible.read_text(encoding="utf-8"))
            failures = self.init.construction_authorization_failures(
                root, current, route_manifest_path=manifest, dossier_path=dossier,
            )
            self.assertTrue(any("legacy-audit" in item for item in failures), failures)

    def test_div_paragraph_and_span_source_are_not_missed_as_nonvisual_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "App.jsx").write_text(
                "export default () => <div><p>Already visible generic UI</p><span>CTA</span></div>;",
                encoding="utf-8",
            )
            manifest, dossier, visible, payload = self.base(root)
            self.init.begin_construction_journal(
                root, manifest_path=manifest, dossier_path=dossier,
                visible_path=visible, visible_payload=payload,
            )
            current = json.loads(visible.read_text(encoding="utf-8"))
            failures = self.init.construction_authorization_failures(
                root, current, route_manifest_path=manifest, dossier_path=dossier,
            )
        self.assertTrue(any("legacy-audit" in item for item in failures), failures)

    def test_react_element_factory_is_visible_source_not_clean_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "Future.js").write_text(
                "export default () => React.createElement('section', null, React.createElement('a', {href:'/secret'}, 'Future'));",
                encoding="utf-8",
            )
            _tree, _files, visible, _assets = self.init.construction_source_snapshot(root)
        self.assertEqual(["Future.js"], [row["path"] for row in visible])

    def test_compiled_dist_surface_cannot_hide_from_precode_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "dist").mkdir()
            (root / "dist" / "index.html").write_text(
                "<main><h1>Existing shipped page</h1></main>", encoding="utf-8"
            )
            manifest, dossier, visible, payload = self.base(root)
            self.init.begin_construction_journal(
                root, manifest_path=manifest, dossier_path=dossier,
                visible_path=visible, visible_payload=payload,
            )
            current = json.loads(visible.read_text(encoding="utf-8"))
            failures = self.init.construction_authorization_failures(
                root, current, route_manifest_path=manifest, dossier_path=dossier,
            )
        self.assertTrue(any("legacy-audit" in item for item in failures), failures)

    def test_canonical_inventory_hash_is_order_independent_and_self_validating(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            # Write in reverse lexical order; the entry must still be sorted
            # and its own inventory hash must validate exactly.
            (root / "zeta.txt").write_text("z", encoding="utf-8")
            (root / "alpha.txt").write_text("a", encoding="utf-8")
            manifest, dossier, visible, payload = self.base(root)
            self.init.begin_construction_journal(
                root, manifest_path=manifest, dossier_path=dossier,
                visible_path=visible, visible_payload=payload,
            )
            failures, records = self.init.construction_journal_chain(root)
        self.assertEqual([], failures, failures)
        self.assertEqual(
            ["alpha.txt", "zeta.txt"],
            [row["path"] for row in records[0][1]["implementation_files"]],
        )

    def test_journal_tampering_breaks_the_chain(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest, dossier, visible, payload = self.base(root)
            self.init.begin_construction_journal(
                root, manifest_path=manifest, dossier_path=dossier,
                visible_path=visible, visible_payload=payload,
            )
            entry = next((root / ".design-dna" / "evidence" / "construction-journal").glob("*.json"))
            tampered = json.loads(entry.read_text(encoding="utf-8"))
            tampered["sequence"] = 99
            entry.write_text(json.dumps(tampered), encoding="utf-8")
            failures, _records = self.init.construction_journal_chain(root)
            self.assertTrue(any("identity" in item or "sequence" in item for item in failures), failures)

    def test_proof_lifecycle_appends_without_rewriting_the_precode_authority(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest, dossier, visible, payload = self.base(root)
            self.init.begin_construction_journal(
                root, manifest_path=manifest, dossier_path=dossier,
                visible_path=visible, visible_payload=payload,
            )
            current = json.loads(visible.read_text(encoding="utf-8"))
            action = self.init.append_construction_journal_entry(
                root, entry_kind="first-screen-authorized", manifest_path=manifest,
                dossier_path=dossier, visible_payload=current,
            )
            self.assertEqual("000002-" + action["entry_id"] + ".json", Path(action["path"]).name)
            failures = self.init.construction_authorization_failures(
                root, current, route_manifest_path=manifest, dossier_path=dossier,
            )
            self.assertEqual([], failures, failures)

    def test_changed_source_plan_cannot_reauthorize_visible_code(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest, dossier, visible, payload = self.base(root)
            self.init.begin_construction_journal(
                root, manifest_path=manifest, dossier_path=dossier,
                visible_path=visible, visible_payload=payload,
            )
            (root / "site.html").write_text("<div><p>Already built</p></div>", encoding="utf-8")
            changed = json.loads(visible.read_text(encoding="utf-8"))
            changed["created_at"] = "2026-09-04T12:00:01Z"
            # Simulate an attempted new authorization rather than merely
            # replaying the still-bound original journal pointer.
            changed["construction_authorization"] = {
                "journal_id": None, "entry_path": None, "entry_sha256": None,
            }
            visible.write_text(json.dumps(changed, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(Exception, "post-hoc dossier laundering"):
                self.init.begin_construction_journal(
                    root, manifest_path=manifest, dossier_path=dossier,
                    visible_path=visible, visible_payload=changed,
                )

    def test_first_screen_static_delta_rejects_hidden_lazy_second_route(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest, dossier, visible, payload = self.base(root)
            manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
            manifest_payload["routes"] = [
                {"key": "home", "url": "http://127.0.0.1:4900/"},
                {"key": "about", "url": "http://127.0.0.1:4900/about"},
            ]
            manifest.write_text(json.dumps(manifest_payload), encoding="utf-8")
            self.init.begin_construction_journal(
                root, manifest_path=manifest, dossier_path=dossier,
                visible_path=visible, visible_payload=payload,
            )
            (root / "proof.tsx").write_text(
                "export default () => <section>home</section>; const later = import('/about');",
                encoding="utf-8",
            )
            current = json.loads(visible.read_text(encoding="utf-8"))
            failures = self.init.first_screen_construction_isolation_failures(
                root, current, route_manifest=manifest_payload, route_key="home",
            )
        self.assertTrue(any("another manifested route" in item or "deferred/hidden/lazy" in item for item in failures), failures)

    def test_first_screen_static_delta_rejects_inactive_future_jsx_inside_allowed_file(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest, dossier, visible, payload = self.base(root)
            manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
            manifest_payload["routes"] = [{"key": "home", "url": "http://127.0.0.1:4900/"}]
            manifest.write_text(json.dumps(manifest_payload), encoding="utf-8")
            self.init.begin_construction_journal(
                root, manifest_path=manifest, dossier_path=dossier,
                visible_path=visible, visible_payload=payload,
            )
            (root / "proof.tsx").write_text(
                "export default () => <main><div>proof</div>{false && <div><h1>Prewritten future</h1><button>Future action</button></div>}</main>;",
                encoding="utf-8",
            )
            current = json.loads(visible.read_text(encoding="utf-8"))
            failures = self.init.first_screen_construction_isolation_failures(
                root, current, route_manifest=manifest_payload, route_key="home",
            )
        self.assertTrue(any("conditional-jsx" in item for item in failures), failures)

    def test_first_screen_ast_rejects_unmounted_component_surface(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest, dossier, visible, payload = self.base(root)
            manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
            manifest_payload["routes"] = [{"key": "home", "url": "http://127.0.0.1:4900/"}]
            manifest.write_text(json.dumps(manifest_payload), encoding="utf-8")
            self.init.begin_construction_journal(root, manifest_path=manifest, dossier_path=dossier, visible_path=visible, visible_payload=payload)
            (root / "proof.tsx").write_text(
                "const Future = () => <div><h1>Future</h1></div>; export default () => <main>proof</main>;",
                encoding="utf-8",
            )
            current = json.loads(visible.read_text(encoding="utf-8"))
            failures = self.init.first_screen_construction_isolation_failures(root, current, route_manifest=manifest_payload, route_key="home")
        self.assertTrue(any("proof-jsx-root-count" in item or "unmounted-or-extra-jsx" in item for item in failures), failures)

    def test_first_screen_ast_rejects_static_import_closure(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest, dossier, visible, payload = self.base(root)
            manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
            manifest_payload["routes"] = [{"key": "home", "url": "http://127.0.0.1:4900/"}]
            manifest.write_text(json.dumps(manifest_payload), encoding="utf-8")
            self.init.begin_construction_journal(root, manifest_path=manifest, dossier_path=dossier, visible_path=visible, visible_payload=payload)
            (root / "proof.tsx").write_text(
                "import Future from './Future'; export default () => <main>proof</main>;",
                encoding="utf-8",
            )
            current = json.loads(visible.read_text(encoding="utf-8"))
            failures = self.init.first_screen_construction_isolation_failures(root, current, route_manifest=manifest_payload, route_key="home")
        self.assertTrue(any("proof-static-import" in item for item in failures), failures)

    def test_first_screen_ast_rejects_imperative_future_markup_and_decoder(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest, dossier, visible, payload = self.base(root)
            manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
            manifest_payload["routes"] = [{"key": "home", "url": "http://127.0.0.1:4900/"}]
            manifest.write_text(json.dumps(manifest_payload), encoding="utf-8")
            self.init.begin_construction_journal(root, manifest_path=manifest, dossier_path=dossier, visible_path=visible, visible_payload=payload)
            (root / "proof.tsx").write_text(
                "const future = () => document.body.insertAdjacentHTML('beforeend', atob('PGRpdj48aDE+RnV0dXJlPC9oMT48L2Rpdj4=')); export default () => <main>proof</main>;",
                encoding="utf-8",
            )
            current = json.loads(visible.read_text(encoding="utf-8"))
            failures = self.init.first_screen_construction_isolation_failures(root, current, route_manifest=manifest_payload, route_key="home")
        self.assertTrue(any("dom-html-mutation" in item for item in failures), failures)
        self.assertTrue(any("dynamic-code-or-decoder" in item for item in failures), failures)

    def test_first_screen_ast_rejects_computed_global_dom_sink(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest, dossier, visible, payload = self.base(root)
            manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
            manifest_payload["routes"] = [{"key": "home", "url": "http://127.0.0.1:4900/"}]
            manifest.write_text(json.dumps(manifest_payload), encoding="utf-8")
            self.init.begin_construction_journal(root, manifest_path=manifest, dossier_path=dossier, visible_path=visible, visible_payload=payload)
            (root / "proof.tsx").write_text(
                "const method = 'insertAdjacentHTML'; const future = () => document.body[method]('beforeend', '<div>future</div>'); export default () => <main>proof</main>;",
                encoding="utf-8",
            )
            current = json.loads(visible.read_text(encoding="utf-8"))
            failures = self.init.first_screen_construction_isolation_failures(root, current, route_manifest=manifest_payload, route_key="home")
        self.assertTrue(any("dynamic-global-dom-access" in item for item in failures), failures)

    def test_first_screen_fails_closed_for_unparsed_vue_source(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest, dossier, visible, payload = self.base(root)
            payload["proof_isolation"] = {
                "primary_route_key": "home", "source_files": ["proof.vue"], "region_component_id": "home-hero",
            }
            visible.write_text(json.dumps(payload), encoding="utf-8")
            manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
            manifest_payload["routes"] = [{"key": "home", "url": "http://127.0.0.1:4900/"}]
            manifest.write_text(json.dumps(manifest_payload), encoding="utf-8")
            self.init.begin_construction_journal(root, manifest_path=manifest, dossier_path=dossier, visible_path=visible, visible_payload=payload)
            (root / "proof.vue").write_text(
                "<template><main>Proof</main><div v-if=\"false\"><h1>Future</h1><button>Later</button></div></template>",
                encoding="utf-8",
            )
            current = json.loads(visible.read_text(encoding="utf-8"))
            failures = self.init.first_screen_construction_isolation_failures(root, current, route_manifest=manifest_payload, route_key="home")
        self.assertTrue(any("no pinned structural parser" in item for item in failures), failures)


class ConstructionBindingCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.init = load_initializer()

    def test_legacy_manifest_cannot_authorize_new_construction(self) -> None:
        legacy = {
            "schema_version": 1,
            "record_type": "design-dna-visible-decision-source-manifest",
        }
        # A malformed legacy record naturally has other failures; the
        # construction-specific blocker must still be explicit and actionable.
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            failures = self.init.visible_decision_source_manifest_failures(
                legacy,
                project=root,
                route_manifest={"manifest_id": "legacy-manifest-001", "routes": [], "viewports": []},
                route_manifest_path=root / "missing.json",
                proof_identity="",
                require_construction_v2=True,
            )
        self.assertTrue(any("legacy evidence only" in item for item in failures), failures)


if __name__ == "__main__":
    unittest.main()
