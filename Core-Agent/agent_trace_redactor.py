#!/usr/bin/env python3
"""Redact common credentials from Agent trace JSONL before sharing it.

The utility is deliberately standalone: it uses only the Python standard
library and is never imported by YYGlobal's API or web application. Sensitive
keys are matched case-insensitively after normalizing spaces and hyphens to
underscores. Values are redacted recursively in nested objects and arrays.
The utility does not inspect secrets embedded in free-form string values, so
review the generated trace before publishing it outside a trusted environment.

Examples:
    python Core-Agent/agent_trace_redactor.py trace.jsonl
    python Core-Agent/agent_trace_redactor.py trace.jsonl --output safe-trace.jsonl
    python Core-Agent/agent_trace_redactor.py trace.jsonl --sensitive-key session_id
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable


DEFAULT_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "set_cookie",
        "password",
        "passwd",
        "secret",
        "client_secret",
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "x_api_key",
        "x_auth_token",
        "proxy_authorization",
    }
)
DEFAULT_PLACEHOLDER = "[REDACTED]"


def normalize_key(key: str) -> str:
    """Normalize a JSON object key for exact sensitive-key matching."""
    return key.strip().lower().replace("-", "_").replace(" ", "_")


def sensitive_key_set(extra_keys: Iterable[str] = ()) -> frozenset[str]:
    """Return default sensitive keys plus normalized caller-supplied keys."""
    return DEFAULT_SENSITIVE_KEYS | {
        normalize_key(key) for key in extra_keys if normalize_key(key)
    }


def redact_value(
    value: Any,
    sensitive_keys: frozenset[str] = DEFAULT_SENSITIVE_KEYS,
    placeholder: str = DEFAULT_PLACEHOLDER,
) -> Any:
    """Return a recursively redacted copy of a JSON-compatible value."""
    if isinstance(value, dict):
        return {
            key: (
                placeholder
                if normalize_key(key) in sensitive_keys
                else redact_value(child, sensitive_keys, placeholder)
            )
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [redact_value(child, sensitive_keys, placeholder) for child in value]
    return value


def redact_jsonl(
    path: Path,
    sensitive_keys: frozenset[str] = DEFAULT_SENSITIVE_KEYS,
    placeholder: str = DEFAULT_PLACEHOLDER,
) -> list[str]:
    """Load, validate, and redact non-empty JSON object lines from ``path``."""
    output: list[str] = []
    with path.open(encoding="utf-8-sig") as trace_file:
        for line_number, raw_line in enumerate(trace_file, start=1):
            if not raw_line.strip():
                continue
            try:
                value = json.loads(raw_line)
            except json.JSONDecodeError as error:
                raise ValueError(f"line {line_number}: invalid JSON ({error.msg})") from error
            if not isinstance(value, dict):
                raise ValueError(f"line {line_number}: trace event must be a JSON object")
            redacted = redact_value(value, sensitive_keys, placeholder)
            output.append(json.dumps(redacted, ensure_ascii=False, separators=(",", ":")))
    if not output:
        raise ValueError("input file contains no trace events")
    return output


def _same_path(left: Path, right: Path) -> bool:
    """Compare paths without requiring either one to exist."""
    return left.expanduser().resolve() == right.expanduser().resolve()


def main(argv: list[str] | None = None) -> int:
    """Run the redaction command-line interface."""
    parser = argparse.ArgumentParser(
        description="Redact common credentials from an Agent trace JSONL file."
    )
    parser.add_argument("trace_file", type=Path, help="path to a UTF-8 JSONL trace file")
    parser.add_argument(
        "--output",
        type=Path,
        help="write redacted JSONL here instead of stdout (must differ from input)",
    )
    parser.add_argument(
        "--sensitive-key",
        action="append",
        default=[],
        metavar="KEY",
        help="redact an additional exact key; repeatable",
    )
    parser.add_argument(
        "--placeholder",
        default=DEFAULT_PLACEHOLDER,
        help=f"replacement value (default: {DEFAULT_PLACEHOLDER})",
    )
    args = parser.parse_args(argv)

    if args.output is not None and _same_path(args.trace_file, args.output):
        print("[ERROR] output path must differ from input path", file=sys.stderr)
        return 2

    try:
        lines = redact_jsonl(
            args.trace_file,
            sensitive_key_set(args.sensitive_key),
            args.placeholder,
        )
        content = "\n".join(lines) + "\n"
        if args.output is None:
            sys.stdout.write(content)
        else:
            args.output.write_text(content, encoding="utf-8")
            print(f"[PASS] redacted {len(lines)} event(s) to {args.output}")
    except (OSError, UnicodeError, ValueError) as error:
        print(f"[ERROR] unable to redact trace: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
