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


if __name__ == "__main__":
    unittest.main()
