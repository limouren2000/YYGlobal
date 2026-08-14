"""Tests for the configurable application material checklist."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from material_checklist import check_materials, normalize_name


class MaterialChecklistTests(unittest.TestCase):
    def test_default_checklist_reports_missing_items(self) -> None:
        result = check_materials(["cv", "transcript"])
        self.assertEqual(result.completion_percent, 40)
        self.assertEqual(
            result.missing,
            ("personal_statement", "recommendation_letters", "language_score"),
        )
        self.assertFalse(result.complete)

    def test_custom_checklist_supports_portfolio(self) -> None:
        result = check_materials(
            ["CV", "Portfolio"],
            ["CV", "Transcript", "Portfolio"],
        )
        self.assertEqual(result.prepared, ("cv", "portfolio"))
        self.assertEqual(result.missing, ("transcript",))
        self.assertEqual(result.completion_percent, 67)

    def test_complete_custom_checklist(self) -> None:
        result = check_materials(["writing sample"], ["Writing-Sample"])
        self.assertTrue(result.complete)
        self.assertEqual(result.completion_percent, 100)

    def test_additional_materials_are_preserved(self) -> None:
        result = check_materials(["cv", "gre"], ["cv"])
        self.assertEqual(result.extra, ("gre",))

    def test_duplicate_items_do_not_change_completion(self) -> None:
        result = check_materials(["cv", "CV"], ["cv", "transcript"])
        self.assertEqual(result.completion_percent, 50)

    def test_empty_custom_checklist_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            check_materials(["cv"], [])

    def test_normalizes_spaces_and_hyphens(self) -> None:
        self.assertEqual(normalize_name("  Writing-Sample  "), "writing_sample")


if __name__ == "__main__":
    unittest.main()
