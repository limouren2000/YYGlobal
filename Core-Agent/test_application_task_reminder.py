"""Tests for the application task reminder."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from application_task_reminder import build_reminder_report, main


class ApplicationTaskReminderTests(unittest.TestCase):
    def test_reports_overdue_and_soon_tasks_in_date_order(self) -> None:
        report = build_reminder_report(
            {
                "tasks": [
                    {
                        "title": "Submit portfolio",
                        "due_date": "2026-08-14",
                        "status": "in_progress",
                    },
                    {
                        "title": "Request transcript",
                        "due_date": "2026-08-16",
                        "status": "pending",
                    },
                    {
                        "title": "Confirm referee",
                        "due_date": "2026-08-15",
                        "status": "blocked",
                    },
                ]
            },
            as_of=date(2026, 8, 16),
            within_days=7,
        )

        self.assertEqual(report["overdue_count"], 2)
        self.assertEqual(
            [task["title"] for task in report["overdue"]],
            ["Submit portfolio", "Confirm referee"],
        )
        self.assertEqual(report["due_soon"][0]["days_remaining"], 0)

    def test_excludes_completed_and_distant_tasks(self) -> None:
        report = build_reminder_report(
            {
                "tasks": [
                    {
                        "title": "Completed task",
                        "due_date": "2026-08-10",
                        "status": "completed",
                    },
                    {
                        "title": "Future task",
                        "due_date": "2026-09-01",
                        "status": "pending",
                    },
                ]
            },
            as_of=date(2026, 8, 16),
            within_days=7,
        )

        self.assertEqual(report["overdue"], [])
        self.assertEqual(report["due_soon"], [])

    def test_rejects_invalid_task_data(self) -> None:
        with self.assertRaisesRegex(ValueError, "due_date"):
            build_reminder_report(
                {
                    "tasks": [
                        {
                            "title": "Broken date",
                            "due_date": "16-08-2026",
                            "status": "pending",
                        }
                    ]
                },
                as_of=date(2026, 8, 16),
            )

    def test_cli_json_reports_overdue_tasks_with_exit_code_one(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "timeline.json"
            path.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "title": "Pay application fee",
                                "due_date": "2026-08-15",
                                "status": "pending",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [str(path), "--as-of", "2026-08-16", "--json"]
                )

        self.assertEqual(exit_code, 1)
        self.assertEqual(json.loads(stdout.getvalue())["overdue_count"], 1)


if __name__ == "__main__":
    unittest.main()
