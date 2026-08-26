"""Tests for target book clocks and explicit pathwise subordination."""

from __future__ import annotations

import csv
import json
import sys
import unittest
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from functions.observation import (
    BookClockPath,
    book_clock_from_intervals,
    identity_book_clock,
    inverse_clock_previous_state,
    subordinate_operational_values,
    subordinate_two_book_prices,
)


class ObservationSubordinationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.operational_times = np.asarray([0.0, 0.5, 1.0, 1.5, 2.0])
        self.first = book_clock_from_intervals(
            self.operational_times,
            np.asarray([0.4, 0.6, 0.3, 0.7]),
            law="fixture",
            stream_id="book-1",
            seed=11,
        )
        self.second = book_clock_from_intervals(
            self.operational_times,
            np.asarray([0.6, 0.4, 0.7, 0.3]),
            law="fixture",
            stream_id="book-2",
            seed=12,
        )

    def test_clock_requires_uniform_operational_grid_and_positive_intervals(self) -> None:
        with self.assertRaisesRegex(ValueError, "start at zero"):
            book_clock_from_intervals(
                np.asarray([0.1, 0.6]),
                np.asarray([0.5]),
                law="fixture",
                stream_id="bad",
            )
        with self.assertRaisesRegex(ValueError, "uniform"):
            book_clock_from_intervals(
                np.asarray([0.0, 0.5, 1.1]),
                np.asarray([0.5, 0.6]),
                law="fixture",
                stream_id="bad",
            )
        with self.assertRaisesRegex(ValueError, "strictly positive"):
            book_clock_from_intervals(
                self.operational_times,
                np.asarray([0.4, 0.6, 0.0, 1.0]),
                law="fixture",
                stream_id="bad",
            )
        with self.assertRaisesRegex(ValueError, "one value per operational step"):
            book_clock_from_intervals(
                self.operational_times,
                np.asarray([0.5, 0.5]),
                law="fixture",
                stream_id="bad",
            )

    def test_clock_inputs_are_copied_and_immutable(self) -> None:
        operational = self.operational_times.copy()
        intervals = np.asarray([0.4, 0.6, 0.3, 0.7])
        clock = book_clock_from_intervals(
            operational,
            intervals,
            law="fixture",
            stream_id="copy-test",
        )
        operational[1] = 99.0
        intervals[0] = 99.0
        self.assertEqual(clock.operational_times[1], 0.5)
        self.assertEqual(clock.calendar_intervals[0], 0.4)
        with self.assertRaises(ValueError):
            clock.calendar_times[1] = 9.0

    def test_public_clock_object_cannot_bypass_path_validation(self) -> None:
        with self.assertRaisesRegex(ValueError, "cumulative"):
            BookClockPath(
                operational_times=self.operational_times,
                calendar_times=np.asarray([0.0, 0.4, 1.0, 1.4, 2.0]),
                calendar_intervals=np.asarray([0.4, 0.6, 0.3, 0.7]),
                law="fixture",
                stream_id="invalid-direct-construction",
                seed=None,
            )

    def test_clock_metadata_and_horizon_are_explicit(self) -> None:
        self.assertEqual(self.first.law, "fixture")
        self.assertEqual(self.first.stream_id, "book-1")
        self.assertEqual(self.first.seed, 11)
        self.assertEqual(self.first.supported_calendar_horizon, 2.0)
        self.assertEqual(self.first.inverse_convention, "previous_completed_operational_state")

    def test_identity_clock_recovers_nodes_exactly(self) -> None:
        identity = identity_book_clock(self.operational_times, stream_id="identity")
        inverse = inverse_clock_previous_state(identity, self.operational_times)
        self.assertTrue(np.array_equal(identity.calendar_times, self.operational_times))
        self.assertTrue(np.array_equal(inverse.operational_indices, np.arange(5)))
        self.assertTrue(np.array_equal(inverse.operational_times, self.operational_times))

    def test_previous_completed_state_convention_between_nodes(self) -> None:
        queries = np.asarray([0.0, 0.39, 0.4, 0.99, 1.0, 1.29, 1.3, 2.0])
        inverse = inverse_clock_previous_state(self.first, queries)
        self.assertTrue(
            np.array_equal(inverse.operational_indices, [0, 0, 1, 1, 2, 2, 3, 4])
        )

    def test_endpoint_is_included_but_extrapolation_is_rejected(self) -> None:
        endpoint = inverse_clock_previous_state(self.first, np.asarray([2.0]))
        self.assertEqual(endpoint.operational_indices[0], 4)
        with self.assertRaisesRegex(ValueError, "precede zero"):
            inverse_clock_previous_state(self.first, np.asarray([-0.1]))
        with self.assertRaisesRegex(ValueError, "supported horizon"):
            inverse_clock_previous_state(self.first, np.asarray([2.1]))

    def test_query_order_is_explicit(self) -> None:
        repeated = inverse_clock_previous_state(
            self.first, np.asarray([0.1, 0.1, 0.4])
        )
        self.assertTrue(np.array_equal(repeated.operational_indices, [0, 0, 1]))
        with self.assertRaisesRegex(ValueError, "nondecreasing"):
            inverse_clock_previous_state(self.first, np.asarray([0.4, 0.2]))

    def test_arbitrary_operational_field_is_subordinated_without_interpolation(self) -> None:
        field = np.column_stack((np.arange(5.0), np.arange(5.0) ** 2))
        result = subordinate_operational_values(
            field, self.first, np.asarray([0.2, 0.4, 0.8, 1.3])
        )
        self.assertTrue(np.array_equal(result, field[[0, 1, 1, 3]]))
        result[0, 0] = 99.0
        self.assertEqual(field[0, 0], 0.0)

    def test_two_book_subordination_uses_distinct_inverse_paths(self) -> None:
        prices = np.column_stack(
            (np.arange(5.0), 10.0 + np.arange(5.0))
        )
        result = subordinate_two_book_prices(
            prices, (self.first, self.second), np.asarray([0.0, 0.5, 1.0, 1.5, 2.0])
        )
        self.assertTrue(
            np.array_equal(
                result.operational_indices,
                [[0, 0], [1, 0], [2, 2], [3, 2], [4, 4]],
            )
        )
        self.assertTrue(
            np.array_equal(result.prices, [[0, 10], [1, 10], [2, 12], [3, 12], [4, 14]])
        )
        self.assertEqual(result.clock_stream_ids, ("book-1", "book-2"))

    def test_two_book_validation_rejects_mixed_operational_grids(self) -> None:
        other = book_clock_from_intervals(
            np.asarray([0.0, 0.25, 0.5, 0.75, 1.0]),
            np.asarray([0.5, 0.5, 0.5, 0.5]),
            law="fixture",
            stream_id="other-grid",
        )
        prices = np.zeros((5, 2))
        with self.assertRaisesRegex(ValueError, "same operational grid"):
            subordinate_two_book_prices(prices, (self.first, other), np.asarray([0.0]))
        with self.assertRaisesRegex(ValueError, "one explicit path per book"):
            subordinate_two_book_prices(prices, (self.first,), np.asarray([0.0]))

    def test_generated_evidence_contracts(self) -> None:
        with CHECK_PATH.open("r", encoding="utf-8", newline="") as handle:
            checks = list(csv.DictReader(handle))
        self.assertEqual(len(checks), 15)
        self.assertTrue(all(row["status"] == "Verified" for row in checks))
        with FIXTURE_PATH.open("r", encoding="utf-8", newline="") as handle:
            fixture = list(csv.DictReader(handle))
        self.assertEqual(len(fixture), 52)
        self.assertEqual({row["scenario"] for row in fixture}, {"identity", "book_specific"})
        self.assertEqual(
            {row["inverse_convention"] for row in fixture},
            {"previous_completed_operational_state"},
        )
        for row in fixture:
            self.assertEqual(float(row["calendar_price"]), float(row["operational_price"]))

    def test_observation_layer_is_separate_and_owns_no_rng(self) -> None:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            configuration = json.load(handle)
        self.assertEqual(configuration["schema_version"], "1.5.0")
        self.assertEqual(
            configuration["finite_grid_convention"],
            "previous_completed_operational_state",
        )
        for name in ("clocks.py", "subordination.py"):
            source = (PROJECT_ROOT / "functions" / "observation" / name).read_text(
                encoding="utf-8"
            )
            self.assertNotIn("functions.legacy", source)
            self.assertNotIn("functions.operational", source)
            self.assertNotIn("np.random", source)
            self.assertNotIn("np.interp", source)


CHECK_PATH = PROJECT_ROOT / "diagnostics" / "clock-subordination-checks-v1.5.csv"
FIXTURE_PATH = PROJECT_ROOT / "outputs" / "clock-subordination-fixture-v1.5.csv"
CONFIG_PATH = PROJECT_ROOT / "config" / "config-v1.5.json"


if __name__ == "__main__":
    unittest.main()
