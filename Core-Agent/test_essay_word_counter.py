import unittest

from essay_word_counter import EssayWordCounterSkill, main


class EssayWordCounterSkillTest(unittest.TestCase):
    def test_counts_words(self):
        result = EssayWordCounterSkill().run("one two three")
        self.assertEqual(result["word_count"], 3)
        self.assertTrue(result["within_limit"])

    def test_whitespace_and_newlines_are_handled(self):
        result = EssayWordCounterSkill().run("  hello\nworld\tagain  ")
        self.assertEqual(result["word_count"], 3)

    def test_within_limit(self):
        result = EssayWordCounterSkill().run("one two three", limit=5)
        self.assertEqual(result["word_count"], 3)
        self.assertTrue(result["within_limit"])
        self.assertEqual(result["over_by"], 0)

    def test_over_limit(self):
        result = EssayWordCounterSkill().run("one two three", limit=2)
        self.assertFalse(result["within_limit"])
        self.assertEqual(result["over_by"], 1)

    def test_no_limit(self):
        result = EssayWordCounterSkill().run("one two")
        self.assertNotIn("limit", result)
        self.assertNotIn("over_by", result)


class EssayWordCounterMainTest(unittest.TestCase):
    def test_over_limit_exits_one(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "essay.txt"
            path.write_text("one two three", encoding="utf-8")
            self.assertEqual(main([str(path), "--limit", "2"]), 1)

    def test_missing_file_exits_two(self):
        self.assertEqual(main(["does-not-exist.txt"]), 2)


if __name__ == "__main__":
    unittest.main()
