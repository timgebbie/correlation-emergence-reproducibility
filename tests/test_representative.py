"""Tests for stable representative-path validation."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

import numpy as np

from functions.representative import (
    stable_nearest_median_index,
    validated_predeclared_nearest_median_index,
)


class RepresentativePathTests(unittest.TestCase):
    def test_release_policy_pins_only_accepted_display_paths(self) -> None:
        root = Path(__file__).resolve().parents[1]
        policy = json.loads(
            (root / "config/config-v2.1.0-representative-paths.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(policy["distance_tolerance_ulps"], 64)
        self.assertEqual(policy["figure_11"]["predeclared_path_index"], 4)
        self.assertEqual(policy["figure_13"]["predeclared_master_path_index"], 2)

    def test_unpinned_tie_uses_lowest_index(self) -> None:
        values = np.asarray([1.0, 3.0, 1.0, 3.0])
        self.assertEqual(
            stable_nearest_median_index(values, distance_tolerance_ulps=64), 0
        )

    def test_predeclared_member_of_exact_tie_is_retained(self) -> None:
        values = np.asarray([1.0, 3.0, 1.0, 3.0])
        self.assertEqual(
            validated_predeclared_nearest_median_index(
                values, predeclared_index=2, distance_tolerance_ulps=64
            ),
            2,
        )

    def test_roundoff_scale_tie_is_retained(self) -> None:
        values = np.asarray([0.9, 1.1, np.nextafter(0.9, 1.0), 1.3])
        self.assertEqual(
            validated_predeclared_nearest_median_index(
                values, predeclared_index=0, distance_tolerance_ulps=64
            ),
            0,
        )

    def test_non_nearest_predeclared_path_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validated_predeclared_nearest_median_index(
                np.asarray([0.0, 1.0, 1.1, 9.0]),
                predeclared_index=3,
                distance_tolerance_ulps=64,
            )

    def test_invalid_inputs_are_rejected(self) -> None:
        for values, index, ulps in (
            (np.asarray([]), 0, 64),
            (np.asarray([1.0, np.nan]), 0, 64),
            (np.asarray([1.0]), 1, 64),
            (np.asarray([1.0]), 0, 0),
        ):
            with self.subTest(values=values, index=index, ulps=ulps):
                with self.assertRaises(ValueError):
                    validated_predeclared_nearest_median_index(
                        values,
                        predeclared_index=index,
                        distance_tolerance_ulps=ulps,
                    )


if __name__ == "__main__":
    unittest.main()
