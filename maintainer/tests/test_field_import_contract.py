from __future__ import annotations

import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
SKILL = PACKAGE_ROOT / "skills" / "design-dna"


def read(relative_path: str) -> str:
    return (SKILL / relative_path).read_text(encoding="utf-8")


class FieldImportContractTests(unittest.TestCase):
    """Keep vetted field imports durable and doctrine-safe."""

    def test_default_basins_stays_post_render_evidence(self) -> None:
        basins = read("references/quality/default-basins.md")
        folded = " ".join(basins.casefold().split())
        self.assertIn("not a ban list", folded)
        self.assertIn("never consult this file while generating", folded)
        self.assertIn("compiled 2026-08-23", folded)
        self.assertIn("review this record by 2027-02-23", folded)
        self.assertIn("derived", folded)
        self.assertIn("defaulted", folded)
        self.assertIn("counterexample", folded)
        # the record cites evidence classes, never prescribes an aesthetic
        self.assertNotIn("must not use", folded)
        self.assertNotIn("banned font", folded)
        self.assertNotIn("banned color", folded)
        # Runtime review stays cause-based rather than preserving a dated
        # color or font blacklist without representative prevalence evidence.
        self.assertNotIn("#6366f1", folded)
        self.assertNotIn("#f5f1ea", folded)
        self.assertNotIn("fraunces", folded)
        self.assertNotIn("instrument serif", folded)
        self.assertIn("do not establish", folded)

    def test_fidelity_mode_binds_rendered_comparison_and_floors(self) -> None:
        fidelity = read("references/quality/artwork-fidelity.md").casefold()
        self.assertIn("visually faithful to the artwork", fidelity)
        self.assertIn("assurance boundaries", fidelity)
        self.assertIn("render-comparison.md", fidelity)
        self.assertIn("extraction", fidelity)
        self.assertIn("drift", fidelity)
        self.assertIn("request the source", fidelity)

    def test_redesign_contract_protects_continuity(self) -> None:
        redesign = read("references/flows/redesign.md").casefold()
        self.assertIn("what never changes silently", redesign)
        self.assertIn("form field names", redesign)
        self.assertIn("301", redesign)
        self.assertIn("search", redesign)
        self.assertIn("live baseline", redesign)

    def test_feedback_states_exist_with_honest_timing(self) -> None:
        states = read("references/craft/feedback-states.md").casefold()
        self.assertIn("show-delay", states)
        self.assertIn("minimum visible time", states)
        self.assertIn("skeleton", states)
        self.assertIn("optimistic", states)
        self.assertIn("undo", states)
        self.assertIn("dead end", states)
        self.assertIn("never fabricate percentages", states)

    def test_handoff_template_is_project_derived_and_optional(self) -> None:
        template = " ".join(
            read("templates/design-handoff-template.md").casefold().split()
        )
        self.assertIn("repository benefits from a", template)
        self.assertIn("client-facing `design.md`", template)
        self.assertIn("known gaps", template)
        self.assertIn("delete irrelevant sections", template)
        self.assertNotIn("write 5–10", template)
        self.assertIn("never from another brand's record", template)

    def test_router_reaches_every_new_reference(self) -> None:
        skill = read("SKILL.md")
        router = read("references/router.md")
        self.assertIn("references/router.md", skill)
        for link, target in (
            ("quality/default-basins.md", "references/quality/default-basins.md"),
            ("quality/artwork-fidelity.md", "references/quality/artwork-fidelity.md"),
            ("quality/implementation-integrity.md", "references/quality/implementation-integrity.md"),
            ("flows/redesign.md", "references/flows/redesign.md"),
            ("craft/feedback-states.md", "references/craft/feedback-states.md"),
            ("../templates/design-handoff-template.md", "templates/design-handoff-template.md"),
            ("craft/public-copy.md", "references/craft/public-copy.md"),
            ("quality/browser-support.md", "references/quality/browser-support.md"),
        ):
            with self.subTest(target=target):
                self.assertIn(link, router)
                self.assertTrue((SKILL / target).exists())

    def test_harness_adopts_the_cli_without_replacing_the_reviewer(self) -> None:
        harness = " ".join(
            read("references/quality/render-harness.md").casefold().split()
        )
        self.assertIn("@playwright/cli", harness)
        self.assertIn("pin", harness)
        self.assertIn("title", harness)
        self.assertIn("complement it and never replace", harness)
        # the schema reviewer remains the bound-report source
        self.assertIn("bundled reviewer", harness)
        self.assertIn("continue with every safe claim-relevant", harness)
        self.assertIn("do not turn one unavailable capture adapter", harness)
        self.assertIn("chromium-family evidence only", harness)
        self.assertIn("no audited importer for external evidence", harness)

    def test_browser_support_is_project_specific_and_engine_honest(self) -> None:
        support = " ".join(
            read("references/quality/browser-support.md").casefold().split()
        )
        for phrase in (
            "product support policy",
            "provisional test hypothesis",
            "baseline is a feature-availability summary",
            "chromium-family evidence does not cover gecko or webkit",
            "when emulation cannot establish the claim",
            "do not generalize one green engine",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, support)
        self.assertIn('do not invent a universal "last two versions"', support)

    def test_asset_privacy_checks_visible_and_embedded_data(self) -> None:
        assets = " ".join(
            read("references/quality/asset-integrity.md").casefold().split()
        )
        for phrase in (
            "inspect visible and embedded privacy",
            "exif, iptc, xmp, gps",
            "embedded thumbnails or previews",
            "do not blindly destroy intentional orientation",
            "inspect the output metadata again",
            "outside the deployable root",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, assets)

    def test_custom_widgets_route_to_apg_without_copy_paste_authority(self) -> None:
        access = " ".join(
            read("references/quality/accessibility-baseline.md")
            .casefold()
            .split()
        )
        for phrase in (
            "wai-aria authoring practices guide",
            "closest current",
            "complete keyboard contract",
            "informative guidance, not a normative standard",
            "not be copied without testing",
            "adding a role without its behavior breaks the promise",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, access)

    def test_performance_fallback_is_dated_diagnostic_not_a_budget(self) -> None:
        performance = " ".join(
            read("references/quality/performance.md").casefold().split()
        )
        for phrase in (
            "dated diagnostic references",
            "lcp at or below 2.5 seconds",
            "inp at or below 200 milliseconds",
            "cls at or below 0.1",
            "field 75th percentile",
            "these references do not become an owner-approved budget",
            "lab lcp/interaction/shift observation is not field percentile evidence",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, performance)

    def test_submit_availability_exception_remains_perceivable(self) -> None:
        forms = " ".join(
            read("references/flows/forms-complex-transactions.md")
            .casefold()
            .split()
        )
        self.assertIn("when validation is what decides readiness", forms)
        self.assertIn("genuinely unavailable or unsafe action", forms)
        self.assertIn("reason and next available step must be perceivable", forms)

    def test_critique_chain_requires_evidence_and_contextual_nonfindings(self) -> None:
        critique = " ".join(
            read("references/quality/critique-and-expert-review.md")
            .casefold()
            .split()
        )
        for phrase in (
            "observed relationship -> visitor consequence -> project or brief principle -> smallest corrective move -> rendered proof",
            "an audit does not silently become a redesign",
            "record `unknown` or a review candidate instead of a failure",
            "plausible patterns examined but deliberately not flagged",
            "contextual guard that rejected each one",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, critique)

    def test_deep_link_state_is_useful_only_when_safe(self) -> None:
        content = " ".join(
            read("references/craft/content-ia.md").casefold().split()
        )
        for phrase in (
            "stable, non-sensitive, permission-safe state",
            "never place a secret, token, personal datum",
            "history, logs, analytics, screenshots, and referrers",
            "history, session, or application state",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, content)
        self.assertNotIn("belongs in the url", content)

    def test_convergence_review_points_at_the_basins(self) -> None:
        watch = read("references/convergence-watch.md")
        self.assertIn("quality/default-basins.md", watch)


