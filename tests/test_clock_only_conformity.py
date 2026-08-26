"""Regression and output-contract tests for the v1.7.4 clock-only gate."""

from __future__ import annotations

import csv
import hashlib
import json
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


class ClockOnlyConformityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads((ROOT / "config" / "config-v1.7.4.json").read_text())
        with (ROOT / "outputs" / "clock-only-conformity-curves-v1.7.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            cls.curves = list(csv.DictReader(handle))
        with (ROOT / "outputs" / "clock-only-conformity-summary-v1.7.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            cls.summary = list(csv.DictReader(handle))
        with (ROOT / "diagnostics" / "clock-only-conformity-checks-v1.7.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            cls.checks = list(csv.DictReader(handle))

    def test_rate_correction_distinguishes_book_and_minimum_wait_rates(self) -> None:
        correction = self.config["theory_rate_correction"]
        self.assertEqual(correction["equal_book_refresh_rates_per_second"], [0.1, 0.1])
        self.assertEqual(correction["pooled_minimum_wait_rate_per_second"], 0.2)
        self.assertEqual(correction["accepted_equal_rate_curve"], "F(lambda_clock*Delta_t)")

    def test_architecture_keeps_general_inverse_and_refresh_reference_distinct(self) -> None:
        architecture = self.config["architecture"]
        self.assertEqual(architecture["operational_dynamics"], "uniform_fixed_grid_only")
        self.assertIn("realised_operational_interval_overlap", architecture["general_inverse_clock_status"])
        self.assertEqual(architecture["previous_refresh_status"], "separate_exact_equal_rate_reference_benchmark")

    def test_curve_contract_and_exact_values(self) -> None:
        self.assertEqual(len(self.curves), 40)
        self.assertEqual({row["tier"] for row in self.curves}, {"reduced_reference", "thick_boundary"})
        for row in self.curves:
            lag = float(row["lag_seconds"])
            expected = float(1.0 - (1.0 - np.exp(-0.1 * lag)) / (0.1 * lag))
            old = float(1.0 - (1.0 - np.exp(-0.2 * lag)) / (0.2 * lag))
            self.assertAlmostEqual(float(row["exact_equal_rate_curve"]), expected)
            self.assertAlmostEqual(float(row["old_pooled_rate_envelope"]), old)

    def test_result_labels_preserve_qualified_boundary(self) -> None:
        labels = {row["tier"]: row["result_label"] for row in self.summary}
        self.assertEqual(labels["reduced_reference"], "recovered")
        self.assertEqual(labels["thick_boundary"], "qualified_nonconformity")

    def test_generated_checks_have_no_failures(self) -> None:
        self.assertEqual(len(self.checks), 22)
        self.assertNotIn("Failed", {row["status"] for row in self.checks})
        qualified = [row for row in self.checks if row["status"] == "Qualified"]
        self.assertEqual([row["check_id"] for row in qualified], ["S7CLK-16"])

    def test_figure_and_boundary_archive_exist(self) -> None:
        for suffix in ("pdf", "png"):
            path = ROOT / "figures" / f"figure-19-clock-only-conformity-v1.{suffix}"
            self.assertGreater(path.stat().st_size, 1000)
        with np.load(ROOT / "outputs" / "clock-only-boundary-paths-v1.7.npz") as archive:
            self.assertEqual(archive["calibration_identity_prices"].shape, (16, 4401, 2))
            self.assertEqual(archive["validation_operational_prices"].shape, (32, 4401, 2))

    def test_source_records_equal_rate_correction(self) -> None:
        accepted = ROOT / "source" / "source-v1" / "CATG-RD2Epps-v3-arXiv.tex"
        self.assertEqual(
            hashlib.sha256(accepted.read_bytes()).hexdigest(),
            "48eea98a6fb084d6ecc397bede4c107a44cae947e16271d66a7041e2997afb5a",
        )
        source = (
            ROOT / "source" / "source-v2" / "CLOCK-RATE-CORRECTION-v1.7.tex"
        ).read_text()
        self.assertIn("equal-rate previous-refresh benchmark", source)
        self.assertIn("does not replace $\\lambda^{\\rm clk}$", source)
        self.assertIn("exact realised operational-interval intersection", source)


if __name__ == "__main__":
    unittest.main()
