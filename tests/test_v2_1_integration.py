"""Regression tests for the v2.1.0 reader-facing integration gate."""

from __future__ import annotations

import csv
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECK_PATH = ROOT / "diagnostics/v2.1.0-integration-checks.csv"


class V21IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        completed = subprocess.run(
            [sys.executable, "scripts/42_run_v2_1_integration_verification.py"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode:
            raise AssertionError(completed.stdout + completed.stderr)

    def test_all_integration_checks_are_verified(self) -> None:
        with CHECK_PATH.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 32)
        self.assertTrue(all(row["status"] == "Verified" for row in rows))

    def test_frozen_v2_supplement_is_retained(self) -> None:
        self.assertTrue((ROOT / "SUPPLEMENTARY-MATERIAL-v2.0.0.tex").is_file())
        self.assertTrue(
            (ROOT / "supplementary-materials/SUPPLEMENTARY-MATERIAL-v2.0.0.pdf").is_file()
        )

    def test_v2_1_supplement_is_separate(self) -> None:
        self.assertTrue((ROOT / "SUPPLEMENTARY-MATERIAL-v2.1.0.tex").is_file())
        self.assertTrue(
            (ROOT / "supplementary-materials/SUPPLEMENTARY-MATERIAL-v2.1.0.pdf").is_file()
        )


if __name__ == "__main__":
    unittest.main()
