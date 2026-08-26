"""Tests for the exact previous-refresh benchmark and pooled estimator."""

from __future__ import annotations

import unittest

import numpy as np

from functions.observation import (
    overlap_component_sums,
    poisson_refresh_path_from_uniforms,
    pooled_correlation_summary,
    return_component_sums,
    subordinate_two_book_previous_refresh,
)


class PreviousRefreshSamplingTests(unittest.TestCase):
    def test_uniform_transform_and_measured_rate(self) -> None:
        uniforms = 1.0 - np.exp(-np.asarray([0.5, 1.0, 0.25, 2.0]))
        path = poisson_refresh_path_from_uniforms(
            uniforms, 2.0, 1.5, stream_id="TEST-B1"
        )
        np.testing.assert_allclose(path.waiting_intervals, [0.25, 0.5, 0.125, 1.0])
        self.assertAlmostEqual(path.measured_rate, 1.0 / np.mean(path.waiting_intervals))
        self.assertGreaterEqual(path.event_times[-1], 1.5)

    def test_long_cumulative_refresh_path_retains_waits(self) -> None:
        uniforms = np.random.default_rng(7).random(1024)
        path = poisson_refresh_path_from_uniforms(
            uniforms, 0.1, 2200.0, stream_id="LONG-B1"
        )
        np.testing.assert_allclose(
            np.diff(path.event_times), path.waiting_intervals, rtol=1e-12, atol=1e-11
        )

    def test_previous_refresh_has_no_interpolation(self) -> None:
        operational = np.arange(6, dtype=float)
        prices = np.column_stack((operational, 10.0 * operational))
        uniforms = 1.0 - np.exp(-np.asarray([1.2, 1.3, 1.5, 2.0]))
        first = poisson_refresh_path_from_uniforms(
            uniforms, 1.0, 5.0, stream_id="TEST-B1"
        )
        second = poisson_refresh_path_from_uniforms(
            1.0 - np.exp(-np.asarray([0.7, 2.0, 1.0, 2.0])),
            1.0,
            5.0,
            stream_id="TEST-B2",
        )
        result = subordinate_two_book_previous_refresh(
            operational, prices, (first, second), np.arange(6, dtype=float)
        )
        np.testing.assert_array_equal(result.operational_indices[:, 0], [0, 0, 1, 2, 4, 4])
        np.testing.assert_array_equal(result.prices[:, 0], [0, 0, 1, 2, 4, 4])
        self.assertEqual(result.convention, "previous_refresh_then_previous_uniform_state")

    def test_roundoff_at_operational_endpoint_is_supported(self) -> None:
        grid = np.linspace(-10.0, 10.0, 201)
        delta_x = grid[1] - grid[0]
        delta_u = 0.5 * delta_x**2 / (2.0 * 0.5)
        operational = delta_u * np.arange(4401, dtype=float) * 100.0
        self.assertLess(operational[-1], 2200.0)
        prices = np.column_stack((operational, operational))
        uniforms = 1.0 - np.exp(-np.full(512, 5.0))
        path = poisson_refresh_path_from_uniforms(
            uniforms, 1.0, 2200.0, stream_id="ENDPOINT"
        )
        result = subordinate_two_book_previous_refresh(
            operational,
            prices,
            (path, path),
            np.asarray([2199.5, 2200.0]),
        )
        self.assertEqual(result.prices.shape, (2, 2))

    def test_return_components_recover_perfect_correlation(self) -> None:
        values = np.column_stack((np.arange(8, dtype=float), 2.0 * np.arange(8)))
        components = return_component_sums(values, [1, 2, 3])
        summary = pooled_correlation_summary(np.stack((components, components)))
        np.testing.assert_allclose(summary.correlation, 1.0)
        np.testing.assert_allclose(summary.jackknife_standard_error, 0.0)

    def test_overlap_components_use_interval_intersection(self) -> None:
        indices = np.asarray([[0, 0], [1, 0], [2, 1], [3, 3], [4, 3]], dtype=int)
        components = overlap_component_sums(indices, [1], operational_step=0.5)
        self.assertAlmostEqual(components[0, 0], 0.5)
        self.assertAlmostEqual(components[0, 1], 2.0)
        self.assertAlmostEqual(components[0, 2], 1.5)

    def test_invalid_support_and_group_shapes(self) -> None:
        with self.assertRaises(ValueError):
            poisson_refresh_path_from_uniforms(
                np.asarray([0.1]), 1.0, 10.0, stream_id="SHORT"
            )
        with self.assertRaises(ValueError):
            pooled_correlation_summary(np.ones((1, 3, 3)))


if __name__ == "__main__":
    unittest.main()
