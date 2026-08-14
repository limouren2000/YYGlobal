"""Tests for the YYGlobal Agent run budget auditor."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_run_budget_auditor import BudgetLimits, audit_trace, main


def valid_trace() -> dict:
    return {
        "run": {
            "id": "run-1",
            "status": "completed",
            "plan": [{"name": "plan"}, {"name": "execute"}],
            "duration_ms": 1500,
        },
        "steps": [
            {"id": "step-1", "position": 0, "status": "completed"},
            {"id": "step-2", "position": 1, "status": "completed"},
        ],
        "tool_calls": [
            {"id": "call-1", "tool_name": "search_programs", "duration_ms": 250}
        ],
    }


class BudgetLimitsTests(unittest.TestCase):
    def test_rejects_non_positive_limits(self) -> None:
        with self.assertRaises(ValueError):
            BudgetLimits(max_steps=0)


class AuditTraceTests(unittest.TestCase):
    def test_accepts_trace_within_budget(self) -> None:
        result = audit_trace(valid_trace())
        self.assertTrue(result.ok)
        self.assertEqual(result.plan_step_count, 2)
        self.assertEqual(result.persisted_step_count, 2)
        self.assertEqual(result.tool_call_count, 1)

    def test_rejects_non_object_document(self) -> None:
        result = audit_trace([])
        self.assertEqual([item.code for item in result.findings], ["invalid_document"])

    def test_checks_plan_and_persisted_step_budgets_separately(self) -> None:
        trace = valid_trace()
        trace["run"]["plan"] = [{"name": str(index)} for index in range(4)]
        trace["steps"] = [
            {"id": str(index), "position": index, "status": "completed"}
            for index in range(3)
        ]
        result = audit_trace(trace, BudgetLimits(max_steps=2))
        self.assertEqual(
            {item.code for item in result.findings},
            {"plan_step_budget_exceeded", "persisted_step_budget_exceeded"},
        )

    def test_counts_malformed_tool_calls_toward_budget(self) -> None:
        trace = valid_trace()
        trace["tool_calls"] = [None, None]
        result = audit_trace(trace, BudgetLimits(max_tool_calls=1))
        codes = [item.code for item in result.findings]
        self.assertIn("tool_call_budget_exceeded", codes)
        self.assertEqual(codes.count("invalid_tool_call"), 2)

    def test_reports_tool_timeout(self) -> None:
        trace = valid_trace()
        trace["tool_calls"][0]["duration_ms"] = 30_001
        result = audit_trace(trace)
        self.assertEqual([item.code for item in result.findings], ["tool_timeout_exceeded"])

    def test_rejects_boolean_and_non_finite_durations(self) -> None:
        trace = valid_trace()
        trace["run"]["duration_ms"] = True
        trace["tool_calls"][0]["duration_ms"] = float("nan")
        result = audit_trace(trace)
        self.assertEqual(
            {item.code for item in result.findings},
            {"invalid_run_duration", "invalid_tool_duration"},
        )

    def test_reports_duplicate_step_positions(self) -> None:
        trace = valid_trace()
        trace["steps"][1]["position"] = 0
        result = audit_trace(trace)
        self.assertEqual(
            [item.code for item in result.findings],
            ["duplicate_step_position"],
        )

    def test_structured_result_contains_limits_counts_and_locations(self) -> None:
        trace = valid_trace()
        trace["tool_calls"][0]["duration_ms"] = 500
        limits = BudgetLimits(tool_timeout_ms=100)
        payload = audit_trace(trace, limits).to_dict(limits)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["counts"]["tool_calls"], 1)
        self.assertEqual(payload["issues"][0]["location"], "tool_calls[0].duration_ms")


class CommandLineTests(unittest.TestCase):
    def test_cli_json_output_and_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.json"
            path.write_text(json.dumps(valid_trace()), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main([str(path), "--json"])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())["status"], "passed")

            with contextlib.redirect_stdout(io.StringIO()):
                code = main([str(path), "--max-tool-calls", "1", "--tool-timeout-seconds", "1"])
            self.assertEqual(code, 0)

    def test_cli_returns_two_for_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.json"
            path.write_text("not-json", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                code = main([str(path)])
            self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
