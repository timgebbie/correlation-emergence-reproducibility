"""Standard-library regression tests for the active v1 numerical route."""

from __future__ import annotations

import csv
import sys
import unittest
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from functions.correlation_build_up import (
    combined_build_up,
    exponential_memory,
    fractional_build_up,
    ordinary_build_up,
    ordinary_derivative,
    rate_elasticity,
)
from functions.coupling_moment import (
    analytic_half_line_moment,
    discrete_selected_moment,
    numerical_continuum_moment,
    response_rate_total,
)
from functions.diagnostic_checks import FRACTIONAL_REFERENCE_VALUES, OVERLAY_REQUIRED_FIELDS
from functions.io_utils import load_config


class NumericalKernelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config()

    def test_ordinary_zero_and_known_value(self) -> None:
        self.assertEqual(ordinary_build_up(0.0), 0.0)
        self.assertAlmostEqual(ordinary_build_up(1.0), np.exp(-1.0), places=14)

    def test_ordinary_derivative_at_zero(self) -> None:
        self.assertAlmostEqual(ordinary_derivative(0.0), 0.5, places=15)

    def test_ordinary_monotonic_and_bounded(self) -> None:
        curve = np.asarray(ordinary_build_up(np.logspace(-8, 4, 1000)))
        self.assertTrue(np.all(curve >= 0.0))
        self.assertTrue(np.all(curve < 1.0))
        self.assertTrue(np.all(np.diff(curve) >= 0.0))

    def test_rate_elasticity_limits(self) -> None:
        self.assertAlmostEqual(rate_elasticity(0.0), 1.0, places=15)
        self.assertLess(rate_elasticity(1.0e6), 2.0e-6)

    def test_exponential_memory_values_and_validation(self) -> None:
        lag = np.asarray([0.0, 1.0, 2.0])
        np.testing.assert_allclose(exponential_memory(lag, 0.5), np.exp(-0.5 * lag), rtol=0.0, atol=0.0)
        with self.assertRaises(ValueError):
            exponential_memory(lag, 0.0)

    def test_fractional_alpha_one_recovery(self) -> None:
        delta = np.logspace(-3, 2, 301)
        np.testing.assert_allclose(fractional_build_up(delta, 1.0), ordinary_build_up(delta), rtol=0.0, atol=2e-13)

    def test_fractional_reference_values(self) -> None:
        for (alpha, delta), reference in FRACTIONAL_REFERENCE_VALUES.items():
            with self.subTest(alpha=alpha, delta=delta):
                self.assertAlmostEqual(fractional_build_up(delta, alpha), reference, places=9)

    def test_fractional_monotonic_and_bounded(self) -> None:
        delta = np.logspace(-3, 2, 301)
        for alpha in (0.6, 0.8):
            curve = np.asarray(fractional_build_up(delta, alpha))
            self.assertTrue(np.all(curve >= 0.0))
            self.assertTrue(np.all(curve <= 1.0))
            self.assertTrue(np.all(np.diff(curve) >= -2e-12))

    def test_combined_product(self) -> None:
        a = np.asarray([0.1, 0.5, 0.9])
        b = np.asarray([0.2, 0.4, 0.8])
        np.testing.assert_array_equal(combined_build_up(a, b), a * b)

    def test_analytic_moment(self) -> None:
        expected = -np.sqrt(np.pi) / 4.0
        self.assertAlmostEqual(analytic_half_line_moment(1.0, 1.0), expected, places=15)

    def test_continuum_selector_invariance(self) -> None:
        analytic = analytic_half_line_moment(1.0, 1.0)
        for epsilon in (0.01, 0.1, 1.0):
            numeric = numerical_continuum_moment(1.0, 1.0, 0.2, epsilon, points=50_001)
            self.assertAlmostEqual(numeric / analytic, 1.0, places=8)

    def test_discrete_moment_convergence(self) -> None:
        analytic = analytic_half_line_moment(1.0, 1.0)
        errors = []
        for dx in (1.5, 1.0, 0.75, 0.5):
            discrete, _, _ = discrete_selected_moment(1.0, 1.0, 0.2, (2.0 * dx) ** 2, dx, 6.0)
            errors.append(abs(discrete / analytic - 1.0))
        self.assertGreater(errors[0], errors[1])
        self.assertGreater(errors[1], errors[2])
        self.assertGreater(errors[2], errors[3])
        self.assertLess(errors[-1], 2e-5)

    def test_boundary_baseline_rate(self) -> None:
        boundary = self.config["boundary"]
        rate = response_rate_total(
            books=boundary["books"],
            coupling_strength=boundary["coupling_strength"],
            source_amplitude=boundary["source_amplitude"],
            source_width=boundary["source_width"],
            front_slope_abs=boundary["front_slope_abs"],
        )
        self.assertAlmostEqual(rate, 1.0, places=14)

    def test_invalid_parameters(self) -> None:
        with self.assertRaises(ValueError):
            ordinary_build_up(-1.0)
        with self.assertRaises(ValueError):
            fractional_build_up(1.0, 0.0)
        with self.assertRaises(ValueError):
            analytic_half_line_moment(1.0, 0.0)

    def test_overlay_schema_roles(self) -> None:
        self.assertEqual(len(OVERLAY_REQUIRED_FIELDS), 10)

    def test_generated_overlay_file_when_present(self) -> None:
        path = PROJECT_ROOT / "outputs" / "epps-overlay-v1.csv"
        if not path.exists():
            self.skipTest("generated overlay file is created by scripts/run_all.py")
        with path.open("r", encoding="utf-8", newline="") as handle:
            fields = set(csv.DictReader(handle).fieldnames or [])
        self.assertTrue(OVERLAY_REQUIRED_FIELDS.issubset(fields))


if __name__ == "__main__":
    unittest.main()
