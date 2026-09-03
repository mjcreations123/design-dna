#!/usr/bin/env python3
"""Regressions for check_style_provenance.mjs.

The gate exists because a build passed every prose gate this skill had while
carrying the producer's own accent color and the producer's own display face.
These tests hold the two failures that actually shipped, plus the ways a
producer would get around the check if it were written loosely.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
CHECKER = SKILL / "scripts" / "check_style_provenance.mjs"
NODE = shutil.which("node")


def style_record(record_id, *, families=(), colors=(), control_fills=(),
                 sizes=(), radii=(), transitions=(), section_grounds=()):
    """A record shaped exactly like extract_reference_styles.mjs writes one."""
    return {
        "tool": "extract_reference_styles.mjs",
        "schema_version": 1,
        "id": record_id,
        "url": f"https://{record_id}.test/",
        "viewport": {"w": 1440, "h": 900},
        "type": [
            {"family": family, "size": size, "weight": "400", "leading": 1,
             "tracking": "normal", "transform": "none", "style": "normal",
             "color": "rgb(20, 20, 20)", "count": 4, "sample": "Sample"}
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
        "numbers": [0, 1, 8, 16, 44, 48, 120],
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
            build_file = root / "build-styles.json"
            build_file.write_text(json.dumps(build), encoding="utf8")
            argv = [NODE, str(CHECKER), "--build", str(build_file)]
            for index, reference in enumerate(references):
                path = root / f"ref-{index}-styles.json"
                path.write_text(json.dumps(reference), encoding="utf8")
                argv += ["--reference", str(path)]
            argv += list(extra)
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
        report, _ = self.run_check(build, references=(reference,))
        self.assertFalse([f for f in report["findings"] if f["dimension"] == "typeface"],
                         report["verdict"])

    def test_fallback_stack_names_are_not_judged_as_the_build_face(self):
        """A stack's Times/Arial fallback is not a typeface the producer chose."""
        build = style_record(
            "build-index", families=["Louize Display", "Times New Roman", "Arial"],
            sizes=[120, 16, 14],
            colors=[("rgb(243, 240, 237)", "background", 0.4)],
        )
        report, _ = self.run_check(build)
        self.assertFalse([f for f in report["findings"] if f["dimension"] == "typeface"],
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
        empty = style_record("strong-x")
        build = style_record("build-index", families=["Anything At All"], sizes=[48])
        report, code = self.run_check(build, references=(empty,))
        self.assertFalse(report["ok"])
        self.assertEqual(code, 2)
        self.assertEqual(report["error"]["code"], "empty-references")

    def test_a_build_record_is_required_to_come_from_the_extractor(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            build_file = root / "build.json"
            build_file.write_text(json.dumps({"tool": "hand-written", "colors": []}),
                                  encoding="utf8")
            ref_file = root / "ref.json"
            ref_file.write_text(json.dumps(REFERENCE), encoding="utf8")
            done = subprocess.run(
                [NODE, str(CHECKER), "--build", str(build_file),
                 "--reference", str(ref_file)],
                capture_output=True, text=True,
            )
            report = json.loads(done.stdout)
        self.assertFalse(report["ok"])
        self.assertEqual(report["error"]["code"], "not-a-style-record")

    def test_union_of_references_is_what_traces(self):
        """A color from reference two is traced even when reference one lacks it."""
        second = style_record(
            "strong-2", families=["ABC Diatype"], sizes=[150],
            colors=[("rgb(232, 183, 29)", "background", 0.3)],
        )
        build = style_record(
            "build-index", families=["Louize Display"], sizes=[120],
            colors=[("rgb(232, 183, 29)", "background", 0.5)],
            control_fills=["rgb(232, 183, 29)"],
        )
        report, _ = self.run_check(build, references=(REFERENCE, second))
        self.assertTrue(report["ok"], report["verdict"])


if __name__ == "__main__":
    unittest.main()
