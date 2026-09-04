from __future__ import annotations

import ast
import csv
import hashlib
import json
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "config-v1.9.0.json"
CURVE_PATH = ROOT / "outputs" / "final-estimator-aware-epps-curves-v1.9.csv"
SUMMARY_PATH = ROOT / "outputs" / "final-estimator-aware-epps-summary-v1.9.csv"
CHECK_PATH = ROOT / "diagnostics" / "final-estimator-aware-epps-checks-v1.9.csv"
SCRIPT_PATH = ROOT / "scripts" / "36_generate_final_epps_integration.py"
FIGURE_STEMS = (
    "figure-07-final-estimator-aware-epps-v2",
    "figure-07a-clock-only-epps-v2",
    "figure-07b-coupling-only-epps-v2",
    "figure-07c-combined-epps-v2",
)


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class FinalEstimatorAwareEppsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.curves = _rows(CURVE_PATH)
        cls.summary = _rows(SUMMARY_PATH)
        cls.checks = _rows(CHECK_PATH)

    def test_parent_architecture_and_curve_inventory(self) -> None:
        self.assertEqual(self.config["accepted_parent"], "v1.8.3")
        architecture = self.config["architecture"]
        self.assertEqual(architecture["operational_dynamics"], "uniform_fixed_grid_only")
        self.assertEqual(
            architecture["calendar_observation"],
            "book_specific_previous_refresh_after_operational_completion",
        )
        self.assertEqual(architecture["calendar_interpolation"], "forbidden")
        self.assertEqual(architecture["legacy_nonuniform_state_update"], "forbidden")
        self.assertEqual(len(self.config["required_curves"]), 7)

    def test_all_generated_checks_pass(self) -> None:
        self.assertEqual(len(self.checks), 24)
        self.assertEqual({row["status"] for row in self.checks}, {"Verified"})
        self.assertEqual({row["software_version"] for row in self.checks}, {"1.9.0"})

    def test_curve_contract_and_exact_lags(self) -> None:
        self.assertEqual(len(self.curves), 20)
        self.assertEqual(
            [float(row["lag_seconds"]) for row in self.curves],
            [float(value) for value in self.config["registered_lags_seconds"]],
        )
        self.assertEqual({row["fit_policy"] for row in self.curves}, {"frozen_no_retuning"})

    def test_leading_order_product_reconstructs(self) -> None:
        for row in self.curves:
            self.assertAlmostEqual(
                float(row["leading_order_product"]),
                float(row["clock_only_theory"]) * float(row["coupling_only_theory"]),
            )

    def test_final_curves_are_exact_accepted_source_joins(self) -> None:
        combined = _rows(ROOT / "outputs" / "combined-no-refit-curves-v1.7.csv")
        for final, source in zip(self.curves, combined, strict=True):
            self.assertEqual(
                float(final["clock_only_simulation"]),
                float(source["accepted_clock_thick_boundary"]),
            )
            self.assertEqual(
                float(final["coupling_only_simulation"]),
                float(source["accepted_corrected_coupling"]),
            )
            self.assertEqual(
                float(final["combined_simulation"]),
                float(source["thick_simulated_combined_covariance"]),
            )
            self.assertEqual(
                float(final["estimator_aware_finite_grid_finite_step_theory"]),
                float(source["thick_exact_reduced_same_clock_covariance"]),
            )

    def test_estimator_aware_curve_improves_on_product(self) -> None:
        self.assertEqual(len(self.summary), 1)
        row = self.summary[0]
        self.assertEqual(row["result_label"], "final_estimator_aware_integration_established")
        self.assertLess(
            float(row["combined_estimator_aware_rmse"]),
            float(row["combined_leading_order_product_rmse"]),
        )
        self.assertGreaterEqual(float(row["combined_estimator_aware_coverage"]), 0.9)
        self.assertEqual(row["parameters_refitted"], "False")

    def test_common_display_scale_and_figure_pair(self) -> None:
        display = self.config["display_contract"]
        self.assertEqual(display["shared_x_scale_seconds"], [0.0, 410.0])
        self.assertEqual(display["shared_y_scale"], [0.0, 1.1])
        self.assertEqual(display["aggregation_axis"], "linear")
        self.assertEqual(
            self.config["output_contract"]["standalone_figure_stems"],
            list(FIGURE_STEMS[1:]),
        )
        for stem in FIGURE_STEMS:
            for suffix in ("pdf", "png"):
                path = ROOT / "figures" / f"{stem}.{suffix}"
                self.assertGreater(path.stat().st_size, 1000)

    def test_standalone_png_canvases_are_square(self) -> None:
        for stem in FIGURE_STEMS[1:]:
            payload = (ROOT / "figures" / f"{stem}.png").read_bytes()
            self.assertEqual(payload[:8], b"\x89PNG\r\n\x1a\n")
            width, height = struct.unpack(">II", payload[16:24])
            self.assertEqual(width, height)
            self.assertGreaterEqual(width, 1200)

    def test_route_is_assembly_only(self) -> None:
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(SCRIPT_PATH))
        imported_modules = {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        self.assertFalse(any(module.startswith("functions.operational") for module in imported_modules))
        for forbidden in (
            "default_rng(",
            "np.random",
            "np.interp(",
            "curve_fit(",
            "least_squares(",
            "minimize(",
        ):
            self.assertNotIn(forbidden, source)

    def test_source_v1_paper_remains_frozen(self) -> None:
        digest = hashlib.sha256(
            (ROOT / "source/source-v1/CATG-RD2Epps-v3-arXiv.tex").read_bytes()
        ).hexdigest()
        self.assertEqual(
            digest,
            "48eea98a6fb084d6ecc397bede4c107a44cae947e16271d66a7041e2997afb5a",
        )

    def test_supplementary_text_states_the_time_layer_separation(self) -> None:
        source = (
            ROOT / "source/source-v2/FINAL-ESTIMATOR-AWARE-EPPS-v1.9.tex"
        ).read_text(encoding="utf-8")
        self.assertIn("uniform operational-time grid", source)
        self.assertIn("only after the", source)
        self.assertIn("not a fitted replacement", source)


if __name__ == "__main__":
    unittest.main()
