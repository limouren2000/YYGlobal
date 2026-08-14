"""Tests for the framework-independent evidence bundle auditor."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from evidence_bundle_auditor import audit_bundle, main

AUDIT_DATE = date(2026, 8, 13)


def valid_bundle() -> dict[str, object]:
    return {
        "sources": [
            {
                "id": "source-1",
                "url": "https://www.example.edu/program/admissions",
                "source_type": "official",
                "status": "verified",
                "fetched_at": "2026-08-01T08:30:00Z",
            }
        ],
        "evidence": [
            {
                "source_id": "source-1",
                "field": "deadline",
                "quote": "Applications close on December 1.",
                "confidence": 0.98,
            },
            {
                "source_id": "source-1",
                "field": "materials",
                "quote": "Submit a CV and two recommendation letters.",
                "confidence": 0.95,
            },
        ],
    }


class EvidenceBundleAuditorTests(unittest.TestCase):
    def test_accepts_complete_verified_bundle(self) -> None:
        result = audit_bundle(valid_bundle(), as_of=AUDIT_DATE)

        self.assertTrue(result.ok)
        self.assertEqual(result.findings, ())
        self.assertEqual(result.source_count, 1)
        self.assertEqual(result.evidence_count, 2)

    def test_reports_missing_required_field(self) -> None:
        bundle = valid_bundle()
        bundle["evidence"] = bundle["evidence"][:1]

        result = audit_bundle(bundle, as_of=AUDIT_DATE)

        self.assertFalse(result.ok)
        self.assertTrue(
            any(
                item.code == "missing_verified_evidence" and "materials" in item.message
                for item in result.errors
            )
        )

    def test_unverified_source_does_not_cover_required_fields(self) -> None:
        bundle = valid_bundle()
        bundle["sources"][0]["status"] = "fetched_needs_review"

        result = audit_bundle(bundle, as_of=AUDIT_DATE)

        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.warnings[0].code, "source_needs_review")
        self.assertEqual(
            [item.code for item in result.errors],
            ["missing_verified_evidence", "missing_verified_evidence"],
        )

    def test_rejects_non_https_or_credentialed_source_url(self) -> None:
        for url in (
            "http://www.example.edu/program",
            "https://user:secret@www.example.edu/program",
            "https://[invalid-host",
        ):
            with self.subTest(url=url):
                bundle = valid_bundle()
                bundle["sources"][0]["url"] = url

                result = audit_bundle(bundle, as_of=AUDIT_DATE)

                self.assertIn("invalid_source_url", [item.code for item in result.errors])

    def test_rejects_non_string_source_status_without_crashing(self) -> None:
        bundle = valid_bundle()
        bundle["sources"][0]["status"] = ["verified"]

        result = audit_bundle(bundle, as_of=AUDIT_DATE)

        self.assertIn("invalid_source_status", [item.code for item in result.errors])

    def test_rejects_duplicate_source_ids_as_ambiguous(self) -> None:
        bundle = valid_bundle()
        bundle["sources"].append(dict(bundle["sources"][0]))

        result = audit_bundle(bundle, as_of=AUDIT_DATE)

        codes = [item.code for item in result.errors]
        self.assertIn("duplicate_source_id", codes)
        self.assertEqual(codes.count("missing_verified_evidence"), 2)

    def test_rejects_unknown_evidence_source(self) -> None:
        bundle = valid_bundle()
        bundle["evidence"][0]["source_id"] = "missing-source"

        result = audit_bundle(bundle, as_of=AUDIT_DATE)

        self.assertIn("unknown_evidence_source", [item.code for item in result.errors])
        self.assertIn("missing_verified_evidence", [item.code for item in result.errors])

    def test_rejects_boolean_and_out_of_range_confidence(self) -> None:
        for confidence in (True, -0.1, 1.1, float("inf")):
            with self.subTest(confidence=confidence):
                bundle = valid_bundle()
                bundle["evidence"][0]["confidence"] = confidence

                result = audit_bundle(bundle, as_of=AUDIT_DATE)

                self.assertIn("invalid_confidence", [item.code for item in result.errors])

    def test_stale_source_is_a_non_failing_warning(self) -> None:
        bundle = valid_bundle()
        bundle["sources"][0]["fetched_at"] = "2026-01-01T00:00:00+00:00"

        result = audit_bundle(bundle, as_of=AUDIT_DATE, max_age_days=90)

        self.assertTrue(result.ok)
        self.assertEqual([item.code for item in result.warnings], ["stale_source"])

    def test_rejects_timestamp_without_timezone_and_future_timestamp(self) -> None:
        for fetched_at, expected_code in (
            ("2026-08-01T08:30:00", "invalid_fetched_at"),
            ("2026-08-14T00:00:00Z", "future_fetched_at"),
        ):
            with self.subTest(fetched_at=fetched_at):
                bundle = valid_bundle()
                bundle["sources"][0]["fetched_at"] = fetched_at

                result = audit_bundle(bundle, as_of=AUDIT_DATE)

                self.assertIn(expected_code, [item.code for item in result.errors])

    def test_cli_emits_json_and_uses_documented_exit_codes(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            json.dump(valid_bundle(), handle)
            bundle_path = Path(handle.name)
        self.addCleanup(bundle_path.unlink)
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            exit_code = main(
                [str(bundle_path), "--as-of", AUDIT_DATE.isoformat(), "--json"]
            )

        self.assertEqual(exit_code, 0)
        self.assertTrue(json.loads(output.getvalue())["ok"])

    def test_cli_returns_two_for_invalid_json(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write("not-json")
            bundle_path = Path(handle.name)
        self.addCleanup(bundle_path.unlink)

        with contextlib.redirect_stderr(io.StringIO()):
            exit_code = main([str(bundle_path)])

        self.assertEqual(exit_code, 2)


if __name__ == "__main__":
    unittest.main()
