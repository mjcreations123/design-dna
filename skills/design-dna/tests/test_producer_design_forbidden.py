#!/usr/bin/env python3
"""The owner's standing order, 2026-09-03: no producer design, in any part.

"Your own designs is absolutely forbidden ... There is absolutely no using
your design. You must only use the designs from the websites you are copying
from. And this includes designs, layouts, fonts, and everything else."

These tests hold the three mechanical consequences:
- a typeface substitute is accepted only when match_typeface.mjs ranked it
  first for the family it replaces (check_style_provenance.mjs --match);
- match_typeface.mjs ranks by the observation's own numbers, offline;
- gate.py, the one command, refuses to plan a run with nothing to trace to
  and refuses a substitute that has no match record.
"""

from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_style_provenance import bind_served_record, style_record

SKILL = Path(__file__).resolve().parents[1]
PROVENANCE = SKILL / "scripts" / "check_style_provenance.mjs"
MATCHER = SKILL / "scripts" / "match_typeface.mjs"
GATE = SKILL / "scripts" / "gate.py"
NODE = shutil.which("node")
OBSERVER_SHA256 = hashlib.sha256((SKILL / "scripts" / "observe_reference.mjs").read_bytes()).hexdigest()
MATCHER_SHA256 = hashlib.sha256(MATCHER.read_bytes()).hexdigest()


def write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def observation(path: Path, *, display: str, x_ratio: float, advance: float) -> Path:
    return write_json(path, {
        "schema_version": 5,
        "tool": "observe_reference.mjs",
        "producer_script_sha256": OBSERVER_SHA256,
        "runtime_identity": {
            "structure_probe.mjs": hashlib.sha256((SKILL / "scripts" / "structure_probe.mjs").read_bytes()).hexdigest(),
            "browser_evidence.mjs": hashlib.sha256((SKILL / "scripts" / "browser_evidence.mjs").read_bytes()).hexdigest(),
            "playwright_resolver.mjs": hashlib.sha256((SKILL / "scripts" / "playwright_resolver.mjs").read_bytes()).hexdigest(),
        },
        "id": path.name.replace("-observation.json", ""),
        "url": f"https://{path.name.replace('-observation.json', '')}.test/",
        "first_screen": {
            "grid": [],
            "type": {
                "display": {"family": display, "size": 96, "weight": "500", "x_ratio": x_ratio, "advance": advance},
                "body": {"family": "Bodyface", "size": 16, "weight": "400", "x_ratio": 0.71, "advance": 8.2},
                "families": [display, "Bodyface"],
            },
        },
        "mechanisms": [],
        "score": {"distinct_mechanisms": 3, "scroll_coverage": 1},
        "motion": {"observed": True},
        "coverage": {"rest": True, "scroll_holds": 3, "hovers": 2},
        "states_by_viewport": {"wide": {"rest": {}}, "narrow": {"rest": {}}},
    })


