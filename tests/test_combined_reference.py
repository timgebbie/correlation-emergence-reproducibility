"""Unit tests for the exact estimator-aware combined reduced reference."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

import numpy as np

from functions.observation import symmetric_previous_refresh_expected_components
from functions.operational import (
    coupling_covariance_build_up,
    symmetric_closed_sde_correlation,
)


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "functions" / "observation" / "combined_reference.py"


class CombinedReferenceTests(unittest.TestCase):
    def test_identity_clock_recovers_coupling_only_moments(self) -> None:
        indices = np.column_stack((np.arange(1001), np.arange(1001)))
        lags = np.asarray([10, 20, 40])
        step = 0.5
        rate = 0.025
        components = symmetric_previous_refresh_expected_components(
            indices,
            lags,
            operational_step=step,
            response_rate=rate,
        )
        windows = indices.shape[0] - lags
        scales = step * lags
        normalized_covariance = components[:, 0] / (windows * scales)
        correlation = components[:, 0] / np.sqrt(
            components[:, 1] * components[:, 2]
        )
        np.testing.assert_allclose(
            normalized_covariance,
            coupling_covariance_build_up(rate, scales),
            rtol=2e-14,
            atol=2e-14,
        )
        np.testing.assert_allclose(
            correlation,
            symmetric_closed_sde_correlation(rate, scales),
            rtol=2e-14,
            atol=2e-14,
        )

    def test_book_exchange_symmetry(self) -> None:
        indices = np.column_stack(
            (
                np.asarray([0, 0, 2, 2, 5, 5, 8, 9, 9, 12]),
                np.asarray([0, 1, 1, 4, 4, 6, 6, 8, 11, 11]),
            )
        )
        original = symmetric_previous_refresh_expected_components(
            indices, [1, 3], operational_step=0.25, response_rate=0.4
        )
        exchanged = symmetric_previous_refresh_expected_components(
            indices[:, ::-1], [1, 3], operational_step=0.25, response_rate=0.4
        )
        np.testing.assert_allclose(original[:, 0], exchanged[:, 0])
        np.testing.assert_allclose(original[:, 1], exchanged[:, 2])
        np.testing.assert_allclose(original[:, 2], exchanged[:, 1])

    def test_validation(self) -> None:
        valid = np.column_stack((np.arange(5), np.arange(5)))
        for indices, lags, step, rate in (
            (valid.astype(float), [1], 1.0, 1.0),
            (valid[::-1], [1], 1.0, 1.0),
            (valid, [0], 1.0, 1.0),
            (valid, [1, 1], 1.0, 1.0),
            (valid, [1], 0.0, 1.0),
            (valid, [1], 1.0, 0.0),
        ):
            with self.subTest(indices=indices, lags=lags, step=step, rate=rate):
                with self.assertRaises(ValueError):
                    symmetric_previous_refresh_expected_components(
                        indices,
                        lags,
                        operational_step=step,
                        response_rate=rate,
                    )

    def test_module_owns_no_rng_clock_or_interpolation(self) -> None:
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                else:
                    names = [node.module or ""]
                for name in names:
                    self.assertNotIn("clock", name)
                    self.assertNotIn("interpol", name)
                    self.assertNotIn("legacy", name)
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("default_rng", source)
        self.assertNotIn("np.random", source)
        self.assertNotIn("np.interp(", source)


class StationaryJointReferenceTests(unittest.TestCase):
    def test_matches_integrated_stationary_cross_kernel(self):
        from functions.observation.combined_reference import stationary_poisson_joint_attenuation
        nodes, weights = np.polynomial.legendre.leggauss(96)
        for lam, kappa in [(0.1, 0.025), (0.1, 0.1), (0.025, 0.1)]:
            for lag in [0.001, 0.5, 1., 20., 100., 400.]:
                time = lag * (nodes + 1) / 2
                if lam == kappa:
                    kernel = kappa / 4 * (1 + kappa * time) * np.exp(-kappa * time)
                else:
                    kernel = kappa * lam / (2 * (lam**2-kappa**2)) * (lam*np.exp(-kappa*time)-kappa*np.exp(-lam*time))
                integral = np.sum(weights * (lag-time) * kernel)
                actual = stationary_poisson_joint_attenuation([lag], clock_rate=lam, response_rate=kappa)[0]
                self.assertAlmostEqual(float(actual), float(integral), places=11)

    def test_short_lag_coefficient_and_zero(self):
        from functions.observation.combined_reference import stationary_poisson_joint_attenuation
        values = stationary_poisson_joint_attenuation([0., 1e-5], clock_rate=.1, response_rate=.025)
        self.assertEqual(values[0], 0.)
        self.assertAlmostEqual(values[1]/1e-5, .1*.025/(2*(.1+.025)), places=10)


if __name__ == "__main__":
    unittest.main()
