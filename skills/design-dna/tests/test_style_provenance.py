#!/usr/bin/env python3
"""Regressions for check_style_provenance.mjs.

The gate exists because a build passed every prose gate this skill had while
carrying the producer's own accent color and the producer's own display face.
These tests hold the two failures that actually shipped, plus the ways a
producer would get around the check if it were written loosely.
"""

from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
CHECKER = SKILL / "scripts" / "check_style_provenance.mjs"
NODE = shutil.which("node")
EXTRACTOR_SHA256 = hashlib.sha256((SKILL / "scripts" / "extract_reference_styles.mjs").read_bytes()).hexdigest()
OBSERVER_SHA256 = hashlib.sha256((SKILL / "scripts" / "observe_reference.mjs").read_bytes()).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def bind_served_record(root: Path, file_name: str, record: dict, route_key: str, viewport: str) -> None:
    probe = {
        "route_key": route_key, "viewport": viewport,
        "requested_url": record["url"], "final_url": record["url"], "status": 200,
        "document_sha256": "1" * 64, "resources": [], "sha256": "2" * 64,
    }
    bindings = [{"route_key": route_key, "viewport": viewport, "sha256": probe["sha256"]}]
    served = {
        "algorithm": "sha256-response-bodies-v1", "probes": [probe],
        "reload_counts": {f"{route_key}/{viewport}": 2}, "inconsistent_reloads": [],
        "sha256": hashlib.sha256(canonical(bindings)).hexdigest(), "complete": True,
    }
    ledger_name = file_name.replace(".json", "-ledger.json")
    ledger_bytes = (json.dumps(served, indent=2) + "\n").encode("utf-8")
    (root / ledger_name).write_bytes(ledger_bytes)
    record["served_content"] = served
    record["served_content_identity"] = served
    record["resource_ledger"] = {
        "file": ledger_name, "sha256": hashlib.sha256(ledger_bytes).hexdigest(),
        "algorithm": served["algorithm"], "served_content_sha256": served["sha256"],
    }


def style_record(record_id, *, families=(), colors=(), control_fills=(),
                 sizes=(), radii=(), transitions=(), section_grounds=()):
    """A record shaped exactly like extract_reference_styles.mjs writes one."""
    return {
        "tool": "extract_reference_styles.mjs",
        "producer_script_sha256": EXTRACTOR_SHA256,
        "schema_version": 3,
        "id": record_id,
        "url": f"https://{record_id}.test/",
        "build_id": "test-build-123" if str(record_id).startswith("build-") else None,
        "run_id": "test-run-123" if str(record_id).startswith("build-") else None,
        "viewport": {"w": 1440, "h": 900},
        "viewports_measured": [{"name": "wide", "width": 1440, "height": 900},
                               {"name": "narrow", "width": 390, "height": 844}],
        "type": [
            {"family": family, "size": size, "weight": "400", "leading": 1,
             "tracking": "normal", "transform": "none", "style": "normal",
             "color": "rgb(20, 20, 20)", "count": 4, "sample": "Sample",
             "font_fingerprint": {"raster": hashlib.sha256(family.encode()).hexdigest()[:16],
                                  "probe_width": float(len(family) * 10), "ink": len(family) * 100}}
            for family, size in zip(families, list(sizes) + [48] * len(list(families)))
        ],
        "controls": [
            {"tag": "a", "cls": "btn", "w": 160, "h": 44, "padding": "8px 16px",
             "radius": radius, "border": "1px solid", "background": fill,
             "color": "rgb(255, 255, 255)", "font": "14 400 none",
             "tracking": "0px", "transition": "none", "decoration": "none"}
            for fill, radius in zip(control_fills, list(radii) + ["0px"] * len(list(control_fills)))
        ],
        "transitions": [
            {"property": "transform", "duration": duration, "easing": easing, "count": 12}
            for duration, easing in transitions
        ],
        "sections": [
            {"tag": "section", "cls": "band", "background": ground, "padding": "0px",
             "display": "block", "columns": None, "gap": None,
             "height_ratio": 0.6, "width_ratio": 1}
            for ground in section_grounds
        ],
        "colors": [
            {"value": value, "role": role, "count": 3, "area": area}
            for value, role, area in colors
        ],
        "radii": list(radii),
        "borders": ["1px"],
        "surfaces": [],
        "font_faces": [],
        "numbers": [0, 1, 8, 16, 44, 48, 120],
        "inspection": {"complete": True, "pseudo_elements": 0, "open_shadow_roots": 0,
                       "captured_closed_shadow_roots": 0, "same_origin_iframes": 0,
                       "canvases": 0, "uninspectable": []},
    }


