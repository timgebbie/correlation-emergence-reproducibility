"""Regression and output tests for the v1.7.7 corrected coupling gate."""

from __future__ import annotations

import ast
import csv
import json
import unittest
from pathlib import Path

import numpy as np

from functions.integrity import accepted_input_errors

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "config-v1.7.7.json"
CHECK_PATH = ROOT / "diagnostics" / "corrected-coupling-recovery-checks-v1.7.csv"
CURVE_PATH = ROOT / "outputs" / "corrected-coupling-recovery-curves-v1.7.csv"
RATE_PATH = ROOT / "outputs" / "corrected-coupling-rate-summary-v1.7.csv"
RESPONSE_PATH = ROOT / "outputs" / "corrected-coupling-response-v1.7.csv"
SUMMARY_PATH = ROOT / "outputs" / "corrected-coupling-recovery-summary-v1.7.csv"
ARCHIVE_PATH = ROOT / "outputs" / "corrected-coupling-validation-paths-v1.7.npz"
DENSITY_PATH = ROOT / "outputs" / "corrected-coupling-density-snapshots-v1.7.csv"
SCRIPT_PATH = ROOT / "scripts" / "29_run_corrected_coupling_recovery.py"
SOURCE_PATH = ROOT / "source" / "source-v2" / "CORRECTED-COUPLING-RECOVERY-v1.7.tex"


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class CorrectedCouplingRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.checks = _rows(CHECK_PATH)
        cls.curves = _rows(CURVE_PATH)
        cls.rates = _rows(RATE_PATH)
        cls.responses = _rows(RESPONSE_PATH)
        cls.densities = _rows(DENSITY_PATH)
        cls.summary = _rows(SUMMARY_PATH)

    def test_accepted_v176_inputs_are_exact(self) -> None:
        self.assertEqual(self.config["accepted_parent"], "v1.7.6")
        self.assertEqual(
            self.config["accepted_parent_commit"],
            "ed7565a1d8d261e329d2a0a74071af0fb6c85497",
        )
        self.assertFalse(accepted_input_errors(self.config["accepted_inputs"]))

    def test_split_implementation_and_layer_boundary(self) -> None:
        architecture = self.config["architecture"]
        self.assertEqual(architecture["production_type"], "TranslationModeCoupling")
        self.assertEqual(len(architecture["implementation_split"]["corrected_target"]), 3)
        self.assertEqual(architecture["operational_dynamics"], "uniform_fixed_grid_only")
        self.assertEqual(architecture["calendar_observation"], "identity_clock_only")
        self.assertEqual(architecture["subordination"], "not_active_in_this_component_gate")
        self.assertEqual(architecture["legacy_nonuniform_state_update"], "forbidden")
        self.assertEqual(architecture["calendar_interpolation"], "forbidden")
        self.assertEqual(architecture["combined_curve_refit"], "forbidden")

    def test_generated_checks_are_complete(self) -> None:
        self.assertEqual(len(self.checks), 38)
        self.assertEqual(len({row["check_id"] for row in self.checks}), 38)
        self.assertTrue(all(row["status"] == "Verified" for row in self.checks))
        self.assertEqual({row["software_version"] for row in self.checks}, {"1.7.7"})

    def test_summary_records_recovery_and_thresholds(self) -> None:
        self.assertEqual(len(self.summary), 1)
        row = self.summary[0]
        policy = self.config["acceptance_policy"]
        self.assertEqual(row["result_label"], "recovered")
        self.assertEqual(row["deterministic_gate"], "passed")
        self.assertLessEqual(
            float(row["maximum_exponential_rate_relative_error"]),
            float(policy["deterministic_rate_relative_error_maximum"]),
        )
        self.assertLessEqual(
            float(row["maximum_local_rate_relative_error"]),
            float(policy["deterministic_rate_relative_error_maximum"]),
        )
        self.assertLessEqual(
            float(row["normalized_covariance_rmse"]),
            float(policy["curve_absolute_rmse_maximum"]),
        )
        self.assertLessEqual(
            float(row["return_correlation_rmse"]),
            float(policy["curve_absolute_rmse_maximum"]),
        )
        self.assertEqual(float(row["normalized_covariance_coverage"]), 1.0)
        self.assertEqual(float(row["return_correlation_coverage"]), 1.0)

    def test_curve_contract_and_two_estimands(self) -> None:
        self.assertEqual(len(self.curves), 20)
        lags = np.asarray([float(row["lag_seconds"]) for row in self.curves])
        self.assertTrue(np.all(np.diff(lags) > 0.0))
        for row in self.curves:
            lag = float(row["lag_seconds"])
            x = 0.025 * lag
            survival = 1.0 - np.exp(-x)
            expected_covariance = 1.0 - survival / x
            expected_correlation = (x - survival) / (x + survival)
            self.assertAlmostEqual(
                float(row["analytical_normalized_covariance"]),
                expected_covariance,
            )
            self.assertAlmostEqual(
                float(row["analytical_exact_return_correlation"]),
                expected_correlation,
            )
            self.assertEqual(row["clock"], "identity")
            self.assertGreater(float(row["frozen_covariance_scale"]), 0.0)

    def test_signed_rates_and_grid_convergence(self) -> None:
        primary = [row for row in self.rates if row["record_type"] == "primary_signed_perturbation"]
        grids = [row for row in self.rates if row["record_type"] == "grid_convergence"]
        self.assertEqual(len(primary), 8)
        self.assertEqual(len(grids), 3)
        self.assertEqual(
            {np.sign(float(row["book_one_displacement"])) for row in primary},
            {-1.0, 1.0},
        )
        self.assertTrue(all(row["sign_preserved"] == "True" for row in primary))
        self.assertTrue(all(row["receiving_sign_correct"] == "True" for row in primary))
        self.assertTrue(
            all(float(row["projection_relative_residual"]) == 0.0 for row in primary)
        )
        errors = np.asarray(
            [float(row["exponential_rate_relative_error"]) for row in grids]
        )
        self.assertTrue(np.all(np.diff(errors) < 0.0))

    def test_response_rows_reconstruct_the_ratios(self) -> None:
        self.assertEqual(len(self.responses), 1288)
        groups: dict[str, list[dict[str, str]]] = {}
        for row in self.responses:
            groups.setdefault(row["record_index"], []).append(row)
        self.assertEqual(len(groups), 8)
        self.assertTrue(all(len(rows) == 161 for rows in groups.values()))
        for rows in groups.values():
            self.assertEqual(int(rows[0]["operational_step"]), 0)
            self.assertEqual(int(rows[-1]["operational_step"]), 160)
            for row in rows:
                expected = float(row["coupled_spread"]) / float(row["control_spread"])
                self.assertAlmostEqual(float(row["paired_spread_ratio"]), expected)

    def test_figure_archive_and_source_overlay(self) -> None:
        for suffix in ("pdf", "png"):
            path = ROOT / "figures" / f"figure-08-corrected-translation-mode-coupling-v2.{suffix}"
            self.assertGreater(path.stat().st_size, 1000)
        with np.load(ARCHIVE_PATH) as archive:
            self.assertEqual(archive["validation_prices"].shape, (32, 4001, 2))
            self.assertEqual(archive["validation_lag_steps"].shape, (20,))
            self.assertEqual(archive["calibration_lag_steps"].shape, (4,))
            self.assertGreater(float(archive["frozen_covariance_scale"]), 0.0)
        self.assertEqual(len(self.densities), 603)
        self.assertEqual(
            {float(row["time_seconds"]) for row in self.densities},
            {0.0, 20.0, 80.0},
        )
        for time in (0.0, 20.0, 80.0):
            rows = [row for row in self.densities if float(row["time_seconds"]) == time]
            self.assertEqual(len(rows), 201)
            self.assertEqual([int(row["grid_index"]) for row in rows], list(range(201)))
        initial = [row for row in self.densities if float(row["time_seconds"]) == 0.0][0]
        final = [row for row in self.densities if float(row["time_seconds"]) == 80.0][0]
        self.assertLess(
            abs(float(final["book_1_boundary_log_price"])),
            abs(float(initial["book_1_boundary_log_price"])),
        )
        source = SOURCE_PATH.read_text(encoding="utf-8")
        self.assertIn(r"\ell_T^{(j,k)}", source)
        self.assertIn("closure assumption", source)
        self.assertIn("source-v1 manuscript remains unchanged", source)

    def test_recovery_script_excludes_legacy_clock_and_subordination(self) -> None:
        tree = ast.parse(
            SCRIPT_PATH.read_text(encoding="utf-8"), filename=str(SCRIPT_PATH)
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                self.assertFalse(module.startswith("functions.legacy"))
                self.assertNotIn("clock", module)
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        for forbidden_call in (
            "subordinate_two_book_previous_refresh(",
            "subordinate_operational_path(",
            "np.interp(",
            "scipy.interpolate",
        ):
            self.assertNotIn(forbidden_call, source)


if __name__ == "__main__":
    unittest.main()
