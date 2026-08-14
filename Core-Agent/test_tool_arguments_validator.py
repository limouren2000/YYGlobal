from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from jsonschema.exceptions import SchemaError

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tool_arguments_validator import (  # noqa: E402
    ToolArgumentsValidationError,
    main,
    require_valid_tool_arguments,
    validate_tool_arguments,
)

TOOL_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "program_ids": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "minItems": 1,
            "uniqueItems": True,
        },
        "tier": {"type": "string", "enum": ["reach", "target", "safer"]},
        "score": {"type": "number", "minimum": 0, "maximum": 100},
        "options": {
            "type": "object",
            "properties": {"verified": {"type": "boolean"}},
            "required": ["verified"],
            "additionalProperties": False,
        },
    },
    "required": ["program_ids", "tier", "score", "options"],
    "additionalProperties": False,
}


class ToolArgumentsValidatorTests(unittest.TestCase):
    def valid_arguments(self) -> dict:
        return {
            "program_ids": ["program-1", "program-2"],
            "tier": "target",
            "score": 88.5,
            "options": {"verified": True},
        }

    def test_accepts_nested_valid_arguments(self) -> None:
        self.assertEqual(validate_tool_arguments(TOOL_SCHEMA, self.valid_arguments()), [])

    def test_rejects_invalid_array_items_and_nested_values(self) -> None:
        arguments = self.valid_arguments()
        arguments["program_ids"] = ["program-1", 42]
        arguments["options"] = {"verified": "yes"}

        issues = validate_tool_arguments(TOOL_SCHEMA, arguments)

        self.assertEqual(
            {issue.path for issue in issues},
            {"$.program_ids[1]", "$.options.verified"},
        )

    def test_enforces_enum_numeric_bounds_and_additional_properties(self) -> None:
        arguments = self.valid_arguments()
        arguments.update({"tier": "guaranteed", "score": 101, "unexpected": True})

        issues = validate_tool_arguments(TOOL_SCHEMA, arguments)

        self.assertEqual(
            {issue.validator for issue in issues},
            {"additionalProperties", "enum", "maximum"},
        )

    def test_boolean_is_not_accepted_as_number(self) -> None:
        arguments = self.valid_arguments()
        arguments["score"] = True

        issues = validate_tool_arguments(TOOL_SCHEMA, arguments)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].path, "$.score")
        self.assertEqual(issues[0].validator, "type")

    def test_requires_tool_arguments_to_be_an_object(self) -> None:
        issues = validate_tool_arguments(True, ["not", "an", "object"])

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].path, "$")

    def test_invalid_schema_is_not_silently_accepted(self) -> None:
        with self.assertRaises(SchemaError):
            validate_tool_arguments({"type": "not-a-json-schema-type"}, {})

    def test_raise_helper_exposes_structured_issues(self) -> None:
        arguments = self.valid_arguments()
        arguments["tier"] = "unknown"

        with self.assertRaises(ToolArgumentsValidationError) as context:
            require_valid_tool_arguments(TOOL_SCHEMA, arguments)

        self.assertEqual(context.exception.issues[0].path, "$.tier")

    def test_cli_returns_machine_readable_validation_result(self) -> None:
        with TemporaryDirectory() as directory:
            schema_path = Path(directory) / "schema.json"
            arguments_path = Path(directory) / "arguments.json"
            schema_path.write_text(json.dumps(TOOL_SCHEMA), encoding="utf-8")
            arguments_path.write_text(json.dumps(self.valid_arguments()), encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    [
                        "--schema",
                        str(schema_path),
                        "--arguments",
                        str(arguments_path),
                        "--json",
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output.getvalue()), {"issues": [], "valid": True})

    def test_cli_returns_one_for_invalid_arguments(self) -> None:
        with TemporaryDirectory() as directory:
            schema_path = Path(directory) / "schema.json"
            schema_path.write_text(json.dumps(TOOL_SCHEMA), encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    [
                        "--schema",
                        str(schema_path),
                        "--arguments-json",
                        '{"program_ids": [1]}',
                        "--json",
                    ]
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["valid"])
        self.assertGreater(len(payload["issues"]), 0)


if __name__ == "__main__":
    unittest.main()
