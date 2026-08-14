"""Check an application personal statement against the ps-planner contract.

The ``ps-planner`` skill declares three acceptance criteria in its own prompt:
stay on-topic, do not misuse the school name, and only cite traceable material.
This utility turns those criteria into deterministic checks instead of relying
on the model to self-police. It only uses the Python standard library.

The input is a single JSON object that mirrors the fields the ``ps-planner``
skill already produces, plus the target program and the applicant's confirmed
experiences:

    {
      "program": {"university": "Stanford University", "name": "MSCS"},
      "prompt_requirements": ["research experience", "career goal"],
      "word_limit": 1000,
      "min_words": 500,
      "selected_evidence": [{"experience_id": "exp-1", "use": "motivation"}],
      "confirmed_experiences": [{"id": "exp-1", "title": "Research internship"}],
      "other_universities": ["Harvard University"],
      "ps_text": "..."
    }

Examples:
    python Core-Agent/ps_quality_checker.py ps-bundle.json
    python Core-Agent/ps_quality_checker.py ps-bundle.json --json

Exit codes: 0 when no errors are found, 1 when errors are found, and 2 when the
input cannot be read or parsed. Warnings do not fail the check.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

# A small, hand-picked corpus of distinctive proper-noun tokens for well-known
# universities. Common English words that would produce false positives (e.g.
# "brown", "duke", "imperial") are deliberately excluded. This is a heuristic
# fallback: callers can extend it through the bundle's ``other_universities``.
DEFAULT_UNIVERSITY_TOKENS = {
    "Harvard University": "harvard",
    "Yale University": "yale",
    "Princeton University": "princeton",
    "Stanford University": "stanford",
    "Massachusetts Institute of Technology": "massachusetts",
    "California Institute of Technology": "caltech",
    "Cornell University": "cornell",
    "Dartmouth College": "dartmouth",
    "Johns Hopkins University": "hopkins",
    "Northwestern University": "northwestern",
    "University of Pennsylvania": "pennsylvania",
    "University of Chicago": "chicago",
    "Carnegie Mellon University": "mellon",
    "New York University": "new york",
    "University of Michigan": "michigan",
    "University of Toronto": "toronto",
    "University of Oxford": "oxford",
    "University of Cambridge": "cambridge",
    "University of California Berkeley": "berkeley",
    "University of California Los Angeles": "los angeles",
    "National University of Singapore": "singapore",
    "ETH Zurich": "zurich",
}

# Grammatical and institution words that are not useful for matching either a
# school name or a prompt requirement.
_STOP_WORDS = frozenset(
    {
        "university",
        "college",
        "institute",
        "school",
        "academy",
        "polytechnic",
        "of",
        "the",
        "and",
        "for",
        "at",
        "in",
        "on",
        "to",
        "a",
        "an",
        "this",
        "that",
        "these",
        "those",
        "your",
        "my",
        "our",
        "their",
        "his",
        "her",
        "why",
        "how",
        "what",
        "when",
        "where",
        "who",
        "which",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "do",
        "does",
        "did",
        "technology",
        "tech",
        "science",
        "sciences",
        "state",
    }
)

# Leftover template markers that must not survive into a final PS.
PLACEHOLDER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("bracketed placeholder", re.compile(r"\[[^\]\n]{1,40}\]")),
    ("braced placeholder", re.compile(r"\{[^\}\n]{1,40}\}")),
    ("angle-bracket placeholder", re.compile(r"<[^>\n]{1,40}>")),
    ("repeated X", re.compile(r"\bX{2,}\b")),
    ("todo marker", re.compile(r"\b(TODO|FIXME|TBD)\b")),
    ("lorem ipsum", re.compile(r"\blorem\b")),
    ("your name", re.compile(r"\byour name\b", re.IGNORECASE)),
    ("insert here", re.compile(r"\binsert\b[^\n]{0,20}\bhere\b", re.IGNORECASE)),
)


@dataclass(frozen=True)
class Finding:
    """One deterministic PS quality finding."""

    severity: str
    code: str
    message: str


@dataclass(frozen=True)
class CheckResult:
    """Structured result returned by :func:`check_ps`."""

    findings: tuple[Finding, ...]
    word_count: int

    @property
    def errors(self) -> tuple[Finding, ...]:
        return tuple(item for item in self.findings if item.severity == "error")

    @property
    def warnings(self) -> tuple[Finding, ...]:
        return tuple(item for item in self.findings if item.severity == "warning")

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "word_count": self.word_count,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "findings": [
                {"severity": item.severity, "code": item.code, "message": item.message}
                for item in self.findings
            ],
        }


def _optional_int(value: Any) -> int | None:
    """Return an int, or None when the value is not a plain integer."""
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def _significant_words(value: str) -> list[str]:
    """Lowercase alphanumeric words, dropping stopwords and very short tokens."""
    words = re.findall(r"[A-Za-z0-9]+", value.lower())
    return [word for word in words if len(word) >= 3 and word not in _STOP_WORDS]


def _token_for(name: str) -> str:
    """Return a distinctive matching token for a university name.

    Known schools use the hand-picked token from :data:`DEFAULT_UNIVERSITY_TOKENS`;
    unknown schools fall back to their significant words joined in order.
    """
    for full_name, token in DEFAULT_UNIVERSITY_TOKENS.items():
        if full_name.lower() == name.strip().lower():
            return token
    return " ".join(_significant_words(name))


def _mentions(text: str, token: str) -> bool:
    """Return whether ``token`` appears in ``text`` on word boundaries."""
    parts = [part for part in token.split() if part]
    if not parts:
        return False
    pattern = r"\s+".join(r"\b" + re.escape(part) + r"\b" for part in parts)
    return re.search(pattern, text, re.IGNORECASE) is not None


def _check_placeholders(text: str, add: Callable[[str, str, str], None]) -> None:
    for line_number, line in enumerate(text.splitlines(), start=1):
        for label, pattern in PLACEHOLDER_PATTERNS:
            for match in pattern.finditer(line):
                add(
                    "error",
                    "placeholder",
                    f"line {line_number}: {label} {match.group(0)!r}",
                )


def _check_word_count(
    payload: dict[str, Any], word_count: int, add: Callable[[str, str, str], None]
) -> None:
    limit = _optional_int(payload.get("word_limit"))
    if limit is not None and word_count > limit:
        add(
            "error",
            "over_word_limit",
            f"{word_count} words exceeds the limit {limit} by {word_count - limit}",
        )
    minimum = _optional_int(payload.get("min_words"))
    if minimum is not None and word_count < minimum:
        add(
            "warning",
            "under_min_words",
            f"{word_count} words is below the minimum {minimum} by {minimum - word_count}",
        )


def _requirement_addressed(requirement: str, text: str) -> bool:
    words = _significant_words(requirement)
    if not words:
        return True  # no meaningful keyword to check; do not flag
    lowered = text.lower()
    return any(word in lowered for word in words)


def _check_on_topic(
    payload: dict[str, Any], text: str, add: Callable[[str, str, str], None]
) -> None:
    requirements = payload.get("prompt_requirements")
    if not isinstance(requirements, list):
        return
    for requirement in requirements:
        if not isinstance(requirement, str) or not requirement.strip():
            add(
                "error",
                "invalid_requirement",
                "prompt_requirements entries must be non-empty strings",
            )
            continue
        if not _requirement_addressed(requirement, text):
            add(
                "warning",
                "requirement_not_addressed",
                f"PS may not address the requirement {requirement!r}",
            )


def _confirmed_ids(experiences: Any) -> set[str]:
    ids: set[str] = set()
    if not isinstance(experiences, list):
        return ids
    for item in experiences:
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip():
            ids.add(item["id"].strip())
    return ids


def _check_traceability(
    payload: dict[str, Any], add: Callable[[str, str, str], None]
) -> None:
    selected = payload.get("selected_evidence")
    if not isinstance(selected, list):
        return
    confirmed = _confirmed_ids(payload.get("confirmed_experiences"))
    for index, item in enumerate(selected):
        if not isinstance(item, dict):
            add(
                "error",
                "invalid_evidence_reference",
                f"selected_evidence[{index}] must be an object",
            )
            continue
        experience_id = item.get("experience_id")
        if not isinstance(experience_id, str) or not experience_id.strip():
            add(
                "error",
                "invalid_evidence_reference",
                f"selected_evidence[{index}].experience_id must be a non-empty string",
            )
            continue
        if experience_id not in confirmed:
            add(
                "error",
                "unverified_experience",
                f"experience_id {experience_id!r} is not among the confirmed experiences",
            )


def _check_school_names(
    payload: dict[str, Any], text: str, add: Callable[[str, str, str], None]
) -> None:
    program = payload.get("program")
    university = program.get("university") if isinstance(program, dict) else None
    if not isinstance(university, str) or not university.strip():
        return

    target_words = _significant_words(university)
    target_token = _token_for(university) or " ".join(target_words)

    if target_words and not any(_mentions(text, word) for word in target_words):
        add(
            "warning",
            "generic_ps_missing_school",
            f"PS never mentions the target school {university!r}",
        )

    other_names = list(DEFAULT_UNIVERSITY_TOKENS.keys())
    extra = payload.get("other_universities")
    if isinstance(extra, list):
        other_names.extend(item for item in extra if isinstance(item, str))

    target_lower = university.strip().lower()
    for name in other_names:
        if name.strip().lower() == target_lower:
            continue
        token = _token_for(name)
        if not token or token == target_token:
            continue
        if _mentions(text, token):
            add(
                "error",
                "wrong_school_mention",
                f"PS mentions {name!r}, which is not the target school {university!r}",
            )


def check_ps(payload: Any) -> CheckResult:
    """Validate a parsed PS bundle and return all detected findings."""
    findings: list[Finding] = []

    def add(severity: str, code: str, message: str) -> None:
        findings.append(Finding(severity, code, message))

    if not isinstance(payload, dict):
        add("error", "invalid_bundle", "bundle must be a JSON object")
        return CheckResult(tuple(findings), 0)

    ps_text = payload.get("ps_text")
    if not isinstance(ps_text, str) or not ps_text.strip():
        add("error", "invalid_ps_text", "ps_text must be a non-empty string")
        return CheckResult(tuple(findings), 0)

    word_count = len(ps_text.split())

    _check_placeholders(ps_text, add)
    _check_word_count(payload, word_count, add)
    _check_on_topic(payload, ps_text, add)
    _check_traceability(payload, add)
    _check_school_names(payload, ps_text, add)

    return CheckResult(tuple(findings), word_count)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check a personal statement against the ps-planner contract."
    )
    parser.add_argument("bundle", type=Path, help="path to the UTF-8 JSON PS bundle")
    parser.add_argument("--json", action="store_true", help="print structured JSON output")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        payload = json.loads(args.bundle.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError) as exc:
        print(f"[ERROR] cannot read {args.bundle}: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"[ERROR] invalid JSON in {args.bundle}: {exc.msg}", file=sys.stderr)
        return 2

    result = check_ps(payload)
    if args.json:
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    else:
        for finding in result.findings:
            print(f"[{finding.severity.upper()}] {finding.code}: {finding.message}")
        status = "PASS" if result.ok else "FAIL"
        print(
            f"[{status}] {result.word_count} word(s): "
            f"{len(result.errors)} error(s), {len(result.warnings)} warning(s)"
        )
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
