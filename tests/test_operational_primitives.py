"""Tests for the separately implemented v1.3.4 target primitives."""

from __future__ import annotations

import ast
import csv
import math
import sys
import unittest
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from functions.operational import (
    BurnInPolicy,
    OperationalSource,
    RegularizedCoupling,
    burn_in_converged,
    lattice_first_moment,
    operational_sibuya_kernel,
    operational_source_density,
    operational_uniform_memory_step,
    positive_half_first_moment,
    regularized_coupling_density,
    regularized_selector,
    relative_state_change,
    simultaneous_stationary_initialization,
    stationary_density,
)


class OperationalPrimitiveTests(unittest.TestCase):
    def test_corrected_source_formula_and_scalar_contract(self) -> None:
        source = OperationalSource(1.0, 0.1)
        expected = -0.1 * math.exp(-0.1)
        self.assertAlmostEqual(operational_source_density(1.0, 0.0, source), expected, places=15)
        values = operational_source_density(np.asarray([-1.0, 0.0, 1.0]), 0.0, source)
        np.testing.assert_allclose(values, np.asarray([-expected, 0.0, expected]), rtol=0.0, atol=1e-15)

    def test_source_first_moment_matches_independent_quadrature(self) -> None:
        source = OperationalSource(1.0, 0.1)
        y = np.linspace(0.0, 50.0, 200_001)
        values = np.asarray(operational_source_density(y, 0.0, source))
        numerical = float(np.trapezoid(y * values, y))
        self.assertAlmostEqual(numerical / positive_half_first_moment(source), 1.0, places=11)

    def test_corrected_source_uses_target_exponent_and_does_not_wrap(self) -> None:
        source = OperationalSource(1.0, 0.1)
        displacement = 2.0
        observed = operational_source_density(232.0, 230.0, source)
        expected = -0.1 * displacement * math.exp(-0.1 * displacement**2)
        rejected_square_mu_convention = (
            -0.1 * displacement * math.exp(-(0.1 * displacement) ** 2)
        )
        self.assertAlmostEqual(observed, expected, places=15)
        self.assertNotAlmostEqual(observed, rejected_square_mu_convention, places=6)
        self.assertLess(
            abs(operational_source_density(432.0, 230.0, source)),
            1e-300,
        )

    def test_selector_and_coupling_are_well_defined_at_zero_spread(self) -> None:
        y = np.linspace(-5.0, 5.0, 101)
        np.testing.assert_array_equal(
            regularized_selector(y, 0.0, 0.5), np.full_like(y, 0.5)
        )
        field = regularized_coupling_density(
            y, 0.0, 0.0, OperationalSource(1.0, 0.1), RegularizedCoupling(0.3, 0.5)
        )
        np.testing.assert_array_equal(field, np.zeros_like(y))

    def test_coupling_reversal_symmetry_and_bound(self) -> None:
        y = np.linspace(-20.0, 20.0, 4001)
        source = OperationalSource(1.0, 0.1)
        coupling = RegularizedCoupling(0.3, 0.5)
        positive = np.asarray(regularized_coupling_density(y, 1.0, -1.0, source, coupling))
        negative = np.asarray(regularized_coupling_density(-y, -1.0, 1.0, source, coupling))
        np.testing.assert_allclose(positive, negative, rtol=0.0, atol=2e-16)
        q = np.asarray(operational_source_density(y, 1.0, source))
        self.assertTrue(np.all(np.abs(positive) <= coupling.gamma * 2.0 * np.abs(q) + 1e-15))

    def test_coupling_lattice_moment_matches_target_coefficient(self) -> None:
        grid = np.linspace(-50.0, 50.0, 20_001)
        source = OperationalSource(1.0, 0.1)
        coupling = RegularizedCoupling(0.3, 0.5)
        positive = regularized_coupling_density(grid, 1.0, -1.0, source, coupling)
        negative = regularized_coupling_density(grid, -1.0, 1.0, source, coupling)
        expected_positive = coupling.gamma * positive_half_first_moment(source) * 2.0
        expected_negative = coupling.gamma * positive_half_first_moment(source) * -2.0
        self.assertAlmostEqual(lattice_first_moment(grid, 1.0, positive) / expected_positive, 1.0, places=11)
        self.assertAlmostEqual(lattice_first_moment(grid, -1.0, negative) / expected_negative, 1.0, places=11)

    def test_raw_sibuya_kernel_has_no_cancellation_weight(self) -> None:
        kernel = operational_sibuya_kernel(0.8, 4)
        np.testing.assert_allclose(
            kernel,
            np.asarray([0.8, -0.08, -0.048, -0.0336]),
            rtol=0.0,
            atol=2e-17,
        )
        np.testing.assert_array_equal(operational_sibuya_kernel(1.0, 4), [1.0, 0.0, 0.0, 0.0])

    def test_uniform_memory_step_applies_one_elapsed_survival(self) -> None:
        density = np.asarray([[1.0, 2.0], [2.0, 4.0], [3.0, 6.0]])
        left = density + 1.0
        right = density - 0.5
        kernel = operational_sibuya_kernel(0.8, 2)
        result = operational_uniform_memory_step(
            density,
            left,
            right,
            kernel,
            np.asarray([0.2, -0.1, 0.3]),
            delta_u=0.25,
            cancellation_rate=2.0,
            transport_probability=0.5,
            jump_bias=0.1,
        )
        transports = [
            0.3 * left[:, index] + 0.2 * right[:, index] - 0.5 * density[:, index]
            for index in range(2)
        ]
        expected_history = kernel[1] * math.exp(-0.5) * transports[0] + kernel[0] * transports[1]
        np.testing.assert_allclose(result.history_contribution, expected_history, rtol=0.0, atol=1e-15)
        np.testing.assert_allclose(
            result.density,
            expected_history + math.exp(-0.5) * density[:, 1] + 0.25 * np.asarray([0.2, -0.1, 0.3]),
            rtol=0.0,
            atol=1e-15,
        )

    def test_alpha_one_most_recent_transport_is_not_survival_damped(self) -> None:
        density = np.asarray([[1.0], [2.0], [3.0]])
        left = density + 2.0
        right = density - 1.0
        result = operational_uniform_memory_step(
            density,
            left,
            right,
            operational_sibuya_kernel(1.0, 1),
            np.zeros(3),
            delta_u=0.125,
            cancellation_rate=14.0,
            transport_probability=0.5,
        )
        expected_transport = 0.25 * left[:, 0] + 0.25 * right[:, 0] - 0.5 * density[:, 0]
        np.testing.assert_allclose(result.history_contribution, expected_transport, rtol=0.0, atol=0.0)
        np.testing.assert_allclose(result.survivor_contribution, math.exp(-1.75) * density[:, 0])

    def test_simultaneous_initializer_uses_one_price_snapshot(self) -> None:
        grid = np.linspace(130.0, 330.0, 401)
        source = OperationalSource(1.0, 0.1)
        coupling = RegularizedCoupling(0.3, 0.5)
        policy = BurnInPolicy(100, 1e-8, 5)
        result = simultaneous_stationary_initialization(
            grid,
            [230.0, 230.0],
            [source, source],
            [[None, coupling], [coupling, None]],
            diffusion=[0.5, 0.5],
            cancellation_rates=[14.0, 14.0],
            boundary_condition="dirichlet_zero",
            burn_in_policy=policy,
        )
        np.testing.assert_array_equal(result.price_inputs, np.full((2, 2), 230.0))
        np.testing.assert_array_equal(result.directed_coupling_fields, np.zeros((2, 2, 401)))
        np.testing.assert_allclose(result.densities[0], result.densities[1], rtol=0.0, atol=0.0)
        self.assertIs(result.burn_in_policy, policy)

    def test_stationary_solvers_satisfy_their_explicit_boundaries(self) -> None:
        grid = np.linspace(-20.0, 20.0, 401)
        source = np.asarray(operational_source_density(grid, 0.0, OperationalSource(1.0, 0.1)))
        dx = grid[1] - grid[0]
        for boundary in ("dirichlet_zero", "neumann_zero_flux"):
            density = stationary_density(
                grid,
                source,
                diffusion=0.5,
                cancellation_rate=2.0,
                boundary_condition=boundary,
            )
            residual = 0.5 * (density[:-2] - 2.0 * density[1:-1] + density[2:]) / dx**2 - 2.0 * density[1:-1] + source[1:-1]
            self.assertLess(float(np.max(np.abs(residual))), 2e-13)
            if boundary == "dirichlet_zero":
                self.assertLess(abs(density[0]), 1e-24)
                self.assertLess(abs(density[-1]), 1e-24)
            else:
                left_residual = 0.5 * 2.0 * (density[1] - density[0]) / dx**2 - 2.0 * density[0] + source[0]
                right_residual = 0.5 * 2.0 * (density[-2] - density[-1]) / dx**2 - 2.0 * density[-1] + source[-1]
                self.assertLess(abs(left_residual), 2e-13)
                self.assertLess(abs(right_residual), 2e-13)

    def test_burn_in_policy_requires_time_tolerance_and_persistence(self) -> None:
        policy = BurnInPolicy(100, 1e-4, 3)
        previous = np.asarray([[1.0, 2.0]])
        close = previous * (1.0 + 1e-5)
        self.assertLess(relative_state_change(previous, close), policy.relative_tolerance)
        self.assertFalse(burn_in_converged(previous, close, operational_step=99, consecutive_converged_checks=3, policy=policy))
        self.assertFalse(burn_in_converged(previous, close, operational_step=100, consecutive_converged_checks=2, policy=policy))
        self.assertTrue(burn_in_converged(previous, close, operational_step=100, consecutive_converged_checks=3, policy=policy))

    def test_target_modules_do_not_import_legacy_implementations(self) -> None:
        operational_directory = PROJECT_ROOT / "functions" / "operational"
        for path in operational_directory.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse((node.module or "").startswith("functions.legacy"), path.name)

    def test_validation_and_generated_diagnostic_contract(self) -> None:
        with self.assertRaises(ValueError):
            OperationalSource(1.0, 0.0)
        with self.assertRaises(ValueError):
            RegularizedCoupling(-1.0, 0.5)
        with self.assertRaises(ValueError):
            operational_sibuya_kernel(0.0, 2)
        diagnostic_path = PROJECT_ROOT / "diagnostics" / "operational-primitive-checks-v1.3.csv"
        self.assertTrue(diagnostic_path.is_file())
        with diagnostic_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 10)
        self.assertTrue(all(row["status"] == "Verified" for row in rows))
        self.assertEqual({row["software_version"] for row in rows}, {"1.3.4"})


if __name__ == "__main__":
    unittest.main()
