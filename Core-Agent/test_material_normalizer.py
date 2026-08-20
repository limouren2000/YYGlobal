"""Unit tests for the Core-Agent material requirement normalizer."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from material_normalizer import (
    MaterialNormalizer,
    material_slot,
    normalize_material_name,
    normalize_materials,
)


class NormalizeMaterialNameTests(unittest.TestCase):
    def test_maps_letter_phrasing_to_recommendations(self) -> None:
        raw = "We request 3 letters, at least two of which are from faculty or recent employers."
        self.assertEqual(normalize_material_name(raw), "Recommendations")

    def test_maps_plural_recommendations(self) -> None:
        self.assertEqual(normalize_material_name("Submit two recommendations."), "Recommendations")
        self.assertEqual(normalize_material_name("Please provide 2 references."), "Recommendations")

    def test_maps_transcript_sentence_to_transcripts(self) -> None:
        raw = "A PDF of your most recent transcript from each college and/or university."
        self.assertEqual(normalize_material_name(raw), "Transcripts")

    def test_maps_english_proficiency(self) -> None:
        self.assertEqual(normalize_material_name("English proficiency"), "English proficiency")
        self.assertEqual(normalize_material_name("TOEFL"), "English proficiency")

    def test_maps_gre_gmat(self) -> None:
        self.assertEqual(normalize_material_name("GRE / GMAT"), "GRE / GMAT")
        self.assertEqual(normalize_material_name("GRE scores are optional."), "GRE / GMAT")

    def test_keeps_unrecognized_text_verbatim(self) -> None:
        self.assertEqual(normalize_material_name("academic records"), "academic records")


class NormalizeMaterialsTests(unittest.TestCase):
    def test_collapses_raw_sentences_to_labels_and_dedupes(self) -> None:
        raw = [
            "CV / Resume",
            "Statement of Purpose / Essays",
            "Transcripts",
            "English proficiency",
            "GRE / GMAT",
            "A PDF of your most recent transcript from each college.",
            "Unofficial transcripts are accepted for the application process.",
            "Please upload your most recent résumé or curriculum vitae in PDF format.",
            "You must include a concise one- or two-page essay describing your research interests.",
            "We request 3 letters, at least two of which are from faculty or recent employers.",
            "GRE scores are optional.",
        ]
        self.assertEqual(
            normalize_materials(raw),
            [
                "CV / Resume",
                "Statement of Purpose / Essays",
                "Transcripts",
                "English proficiency",
                "GRE / GMAT",
                "Recommendations",
            ],
        )


class MaterialSlotTests(unittest.TestCase):
    def test_maps_official_names_to_asset_slots(self) -> None:
        self.assertEqual(material_slot("English proficiency"), "language")
        self.assertEqual(material_slot("GRE / GMAT"), "gre")
        self.assertEqual(material_slot("We request 3 letters, at least two of which are from faculty."), "recommendation")
        self.assertEqual(material_slot("Transcripts"), "transcript")
        self.assertEqual(material_slot("CV / Resume"), "cv")

    def test_unknown_material_gets_other_slot(self) -> None:
        self.assertEqual(material_slot("academic records"), "other_academic_records")


class RunTests(unittest.TestCase):
    def test_run_returns_labels_and_slots(self) -> None:
        result = MaterialNormalizer().run(
            ["We request 3 letters, at least two of which are from faculty."]
        )
        self.assertEqual(result["materials"], ["Recommendations"])
        self.assertEqual(result["slots"], {"Recommendations": "recommendation"})


if __name__ == "__main__":
    unittest.main()
