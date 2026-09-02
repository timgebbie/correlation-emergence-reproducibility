"""Regression tests for the v2.1.0 Figure 12 recovery gate."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
import unittest

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from functions.integrity import accepted_input_errors


CONFIG_PATH = ROOT / "config/config-v2.1.0.json"
CHECK_PATH = ROOT / "diagnostics/figure-12-order-book-shock-checks-v2.1.csv"
SUMMARY_PATH = ROOT / "outputs/figure-12-order-book-shock-summary-v2.1.csv"
ARCHIVE_PATH = ROOT / "outputs/figure-12-order-book-shock-recovery-v2.1.npz"
FIGURE_STEM = ROOT / "figures/figure-12-order-book-shock-recovery-v2"
INSERT_PATH = ROOT / "source/source-v2/ORDER-BOOK-SHOCK-RECOVERY-v2.1.tex"


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class OrderBookShockRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    def test_configuration_and_accepted_inputs(self) -> None:
        self.assertEqual(self.config["schema_version"], "2.1.0")
        self.assertEqual(self.config["public_parent_tag"], "v2.0.0")
        scientific_inputs = [
            record
            for record in self.config["accepted_inputs"]
            if record.get("role") != "doi_bearing_public_readme"
        ]
        self.assertFalse(accepted_input_errors(scientific_inputs))
        self.assertEqual(self.config["model"]["cancellation_rates"], [0.0, 0.0])
        self.assertEqual(
            self.config["figure"]["boundary_window_relative_to_pre_event"],
            [-0.8, 1.2],
        )
        self.assertTrue(self.config["figure"]["full_profile_inset"])

    def test_all_generated_checks_pass(self) -> None:
        checks = _rows(CHECK_PATH)
        self.assertEqual(len(checks), 37)
        self.assertEqual(len({row["check_id"] for row in checks}), 37)
        self.assertTrue(all(row["status"] == "Verified" for row in checks))
        self.assertEqual({row["software_version"] for row in checks}, {"2.1.0"})

    def test_summary_records_scientific_differences(self) -> None:
        summary = _rows(SUMMARY_PATH)
        self.assertEqual(len(summary), 1)
        row = summary[0]
        self.assertEqual(row["result_label"], "figure_12_order_book_shock_recovery_verified")
        self.assertEqual(int(row["failed_checks"]), 0)
        self.assertEqual(float(row["maximum_cancellation_contribution"]), 0.0)
        self.assertEqual(row["post_event_simple_boundary_registered"], "False")
        self.assertEqual(row["post_event_boundary_marker"], "last_registered_pre_event_boundary")
        self.assertEqual(row["positive_cancellation_sensitivity_run"], "False")

    def test_archive_has_literal_nine_panel_objects(self) -> None:
        with np.load(ARCHIVE_PATH, allow_pickle=False) as archive:
            self.assertEqual(archive["densities"].shape, (9, 2, 201))
            self.assertEqual(archive["arrival_contributions"].shape, (9, 2, 201))
            self.assertEqual(archive["cancellation_contributions"].shape, (9, 2, 201))
            self.assertEqual(archive["impulse_contributions"].shape, (9, 2, 201))
            self.assertEqual(archive["coupling_contributions"].shape, (9, 2, 201))
            np.testing.assert_array_equal(
                archive["snapshot_lag_steps"], np.asarray([0, 0, 1, 4, 10, 20, 40, 80, 160])
            )
            np.testing.assert_array_equal(
                archive["snapshot_lag_seconds"], np.asarray([0.0, 0.0, 0.5, 2.0, 5.0, 10.0, 20.0, 40.0, 80.0])
            )
            self.assertFalse(bool(archive["price_is_registered"][1, 0]))
            self.assertTrue(np.all(archive["price_is_registered"][2:]))
            self.assertEqual(float(np.max(np.abs(archive["cancellation_contributions"]))), 0.0)
            self.assertLessEqual(float(np.max(archive["ledger_errors"][2:])), 5e-15)
            self.assertAlmostEqual(float(archive["event_filled_quantity"][0]), 0.05, places=14)

    def test_figure_pair_and_resolution(self) -> None:
        self.assertTrue(FIGURE_STEM.with_suffix(".pdf").is_file())
        self.assertTrue(FIGURE_STEM.with_suffix(".png").is_file())
        with Image.open(FIGURE_STEM.with_suffix(".png")) as image:
            self.assertEqual(image.size, (4500, 3600))
            self.assertIn(image.mode, {"RGB", "RGBA"})

    def test_caption_and_discussion_state_differences_neutrally(self) -> None:
        text = INSERT_PATH.read_text(encoding="utf-8")
        for phrase in (
            r"$\nu_1=\nu_2=0$",
            "removal curve is identically zero",
            "zero-density interval",
            "last registered boundary $p_1^-$",
            "does not assert numerical",
            "substantially relaxed but remains displaced",
            "it is not independently rescaled",
        ):
            self.assertIn(phrase, text)
        self.assertNotIn("defect", text.lower())


if __name__ == "__main__":
    unittest.main()
