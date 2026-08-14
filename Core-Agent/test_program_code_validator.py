import unittest

from program_code_validator import ProgramCodeValidatorSkill, main


class ProgramCodeValidatorSkillTest(unittest.TestCase):
    def test_valid_simple_code(self):
        result = ProgramCodeValidatorSkill().run("USC-MSCS")
        self.assertTrue(result["valid"])
        self.assertEqual(result["normalized"], "USC-MSCS")
        self.assertIsNone(result["term"])

    def test_normalizes_to_uppercase(self):
        result = ProgramCodeValidatorSkill().run("us-mscs")
        self.assertTrue(result["valid"])
        self.assertEqual(result["normalized"], "US-MSCS")

    def test_extracts_term(self):
        result = ProgramCodeValidatorSkill().run("USC-MSCS-2026FALL")
        self.assertTrue(result["valid"])
        self.assertEqual(result["term"], "FALL 2026")

    def test_empty_code_is_invalid(self):
        result = ProgramCodeValidatorSkill().run("   ")
        self.assertFalse(result["valid"])
        self.assertIn("不能为空", result["reason"])

    def test_whitespace_is_invalid(self):
        result = ProgramCodeValidatorSkill().run("USC MSCS")
        self.assertFalse(result["valid"])

    def test_disallowed_characters_are_invalid(self):
        result = ProgramCodeValidatorSkill().run("USC_MSCS")
        self.assertFalse(result["valid"])

    def test_numbers_only_are_invalid(self):
        result = ProgramCodeValidatorSkill().run("2026")
        self.assertFalse(result["valid"])


class ProgramCodeValidatorMainTest(unittest.TestCase):
    def test_valid_exits_zero(self):
        self.assertEqual(main(["USC-MSCS-2026FALL"]), 0)

    def test_invalid_exits_one(self):
        self.assertEqual(main(["not a code"]), 1)


if __name__ == "__main__":
    unittest.main()
