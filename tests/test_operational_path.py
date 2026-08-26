"""Regression tests for the v1.4.1 rolling operational-path gate."""

from __future__ import annotations

import ast
import csv
import sys
import unittest
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from functions.operational import (
    BurnInPolicy,
    OperationalSolverSpec,
    OperationalSource,
    RegularizedCoupling,
    TwoBookInnovationPolicy,
    apply_spatial_boundary,
    operational_sibuya_kernel,
    operational_source_density,
    operational_two_book_path,
    regularization_epsilon,
    regularized_transition_width,
    stationary_density,
)


def _initial_density(
    grid: np.ndarray,
    price: float,
    source: OperationalSource,
    diffusion: float,
) -> np.ndarray:
    return apply_spatial_boundary(
        stationary_density(
            grid,
            np.asarray(operational_source_density(grid, price, source)),
            diffusion=diffusion,
            cancellation_rate=0.0,
            boundary_condition="dirichlet_zero",
        )
    )


def _path_inputs(*, prices: tuple[float, float] = (0.0, 0.0), steps: int = 10):
    grid = np.linspace(-10.0, 10.0, 201)
    delta_x = float(grid[1] - grid[0])
    diffusion = 0.5
    transport = 0.5
    delta_u = transport * delta_x**2 / (2.0 * diffusion)
    source = OperationalSource(1.0, 0.1)
    initial = np.stack(
        [_initial_density(grid, price, source, diffusion) for price in prices]
    )
    coupling = RegularizedCoupling.from_reference_scale(0.01, 1.0, 0.5)
    return {
        "price_grid": grid,
        "initial_densities": initial,
        "initial_prices": prices,
        "sources": [source, source],
        "couplings": [[None, coupling], [coupling, None]],
        "raw_kernels": [operational_sibuya_kernel(1.0, 5)] * 2,
        "base_standard_normals": np.zeros((steps, 2)),
        "innovation_policy": TwoBookInnovationPolicy(1.0, 1.0, 0.0),
        "diffusion": [diffusion, diffusion],
        "solver_spec": OperationalSolverSpec(
            delta_u,
            transport,
            (0.0, 0.0),
            minimum_abs_boundary_slope=1e-6,
        ),
    }


