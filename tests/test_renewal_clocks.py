"""Mathematical and contract tests for R13 observation renewal clocks."""

from __future__ import annotations

import unittest

import numpy as np

from functions.observation import (
    mittag_leffler_refresh_path_from_uniforms,
    mittag_leffler_wait_laplace,
    mittag_leffler_waits_from_uniforms,
    positive_stable_from_uniforms,
    subordinate_two_book_previous_refresh,
    tempered_mittag_leffler_mean_wait,
    tempered_mittag_leffler_refresh_path_from_uniforms,
    tempered_mittag_leffler_wait_laplace,
    tempered_mittag_leffler_waits_from_uniforms,
)


class RenewalClockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rng = np.random.default_rng(130013)

    def _uniforms(self, count: int, streams: int = 4) -> tuple[np.ndarray, ...]:
        values = self.rng.random((streams, count))
        return tuple(values[index] for index in range(streams))

    def test_positive_stable_beta_one_is_deterministic(self) -> None:
        first, second = self._uniforms(32, streams=2)
        np.testing.assert_array_equal(
            positive_stable_from_uniforms(first, second, 1.0),
            np.ones(32),
        )

    def test_beta_one_mittag_leffler_reduces_to_exponential(self) -> None:
        first, second, mixture = self._uniforms(64, streams=3)
        waits = mittag_leffler_waits_from_uniforms(
            first,
            second,
            mixture,
            beta=1.0,
            scale_seconds=2.5,
        )
        np.testing.assert_allclose(waits, -2.5 * np.log(mixture))

    def test_untempered_empirical_laplace_transform(self) -> None:
        first, second, mixture = self._uniforms(200_000, streams=3)
        waits = mittag_leffler_waits_from_uniforms(
            first,
            second,
            mixture,
            beta=0.8,
            scale_seconds=2.5,
        )
        points = np.asarray([0.05, 0.2, 0.8])
        empirical = np.mean(np.exp(-points[:, None] * waits[None, :]), axis=1)
        expected = mittag_leffler_wait_laplace(
            points, beta=0.8, scale_seconds=2.5
        )
        np.testing.assert_allclose(empirical, expected, atol=3.0e-3, rtol=0.0)

    def test_tempered_empirical_laplace_transform_and_mean(self) -> None:
        first, second, mixture, acceptance = self._uniforms(400_000)
        waits = tempered_mittag_leffler_waits_from_uniforms(
            first,
            second,
            mixture,
            acceptance,
            beta=0.8,
            scale_seconds=2.5,
            tempering_rate_per_second=0.05,
        )
        points = np.asarray([0.05, 0.2, 0.8])
        empirical = np.mean(np.exp(-points[:, None] * waits[None, :]), axis=1)
        expected = tempered_mittag_leffler_wait_laplace(
            points,
            beta=0.8,
            scale_seconds=2.5,
            tempering_rate_per_second=0.05,
        )
        np.testing.assert_allclose(empirical, expected, atol=3.5e-3, rtol=0.0)
        expected_mean = tempered_mittag_leffler_mean_wait(
            beta=0.8,
            scale_seconds=2.5,
            tempering_rate_per_second=0.05,
        )
        self.assertLess(abs(float(np.mean(waits)) - expected_mean) / expected_mean, 0.03)

    def test_paths_support_previous_refresh_without_interpolation(self) -> None:
        streams = self._uniforms(20_000)
        first = mittag_leffler_refresh_path_from_uniforms(
            streams[0],
            streams[1],
            streams[2],
            beta=0.8,
            scale_seconds=1.0,
            horizon=20.0,
            stream_id="R13-ML-B1",
        )
        second = tempered_mittag_leffler_refresh_path_from_uniforms(
            streams[1],
            streams[2],
            streams[3],
            streams[0],
            beta=0.8,
            scale_seconds=1.0,
            tempering_rate_per_second=0.05,
            horizon=20.0,
            stream_id="R13-TML-B2",
        )
        operational_times = np.arange(21, dtype=float)
        prices = np.column_stack((operational_times, -operational_times))
        result = subordinate_two_book_previous_refresh(
            operational_times,
            prices,
            (first, second),
            operational_times,
        )
        np.testing.assert_array_equal(
            result.prices[:, 0],
            prices[result.operational_indices[:, 0], 0],
        )
        np.testing.assert_array_equal(
            result.prices[:, 1],
            prices[result.operational_indices[:, 1], 1],
        )
        self.assertEqual(
            result.convention, "previous_refresh_then_previous_uniform_state"
        )

    def test_invalid_parameters_are_rejected(self) -> None:
        first, second, mixture = self._uniforms(4, streams=3)
        for beta in (0.0, -0.1, 1.1):
            with self.assertRaises(ValueError):
                mittag_leffler_waits_from_uniforms(
                    first,
                    second,
                    mixture,
                    beta=beta,
                    scale_seconds=1.0,
                )


if __name__ == "__main__":
    unittest.main()