def run_node(script: Path, *args: str, cwd: Path) -> tuple[int, dict]:
    proc = subprocess.run([NODE, str(script), *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8")
    text = proc.stdout.strip()
    payload = {}
    if text:
        try:
            payload = json.loads(text[text.rfind("\n{") + 1:] if text.rfind("\n{") != -1 else text)
        except ValueError:
            payload = {"raw": text}
    return proc.returncode, payload


@unittest.skipIf(NODE is None, "node is required")
class TypefaceMatcherTests(unittest.TestCase):
    def test_ranks_the_nearest_measured_face_first(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            obs = observation(root / "strong-1-observation.json", display="Louize Display", x_ratio=0.62, advance=6.86)
            measured = write_json(root / "measured.json", [
                {"family": "Cormorant Garamond", "weight": "500", "x_ratio": 0.619, "advance": 6.852,
                 "font_fingerprint": {"raster": hashlib.sha256(b"Cormorant Garamond").hexdigest()[:16], "probe_width": 180, "ink": 1800}},
                {"family": "Playfair Display", "weight": "400", "x_ratio": 0.732, "advance": 7.85,
                 "font_fingerprint": {"raster": "1111111111111111", "probe_width": 160, "ink": 1600}},
                {"family": "Inter", "weight": "400", "x_ratio": 0.753, "advance": 8.69,
                 "font_fingerprint": {"raster": "2222222222222222", "probe_width": 50, "ink": 500}},
                {"family": "Broken", "weight": "400", "error": "no src"},
            ])
            out = root / "typeface-match.json"
            code, payload = run_node(MATCHER, "--observation", str(obs), "--measured", str(measured), "--out", str(out), cwd=root)
            self.assertEqual(0, code, payload)
            record = json.loads(out.read_text(encoding="utf-8"))
        display = next(r for r in record["results"] if r["target"]["role"] == "display")
        self.assertEqual("Cormorant Garamond", display["chosen"]["family"])
        self.assertEqual("Louize Display", display["target"]["family"])
        self.assertTrue(all(r["family"] != "Broken" for r in display["ranked"]))


@unittest.skipIf(NODE is None, "node is required")
class SubstituteMustBeRankOneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        state = self.root / ".design-dna"
        refs = state / "references"
        refs.mkdir(parents=True)
        self.observation = observation(refs / "strong-1-observation.json", display="Louize Display", x_ratio=.62, advance=6.86)
        observation_sha = hashlib.sha256(self.observation.read_bytes()).hexdigest()
        manifest_payload = {
            "schema_version": 2, "manifest_id": "substitute-manifest-123",
            "viewports": [{"name": "wide", "width": 1440, "height": 900}, {"name": "narrow", "width": 390, "height": 844}],
            "routes": [{"key": "home", "url": "http://127.0.0.1:9000/", "mapped_reference_rank": 1,
                        "mapped_reference_id": "strong-1", "mapped_reference_observation": ".design-dna/references/strong-1-observation.json",
                        "mapped_reference_sha256": observation_sha,
                        "states": [{"id": "rest", "kind": "rest", "trigger": {"type": "none", "target": "document", "value": None},
                                    "expectation": "initial settled route", "mapped_reference_state_id": "rest"}]}],
        }
        self.manifest = write_json(state / "route-manifest.json", manifest_payload)
        manifest_sha = hashlib.sha256(self.manifest.read_bytes()).hexdigest()
        reference_record = style_record(
            "strong-1", families=("Louize Display", "Bodyface"), colors=(("rgb(243, 240, 237)", "background", 0.4), ("rgb(24, 22, 21)", "text", 0.0)),
            control_fills=("rgb(24, 22, 21)",), sizes=(120, 18), radii=("0px",), transitions=(("0.65s", "ease"),), section_grounds=("rgb(243, 240, 237)",),
        )
        reference_record["source_observation"] = {"id": "strong-1", "url": "https://strong-1.test/",
                                                   "file": ".design-dna/references/strong-1-observation.json", "sha256": observation_sha}
        bind_served_record(self.root, "strong-1-styles.json", reference_record, "source", "wide")
        self.reference = write_json(self.root / "strong-1-styles.json", reference_record)
        build_record = style_record(
            "build-index", families=("Cormorant Garamond", "Bodyface"), colors=(("rgb(243, 240, 237)", "background", 0.4), ("rgb(24, 22, 21)", "text", 0.0)),
            control_fills=("rgb(24, 22, 21)",), sizes=(120, 18), radii=("0px",), transitions=(("0.65s", "ease"),), section_grounds=("rgb(243, 240, 237)",),
        )
        self.builds = []
        for viewport in ("wide", "narrow"):
            record = json.loads(json.dumps(build_record))
            record.update({"route_key": "home", "viewport": viewport, "manifest_id": "substitute-manifest-123",
                           "manifest_sha256": manifest_sha})
            filename = f"build-{viewport}-styles.json"
            bind_served_record(self.root, filename, record, "home", viewport)
            self.builds.append(write_json(self.root / filename, record))
        self.observation_sha = observation_sha

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def match_record(self, chosen: str) -> Path:
        return write_json(self.root / "typeface-match.json", {
            "tool": "match_typeface.mjs", "schema_version": 3,
            "producer_script_sha256": MATCHER_SHA256, "verified_browser_measurement": True,
            "runtime_identity": {
                "observe_reference.mjs": OBSERVER_SHA256,
                "playwright_resolver.mjs": hashlib.sha256(
                    (SKILL / "scripts" / "playwright_resolver.mjs").read_bytes()
                ).hexdigest(),
            },
            "input_observations": [{"file": ".design-dna/references/strong-1-observation.json", "id": "strong-1",
                                    "url": "https://strong-1.test/", "sha256": self.observation_sha}],
            "observation_set_sha256": hashlib.sha256(json.dumps([
                {"id": "strong-1", "url": "https://strong-1.test/", "sha256": self.observation_sha}
            ], separators=(",", ":")).encode()).hexdigest(),
            "results": [{
                "target": {"family": "Louize Display", "role": "display", "x_ratio": 0.62, "advance": 6.86,
                           "observation_sha256": self.observation_sha},
                "ranked": [{"family": chosen, "weight": "500", "delta": 0.003,
                            "font_fingerprint": {"raster": hashlib.sha256(chosen.encode()).hexdigest()[:16],
                                                 "probe_width": float(len(chosen) * 10), "ink": len(chosen) * 100},
                            "source_url": "https://fonts.example.test/font.woff2", "source_sha256": "a" * 64}],
                "chosen": {"family": chosen, "weight": "500", "delta": 0.003,
                           "font_fingerprint": {"raster": hashlib.sha256(chosen.encode()).hexdigest()[:16],
                                                "probe_width": float(len(chosen) * 10), "ink": len(chosen) * 100},
                           "source_url": "https://fonts.example.test/font.woff2", "source_sha256": "a" * 64},
            }],
        })

    def run_check(self, *extra: str) -> tuple[int, dict]:
        return run_node(
            PROVENANCE, "--manifest", str(self.manifest),
            "--build", str(self.builds[0]), "--build", str(self.builds[1]), "--reference", str(self.reference),
            "--build-id", "test-build-123", "--run-id", "test-run-123", "--out", str(self.root / "style-provenance.json"), *extra, cwd=self.root,
        )

    def test_a_substitute_without_a_match_record_is_refused(self) -> None:
        code, payload = self.run_check("--substitute", "Louize Display=Cormorant Garamond")
        self.assertNotEqual(0, code, payload)
        self.assertEqual("bad-substitute", payload.get("error", {}).get("code"), payload)

    def test_a_substitute_the_matcher_ranked_first_passes(self) -> None:
        match = self.match_record("Cormorant Garamond")
        code, payload = self.run_check("--substitute", "Louize Display=Cormorant Garamond", "--match", str(match))
        self.assertEqual(0, code, payload)
        record = json.loads((self.root / "style-provenance.json").read_text(encoding="utf-8"))
        self.assertTrue(record["ok"], record.get("verdict"))
        self.assertEqual("Cormorant Garamond", record["substitutes"][0]["to"])

    def test_a_substitute_the_producer_chose_is_refused(self) -> None:
        match = self.match_record("EB Garamond")
        code, payload = self.run_check("--substitute", "Louize Display=Cormorant Garamond", "--match", str(match))
        self.assertNotEqual(0, code, payload)
        self.assertIn("ranked", payload.get("error", {}).get("message", ""), payload)


class RebindTests(unittest.TestCase):
    """The gate rewrites the records the dossier binds, so it rebinds them."""

    def load_gate(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("design_dna_gate", GATE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_only_bound_records_the_gate_wrote_are_rebound(self) -> None:
        gate = self.load_gate()
        old = "a" * 64
        new = "b" * 64
        untouched = "c" * 64
        text = (
            "- Component census: .design-dna/evidence/component-census.json plus sha256:" + old + "\n"
            "| 1 | sig | hero | .design-dna/evidence/mechanism-diff.json plus sha256:" + old + " | loss |\n"
            "| 2 | sig | btn | .design-dna/references/strong-1-observation.json plus sha256:" + untouched + " | loss |\n"
        )
        rebound_text, rebound = gate.rebind_dossier(text, {
            ".design-dna/evidence/component-census.json": new,
            ".design-dna/evidence/mechanism-diff.json": new,
            ".design-dna/evidence/structure-diff.json": new,
        })
        self.assertEqual(
            [".design-dna/evidence/component-census.json", ".design-dna/evidence/mechanism-diff.json"], rebound
        )
        self.assertEqual(2, rebound_text.count(new))
        self.assertIn(untouched, rebound_text)
        self.assertNotIn(old, rebound_text)

    def test_an_unchanged_digest_is_not_reported(self) -> None:
        gate = self.load_gate()
        same = "d" * 64
        text = "- Component census: .design-dna/evidence/component-census.json plus sha256:" + same + "\n"
        rebound_text, rebound = gate.rebind_dossier(text, {".design-dna/evidence/component-census.json": same})
        self.assertEqual([], rebound)
        self.assertEqual(text, rebound_text)


class GateTests(unittest.TestCase):
    BUILD_ID = "test-build-123"

    def manifest(self, root: Path) -> Path:
        observation_path = root / ".design-dna" / "references" / "strong-1-observation.json"
        observation_sha = hashlib.sha256(observation_path.read_bytes()).hexdigest() if observation_path.is_file() else "0" * 64
        return write_json(root / ".design-dna" / "route-manifest.json", {
            "schema_version": 2,
            "manifest_id": "test-manifest-123",
            "viewports": [
                {"name": "wide", "width": 1440, "height": 900},
                {"name": "narrow", "width": 390, "height": 844},
            ],
            "routes": [{
                "key": "home", "url": "http://127.0.0.1:1/",
                "mapped_reference_rank": 1,
                "mapped_reference_id": "strong-1",
                "mapped_reference_observation": ".design-dna/references/strong-1-observation.json",
                "mapped_reference_sha256": observation_sha,
                "states": [{"id": "rest", "kind": "rest",
                            "trigger": {"type": "none", "target": "document", "value": None},
                            "expectation": "initial settled route",
                            "mapped_reference_state_id": "rest"}],
            }],
        })

    def run_gate(self, root: Path, *args: str) -> tuple[int, str]:
        proc = subprocess.run(
            [sys.executable, "-B", str(GATE), "--project", str(root),
             "--build-id", self.BUILD_ID, "--route-manifest", str(self.manifest(root)),
             "--phase", "first-screen", "--route-key", "home", *args],
            capture_output=True, text=True, encoding="utf-8",
        )
        return proc.returncode, proc.stdout + proc.stderr

    def test_help_runs(self) -> None:
        proc = subprocess.run([sys.executable, "-B", str(GATE), "--help"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("--route-manifest", proc.stdout)

    def test_a_project_with_nothing_to_trace_to_fails_the_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".design-dna").mkdir()
            code, out = self.run_gate(root, "--dry-run")
        self.assertEqual(1, code, out)
        self.assertIn("nothing to trace to", out)

    def test_a_substitute_without_a_match_record_fails_the_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            refs = root / ".design-dna" / "references"
            observation(refs / "strong-1-observation.json", display="Louize Display", x_ratio=0.62, advance=6.86)
            write_json(refs / "strong-1-styles.json", style_record("strong-1", families=("Louize Display",)))
            (root / ".design-dna" / "reference-dossier.md").write_text("# dossier\n", encoding="utf-8")
            code, out = self.run_gate(root, "--dry-run", "--substitute", "Louize Display=Cormorant Garamond")
        self.assertEqual(1, code, out)
        self.assertIn("does not choose faces", out)

    def test_the_verdict_record_names_the_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".design-dna").mkdir()
            code, out = self.run_gate(root)
            record = json.loads((root / ".design-dna" / "evidence" / "first-screen-gate.json").read_text(encoding="utf-8"))
        self.assertEqual(1, code, out)
        self.assertFalse(record["pass"])
        self.assertTrue(record["verdict"].startswith("GATE FAIL"))
        self.assertIn("forbidden", record["owner_order"])
        self.assertIn("GATE FAIL", out)


if __name__ == "__main__":
    unittest.main()
