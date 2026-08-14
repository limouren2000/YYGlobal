"""Regression tests for the Skill contract auditor."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("audit_skill_contracts.py")
SPEC = importlib.util.spec_from_file_location("audit_skill_contracts", MODULE_PATH)
assert SPEC and SPEC.loader
AUDITOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AUDITOR
SPEC.loader.exec_module(AUDITOR)


class SkillContractAuditTests(unittest.TestCase):
    def make_package(self, root: Path) -> Path:
        package = root / "example-skill"
        package.mkdir()
        (package / "SKILL.md").write_text(
            "---\nname: example-skill\ndescription: Example\nmetadata:\n"
            "  version: 1.0.0\n---\n# Example\n",
            encoding="utf-8",
        )
        (package / "prompt.md").write_text("Return grounded JSON.", encoding="utf-8")
        schema = {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
            "additionalProperties": False,
        }
        for filename in ("input.schema.json", "output.schema.json"):
            (package / filename).write_text(json.dumps(schema), encoding="utf-8")
        (package / "tool-policy.yaml").write_text(
            "tools:\n  - known_tool\napproval_required: []\n",
            encoding="utf-8",
        )
        (package / "evals.yaml").write_text(
            "cases:\n  - name: grounded\n    input: find a program\n"
            "    expected_concepts: [official source]\n",
            encoding="utf-8",
        )
        return package

    def test_valid_package_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package = self.make_package(Path(directory))
            self.assertEqual(AUDITOR.audit_skill(package, {"known_tool"}), [])

    def test_unknown_and_unapproved_tools_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package = self.make_package(Path(directory))
            (package / "tool-policy.yaml").write_text(
                "tools:\n  - missing_tool\napproval_required:\n  - write_tool\n",
                encoding="utf-8",
            )
            messages = [
                issue.message for issue in AUDITOR.audit_skill(package, {"known_tool"})
            ]
            self.assertIn("unknown tools: missing_tool", messages)
            self.assertIn("approval_required tools are not allowed: write_tool", messages)

    def test_broken_schema_and_eval_contract_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package = self.make_package(Path(directory))
            (package / "input.schema.json").write_text(
                '{"type":"object","required":"message"}', encoding="utf-8"
            )
            (package / "evals.yaml").write_text(
                "cases:\n  - name: duplicate\n    input: first\n"
                "    expected_concepts: [source]\n"
                "  - name: duplicate\n    input: second\n"
                "  - name: empty-assertion\n    input: third\n"
                "    must_not_contain: []\n",
                encoding="utf-8",
            )
            messages = [issue.message for issue in AUDITOR.audit_skill(package, {"known_tool"})]
            self.assertTrue(any(message.startswith("invalid JSON Schema:") for message in messages))
            self.assertIn("duplicate case name: duplicate", messages)
            self.assertIn("case must define at least one assertion", messages)
            self.assertIn("must_not_contain must be a non-empty string list", messages)


if __name__ == "__main__":
    unittest.main()
