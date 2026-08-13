"""Count words in an application essay and check it against a word limit.

Only the Python standard library is used. Word counts follow the common
application convention: contiguous non-whitespace characters count as one
word. This matches the behaviour of most word processors for plain text.

Examples:
    python Core-Agent/essay_word_counter.py personal_statement.txt
    python Core-Agent/essay_word_counter.py statement.txt --limit 500
    python Core-Agent/essay_word_counter.py statement.txt --limit 500 --json

Exit codes: 0 for a passing essay (within limit), 1 for a word count over the
limit, and 2 when the input cannot be read.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


class EssayWordCounterSkill:
    """轻量 Skill：统计申请文书（PS / SOP）字数并检查是否超限。"""

    name = "essay_word_counter"
    description = "统计申请文书字数，并按字数上限判断是否超限"

    def run(
        self,
        text: str,
        limit: int | None = None,
    ) -> dict[str, Any]:
        word_count = len(text.split())
        result: dict[str, Any] = {
            "word_count": word_count,
            "within_limit": True,
        }
        if limit is not None:
            result["limit"] = limit
            result["within_limit"] = word_count <= limit
            result["over_by"] = max(0, word_count - limit)
        return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Count words in an application essay and check a word limit."
    )
    parser.add_argument(
        "input",
        type=Path,
        help="text file to count (e.g. personal statement or SOP)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="optional maximum word count",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the result as JSON instead of plain text",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        text = args.input.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"File error: {exc}", file=sys.stderr)
        return 2

    result = EssayWordCounterSkill().run(text=text, limit=args.limit)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.limit is not None:
        status = "within limit" if result["within_limit"] else "OVER limit"
        print(
            f"{result['word_count']} words "
            f"(limit {result['limit']}): {status}"
        )
    else:
        print(f"{result['word_count']} words")

    return 0 if result["within_limit"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
