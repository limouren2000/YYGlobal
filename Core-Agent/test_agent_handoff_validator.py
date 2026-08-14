"""Regression tests for the Agent handoff validator."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("agent_handoff_validator.py")
SPEC = importlib.util.spec_from_file_location("agent_handoff_validator", MODULE_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


def valid_handoff() -> dict[str, object]:
    return {
        "handoff_id": "research-to-writer-001",
        "from_agent": "research-agent",
        "to_agent": "writing-agent",
        "summary": "Official program requirements were collected.",
        "completed": ["Verified application deadline."],
        "next_steps": ["Draft the applicant timeline."],
        "evidence": ["https://example.edu/admissions"],
        "risks": [],
        "status": "ready",
    }


class AgentHandoffValidatorTests(unittest.TestCase):
    def test_valid_ready_handoff_passes(self) -> None:
        self.assertEqual(VALIDATOR.validate_handoff(valid_handoff()), [])

    def test_missing_receiver_is_reported(self) -> None:
        handoff = valid_handoff()
        handoff["to_agent"] = ""
        issues = VALIDATOR.validate_handoff(handoff)
        self.assertTrue(any(issue.field == "to_agent" for issue in issues))

    def test_handoff_requires_next_step(self) -> None:
        handoff = valid_handoff()
        handoff["next_steps"] = []
        issues = VALIDATOR.validate_handoff(handoff)
        self.assertTrue(any(issue.field == "next_steps" for issue in issues))

    def test_blocked_handoff_requires_risk(self) -> None:
        handoff = valid_handoff()
        handoff["status"] = "blocked"
        issues = VALIDATOR.validate_handoff(handoff)
        self.assertTrue(any(issue.field == "risks" for issue in issues))

    def test_same_sender_and_receiver_is_rejected(self) -> None:
        handoff = valid_handoff()
        handoff["to_agent"] = handoff["from_agent"]
        issues = VALIDATOR.validate_handoff(handoff)
        self.assertTrue(any(issue.field == "to_agent" for issue in issues))

    def test_cli_json_output_for_invalid_record(self) -> None:
        handoff = valid_handoff()
        handoff["status"] = "unknown"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "handoff.json"
            path.write_text(json.dumps(handoff), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(MODULE_PATH), str(path), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["status"], "failed")


if __name__ == "__main__":
    unittest.main()
