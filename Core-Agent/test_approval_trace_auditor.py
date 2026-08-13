"""Tests for approval_trace_auditor."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from approval_trace_auditor import audit_events, audit_file, main


class ApprovalTraceAuditorTests(unittest.TestCase):
    def write_events(self, events: list[object]) -> Path:
        handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
        path = Path(handle.name)
        self.addCleanup(path.unlink)
        with handle:
            for event in events:
                handle.write(json.dumps(event) + "\n")
        return path

    def test_accepts_read_and_preapproved_write_calls(self) -> None:
        events = [
            (1, {"event_type": "tool_requested", "call_id": "r1", "tool_name": "search", "effect": "read"}),
            (2, {"event_type": "tool_executed", "call_id": "r1"}),
            (3, {"event_type": "tool_requested", "call_id": "w1", "tool_name": "send_email", "effect": "write"}),
            (4, {"event_type": "approval_decision", "approval_id": "a1", "call_id": "w1", "decision": "approved"}),
            (5, {"event_type": "tool_executed", "call_id": "w1"}),
        ]

        result = audit_events(events)

        self.assertTrue(result.ok)
        self.assertEqual((result.requested_count, result.executed_count), (2, 2))

    def test_rejects_write_execution_without_approval(self) -> None:
        result = audit_events([
            (1, {"event_type": "tool_requested", "call_id": "w1", "tool_name": "submit", "effect": "irreversible"}),
            (2, {"event_type": "tool_executed", "call_id": "w1"}),
        ])

        self.assertFalse(result.ok)
        self.assertIn("without prior approval", result.findings[0])

    def test_rejects_execution_after_denial(self) -> None:
        result = audit_events([
            (1, {"event_type": "tool_requested", "call_id": "w1", "tool_name": "pay", "effect": "write"}),
            (2, {"event_type": "approval_decision", "approval_id": "a1", "call_id": "w1", "decision": "denied"}),
            (3, {"event_type": "tool_executed", "call_id": "w1"}),
        ])

        self.assertTrue(any("decision: denied" in item for item in result.findings))

    def test_rejects_late_approval(self) -> None:
        result = audit_events([
            (1, {"event_type": "tool_requested", "call_id": "w1", "tool_name": "send", "effect": "write"}),
            (2, {"event_type": "tool_executed", "call_id": "w1"}),
            (3, {"event_type": "approval_decision", "approval_id": "a1", "call_id": "w1", "decision": "approved"}),
        ])

        self.assertTrue(any("without prior approval" in item for item in result.findings))

    def test_reports_unknown_references_and_duplicate_ids(self) -> None:
        result = audit_events([
            (1, {"event_type": "tool_executed", "call_id": "missing"}),
            (2, {"event_type": "approval_decision", "approval_id": "a1", "call_id": "missing", "decision": "approved"}),
            (3, {"event_type": "approval_decision", "approval_id": "a1", "call_id": "missing", "decision": "approved"}),
        ])

        joined = "\n".join(result.findings)
        self.assertIn("execution references unknown call", joined)
        self.assertIn("approval references unknown call", joined)
        self.assertIn("duplicate approval_id", joined)

    def test_invalid_json_is_a_finding(self) -> None:
        path = self.write_events([{"event_type": "tool_executed", "call_id": "x"}])
        path.write_text("not-json\n", encoding="utf-8")

        result = audit_file(path)

        self.assertFalse(result.ok)
        self.assertIn("invalid JSON", result.findings[0])

    def test_cli_json_output_and_exit_codes(self) -> None:
        path = self.write_events([
            {"event_type": "tool_requested", "call_id": "r1", "tool_name": "read", "effect": "read"},
            {"event_type": "tool_executed", "call_id": "r1"},
        ])
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            exit_code = main([str(path), "--json"])

        self.assertEqual(exit_code, 0)
        self.assertTrue(json.loads(output.getvalue())["ok"])


if __name__ == "__main__":
    unittest.main()
