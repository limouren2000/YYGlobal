"""Audit YYGlobal Skill packages without importing the application.

The auditor checks package completeness, metadata, JSON Schemas, evaluation
contracts, and tool policies.  It intentionally parses the tool registry with
``ast`` so configuration errors can still be reported when the API cannot boot.

Usage:
    python Core-Agent/audit_skill_contracts.py
    python Core-Agent/audit_skill_contracts.py --json
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

REQUIRED_FILES = {
    "SKILL.md",
    "evals.yaml",
    "input.schema.json",
    "output.schema.json",
    "prompt.md",
    "tool-policy.yaml",
}
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
EVAL_ASSERTIONS = {"expected_concepts", "must_not_contain"}


@dataclass(frozen=True)
class AuditIssue:
    skill: str
    location: str
    message: str


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError("missing YAML frontmatter")
    parts = text.split("---", 2)
    if len(parts) != 3:
        raise ValueError("unterminated YAML frontmatter")
    value = yaml.safe_load(parts[1]) or {}
    if not isinstance(value, dict):
        raise TypeError("frontmatter must be a mapping")
    return value


def registered_tools(registry_path: Path) -> set[str]:
    """Return literal ToolSpec names registered in the application registry."""
    tree = ast.parse(registry_path.read_text(encoding="utf-8"), filename=str(registry_path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        function = node.func
        is_tool_spec = (
            isinstance(function, ast.Name) and function.id == "ToolSpec"
        ) or (
            isinstance(function, ast.Attribute) and function.attr == "ToolSpec"
        )
        if is_tool_spec and isinstance(node.args[0], ast.Constant):
            value = node.args[0].value
            if isinstance(value, str):
                names.add(value)
    return names


def _string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value)


def _nonempty_string_list(value: Any) -> bool:
    return bool(value) and _string_list(value)


def _issue(skill: str, location: str, message: str) -> AuditIssue:
    return AuditIssue(skill=skill, location=location, message=message)


def audit_skill(package: Path, known_tools: set[str]) -> list[AuditIssue]:
    skill = package.name
    issues: list[AuditIssue] = []
    present = {path.name for path in package.iterdir() if path.is_file()}
    for filename in sorted(REQUIRED_FILES - present):
        issues.append(_issue(skill, filename, "required file is missing"))
    if issues:
        return issues

    try:
        metadata = _frontmatter(package / "SKILL.md")
        if metadata.get("name") != skill:
            issues.append(_issue(skill, "SKILL.md", "frontmatter name must match directory name"))
        if not str(metadata.get("description", "")).strip():
            issues.append(_issue(skill, "SKILL.md", "description must not be empty"))
        extension = metadata.get("metadata")
        version = extension.get("version") if isinstance(extension, dict) else None
        if not isinstance(version, str) or not SEMVER.fullmatch(version):
            issues.append(_issue(skill, "SKILL.md", "metadata.version must be semantic versioning"))
    except (OSError, UnicodeError, yaml.YAMLError, TypeError, ValueError) as exc:
        issues.append(_issue(skill, "SKILL.md", str(exc)))

    if not (package / "prompt.md").read_text(encoding="utf-8").strip():
        issues.append(_issue(skill, "prompt.md", "prompt must not be empty"))

    for filename in ("input.schema.json", "output.schema.json"):
        try:
            schema = _load_json(package / filename)
            Draft202012Validator.check_schema(schema)
            if not isinstance(schema, dict) or schema.get("type") != "object":
                issues.append(_issue(skill, filename, "root schema type must be object"))
        except (OSError, UnicodeError, json.JSONDecodeError, SchemaError) as exc:
            issues.append(_issue(skill, filename, f"invalid JSON Schema: {exc}"))

    try:
        policy = _load_yaml(package / "tool-policy.yaml")
        if not isinstance(policy, dict):
            raise TypeError("policy must be a mapping")
        tools = policy.get("tools")
        approvals = policy.get("approval_required")
        if not _string_list(tools):
            issues.append(_issue(skill, "tool-policy.yaml", "tools must be a non-empty string list"))
            tools = []
        if not _string_list(approvals) and approvals != []:
            issues.append(_issue(skill, "tool-policy.yaml", "approval_required must be a string list"))
            approvals = []
        unknown = sorted(set(tools) - known_tools)
        if unknown:
            issues.append(_issue(skill, "tool-policy.yaml", f"unknown tools: {', '.join(unknown)}"))
        unapproved = sorted(set(approvals) - set(tools))
        if unapproved:
            issues.append(
                _issue(
                    skill,
                    "tool-policy.yaml",
                    f"approval_required tools are not allowed: {', '.join(unapproved)}",
                )
            )
    except (OSError, UnicodeError, yaml.YAMLError, TypeError, ValueError) as exc:
        issues.append(_issue(skill, "tool-policy.yaml", str(exc)))

    try:
        evals = _load_yaml(package / "evals.yaml")
        cases = evals.get("cases") if isinstance(evals, dict) else None
        if not isinstance(cases, list) or not cases:
            issues.append(_issue(skill, "evals.yaml", "cases must be a non-empty list"))
        else:
            names: set[str] = set()
            for index, case in enumerate(cases):
                location = f"evals.yaml:cases[{index}]"
                if not isinstance(case, dict):
                    issues.append(_issue(skill, location, "case must be a mapping"))
                    continue
                name = case.get("name")
                if not isinstance(name, str) or not name.strip():
                    issues.append(_issue(skill, location, "case name must not be empty"))
                elif name in names:
                    issues.append(_issue(skill, location, f"duplicate case name: {name}"))
                else:
                    names.add(name)
                if not isinstance(case.get("input"), str) or not case["input"].strip():
                    issues.append(_issue(skill, location, "case input must not be empty"))
                assertions = EVAL_ASSERTIONS & case.keys()
                if not assertions:
                    issues.append(_issue(skill, location, "case must define at least one assertion"))
                for assertion in assertions:
                    if not _nonempty_string_list(case[assertion]):
                        issues.append(_issue(skill, location, f"{assertion} must be a non-empty string list"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        issues.append(_issue(skill, "evals.yaml", str(exc)))

    return issues


def audit_repository(repo_root: Path) -> tuple[list[Path], list[AuditIssue]]:
    skills_root = repo_root / "services" / "api" / "app" / "skills"
    registry_path = repo_root / "services" / "api" / "app" / "agent" / "tools.py"
    packages = sorted(path for path in skills_root.iterdir() if path.is_dir())
    tools = registered_tools(registry_path)
    issues = [issue for package in packages for issue in audit_skill(package, tools)]
    return packages, issues


def _format_issues(issues: Iterable[AuditIssue]) -> str:
    return "\n".join(
        f"- {issue.skill}/{issue.location}: {issue.message}" for issue in issues
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit YYGlobal Skill package contracts")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="YYGlobal repository root",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    try:
        packages, issues = audit_repository(args.repo_root.resolve())
    except (OSError, SyntaxError, ValueError) as exc:
        print(f"ERROR: unable to audit repository: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(
            json.dumps(
                {
                    "status": "failed" if issues else "passed",
                    "skills_checked": len(packages),
                    "issue_count": len(issues),
                    "issues": [asdict(issue) for issue in issues],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif issues:
        print(f"FAIL: {len(issues)} Skill contract issue(s) found")
        print(_format_issues(issues))
    else:
        print(f"PASS: {len(packages)} Skill package contract(s) validated")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
