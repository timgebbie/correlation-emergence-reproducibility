"""Unit tests for the v1.7.5 operational response helpers."""

from __future__ import annotations

import ast
import math
import unittest
from pathlib import Path

import numpy as np

from functions.operational import (
    coupling_covariance_build_up,
    exponential_relaxation_rate,
    extract_reaction_boundary,
    linearized_translation_mode,
    local_drift_relaxation_rate,
    symmetric_closed_sde_correlation,
    symmetric_linear_coupling_paths,
)


ROOT = Path(__file__).resolve().parents[1]


class OperationalResponseTests(unittest.TestCase):
    def test_covariance_build_up_zero_and_known_value(self) -> None:
        scales = np.asarray([0.0, 1.0, 2.0])
        observed = coupling_covariance_build_up(0.5, scales)
        expected = np.asarray(
            [0.0, 1.0 - (1.0 - math.exp(-0.5)) / 0.5, math.exp(-1.0)]
        )
        np.testing.assert_allclose(observed, expected, rtol=0.0, atol=2e-16)
        self.assertEqual(coupling_covariance_build_up(2.0, 0.0), 0.0)

    def test_closed_sde_correlation_is_distinct_from_covariance_response(self) -> None:
        scale = 2.0
        rate = 0.5
        expected = (1.0 - (1.0 - math.exp(-1.0))) / (
            1.0 + (1.0 - math.exp(-1.0))
        )
        observed = symmetric_closed_sde_correlation(rate, scale)
        self.assertAlmostEqual(observed, expected, places=15)
        self.assertNotAlmostEqual(
            observed, coupling_covariance_build_up(rate, scale), places=6
        )

    def test_exact_symmetric_paths_follow_stationary_ou_transition(self) -> None:
        centre = np.zeros((2, 4))
        spread = np.zeros_like(centre)
        initial = np.asarray([1.0, -1.0])
        result = symmetric_linear_coupling_paths(
            centre,
            spread,
            initial,
            delta_time=0.25,
            response_rate=0.4,
            innovation_scale=2.0,
        )
        expected_initial = 2.0 * initial / math.sqrt(0.4)
        decay = math.exp(-0.4 * 0.25)
        expected = expected_initial[:, None] * decay ** np.arange(5)
        np.testing.assert_allclose(result.spreads, expected, rtol=0.0, atol=2e-15)
        self.assertEqual(result.prices.shape, (2, 5, 2))
        np.testing.assert_allclose(
            result.prices[:, :, 0] - result.prices[:, :, 1], result.spreads
        )
        centre[0, 0] = 99.0
        self.assertEqual(result.centre_standard_normals[0, 0], 0.0)

    def test_linearized_translation_places_the_zero_at_the_declared_shift(self) -> None:
        grid = np.linspace(-2.0, 2.0, 41)
        density = -grid
        for displacement in (-0.3, 0.2):
            shifted = linearized_translation_mode(grid, density, displacement)
            boundary = extract_reaction_boundary(
                grid,
                shifted,
                selection="nearest_previous",
                previous_price=displacement,
                minimum_abs_slope=1e-6,
            )
            self.assertAlmostEqual(boundary.price, displacement, places=14)

    def test_exponential_relaxation_estimator_recovers_synthetic_rate(self) -> None:
        times = np.linspace(0.0, 2.0, 21)
        control = np.asarray([[1.0], [-2.0]]) * np.ones((2, times.size))
        coupled = control * np.exp(-0.7 * times)
        estimate = exponential_relaxation_rate(
            times, coupled, control, maximum_time=1.5
        )
        self.assertAlmostEqual(estimate.response_rate, 0.7, places=14)
        self.assertLess(estimate.root_mean_square_residual, 2e-15)
        self.assertTrue(estimate.sign_preserved)

    def test_local_drift_estimator_recovers_synthetic_rate(self) -> None:
        step = 0.1
        rate = 0.6
        control = np.asarray([[1.0], [-2.0]]) * np.ones((2, 11))
        coupled = np.empty_like(control)
        coupled[:, 0] = control[:, 0]
        for index in range(10):
            coupled[:, index + 1] = (1.0 - rate * step) * coupled[:, index]
        estimate = local_drift_relaxation_rate(
            coupled, control, delta_time=step, fit_steps=10
        )
        self.assertAlmostEqual(estimate.response_rate, rate, places=14)
        self.assertLess(estimate.root_mean_square_residual, 2e-15)
        self.assertTrue(estimate.sign_preserved)

    def test_validation_and_rng_ownership(self) -> None:
        with self.assertRaises(ValueError):
            coupling_covariance_build_up(0.0, 1.0)
        with self.assertRaises(ValueError):
            symmetric_closed_sde_correlation(1.0, -1.0)
        with self.assertRaises(ValueError):
            symmetric_linear_coupling_paths(
                np.zeros((1, 2)),
                np.zeros((1, 3)),
                np.zeros(1),
                delta_time=1.0,
                response_rate=1.0,
                innovation_scale=1.0,
            )
        source_path = ROOT / "functions" / "operational" / "response.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                self.assertNotEqual(
                    (getattr(node.value, "attr", None), node.attr),
                    ("random", "default_rng"),
                )


if __name__ == "__main__":
    unittest.main()
