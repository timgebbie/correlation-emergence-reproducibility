"""Tests for the v1.8.2 scheduled meta-order impact gate."""

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

from functions.events import MetaOrderSchedule
from functions.integrity import accepted_input_errors


CONFIG_PATH = ROOT / "config" / "config-v1.8.2.json"
CHECK_PATH = ROOT / "diagnostics" / "meta-order-impact-checks-v1.8.csv"
TRAJECTORY_PATH = ROOT / "outputs" / "meta-order-impact-trajectory-v1.8.csv"
TRAJECTORY_MEMBER_PATH = ROOT / "outputs" / "meta-order-impact-trajectory-members-v1.8.csv"
RELAXATION_PATH = ROOT / "outputs" / "meta-order-impact-relaxation-v1.8.csv"
RELAXATION_MEMBER_PATH = ROOT / "outputs" / "meta-order-impact-relaxation-members-v1.8.csv"
EVENT_PATH = ROOT / "outputs" / "meta-order-impact-events-v1.8.csv"
SCHEDULE_PATH = ROOT / "outputs" / "meta-order-impact-schedules-v1.8.csv"
SUMMARY_PATH = ROOT / "outputs" / "meta-order-impact-summary-v1.8.csv"
ARCHIVE_PATH = ROOT / "outputs" / "meta-order-impact-paths-v1.8.npz"
PROVENANCE_PATH = ROOT / "provenance" / "META-ORDER-IMPACT-v1.8.md"
SUPPLEMENT_PATH = ROOT / "source" / "source-v2" / "META-ORDER-NUMERICAL-ARCHITECTURE-v1.8.tex"


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class MetaOrderImpactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    def test_parent_and_accepted_inputs_are_exact(self) -> None:
        self.assertEqual(self.config["schema_version"], "1.8.2")
        self.assertEqual(self.config["accepted_parent"], "v1.8.1")
        self.assertFalse(accepted_input_errors(self.config["accepted_inputs"]))

    def test_schedule_expands_to_distinct_child_market_events(self) -> None:
        schedule = MetaOrderSchedule("M", 1, -1, (3, 7, 12), (0.1, 0.2, 0.3))
        events = schedule.events()
        self.assertEqual(schedule.child_count, 3)
        self.assertAlmostEqual(schedule.total_quantity, 0.6)
        np.testing.assert_allclose(schedule.cumulative_quantities, (0.1, 0.3, 0.6))
        self.assertEqual([event.operational_step for event in events], [3, 7, 12])
        self.assertEqual([event.child_index for event in events], [0, 1, 2])
        self.assertEqual({event.meta_order_id for event in events}, {"M"})
        self.assertEqual({event.event_type for event in events}, {"market_order"})

    def test_schedule_rejects_ambiguous_or_invalid_children(self) -> None:
        invalid = (
            ("", 0, 1, (1, 2), (0.1, 0.1)),
            ("M", 2, 1, (1, 2), (0.1, 0.1)),
            ("M", 0, 0, (1, 2), (0.1, 0.1)),
            ("M", 0, 1, (2, 2), (0.1, 0.1)),
            ("M", 0, 1, (1,), (0.1,)),
            ("M", 0, 1, (1, 2), (0.1, 0.0)),
        )
        for arguments in invalid:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                MetaOrderSchedule(*arguments)

    def test_operational_meta_order_layer_owns_no_clock_or_rng(self) -> None:
        source = (ROOT / "functions" / "events" / "meta_order.py").read_text(encoding="utf-8")
        for token in (
            "default_rng",
            "np.random",
            "poisson_refresh",
            "subordinate_two_book",
            "step_uniform",
            "legacy_coupling",
        ):
            self.assertNotIn(token, source)

    def test_all_generated_checks_pass(self) -> None:
        checks = _rows(CHECK_PATH)
        self.assertEqual(len(checks), 50)
        self.assertEqual(len({row["check_id"] for row in checks}), 50)
        self.assertTrue(all(row["status"] == "Verified" for row in checks))
        self.assertEqual({row["software_version"] for row in checks}, {"1.8.2"})

    def test_output_counts_domains_and_matrix_are_complete(self) -> None:
        trajectory = _rows(TRAJECTORY_PATH)
        trajectory_members = _rows(TRAJECTORY_MEMBER_PATH)
        relaxation = _rows(RELAXATION_PATH)
        relaxation_members = _rows(RELAXATION_MEMBER_PATH)
        events = _rows(EVENT_PATH)
        schedules = _rows(SCHEDULE_PATH)
        self.assertEqual(
            (len(trajectory), len(trajectory_members), len(relaxation),
             len(relaxation_members), len(events), len(schedules)),
            (64, 1024, 144, 2304, 256, 2),
        )
        self.assertEqual({row["measurement_domain"] for row in trajectory}, {"operational", "calendar"})
        self.assertEqual(
            {(row["event_book"], row["response_book"]) for row in trajectory},
            {("0", "0"), ("0", "1"), ("1", "0"), ("1", "1")},
        )
        self.assertEqual({row["schedule_id"] for row in schedules}, {"fast", "slow"})
        self.assertTrue(all(float(row["filled_quantity"]) == 0.05 for row in events))

    def test_summary_separates_execution_catchup_and_relaxation(self) -> None:
        row = _rows(SUMMARY_PATH)[0]
        self.assertEqual(row["result_label"], "meta_order_impact_established")
        self.assertEqual(int(row["verified_checks"]), 50)
        self.assertEqual(int(row["failed_checks"]), 0)
        self.assertGreater(float(row["fast_slow_final_own_absolute_difference"]), 0.1)
        self.assertGreater(float(row["minimum_post_completion_own_relaxation_fraction"]), 0.7)
        self.assertGreater(float(row["minimum_peak_post_completion_cross_catchup_fraction"]), 0.05)

    def test_path_archive_shapes(self) -> None:
        with np.load(ARCHIVE_PATH, allow_pickle=False) as archive:
            self.assertEqual(archive["base_standard_normals"].shape, (8, 1000, 2))
            self.assertEqual(archive["control_prices"].shape, (8, 1001, 2))
            self.assertEqual(archive["shocked_prices"].shape, (2, 8, 2, 2, 1001, 2))
            self.assertEqual(archive["trajectory_responses"].shape, (2, 8, 2, 2, 2, 4, 2))
            self.assertEqual(archive["relaxation_responses"].shape, (2, 8, 2, 2, 2, 9, 2))

    def test_figure_pair_exists(self) -> None:
        stem = ROOT / "figures" / "figure-10-meta-order-impact-v2"
        self.assertTrue(stem.with_suffix(".pdf").is_file())
        self.assertTrue(stem.with_suffix(".png").is_file())

    def test_provenance_and_supplement_state_scientific_boundaries(self) -> None:
        provenance = PROVENANCE_PATH.read_text(encoding="utf-8")
        supplement = SUPPLEMENT_PATH.read_text(encoding="utf-8")
        for phrase in (
            "not one large density shock",
            "true participation rate is not identified",
            "post-completion peak",
            "source-v1 paper remains frozen",
        ):
            self.assertIn(phrase, provenance)
        for phrase in (
            "uniform operational grid",
            "previous-refresh subordination",
            "not a participation rate",
            "translation-mode numerical source",
        ):
            self.assertIn(phrase, supplement)


if __name__ == "__main__":
    unittest.main()
