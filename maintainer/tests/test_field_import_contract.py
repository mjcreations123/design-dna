from __future__ import annotations

import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
SKILL = PACKAGE_ROOT / "skills" / "design-dna"


def read(relative_path: str) -> str:
    return (SKILL / relative_path).read_text(encoding="utf-8")


class FieldImportContractTests(unittest.TestCase):
    """Keep the 5.3.0 field imports durable and doctrine-safe."""

    def test_default_basins_stays_post_render_evidence(self) -> None:
        basins = read("references/quality/default-basins.md")
        folded = basins.casefold()
        self.assertIn("not a ban list", folded)
        self.assertIn("never consult this file while generating", folded)
        self.assertIn("compiled 2026-08", folded)
        self.assertIn("review by 2027-02", folded)
        self.assertIn("derived", folded)
        self.assertIn("defaulted", folded)
        self.assertIn("counterexample", folded)
        # the record cites evidence classes, never prescribes an aesthetic
        self.assertNotIn("must not use", folded)
        self.assertNotIn("banned font", folded)
        self.assertNotIn("banned color", folded)
        # the strongest basins keep their coordinates so review has specifics
        self.assertIn("#6366f1", folded)
        self.assertIn("#f5f1ea", folded)
        self.assertIn("fraunces", folded)
        self.assertIn("instrument serif", folded)

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

    def test_handoff_template_carries_budget_and_gaps(self) -> None:
        template = read("templates/design-handoff-template.md").casefold()
        self.assertIn("accent", template)
        self.assertIn("known gaps", template)
        self.assertIn("do not", template)
        self.assertIn("never from another brand's record", template)

    def test_router_reaches_every_new_reference(self) -> None:
        skill = read("SKILL.md")
        for target in (
            "references/quality/default-basins.md",
            "references/quality/artwork-fidelity.md",
            "references/quality/implementation-integrity.md",
            "references/flows/redesign.md",
            "references/craft/feedback-states.md",
            "templates/design-handoff-template.md",
        ):
            with self.subTest(target=target):
                self.assertIn(target, skill)
                self.assertTrue((SKILL / target).exists())

    def test_harness_adopts_the_cli_without_replacing_the_reviewer(self) -> None:
        harness = " ".join(
            read("references/quality/render-harness.md").casefold().split()
        )
        self.assertIn("@playwright/cli", harness)
        self.assertIn("pin", harness)
        self.assertIn("title", harness)
        self.assertIn("complements and never replaces", harness)
        # the schema reviewer remains the bound-report source
        self.assertIn("bundled reviewer", harness)

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
            "presentational hints",
            "[hidden]",
            "one class more specific",
            "the start state must be the visible state",
            "containing block",
            "built-in members before author",
            "self-test the detector",
        ):
            with self.subTest(mechanism=mechanism):
                self.assertIn(mechanism, integrity)
        self.assertIn("treat this as a live list", integrity)

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
        self.assertIn("computed result rather than the source", gate)

    def test_versions_are_resolved_not_remembered(self) -> None:
        verification = " ".join(
            read("references/quality/engineering-verification.md")
            .casefold()
            .split()
        )
        self.assertIn("rather than from a remembered value", verification)
        self.assertIn("leave unrelated dependency ranges untouched", verification)
        self.assertIn("implementation-integrity.md", verification)


if __name__ == "__main__":
    unittest.main()
