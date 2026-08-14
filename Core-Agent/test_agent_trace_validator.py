"""Unit tests for the teaching-oriented Agent trace validator."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("agent_trace_validator.py")
SPEC = importlib.util.spec_from_file_location("agent_trace_validator", MODULE_PATH)
agent_trace_validator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(agent_trace_validator)


class AgentTraceValidatorTests(unittest.TestCase):
    def write_trace(self, events: list[object], encoding: str = "utf-8") -> Path:
        handle = tempfile.NamedTemporaryFile("w", encoding=encoding, delete=False)
        path = Path(handle.name)
        self.addCleanup(path.unlink)
        with handle:
            for event in events:
                handle.write(json.dumps(event))
                handle.write("\n")
        return path

    @staticmethod
    def valid_events() -> list[dict[str, object]]:
        return [
            {
                "trace_id": "run-1",
                "step_id": "step-1",
                "event_type": "agent_start",
                "status": "started",
            },
            {
                "trace_id": "run-1",
                "step_id": "step-2",
                "parent_step_id": "step-1",
                "event_type": "agent_end",
                "status": "success",
                "duration_ms": 12.5,
            },
        ]

    def test_accepts_valid_trace(self) -> None:
        path = self.write_trace(self.valid_events())

        self.assertEqual(
            agent_trace_validator.validate_file(path),
            (2, 1, [], []),
        )

    def test_accepts_utf8_bom_export(self) -> None:
        path = self.write_trace(self.valid_events(), encoding="utf-8-sig")

        event_count, trace_count, errors, warnings = (
            agent_trace_validator.validate_file(path)
        )

        self.assertEqual((event_count, trace_count), (2, 1))
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_reports_missing_parent_and_event_after_terminal(self) -> None:
        events = self.valid_events()
        events[1]["parent_step_id"] = "missing-step"
        events.append(
            {
                "trace_id": "run-1",
                "step_id": "step-3",
                "event_type": "tool_result",
                "status": "success",
            }
        )
        path = self.write_trace(events)

        _, _, errors, _ = agent_trace_validator.validate_file(path)

        self.assertTrue(any("event appears after terminal event" in error for error in errors))
        self.assertTrue(any("parent_step_id 'missing-step'" in error for error in errors))

    def test_rejects_invalid_duration(self) -> None:
        event = self.valid_events()[0]
        event["duration_ms"] = -1
        path = self.write_trace([event])

        _, _, errors, _ = agent_trace_validator.validate_file(path)

        self.assertIn("line 1: duration_ms must be >= 0", errors)

    def test_warns_when_error_event_has_no_details(self) -> None:
        event = self.valid_events()[0]
        event["status"] = "error"
        path = self.write_trace([event])

        _, _, errors, warnings = agent_trace_validator.validate_file(path)

        self.assertEqual(errors, [])
        self.assertEqual(
            warnings,
            ["line 1: error event has no error or error_code"],
        )


if __name__ == "__main__":
    unittest.main()
