"""Regression and output tests for the v1.7.11 combined no-refit gate."""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import unittest
from pathlib import Path

import numpy as np

from functions.integrity import accepted_input_errors

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "config-v1.7.11.json"
CHECK_PATH = ROOT / "diagnostics" / "combined-no-refit-checks-v1.7.csv"
CURVE_PATH = ROOT / "outputs" / "combined-no-refit-curves-v1.7.csv"
SUMMARY_PATH = ROOT / "outputs" / "combined-no-refit-summary-v1.7.csv"
CLOCK_PATH = ROOT / "outputs" / "combined-no-refit-clock-rates-v1.7.csv"
ARCHIVE_PATH = ROOT / "outputs" / "combined-no-refit-paths-v1.7.npz"
SCRIPT_PATH = ROOT / "scripts" / "30_run_combined_no_refit_prediction.py"
SOURCE_PATH = (
    ROOT / "source" / "source-v2" / "COMBINED-NO-REFIT-PREDICTION-v1.7.tex"
)


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class CombinedNoRefitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.checks = _rows(CHECK_PATH)
        cls.curves = _rows(CURVE_PATH)
        cls.summary = _rows(SUMMARY_PATH)
        cls.clock_rates = _rows(CLOCK_PATH)

    def test_accepted_v177_inputs_are_exact(self) -> None:
        self.assertEqual(self.config["accepted_parent"], "v1.7.7")
        self.assertEqual(
            self.config["accepted_parent_commit"],
            "0e82ec1e61cc39594113281abacd10f85799f168",
        )
        self.assertFalse(accepted_input_errors(self.config["accepted_inputs"]))

    def test_architecture_is_operational_then_calendar_without_refit(self) -> None:
        architecture = self.config["architecture"]
        self.assertEqual(architecture["operational_dynamics"], "uniform_fixed_grid_only")
        self.assertEqual(
            architecture["calendar_observation"],
            "independent_equal_rate_previous_refresh_after_operational_completion",
        )
        self.assertEqual(architecture["calendar_interpolation"], "forbidden")
        self.assertEqual(architecture["legacy_nonuniform_state_update"], "forbidden")
        self.assertFalse(architecture["clock_owns_operational_dynamics"])
        self.assertEqual(architecture["component_parameter_refit"], "forbidden")
        self.assertEqual(architecture["combined_curve_refit"], "forbidden")

    def test_generated_checks_record_qualified_scientific_result(self) -> None:
        self.assertEqual(len(self.checks), 38)
        self.assertEqual(len({row["check_id"] for row in self.checks}), 38)
        self.assertNotIn("Failed", {row["status"] for row in self.checks})
        self.assertEqual(
            {row["check_id"] for row in self.checks if row["status"] == "Qualified"},
            {"S7CM-20", "S7CM-27", "S7CM-31", "S7CM-34", "S7CM-35"},
        )
        self.assertEqual({row["software_version"] for row in self.checks}, {"1.7.11"})

    def test_reduced_exact_estimator_gate_recovers(self) -> None:
        rows = {row["tier"]: row for row in self.summary}
        reduced = rows["reduced_estimator_reference"]
        policy = self.config["acceptance_policy"]
        self.assertEqual(reduced["result_label"], "recovered")
        self.assertLessEqual(
            float(reduced["covariance_rmse"]),
            float(policy["reduced_exact_covariance_rmse_maximum"]),
        )
        self.assertLessEqual(
            float(reduced["correlation_rmse"]),
            float(policy["reduced_exact_correlation_rmse_maximum"]),
        )
        self.assertLessEqual(
            float(reduced["covariance_standardized_rmse"]),
            float(policy["standardized_rmse_maximum"]),
        )
        self.assertLessEqual(
            float(reduced["correlation_standardized_rmse"]),
            float(policy["standardized_rmse_maximum"]),
        )
        self.assertEqual(float(reduced["covariance_coverage"]), 1.0)
        self.assertEqual(float(reduced["correlation_coverage"]), 1.0)

    def test_summary_separates_approximation_and_boundary_residuals(self) -> None:
        self.assertEqual(len(self.summary), 3)
        rows = {row["tier"]: row for row in self.summary}
        product = rows["leading_order_product"]
        thick = rows["thick_boundary_combined"]
        self.assertEqual(product["result_label"], "qualified_nonconformity")
        self.assertEqual(thick["result_label"], "qualified_nonconformity")
        self.assertGreater(
            float(product["product_rmse"]),
            float(self.config["acceptance_policy"]["leading_order_product_rmse_maximum"]),
        )
        self.assertGreater(
            float(thick["covariance_rmse"]),
            float(self.config["acceptance_policy"]["boundary_specific_rmse_maximum"]),
        )
        self.assertLessEqual(
            float(thick["correlation_rmse"]),
            float(self.config["acceptance_policy"]["boundary_specific_rmse_maximum"]),
        )

    def test_curve_contract_products_and_residuals(self) -> None:
        self.assertEqual(len(self.curves), 20)
        lags = np.asarray([float(row["lag_seconds"]) for row in self.curves])
        self.assertTrue(np.all(np.diff(lags) > 0.0))
        for row in self.curves:
            clock = float(row["analytical_clock_factor"])
            coupling = float(row["analytical_coupling_factor"])
            product = float(row["analytical_leading_order_product"])
            accepted_product = float(row["accepted_component_product"])
            reduced_exact = float(row["reduced_exact_conditional_covariance"])
            thick = float(row["thick_simulated_combined_covariance"])
            self.assertAlmostEqual(product, clock * coupling)
            self.assertAlmostEqual(
                accepted_product,
                float(row["accepted_clock_thick_boundary"])
                * float(row["accepted_corrected_coupling"]),
            )
            self.assertAlmostEqual(
                float(row["exact_reduced_minus_product"]), reduced_exact - product
            )
            self.assertAlmostEqual(
                float(row["thick_minus_exact_reduced"]),
                thick - float(row["thick_exact_reduced_same_clock_covariance"]),
            )
            self.assertAlmostEqual(
                float(row["thick_minus_accepted_component_product"]),
                thick - accepted_product,
            )
            self.assertAlmostEqual(
                float(row["thick_minus_analytical_product"]), thick - product
            )
            self.assertEqual(row["fit_policy"], "no_component_or_combined_refit")

    def test_realised_clock_rates_match_registered_equal_rates(self) -> None:
        self.assertEqual(len(self.clock_rates), 4)
        policy = float(self.config["acceptance_policy"]["clock_rate_relative_error_maximum"])
        self.assertEqual({row["book"] for row in self.clock_rates}, {"1", "2"})
        self.assertEqual(
            {row["tier"] for row in self.clock_rates},
            {"reduced_reference", "thick_boundary_holdout"},
        )
        for row in self.clock_rates:
            self.assertEqual(float(row["target_rate_per_second"]), 0.1)
            self.assertLessEqual(float(row["relative_error"]), policy)

    def test_archive_shapes_and_frozen_scale(self) -> None:
        with np.load(ARCHIVE_PATH) as archive:
            self.assertEqual(archive["thick_validation_prices"].shape, (32, 4001, 2))
            self.assertEqual(archive["reduced_observed_components"].shape, (64, 20, 3))
            self.assertEqual(archive["reduced_exact_components"].shape, (64, 20, 3))
            self.assertEqual(archive["thick_observed_components"].shape, (32, 20, 3))
            self.assertEqual(archive["thick_exact_components"].shape, (32, 20, 3))
            self.assertEqual(archive["lags_seconds"].shape, (20,))
            self.assertEqual(
                float(archive["frozen_covariance_scale"]),
                float(
                    self.config["frozen_components"][
                        "frozen_thick_boundary_covariance_scale"
                    ]
                ),
            )

    def test_figure_and_source_overlay_exist(self) -> None:
        for suffix in ("pdf", "png"):
            path = ROOT / "figures" / f"figure-22-combined-no-refit-prediction-v1.{suffix}"
            self.assertGreater(path.stat().st_size, 1000)
        source = SOURCE_PATH.read_text(encoding="utf-8")
        self.assertIn("leading-order separability approximation", source)
        self.assertIn("exact estimator-aware reference", source)
        self.assertIn("source-v1 manuscript remains unchanged", source)

    def test_script_excludes_legacy_nonuniform_and_refitting_paths(self) -> None:
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(SCRIPT_PATH))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                self.assertFalse(module.startswith("functions.legacy"))
        for forbidden in (
            "np.interp(",
            "scipy.interpolate",
            "curve_fit(",
            "least_squares(",
            "minimize(",
        ):
            self.assertNotIn(forbidden, source)
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "source/source-v1/CATG-RD2Epps-v3-arXiv.tex").read_bytes()
            ).hexdigest(),
            "48eea98a6fb084d6ecc397bede4c107a44cae947e16271d66a7041e2997afb5a",
        )


if __name__ == "__main__":
    unittest.main()
