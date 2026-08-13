"""Validate structured handoff records passed between Agents.

A handoff records who owns the next step, what was completed, what remains,
and the evidence or decision that makes the handoff safe to continue. Keeping
this contract small makes it usable by Agents, CI checks, and other automation.

Usage:
    python Core-Agent/agent_handoff_validator.py handoff.json
    python Core-Agent/agent_handoff_validator.py handoff.json --json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


REQUIRED_NONEMPTY_STRINGS = ("handoff_id", "from_agent", "to_agent", "summary")
LIST_FIELDS = ("completed", "next_steps", "evidence", "risks")


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    message: str


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_handoff(record: Any) -> list[ValidationIssue]:
    """Return contract violations for one handoff object."""
    if not isinstance(record, dict):
        return [ValidationIssue("$", "handoff must be a JSON object")]

    issues: list[ValidationIssue] = []
    for field in REQUIRED_NONEMPTY_STRINGS:
        if not _is_nonempty_string(record.get(field)):
            issues.append(ValidationIssue(field, "must be a non-empty string"))

    if record.get("from_agent") == record.get("to_agent") and _is_nonempty_string(
        record.get("from_agent")
    ):
        issues.append(ValidationIssue("to_agent", "must name a different Agent than from_agent"))

    for field in LIST_FIELDS:
        value = record.get(field, [])
        if not isinstance(value, list):
            issues.append(ValidationIssue(field, "must be an array"))
        elif any(not _is_nonempty_string(item) for item in value):
            issues.append(ValidationIssue(field, "must contain only non-empty strings"))

    next_steps = record.get("next_steps")
    if isinstance(next_steps, list) and not next_steps:
        issues.append(ValidationIssue("next_steps", "must contain at least one actionable next step"))

    status = record.get("status")
    if status not in {"ready", "blocked"}:
        issues.append(ValidationIssue("status", "must be either 'ready' or 'blocked'"))
    elif status == "blocked":
        risks = record.get("risks")
        if not isinstance(risks, list) or not risks:
            issues.append(ValidationIssue("risks", "must describe the blocker when status is 'blocked'"))

    return issues


def load_handoff(path: Path) -> Any:
    """Read one UTF-8 JSON handoff record from *path*."""
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an Agent handoff JSON record")
    parser.add_argument("handoff", type=Path, help="path to a JSON handoff record")
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    args = parser.parse_args(argv)

    try:
        record = load_handoff(args.handoff)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: unable to read handoff: {exc}", file=sys.stderr)
        return 2

    issues = validate_handoff(record)
    if args.json:
        print(
            json.dumps(
                {
                    "status": "failed" if issues else "passed",
                    "issue_count": len(issues),
                    "issues": [asdict(issue) for issue in issues],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif issues:
        print(f"FAIL: {len(issues)} handoff validation issue(s) found")
        for issue in issues:
            print(f"- {issue.field}: {issue.message}")
    else:
        print("PASS: handoff record is ready for the receiving Agent")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
