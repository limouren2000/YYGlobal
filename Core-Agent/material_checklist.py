"""Check application-material readiness with a default or custom checklist.

Examples:
    python Core-Agent/material_checklist.py cv transcript
    python Core-Agent/material_checklist.py --required "cv,transcript,portfolio" --prepared "cv,portfolio"
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Iterable


DEFAULT_REQUIRED = (
    "cv",
    "personal_statement",
    "transcript",
    "recommendation_letters",
    "language_score",
)

DISPLAY_NAMES = {
    "cv": "CV / Resume",
    "personal_statement": "Personal Statement",
    "transcript": "Transcript",
    "recommendation_letters": "Recommendation Letters",
    "language_score": "Language Score",
}


def normalize_name(value: str) -> str:
    """Normalize a material name while keeping custom items supported."""
    return "_".join(value.strip().lower().replace("-", " ").split())


def parse_list(value: str) -> list[str]:
    """Parse a comma-separated CLI value and discard empty entries."""
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class ChecklistResult:
    required: tuple[str, ...]
    prepared: tuple[str, ...]
    missing: tuple[str, ...]
    extra: tuple[str, ...]
    completion_percent: int

    @property
    def complete(self) -> bool:
        return not self.missing

    def as_dict(self) -> dict[str, object]:
        return {
            "required": list(self.required),
            "prepared": list(self.prepared),
            "missing": list(self.missing),
            "extra": list(self.extra),
            "completion_percent": self.completion_percent,
            "complete": self.complete,
        }


def check_materials(
    prepared: Iterable[str], required: Iterable[str] | None = None
) -> ChecklistResult:
    """Compare prepared materials with a configurable required checklist."""
    source_required = DEFAULT_REQUIRED if required is None else required
    required_items = tuple(
        dict.fromkeys(normalize_name(item) for item in source_required if item.strip())
    )
    if not required_items:
        raise ValueError("required materials cannot be empty")

    prepared_items = tuple(
        dict.fromkeys(normalize_name(item) for item in prepared if item.strip())
    )
    required_set = set(required_items)
    prepared_set = set(prepared_items)
    present = tuple(item for item in required_items if item in prepared_set)
    missing = tuple(item for item in required_items if item not in prepared_set)
    extra = tuple(item for item in prepared_items if item not in required_set)
    completion = round(len(present) / len(required_items) * 100)

    return ChecklistResult(
        required=required_items,
        prepared=present,
        missing=missing,
        extra=extra,
        completion_percent=completion,
    )


def display_name(value: str) -> str:
    return DISPLAY_NAMES.get(value, value.replace("_", " ").title())


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check which application materials are ready or missing."
    )
    parser.add_argument(
        "materials",
        nargs="*",
        help="prepared materials; uses the default required checklist",
    )
    parser.add_argument(
        "--required",
        help="custom comma-separated required materials",
    )
    parser.add_argument(
        "--prepared",
        help="custom comma-separated prepared materials",
    )
    parser.add_argument("--json", action="store_true", help="print JSON output")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.prepared is not None and args.materials:
        print("[ERROR] use positional materials or --prepared, not both", file=sys.stderr)
        return 2

    required = parse_list(args.required) if args.required is not None else None
    prepared = parse_list(args.prepared) if args.prepared is not None else args.materials
    try:
        result = check_materials(prepared, required)
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    else:
        ready = ", ".join(map(display_name, result.prepared)) or "None"
        missing = ", ".join(map(display_name, result.missing)) or "None"
        print(f"Prepared: {ready}")
        print(f"Missing: {missing}")
        if result.extra:
            print(f"Additional: {', '.join(map(display_name, result.extra))}")
        print(f"Completion: {result.completion_percent}%")

    return 0 if result.complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
