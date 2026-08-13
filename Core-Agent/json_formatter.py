"""Validate and format JSON using only the Python standard library.

Examples:
    python Core-Agent/json_formatter.py data.json
    type data.json | python Core-Agent/json_formatter.py --sort-keys
    python Core-Agent/json_formatter.py data.json --output formatted.json

"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TextIO


def load_json(source: TextIO) -> object:
    """Parse and return one JSON value from a text stream."""
    return json.load(source)


def format_json(value: object, *, indent: int, sort_keys: bool) -> str:
    """Return consistently formatted JSON with Unicode characters preserved."""
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=indent,
        sort_keys=sort_keys,
    ) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and format JSON from a file or standard input."
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        help="JSON file to read; omit to read from standard input",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="file to write; omit to write to standard output",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        choices=range(1, 9),
        metavar="1-8",
        help="spaces per indentation level (default: 2)",
    )
    parser.add_argument(
        "--sort-keys",
        action="store_true",
        help="sort object keys alphabetically",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        if args.input is None:
            value = load_json(sys.stdin)
        else:
            with args.input.open(encoding="utf-8") as source:
                value = load_json(source)

        formatted = format_json(
            value,
            indent=args.indent,
            sort_keys=args.sort_keys,
        )

        if args.output is None:
            sys.stdout.write(formatted)
        else:
            args.output.write_text(formatted, encoding="utf-8")
    except json.JSONDecodeError as exc:
        print(
            f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}",
            file=sys.stderr,
        )
        return 1
    except OSError as exc:
        print(f"File error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
