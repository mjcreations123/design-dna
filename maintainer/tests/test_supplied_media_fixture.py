from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
EVALS = PACKAGE_ROOT / "maintainer" / "evals"
FIXTURE_ROOT = EVALS / "fixtures" / "inputs" / "supplied-media-relay"
CASES_PATH = EVALS / "fixtures" / "behavioral-cases.json"
PROVENANCE_PATH = FIXTURE_ROOT / "media-provenance.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SuppliedMediaFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.provenance = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
        cls.cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))

    def test_behavioral_suite_and_new_case_validate(self) -> None:
        schema = json.loads((EVALS / "schema.json").read_text(encoding="utf-8"))
        errors = list(Draft202012Validator(schema).iter_errors(self.cases))
        self.assertEqual(errors, [], "\n".join(error.message for error in errors))

        matches = [
            case
            for case in self.cases["cases"]
            if case["id"] == "supplied-media-relay-control"
        ]
        self.assertEqual(len(matches), 1)
        case = matches[0]
        self.assertEqual(case["input_dir"], "inputs/supplied-media-relay")
        self.assertTrue(case["adversarial"])
        self.assertIn("do not generate, download, replace, or remotely load media", case["task"])
        self.assertIn("meaningfully text-led", case["task"])

    def test_provenance_pins_supplied_assets_without_prescribing_composition(self) -> None:
        assets = self.provenance["assets"]
        self.assertGreater(len(assets), 0)
        self.assertEqual(len({asset["path"] for asset in assets}), len(assets))
        self.assertEqual(len({asset["sha256"] for asset in assets}), len(assets))

        for asset in assets:
            self.assertRegex(asset["sha256"], re.compile(r"^[0-9a-f]{64}$"))
            path = FIXTURE_ROOT / asset["path"]
            self.assertTrue(path.is_file(), asset["path"])
            self.assertEqual(sha256(path), asset["sha256"], asset["path"])
            header = path.read_bytes()[:12]
            self.assertEqual(header[:4], b"RIFF", asset["path"])
            self.assertEqual(header[8:12], b"WEBP", asset["path"])

    def test_expressive_cases_use_outcome_checks_not_house_style(self) -> None:
        case_ids = {
            "coffee-concept-no-assets",
            "owner-rejected-listening-room-regression",
            "supplied-media-relay-control",
        }
        matched = {
            case["id"]: case
            for case in self.cases["cases"]
            if case["id"] in case_ids
        }
        self.assertEqual(set(matched), case_ids)
        for case_id, case in matched.items():
            combined = (
                case["task"]
                + " "
                + " ".join(case["review_requirements"])
            ).casefold()
            with self.subTest(case=case_id):
                for prescribed_recipe in (
                    "signature relationship",
                    "design channels",
                    "loud surface recipe",
                    "surface-only volume",
                    "mentally removing",
                    "giant sans-serif",
                    "atmosphere, human-use",
                ):
                    self.assertNotIn(prescribed_recipe, combined)
                self.assertRegex(combined, r"complete render(?:ed)?")
                self.assertRegex(
                    combined,
                    r"(?:do not (?:treat|require|grade)|no visual device)",
                )
                self.assertIn("specificity", combined)

    def test_unadorned_prompts_require_specificity_without_a_deletion_recipe(self) -> None:
        case_ids = {
            "implicit-discovery-neighborhood-bakery",
            "coffee-current-supplied-facts",
        }
        matched = {
            case["id"]: case
            for case in self.cases["cases"]
            if case["id"] in case_ids
        }
        self.assertEqual(set(matched), case_ids)
        for case_id, case in matched.items():
            requirements = " ".join(case["review_requirements"]).casefold()
            with self.subTest(case=case_id):
                self.assertIn("complete render", requirements)
                self.assertIn("interchangeable", requirements)
                self.assertIn(
                    "do not require any particular visual device",
                    requirements,
                )
                self.assertNotIn("project-character floor", requirements)
                self.assertNotIn("dominant image", requirements)
                self.assertNotIn("display heading", requirements)

    def test_truth_and_authorization_boundaries_are_explicit(self) -> None:
        origin = self.provenance["origin"]
        self.assertEqual(origin["provider"], "OpenAI")
        self.assertEqual(origin["tool"], "ImageGen")
        self.assertEqual(origin["model_version"], "not recorded")
        self.assertEqual(self.provenance["authorization"]["status"], "owner-authorized")

        truth = self.provenance["truth_boundary"]
        self.assertTrue(truth["fictional"])
        self.assertFalse(truth["documentary_evidence"])
        self.assertFalse(truth["external_photo_credit_claimed"])
        self.assertFalse(truth["identity_release_claimed"])
        self.assertFalse(truth["model_release_claimed"])
        self.assertFalse(truth["property_release_claimed"])
        self.assertEqual(
            truth["required_public_disclosure"],
            "Fictional concept for evaluation.",
        )

        readme = (FIXTURE_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("generated by OpenAI ImageGen on 2026-07-29", readme)
        self.assertIn("No real venue", readme)
        self.assertIn("separate asset\nlicense is claimed", readme)

    def test_case_freezes_every_supplied_input(self) -> None:
        case = next(
            case
            for case in self.cases["cases"]
            if case["id"] == "supplied-media-relay-control"
        )
        expected = case["expected"]
        supplied_paths = {
            "README.md",
            "media-provenance.json",
            *[asset["path"] for asset in self.provenance["assets"]],
        }
        self.assertEqual(set(expected["files_unchanged"]), supplied_paths)
        self.assertTrue(supplied_paths.issubset(set(expected["files_exist"])))
        self.assertEqual(expected["max_changed_input_files"], 0)

        requirements = " ".join(case["review_requirements"])
        self.assertIn("every placed asset", requirements)
        self.assertIn("unused supplied asset is allowed", requirements)
        self.assertIn("do not grade by placement count", requirements)
        self.assertIn("meaningfully text-led", requirements)
        self.assertIn("public disclosure", requirements)

        required_home_text = set(expected["file_contains"]["index.html"])
        for asset in self.provenance["assets"]:
            self.assertNotIn(asset["path"], required_home_text)


if __name__ == "__main__":
    unittest.main()
