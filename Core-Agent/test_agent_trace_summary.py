import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("agent_trace_summary.py")
SPEC = importlib.util.spec_from_file_location("agent_trace_summary", MODULE_PATH)
agent_trace_summary = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(agent_trace_summary)


class AgentTraceSummaryTests(unittest.TestCase):
    def write_trace(self, lines: list[object]) -> Path:
        handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
        self.addCleanup(Path(handle.name).unlink)
        with handle:
            for line in lines:
                handle.write(json.dumps(line))
                handle.write("\n")
        return Path(handle.name)

    def write_raw_trace(self, content: str) -> Path:
        handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
        self.addCleanup(Path(handle.name).unlink)
        with handle:
            handle.write(content)
        return Path(handle.name)

    def test_counts_traces_statuses_and_event_types(self) -> None:
        path = self.write_trace(
            [
                {"trace_id": "run-1", "status": "started", "event_type": "agent_start"},
                {"trace_id": "run-1", "status": "success", "event_type": "agent_end"},
                {"trace_id": "run-2", "status": "success", "event_type": "agent_end"},
            ]
        )

        self.assertEqual(
            agent_trace_summary.summarize_trace(path),
            {
                "event_count": 3,
                "trace_count": 2,
                "statuses": {"started": 1, "success": 2},
                "event_types": {"agent_end": 2, "agent_start": 1},
            },
        )

    def test_rejects_invalid_json(self) -> None:
        path = self.write_raw_trace('{"trace_id": "run-1"}\nnot-json\n')

        with self.assertRaisesRegex(ValueError, "line 2: invalid JSON"):
            agent_trace_summary.summarize_trace(path)

    def test_rejects_non_object_event(self) -> None:
        path = self.write_trace([["not", "an", "object"]])

        with self.assertRaisesRegex(ValueError, "line 1: JSONL event must be a JSON object"):
            agent_trace_summary.summarize_trace(path)