class ImplementationIntegrityContractTests(unittest.TestCase):
    """Keep the shipped-code layer covered without importing a lint dialect."""

    def test_silent_defeat_list_names_its_observed_mechanisms(self) -> None:
        integrity = " ".join(
            read("references/quality/implementation-integrity.md")
            .casefold()
            .split()
        )
        self.assertIn("silent defeat", integrity)
        # each entry is an observed inert-declaration mechanism, not a style rule
        for mechanism in (
            "aspect-ratio",
            "[hidden]",
            'hidden="until-found"',
            "one class more specific",
            "keep required content visible in the base document",
            "containing block",
            "built-in members before author",
            "self-test the detector",
        ):
            with self.subTest(mechanism=mechanism):
                self.assertIn(mechanism, integrity)
        self.assertIn("treat this as a live list", integrity)
        self.assertIn(
            "do not ship a blanket `[hidden] { display: none !important }`",
            integrity,
        )
        self.assertIn(
            '[hidden]:not([hidden="until-found"]) { display: none !important; }',
            integrity,
        )

    def test_script_failure_contract_matches_the_surface(self) -> None:
        integrity = " ".join(
            read("references/quality/implementation-integrity.md")
            .casefold()
            .split()
        )
        self.assertIn("public information or marketing route", integrity)
        self.assertIn("javascript application may legitimately depend", integrity)
        self.assertIn("do not turn `no javascript` into a universal release test", integrity)
        self.assertNotIn("the page renders complete with scripts disabled", integrity)

    def test_typed_code_preserves_evidence_without_importing_a_dialect(self) -> None:
        integrity = " ".join(
            read("references/quality/implementation-integrity.md")
            .casefold()
            .split()
        )
        for phrase in (
            "parse untrusted network, storage, url, form, and message values",
            "value as unknown as user",
            "widened to a broad type only to be cast back",
            "a marker such as `safety:` with no explanation is not evidence",
            "not a mandatory lint dialect",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, integrity)

    def test_integrity_reference_stays_in_the_working_behavior_lane(self) -> None:
        integrity = " ".join(
            read("references/quality/implementation-integrity.md")
            .casefold()
            .split()
        )
        self.assertIn("working behavior is a low-freedom area", integrity)
        self.assertIn("nothing here constrains an aesthetic choice", integrity)
        # it must not quietly become a taste or vocabulary gate
        for overreach in (
            "forbidden term",
            "rename symbol",
            "banned word",
            "must not name",
        ):
            with self.subTest(overreach=overreach):
                self.assertNotIn(overreach, integrity)

    def test_integrity_defers_to_the_existing_completion_gates(self) -> None:
        integrity = read("references/quality/implementation-integrity.md")
        for target in (
            "engineering-verification.md",
            "preship-gate.md",
            "production-readiness.md",
        ):
            with self.subTest(target=target):
                self.assertIn(target, integrity)
        folded = " ".join(integrity.casefold().split())
        self.assertIn("establish implementation integrity only", folded)

    def test_a_gate_may_never_be_weakened_to_pass(self) -> None:
        assurance = " ".join(
            read("policy/absolutes.md").casefold().split()
        )
        self.assertIn("never satisfy a check by weakening the check", assurance)
        self.assertIn("lowering a threshold", assurance)
        self.assertIn("suppressing the finding", assurance)
        self.assertIn("revising a standard is an owner decision", assurance)

        gate = " ".join(read("templates/preship-gate.md").casefold().split())
        self.assertIn("no gate was made to pass by lowering a threshold", gate)
        self.assertIn("silently defeated", gate)
        self.assertIn("computed or rendered result rather than the source", gate)

    def test_versions_are_resolved_not_remembered(self) -> None:
        verification = " ".join(
            read("references/quality/engineering-verification.md")
            .casefold()
            .split()
        )
        self.assertIn("rather than from a remembered value", verification)
        self.assertIn("leave unrelated dependency ranges untouched", verification)
        self.assertIn("implementation-integrity.md", verification)


class PublicCopyContractTests(unittest.TestCase):
    def test_copy_pass_keeps_voice_truth_and_private_reasoning_separate(self) -> None:
        copy = " ".join(read("references/craft/public-copy.md").casefold().split())
        for phrase in (
            "project voice outranks a generic clarity style",
            "keep construction language private",
            "portable praise or promise language",
            "minimum effective edit",
            "never claim that a pattern proves who or what wrote the text",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, copy)
        self.assertIn("em dashes", copy)
        self.assertIn("can all be right", copy)
        self.assertNotIn("never use an em dash", copy)


if __name__ == "__main__":
    unittest.main()
