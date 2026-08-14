"""Audit exported program sources and evidence before an Agent cites them.

The input is a JSON object with ``sources`` and ``evidence`` arrays.  The
contract mirrors the core fields used by YYGlobal's ``ProgramSource`` and
``EvidenceChunk`` records while remaining framework-independent.

Example:
    python Core-Agent/evidence_bundle_auditor.py evidence.json
    python Core-Agent/evidence_bundle_auditor.py evidence.json --json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

DEFAULT_REQUIRED_FIELDS = ("deadline", "materials")
KNOWN_SOURCE_STATUSES = {"verified", "fetched_needs_review", "pending", "failed"}


@dataclass(frozen=True)
class Finding:
    """One deterministic audit finding."""

    severity: str
    code: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "path": self.path,
            "message": self.message,
        }


@dataclass(frozen=True)
class AuditResult:
    """Structured evidence bundle audit result."""

    source_count: int
    evidence_count: int
    required_fields: tuple[str, ...]
    findings: tuple[Finding, ...]

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
            "source_count": self.source_count,
            "evidence_count": self.evidence_count,
            "required_fields": list(self.required_fields),
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "findings": [item.as_dict() for item in self.findings],
        }


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _normalize_required_fields(fields: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(
        dict.fromkeys(item.strip() for item in fields if item.strip())
    )
    if not normalized:
        raise ValueError("required fields cannot be empty")
    return normalized


def _parse_timestamp(value: Any) -> datetime | None:
    if not _non_empty_string(value):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _valid_official_url(value: Any) -> bool:
    if not _non_empty_string(value):
        return False
    try:
        parsed = urlsplit(value.strip())
        hostname = parsed.hostname
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and bool(hostname)
        and parsed.username is None
        and parsed.password is None
    )


def _today() -> date:
    """Return the local calendar date from a timezone-aware timestamp."""
    return datetime.now().astimezone().date()


def audit_bundle(
    payload: Any,
    *,
    required_fields: Iterable[str] = DEFAULT_REQUIRED_FIELDS,
    as_of: date | None = None,
    max_age_days: int = 90,
) -> AuditResult:
    """Validate source integrity, evidence links, and required field coverage."""
    required = _normalize_required_fields(required_fields)
    if max_age_days < 0:
        raise ValueError("max_age_days must be >= 0")
    audit_date = as_of or _today()
    findings: list[Finding] = []

    def add(severity: str, code: str, path: str, message: str) -> None:
        findings.append(Finding(severity, code, path, message))

    if not isinstance(payload, dict):
        add("error", "invalid_bundle", "$", "bundle must be a JSON object")
        return AuditResult(0, 0, required, tuple(findings))

    raw_sources = payload.get("sources")
    raw_evidence = payload.get("evidence")
    if not isinstance(raw_sources, list):
        add("error", "invalid_sources", "$.sources", "sources must be an array")
        sources: list[Any] = []
    else:
        sources = raw_sources
        if not sources:
            add("error", "empty_sources", "$.sources", "at least one source is required")

    if not isinstance(raw_evidence, list):
        add("error", "invalid_evidence", "$.evidence", "evidence must be an array")
        evidence_items: list[Any] = []
    else:
        evidence_items = raw_evidence

    source_eligible: dict[str, bool] = {}
    duplicate_source_ids: set[str] = set()
    for index, source in enumerate(sources):
        path = f"$.sources[{index}]"
        if not isinstance(source, dict):
            add("error", "invalid_source", path, "source must be an object")
            continue

        source_id = source.get("id")
        id_valid = _non_empty_string(source_id)
        if not id_valid:
            add("error", "invalid_source_id", f"{path}.id", "id must be a non-empty string")
        else:
            source_id = source_id.strip()
            if source_id in source_eligible:
                duplicate_source_ids.add(source_id)
                add(
                    "error",
                    "duplicate_source_id",
                    f"{path}.id",
                    f"source id {source_id!r} is duplicated",
                )

        url_valid = _valid_official_url(source.get("url"))
        if not url_valid:
            add(
                "error",
                "invalid_source_url",
                f"{path}.url",
                "official source URL must be HTTPS, include a host, and contain no credentials",
            )

        source_type = source.get("source_type")
        type_valid = source_type == "official"
        if not type_valid:
            add(
                "error",
                "source_not_official",
                f"{path}.source_type",
                "source_type must be 'official'",
            )

        status = source.get("status")
        status_known = isinstance(status, str) and status in KNOWN_SOURCE_STATUSES
        if not status_known:
            add(
                "error",
                "invalid_source_status",
                f"{path}.status",
                f"status must be one of {sorted(KNOWN_SOURCE_STATUSES)}",
            )
        elif status != "verified":
            add(
                "warning",
                "source_needs_review",
                f"{path}.status",
                f"source status is {status!r}, not 'verified'",
            )

        fetched_at = _parse_timestamp(source.get("fetched_at"))
        timestamp_valid = fetched_at is not None
        if not timestamp_valid:
            add(
                "error",
                "invalid_fetched_at",
                f"{path}.fetched_at",
                "fetched_at must be an ISO 8601 timestamp with a timezone",
            )
        else:
            age_days = (audit_date - fetched_at.date()).days
            if age_days < 0:
                timestamp_valid = False
                add(
                    "error",
                    "future_fetched_at",
                    f"{path}.fetched_at",
                    f"fetched_at is {-age_days} day(s) after the audit date",
                )
            elif age_days > max_age_days:
                add(
                    "warning",
                    "stale_source",
                    f"{path}.fetched_at",
                    f"source is {age_days} days old; maximum is {max_age_days}",
                )

        if id_valid:
            source_eligible[source_id] = (
                url_valid
                and type_valid
                and status == "verified"
                and status_known
                and timestamp_valid
            )

    for source_id in duplicate_source_ids:
        source_eligible[source_id] = False

    covered_fields: set[str] = set()
    evidence_keys: set[tuple[str, str, str]] = set()
    for index, evidence in enumerate(evidence_items):
        path = f"$.evidence[{index}]"
        if not isinstance(evidence, dict):
            add("error", "invalid_evidence_item", path, "evidence must be an object")
            continue

        source_id = evidence.get("source_id")
        source_valid = _non_empty_string(source_id)
        if not source_valid:
            add(
                "error",
                "invalid_evidence_source",
                f"{path}.source_id",
                "source_id must be a non-empty string",
            )
        else:
            source_id = source_id.strip()
            if source_id not in source_eligible:
                source_valid = False
                add(
                    "error",
                    "unknown_evidence_source",
                    f"{path}.source_id",
                    f"source_id {source_id!r} does not reference a source",
                )

        field = evidence.get("field")
        field_valid = _non_empty_string(field)
        if not field_valid:
            add("error", "invalid_evidence_field", f"{path}.field", "field must be a non-empty string")
        else:
            field = field.strip()

        quote = evidence.get("quote")
        quote_valid = _non_empty_string(quote)
        if not quote_valid:
            add("error", "invalid_evidence_quote", f"{path}.quote", "quote must be a non-empty string")
        else:
            quote = quote.strip()

        confidence = evidence.get("confidence")
        confidence_valid = (
            not isinstance(confidence, bool)
            and isinstance(confidence, (int, float))
            and math.isfinite(confidence)
            and 0 <= confidence <= 1
        )
        if not confidence_valid:
            add(
                "error",
                "invalid_confidence",
                f"{path}.confidence",
                "confidence must be a finite number between 0 and 1",
            )

        if source_valid and field_valid and quote_valid:
            key = (source_id, field, quote)
            if key in evidence_keys:
                add(
                    "warning",
                    "duplicate_evidence",
                    path,
                    "the same source, field, and quote already appeared",
                )
            evidence_keys.add(key)
            if confidence_valid and source_eligible.get(source_id, False):
                covered_fields.add(field)

    for field in required:
        if field not in covered_fields:
            add(
                "error",
                "missing_verified_evidence",
                "$.evidence",
                f"required field {field!r} has no valid evidence from a verified official source",
            )

    return AuditResult(
        source_count=len(sources),
        evidence_count=len(evidence_items),
        required_fields=required,
        findings=tuple(findings),
    )


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc


def _parse_required_fields(value: str) -> tuple[str, ...]:
    try:
        return _normalize_required_fields(value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit official program sources and their evidence links."
    )
    parser.add_argument("bundle", type=Path, help="path to the UTF-8 JSON bundle")
    parser.add_argument(
        "--required-fields",
        type=_parse_required_fields,
        default=DEFAULT_REQUIRED_FIELDS,
        help="comma-separated fields that require verified evidence (default: deadline,materials)",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=90,
        help="warn when a source is older than this many days (default: 90)",
    )
    parser.add_argument(
        "--as-of",
        type=_parse_date,
        default=_today(),
        help="audit date for deterministic checks, YYYY-MM-DD (default: today)",
    )
    parser.add_argument("--json", action="store_true", help="print structured JSON output")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.max_age_days < 0:
        print("[ERROR] --max-age-days must be >= 0", file=sys.stderr)
        return 2

    try:
        payload = json.loads(args.bundle.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError) as exc:
        print(f"[ERROR] cannot read {args.bundle}: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"[ERROR] invalid JSON in {args.bundle}: {exc.msg}", file=sys.stderr)
        return 2

    result = audit_bundle(
        payload,
        required_fields=args.required_fields,
        as_of=args.as_of,
        max_age_days=args.max_age_days,
    )
    if args.json:
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    else:
        for item in result.findings:
            print(f"[{item.severity.upper()}] {item.code} {item.path}: {item.message}")
        status = "PASS" if result.ok else "FAIL"
        print(
            f"[{status}] audited {result.source_count} source(s) and "
            f"{result.evidence_count} evidence item(s): "
            f"{len(result.errors)} error(s), {len(result.warnings)} warning(s)"
        )
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
