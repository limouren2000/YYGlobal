"""Validate dependencies, dates, and states in an application task timeline.

The input is a JSON object containing a ``tasks`` array. This module only uses
the Python standard library and can be imported or run as a command-line tool.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

VALID_STATUSES = frozenset({"pending", "in_progress", "completed", "blocked"})


@dataclass(frozen=True)
class Finding:
    """One actionable timeline validation finding."""

    code: str
    message: str
    task_id: str | None = None


@dataclass(frozen=True)
class ValidationResult:
    """Structured result returned by :func:`validate_timeline`."""

    task_count: int
    findings: tuple[Finding, ...]

    @property
    def ok(self) -> bool:
        return not self.findings


@dataclass(frozen=True)
class _Task:
    task_id: str
    deadline: date | None
    status: str | None
    dependencies: tuple[str, ...] | None


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
    return parsed if parsed.isoformat() == value else None


def _find_cycles(tasks: dict[str, _Task]) -> list[tuple[str, ...]]:
    graph = {
        task_id: tuple(
            dependency
            for dependency in (task.dependencies or ())
            if dependency in tasks and dependency != task_id
        )
        for task_id, task in tasks.items()
    }
    state: dict[str, int] = {}
    cycles: list[tuple[str, ...]] = []
    seen: set[frozenset[str]] = set()

    for root in graph:
        if state.get(root, 0) != 0:
            continue
        path: list[str] = [root]
        path_indexes = {root: 0}
        frames: list[tuple[str, int]] = [(root, 0)]
        state[root] = 1

        while frames:
            task_id, dependency_index = frames[-1]
            dependencies = graph[task_id]
            if dependency_index >= len(dependencies):
                frames.pop()
                path_indexes.pop(task_id)
                path.pop()
                state[task_id] = 2
                continue

            dependency = dependencies[dependency_index]
            frames[-1] = (task_id, dependency_index + 1)
            dependency_state = state.get(dependency, 0)
            if dependency_state == 0:
                state[dependency] = 1
                path_indexes[dependency] = len(path)
                path.append(dependency)
                frames.append((dependency, 0))
            elif dependency_state == 1:
                start = path_indexes[dependency]
                cycle = tuple(path[start:] + [dependency])
                signature = frozenset(cycle[:-1])
                if signature not in seen:
                    seen.add(signature)
                    cycles.append(cycle)
    return cycles


def validate_timeline(document: Any, *, as_of: date) -> ValidationResult:
    """Validate a parsed timeline document and return all detected findings."""
    if not isinstance(document, dict) or not isinstance(document.get("tasks"), list):
        return ValidationResult(
            task_count=0,
            findings=(
                Finding(
                    "invalid_document",
                    "timeline must be an object containing a tasks array",
                ),
            ),
        )

    raw_tasks = document["tasks"]
    findings: list[Finding] = []
    parsed_tasks: list[_Task] = []
    id_counts: dict[str, int] = {}

    for index, raw_task in enumerate(raw_tasks):
        if not isinstance(raw_task, dict):
            findings.append(
                Finding("invalid_task", f"tasks[{index}] must be an object")
            )
            continue

        raw_id = raw_task.get("id")
        task_id = raw_id.strip() if isinstance(raw_id, str) else ""
        if not task_id:
            findings.append(
                Finding("invalid_task_id", f"tasks[{index}].id must be non-empty")
            )
        else:
            id_counts[task_id] = id_counts.get(task_id, 0) + 1

        deadline = _parse_date(raw_task.get("deadline"))
        if deadline is None:
            findings.append(
                Finding(
                    "invalid_deadline",
                    "deadline must be a valid date in YYYY-MM-DD format",
                    task_id or None,
                )
            )

        raw_status = raw_task.get("status")
        status = raw_status if isinstance(raw_status, str) else None
        if status not in VALID_STATUSES:
            findings.append(
                Finding(
                    "invalid_status",
                    "status must be pending, in_progress, completed, or blocked",
                    task_id or None,
                )
            )

        raw_dependencies = raw_task.get("depends_on", [])
        dependencies: tuple[str, ...] | None = None
        if not isinstance(raw_dependencies, list) or any(
            not isinstance(item, str) or not item.strip() for item in raw_dependencies
        ):
            findings.append(
                Finding(
                    "invalid_dependencies",
                    "depends_on must be an array of non-empty task IDs",
                    task_id or None,
                )
            )
        else:
            dependencies = tuple(item.strip() for item in raw_dependencies)
            if len(set(dependencies)) != len(dependencies):
                findings.append(
                    Finding(
                        "duplicate_dependency",
                        "depends_on must not contain duplicate task IDs",
                        task_id or None,
                    )
                )

        parsed_tasks.append(_Task(task_id, deadline, status, dependencies))

    duplicate_ids = {
        task_id for task_id, count in id_counts.items() if count > 1
    }
    for task_id in sorted(duplicate_ids):
        findings.append(
            Finding("duplicate_task_id", f"task ID {task_id!r} is duplicated", task_id)
        )

    tasks = {
        task.task_id: task
        for task in parsed_tasks
        if task.task_id and task.task_id not in duplicate_ids
    }

    for task in tasks.values():
        if task.dependencies is None:
            continue
        unique_dependencies = dict.fromkeys(task.dependencies)
        for dependency in unique_dependencies:
            if dependency == task.task_id:
                findings.append(
                    Finding(
                        "self_dependency",
                        "a task cannot depend on itself",
                        task.task_id,
                    )
                )
            elif dependency not in tasks:
                findings.append(
                    Finding(
                        "unknown_dependency",
                        f"dependency {dependency!r} does not reference "
                        "an existing task",
                        task.task_id,
                    )
                )

    for cycle in _find_cycles(tasks):
        findings.append(
            Finding(
                "dependency_cycle",
                f"dependency cycle detected: {' -> '.join(cycle)}",
                cycle[0],
            )
        )

    for task in tasks.values():
        if task.dependencies is None:
            continue
        for dependency_id in dict.fromkeys(task.dependencies):
            dependency = tasks.get(dependency_id)
            if dependency is None or dependency_id == task.task_id:
                continue
            if (
                task.deadline is not None
                and dependency.deadline is not None
                and dependency.deadline > task.deadline
            ):
                findings.append(
                    Finding(
                        "deadline_order",
                        f"dependency {dependency_id!r} is due after this task",
                        task.task_id,
                    )
                )
            if task.status == "completed" and dependency.status != "completed":
                findings.append(
                    Finding(
                        "completed_with_incomplete_dependency",
                        f"completed task depends on incomplete task {dependency_id!r}",
                        task.task_id,
                    )
                )

    for task in tasks.values():
        if (
            task.deadline is not None
            and task.deadline < as_of
            and task.status != "completed"
        ):
            findings.append(
                Finding(
                    "overdue_task",
                    "task deadline "
                    f"{task.deadline.isoformat()} is before {as_of.isoformat()}",
                    task.task_id,
                )
            )

    return ValidationResult(task_count=len(raw_tasks), findings=tuple(findings))


def _parse_as_of(value: str) -> date:
    parsed = _parse_date(value)
    if parsed is None:
        raise ValueError("--as-of must be a valid date in YYYY-MM-DD format")
    return parsed


def _result_payload(result: ValidationResult, as_of: date) -> dict[str, object]:
    return {
        "ok": result.ok,
        "as_of": as_of.isoformat(),
        "task_count": result.task_count,
        "findings": [asdict(finding) for finding in result.findings],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate an application task timeline and its dependencies."
    )
    parser.add_argument("timeline", type=Path, help="path to the timeline JSON file")
    parser.add_argument(
        "--as-of",
        default=date.today().isoformat(),
        help="date used to detect overdue tasks (default: today)",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON output")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    try:
        as_of = _parse_as_of(args.as_of)
        document = json.loads(args.timeline.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    result = validate_timeline(document, as_of=as_of)
    if args.json:
        print(json.dumps(_result_payload(result, as_of), indent=2, ensure_ascii=False))
    elif result.ok:
        print(f"[PASS] {result.task_count} timeline task(s) are valid")
    else:
        print(f"[FAIL] {len(result.findings)} finding(s) in the application timeline")
        for finding in result.findings:
            location = f" [{finding.task_id}]" if finding.task_id else ""
            print(f"  - {finding.code}{location}: {finding.message}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
