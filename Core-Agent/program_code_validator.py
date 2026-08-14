"""Program code validator Skill：校验留学申请中的项目编号格式。

只使用 Python 标准库。项目编号遵循常见约定：字母数字加连字符分段，
末尾可携带入学学期后缀（如 -2026FALL / -2027SPRING），用于研究项目、
创建选校清单、生成材料计划等场景。

Examples:
    python Core-Agent/program_code_validator.py "USC-MSCS-2026FALL"
    python Core-Agent/program_code_validator.py "us-mscs" --json
    python Core-Agent/program_code_validator.py "not a code"

Exit codes: 0 for a valid code, 1 for an invalid code.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

_TERM_PATTERN = re.compile(r"^(?P<year>20\d{2})(?P<season>FALL|SPRING|SUMMER|WINTER)$")
_ALLOWED_CHARS = re.compile(r"^[A-Z0-9]+(?:-[A-Z0-9]+)*$")


class ProgramCodeValidatorSkill:
    """留学申请场景下的轻量 Skill：校验并规范化项目编号。"""

    name = "program_code_validator"
    description = "校验项目编号格式，并提取入学学期（若有）"

    def run(self, code: str) -> dict[str, Any]:
        normalized = code.strip().upper()

        result: dict[str, Any] = {
            "original": code,
            "normalized": normalized,
            "valid": False,
            "reason": None,
            "term": None,
        }

        if not normalized:
            result["reason"] = "项目编号不能为空"
            return result
        if any(ch.isspace() for ch in normalized):
            result["reason"] = "项目编号不能包含空白字符"
            return result
        if not _ALLOWED_CHARS.match(normalized):
            result["reason"] = "项目编号只能包含字母、数字和连字符"
            return result
        if not any(ch.isalpha() for ch in normalized):
            result["reason"] = "项目编号至少需要包含一个字母"
            return result

        term = None
        parts = normalized.split("-")
        if len(parts) > 1:
            match = _TERM_PATTERN.match(parts[-1])
            if match:
                term = f"{match.group('season')} {match.group('year')}"

        result["valid"] = True
        result["term"] = term
        return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=ProgramCodeValidatorSkill.description)
    parser.add_argument("code", help="待校验的项目编号，例如 USC-MSCS-2026FALL")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = ProgramCodeValidatorSkill().run(code=args.code)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["valid"]:
        term = f"，入学学期 {result['term']}" if result["term"] else ""
        print(f"有效：{result['normalized']}{term}")
    else:
        print(f"无效：{result['reason']}", file=sys.stderr)

    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
