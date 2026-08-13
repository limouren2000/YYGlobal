#!/usr/bin/env python3
"""Audit whether risky Agent tool calls were approved before execution.

The input is a JSONL event stream with three event types:

* ``tool_requested``: call_id, tool_name, effect (read/write/irreversible)
* ``approval_decision``: approval_id, call_id, decision (approved/denied)
* ``tool_executed``: call_id

The format is intentionally framework-independent so exported traces can be
checked locally or in CI without access to production services.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


EVENT_TYPES = {"tool_requested", "approval_decision", "tool_executed"}
EFFECTS = {"read", "write", "irreversible"}
DECISIONS = {"approved", "denied"}
APPROVAL_REQUIRED = {"write", "irreversible"}


@dataclass(frozen=True)
class AuditResult:
    """Structured result for callers and JSON output."""

    event_count: int
    requested_count: int
    executed_count: int
    findings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.findings

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "event_count": self.event_count,
            "requested_count": self.requested_count,
            "executed_count": self.executed_count,
            "findings": list(self.findings),
        }


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def load_jsonl(path: Path) -> tuple[list[tuple[int, dict[str, Any]]], list[str]]:
    """Load JSON objects while preserving line numbers and parse findings."""
    events: list[tuple[int, dict[str, Any]]] = []
    findings: list[str] = []
    with path.open(encoding="utf-8-sig") as handle:
        for line_number, raw_line in enumerate(handle, 1):
            if not raw_line.strip():
                continue
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError as error:
                findings.append(f"line {line_number}: invalid JSON ({error.msg})")
                continue
            if not isinstance(event, dict):
                findings.append(f"line {line_number}: event must be a JSON object")
                continue
            events.append((line_number, event))
    return events, findings


def audit_events(
    events: Iterable[tuple[int, dict[str, Any]]],
    initial_findings: Iterable[str] = (),
) -> AuditResult:
    """Audit ordering, references, and approval requirements in an event stream."""
    findings = list(initial_findings)
    requests: dict[str, tuple[str, str]] = {}
    decisions: dict[str, str] = {}
    approval_ids: set[str] = set()
    executed: set[str] = set()
    event_count = 0

    for line_number, event in events:
        event_count += 1
        event_type = _text(event.get("event_type"))
        if event_type not in EVENT_TYPES:
            findings.append(f"line {line_number}: invalid event_type {event_type!r}")
            continue

        call_id = _text(event.get("call_id"))
        if call_id is None:
            findings.append(f"line {line_number}: call_id must be a non-empty string")
            continue

        if event_type == "tool_requested":
            tool_name = _text(event.get("tool_name"))
            effect = _text(event.get("effect"))
            if tool_name is None:
                findings.append(f"line {line_number}: tool_name must be a non-empty string")
            if effect not in EFFECTS:
                findings.append(f"line {line_number}: invalid effect {effect!r}")
            if call_id in requests:
                findings.append(f"line {line_number}: duplicate call_id {call_id!r}")
            elif tool_name is not None and effect in EFFECTS:
                requests[call_id] = (tool_name, effect)

        elif event_type == "approval_decision":
            approval_id = _text(event.get("approval_id"))
            decision = _text(event.get("decision"))
            if approval_id is None:
                findings.append(f"line {line_number}: approval_id must be a non-empty string")
            elif approval_id in approval_ids:
                findings.append(f"line {line_number}: duplicate approval_id {approval_id!r}")
            else:
                approval_ids.add(approval_id)
            if call_id not in requests:
                findings.append(f"line {line_number}: approval references unknown call {call_id!r}")
            if decision not in DECISIONS:
                findings.append(f"line {line_number}: invalid decision {decision!r}")
            elif call_id in decisions:
                findings.append(f"line {line_number}: call {call_id!r} already has a decision")
            elif call_id in requests:
                decisions[call_id] = decision

        else:
            if call_id not in requests:
                findings.append(f"line {line_number}: execution references unknown call {call_id!r}")
                continue
            if call_id in executed:
                findings.append(f"line {line_number}: call {call_id!r} was executed more than once")
                continue
            executed.add(call_id)
            tool_name, effect = requests[call_id]
            if effect in APPROVAL_REQUIRED and decisions.get(call_id) != "approved":
                decision = decisions.get(call_id, "missing")
                findings.append(
                    f"line {line_number}: {effect} tool {tool_name!r} executed "
                    f"without prior approval (decision: {decision})"
                )

    return AuditResult(
        event_count=event_count,
        requested_count=len(requests),
        executed_count=len(executed),
        findings=tuple(findings),
    )


def audit_file(path: Path) -> AuditResult:
    events, findings = load_jsonl(path)
    if not events and not findings:
        findings.append("input file contains no events")
    return audit_events(events, findings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit approval ordering for risky Agent tool calls."
    )
    parser.add_argument("trace_file", type=Path, help="UTF-8 JSONL event stream")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    try:
        result = audit_file(args.trace_file)
    except (OSError, UnicodeError) as error:
        print(f"[ERROR] cannot read {args.trace_file}: {error}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    elif result.ok:
        print(
            f"[PASS] {result.executed_count} execution(s) audited across "
            f"{result.requested_count} request(s)"
        )
    else:
        print(f"[FAIL] {len(result.findings)} issue(s) found:")
        for finding in result.findings:
            print(f"  - {finding}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
