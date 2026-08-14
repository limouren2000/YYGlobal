"""Unit tests for the Core-Agent PR summary generator."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pr_summary import render_pr_summary


class RenderPrSummaryTests(unittest.TestCase):
    def test_lists_changed_files_in_sorted_order(self) -> None:
        summary = render_pr_summary(
            {"Core-Agent/z_tool.py", "Core-Agent/a_tool.py"},
            "origin/main",
        )

        self.assertIn("修改了 2 个文件", summary)
        self.assertIn("对比基线：`origin/main`", summary)
        self.assertLess(
            summary.index("`Core-Agent/a_tool.py`"),
            summary.index("`Core-Agent/z_tool.py`"),
        )


if __name__ == "__main__":
    unittest.main()
