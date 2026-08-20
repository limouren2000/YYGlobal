"""Report overdue and soon-due tasks from an application-timeline result.

The input is a JSON object produced by the application-timeline Skill. Each
task must have a title, due_date (YYYY-MM-DD), and status.

Examples:
    python Core-Agent/application_task_reminder.py timeline.json
    python Core-Agent/application_task_reminder.py timeline.json --as-of 2026-08-16
    python Core-Agent/application_task_reminder.py timeline.json --within-days 7 --json

Exit codes: 0 when no task is overdue, 1 when overdue tasks need attention,
and 2 for unreadable or invalid input.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DueTask:
    """One incomplete task that needs attention."""

    title: str
    due_date: str
    status: str
    days_remaining: int


def parse_iso_date(value: object, field: str) -> date:
    """Parse an exact YYYY-MM-DD date."""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a YYYY-MM-DD string")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid YYYY-MM-DD date") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{field} must be a valid YYYY-MM-DD date")
    return parsed


def build_reminder_report(
    document: Any, *, as_of: date, within_days: int = 14
) -> dict[str, object]:
    """Return incomplete tasks that are overdue or due within the given window."""
    if isinstance(within_days, bool) or not isinstance(within_days, int):
        raise ValueError("within_days must be an integer")
    if within_days < 0:
        raise ValueError("within_days must be non-negative")
    if not isinstance(document, dict) or not isinstance(document.get("tasks"), list):
        raise ValueError("timeline must be an object containing a tasks array")

    overdue: list[DueTask] = []
    due_soon: list[DueTask] = []
    for index, task in enumerate(document["tasks"]):
        if not isinstance(task, dict):
            raise ValueError(f"tasks[{index}] must be an object")

        raw_title = task.get("title")
        title = raw_title.strip() if isinstance(raw_title, str) else ""
        if not title:
            raise ValueError(f"tasks[{index}].title must be non-empty")

        raw_status = task.get("status")
        status = raw_status.strip() if isinstance(raw_status, str) else ""
        if not status:
            raise ValueError(f"tasks[{index}].status must be non-empty")
        if status.lower() == "completed":
            continue

        due = parse_iso_date(task.get("due_date"), f"tasks[{index}].due_date")
        due_task = DueTask(
            title=title,
            due_date=due.isoformat(),
            status=status,
            days_remaining=(due - as_of).days,
        )
        if due_task.days_remaining < 0:
            overdue.append(due_task)
        elif due_task.days_remaining <= within_days:
            due_soon.append(due_task)

    order_key = lambda task: (task.due_date, task.title.casefold())
    overdue.sort(key=order_key)
    due_soon.sort(key=order_key)
    return {
        "as_of": as_of.isoformat(),
        "within_days": within_days,
        "overdue": [asdict(task) for task in overdue],
        "due_soon": [asdict(task) for task in due_soon],
        "overdue_count": len(overdue),
        "due_soon_count": len(due_soon),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report overdue and soon-due application timeline tasks."
    )
    parser.add_argument("input", type=Path, help="application-timeline JSON file")
    parser.add_argument(
        "--as-of",
        default=date.today().isoformat(),
        help="reference date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--within-days",
        type=int,
        default=14,
        help="include incomplete tasks due within this many days (default: 14)",
    )
    parser.add_argument("--json", action="store_true", help="print JSON output")
    return parser.parse_args(argv)


def print_text_report(report: dict[str, object]) -> None:
    """Print a concise human-readable report."""
    overdue = report["overdue"]
    due_soon = report["due_soon"]
    if not overdue and not due_soon:
        print("No incomplete tasks are overdue or due soon.")
        return

    if overdue:
        print("Overdue:")
        for task in overdue:
            print(f"  - {task['title']} (due {task['due_date']})")
    if due_soon:
        print(f"Due within {report['within_days']} days:")
        for task in due_soon:
            print(
                f"  - {task['title']} "
                f"(due {task['due_date']}, {task['days_remaining']} days remaining)"
            )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        document = json.loads(args.input.read_text(encoding="utf-8"))
        as_of = parse_iso_date(args.as_of, "--as-of")
        report = build_reminder_report(
            document, as_of=as_of, within_days=args.within_days
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text_report(report)
    return 1 if report["overdue_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
