"""Audit write-capable Agent tools for missing human-approval guardrails.

YYGlobal enforces two independent approval layers before a mutating tool call
reaches an external effect:

1. The global ``ToolSpec.approval_required`` flag in
   ``services/api/app/agent/tools.py``, enforced by ``ToolRegistry.execute``.
2. Each Skill's own ``approval_required`` list in its ``tool-policy.yaml``,
   used to decide whether the tool is offered to the model without requiring
   a confirmation phrase (see ``services/api/app/agent/provider.py``).

Because these two layers are maintained in different files (a Python dataclass
registry and per-Skill YAML), they can drift apart: a tool can be marked
``mutates_data=True`` yet be reachable by a Skill without any approval gate on
either layer. This auditor parses both sources with ``ast`` / ``yaml`` --
without importing the FastAPI application -- and reports every Skill/tool pair
where a data-mutating tool is not gated by approval anywhere.

Usage:
    python Core-Agent/guardrail_coverage_auditor.py
    python Core-Agent/guardrail_coverage_auditor.py --json
    python Core-Agent/guardrail_coverage_auditor.py --allow program-research:verify_program_official
    python Core-Agent/guardrail_coverage_auditor.py --allowlist-file Core-Agent/guardrail_allowlist.txt
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class AuditIssue:
    skill: str
    tool: str
    message: str


@dataclass(frozen=True)
class ToolFlags:
    mutates_data: bool = False
    approval_required: bool = False


def _bool_constant(node: ast.AST) -> bool | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    return None


def registered_tool_flags(registry_path: Path) -> dict[str, ToolFlags]:
    """Return ``{tool_name: ToolFlags}`` for every literal ``ToolSpec(...)`` call."""
    tree = ast.parse(registry_path.read_text(encoding="utf-8"), filename=str(registry_path))
    flags: dict[str, ToolFlags] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        function = node.func
        is_tool_spec = (
            isinstance(function, ast.Name) and function.id == "ToolSpec"
        ) or (isinstance(function, ast.Attribute) and function.attr == "ToolSpec")
        if not is_tool_spec or not isinstance(node.args[0], ast.Constant):
            continue
        name = node.args[0].value
        if not isinstance(name, str):
            continue

        mutates_data = False
        approval_required = False
        for keyword in node.keywords:
            if keyword.arg is None:
                continue
            value = _bool_constant(keyword.value)
            if keyword.arg == "mutates_data" and value is not None:
                mutates_data = value
            elif keyword.arg == "approval_required" and value is not None:
                approval_required = value
        # Positional fallback: ToolSpec(name, description, parameters, handler,
        # mutates_data=False, approval_required=False) -- supports call sites
        # that pass the two flags positionally instead of as keywords.
        if len(node.args) > 4:
            value = _bool_constant(node.args[4])
            if value is not None:
                mutates_data = value
        if len(node.args) > 5:
            value = _bool_constant(node.args[5])
            if value is not None:
                approval_required = value

        flags[name] = ToolFlags(mutates_data=mutates_data, approval_required=approval_required)
    return flags


def load_skill_policies(skills_root: Path) -> dict[str, dict[str, list[str]]]:
    """Return ``{skill_name: {"tools": [...], "approval_required": [...]}}``."""
    policies: dict[str, dict[str, list[str]]] = {}
    if not skills_root.exists():
        return policies
    for package in sorted(path for path in skills_root.iterdir() if path.is_dir()):
        policy_path = package / "tool-policy.yaml"
        if not policy_path.exists():
            continue
        policy = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
        if not isinstance(policy, dict):
            continue
        tools = policy.get("tools")
        approvals = policy.get("approval_required")
        policies[package.name] = {
            "tools": list(tools) if isinstance(tools, list) else [],
            "approval_required": list(approvals) if isinstance(approvals, list) else [],
        }
    return policies


def _parse_allow_entry(entry: str) -> tuple[str | None, str]:
    """Parse ``"skill:tool"`` or a bare ``"tool"`` (exempt in every Skill)."""
    if ":" in entry:
        skill, tool = entry.split(":", 1)
        return skill.strip(), tool.strip()
    return None, entry.strip()


def load_allowlist(entries: list[str], allowlist_file: Path | None) -> set[tuple[str | None, str]]:
    allowlist: set[tuple[str | None, str]] = set()
    for entry in entries:
        if entry.strip():
            allowlist.add(_parse_allow_entry(entry))
    if allowlist_file is not None:
        for line in allowlist_file.read_text(encoding="utf-8").splitlines():
            stripped = line.split("#", 1)[0].strip()
            if stripped:
                allowlist.add(_parse_allow_entry(stripped))
    return allowlist


def _is_allowed(skill: str, tool: str, allowlist: set[tuple[str | None, str]]) -> bool:
    return (skill, tool) in allowlist or (None, tool) in allowlist


def audit_policies(
    tool_flags: dict[str, ToolFlags],
    skill_policies: dict[str, dict[str, list[str]]],
    allowlist: set[tuple[str | None, str]] | None = None,
) -> list[AuditIssue]:
    allowlist = allowlist or set()
    issues: list[AuditIssue] = []
    for skill, policy in skill_policies.items():
        approved_in_skill = set(policy["approval_required"])
        for tool in policy["tools"]:
            flags = tool_flags.get(tool)
            if flags is None or not flags.mutates_data:
                continue
            if flags.approval_required or tool in approved_in_skill:
                continue
            if _is_allowed(skill, tool, allowlist):
                continue
            issues.append(
                AuditIssue(
                    skill=skill,
                    tool=tool,
                    message=(
                        f"tool '{tool}' mutates data but is not gated by "
                        f"ToolSpec.approval_required nor listed in "
                        f"'{skill}' Skill's tool-policy.yaml approval_required"
                    ),
                )
            )
    return issues


def audit_repository(
    repo_root: Path, allowlist: set[tuple[str | None, str]] | None = None
) -> tuple[dict[str, ToolFlags], list[AuditIssue]]:
    registry_path = repo_root / "services" / "api" / "app" / "agent" / "tools.py"
    skills_root = repo_root / "services" / "api" / "app" / "skills"
    tool_flags = registered_tool_flags(registry_path)
    policies = load_skill_policies(skills_root)
    issues = audit_policies(tool_flags, policies, allowlist)
    return tool_flags, issues


def _format_issues(issues: list[AuditIssue]) -> str:
    return "\n".join(f"- {issue.skill}: {issue.message}" for issue in issues)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit Skill tool-policy.yaml files for ungated write tools"
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="YYGlobal repository root",
    )
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        metavar="[SKILL:]TOOL",
        help="exempt a Skill/tool pair (or a tool in every Skill); repeatable",
    )
    parser.add_argument(
        "--allowlist-file",
        type=Path,
        default=None,
        help="text file with one 'skill:tool' or 'tool' exemption per line",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    try:
        allowlist = load_allowlist(args.allow, args.allowlist_file)
        tool_flags, issues = audit_repository(args.repo_root.resolve(), allowlist)
    except (OSError, SyntaxError, yaml.YAMLError) as exc:
        print(f"ERROR: unable to audit repository: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(
            json.dumps(
                {
                    "status": "failed" if issues else "passed",
                    "tools_registered": len(tool_flags),
                    "issue_count": len(issues),
                    "issues": [asdict(issue) for issue in issues],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif issues:
        print(f"FAIL: {len(issues)} ungated write tool(s) found")
        print(_format_issues(issues))
    else:
        print(f"PASS: {len(tool_flags)} registered tool(s) checked, no gaps found")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
