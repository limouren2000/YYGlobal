"""Regression tests for the standalone Agent trace redactor."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("agent_trace_redactor.py")
SPEC = importlib.util.spec_from_file_location("agent_trace_redactor", MODULE_PATH)
assert SPEC and SPEC.loader
REDACTOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = REDACTOR
SPEC.loader.exec_module(REDACTOR)


class AgentTraceRedactorTests(unittest.TestCase):
    def test_redacts_nested_keys_and_normalized_header_names(self) -> None:
        value = {
            "Authorization": "Bearer private",
            "request": {
                "API-Key": "private-key",
                "items": [{"password": "private-password"}],
            },
        }

        redacted = REDACTOR.redact_value(value)

        self.assertEqual(redacted["Authorization"], "[REDACTED]")
        self.assertEqual(redacted["request"]["API-Key"], "[REDACTED]")
        self.assertEqual(redacted["request"]["items"][0]["password"], "[REDACTED]")

    def test_keeps_similarly_named_non_secret_fields(self) -> None:
        value = {"token_count": 42, "secret_reason": "classification", "status": "ok"}

        self.assertEqual(REDACTOR.redact_value(value), value)

    def test_custom_sensitive_key_is_added_to_defaults(self) -> None:
        keys = REDACTOR.sensitive_key_set(["Session-ID"])
        value = {"session_id": "private-session", "access_token": "private-token"}

        redacted = REDACTOR.redact_value(value, keys)

        self.assertEqual(
            redacted,
            {"session_id": "[REDACTED]", "access_token": "[REDACTED]"},
        )

    def test_jsonl_loader_accepts_bom_and_skips_blank_lines(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            trace_path = Path(directory) / "trace.jsonl"
            trace_path.write_text(
                '\ufeff{"event_type":"start","token":"private"}\n\n'
                '{"event_type":"end","status":"ok"}\n',
                encoding="utf-8",
            )

            lines = REDACTOR.redact_jsonl(trace_path)

        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["token"], "[REDACTED]")
        self.assertEqual(json.loads(lines[1])["status"], "ok")

    def test_invalid_json_reports_source_line(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            trace_path = Path(directory) / "trace.jsonl"
            trace_path.write_text('\n{"event_type":}\n', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, r"line 2: invalid JSON"):
                REDACTOR.redact_jsonl(trace_path)

    def test_non_object_event_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            trace_path = Path(directory) / "trace.jsonl"
            trace_path.write_text('["not", "an", "event"]\n', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "trace event must be a JSON object"):
                REDACTOR.redact_jsonl(trace_path)

    def test_cli_stdout_contains_only_redacted_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            trace_path = Path(directory) / "trace.jsonl"
            trace_path.write_text('{"token":"private","status":"ok"}\n', encoding="utf-8")
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                exit_code = REDACTOR.main([str(trace_path)])

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            json.loads(stdout.getvalue()),
            {"token": "[REDACTED]", "status": "ok"},
        )

    def test_cli_refuses_to_overwrite_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            trace_path = Path(directory) / "trace.jsonl"
            original = '{"token":"private"}\n'
            trace_path.write_text(original, encoding="utf-8")
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                exit_code = REDACTOR.main(
                    [str(trace_path), "--output", str(trace_path)]
                )

            self.assertEqual(trace_path.read_text(encoding="utf-8"), original)

        self.assertEqual(exit_code, 2)
        self.assertIn("output path must differ", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