class OperationalPathTests(unittest.TestCase):
    def test_reference_scale_parameterization_and_dynamic_width(self) -> None:
        self.assertEqual(regularization_epsilon(-2.0, 0.25), 0.5)
        coupling = RegularizedCoupling.from_reference_scale(0.3, 2.0, 0.25)
        self.assertEqual(coupling.epsilon, 0.5)
        widths = regularized_transition_width(np.asarray([0.0, 0.5, -2.0]), 0.5)
        self.assertTrue(np.isinf(widths[0]))
        np.testing.assert_array_equal(widths[1:], [1.0, 0.25])

    def test_uniform_path_preserves_the_stationary_state(self) -> None:
        arguments = _path_inputs()
        result = operational_two_book_path(**arguments)
        self.assertEqual(result.completed_steps, 10)
        np.testing.assert_allclose(
            result.prices, 0.0, rtol=0.0, atol=2e-12
        )
        np.testing.assert_allclose(
            np.diff(result.operational_times),
            result.delta_u,
            rtol=0.0,
            atol=2e-18,
        )
        self.assertLess(float(np.max(result.relative_state_changes)), 2e-14)
        self.assertTrue(np.all(result.boundary_candidate_counts == 1))
        self.assertEqual(result.boundary_curvatures.shape, (11, 2))
        self.assertEqual(result.boundary_curvature_lengths.shape, (11, 2))
        self.assertTrue(np.all(np.isfinite(result.boundary_curvatures)))

    def test_rolling_history_is_bounded_by_the_kernel_cutoff(self) -> None:
        result = operational_two_book_path(**_path_inputs(steps=12))
        self.assertEqual(result.history_capacity, 5)
        self.assertEqual(result.final_density_histories.shape, (2, 201, 5))

    def test_burn_in_obeys_minimum_and_persistence_and_stops(self) -> None:
        arguments = _path_inputs(steps=10)
        result = operational_two_book_path(
            **arguments,
            burn_in_policy=BurnInPolicy(4, 1e-10, 2),
            stop_on_burn_in=True,
            density_snapshot_steps=(0, 2, 4, 8),
        )
        self.assertEqual(result.burn_in_step, 4)
        self.assertEqual(result.completed_steps, 4)
        self.assertTrue(result.stopped_on_burn_in)
        np.testing.assert_array_equal(result.density_snapshot_steps, [0, 2, 4])
        self.assertEqual(result.density_snapshots.shape, (3, 2, 201))

    def test_requested_snapshots_do_not_force_full_density_storage(self) -> None:
        result = operational_two_book_path(
            **_path_inputs(steps=8), density_snapshot_steps=(0, 3, 8)
        )
        np.testing.assert_array_equal(result.density_snapshot_steps, [0, 3, 8])
        self.assertEqual(result.density_snapshots.shape, (3, 2, 201))
        self.assertEqual(result.final_density_histories.shape[-1], 5)

    def test_external_innovations_are_deterministic_and_copied(self) -> None:
        arguments = _path_inputs(steps=4)
        arguments["base_standard_normals"][:] = np.asarray(
            [[0.2, -0.3], [0.4, 0.1], [-0.2, 0.5], [0.0, -0.1]]
        )
        first = operational_two_book_path(**arguments)
        second = operational_two_book_path(**arguments)
        np.testing.assert_array_equal(first.prices, second.prices)
        stored_base = first.base_standard_normals.copy()
        arguments["base_standard_normals"][:] = 9.0
        np.testing.assert_array_equal(first.base_standard_normals, stored_base)

    def test_external_shock_timing_is_recorded_without_full_field_storage(self) -> None:
        arguments = _path_inputs(steps=4)
        shocks = np.zeros((4, 2, 201))
        shocks[2, 0, 100] = 1e-3
        result = operational_two_book_path(**arguments, shock_fields=shocks)
        expected = np.zeros((4, 2))
        expected[2, 0] = 1e-3
        np.testing.assert_array_equal(result.shock_l1_norms, expected)

    def test_path_records_angstmann_gebbie_width_dynamics(self) -> None:
        arguments = _path_inputs(prices=(-0.5, 0.5), steps=1)
        arguments["initial_densities"] = np.stack(
            [
                np.asarray(
                    operational_source_density(
                        arguments["price_grid"], price, arguments["sources"][book]
                    )
                )
                for book, price in enumerate(arguments["initial_prices"])
            ]
        )
        arguments["initial_densities"][:, [0, -1]] = 0.0
        result = operational_two_book_path(**arguments)
        self.assertEqual(result.directed_spreads[0, 0, 1], -1.0)
        self.assertEqual(result.directed_spreads[0, 1, 0], 1.0)
        self.assertEqual(result.selector_transition_widths[0, 0, 1], 0.5)
        self.assertEqual(result.selector_transition_widths[0, 1, 0], 0.5)

    def test_equal_prices_have_vanishing_coupling_and_infinite_selector_limit(self) -> None:
        result = operational_two_book_path(**_path_inputs(steps=1))
        self.assertTrue(np.isinf(result.selector_transition_widths[0, 0, 1]))
        self.assertTrue(np.isinf(result.selector_transition_widths[0, 1, 0]))
        self.assertEqual(result.directed_spreads[0, 0, 1], 0.0)
        self.assertEqual(result.directed_spreads[0, 1, 0], 0.0)

    def test_initial_price_must_match_the_density_boundary(self) -> None:
        arguments = _path_inputs(steps=1)
        arguments["initial_prices"] = (0.1, 0.0)
        with self.assertRaises(ValueError):
            operational_two_book_path(**arguments)

    def test_path_validation_rejects_ambiguous_storage_or_burn_in(self) -> None:
        arguments = _path_inputs(steps=3)
        with self.assertRaises(ValueError):
            operational_two_book_path(
                **arguments, density_snapshot_steps=(2, 1)
            )
        with self.assertRaises(ValueError):
            operational_two_book_path(**arguments, stop_on_burn_in=True)

    def test_target_path_does_not_import_legacy_clock_or_observation_layers(self) -> None:
        path = PROJECT_ROOT / "functions" / "operational" / "path.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                self.assertFalse(module.startswith("functions.legacy"))
                self.assertFalse(module.startswith("functions.observation"))
                self.assertNotIn("clock", module)

    def test_generated_path_diagnostic_contract(self) -> None:
        path = PROJECT_ROOT / "diagnostics" / "operational-path-checks-v1.4.csv"
        self.assertTrue(path.is_file())
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 8)
        self.assertTrue(all(row["status"] == "Verified" for row in rows))
        self.assertEqual({row["software_version"] for row in rows}, {"1.4.1"})


if __name__ == "__main__":
    unittest.main()
