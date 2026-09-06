#!/usr/bin/env python3
"""Strictly non-public, source-faithful proof-slice regressions."""

from __future__ import annotations

import hashlib
import http.server
import importlib.util
import json
import socketserver
import subprocess
import sys
import tempfile
import threading
import unittest
import struct
import zlib
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
GATE = SCRIPTS / "gate.py"
INIT = SCRIPTS / "init_project_state.py"
PYTHON = sys.executable

# Synthetic contract fixture, never evidence of an Apple/public-site capture.
PRODUCT_STORY_URL = "http://127.0.0.1:8123/synthetic-product-story"
SIX_REFERENCE_URLS = [
    PRODUCT_STORY_URL,
    "https://www.apple.com/iphone-16-pro/",
    "https://www.apple.com/apple-watch-ultra-2/",
    "https://www.apple.com/macbook-pro/",
    "https://www.apple.com/ipad-pro/",
    "https://www.apple.com/apple-vision-pro/",
]
LABEL = "Internal unverified proof slice — not for public release"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_sha(value: str) -> str:
    return hashlib.sha256(" ".join(value.split()).encode("utf-8")).hexdigest()


def write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def write_bytes(path: Path, content: bytes) -> tuple[int, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path.stat().st_size, sha(path)


def load_init():
    spec = importlib.util.spec_from_file_location("proof_slice_init", INIT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class LocalServer:
    def __init__(self, root: Path) -> None:
        class QuietHandler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, _format, *_args) -> None:
                return
        handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(root), **kwargs)
        self.server = socketserver.TCPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}/"

    def url_for(self, relative: str) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}/{relative.lstrip('/')}"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


class ProofSliceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.init = load_init()

    def test_template_declares_nonpublic_local_render_and_all_material_transfer_coverage(self) -> None:
        payload = json.loads((SKILL / "templates" / "proof-slice-template.json").read_text(encoding="utf-8"))
        self.assertEqual(1, payload["schema_version"])
        self.assertEqual("internal-unverified", payload["status"])
        self.assertIn("127.0.0.1", payload["implementation"]["proof_url"])
        self.assertEqual({"layout", "type", "color", "spacing", "control", "media"}, set(payload["transfer_coverage"]))
        self.assertEqual("source-absent", payload["transfer_coverage"]["control"]["status"])

    @staticmethod
    def rebind_source(root: Path, payload: dict[str, object]) -> None:
        implementation = payload["implementation"]
        source = root / implementation["source_file"]
        implementation["source_file_sha256"] = sha(source)

    def prepared(self, root: Path, *, source_kind: str = "proof-slice") -> tuple[Path, dict[str, object]]:
        references = root / ".design-dna" / "references"
        brief = root / ".design-dna" / "brief.md"
        brief.parent.mkdir(parents=True, exist_ok=True)
        brief.write_text(
            "Current product-story proof brief: show the exact opening arrangement as an internal specimen only. "
            + "\n".join(SIX_REFERENCE_URLS), encoding="utf-8"
        )
        source_id = "proof-source-product-story"
        frames: dict[str, dict[str, object]] = {}
        signed: list[dict[str, object]] = []
        states: dict[str, dict[str, object]] = {}
        for profile, width, height in (("wide", 1440, 900), ("narrow", 390, 844)):
            def chunk(kind: bytes, content: bytes) -> bytes:
                return struct.pack("!I", len(content)) + kind + content + struct.pack("!I", zlib.crc32(kind + content) & 0xffffffff)
            value = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress((b"\x00" + b"\xee\xee\xee" * width) * height)) + chunk(b"IEND", b"")
            frame = references / f"{source_id}-{profile}-settled.png"
            size, digest = write_bytes(frame, value)
            reference_file = frame.relative_to(root).as_posix()
            frames[profile] = {"file": frame.name, "bytes": size, "sha256": digest}
            signed.append({"kind": "frame", "file": reference_file, "bytes": size, "sha256": digest, "producer": "observe_reference.mjs"})
            states[profile] = {
                "id": "rest", "trigger": {"type": "none", "target": "document", "value": None},
                "evidence_frames": {"settled": {"file": frame.name, "bytes": size, "sha256": digest}},
            }
        counters = {"frames": 2, "events": 1, "states": 1, "routes": 1, "targets": 3}
        journal_rel = f".design-dna/references/{source_id}-study.jsonl"
        progress_rel = f".design-dna/references/{source_id}-study.json"
        journal = root / journal_rel
        previous = None
        rows = []
        for sequence, kind, detail in (
            (1, "started", {}),
            (2, "frame-captured", {}),
            (3, "complete", {"terminal_success": True, "signed_artifacts": signed}),
        ):
            core = {
                "schema_version": 1, "sequence": sequence, "at": f"2026-09-04T00:00:0{sequence}Z",
                "kind": kind, "counters": counters if sequence > 1 else {key: 0 for key in counters},
                "previous_sha256": previous, "detail": detail,
            }
            previous = self.init.canonical_json_sha256(core)
            rows.append({**core, "sha256": previous})
        journal.parent.mkdir(parents=True, exist_ok=True)
        journal.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        progress_core = {
            "schema_version": 1, "kind": "source-study-progress", "status": "complete", "source_status": "complete",
            "eligible_for_source_selection": False, "source_kind": source_kind, "id": source_id,
            "producer": "observe_reference.mjs", "progress_event_file": journal_rel,
            "progress_event_count": 3, "tail_event_sha256": previous, "counters": counters,
            "signed_artifacts": signed,
        }
        progress = root / progress_rel
        write_json(progress, progress_core)
        study = {
            **progress_core,
            "progress": {"path": progress_rel, "bytes": progress.stat().st_size, "sha256": sha(progress)},
            "progress_events": {"path": journal_rel, "bytes": journal.stat().st_size, "sha256": sha(journal)},
        }
        proof_text_hashes = {
            "product-story-opening": text_sha("AirPods Pro" + "A bounded source-faithful opening specimen."),
            "product-story-heading": text_sha("AirPods Pro"),
            "product-story-summary": text_sha("A bounded source-faithful opening specimen."),
        }
        observation = {
            "tool": "observe_reference.mjs", "schema_version": self.init.REFERENCE_OBSERVATION_SCHEMA,
            "producer_script_sha256": sha(SCRIPTS / "observe_reference.mjs"),
            "runtime_identity": {"observe_reference.mjs": sha(SCRIPTS / "observe_reference.mjs")},
            "id": source_id, "url": PRODUCT_STORY_URL, "source_kind": source_kind,
            "source_study": study, "states_by_viewport": {profile: {"rest": states[profile]} for profile in ("wide", "narrow")},
            "proof_component_maps": [{
                "profile": profile, "state_id": "rest", "selector": "#" + component_id,
                "component_key": "id:" + component_id, "text_sha256": proof_text_hashes[component_id],
                "rect": {"left": 0, "top": height / 2 if component_id.endswith("summary") else 0,
                         "width": width, "height": height if component_id.endswith("opening") else height / 2},
            } for profile, width, height in (("wide", 1440, 900), ("narrow", 390, 844))
              for component_id in proof_text_hashes],
            "interaction_census_by_viewport": {"wide": {"pages": []}, "narrow": {"pages": []}},
        }
        observation_path = write_json(references / f"{source_id}-observation.json", observation)
        selector_rows = []
        style_values = {
            "product-story-opening": ("#product-story-opening", "id:product-story-opening", {
                "display": "grid", "padding": "0px", "gap": "0px", "background-color": "rgba(0, 0, 0, 0)", "height": "900px", "grid-template-rows": "450px 450px",
            }),
            "product-story-heading": ("#product-story-heading", "id:product-story-heading", {
                "display": "block", "font-family": "sans-serif", "font-size": "32px", "font-weight": "700", "line-height": "40px", "margin": "0px",
            }),
            "product-story-summary": ("#product-story-summary", "id:product-story-summary", {
                "display": "block", "color": "rgb(0, 0, 0)", "margin": "0px",
            }),
        }
        for profile in ("wide", "narrow"):
            for selector, component_key, properties in style_values.values():
                selector_rows.append({"profile": profile, "state_id": "rest", "selector": selector,
                                      "component_key": component_key, "properties": {key: ("844px" if profile == "narrow" and key == "height" else "422px 422px" if profile == "narrow" and key == "grid-template-rows" else value) for key, value in properties.items()}})
        styles = write_json(references / f"{source_id}-styles.json", {"tool": "extract_reference_styles.mjs", "component_styles": selector_rows})
        source_code = root / "src" / "proof-slice.tsx"
        source_code.parent.mkdir(parents=True, exist_ok=True)
        source_code.write_text(
            "export default () => <main data-design-dna-component=\"product-story-opening\" data-design-dna-proof-status=\"internal-unverified\">"
            + LABEL
            + "<h1 data-design-dna-component=\"product-story-heading\">AirPods Pro</h1>"
            + "<p data-design-dna-component=\"product-story-summary\">A bounded source-faithful opening specimen.</p></main>;\n",
            encoding="utf-8",
        )
        html = root / "index.html"
        html.write_text(
            "<!doctype html><meta charset=\"utf-8\"><meta name=\"design-dna-proof-source-file\" content=\"src/proof-slice.tsx\"><meta name=\"design-dna-proof-source-sha256\" content=\"" + sha(source_code) + "\"><style>html,body{margin:0;height:100%;overflow:hidden}main{display:grid;height:100vh;padding:0;gap:0;background-color:transparent}h1{display:block;margin:0;font-family:sans-serif;font-size:32px;font-weight:700;line-height:40px}p{display:block;margin:0;color:rgb(0,0,0)}</style>"
            + "<main data-design-dna-component=\"product-story-opening\" data-design-dna-proof-status=\"internal-unverified\">"
            + LABEL
            + "<h1 data-design-dna-component=\"product-story-heading\">AirPods Pro</h1>"
            + "<p data-design-dna-component=\"product-story-summary\">A bounded source-faithful opening specimen.</p></main>",
            encoding="utf-8",
        )
        components = []
        for component_id, (selector, component_key, properties) in style_values.items():
            components.append({
                "component_id": component_id, "source_selector": selector, "source_component_key": component_key,
                "content": {"source_text_sha256": proof_text_hashes[component_id], "build_text_sha256": proof_text_hashes[component_id]},
                "styles": {
                    "record": {"path": styles.relative_to(root).as_posix(), "sha256": sha(styles)},
                    "properties": list(properties),
                    "tuples": [{"viewport": profile, "source_state_id": "rest", "property": property,
                                "source_value": ("844px" if profile == "narrow" and property == "height" else "422px 422px" if profile == "narrow" and property == "grid-template-rows" else value), "build_value": ("844px" if profile == "narrow" and property == "height" else "422px 422px" if profile == "narrow" and property == "grid-template-rows" else value)}
                               for profile in ("wide", "narrow") for property, value in properties.items()],
                },
                "media": {"kind": "none"},
            })
        payload: dict[str, object] = {
            "schema_version": 1, "record_type": "design-dna-proof-slice",
            "proof_slice_id": "product-story-opening", "status": "internal-unverified",
            "brief": {"path": brief.relative_to(root).as_posix(), "sha256": sha(brief), "current_at": "2026-09-04T00:00:00Z"},
            "source": {
                "source_kind": source_kind, "id": source_id,
                "observation": observation_path.relative_to(root).as_posix(), "sha256": sha(observation_path), "url": PRODUCT_STORY_URL,
                "states": {profile: {"id": "rest", "sha256": self.init.canonical_json_sha256(states[profile])} for profile in ("wide", "narrow")},
                "arrangement_frames": {profile: {"path": f".design-dna/references/{frames[profile]['file']}", "bytes": frames[profile]["bytes"], "sha256": frames[profile]["sha256"]} for profile in ("wide", "narrow")},
            },
            "implementation": {
                "source_file": source_code.relative_to(root).as_posix(), "source_file_sha256": sha(source_code),
                "build_output_path": html.relative_to(root).as_posix(),
                "proof_url": "__LOCAL_URL__", "primary_component_id": "product-story-opening", "visible_label": LABEL,
            },
            "visible_components": components,
            "transfer_coverage": {
                "layout": ["product-story-opening"],
                "type": ["product-story-heading"],
                "color": ["product-story-opening", "product-story-summary"],
                "spacing": ["product-story-opening"],
                "control": {"status": "source-absent", "component_ids": [], "evidence": {profile: {"path": f".design-dna/references/{frames[profile]['file']}", "bytes": frames[profile]["bytes"], "sha256": frames[profile]["sha256"]} for profile in ("wide", "narrow")}},
                "media": {"status": "source-absent", "component_ids": [], "evidence": {profile: {"path": f".design-dna/references/{frames[profile]['file']}", "bytes": frames[profile]["bytes"], "sha256": frames[profile]["sha256"]} for profile in ("wide", "narrow")}},
            },
        }
        return write_json(root / ".design-dna" / "proof-slice.json", payload), payload

    def invoke(self, root: Path, *, dry_run: bool = False) -> tuple[int, dict]:
        command = [PYTHON, "-X", "utf8", "-B", str(GATE), "--project", str(root),
                   "--build-id", "proof-build-0001", "--phase", "proof-slice", "--proof-slice", ".design-dna/proof-slice.json"]
        if dry_run:
            command.append("--dry-run")
        done = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        return done.returncode, json.loads(done.stdout)

    def test_local_product_story_proof_slice_renders_but_cannot_authorize_public_work(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest_path, payload = self.prepared(root)
            with LocalServer(root) as server:
                payload["implementation"]["proof_url"] = server.url
                write_json(manifest_path, payload)
                code, record = self.invoke(root)
                build = json.loads((root / record["controlled_build"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual(0, code, record)
        self.assertTrue(record["pass"])
        self.assertEqual("built", record["statuses"]["proof_slice_built"])
        self.assertEqual("pass", record["statuses"]["proof_slice_gate"])
        self.assertEqual("did-not-run", record["statuses"]["standard_first_screen_gate"])
        self.assertEqual("not-applicable", record["statuses"]["final_site"])
        self.assertEqual("ineligible", record["statuses"]["public_eligibility"])
        self.assertIsNone(record.get("prebuild_authorization"))
        self.assertEqual(payload["implementation"]["source_file_sha256"], build["source"]["sha256"])
        self.assertTrue(build["output"]["sha256"])

    def test_responsive_values_are_checked_in_their_own_viewport(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest_path, payload = self.prepared(root)
            styles_path = root / payload["visible_components"][0]["styles"]["record"]["path"]
            styles = json.loads(styles_path.read_text(encoding="utf-8"))
            for row in styles["component_styles"]:
                if row["profile"] == "narrow" and row["selector"] == "#product-story-heading":
                    row["properties"]["font-size"] = "24px"
            write_json(styles_path, styles)
            for component in payload["visible_components"]:
                component["styles"]["record"]["sha256"] = sha(styles_path)
                for tuple_ in component["styles"]["tuples"]:
                    if tuple_["viewport"] == "narrow" and tuple_["property"] == "font-size":
                        tuple_["source_value"] = tuple_["build_value"] = "24px"
            with LocalServer(root) as server:
                payload["implementation"]["proof_url"] = server.url
                write_json(manifest_path, payload)
                code, record = self.invoke(root)
            self.assertEqual(0, code, record["failures"])

    def test_declared_but_undelivered_font_is_not_a_rendered_font_pass(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest_path, payload = self.prepared(root)
            styles_path = root / payload["visible_components"][0]["styles"]["record"]["path"]
            styles = json.loads(styles_path.read_text(encoding="utf-8"))
            for row in styles["component_styles"]:
                if "font-family" in row["properties"]:
                    row["properties"]["font-family"] = '"Definitely Missing Product Font", sans-serif'
            write_json(styles_path, styles)
            for component in payload["visible_components"]:
                component["styles"]["record"]["sha256"] = sha(styles_path)
                for tuple_ in component["styles"]["tuples"]:
                    if tuple_["property"] == "font-family":
                        tuple_["source_value"] = tuple_["build_value"] = '"Definitely Missing Product Font", sans-serif'
            with LocalServer(root) as server:
                payload["implementation"]["proof_url"] = server.url
                write_json(manifest_path, payload)
                code, record = self.invoke(root)
            self.assertNotEqual(0, code)
            self.assertIn("declared-font-not-rendered", " ".join(record["failures"]))

    def test_repeated_runs_preserve_prior_rendered_frames(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest_path, payload = self.prepared(root)
            with LocalServer(root) as server:
                payload["implementation"]["proof_url"] = server.url
                write_json(manifest_path, payload)
                first_code, first = self.invoke(root)
                rendered = json.loads((root / first["rendered_proof"]["path"]).read_text(encoding="utf-8"))
                frames = [(Path(check["screenshot"]["path"]), check["screenshot"]["sha256"]) for check in rendered["checks"]]
                second_code, second = self.invoke(root)
                self.assertEqual([0, 0], [first_code, second_code], [first["failures"], second["failures"]])
                self.assertTrue(all(sha(path) == digest for path, digest in frames))
                self.assertNotEqual(first["rendered_proof"]["path"], second["rendered_proof"]["path"])

    def test_same_six_urls_cannot_make_a_generic_electronics_scaffold_source_faithful(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest_path, payload = self.prepared(root)
            generic = root / "src" / "proof-slice.tsx"
            generic.write_text(
                "const sources = " + json.dumps(SIX_REFERENCE_URLS) + "; export default () => <main data-design-dna-component=\"product-story-opening\" data-design-dna-proof-status=\"internal-unverified\">"
                + LABEL + "<h1 data-design-dna-component=\"product-story-heading\">Electronics</h1><p data-design-dna-component=\"product-story-summary\">Generic card grid</p></main>;",
                encoding="utf-8",
            )
            payload["implementation"]["source_file_sha256"] = sha(generic)
            payload["source"]["sha256"] = "0" * 64
            write_json(manifest_path, payload)
            code, record = self.invoke(root, dry_run=True)
        self.assertNotEqual(0, code)
        self.assertFalse(record["pass"])
        self.assertEqual("unverified", record["statuses"]["proof_slice_built"])
        self.assertTrue(any("generated proof-source" in item or "screenshot-only" in item for item in record["failures"]))

    def test_generic_runtime_scaffold_cannot_clear_static_maps_or_the_same_six_urls(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest_path, payload = self.prepared(root)
            source = root / payload["implementation"]["source_file"]
            source.write_text(
                "const sources = " + json.dumps(SIX_REFERENCE_URLS) + "; export default () => <main data-design-dna-component=\"product-story-opening\" data-design-dna-proof-status=\"internal-unverified\">"
                + LABEL + "<h1 data-design-dna-component=\"product-story-heading\">Electronics</h1><p data-design-dna-component=\"product-story-summary\">Generic grid</p></main>;",
                encoding="utf-8",
            )
            (root / "wrong.html").write_text(
                "<!doctype html><meta charset=\"utf-8\"><style>html,body{margin:0;height:100%;overflow:hidden}main{display:block;height:100vh}h1,p{display:block;margin:0}</style>"
                + "<main data-design-dna-component=\"product-story-opening\" data-design-dna-proof-status=\"internal-unverified\">"
                + LABEL + "<h1 data-design-dna-component=\"product-story-heading\">Electronics</h1><p data-design-dna-component=\"product-story-summary\">Generic grid</p></main>",
                encoding="utf-8",
            )
            self.rebind_source(root, payload)
            with LocalServer(root) as server:
                payload["implementation"]["proof_url"] = server.url_for("wrong.html")
                write_json(manifest_path, payload)
                code, record = self.invoke(root)
        self.assertNotEqual(0, code)
        self.assertEqual("unverified", record["statuses"]["proof_slice_built"])
        self.assertTrue(any("controlled build" in item for item in record["failures"]))

    def test_wrong_tsx_cannot_launder_a_compliant_handwritten_served_html(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest_path, payload = self.prepared(root)
            source = root / payload["implementation"]["source_file"]
            source.write_text(
                "export default () => <main data-design-dna-component=\"product-story-opening\" data-design-dna-proof-status=\"internal-unverified\">"
                + LABEL + "<h1 data-design-dna-component=\"product-story-heading\">Wrong source</h1><p data-design-dna-component=\"product-story-summary\">Unserved TSX</p></main>;",
                encoding="utf-8",
            )
            self.rebind_source(root, payload)
            (root / "handwritten.html").write_text((root / "index.html").read_text(encoding="utf-8"), encoding="utf-8")
            with LocalServer(root) as server:
                payload["implementation"]["proof_url"] = server.url_for("handwritten.html")
                write_json(manifest_path, payload)
                code, record = self.invoke(root)
        self.assertNotEqual(0, code)
        self.assertTrue(any("controlled build" in item for item in record["failures"]))

    def test_screenshot_only_or_dry_run_is_unverified_and_cannot_advance(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest_path, payload = self.prepared(root)
            observation_path = root / payload["source"]["observation"]
            observation = json.loads(observation_path.read_text(encoding="utf-8"))
            observation.pop("source_study")
            write_json(observation_path, observation)
            payload["source"]["sha256"] = sha(observation_path)
            write_json(manifest_path, payload)
            code, record = self.invoke(root, dry_run=True)
        self.assertNotEqual(0, code)
        self.assertEqual("unverified", record["statuses"]["proof_slice_built"])
        self.assertEqual("unverified", record["statuses"]["proof_slice_gate"])
        self.assertEqual("did-not-run", record["statuses"]["standard_first_screen_gate"])
        self.assertEqual("not-applicable", record["statuses"]["final_site"])

    def test_hidden_second_region_or_route_is_rejected_before_rendering(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest_path, payload = self.prepared(root)
            source = root / payload["implementation"]["source_file"]
            source.write_text(
                "export default () => <main data-design-dna-component=\"product-story-opening\" data-design-dna-proof-status=\"internal-unverified\">"
                + LABEL + "<h1 data-design-dna-component=\"product-story-heading\">Proof</h1><p data-design-dna-component=\"product-story-summary\">One screen</p>{false && <section>hidden route</section>}</main>;",
                encoding="utf-8",
            )
            self.rebind_source(root, payload)
            write_json(manifest_path, payload)
            code, record = self.invoke(root, dry_run=True)
        self.assertNotEqual(0, code)
        self.assertTrue(any("conditional-jsx" in item or "unmapped-visible" in item for item in record["failures"]))

    def test_hidden_runtime_second_section_cannot_launder_a_valid_source_file(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest_path, payload = self.prepared(root)
            (root / "wrong.html").write_text(
                "<!doctype html><meta charset=\"utf-8\"><style>html,body{margin:0;height:100%;overflow:hidden}main{display:grid;height:100vh}h1,p{display:block;margin:0}</style>"
                + "<main data-design-dna-component=\"product-story-opening\" data-design-dna-proof-status=\"internal-unverified\">"
                + LABEL + "<h1 data-design-dna-component=\"product-story-heading\">Proof</h1><p data-design-dna-component=\"product-story-summary\">One screen</p></main>"
                + "<section style=\"display:none\">prewritten second section</section>",
                encoding="utf-8",
            )
            self.rebind_source(root, payload)
            with LocalServer(root) as server:
                payload["implementation"]["proof_url"] = server.url_for("wrong.html")
                write_json(manifest_path, payload)
                code, record = self.invoke(root)
                rendered = json.loads((root / record["rendered_proof"]["path"]).read_text(encoding="utf-8"))
        self.assertNotEqual(0, code)
        self.assertTrue(any(
            finding.get("code") == "proof-region-runtime-count"
            for check in rendered["checks"] for finding in check["findings"]
        ))

    def test_proof_slice_cli_cannot_request_standard_first_screen_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest_path, _payload = self.prepared(root)
            done = subprocess.run(
                [PYTHON, "-X", "utf8", "-B", str(GATE), "--project", str(root),
                 "--build-id", "proof-build-0001", "--phase", "proof-slice",
                 "--proof-slice", str(manifest_path.relative_to(root)), "--route-manifest", ".design-dna/route-manifest.json"],
                capture_output=True, text=True, encoding="utf-8",
            )
        self.assertNotEqual(0, done.returncode)
        self.assertIn("separate from route-manifest", done.stderr)

    def test_internal_label_on_a_child_cannot_launder_an_unlabeled_proof_root(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest_path, payload = self.prepared(root)
            source = root / payload["implementation"]["source_file"]
            source.write_text(
                "export default () => <main data-design-dna-component=\"product-story-opening\">"
                + "<aside data-design-dna-proof-status=\"internal-unverified\">" + LABEL + "</aside>"
                + "<h1 data-design-dna-component=\"product-story-heading\">Proof</h1><p data-design-dna-component=\"product-story-summary\">One screen</p></main>;",
                encoding="utf-8",
            )
            payload["implementation"]["source_file_sha256"] = sha(source)
            write_json(manifest_path, payload)
            code, record = self.invoke(root, dry_run=True)
        self.assertNotEqual(0, code)
        self.assertTrue(any("proof-label-missing" in item for item in record["failures"]))

    def test_proof_slice_cannot_substitute_one_token_for_layout_type_color_and_spacing_transfer(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest_path, payload = self.prepared(root)
            payload["transfer_coverage"]["type"] = []
            payload["transfer_coverage"]["color"] = []
            write_json(manifest_path, payload)
            code, record = self.invoke(root, dry_run=True)
        self.assertNotEqual(0, code)
        self.assertTrue(any("type coverage" in item for item in record["failures"]))
        self.assertTrue(any("color coverage" in item for item in record["failures"]))

    def test_unmapped_runtime_decorative_connective_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest_path, payload = self.prepared(root)
            (root / "wrong.html").write_text(
                "<!doctype html><meta charset=\"utf-8\"><style>html,body{margin:0;height:100%;overflow:hidden}.producer-ornament{position:absolute;width:40px;height:40px;background:red}main{display:grid;height:100vh}h1,p{display:block;margin:0}</style>"
                + "<div class=\"producer-ornament\"></div><main data-design-dna-component=\"product-story-opening\" data-design-dna-proof-status=\"internal-unverified\">"
                + LABEL + "<h1 data-design-dna-component=\"product-story-heading\">Proof</h1><p data-design-dna-component=\"product-story-summary\">One screen</p></main>",
                encoding="utf-8",
            )
            self.rebind_source(root, payload)
            with LocalServer(root) as server:
                payload["implementation"]["proof_url"] = server.url_for("wrong.html")
                write_json(manifest_path, payload)
                code, record = self.invoke(root)
                rendered = json.loads((root / record["rendered_proof"]["path"]).read_text(encoding="utf-8"))
        self.assertNotEqual(0, code)
        self.assertTrue(any(
            finding.get("code") == "proof-unmapped-runtime-visible"
            for check in rendered["checks"] for finding in check["findings"]
        ))

    def test_iframe_shadow_canvas_and_pseudo_surfaces_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest_path, payload = self.prepared(root)
            (root / "wrong.html").write_text(
                "<!doctype html><meta charset=\"utf-8\"><style>main::before{content:'x';display:block;background:red;width:10px;height:10px}main{display:grid}h1,p{display:block}</style>"
                + "<main data-design-dna-component=\"product-story-opening\" data-design-dna-proof-status=\"internal-unverified\">"
                + LABEL + "<h1 data-design-dna-component=\"product-story-heading\">Proof</h1><p data-design-dna-component=\"product-story-summary\">One screen</p><iframe srcdoc=\"<section><a href='/secret'>secret</a></section>\"></iframe><object data=\"/secret.html\"></object><embed src=\"/secret.html\"><canvas></canvas></main>"
                + "<script>document.querySelector('[data-design-dna-component=product-story-summary]').attachShadow({mode:'open'}).innerHTML='<b>hidden</b>'</script>",
                encoding="utf-8",
            )
            with LocalServer(root) as server:
                payload["implementation"]["proof_url"] = server.url_for("wrong.html")
                write_json(manifest_path, payload)
                code, record = self.invoke(root)
                rendered = json.loads((root / record["rendered_proof"]["path"]).read_text(encoding="utf-8"))
        self.assertNotEqual(0, code)
        codes = {finding.get("code") for check in rendered["checks"] for finding in check["findings"]}
        self.assertTrue({"proof-frame-surface", "proof-shadow-surface", "proof-canvas-surface", "proof-pseudo-surface"}.issubset(codes), codes)

    def test_delayed_runtime_mutation_fails_the_required_quiet_window(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest_path, payload = self.prepared(root)
            (root / "wrong.html").write_text(
                "<!doctype html><meta charset=\"utf-8\"><main data-design-dna-component=\"product-story-opening\" data-design-dna-proof-status=\"internal-unverified\">"
                + LABEL + "<h1 data-design-dna-component=\"product-story-heading\">Proof</h1><p data-design-dna-component=\"product-story-summary\">One screen</p></main>"
                + "<script>setTimeout(()=>document.body.append(document.createElement('section')),900)</script>",
                encoding="utf-8",
            )
            with LocalServer(root) as server:
                payload["implementation"]["proof_url"] = server.url_for("wrong.html")
                write_json(manifest_path, payload)
                code, record = self.invoke(root)
                rendered = json.loads((root / record["rendered_proof"]["path"]).read_text(encoding="utf-8"))
        self.assertNotEqual(0, code)
        self.assertTrue(any(
            finding.get("code") == "proof-postload-mutation"
            for check in rendered["checks"] for finding in check["findings"]
        ))

    def test_runtime_media_crop_must_match_the_typed_source_role_map(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest_path, payload = self.prepared(root)
            asset_url = "https://images.apple.com/airpods-pro-proof.png"
            observation_path = root / payload["source"]["observation"]
            observation = json.loads(observation_path.read_text(encoding="utf-8"))
            for profile in ("wide", "narrow"):
                observation["interaction_census_by_viewport"][profile] = {
                    "pages": [{"dom_code_inventory": {"assets": [asset_url]}}],
                }
            for profile in ("wide", "narrow"):
                observation["proof_component_maps"].append({
                    "selector": "#product-story-media", "component_key": "id:product-story-media", "text_sha256": text_sha(""),
                    "profile": profile, "rect": {"width": 101, "height": 50},
                    "properties": {"object-fit": "cover", "object-position": "50% 50%"}, "media": {"source_url": asset_url},
                })
            write_json(observation_path, observation)
            payload["source"]["sha256"] = sha(observation_path)
            styles_path = root / payload["visible_components"][0]["styles"]["record"]["path"]
            styles = json.loads(styles_path.read_text(encoding="utf-8"))
            for profile in ("wide", "narrow"):
                styles["component_styles"].append({
                    "profile": profile, "state_id": "rest", "selector": "#product-story-media",
                    "component_key": "id:product-story-media", "properties": {"display": "block"},
                })
            write_json(styles_path, styles)
            for component in payload["visible_components"]:
                component["styles"]["record"]["sha256"] = sha(styles_path)
            payload["visible_components"].append({
                "component_id": "product-story-media", "source_selector": "#product-story-media",
                "source_component_key": "id:product-story-media",
                "content": {"source_text_sha256": text_sha(""), "build_text_sha256": text_sha("")},
                "styles": {
                    "record": {"path": styles_path.relative_to(root).as_posix(), "sha256": sha(styles_path)},
                    "properties": ["display"],
                    "tuples": [{"viewport": profile, "source_state_id": "rest", "property": "display", "source_value": "block", "build_value": "block"} for profile in ("wide", "narrow")],
                },
                "media": {
                    "kind": "image", "source_url": asset_url, "role": "Source product subject crop", "temporal_mode": "still",
                    "crop": {"width": 101, "height": 50, "object_fit": "cover", "object_position": "50% 50%"},
                },
            })
            payload["transfer_coverage"]["media"] = {
                "status": "present", "component_ids": ["product-story-media"],
                "evidence": payload["source"]["arrangement_frames"],
            }
            source = root / payload["implementation"]["source_file"]
            source.write_text(source.read_text(encoding="utf-8").replace(
                "</main>;", "<img data-design-dna-component=\"product-story-media\" /></main>;"
            ), encoding="utf-8")
            (root / "wrong.html").write_text((root / "index.html").read_text(encoding="utf-8").replace(
                "</style>", "img{display:block;width:100px;height:50px;object-fit:cover;object-position:50% 50%}</style>"
            ).replace("</main>", "<img data-design-dna-component=\"product-story-media\" src=\"product.png\"></main>"), encoding="utf-8")
            self.rebind_source(root, payload)
            with LocalServer(root) as server:
                payload["implementation"]["proof_url"] = server.url_for("wrong.html")
                write_json(manifest_path, payload)
                code, record = self.invoke(root)
                rendered = json.loads((root / record["rendered_proof"]["path"]).read_text(encoding="utf-8"))
        self.assertNotEqual(0, code)
        self.assertTrue(any(
            finding.get("code") == "proof-component-runtime" and "media-crop-mismatch" in finding.get("message", "")
            for check in rendered["checks"] for finding in check["findings"]
        ))

    def test_present_control_requires_exact_source_selector_and_rendered_semantic_control(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest_path, payload = self.prepared(root)
            observation_path = root / payload["source"]["observation"]
            observation = json.loads(observation_path.read_text(encoding="utf-8"))
            for profile in ("wide", "narrow"):
                observation["interaction_census_by_viewport"][profile] = {
                    "pages": [{"targets": [{"selector": "#product-story-heading", "kind": "control", "tag": "button"}]}],
                }
            write_json(observation_path, observation)
            payload["source"]["sha256"] = sha(observation_path)
            payload["transfer_coverage"]["control"] = {
                "status": "present", "component_ids": ["product-story-heading"],
                "evidence": payload["source"]["arrangement_frames"],
            }
            source = root / payload["implementation"]["source_file"]
            source.write_text(source.read_text(encoding="utf-8").replace("<h1 ", "<button ").replace("</h1>", "</button>"), encoding="utf-8")
            html = root / "index.html"
            html.write_text(html.read_text(encoding="utf-8").replace("h1{display:block", "button{display:block").replace("<h1 ", "<button ").replace("</h1>", "</button>"), encoding="utf-8")
            self.rebind_source(root, payload)
            with LocalServer(root) as server:
                payload["implementation"]["proof_url"] = server.url
                write_json(manifest_path, payload)
                code, record = self.invoke(root)
        self.assertEqual(0, code, record)
        self.assertEqual("pass", record["statuses"]["proof_slice_gate"])


if __name__ == "__main__":
    unittest.main()
