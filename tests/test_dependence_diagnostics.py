"""Tests for the v1.8.3 mid-price and trade-sign dependence gate."""

from __future__ import annotations

import csv
import json
import sys
import unittest
from collections import defaultdict
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from functions.integrity import accepted_input_errors


CONFIG_PATH = ROOT / "config" / "config-v1.8.3.json"
CHECK_PATH = ROOT / "diagnostics" / "dependence-diagnostic-checks-v1.8.csv"
PRICE_CURVE_PATH = ROOT / "outputs" / "dependence-mid-price-acf-v1.8.csv"
PRICE_MEMBER_PATH = ROOT / "outputs" / "dependence-mid-price-acf-members-v1.8.csv"
SIGN_CURVE_PATH = ROOT / "outputs" / "dependence-trade-sign-acf-v1.8.csv"
SIGN_MEMBER_PATH = ROOT / "outputs" / "dependence-trade-sign-acf-members-v1.8.csv"
CALENDAR_SIGN_CURVE_PATH = ROOT / "outputs" / "dependence-calendar-sign-flow-acf-v1.8.csv"
CALENDAR_SIGN_MEMBER_PATH = ROOT / "outputs" / "dependence-calendar-sign-flow-acf-members-v1.8.csv"
AGREEMENT_PATH = ROOT / "outputs" / "dependence-sign-agreement-v1.8.csv"
EVENT_PATH = ROOT / "outputs" / "dependence-event-tape-v1.8.csv"
CLOCK_PATH = ROOT / "outputs" / "dependence-clock-rates-v1.8.csv"
SUMMARY_PATH = ROOT / "outputs" / "dependence-summary-v1.8.csv"
ARCHIVE_PATH = ROOT / "outputs" / "dependence-paths-v1.8.npz"
REPRESENTATIVE_PATH_PATH = ROOT / "outputs" / "dependence-representative-path-v1.8.csv"
RETURN_DISTRIBUTION_PATH = ROOT / "outputs" / "dependence-return-distribution-v1.8.csv"
RETURN_QQ_PATH = ROOT / "outputs" / "dependence-return-qq-v1.8.csv"
PROVENANCE_PATH = ROOT / "provenance" / "MID-PRICE-TRADE-SIGN-DEPENDENCE-v1.8.md"
SUPPLEMENT_PATH = ROOT / "source" / "source-v2" / "DEPENDENCE-DIAGNOSTICS-v1.8.tex"


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class DependenceDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    def test_parent_and_accepted_inputs_are_exact(self) -> None:
        self.assertEqual(self.config["schema_version"], "1.8.3")
        self.assertEqual(self.config["accepted_parent"], "v1.8.2")
        self.assertFalse(accepted_input_errors(self.config["accepted_inputs"]))

    def test_operational_event_tape_owns_no_clock_or_rng(self) -> None:
        source = (ROOT / "functions" / "events" / "tape.py").read_text(encoding="utf-8")
        for token in (
            "default_rng",
            "np.random",
            "poisson_refresh",
            "subordinate_two_book",
            "calendar_time",
            "legacy_nonuniform",
        ):
            self.assertNotIn(token, source)

    def test_all_generated_checks_pass(self) -> None:
        checks = _rows(CHECK_PATH)
        self.assertEqual(len(checks), 49)
        self.assertEqual(len({row["check_id"] for row in checks}), 49)
        self.assertTrue(all(row["status"] == "Verified" for row in checks))
        self.assertEqual({row["software_version"] for row in checks}, {"1.8.3"})

    def test_output_counts_and_domains_are_complete(self) -> None:
        price = _rows(PRICE_CURVE_PATH)
        price_members = _rows(PRICE_MEMBER_PATH)
        signs = _rows(SIGN_CURVE_PATH)
        sign_members = _rows(SIGN_MEMBER_PATH)
        calendar_signs = _rows(CALENDAR_SIGN_CURVE_PATH)
        calendar_sign_members = _rows(CALENDAR_SIGN_MEMBER_PATH)
        agreements = _rows(AGREEMENT_PATH)
        events = _rows(EVENT_PATH)
        clocks = _rows(CLOCK_PATH)
        self.assertEqual(
            tuple(map(len, (price, price_members, signs, sign_members,
                            calendar_signs, calendar_sign_members,
                            agreements, events, clocks))),
            (42, 672, 39, 624, 63, 1008, 3, 768, 16),
        )
        self.assertEqual(
            {row["measurement_domain"] for row in price},
            {"operational", "calendar_previous_refresh"},
        )
        conventions = {"ground_truth_aggressor", "quote_midpoint", "legacy_tick_rule"}
        self.assertEqual({row["sign_convention"] for row in signs}, conventions)
        self.assertEqual({row["sign_convention"] for row in calendar_signs}, conventions)

    def test_event_records_preserve_three_sign_conventions(self) -> None:
        events = _rows(EVENT_PATH)
        self.assertTrue(all(float(row["filled_quantity"]) == 0.015 for row in events))
        self.assertTrue(
            all(row["quote_midpoint_sign"] == row["ground_truth_aggressor_sign"] for row in events)
        )
        grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
        for row in events:
            grouped[(row["path_index"], row["book_index"])].append(row)
        self.assertEqual(len(grouped), 16)
        for rows in grouped.values():
            ordered = sorted(rows, key=lambda row: int(row["same_book_event_index"]))
            self.assertEqual(ordered[0]["legacy_tick_rule_sign"], "0")
        self.assertTrue(
            any(row["legacy_tick_rule_sign"] != row["ground_truth_aggressor_sign"] for row in events)
        )

    def test_increment_and_sign_autocorrelations_are_registered(self) -> None:
        price = _rows(PRICE_CURVE_PATH)
        signs = _rows(SIGN_CURVE_PATH)
        calendar_signs = _rows(CALENDAR_SIGN_CURVE_PATH)
        self.assertEqual({row["level_autocorrelation_included"] for row in price}, {"False"})
        for rows, lag_name, value_name in (
            (price, "lag_index", "mean_increment_autocorrelation"),
            (signs, "event_lag", "mean_sign_autocorrelation"),
            (calendar_signs, "calendar_lag_index", "mean_signed_flow_autocorrelation"),
        ):
            lag_zero = [row for row in rows if row[lag_name] == "0"]
            self.assertTrue(lag_zero)
            self.assertTrue(all(float(row[value_name]) == 1.0 for row in lag_zero))

    def test_summary_qualifies_the_finite_persistence_fixture(self) -> None:
        row = _rows(SUMMARY_PATH)[0]
        self.assertEqual(row["result_label"], "dependence_diagnostics_established")
        self.assertEqual((int(row["verified_checks"]), int(row["failed_checks"])), (49, 0))
        self.assertEqual(row["stage_8_status"], "closed_on_acceptance")
        self.assertAlmostEqual(float(row["quote_midpoint_ground_truth_agreement"]), 1.0)
        self.assertGreater(float(row["legacy_tick_ground_truth_agreement"]), 0.4)
        self.assertLess(float(row["legacy_tick_ground_truth_agreement"]), 0.99)

    def test_path_archive_shapes(self) -> None:
        with np.load(ARCHIVE_PATH, allow_pickle=False) as archive:
            self.assertEqual(archive["base_standard_normals"].shape, (8, 1400, 2))
            self.assertEqual(archive["declared_event_steps"].shape, (2, 48))
            self.assertEqual(archive["declared_ground_truth_signs"].shape, (8, 2, 48))
            self.assertEqual(archive["operational_prices"].shape, (8, 1401, 2))
            self.assertEqual(archive["calendar_prices"].shape, (8, 1401, 2))
            self.assertEqual(archive["event_sign_autocorrelations"].shape, (8, 2, 3, 13))
            self.assertEqual(archive["calendar_sign_flow_autocorrelations"].shape, (8, 2, 3, 21))

    def test_figure_pair_exists(self) -> None:
        stem = ROOT / "figures" / "figure-11-mid-price-trade-sign-autocorrelations-v2"
        self.assertTrue(stem.with_suffix(".pdf").is_file())
        self.assertTrue(stem.with_suffix(".png").is_file())
        paths = _rows(REPRESENTATIVE_PATH_PATH)
        distributions = _rows(RETURN_DISTRIBUTION_PATH)
        quantiles = _rows(RETURN_QQ_PATH)
        self.assertEqual((len(paths), len(distributions), len(quantiles)), (1401, 82, 102))
        self.assertEqual(len({row["path_index"] for row in paths}), 1)
        self.assertEqual(
            {row["selection_policy"] for row in paths},
            {"operational_return_rms_nearest_cross_path_median"},
        )
        self.assertEqual(
            {row["reference_status"] for row in distributions + quantiles},
            {"fixed_standard_normal_not_fitted"},
        )

    def test_provenance_and_supplement_state_scientific_boundaries(self) -> None:
        provenance = " ".join(PROVENANCE_PATH.read_text(encoding="utf-8").split())
        supplement = " ".join(SUPPLEMENT_PATH.read_text(encoding="utf-8").split())
        for phrase in (
            "finite persistent estimator fixture",
            "not endogenous long memory",
            "level autocorrelation is excluded",
            "source-v1 paper remains frozen",
        ):
            self.assertIn(phrase, provenance)
        for phrase in (
            "uniform operational event tape",
            "previous-refresh subordination",
            "three sign conventions",
            "not an empirical calibration",
        ):
            self.assertIn(phrase, supplement)


if __name__ == "__main__":
    unittest.main()
