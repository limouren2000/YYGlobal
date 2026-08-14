"""Tests for the framework-independent personal statement quality checker."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ps_quality_checker import check_ps, main


def valid_bundle() -> dict[str, object]:
    return {
        "program": {"university": "Stanford University", "name": "MSCS"},
        "prompt_requirements": ["research experience", "career goal"],
        "word_limit": 1000,
        "selected_evidence": [{"experience_id": "exp-1", "use": "motivation"}],
        "confirmed_experiences": [{"id": "exp-1", "title": "Research internship"}],
        "ps_text": (
            "I want to study at Stanford University. "
            "My research experience and career goal motivate me."
        ),
    }


class PSQualityCheckerTests(unittest.TestCase):
    def test_accepts_a_clean_bundle(self) -> None:
        result = check_ps(valid_bundle())

        self.assertTrue(result.ok)
        self.assertEqual(result.findings, ())
        self.assertGreater(result.word_count, 0)

    def test_flags_leftover_placeholder(self) -> None:
        bundle = valid_bundle()
        bundle["ps_text"] = "I want to study at [University Name]."

        result = check_ps(bundle)

        self.assertFalse(result.ok)
        self.assertIn("placeholder", [item.code for item in result.errors])

    def test_flags_word_count_over_the_limit(self) -> None:
        bundle = valid_bundle()
        bundle["word_limit"] = 2

        result = check_ps(bundle)

        self.assertIn("over_word_limit", [item.code for item in result.errors])

    def test_warns_when_below_the_minimum(self) -> None:
        bundle = valid_bundle()
        bundle["min_words"] = 1000

        result = check_ps(bundle)

        self.assertTrue(result.ok)
        self.assertEqual([item.code for item in result.warnings], ["under_min_words"])

    def test_warns_when_a_requirement_is_not_addressed(self) -> None:
        bundle = valid_bundle()
        bundle["prompt_requirements"] = ["leadership"]

        result = check_ps(bundle)

        self.assertTrue(result.ok)
        self.assertIn("requirement_not_addressed", [item.code for item in result.warnings])

    def test_flags_an_unverified_experience(self) -> None:
        bundle = valid_bundle()
        bundle["selected_evidence"] = [{"experience_id": "missing-exp", "use": "motivation"}]

        result = check_ps(bundle)

        self.assertIn("unverified_experience", [item.code for item in result.errors])

    def test_flags_a_wrong_school_mention(self) -> None:
        bundle = valid_bundle()
        bundle["ps_text"] = "I want to study at Stanford University, but Harvard is also good."

        result = check_ps(bundle)

        self.assertFalse(result.ok)
        self.assertIn("wrong_school_mention", [item.code for item in result.errors])

    def test_warns_when_the_target_school_is_not_mentioned(self) -> None:
        bundle = valid_bundle()
        bundle["ps_text"] = "I am motivated by my research experience and career goal."

        result = check_ps(bundle)

        self.assertTrue(result.ok)
        self.assertIn("generic_ps_missing_school", [item.code for item in result.warnings])

    def test_rejects_a_missing_ps_text(self) -> None:
        bundle = valid_bundle()
        bundle["ps_text"] = ""

        result = check_ps(bundle)

        self.assertIn("invalid_ps_text", [item.code for item in result.errors])

    def test_rejects_a_non_object_bundle(self) -> None:
        result = check_ps(["not", "an", "object"])

        self.assertIn("invalid_bundle", [item.code for item in result.errors])

    def test_cli_emits_json_and_returns_zero_for_a_clean_bundle(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            json.dump(valid_bundle(), handle)
            bundle_path = Path(handle.name)
        self.addCleanup(bundle_path.unlink)
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            exit_code = main([str(bundle_path), "--json"])

        self.assertEqual(exit_code, 0)
        self.assertTrue(json.loads(output.getvalue())["ok"])

    def test_cli_returns_one_when_errors_are_found(self) -> None:
        bundle = valid_bundle()
        bundle["ps_text"] = "I want to study at [University Name]."
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            json.dump(bundle, handle)
            bundle_path = Path(handle.name)
        self.addCleanup(bundle_path.unlink)

        with contextlib.redirect_stdout(io.StringIO()):
            exit_code = main([str(bundle_path)])

        self.assertEqual(exit_code, 1)

    def test_cli_returns_two_for_invalid_json(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write("not-json")
            bundle_path = Path(handle.name)
        self.addCleanup(bundle_path.unlink)

        with contextlib.redirect_stderr(io.StringIO()):
            exit_code = main([str(bundle_path)])

        self.assertEqual(exit_code, 2)


if __name__ == "__main__":
    unittest.main()
