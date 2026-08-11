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
        self.assertIn("no universal set of \"ai fonts,\"", typography)
        self.assertIn("system font can be an intentional identity decision", typography)
        self.assertIn(
            "self-hosted files, a trusted service, platform fonts, system fonts",
            typography,
        )
        self.assertNotIn("approved font list", typography)
        self.assertNotIn("forbidden font list", typography)
        self.assertNotIn("preferred font list", typography)

    def test_runtime_cannot_reintroduce_aesthetic_absolutes(self) -> None:
        runtime = "\n".join(
            path.read_text(encoding="utf-8").casefold()
            for path in sorted(SKILL.rglob("*"))
            if path.is_file()
            and path.suffix.casefold()
            in {".md", ".yml", ".yaml", ".json", ".py", ".mjs"}
        )
        retired_rules = (
            "never use an em dash",
            "two families maximum",
            "self-host every face",
            "default target is rich",
            "one memorable element",
            "display family must not",
            "must not be a familiar geometric sans",
            "all-system-font typography on a flagship site is a failure",
            "font rotation",
            "quantitative-claim-density",
            "compound-display-compression",
            "severe-typography-compression",
            "prominent-fragment-context",
            "prominent-fragment-dynamic-style",
            "prominent-fragment-selector-context",
            "tracking <= -0.03em",
            "horizontal scale <= 0.75",
        )
        for rule in retired_rules:
            with self.subTest(rule=rule):
                self.assertNotIn(rule, runtime)

        assurance = read(SKILL / "policy" / "absolutes.md").casefold()
        self.assertIn("not an aesthetic blacklist", assurance)
        self.assertIn("truth and provenance", assurance)
        self.assertIn("access and working behavior", assurance)
        self.assertIn("aesthetic, expressive, compositional", assurance)
        self.assertIn("ingredients remain neutral and open", assurance)
        for motif in (
            "hero formulas",
            "font choices",
            "colored-word",
            "gradients",
            "count-up",
            "card grids",
            "monospace labels",
            "tiny captions",
            "decorative numbers",
        ):
            with self.subTest(motif=motif):
                self.assertNotIn(motif, assurance)

    def test_neutral_ingredients_remain_available_to_project_judgment(self) -> None:
        typography = read(SKILL / "references" / "craft" / "typography.md").casefold()
        watch = " ".join(
            read(SKILL / "references" / "convergence-watch.md")
            .casefold()
            .split()
        )
        freedom = read(SKILL / "references" / "creative-freedom.md").casefold()
        policy = read(SKILL / "policy" / "owner-defaults.yml").casefold()

        self.assertIn("a familiar card, gradient, serif, grotesk", watch)
        self.assertIn("is not a finding by itself", watch)
        self.assertIn("an unusual choice is not proof of quality", watch)
        self.assertIn("system font can be an intentional identity decision", typography)
        self.assertIn("colored, italic, underlined, outlined, animated", typography)
        self.assertIn("singular, plural, layered, local, restrained, maximal", freedom)
        self.assertIn("no universal richness or memorability device is required", freedom)
        self.assertIn("gradients, icons, and conventional components are neutral", policy)

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

    def test_visual_review_requires_rendered_microtype_observation_without_a_house_scale(self) -> None:
        review = read(
            SKILL / "templates" / "visual-review-template.md"
        ).casefold()
        preship = read(SKILL / "templates" / "preship-gate.md").casefold()
        normalized_review = " ".join(review.split())
        for phrase in (
            "smallest ordinary-reading role actually inspected",
            "smallest interactive, caption, credit, legend, or utility role",
            "narrow-width and text-spacing result",
            "repeated compact-uppercase or tracking pattern disposition",
            "numerical value is diagnostic evidence, never an automatic",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, normalized_review)
        self.assertIn("no portable numeric type threshold", preship)
        for house_value in ("12px", "13px", "0.05em", "0.1em"):
            with self.subTest(house_value=house_value):
                self.assertNotIn(house_value, review + preship)

    def test_fictional_identity_must_fit_fixture_depth_without_a_category_recipe(self) -> None:
        discovery = read(
            SKILL / "references" / "quality" / "content-discovery.md"
        ).casefold()
        normalized_discovery = " ".join(discovery.split())
        skill = " ".join(read(SKILL / "SKILL.md").casefold().split())
        workflow = " ".join(
            read(SKILL / "references" / "workflow.md").casefold().split()
        )
        preship = " ".join(
            read(SKILL / "templates" / "preship-gate.md").casefold().split()
        )
        self.assertIn("compare what its nouns promise", normalized_discovery)
        self.assertIn("not a required content checklist", normalized_discovery)
        self.assertIn(
            "repeated disclaimers do not repair a mismatch",
            normalized_discovery,
        )
        self.assertIn(
            "provide enough bounded material",
            normalized_discovery,
        )
        self.assertIn(
            "fictional, sample, demo, or prototype identity or scenario content",
            skill,
        )
        self.assertIn("even when the material appears plentiful", skill)
        self.assertIn("even when the source packet appears plentiful", workflow)
        self.assertIn("no category checklist", preship)

    def test_content_models_preserve_evidence_based_variance_without_fake_irregularity(self) -> None:
        content = " ".join(
            read(SKILL / "references" / "craft" / "content-ia.md")
            .casefold()
            .split()
        )
        self.assertIn("test sparse, rich, ordinary, and outlier entries", content)
        self.assertIn("not from the visual desire to make every item equally complete", content)
        self.assertIn("do not pad every card", content)
        self.assertIn("random omissions, fake wear, or manufactured inconsistency", content)

    def test_reused_media_must_fit_each_claim_without_a_shot_quota(self) -> None:
        imagery = " ".join(
            read(SKILL / "references" / "craft" / "imagery-illustration.md")
            .casefold()
            .split()
        )
        preship = " ".join(
            read(SKILL / "templates" / "preship-gate.md")
            .casefold()
            .split()
        )
        self.assertIn("review every content job", imagery)
        self.assertIn("changed crop alone is not distinct evidence", imagery)
        self.assertIn("do not impose a global image-count or shot-list rule", imagery)
        self.assertIn("reused media was reviewed against each adjacent claim", preship)

    def test_responsive_runway_and_explanatory_diagrams_use_project_evidence(self) -> None:
        responsive = " ".join(
            read(SKILL / "references" / "craft" / "responsive-adaptation.md")
            .casefold()
            .split()
        )
        data_visualization = " ".join(
            read(SKILL / "references" / "craft" / "data-visualization.md")
            .casefold()
            .split()
        )
        review = " ".join(
            read(SKILL / "templates" / "visual-review-template.md")
            .casefold()
            .split()
        )
        preship = " ".join(
            read(SKILL / "templates" / "preship-gate.md")
            .casefold()
            .split()
        )
        router = " ".join(read(SKILL / "SKILL.md").casefold().split())

        self.assertIn("first delivers meaningful subject content or a useful action", responsive)
        self.assertIn(
            "not as a universal pixel, viewport, screen-count, or page-length limit",
            responsive,
        )
        self.assertIn("shortening every mobile page is not the goal", responsive)
        self.assertIn("content-bearing explanatory diagram", data_visualization)
        self.assertIn("contextual pan or zoom", data_visualization)
        self.assertIn("this is not a prescribed diagram style or mobile recipe", data_visualization)
        self.assertIn("preserve the comparison task", responsive)
        self.assertIn("serially stacking complete records", responsive)
        self.assertIn("field-first transpose", responsive)
        self.assertIn("fit-to-width preview is one option", responsive)
        self.assertIn("decorative continuity devices", responsive)
        self.assertIn("first meaningful subject content or useful action", review)
        self.assertIn("comparison task result", review)
        self.assertIn("repeated status/disclosure hierarchy", review)
        self.assertIn("no universal mobile page length or screen-count target", review)
        self.assertIn("a uniformly shrunken graphic is not treated as sufficient", preship)
        self.assertIn("serial stacking is not accepted solely because it fits", preship)
        self.assertIn("content-bearing explanatory diagram", router)

    def test_truthful_boundaries_use_distinct_consequences_not_repetition(self) -> None:
        microcopy = " ".join(
            read(SKILL / "references" / "craft" / "microcopy.md")
            .casefold()
            .split()
        )
        preship = " ".join(
            read(SKILL / "templates" / "preship-gate.md")
            .casefold()
            .split()
        )
        router = " ".join(read(SKILL / "SKILL.md").casefold().split())
        self.assertIn("separate distinct consequences", microcopy)
        self.assertIn("does not automatically need to be the loudest visual element", microcopy)
        self.assertIn("rather than counting disclosures", microcopy)
        self.assertIn("repeated instances were compared by consequence", preship)
        self.assertIn("status that repeats, competes with the subject", router)

    def test_batch_masking_uses_neutral_labels_and_preserves_authorized_originals(self) -> None:
        watch = " ".join(
            read(SKILL / "references" / "convergence-watch.md")
            .casefold()
            .split()
        )
        batch = " ".join(
            read(SKILL / "references" / "quality" / "batch-range-evaluation.md")
            .casefold()
            .split()
        )
        self.assertIn("neutral labels reduce identity priming", watch)
        self.assertIn("they are not pixel redaction", watch)
        self.assertIn("authorized and needed for privacy, rights, or data minimization", watch)
        self.assertIn("preserve the verified original", watch)
        self.assertIn("record the transformation and resulting coverage loss", watch)
        self.assertIn("preserve the verified original inside its authorized evidence boundary", batch)

    def test_cross_project_review_blinds_identity_without_mandatory_pixel_transform(self) -> None:
        specificity = " ".join(
            read(SKILL / "references" / "quality" / "specificity-review.md")
            .casefold()
            .split()
        )
        freedom = " ".join(
            read(SKILL / "references" / "creative-freedom.md")
            .casefold()
            .split()
        )
        for document in (specificity, freedom):
            self.assertIn("neutral specimen labels", document)
            self.assertIn("identity map", document)
            self.assertIn("do not", document)
            self.assertIn("original and transformed hashes", document)
        self.assertIn("without changing the reviewed pixels", specificity)
        self.assertIn("do not pixel-transform every comparison", freedom)
        self.assertIn("unprovable `geometry-preserved` assertion", freedom)

    def test_batch_review_templates_bind_external_snapshots_and_all_captures(self) -> None:
        whole = read(
            SKILL / "templates" / "batch-whole-system-review-template.md"
        ).casefold()
        site = read(
            SKILL / "templates" / "batch-site-observation-template.md"
        ).casefold()
        self.assertIn("pre-review study-contract snapshot", whole)
        self.assertIn("after freezing, record this file's sha-256", whole)
        self.assertIn("do not append a self-hash", whole)
        self.assertIn("do not transform screenshot pixels by default", whole)
        self.assertIn("authorizing authority and evidence", whole)
        self.assertIn("coverage impact", whole)
        self.assertNotIn("contract sha-256:", whole)
        self.assertIn("reviewed capture manifest", site)
        self.assertIn("page or route", site)
        self.assertIn("capture mode", site)
        self.assertIn("do not compress a multi-route site", site)
        self.assertIn("after freezing, record this file's sha-256", site)
        self.assertIn("do not append a self-hash", site)
        self.assertNotIn("wide capture path and sha-256", site)
        self.assertNotIn("narrow capture path and sha-256", site)

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

    def test_showcase_requires_contrast_not_plural_full_alternatives(self) -> None:
        skill = read(SKILL / "SKILL.md").casefold()
        readme = read(PACKAGE_ROOT / "README.md").casefold()
        quick_start = read(PACKAGE_ROOT / "docs" / "QUICK_START.md").casefold()
        for name, document in (
            ("skill", skill),
            ("readme", readme),
            ("quick-start", quick_start),
        ):
            with self.subTest(document=name):
                self.assertIn(
                    "directly reviewable contrast sufficient to challenge",
                    document,
                )
                self.assertIn("full alternatives when uncertainty", document)
        self.assertNotIn("compare rendered alternatives that", skill)
        self.assertNotIn("enough directly reviewable alternatives", quick_start)

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
        self.assertIn("does not detect ai authorship", watch)
        self.assertIn("owner-authorized ledger", watch)
        self.assertIn("do not conceal truthful implementation", watch)

    def test_delivery_capture_type_and_batch_claims_stay_calibrated(self) -> None:
        runtime = "\n".join(
            path.read_text(encoding="utf-8").casefold()
            for path in sorted(SKILL.rglob("*"))
            if path.is_file()
            and path.suffix.casefold()
            in {".md", ".yml", ".yaml", ".json", ".py", ".mjs"}
        )
        policy = read(SKILL / "policy" / "owner-defaults.yml").casefold()
        render_harness = read(
            SKILL / "references" / "quality" / "render-harness.md"
        ).casefold()
        typography = read(
            SKILL / "references" / "craft" / "typography.md"
        ).casefold()
        batch = read(
            SKILL / "references" / "quality" / "batch-range-evaluation.md"
        ).casefold()
        workflow = read(SKILL / "references" / "workflow.md").casefold()
        readme = read(PACKAGE_ROOT / "README.md").casefold()
        quick_start = read(PACKAGE_ROOT / "docs" / "QUICK_START.md").casefold()
        content_ia = read(SKILL / "references" / "craft" / "content-ia.md").casefold()
        email = read(SKILL / "references" / "craft" / "email-design.md").casefold()

        for retired_claim in (
            "every build is a demo",
            "every build stays a demo",
            "demo_by_default",
            "his own words",
            "measure real composite contrast",
            "roughly 12 css pixels",
        ):
            with self.subTest(retired_claim=retired_claim):
                self.assertNotIn(retired_claim, runtime)

        self.assertIn("delivery_state_honesty", policy)
        self.assertIn("uses playwright", render_harness)
        self.assertIn("does not calculate text contrast", render_harness)
        self.assertIn("indirect evidence", typography)
        self.assertIn("do not create a portable pixel", typography)
        self.assertIn("does not redact their content", batch)
        self.assertIn("screenshot pixels", batch)
        self.assertIn("static, local, sandboxed", workflow)
        self.assertIn("clearly bounded fictional sample", readme)
        self.assertIn("explicitly fictional sample", quick_start)
        self.assertNotIn("use a clear neutral voice", content_ia)
        self.assertIn("instead of manufacturing a brand voice", content_ia)
        self.assertNotIn('first\n  words of a header. write it.', email)
        self.assertIn("target-client evidence", email)

    def test_study_regressions_preserve_tasks_without_creating_style_recipes(self) -> None:
        responsive = " ".join(
            read(SKILL / "references" / "craft" / "responsive-adaptation.md")
            .casefold()
            .split()
        )
        assets = " ".join(
            read(SKILL / "references" / "quality" / "asset-integrity.md")
            .casefold()
            .split()
        )
        visual_review = " ".join(
            read(SKILL / "templates" / "visual-review-template.md")
            .casefold()
            .split()
        )
        preship = " ".join(
            read(SKILL / "templates" / "preship-gate.md")
            .casefold()
            .split()
        )
        content_ia = " ".join(
            read(SKILL / "references" / "craft" / "content-ia.md")
            .casefold()
            .split()
        )
        data_visualization = " ".join(
            read(SKILL / "references" / "craft" / "data-visualization.md")
            .casefold()
            .split()
        )
        microcopy = " ".join(
            read(SKILL / "references" / "craft" / "microcopy.md")
            .casefold()
            .split()
        )

        self.assertIn("deepest meaningful field", responsive)
        self.assertIn("preserve consequential dependency order", responsive)
        self.assertIn("actual composite", responsive)
        self.assertIn("initial, intermediate, and terminal positions", responsive)
        self.assertIn("does not require a progress bar", responsive)
        self.assertIn("caption cannot make near-identical windows", assets)
        self.assertIn("static frame must not be presented", assets)
        self.assertIn("deep-path comparison context", visual_review)
        self.assertIn("consequential dependency order after reflow", visual_review)
        self.assertIn("composite reading-ground result", visual_review)
        self.assertIn("located endpoint", visual_review)
        self.assertIn("referential copy result", visual_review)
        self.assertIn("label/value separation result", visual_review)
        self.assertIn("teaching-model parity result", visual_review)
        self.assertIn("first meaningful action", content_ia)
        self.assertIn("quietly changing the grammar", content_ia)
        self.assertIn("repeated unit of action", microcopy)
        self.assertIn("initial view inventories", data_visualization)
        self.assertIn("static frame is not described as evidence", preship)
        self.assertIn("none is a portable requirement", responsive)
        self.assertNotIn("always use a sticky", responsive)
        self.assertNotIn("always move exclusions", responsive)

    def test_taste_calibration_recovers_direction_without_a_house_style(self) -> None:
        calibration = " ".join(
            read(SKILL / "references" / "craft" / "taste-calibration.md")
            .casefold()
            .split()
        )
        art_direction = " ".join(
            read(SKILL / "references" / "craft" / "art-direction.md")
            .casefold()
            .split()
        )
        workflow = " ".join(
            read(SKILL / "references" / "workflow.md").casefold().split()
        )
        skill = " ".join(read(SKILL / "SKILL.md").casefold().split())
        review = " ".join(
            read(SKILL / "templates" / "visual-review-template.md")
            .casefold()
            .split()
        )
        template = " ".join(
            read(SKILL / "templates" / "taste-calibration-template.md")
            .casefold()
            .split()
        )

        for phrase in (
            "this is not an ai detector, a style picker",
            "technical cleanliness is necessary but not a beauty verdict",
            "recover from an ugly result",
            "replace the root decisions",
            "does not make any family, density, media type, layout, or interaction universally good or bad",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, calibration)

        self.assertIn("maker's private design exercise", art_direction)
        self.assertIn("credible public surface", art_direction)
        self.assertIn("batch study protocol silently turn it into a collection of abstract test specimens", workflow)
        self.assertIn("ugly, artificial, generic, or not actually good", workflow)
        self.assertIn("previous visual rejection", skill)
        self.assertIn("not a font, palette, or effect swap", skill)
        self.assertIn("a fresh public-facing site", skill)
        self.assertIn("does not choose a house style", skill)
        self.assertIn("for showcase work without an approved rendered direction", skill)
        self.assertIn("first-impression and surface-fidelity review", review)
        self.assertIn("it is not a style catalog, an ai score", template)

        for forbidden_recipe in (
            "must use a display font",
            "one accent color",
            "three directions are required",
            "hero must",
            "award-level",
        ):
            with self.subTest(forbidden_recipe=forbidden_recipe):
                self.assertNotIn(forbidden_recipe, calibration)


if __name__ == "__main__":
    unittest.main()
