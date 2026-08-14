#!/usr/bin/env python3
"""Audit an exported YYGlobal Agent run trace against execution budgets.

The input matches the JSON returned by ``GET /api/agent-runs/{run_id}/trace``.
Only the Python standard library is required.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BudgetLimits:
    """Execution limits used when auditing a trace."""

    max_steps: int = 8
    max_tool_calls: int = 12
    tool_timeout_ms: int = 30_000

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True)
class Finding:
    """One actionable budget or trace-integrity finding."""

    code: str
    message: str
    location: str


@dataclass(frozen=True)
class AuditResult:
    """Structured audit result returned by :func:`audit_trace`."""

    plan_step_count: int
    persisted_step_count: int
    tool_call_count: int
    findings: tuple[Finding, ...]

    @property
    def ok(self) -> bool:
        return not self.findings

    def to_dict(self, limits: BudgetLimits) -> dict[str, Any]:
        return {
            "status": "passed" if self.ok else "failed",
            "limits": asdict(limits),
            "counts": {
                "plan_steps": self.plan_step_count,
                "persisted_steps": self.persisted_step_count,
                "tool_calls": self.tool_call_count,
            },
            "issue_count": len(self.findings),
            "issues": [asdict(finding) for finding in self.findings],
        }


def _is_non_negative_number(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
        and value >= 0
    )


def _read_array(
    document: dict[str, Any],
    key: str,
    findings: list[Finding],
) -> list[Any]:
    value = document.get(key)
    if not isinstance(value, list):
        findings.append(
            Finding(
                f"invalid_{key}",
                f"{key} must be a JSON array",
                key,
            )
        )
        return []
    return value


def audit_trace(document: Any, limits: BudgetLimits | None = None) -> AuditResult:
    """Audit one parsed YYGlobal trace response.

    Counts are retained even when individual step or tool-call records are
    malformed so that malformed entries cannot hide a budget overrun.
    """

    limits = limits or BudgetLimits()
    findings: list[Finding] = []
    if not isinstance(document, dict):
        return AuditResult(
            0,
            0,
            0,
            (
                Finding(
                    "invalid_document",
                    "trace must be a JSON object",
                    "$",
                ),
            ),
        )

    run = document.get("run")
    plan: list[Any] = []
    if not isinstance(run, dict):
        findings.append(Finding("invalid_run", "run must be a JSON object", "run"))
    else:
        raw_plan = run.get("plan")
        if not isinstance(raw_plan, list):
            findings.append(
                Finding("invalid_plan", "run.plan must be a JSON array", "run.plan")
            )
        else:
            plan = raw_plan

        duration = run.get("duration_ms")
        if not _is_non_negative_number(duration):
            findings.append(
                Finding(
                    "invalid_run_duration",
                    "run.duration_ms must be a finite number greater than or equal to zero",
                    "run.duration_ms",
                )
            )

    steps = _read_array(document, "steps", findings)
    tool_calls = _read_array(document, "tool_calls", findings)

    if len(plan) > limits.max_steps:
        findings.append(
            Finding(
                "plan_step_budget_exceeded",
                f"plan has {len(plan)} steps; limit is {limits.max_steps}",
                "run.plan",
            )
        )
    if len(steps) > limits.max_steps:
        findings.append(
            Finding(
                "persisted_step_budget_exceeded",
                f"trace has {len(steps)} persisted steps; limit is {limits.max_steps}",
                "steps",
            )
        )
    if len(tool_calls) > limits.max_tool_calls:
        findings.append(
            Finding(
                "tool_call_budget_exceeded",
                f"trace has {len(tool_calls)} tool calls; limit is {limits.max_tool_calls}",
                "tool_calls",
            )
        )

    positions: dict[int, int] = {}
    for index, step in enumerate(steps):
        location = f"steps[{index}]"
        if not isinstance(step, dict):
            findings.append(
                Finding("invalid_step", "step must be a JSON object", location)
            )
            continue
        position = step.get("position")
        if isinstance(position, bool) or not isinstance(position, int) or position < 0:
            findings.append(
                Finding(
                    "invalid_step_position",
                    "position must be a non-negative integer",
                    f"{location}.position",
                )
            )
            continue
        previous_index = positions.get(position)
        if previous_index is not None:
            findings.append(
                Finding(
                    "duplicate_step_position",
                    f"position {position} is also used by steps[{previous_index}]",
                    f"{location}.position",
                )
            )
        else:
            positions[position] = index

    for index, call in enumerate(tool_calls):
        location = f"tool_calls[{index}]"
        if not isinstance(call, dict):
            findings.append(
                Finding("invalid_tool_call", "tool call must be a JSON object", location)
            )
            continue

        tool_name = call.get("tool_name")
        if not isinstance(tool_name, str) or not tool_name.strip():
            findings.append(
                Finding(
                    "invalid_tool_name",
                    "tool_name must be a non-empty string",
                    f"{location}.tool_name",
                )
            )

        duration = call.get("duration_ms")
        if not _is_non_negative_number(duration):
            findings.append(
                Finding(
                    "invalid_tool_duration",
                    "duration_ms must be a finite number greater than or equal to zero",
                    f"{location}.duration_ms",
                )
            )
        elif duration > limits.tool_timeout_ms:
            findings.append(
                Finding(
                    "tool_timeout_exceeded",
                    f"tool call took {duration:g} ms; limit is {limits.tool_timeout_ms} ms",
                    f"{location}.duration_ms",
                )
            )

    return AuditResult(len(plan), len(steps), len(tool_calls), tuple(findings))


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON: {error.msg}") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit an exported YYGlobal Agent run trace against execution budgets."
    )
    parser.add_argument("trace_file", type=Path, help="path to an exported trace JSON file")
    parser.add_argument("--max-steps", type=_positive_int, default=8)
    parser.add_argument("--max-tool-calls", type=_positive_int, default=12)
    parser.add_argument("--tool-timeout-seconds", type=_positive_int, default=30)
    parser.add_argument("--json", action="store_true", help="print structured JSON output")
    args = parser.parse_args(argv)

    limits = BudgetLimits(
        max_steps=args.max_steps,
        max_tool_calls=args.max_tool_calls,
        tool_timeout_ms=args.tool_timeout_seconds * 1000,
    )
    try:
        document = _load_json(args.trace_file)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"[ERROR] cannot read {args.trace_file}: {error}", file=sys.stderr)
        return 2

    result = audit_trace(document, limits)
    if args.json:
        print(json.dumps(result.to_dict(limits), ensure_ascii=False, indent=2))
    elif result.ok:
        print(
            "[PASS] Agent run stayed within budget "
            f"({result.persisted_step_count} steps, {result.tool_call_count} tool calls)"
        )
    else:
        print(f"[FAIL] {len(result.findings)} issue(s) found:")
        for finding in result.findings:
            print(f"  - [{finding.code}] {finding.location}: {finding.message}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
