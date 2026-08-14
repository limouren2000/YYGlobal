"""Tests for the framework-independent application timeline validator."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import application_timeline_validator as validator
except ModuleNotFoundError:
    validator = None

main = getattr(validator, "main", None)
validate_timeline = getattr(validator, "validate_timeline", None)


AS_OF = date(2026, 8, 13)


def valid_timeline() -> dict[str, object]:
    return {
        "tasks": [
            {
                "id": "language_test",
                "deadline": "2026-09-01",
                "status": "completed",
                "depends_on": [],
            },
            {
                "id": "submit_application",
                "deadline": "2026-12-01",
                "status": "pending",
                "depends_on": ["language_test"],
            },
        ]
    }


class ApplicationTimelineValidatorTests(unittest.TestCase):
    def test_accepts_valid_timeline(self) -> None:
        self.assertIsNotNone(validate_timeline, "validator module must exist")

        result = validate_timeline(valid_timeline(), as_of=AS_OF)

        self.assertTrue(result.ok)
        self.assertEqual(result.findings, ())
        self.assertEqual(result.task_count, 2)

    def test_reports_document_and_task_contract_errors(self) -> None:
        invalid_tasks = {
            "tasks": [
                {
                    "id": "essay",
                    "deadline": "2026-02-30",
                    "status": "started",
                    "depends_on": "research",
                },
                {
                    "id": "essay",
                    "deadline": "2026-10-01",
                    "status": "pending",
                    "depends_on": [],
                },
            ]
        }

        result = validate_timeline(invalid_tasks, as_of=AS_OF)

        self.assertEqual(
            {finding.code for finding in result.findings},
            {
                "duplicate_task_id",
                "invalid_deadline",
                "invalid_status",
                "invalid_dependencies",
            },
        )
        self.assertEqual(
            [item.code for item in validate_timeline([], as_of=AS_OF).findings],
            ["invalid_document"],
        )

    def test_reports_invalid_dependency_references(self) -> None:
        timeline = {
            "tasks": [
                {
                    "id": "submit",
                    "deadline": "2026-12-01",
                    "status": "pending",
                    "depends_on": ["submit", "missing", "missing"],
                }
            ]
        }

        result = validate_timeline(timeline, as_of=AS_OF)

        self.assertEqual(
            [finding.code for finding in result.findings],
            ["duplicate_dependency", "self_dependency", "unknown_dependency"],
        )

    def test_detects_indirect_dependency_cycle(self) -> None:
        timeline = {
            "tasks": [
                {
                    "id": "a",
                    "deadline": "2026-10-01",
                    "status": "pending",
                    "depends_on": ["c"],
                },
                {
                    "id": "b",
                    "deadline": "2026-10-01",
                    "status": "pending",
                    "depends_on": ["a"],
                },
                {
                    "id": "c",
                    "deadline": "2026-10-01",
                    "status": "pending",
                    "depends_on": ["b"],
                },
            ]
        }

        result = validate_timeline(timeline, as_of=AS_OF)

        cycles = [item for item in result.findings if item.code == "dependency_cycle"]
        self.assertEqual(len(cycles), 1)
        self.assertIn("a -> c -> b -> a", cycles[0].message)

    def test_accepts_deep_dependency_chain_without_recursion_failure(self) -> None:
        task_count = 1_100
        timeline = {
            "tasks": [
                {
                    "id": f"task-{index}",
                    "deadline": "2026-12-01",
                    "status": "pending",
                    "depends_on": [f"task-{index + 1}"]
                    if index + 1 < task_count
                    else [],
                }
                for index in range(task_count)
            ]
        }

        result = validate_timeline(timeline, as_of=AS_OF)

        self.assertTrue(result.ok)
        self.assertEqual(result.task_count, task_count)

    def test_reports_temporal_and_status_conflicts(self) -> None:
        timeline = {
            "tasks": [
                {
                    "id": "recommendation",
                    "deadline": "2026-12-15",
                    "status": "pending",
                    "depends_on": [],
                },
                {
                    "id": "submit",
                    "deadline": "2026-12-01",
                    "status": "completed",
                    "depends_on": ["recommendation"],
                },
                {
                    "id": "overdue_essay",
                    "deadline": "2026-08-12",
                    "status": "in_progress",
                    "depends_on": [],
                },
            ]
        }

        result = validate_timeline(timeline, as_of=AS_OF)

        self.assertEqual(
            [finding.code for finding in result.findings],
            [
                "deadline_order",
                "completed_with_incomplete_dependency",
                "overdue_task",
            ],
        )

    def test_cli_emits_json_and_documented_exit_codes(self) -> None:
        self.assertIsNotNone(main, "validator CLI must exist")
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            json.dump(valid_timeline(), handle)
            timeline_path = Path(handle.name)
        self.addCleanup(timeline_path.unlink)
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            exit_code = main(
                [str(timeline_path), "--as-of", AS_OF.isoformat(), "--json"]
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["task_count"], 2)

        invalid_timeline = valid_timeline()
        invalid_timeline["tasks"][1]["depends_on"] = ["missing"]
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            json.dump(invalid_timeline, handle)
            invalid_timeline_path = Path(handle.name)
        self.addCleanup(invalid_timeline_path.unlink)

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main([str(invalid_timeline_path)]), 1)

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write("not-json")
            invalid_path = Path(handle.name)
        self.addCleanup(invalid_path.unlink)

        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main([str(invalid_path)]), 2)
            self.assertEqual(main([str(timeline_path), "--as-of", "yesterday"]), 2)


if __name__ == "__main__":
    unittest.main()
