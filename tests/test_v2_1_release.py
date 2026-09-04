"""Focused tests for the v2.1.0 release surface."""

from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path

from scripts.run_all import ACTIVE_STEPS


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config/config-v2.1.0-release.json"
CHECK_PATH = ROOT / "diagnostics/v2.1.0-release-checks.csv"


class V21ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    def test_release_configuration_is_streamlined(self) -> None:
        self.assertEqual(self.config["schema_version"], "2.1.0")
        self.assertEqual(
            self.config["scope"],
            "release_conformity_and_science_consistency",
        )
        self.assertNotIn("gate", self.config)
        self.assertNotIn("accepted_parent", self.config)

    def test_release_metadata_is_consistent(self) -> None:
        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        self.assertIn('version: "2.1.0"', citation)
        self.assertNotIn("date-released:", citation)
        self.assertTrue((ROOT / "RELEASE-NOTES-v2.1.0.md").is_file())

    def test_publication_contract_is_fixed_and_minimal(self) -> None:
        publication = self.config["publication_contract"]
        self.assertEqual(
            set(publication),
            {"version", "tag", "release_title", "archive_name", "single_release_archive"},
        )
        self.assertEqual(publication["version"], "v2.1.0")
        self.assertEqual(publication["tag"], "v2.1.0")
        self.assertTrue(publication["single_release_archive"])

    def test_scientific_limits_are_explicit(self) -> None:
        scientific = self.config["scientific_contract"]
        self.assertFalse(scientific["parameters_refitted"])
        self.assertFalse(scientific["endogenous_memory_claim"])
        self.assertFalse(scientific["empirical_calibration_claim"])
        self.assertEqual(scientific["accepted_stage_7_qualifications"], 6)

    def test_release_audit_is_last_active_step(self) -> None:
        self.assertEqual(
            ACTIVE_STEPS[-1][1],
            "scripts/44_run_v2_1_release_audit.py",
        )

    def test_release_audit_has_no_failures(self) -> None:
        with CHECK_PATH.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 30)
        self.assertTrue(all(row["status"] == "Verified" for row in rows))


if __name__ == "__main__":
    unittest.main()
