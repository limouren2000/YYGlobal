"""Convert international grading scales to a US 4.0 GPA scale.

Study-abroad applicants hold transcripts on many different grading systems.
This tool converts common scales to the 4.0 scale so that profiles can be
compared consistently. Only the Python standard library is used.

Supported scales:
    percentage   0-100, used by China, UK, India, and many others
    chinese_5    0.0-5.0, Chinese university 5-point GPA
    german       1.0-5.0, German system (1.0 best, 4.0 passing, 5.0 fail)
    us_4         0.0-4.0, pass-through validation

Conversion formulas:
    percentage   gpa = clamp((score - 50) / 10, 0, 4)
    chinese_5    gpa = score / 5.0 * 4.0
    german       gpa = clamp(5.0 - score, 0, 4)
    us_4         gpa = score (no conversion)

Examples:
    python Core-Agent/gpa_converter.py --scale percentage --score 88
    python Core-Agent/gpa_converter.py --scale chinese_5 --score 4.2 --json
    python Core-Agent/gpa_converter.py --scale german --score 1.3

Exit codes: 0 for a valid conversion, 1 for an out-of-range score, and 2
for an unknown scale or invalid input.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any


SCALE_RANGES: dict[str, tuple[float, float]] = {
    "percentage": (0.0, 100.0),
    "chinese_5": (0.0, 5.0),
    "german": (1.0, 5.0),
    "us_4": (0.0, 4.0),
}


@dataclass(frozen=True)
class ConversionResult:
    scale: str
    original_score: float
    gpa: float
    grade_letter: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "scale": self.scale,
            "original_score": self.original_score,
            "gpa": round(self.gpa, 2),
            "grade_letter": self.grade_letter,
        }


class GpaConverterSkill:
    """轻量 Skill：将各国成绩体系转换为美国 4.0 GPA 制。"""

    name = "gpa_converter"
    description = "将百分比、5 分制、德国 1-5 制等成绩转换为 4.0 GPA"

    def run(self, scale: str, score: float) -> dict[str, Any]:
        normalized = scale.strip().lower()
        if normalized not in SCALE_RANGES:
            raise ValueError(
                f"unknown scale {scale!r}; choose from {', '.join(SCALE_RANGES)}"
            )

        low, high = SCALE_RANGES[normalized]
        if not (low <= score <= high):
            raise ValueError(
                f"score {score} is out of range for {normalized} "
                f"(expected {low}-{high})"
            )

        gpa = _convert(normalized, score)
        result = ConversionResult(
            scale=normalized,
            original_score=score,
            gpa=gpa,
            grade_letter=_grade_letter(gpa),
        )
        return result.as_dict()


def _convert(scale: str, score: float) -> float:
    if scale == "percentage":
        return max(0.0, min(4.0, (score - 50.0) / 10.0))
    if scale == "chinese_5":
        return score / 5.0 * 4.0
    if scale == "german":
        return max(0.0, min(4.0, 5.0 - score))
    # us_4: pass-through
    return score


def _grade_letter(gpa: float) -> str:
    if gpa >= 3.7:
        return "A"
    if gpa >= 3.0:
        return "B"
    if gpa >= 2.0:
        return "C"
    if gpa >= 1.0:
        return "D"
    return "F"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert international grading scales to a 4.0 GPA."
    )
    parser.add_argument(
        "--scale",
        required=True,
        choices=sorted(SCALE_RANGES),
        help="grading scale of the input score",
    )
    parser.add_argument(
        "--score",
        required=True,
        type=float,
        help="score to convert",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the result as JSON",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        result = GpaConverterSkill().run(scale=args.scale, score=args.score)
    except ValueError as exc:
        message = str(exc)
        print(f"[ERROR] {message}", file=sys.stderr)
        return 2 if "unknown scale" in message else 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            f"{result['original_score']} ({result['scale']}) "
            f"-> {result['gpa']:.2f} / 4.0  [{result['grade_letter']}]"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
