"""Tests for the v1.8.1 paired single-trade impact gate."""

from __future__ import annotations

import csv
import json
import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from functions.integrity import accepted_input_errors


CONFIG_PATH = ROOT / "config" / "config-v1.8.1.json"
CHECK_PATH = ROOT / "diagnostics" / "single-trade-impact-checks-v1.8.csv"
CURVE_PATH = ROOT / "outputs" / "single-trade-impact-curves-v1.8.csv"
MEMBER_PATH = ROOT / "outputs" / "single-trade-impact-members-v1.8.csv"
EVENT_PATH = ROOT / "outputs" / "single-trade-impact-events-v1.8.csv"
SUMMARY_PATH = ROOT / "outputs" / "single-trade-impact-summary-v1.8.csv"
ARCHIVE_PATH = ROOT / "outputs" / "single-trade-impact-paths-v1.8.npz"
PROVENANCE_PATH = ROOT / "provenance" / "SINGLE-TRADE-IMPACT-v1.8.md"
SUPPLEMENT_PATH = ROOT / "source" / "source-v2" / "TRANSLATION-MODE-NUMERICAL-ARCHITECTURE-v1.8.tex"


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class SingleTradeImpactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    def test_parent_and_accepted_inputs_are_exact(self) -> None:
        self.assertEqual(self.config["schema_version"], "1.8.1")
        self.assertEqual(self.config["accepted_parent"], "v1.8.0")
        self.assertFalse(accepted_input_errors(self.config["accepted_inputs"]))

    def test_time_layers_and_event_measurement_are_separate(self) -> None:
        architecture = self.config["architecture"]
        self.assertEqual(architecture["operational_dynamics"], "uniform_fixed_grid_only")
        self.assertEqual(architecture["calendar_interpolation"], "forbidden")
        self.assertEqual(architecture["legacy_nonuniform_state_update"], "forbidden")
        source = (ROOT / "functions" / "events" / "impact.py").read_text(encoding="utf-8")
        self.assertNotIn("default_rng", source)
        self.assertNotIn("poisson_refresh", source)
        self.assertNotIn("subordinate_two_book", source)

    def test_complete_matrix_and_output_counts(self) -> None:
        curves = _rows(CURVE_PATH)
        members = _rows(MEMBER_PATH)
        events = _rows(EVENT_PATH)
        self.assertEqual(len(curves), 96)
        self.assertEqual(len(members), 1536)
        self.assertEqual(len(events), 32)
        self.assertEqual(
            {(row["event_book"], row["response_book"]) for row in curves},
            {("0", "0"), ("0", "1"), ("1", "0"), ("1", "1")},
        )
        self.assertEqual({row["measurement_domain"] for row in curves}, {"operational", "calendar"})

    def test_all_generated_checks_pass(self) -> None:
        checks = _rows(CHECK_PATH)
        self.assertEqual(len(checks), 44)
        self.assertEqual(len({row["check_id"] for row in checks}), 44)
        self.assertTrue(all(row["status"] == "Verified" for row in checks))
        self.assertEqual({row["software_version"] for row in checks}, {"1.8.1"})

    def test_summary_establishes_single_trade_impact(self) -> None:
        summary = _rows(SUMMARY_PATH)
        self.assertEqual(len(summary), 1)
        row = summary[0]
        self.assertEqual(row["result_label"], "single_trade_impact_established")
        self.assertEqual(int(row["verified_checks"]), 44)
        self.assertEqual(int(row["failed_checks"]), 0)
        self.assertGreater(float(row["operational_own_impact_at_zero_seconds"]), 0.05)
        self.assertGreater(float(row["operational_cross_impact_at_twenty_seconds"]), 0.005)

    def test_scale_aware_side_symmetry_is_explicit(self) -> None:
        policy = self.config["acceptance_policy"]
        self.assertEqual(
            policy["buy_sell_symmetry_metric"],
            "maximum_absolute_side_difference_normalized_by_domain_peak_own_impact",
        )
        summary = _rows(SUMMARY_PATH)[0]
        self.assertLessEqual(
            float(summary["buy_sell_domain_scaled_difference"]),
            float(policy["maximum_buy_sell_domain_scaled_difference"]),
        )
        self.assertGreater(float(summary["buy_sell_cellwise_relative_diagnostic"]), 0.15)

    def test_path_archive_shapes(self) -> None:
        with np.load(ARCHIVE_PATH, allow_pickle=False) as archive:
            self.assertEqual(archive["base_standard_normals"].shape, (8, 800, 2))
            self.assertEqual(archive["control_prices"].shape, (8, 801, 2))
            self.assertEqual(archive["shocked_prices"].shape, (8, 2, 2, 801, 2))
            self.assertEqual(archive["calendar_shocked_prices"].shape, (8, 2, 2, 801, 2))
            self.assertEqual(archive["response_lags_seconds"].shape, (12,))

    def test_figure_pair_exists(self) -> None:
        stem = ROOT / "figures" / "figure-09-single-trade-impact-v2"
        self.assertTrue(stem.with_suffix(".pdf").is_file())
        self.assertTrue(stem.with_suffix(".png").is_file())

    def test_supplementary_contrast_is_registered(self) -> None:
        contract = self.config["supplementary_material_contract"]
        self.assertTrue(contract["required_for_v2_release"])
        self.assertFalse(contract["independent_numerical_selector_width"])
        self.assertTrue(contract["resolved_front_thickness_retained"])
        self.assertEqual(contract["equivalence_level"], "reaction_front_projection_not_pointwise_source_identity")
        provenance = PROVENANCE_PATH.read_text(encoding="utf-8")
        supplement = SUPPLEMENT_PATH.read_text(encoding="utf-8")
        for phrase in ("not pointwise identical", "front is infinitely thin", "source-v1 paper"):
            self.assertIn(phrase, provenance)
        for phrase in ("not pointwise identical", "not treated as infinitely thin", "not an additional coupling parameter"):
            self.assertIn(phrase, supplement)


if __name__ == "__main__":
    unittest.main()
