"""Unit tests for the PR labeler helper."""

from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pr_labeler import infer_labels


class PRLabelerTests(unittest.TestCase):
    def test_basic_labels(self) -> None:
        paths = [
            "apps/web/app/page.tsx",
            "components/ui/button.tsx",
            "services/api/app/main.py",
            "README.md",
        ]
        labels = infer_labels(paths)
        # Expect frontend, backend, docs (order sorted alphabetically)
        self.assertEqual(sorted(labels), sorted(["backend", "docs", "frontend"]))

    def test_no_match_returns_other(self) -> None:
        paths = ["some/random/file.xyz"]
        self.assertEqual(infer_labels(paths), ["other"])


if __name__ == "__main__":
    unittest.main()
