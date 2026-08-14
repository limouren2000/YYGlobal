"""Unit tests for the Core-Agent health snapshot."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_status import summarize_workspace


class AgentStatusTests(unittest.TestCase):
    def test_summarizes_core_agent_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            core_agent = Path(directory) / "Core-Agent"
            core_agent.mkdir()
            (core_agent / "alpha.py").write_text("", encoding="utf-8")
            (core_agent / "README.md").write_text("", encoding="utf-8")

            snapshot = summarize_workspace(Path(directory))

        self.assertEqual(snapshot["core_agent_files"], ["README.md", "alpha.py"])
        self.assertEqual(snapshot["artifact_count"], 2)
        self.assertEqual(snapshot["status"], "ready")

    def test_missing_core_agent_directory_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            snapshot = summarize_workspace(Path(directory))

        self.assertEqual(snapshot["core_agent_files"], [])
        self.assertEqual(snapshot["artifact_count"], 0)
        self.assertEqual(snapshot["status"], "ready")


if __name__ == "__main__":
    unittest.main()
