"""Focused tests for the v2.1.0 R14 local release candidate."""

from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path

from scripts.run_all import ACTIVE_STEPS


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config/config-v2.1.0-release.json"
CHECK_PATH = ROOT / "diagnostics/v2.1.0-release-candidate-checks.csv"


class V21ReleaseCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    def test_r13_is_the_fixed_parent(self) -> None:
        self.assertEqual(
            self.config["accepted_parent"]["commit"],
            "d329b00d066c181ae416799688f41401e70c1a80",
        )
        self.assertEqual(
            self.config["accepted_parent"]["stage_bundle_sha256"],
            "57ea08936bbf3cd0aac2d497eab845e78b4789f6441620a0b03e57fd6a5aca16",
        )

    def test_candidate_metadata_is_consistent(self) -> None:
        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        self.assertIn('version: "2.1.0"', citation)
        self.assertNotIn("date-released:", citation)
        self.assertTrue((ROOT / "RELEASE-NOTES-v2.1.0.md").is_file())

    def test_publication_matches_v2_0_structure(self) -> None:
        publication = self.config["publication_contract"]
        self.assertEqual(publication["repository_state"], "untagged_v2.1.0_candidate")
        self.assertTrue(publication["push_untagged_state_first"])
        self.assertTrue(publication["inspect_and_correct_before_tag"])
        self.assertFalse(publication["tag_created"])
        self.assertFalse(publication["github_release_created"])
        self.assertFalse(publication["separate_verification_only_archive"])
        self.assertNotIn("remote_git_authorized", publication)
        self.assertNotIn("drive_upload_requires_gate_acceptance", publication)

    def test_scientific_limits_are_explicit(self) -> None:
        scientific = self.config["scientific_contract"]
        self.assertFalse(scientific["parameters_refitted"])
        self.assertFalse(scientific["endogenous_memory_claim"])
        self.assertFalse(scientific["empirical_calibration_claim"])
        self.assertEqual(scientific["accepted_stage_7_qualifications"], 6)

    def test_r14_audit_is_last_active_step(self) -> None:
        self.assertEqual(
            ACTIVE_STEPS[-1][1],
            "scripts/44_run_v2_1_release_candidate_audit.py",
        )

    def test_r14_audit_has_no_failures(self) -> None:
        with CHECK_PATH.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 30)
        self.assertTrue(all(row["status"] == "Verified" for row in rows))


if __name__ == "__main__":
    unittest.main()
