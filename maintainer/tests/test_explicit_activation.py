from __future__ import annotations

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator


PLUGIN = Path(__file__).resolve().parents[2]
SKILL = PLUGIN / "skills" / "design-dna"
SCRIPTS = PLUGIN / "maintainer" / "scripts"

sys.path.insert(0, str(SCRIPTS))
try:
    import audit_package
finally:
    sys.path.pop(0)


class ExplicitActivationTests(unittest.TestCase):
    def test_claude_native_policy_keeps_the_skill_manual_only(self) -> None:
        metadata, _body = audit_package.frontmatter(SKILL / "SKILL.md")
        self.assertIs(metadata["disable-model-invocation"], True)
        self.assertEqual(audit_package.skill_frontmatter_failures(metadata), [])
        self.assertNotEqual(metadata.get("user-invocable"), False)

    def test_frontmatter_audit_rejects_missing_false_and_nonboolean_policy(self) -> None:
        accepted = {
            "name": "design-dna",
            "description": "Explicit-only source-authorized website design.",
            "disable-model-invocation": True,
        }
        self.assertEqual(audit_package.skill_frontmatter_failures(accepted), [])
        invalid_values = [False, "true", "false", 1, None]
        for value in invalid_values:
            with self.subTest(value=value):
                metadata = {**accepted, "disable-model-invocation": value}
                self.assertEqual(
                    {item["code"] for item in audit_package.skill_frontmatter_failures(metadata)},
                    {"invalid-skill-frontmatter"},
                )
        missing = dict(accepted)
        del missing["disable-model-invocation"]
        self.assertTrue(audit_package.skill_frontmatter_failures(missing))
        self.assertTrue(audit_package.skill_frontmatter_failures({**accepted, "unknown": True}))

    def test_codex_native_policy_disallows_implicit_invocation(self) -> None:
        agent = audit_package.strict_yaml(SKILL / "agents" / "openai.yaml")
        schema = json.loads(
            (PLUGIN / "maintainer" / "schemas" / "agent.schema.json").read_text(encoding="utf-8")
        )
        validator = Draft202012Validator(schema)
        self.assertEqual(list(validator.iter_errors(agent)), [])
        self.assertIs(agent["policy"]["allow_implicit_invocation"], False)
        self.assertIn("$design-dna", agent["interface"]["default_prompt"])
        for value in (True, "false", None):
            with self.subTest(value=value):
                changed = deepcopy(agent)
                changed["policy"]["allow_implicit_invocation"] = value
                self.assertTrue(list(validator.iter_errors(changed)))

    def test_skill_catalog_requires_a_named_human_request(self) -> None:
        metadata, _body = audit_package.frontmatter(SKILL / "SKILL.md")
        description = metadata["description"]
        self.assertTrue(description.startswith(
            "Use only when the user explicitly asks to use Design DNA for the current task."
        ))
        self.assertIn("specific", description.casefold())
        for former_implicit_trigger in (
            "use for landing pages",
            "feedback that work feels",
            "apply when art direction",
        ):
            with self.subTest(trigger=former_implicit_trigger):
                self.assertNotIn(former_implicit_trigger, description.casefold())

    def test_current_behavioral_cases_use_explicit_opt_in(self) -> None:
        suite = json.loads(
            (PLUGIN / "maintainer" / "evals" / "fixtures" / "behavioral-cases.json").read_text(
                encoding="utf-8"
            )
        )
        for case in suite["cases"]:
            with self.subTest(case=case["id"]):
                self.assertEqual(case.get("invocation_mode", "explicit"), "explicit")
        case = next(
            item for item in suite["cases"]
            if item["id"] == "explicit-opt-in-neighborhood-bakery"
        )
        self.assertIn("explicit-opt-in", case["tags"])
        self.assertTrue(any(
            "human explicitly requested Design DNA" in requirement
            for requirement in case["review_requirements"]
        ))


if __name__ == "__main__":
    unittest.main()
