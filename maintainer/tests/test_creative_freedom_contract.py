from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
SKILL = PACKAGE_ROOT / "skills" / "design-dna"
SCHEMAS = PACKAGE_ROOT / "maintainer" / "schemas"
EVAL_FIXTURES = PACKAGE_ROOT / "maintainer" / "evals" / "fixtures"
ROUTE_AUDIT = SKILL / "scripts" / "route_family_audit.py"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> dict[str, object]:
    return json.loads(read(path))


def load_route_audit_module():
    spec = importlib.util.spec_from_file_location(
        "design_dna_route_family_audit_creative_freedom",
        ROUTE_AUDIT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the route-family audit module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CreativeFreedomContractTests(unittest.TestCase):
    """Protect the release from silently turning rigor into a house style."""

    def test_legacy_font_convergence_policy_is_not_shipped(self) -> None:
        self.assertFalse(
            (SKILL / "policy" / "type-convergence-watch.yml").exists()
        )
        self.assertFalse(
            (SCHEMAS / "type-convergence-watch.schema.json").exists()
        )
        self.assertFalse(
            (PACKAGE_ROOT / "maintainer" / "scripts" / "pattern_history.py").exists()
        )
        self.assertFalse((SCHEMAS / "pattern-history.schema.json").exists())

    def test_runtime_typography_guidance_has_no_family_allow_or_deny_list(self) -> None:
        typography = read(
            SKILL / "references" / "craft" / "typography.md"
        ).casefold()
        self.assertIn("there is no runtime list", typography)
        self.assertIn("a familiar choice is not automatically generic", typography)
        self.assertIn("unusual choice is not automatically distinctive", typography)
        self.assertNotIn("approved font list", typography)
        self.assertNotIn("forbidden font list", typography)
        self.assertNotIn("preferred font list", typography)

    def test_discovery_metadata_does_not_prescribe_one_time_register(self) -> None:
        skill_header = read(SKILL / "SKILL.md").split("---", 2)[1].casefold()
        claude_manifest = read(
            PACKAGE_ROOT / ".claude-plugin" / "plugin.json"
        ).casefold()
        codex_manifest = read(
            PACKAGE_ROOT / ".codex-plugin" / "plugin.json"
        ).casefold()
        for artifact in (skill_header, claude_manifest, codex_manifest):
            self.assertIn("time-appropriate", artifact)
            self.assertNotIn("truthful, contemporary", artifact)
            self.assertNotIn("must feel specific, contemporary", artifact)

    def test_creative_freedom_keeps_aesthetic_dimensions_open(self) -> None:
        freedom = read(
            SKILL / "references" / "creative-freedom.md"
        ).casefold()
        for statement in (
            "does not require or prohibit a font",
            "fixed number of concepts or proofs applies across projects",
            "aesthetic autonomy",
            "does not detect ai authorship",
        ):
            with self.subTest(statement=statement):
                self.assertIn(statement, freedom)

    def test_owner_policy_is_extensible_and_uses_contextual_orientation(self) -> None:
        schema = load_json(SCHEMAS / "owner-policy.schema.json")
        defaults = schema["properties"]["defaults"]
        self.assertNotIn("required", defaults)
        self.assertNotIn("properties", defaults)
        self.assertIn("additionalProperties", defaults)
        policy = read(SKILL / "policy" / "owner-defaults.yml")
        self.assertIn('public_orientation: "require-review"', policy)
        self.assertIn('time_register: "require-review"', policy)
        self.assertNotIn("five_second_public_comprehension", policy)
        self.assertNotIn("gradient_headline", policy)
        self.assertNotIn("headline_fragment_exceptions", policy)

    def test_route_family_contract_does_not_encode_a_visual_recipe(self) -> None:
        schema = load_json(SCHEMAS / "route-family.schema.json")
        schema_text = json.dumps(schema).casefold()
        template_text = read(
            SKILL / "templates" / "route-family-template.json"
        ).casefold()
        for legacy_field in (
            '"opening_model"',
            '"content_form"',
            '"media_model"',
            '"typography_register"',
            '"color_material_field"',
            '"signature_interaction"',
            '"energy_arc"',
        ):
            with self.subTest(field=legacy_field):
                self.assertNotIn(legacy_field, schema_text)
                self.assertNotIn(legacy_field, template_text)
        self.assertIn('"creative_logic"', schema_text)
        self.assertIn('"observable_decisions"', schema_text)
        self.assertNotIn("maxitems", schema["properties"]["routes"])
        creative_logic = schema["$defs"]["creative_logic"]
        self.assertEqual(len(creative_logic["oneOf"]), 2)
        self.assertEqual(creative_logic["oneOf"][1]["type"], "object")
        self.assertEqual(
            schema["$defs"]["route"]["properties"]["deliberate_differences"]["minItems"],
            0,
        )
        template = json.loads(template_text)
        self.assertFalse(template["review"]["cultural_acceptance"]["required"])
        self.assertEqual(
            template["review"]["cultural_acceptance"]["status"],
            "not-required",
        )

    def test_active_route_family_fixtures_use_the_current_open_contract(self) -> None:
        suite = load_json(EVAL_FIXTURES / "behavioral-cases.json")
        route_audit = load_route_audit_module()
        legacy_fields = (
            "opening_model",
            "content_form",
            "structural_silhouette",
            "media_model",
            "typography_register",
            "color_material_field",
            "signature_interaction",
            "energy_arc",
            "mobile_transformation",
        )
        inspected: set[str] = set()
        for case in suite["cases"]:
            input_dir = case.get("input_dir")
            if not isinstance(input_dir, str):
                continue
            contract = (
                EVAL_FIXTURES
                / input_dir
                / ".design-dna"
                / "route-family.json"
            )
            if not contract.is_file():
                continue
            inspected.add(input_dir)
            payload = load_json(contract)
            self.assertEqual(
                payload["schema_version"],
                2,
                f"{input_dir} must use the current route-family schema.",
            )
            for route in payload["routes"]:
                for field in legacy_fields:
                    with self.subTest(
                        input_dir=input_dir,
                        route=route["id"],
                        field=field,
                    ):
                        self.assertNotIn(field, route)

            errors, _ = route_audit.validate_contract_payload(payload)
            if input_dir == "inputs/route-family-hash-negative":
                self.assertEqual(len(errors), 10)
                self.assertEqual(
                    {item["code"] for item in errors},
                    {"invalid-route-path"},
                )
            else:
                self.assertEqual(errors, [], f"{input_dir}: {errors}")

        extension_probe = load_json(
            EVAL_FIXTURES
            / "inputs"
            / "route-family-anthology-positive"
            / ".design-dna"
            / "route-family.json"
        )
        extension_probe["routes"][0]["creative_logic"] = {
            "energy_arc": (
                "A project may choose this vocabulary when it genuinely explains "
                "that candidate; it is not a required route-root slot."
            )
        }
        extension_errors, _ = route_audit.validate_contract_payload(
            extension_probe
        )
        self.assertEqual(extension_errors, [])

        self.assertEqual(
            inspected,
            {
                "inputs/route-family-anthology-positive",
                "inputs/route-family-recolor-negative",
                "inputs/route-family-hash-negative",
                "inputs/route-family-broken-orphan-negative",
            },
        )

    def test_current_direction_and_review_templates_have_no_fixed_taste_slots(self) -> None:
        templates = "\n".join(
            read(SKILL / "templates" / name).casefold()
            for name in (
                "direction-template.md",
                "direction-proof-template.md",
                "exploration-template.md",
                "visual-review-template.md",
            )
        )
        for fixed_slot in (
            "signature relationship:",
            "high-energy moment:",
            "quiet counterpoint:",
            "golden route:",
            "bounded aesthetic risk:",
        ):
            with self.subTest(slot=fixed_slot):
                self.assertNotIn(fixed_slot, templates)

    def test_greenfield_and_range_study_do_not_silently_require_showcase(self) -> None:
        initializer = read(SKILL / "scripts" / "init_project_state.py")
        self.assertIn('"greenfield": ("standard",)', initializer)
        self.assertIn(
            '"range-study": ("standard", "range-study")',
            initializer,
        )
        self.assertNotIn('"greenfield": ("showcase",)', initializer)
        self.assertNotIn(
            '"range-study": ("showcase", "range-study")',
            initializer,
        )

    def test_render_report_records_neutral_geometry_and_computed_type_evidence(self) -> None:
        schema = load_json(SCHEMAS / "render-review.schema.json")
        self.assertEqual(schema["properties"]["schema_version"]["const"], 3)
        self.assertEqual(
            schema["properties"]["tool"]["properties"]["version"]["const"],
            "3.0.0",
        )
        definitions = schema["$defs"]
        document_required = set(definitions["document"]["required"])
        silhouette_required = set(definitions["silhouette_item"]["required"])
        type_required = set(definitions["typography_sample"]["required"])
        self.assertIn("typography_samples", document_required)
        self.assertTrue(
            {
                "normalized_rect",
                "grid_column_count",
                "visual_column_count",
                "dominant_media_area_ratio",
            }.issubset(silhouette_required)
        )
        self.assertTrue(
            {
                "font_size_px",
                "line_height_px",
                "letter_spacing_px",
                "font_stretch",
                "rendered_line_count_estimate",
            }.issubset(type_required)
        )

    def test_cross_case_review_has_one_core_and_extensible_lenses(self) -> None:
        schema = load_json(SCHEMAS / "design-review.schema.json")
        cross_case = schema["$defs"]["cross_case_analysis"]
        dimensions = cross_case["properties"]["dimensions"]
        item = dimensions["items"]
        self.assertEqual(dimensions["minItems"], 1)
        self.assertNotIn("enum", item["properties"]["dimension"])
        self.assertIn("applicability", item["required"])
        self.assertEqual(
            set(item["properties"]["applicability"]["enum"]),
            {"applicable", "not-applicable"},
        )
        audit = read(PACKAGE_ROOT / "maintainer" / "scripts" / "audit_package.py")
        self.assertIn(
            'REQUIRED_CROSS_CASE_DIMENSIONS = {"rendered_geometry"}',
            audit,
        )
        self.assertNotIn("\nCROSS_CASE_DIMENSIONS = {", audit)

        readme = " ".join(
            read(PACKAGE_ROOT / "maintainer" / "evals" / "README.md")
            .casefold()
            .split()
        )
        rubric = " ".join(
            read(PACKAGE_ROOT / "maintainer" / "evals" / "review-rubric.md")
            .casefold()
            .split()
        )
        for name, document in (("readme", readme), ("rubric", rubric)):
            with self.subTest(document=name):
                self.assertIn("`rendered_geometry`", document)
                self.assertIn("additional lenses", document)
                self.assertIn("actual projects", document)
                self.assertIn("non-exhaustive", document)
                self.assertIn("applicability", document)
                self.assertIn("counterevidence", document)
                self.assertIn("manufacturing a difference", document)
                self.assertIn("difference is not a quota", document)
        for statement in (
            "non-exhaustive examples, not a required set",
            "record applicability and supporting evidence",
            "without manufacturing a difference or counterevidence",
        ):
            with self.subTest(statement=statement):
                self.assertIn(statement, rubric)
        self.assertNotIn(
            "compare rendered geometry, typography systems, color/material systems",
            rubric,
        )

    def test_direction_phase_does_not_preload_post_render_diagnostics(self) -> None:
        skill = " ".join(read(SKILL / "SKILL.md").casefold().split())
        risk = " ".join(
            read(SKILL / "references" / "risk-rubric.md").casefold().split()
        )
        self.assertIn(
            '| new direction, redesign, "generic," or "dated" | [art direction]',
            skill,
        )
        new_direction_row = next(
            row
            for row in read(SKILL / "SKILL.md").casefold().splitlines()
            if row.startswith('| new direction, redesign, "generic," or "dated"')
        )
        self.assertNotIn("risk-rubric", new_direction_row)
        self.assertIn("first complete render or observed durable defect", skill)
        self.assertIn("use this after a candidate has been rendered", risk)
        self.assertIn("load in phases", skill)
        self.assertIn("direction references before the first candidate", skill)
        self.assertIn(
            "diagnostic or finish references only after a render exists",
            skill,
        )
        self.assertIn(
            "load the smallest set that answers the current decision",
            skill,
        )

    def test_entry_templates_do_not_force_every_genre_into_conversion(self) -> None:
        direction = " ".join(
            read(SKILL / "templates" / "direction-template.md")
            .casefold()
            .split()
        )
        validation = " ".join(
            read(SKILL / "templates" / "user-validation-template.md")
            .casefold()
            .split()
        )
        self.assertIn(
            "decision, task, understanding, invitation, encounter, or response",
            direction,
        )
        self.assertIn("do not force an art, narrative, editorial", direction)
        self.assertIn("for task-, service-, or product-led work", validation)
        self.assertIn(
            "for art, narrative, editorial, cultural, or entertainment work",
            validation,
        )
        self.assertIn("do not force a primary action", validation)

    def test_asset_guidance_preserves_aesthetic_roles_and_proportional_records(self) -> None:
        asset_guidance = " ".join(
            read(SKILL / "references" / "quality" / "asset-integrity.md")
            .casefold()
            .split()
        )
        asset_example = " ".join(
            read(SKILL / "templates" / "asset-manifest.example.yml")
            .casefold()
            .split()
        )
        self.assertIn(
            "do not make a production provenance dossier a prerequisite",
            asset_guidance,
        )
        self.assertIn("scale the review to stage, claim, audience risk", asset_guidance)
        self.assertIn("a decorative asset does not need an invented", asset_guidance)
        self.assertIn("aesthetic, atmospheric, ornamental, or compositional role", asset_example)
        self.assertIn("there is no required subject, crop, palette", asset_example)

    def test_asset_art_direction_is_optional_and_project_defined(self) -> None:
        initializer = read(SKILL / "scripts" / "init_project_state.py")
        asset_example = read(
            SKILL / "templates" / "asset-manifest.example.yml"
        ).casefold()
        asset_guidance = read(
            SKILL / "references" / "quality" / "asset-integrity.md"
        ).casefold()

        self.assertIn('asset_extensible_mapping_fields = {"art_direction"}', initializer.casefold())
        optional_block = initializer.split("ASSET_OPTIONAL_FIELDS = {", 1)[1].split("}", 1)[0]
        self.assertIn('"art_direction"', optional_block)
        nested_block = initializer.split("ASSET_NESTED_FIELDS = {", 1)[1].split(
            "ASSET_LIST_FIELDS = {", 1
        )[0]
        self.assertNotIn('"art_direction": {', nested_block)
        for fixed_field in (
            "crop_or_safe_zone:",
            "lighting_palette_perspective:",
            "set_consistency_notes:",
        ):
            with self.subTest(field=fixed_field):
                self.assertNotIn(fixed_field, asset_example)
        self.assertIn("replace_with_project_specific_concern", asset_example)
        self.assertIn("`art_direction` is optional and extensible", asset_guidance)

    def test_flow_guidance_does_not_ban_a_message_geometry(self) -> None:
        messaging = read(
            SKILL / "references" / "flows" / "messaging-notifications.md"
        ).casefold()
        self.assertNotIn("avoid endless rounded chat bubbles", messaging)
        self.assertIn("bubbles, a log, a comment thread", messaging)
        self.assertIn("can each be correct", messaging)

    def test_policy_and_examples_cannot_masquerade_as_literal_defaults(self) -> None:
        policy = " ".join(
            read(SKILL / "policy" / "owner-defaults.yml").casefold().split()
        )
        route_template = load_json(
            SKILL / "templates" / "route-family-template.json"
        )
        matrix = read(SKILL / "templates" / "state-matrix.example.yml").casefold()
        watch = read(SKILL / "references" / "convergence-watch.md").casefold()
        self.assertIn(
            "truth_and_claims: prohibit means prohibit unsupported",
            policy,
        )
        self.assertIn(
            "working_controls: prohibit means prohibit broken or misleading",
            policy,
        )
        for route in route_template["routes"]:
            self.assertIn("project-derived", route["responsive_result"])
            for viewport in route["capture_requirements"]["viewports"]:
                self.assertTrue(viewport["id"].startswith("replace-with-"))
                self.assertIsNone(viewport["width"])
        self.assertIn("not a recommended device", matrix)
        self.assertNotIn("last reviewed:", watch)
        self.assertNotIn("review by:", watch)
        self.assertIn("intentionally contains no claim", watch)
        self.assertIn("installed skill does not depend on", watch)
        self.assertIn("not a portable runtime dependency", watch)


if __name__ == "__main__":
    unittest.main()
