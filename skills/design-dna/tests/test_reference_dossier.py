#!/usr/bin/env python3
"""Regression coverage for public-reference direction records."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
INITIALIZER_PATH = SKILL / "scripts" / "init_project_state.py"


def load_initializer():
    specification = importlib.util.spec_from_file_location(
        "design_dna_reference_dossier",
        INITIALIZER_PATH,
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


INITIALIZER = load_initializer()


def valid_dossier_body() -> str:
    strong_rows = "\n".join(
        "| {rank} | Reference {rank} | https://example.test/reference-{rank} | "
        "awwwards | 2026-09-01 | public-gallery-entry | Supports the visitor "
        "decision and category story for this exact project. | A clear hierarchy, "
        "media relationship, and direct entry condition. | Do not reproduce its "
        "brand assets, writing, source code, or full page. |".format(rank=rank)
        for rank in range(1, 11)
    )
    negative_rows = "\n".join(
        "| Weak example {rank} | https://example.test/weak-{rank} | siteinspire | "
        "2026-09-01 | public-gallery-entry | Its visible hierarchy turns a real "
        "visitor task into generic spectacle. | Keep task hierarchy and truthful "
        "content ahead of decorative treatment. |".format(rank=rank)
        for rank in range(1, 4)
    )
    return "\n".join((
        "## Research frame",
        "- Brief and priority-source rationale: The brief needs credible product "
        "orientation, material evidence, and a direct shopping path.",
        "- Current active registry audit date and limitations: 2026-09-01; public "
        "source entries only, with unavailable sources skipped.",
        "- Authorized-account basis, if any; otherwise `none`: none",
        "- Public-access disposition for blocked or unavailable sources: Those "
        "sources were excluded from the selected reference set.",
        "",
        "## Ten strong references",
        "| Rank | Reference title or visible entry | Public URL or gallery-entry URL | Discovery source | Retrieval date | Access status | Brief relevance | Transferable relationship | Non-copying boundary |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        strong_rows,
        "",
        "## Negative counterexamples",
        "| Reference title or visible entry | Public URL or gallery-entry URL | Discovery source | Retrieval date | Access status | Observed mismatch or weak relationship | What this project must avoid |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        negative_rows,
        "",
        "## Selected synthesis",
        "- Selected positive ranks (five through ten distinct ranks from the table): 1, 2, 3, 4, 5",
        "- Project-specific organizing synthesis: The selected direction makes "
        "the product, evidence, and next decision visible in one coherent retail "
        "encounter rather than rotating unrelated treatments.",
        "- Negative-counterevidence result: The final direction retains visible "
        "task hierarchy and product specificity instead of decorative spectacle.",
        "- Direction record path and status: .design-dna/direction.md; draft "
        "selection is ready to bind before broad implementation.",
        "",
        "| Selected rank(s) | Decision role | Project-specific adaptation | Boundary or verification |",
        "| --- | --- | --- | --- |",
        "| 1, 2, 3, 4, 5 | Opening, product detail, navigation, proof, and mobile "
        "reading | Adapt each relationship to the actual content model and visitor "
        "task. | Render wide and narrow candidates, then verify direct entry and "
        "non-copying boundaries. |",
    ))


class ReferenceDossierTests(unittest.TestCase):
    def test_registry_excludes_restricted_source_from_active_pool(self) -> None:
        payload, active_sources, failures = INITIALIZER.load_reference_source_registry()
        self.assertEqual([], failures)
        self.assertEqual(1, payload["schema_version"])
        self.assertIn("awwwards", active_sources)
        self.assertNotIn("land-book", active_sources)

        for access in (
            "login-required",
            "paywalled",
            "security-blocked",
            "unavailable-current",
        ):
            with self.subTest(access=access):
                restricted = {
                    "schema_version": 1,
                    "audited_on": "2026-09-01",
                    "policy": "Public-only inspiration sources; do not bypass access controls.",
                    "sources": [{
                        "id": "restricted-source",
                        "name": "Restricted source",
                        "url": "https://example.test/",
                        "status": "active",
                        "access": access,
                        "scope": "Design examples.",
                        "notes": "Useful entries need restricted or unavailable access.",
                    }],
                }
                failures = INITIALIZER.reference_source_registry_failures(restricted)
                self.assertTrue(
                    any("does not have usable public access" in item for item in failures),
                    failures,
                )

        temporary = {
            "schema_version": 1,
            "audited_on": "2026-09-01",
            "policy": "Public-only inspiration sources; do not bypass access controls.",
            "sources": [
                {
                    "id": "public-source",
                    "name": "Public source",
                    "url": "https://example.test/public",
                    "status": "active",
                    "access": "public",
                    "scope": "Design examples.",
                    "notes": "Public examples are visible without an account.",
                },
                {
                    "id": "temporarily-unavailable",
                    "name": "Temporarily unavailable source",
                    "url": "https://example.test/",
                    "status": "inactive",
                    "access": "unavailable-current",
                    "scope": "Design examples.",
                    "notes": "A later public audit may reactivate this source.",
                },
            ],
        }
        self.assertEqual([], INITIALIZER.reference_source_registry_failures(temporary))

    def test_reference_dossier_requires_ten_positive_and_three_negative_rows(self) -> None:
        body = valid_dossier_body()
        self.assertEqual([], INITIALIZER.reference_dossier_failures(body))

        insufficient = body.replace(
            "| Weak example 3 | https://example.test/weak-3 | siteinspire | "
            "2026-09-01 | public-gallery-entry | Its visible hierarchy turns a real "
            "visitor task into generic spectacle. | Keep task hierarchy and truthful "
            "content ahead of decorative treatment. |\n",
            "",
        )
        failures = INITIALIZER.reference_dossier_failures(insufficient)
        self.assertTrue(
            any("at least three negative counterexample rows" in item for item in failures),
            failures,
        )

        blocked = body.replace(
            "| 10 | Reference 10 | https://example.test/reference-10 | awwwards | "
            "2026-09-01 | public-gallery-entry | Supports the visitor decision and "
            "category story for this exact project. | A clear hierarchy, media "
            "relationship, and direct entry condition. | Do not reproduce its brand "
            "assets, writing, source code, or full page. |",
            "| 10 | Reference 10 | https://example.test/reference-10 | land-book | "
            "2026-09-01 | paywalled | Supports the visitor decision and category "
            "story for this exact project. | A clear hierarchy, media relationship, "
            "and direct entry condition. | Do not reproduce its brand assets, writing, "
            "source code, or full page. |",
        )
        failures = INITIALIZER.reference_dossier_failures(blocked)
        self.assertTrue(
            any("active public source ID" in item for item in failures),
            failures,
        )
        self.assertTrue(
            any("blocked or paywalled entries cannot qualify" in item for item in failures),
            failures,
        )

    def test_enterprise_profile_initializes_the_reference_dossier_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / ".design-dna"
            INITIALIZER.render_new_state(
                SKILL,
                state,
                "test-fixture",
                INITIALIZER.PROFILES["enterprise-candidate"],
                ("standard", "enterprise-candidate"),
            )
            payload = json.loads((state / "state.json").read_text(encoding="utf-8"))
            self.assertIn("reference-dossier", payload["records"])
            self.assertIn(
                "reference-led-direction",
                payload["evidence_contract"]["applicable_capabilities"],
            )
            self.assertTrue((state / "reference-dossier.md").is_file())
            direction = (state / "direction.md").read_text(encoding="utf-8")
            visual = (state / "visual-review.md").read_text(encoding="utf-8")
            self.assertIn(
                "## Reference-led direction (required for public candidates)",
                direction,
            )
            self.assertIn(
                "## Reference-led direction closure (required for public candidates)",
                visual,
            )

    def test_prebuild_blocks_an_enterprise_candidate_with_a_draft_dossier(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            INITIALIZER.render_new_state(
                SKILL,
                state,
                "test-fixture",
                INITIALIZER.PROFILES["enterprise-candidate"],
                ("standard", "enterprise-candidate"),
            )
            failures = INITIALIZER.prebuild_failures(project)
            self.assertTrue(
                any("reference-dossier.md remains draft" in item for item in failures),
                failures,
            )

    def test_migration_reopens_missing_enterprise_reference_dossier(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / ".design-dna"
            INITIALIZER.render_new_state(
                SKILL,
                state,
                "test-fixture",
                INITIALIZER.PROFILES["enterprise-candidate"],
                ("standard", "enterprise-candidate"),
            )
            state_path = state / "state.json"
            legacy = json.loads(state_path.read_text(encoding="utf-8"))
            legacy["schema_version"] = 1
            legacy["records"].remove("reference-dossier")
            legacy["evidence_contract"]["applicable_capabilities"].remove(
                "reference-led-direction"
            )
            state_path.write_text(
                json.dumps(legacy, indent=2) + "\n",
                encoding="utf-8",
            )
            (state / "reference-dossier.md").unlink()

            updated = INITIALIZER.migrate_staged_state(state, "test-fixture")

            migrated = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertIn("reference-dossier", updated)
            self.assertIn("reference-dossier", migrated["records"])
            self.assertIn(
                "reference-led-direction",
                migrated["evidence_contract"]["applicable_capabilities"],
            )
            self.assertEqual(
                "draft",
                INITIALIZER.parse_frontmatter(state / "reference-dossier.md")[
                    "record_status"
                ],
            )


if __name__ == "__main__":
    unittest.main()
