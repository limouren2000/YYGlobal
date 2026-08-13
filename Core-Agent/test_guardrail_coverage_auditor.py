"""Regression tests for the guardrail coverage auditor."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("guardrail_coverage_auditor.py")
SPEC = importlib.util.spec_from_file_location("guardrail_coverage_auditor", MODULE_PATH)
assert SPEC and SPEC.loader
AUDITOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AUDITOR
SPEC.loader.exec_module(AUDITOR)

FAKE_TOOLS_PY = '''
class ToolSpec:
    pass


class ToolRegistry:
    def _register_defaults(self) -> None:
        self.register(
            ToolSpec(
                "read_thing",
                "read-only tool",
                {},
                handler,
            )
        )
        self.register(
            ToolSpec(
                "write_thing_ungated",
                "mutates without any approval gate",
                {},
                handler,
                mutates_data=True,
            )
        )
        self.register(
            ToolSpec(
                "write_thing_globally_gated",
                "mutates but requires approval everywhere",
                {},
                handler,
                mutates_data=True,
                approval_required=True,
            )
        )
        self.register(
            ToolSpec(
                "write_thing_skill_gated",
                "mutates, gated per-Skill instead of globally",
                {},
                handler,
                mutates_data=True,
            )
        )
'''


class GuardrailCoverageAuditorTests(unittest.TestCase):
    def make_repo(self, root: Path) -> Path:
        agent_dir = root / "services" / "api" / "app" / "agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "tools.py").write_text(FAKE_TOOLS_PY, encoding="utf-8")
        return root

    def make_skill(self, root: Path, name: str, tools: list[str], approval_required: list[str]) -> None:
        skill_dir = root / "services" / "api" / "app" / "skills" / name
        skill_dir.mkdir(parents=True)
        tools_block = "\n".join(f"  - {tool}" for tool in tools)
        approvals_block = "\n".join(f"  - {tool}" for tool in approval_required)
        content = f"tools:\n{tools_block}\napproval_required:\n{approvals_block}\n"
        if not approval_required:
            content = f"tools:\n{tools_block}\napproval_required: []\n"
        (skill_dir / "tool-policy.yaml").write_text(content, encoding="utf-8")

    def test_read_only_tool_is_never_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_repo(Path(directory))
            self.make_skill(root, "demo-skill", ["read_thing"], [])
            _, issues = AUDITOR.audit_repository(root)
            self.assertEqual(issues, [])

    def test_globally_gated_write_tool_is_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_repo(Path(directory))
            self.make_skill(root, "demo-skill", ["write_thing_globally_gated"], [])
            _, issues = AUDITOR.audit_repository(root)
            self.assertEqual(issues, [])

    def test_skill_gated_write_tool_is_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_repo(Path(directory))
            self.make_skill(
                root,
                "demo-skill",
                ["write_thing_skill_gated"],
                ["write_thing_skill_gated"],
            )
            _, issues = AUDITOR.audit_repository(root)
            self.assertEqual(issues, [])

    def test_ungated_write_tool_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_repo(Path(directory))
            self.make_skill(root, "demo-skill", ["write_thing_ungated"], [])
            _, issues = AUDITOR.audit_repository(root)
            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0].skill, "demo-skill")
            self.assertEqual(issues[0].tool, "write_thing_ungated")

    def test_allowlist_suppresses_a_known_finding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_repo(Path(directory))
            self.make_skill(root, "demo-skill", ["write_thing_ungated"], [])

            allowlist = AUDITOR.load_allowlist(["demo-skill:write_thing_ungated"], None)
            _, issues = AUDITOR.audit_repository(root, allowlist)
            self.assertEqual(issues, [])

    def test_bare_tool_allowlist_entry_exempts_every_skill(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_repo(Path(directory))
            self.make_skill(root, "skill-a", ["write_thing_ungated"], [])
            self.make_skill(root, "skill-b", ["write_thing_ungated"], [])

            allowlist = AUDITOR.load_allowlist(["write_thing_ungated"], None)
            _, issues = AUDITOR.audit_repository(root, allowlist)
            self.assertEqual(issues, [])

    def test_main_returns_nonzero_exit_code_on_findings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_repo(Path(directory))
            self.make_skill(root, "demo-skill", ["write_thing_ungated"], [])
            exit_code = AUDITOR.main(["--repo-root", str(root), "--json"])
            self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
