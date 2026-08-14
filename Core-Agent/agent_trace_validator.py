#!/usr/bin/env python3
"""Validate a small, teaching-oriented Agent trace JSONL contract locally.

This utility is not YYGlobal's official trace schema. It only checks a compact,
framework-agnostic event shape that is useful for inspecting example traces.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


VALID_STATUSES = {"started", "success", "error", "denied", "cancelled"}
TERMINAL_EVENT_TYPES = {"agent_end", "run_completed"}
TERMINAL_STATUSES = {"success", "error", "denied", "cancelled"}
REQUIRED_FIELDS = ("trace_id", "step_id", "event_type", "status")


def non_empty_string(value: Any) -> bool:
    """Return whether value is a non-empty string after surrounding whitespace."""
    return isinstance(value, str) and bool(value.strip())


def validate_event(event: dict[str, Any], line_number: int) -> tuple[list[str], list[str]]:
    """Validate one event and return errors plus non-failing warnings."""
    errors: list[str] = []
    warnings: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in event:
            errors.append(f"line {line_number}: missing required field '{field}'")
        elif not non_empty_string(event[field]):
            errors.append(f"line {line_number}: {field} must be a non-empty string")

    status = event.get("status")
    if isinstance(status, str) and status not in VALID_STATUSES:
        errors.append(f"line {line_number}: invalid status {status!r}")

    if "parent_step_id" in event and not isinstance(event["parent_step_id"], str):
        errors.append(f"line {line_number}: parent_step_id must be a string")
    if "tool_name" in event and not non_empty_string(event["tool_name"]):
        errors.append(f"line {line_number}: tool_name must be a non-empty string")
    if "metadata" in event and not isinstance(event["metadata"], dict):
        errors.append(f"line {line_number}: metadata must be a JSON object")

    if "duration_ms" in event:
        duration = event["duration_ms"]
        if isinstance(duration, bool) or not isinstance(duration, (int, float)):
            errors.append(f"line {line_number}: duration_ms must be a number")
        elif not math.isfinite(duration) or duration < 0:
            errors.append(f"line {line_number}: duration_ms must be >= 0")

    if status == "error" and "error" not in event and "error_code" not in event:
        warnings.append(f"line {line_number}: error event has no error or error_code")
    return errors, warnings


def load_jsonl(path: Path) -> tuple[list[tuple[int, dict[str, Any]]], list[str], list[str]]:
    """Load non-empty JSONL objects while retaining their source line numbers."""
    events: list[tuple[int, dict[str, Any]]] = []
    errors: list[str] = []
    warnings: list[str] = []

    # ``utf-8-sig`` accepts regular UTF-8 and strips an optional BOM. Trace
    # exports from spreadsheet and Windows tooling commonly include one.
    with path.open(encoding="utf-8-sig") as trace_file:
        for line_number, raw_line in enumerate(trace_file, start=1):
            if not raw_line.strip():
                continue
            try:
                value = json.loads(raw_line)
            except json.JSONDecodeError as error:
                errors.append(f"line {line_number}: invalid JSON ({error.msg})")
                continue
            if not isinstance(value, dict):
                errors.append(f"line {line_number}: JSONL event must be a JSON object")
                continue
            event_errors, event_warnings = validate_event(value, line_number)
            errors.extend(event_errors)
            warnings.extend(event_warnings)
            events.append((line_number, value))
    return events, errors, warnings


def validate_traces(events: list[tuple[int, dict[str, Any]]]) -> list[str]:
    """Check per-trace step IDs, parent references, and explicit terminal events."""
    findings: list[str] = []
    traces: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for line_number, event in events:
        trace_id = event.get("trace_id")
        if non_empty_string(trace_id):
            traces[trace_id].append((line_number, event))

    for trace_id, trace_events in traces.items():
        step_ids: set[str] = set()
        terminal_seen = False
        for line_number, event in trace_events:
            step_id = event.get("step_id")
            if non_empty_string(step_id):
                if step_id in step_ids:
                    findings.append(f"trace {trace_id}: duplicate step_id {step_id!r}")
                step_ids.add(step_id)
            if terminal_seen:
                findings.append(f"line {line_number}: event appears after terminal event in trace {trace_id}")
            if (
                event.get("event_type") in TERMINAL_EVENT_TYPES
                and event.get("status") in TERMINAL_STATUSES
            ):
                terminal_seen = True

        for line_number, event in trace_events:
            parent_step_id = event.get("parent_step_id")
            if isinstance(parent_step_id, str) and parent_step_id not in step_ids:
                findings.append(
                    f"line {line_number}: parent_step_id {parent_step_id!r} is not in trace {trace_id}"
                )
    return findings


def validate_file(path: Path) -> tuple[int, int, list[str], list[str]]:
    """Return event count, trace count, errors, and warnings for a trace file."""
    events, errors, warnings = load_jsonl(path)
    if not events and not errors:
        errors.append("input file contains no trace events")
    errors.extend(validate_traces(events))
    trace_ids = {event["trace_id"] for _, event in events if non_empty_string(event.get("trace_id"))}
    return len(events), len(trace_ids), errors, warnings


def main(argv: list[str] | None = None) -> int:
    """Run the validator command-line interface."""
    parser = argparse.ArgumentParser(description="Validate a deterministic Agent trace JSONL file.")
    parser.add_argument("trace_file", type=Path, help="path to a UTF-8 JSONL trace file")
    args = parser.parse_args(argv)

    try:
        event_count, trace_count, errors, warnings = validate_file(args.trace_file)
    except (OSError, UnicodeError) as error:
        print(f"[ERROR] cannot read {args.trace_file}: {error}", file=sys.stderr)
        return 2

    for warning in warnings:
        print(f"[WARN] {warning}")
    if errors:
        print(f"[FAIL] {len(errors)} issue(s) found:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"[PASS] {event_count} events validated across {trace_count} traces")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
