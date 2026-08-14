"""Validate Agent tool arguments with JSON Schema Draft 2020-12.

The validator is intentionally independent from a model provider or tool
registry.  It can be imported by Agent code, used in tests, or invoked as a
small command-line gate before a tool handler receives model-generated input.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


@dataclass(frozen=True)
class ValidationIssue:
    """One deterministic, JSON-serializable argument validation issue."""

    path: str
    schema_path: str
    message: str
    validator: str

    def to_dict(self) -> dict[str, str]:
        """Return a representation suitable for logs and CLI JSON output."""
        return {
            "path": self.path,
            "schema_path": self.schema_path,
            "message": self.message,
            "validator": self.validator,
        }


class ToolArgumentsValidationError(ValueError):
    """Raised when tool arguments do not satisfy their declared schema."""

    def __init__(self, issues: Sequence[ValidationIssue]) -> None:
        self.issues = tuple(issues)
        details = "; ".join(f"{issue.path}: {issue.message}" for issue in self.issues)
        super().__init__(f"Tool arguments failed JSON Schema validation: {details}")


def _json_path(parts: Sequence[Any]) -> str:
    path = "$"
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        elif isinstance(part, str) and part.isidentifier():
            path += f".{part}"
        else:
            path += f"[{json.dumps(part, ensure_ascii=False)}]"
    return path


def validate_tool_arguments(
    schema: Union[Mapping[str, Any], bool],
    arguments: Any,
) -> list[ValidationIssue]:
    """Return all Draft 2020-12 violations in deterministic order.

    JSON Schema permits non-object root values, but tool-call arguments must be
    a JSON object.  That contract is enforced before applying the supplied
    schema.  Invalid schemas raise :class:`jsonschema.exceptions.SchemaError`
    instead of silently weakening validation.
    """

    Draft202012Validator.check_schema(schema)
    if not isinstance(arguments, dict):
        return [
            ValidationIssue(
                path="$",
                schema_path="$.type",
                message=f"tool arguments must be an object, got {type(arguments).__name__}",
                validator="type",
            )
        ]

    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(arguments),
        key=lambda error: (
            tuple(str(part) for part in error.absolute_path),
            tuple(str(part) for part in error.absolute_schema_path),
            error.message,
        ),
    )
    return [
        ValidationIssue(
            path=_json_path(list(error.absolute_path)),
            schema_path=_json_path(list(error.absolute_schema_path)),
            message=error.message,
            validator=str(error.validator or "unknown"),
        )
        for error in errors
    ]


def require_valid_tool_arguments(
    schema: Union[Mapping[str, Any], bool],
    arguments: Any,
) -> None:
    """Raise ``ToolArgumentsValidationError`` when any violation is found."""

    issues = validate_tool_arguments(schema, arguments)
    if issues:
        raise ToolArgumentsValidationError(issues)


def _read_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""

    parser = argparse.ArgumentParser(
        description="Validate Agent tool arguments with JSON Schema Draft 2020-12."
    )
    parser.add_argument("--schema", type=Path, required=True, help="JSON Schema file")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--arguments", type=Path, help="tool arguments JSON file")
    source.add_argument("--arguments-json", help="inline tool arguments JSON object")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:  # noqa: UP045 - Python 3.9
    """Run the CLI and return 0=valid, 1=invalid arguments, or 2=input error."""

    options = build_parser().parse_args(argv)
    try:
        schema = _read_json_file(options.schema)
        if options.arguments is not None:
            arguments = _read_json_file(options.arguments)
        else:
            try:
                arguments = json.loads(options.arguments_json)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid inline arguments JSON: {exc}") from exc
        issues = validate_tool_arguments(schema, arguments)
    except (SchemaError, ValueError) as exc:
        payload = {"valid": False, "error": str(exc), "issues": []}
        print(json.dumps(payload, ensure_ascii=False) if options.json else f"ERROR: {exc}")
        return 2

    payload = {
        "valid": not issues,
        "issues": [issue.to_dict() for issue in issues],
    }
    if options.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    elif issues:
        print("Tool arguments are invalid:")
        for issue in issues:
            print(f"- {issue.path}: {issue.message} ({issue.validator})")
    else:
        print("Tool arguments are valid.")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
