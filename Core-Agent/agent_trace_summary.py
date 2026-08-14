#!/usr/bin/env python3
"""Summarize JSONL Agent trace events with only the Python standard library.

Usage:
    python Core-Agent/agent_trace_summary.py path/to/trace.jsonl
    python Core-Agent/agent_trace_summary.py path/to/trace.jsonl --json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def summarize_trace(path: Path) -> dict[str, Any]:
    """Return event, trace, status, and event-type counts for a JSONL trace."""
    statuses: Counter[str] = Counter()
    event_types: Counter[str] = Counter()
    trace_ids: set[str] = set()
    event_count = 0

    with path.open(encoding="utf-8-sig") as trace_file:
        for line_number, raw_line in enumerate(trace_file, start=1):
            if not raw_line.strip():
                continue
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError as error:
                raise ValueError(f"line {line_number}: invalid JSON ({error.msg})") from error
            if not isinstance(event, dict):
                raise ValueError(f"line {line_number}: JSONL event must be a JSON object")

            event_count += 1
            trace_id = event.get("trace_id")
            if isinstance(trace_id, str) and trace_id.strip():
                trace_ids.add(trace_id)
            status = event.get("status")
            if isinstance(status, str) and status.strip():
                statuses[status] += 1
            event_type = event.get("event_type")
            if isinstance(event_type, str) and event_type.strip():
                event_types[event_type] += 1

    return {
        "event_count": event_count,
        "trace_count": len(trace_ids),
        "statuses": dict(sorted(statuses.items())),
        "event_types": dict(sorted(event_types.items())),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize a JSONL Agent trace file.")
    parser.add_argument("trace_file", type=Path, help="path to a UTF-8 JSONL trace file")
    parser.add_argument("--json", action="store_true", help="print JSON output")
    args = parser.parse_args(argv)

    try:
        summary = summarize_trace(args.trace_file)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"[ERROR] cannot summarize {args.trace_file}: {error}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Events: {summary['event_count']}")
        print(f"Traces: {summary['trace_count']}")
        print(f"Statuses: {summary['statuses']}")
        print(f"Event types: {summary['event_types']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
