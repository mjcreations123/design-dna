from __future__ import annotations

import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
SKILL = PACKAGE_ROOT / "skills" / "design-dna"


def read(relative_path: str) -> str:
    return (SKILL / relative_path).read_text(encoding="utf-8")


class LaunchCompletenessContractTests(unittest.TestCase):
    """Keep conditional launch decisions available without seeding furniture."""

    def test_reference_covers_the_full_decision_set(self) -> None:
        reference = read("references/quality/launch-completeness.md")
        headings = (
            "## 1. Primary above-fold action",
            "## 2. Decision-blocking questions",
            "## 3. Response or delivery expectation",
            "## 4. Success and thank-you state",
            "## 5. Compact-action treatment",
            "## 6. Crawl and indexing policy",
            "## 7. Page descriptions",
            "## 8. Page titles",
            "## 9. Social sharing image",
            "## 10. Location and directions",
            "## 11. Text alternatives",
            "## 12. Privacy and policy boundary",
            "## 13. Analytics",
            "## 14. Decision cue or USP bar",
            "## 15. Approved social promotion",
        )
        for heading in headings:
            with self.subTest(heading=heading):
                self.assertIn(heading, reference)

    def test_the_contract_requires_truthful_applicability_not_a_recipe(self) -> None:
        reference = " ".join(
            read("references/quality/launch-completeness.md").casefold().split()
        )
        template = read("templates/launch-completeness-template.md").casefold()
        for text in (reference, template):
            self.assertIn("included", text)
            self.assertIn("not applicable", text)
            self.assertIn("blocked", text)
        self.assertIn("does not turn every decision into the same visible section", reference)
        self.assertIn("permission to invent a policy", reference)
        self.assertIn("do not invent legal promises", reference)
        self.assertIn("do not insert a placeholder measurement id", reference)
        self.assertIn("never invent a bonus", reference)
        self.assertIn("not a standing requirement", reference)
        self.assertIn("select only rows", reference)
        self.assertIn("delete rows that were never in scope", template)
        self.assertIn("does not enumerate the full library", template)
        self.assertNotIn("| 15 |", template)

    def test_router_workflow_and_preship_gate_make_the_record_actionable(self) -> None:
        router = read("references/router.md")
        workflow = read("references/workflow.md")
        gate = " ".join(read("templates/preship-gate.md").split())
        self.assertIn("Website launch completeness", router)
        self.assertIn("launch-completeness.md", workflow)
        self.assertIn("only the relevant decision families", workflow)
        self.assertIn("## A.1 Launch completeness", gate)
        self.assertIn("was not created or expanded merely", gate)


if __name__ == "__main__":
    unittest.main()