REFERENCE = style_record(
    "strong-1",
    families=["Louize Display", "Beausite Classic"],
    sizes=[120, 16],
    colors=[("rgb(24, 22, 21)", "text", 0.0),
            ("rgb(243, 240, 237)", "background", 0.4),
            ("rgb(255, 104, 49)", "background", 0.05)],
    control_fills=["rgb(24, 22, 21)"],
    radii=["2px"],
    transitions=[("0.65s", "cubic-bezier(0.25, 1, 0.5, 1)")],
    section_grounds=["rgb(243, 240, 237)"],
)


@unittest.skipIf(NODE is None, "node is not on PATH")
class StyleProvenanceTests(unittest.TestCase):
    def run_check(self, build, references=(REFERENCE,), extra=()):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = root / ".design-dna"
            refs_root = state / "references"
            refs_root.mkdir(parents=True)
            prepared_references = []
            for reference in references:
                reference = json.loads(json.dumps(reference))
                source_id = reference["id"]
                observation = refs_root / f"{source_id}-observation.json"
                observation.write_text(json.dumps({
                    "tool": "observe_reference.mjs", "schema_version": 5,
                    "producer_script_sha256": OBSERVER_SHA256, "id": source_id,
                    "url": reference["url"],
                    "runtime_identity": {
                        "structure_probe.mjs": hashlib.sha256((SKILL / "scripts" / "structure_probe.mjs").read_bytes()).hexdigest(),
                        "browser_evidence.mjs": hashlib.sha256((SKILL / "scripts" / "browser_evidence.mjs").read_bytes()).hexdigest(),
                        "playwright_resolver.mjs": hashlib.sha256((SKILL / "scripts" / "playwright_resolver.mjs").read_bytes()).hexdigest(),
                    },
                    "states_by_viewport": {"wide": {"rest": {}}, "narrow": {"rest": {}}},
                }, indent=2) + "\n", encoding="utf-8")
                reference["source_observation"] = {
                    "id": source_id, "url": reference["url"],
                    "file": f".design-dna/references/{source_id}-observation.json",
                    "sha256": hashlib.sha256(observation.read_bytes()).hexdigest(),
                }
                prepared_references.append((reference, observation))
            selected, selected_observation = prepared_references[0]
            rank = int(selected["id"].split("-")[1])
            manifest = state / "route-manifest.json"
            manifest.write_text(json.dumps({
                "schema_version": 2, "manifest_id": "style-provenance-manifest-001",
                "viewports": [{"name": "wide", "width": 1440, "height": 900},
                              {"name": "narrow", "width": 390, "height": 844}],
                "routes": [{"key": "home", "url": "http://127.0.0.1:9000/",
                            "mapped_reference_rank": rank, "mapped_reference_id": selected["id"],
                            "mapped_reference_observation": selected["source_observation"]["file"],
                            "mapped_reference_sha256": selected["source_observation"]["sha256"],
                            "states": [{"id": "rest", "kind": "rest",
                                        "trigger": {"type": "none", "target": "document", "value": None},
                                        "expectation": "initial settled route", "mapped_reference_state_id": "rest"}]}],
            }, indent=2) + "\n", encoding="utf-8")
            manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
            argv = [NODE, str(CHECKER), "--manifest", str(manifest)]
            for viewport in ("wide", "narrow"):
                candidate = json.loads(json.dumps(build))
                candidate.update({"route_key": "home", "viewport": viewport,
                                  "manifest_id": "style-provenance-manifest-001",
                                  "manifest_sha256": manifest_sha})
                file_name = f"build-{viewport}-styles.json"
                bind_served_record(root, file_name, candidate, "home", viewport)
                build_file = root / file_name
                build_file.write_text(json.dumps(candidate), encoding="utf8")
                argv += ["--build", str(build_file)]
            for index, (reference, _observation) in enumerate(prepared_references):
                path = root / f"ref-{index}-styles.json"
                bind_served_record(root, path.name, reference, f"ref-{index}", "wide")
                path.write_text(json.dumps(reference), encoding="utf8")
                argv += ["--reference", str(path)]
            argv += ["--build-id", "test-build-123", "--run-id", "test-run-123", *list(extra)]
            done = subprocess.run(argv, capture_output=True, text=True)
            return json.loads(done.stdout), done.returncode

    # -- the two failures that actually shipped ---------------------------

    def test_typeface_absent_from_every_reference_fails(self):
        """Cormorant Garamond, picked by matching an x-height ratio."""
        build = style_record(
            "build-index",
            families=["Cormorant Garamond", "Beausite Classic"],
            sizes=[120, 16],
            colors=[("rgb(243, 240, 237)", "background", 0.4)],
        )
        report, code = self.run_check(build)
        self.assertFalse(report["ok"])
        self.assertEqual(code, 1)
        self.assertTrue(any(f["dimension"] == "typeface"
                            and "Cormorant" in f["value"] for f in report["findings"]))

    def test_loud_untraced_color_fails(self):
        """The accent that filled every control and a whole band."""
        build = style_record(
            "build-index",
            families=["Louize Display"], sizes=[120],
            colors=[("rgb(232, 183, 29)", "background", 0.76)],
            control_fills=["rgb(232, 183, 29)"],
            section_grounds=["rgb(232, 183, 29)"],
        )
        report, code = self.run_check(build)
        self.assertFalse(report["ok"])
        self.assertEqual(code, 1)
        self.assertIn("232, 183, 29", report["verdict"])

    def test_verdict_names_a_repeated_value_once(self):
        """Twenty controls in one untraceable color is one decision."""
        build = style_record(
            "build-index",
            families=["Louize Display"], sizes=[120],
            colors=[("rgb(232, 183, 29)", "background", 0.76)],
            control_fills=["rgb(232, 183, 29)"] * 12,
            section_grounds=["rgb(232, 183, 29)"] * 6,
        )
        report, _ = self.run_check(build)
        self.assertEqual(report["verdict"].count("232, 183, 29"), 1)

    # -- a faithful build passes ------------------------------------------

    def test_build_taking_the_reference_values_passes(self):
        build = style_record(
            "build-index",
            families=["Louize Display", "Beausite Classic"],
            sizes=[120, 16],
            colors=[("rgb(243, 240, 237)", "background", 0.4),
                    ("rgb(24, 22, 21)", "text", 0.0),
                    ("rgb(255, 104, 49)", "background", 0.05)],
            control_fills=["rgb(24, 22, 21)"],
            radii=["2px"],
            transitions=[("0.65s", "cubic-bezier(0.25, 1, 0.5, 1)")],
            section_grounds=["rgb(243, 240, 237)"],
        )
        report, code = self.run_check(build)
        self.assertTrue(report["ok"], report["verdict"])
        self.assertEqual(code, 0)

    # -- the ways a producer would get around a loose check ---------------

    def test_style_suffix_is_not_a_different_typeface(self):
        """"Geist Semi Bold" is Geist. The check must not fail a faithful build."""
        reference = style_record(
            "strong-3", families=["Geist Regular", "Geist Medium"], sizes=[96, 16],
            colors=[("rgb(243, 240, 237)", "background", 0.4)],
        )
        build = style_record(
            "build-index", families=["Geist", "Geist Semi Bold"], sizes=[96, 16],
            colors=[("rgb(243, 240, 237)", "background", 0.4)],
        )
        for target, source in zip(build["type"], reference["type"]):
            target["font_fingerprint"] = source["font_fingerprint"]
        report, _ = self.run_check(build, references=(reference,))
        self.assertFalse([f for f in report["findings"] if f["dimension"] == "typeface"],
                         report["verdict"])

    def test_generic_family_is_checked_when_it_is_the_rendered_face(self):
        """Arial/Times are not invisible loopholes when they actually render."""
        build = style_record(
            "build-index", families=["Louize Display", "Times New Roman", "Arial"],
            sizes=[120, 16, 14],
            colors=[("rgb(243, 240, 237)", "background", 0.4)],
        )
        report, _ = self.run_check(build)
        self.assertTrue([f for f in report["findings"] if f["dimension"] in {"typeface", "font-rendering"}],
                        report["verdict"])

    def test_a_quiet_untraced_color_is_reported_but_does_not_fail(self):
        """A one-off hairline gray is not the palette."""
        build = style_record(
            "build-index", families=["Louize Display"], sizes=[120],
            colors=[("rgb(243, 240, 237)", "background", 0.4),
                    ("rgb(216, 211, 199)", "border", 0.0)],
        )
        report, code = self.run_check(build)
        self.assertTrue(report["ok"], report["verdict"])
        self.assertEqual(code, 0)

    def test_near_miss_color_inside_tolerance_traces(self):
        """A value retyped off a capture is the reference's color, not a new one."""
        build = style_record(
            "build-index", families=["Louize Display"], sizes=[120],
            colors=[("rgb(244, 241, 236)", "background", 0.4)],
        )
        report, _ = self.run_check(build)
        self.assertTrue(report["ok"], report["verdict"])

    def test_transparent_is_not_a_color(self):
        build = style_record(
            "build-index", families=["Louize Display"], sizes=[120],
            colors=[("rgba(0, 0, 0, 0)", "background", 0.9),
                    ("rgb(243, 240, 237)", "background", 0.4)],
        )
        report, _ = self.run_check(build)
        self.assertTrue(report["ok"], report["verdict"])

    def test_references_without_typefaces_are_refused(self):
        """An empty reference set must not silently pass everything."""
        empty = style_record("strong-1")
        build = style_record("build-index", families=["Anything At All"], sizes=[48])
        report, code = self.run_check(build, references=(empty,))
        self.assertFalse(report["ok"])
        self.assertEqual(code, 2)
        self.assertEqual(report["error"]["code"], "empty-references")

    def test_a_build_record_is_required_to_come_from_the_extractor(self):
        build = style_record("build-index")
        build["tool"] = "hand-written"
        report, _ = self.run_check(build)
        self.assertFalse(report["ok"])
        self.assertEqual(report["error"]["code"], "not-a-style-record")

    def test_claimed_tool_name_with_wrong_runtime_identity_is_refused(self):
        build = style_record("build-index", families=["Louize Display"], sizes=[120])
        build["producer_script_sha256"] = "0" * 64
        report, code = self.run_check(build)
        self.assertEqual(2, code)
        self.assertEqual("style-record-identity", report["error"]["code"])

    def test_unmapped_union_reference_is_refused(self):
        """An extra source cannot launder a value outside the route's exact mapping."""
        second = style_record(
            "strong-2", families=["ABC Diatype"], sizes=[150],
            colors=[("rgb(232, 183, 29)", "background", 0.3)],
        )
        build = style_record(
            "build-index", families=["Louize Display"], sizes=[120],
            colors=[("rgb(232, 183, 29)", "background", 0.5)],
            control_fills=["rgb(232, 183, 29)"],
        )
        report, code = self.run_check(build, references=(REFERENCE, second))
        self.assertEqual(2, code)
        self.assertIn(report["error"]["code"], {"reference-style-observation-mismatch", "reference-style-coverage"})


if __name__ == "__main__":
    unittest.main()
