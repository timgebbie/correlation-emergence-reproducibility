"""Regression tests for the v1.4.0 operational solver-entry gate."""

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
    OperationalSolverSpec,
    OperationalSource,
    ReactionBoundaryError,
    RegularizedCoupling,
    apply_spatial_boundary,
    extract_reaction_boundary,
    operational_sibuya_kernel,
    operational_source_density,
    operational_two_book_step,
    reaction_boundary_candidates,
    regularized_coupling_density,
    spatial_neighbour_histories,
    stationary_density,
)


def _stationary_reference(
    grid: np.ndarray,
    boundary: float,
    source: OperationalSource,
    diffusion: float,
) -> np.ndarray:
    density = stationary_density(
        grid,
        np.asarray(operational_source_density(grid, boundary, source)),
        diffusion=diffusion,
        cancellation_rate=0.0,
        boundary_condition="dirichlet_zero",
    )
    return apply_spatial_boundary(density)


def _reference_step(
    *,
    previous_prices: np.ndarray | None = None,
    coupling_gamma: float = 0.3,
    shock_fields: np.ndarray | None = None,
):
    grid = np.linspace(-10.0, 10.0, 401)
    delta_x = float(grid[1] - grid[0])
    diffusion = 0.5
    transport = 0.5
    delta_u = transport * delta_x**2 / (2.0 * diffusion)
    prices = np.asarray([0.0, 0.0] if previous_prices is None else previous_prices)
    source = OperationalSource(1.0, 0.1)
    histories = np.stack(
        [
            _stationary_reference(grid, prices[0], source, diffusion),
            _stationary_reference(grid, prices[1], source, diffusion),
        ]
    )[:, :, None]
    coupling = RegularizedCoupling(coupling_gamma, 0.5)
    result = operational_two_book_step(
        grid,
        histories,
        prices,
        [source, source],
        [[None, coupling], [coupling, None]],
        [operational_sibuya_kernel(1.0, 1)] * 2,
        [0.0, 0.0],
        OperationalSolverSpec(
            delta_u,
            transport,
            (0.0, 0.0),
            minimum_abs_boundary_slope=1e-6,
        ),
        shock_fields=shock_fields,
    )
    return grid, histories, source, coupling, result


class OperationalSolverEntryTests(unittest.TestCase):
    def test_dirichlet_neighbour_histories_are_explicit(self) -> None:
        density = np.asarray(
            [[0.0, 0.0], [1.0, 2.0], [3.0, 4.0], [0.0, 0.0]]
        )
        left, right = spatial_neighbour_histories(density)
        np.testing.assert_array_equal(left[0], 0.0)
        np.testing.assert_array_equal(left[1:], density[:-1])
        np.testing.assert_array_equal(right[-1], 0.0)
        np.testing.assert_array_equal(right[:-1], density[1:])

    def test_dirichlet_application_is_copying_and_exact(self) -> None:
        field = np.asarray([2.0, 1.0, -1.0, -3.0])
        bounded = apply_spatial_boundary(field)
        np.testing.assert_array_equal(bounded, [0.0, 1.0, -1.0, 0.0])
        np.testing.assert_array_equal(field, [2.0, 1.0, -1.0, -3.0])

    def test_exact_grid_reaction_boundary(self) -> None:
        grid = np.linspace(-2.0, 2.0, 9)
        boundary = extract_reaction_boundary(grid, grid.copy())
        self.assertEqual(boundary.price, 0.0)
        self.assertEqual(boundary.left_index, 4)
        self.assertEqual(boundary.right_index, 4)
        self.assertTrue(boundary.exact_grid_zero)
        self.assertEqual(boundary.candidate_count, 1)

    def test_off_grid_reaction_boundary_is_linearly_interpolated(self) -> None:
        grid = np.linspace(-2.0, 2.0, 9)
        boundary = extract_reaction_boundary(grid, grid - 0.2)
        self.assertAlmostEqual(boundary.price, 0.2, places=15)
        self.assertEqual((boundary.left_index, boundary.right_index), (4, 5))
        self.assertFalse(boundary.exact_grid_zero)

    def test_multiple_crossings_require_an_explicit_selection(self) -> None:
        grid = np.linspace(-4.0, 4.0, 17)
        density = (grid + 2.0) * grid * (grid - 3.0)
        self.assertEqual(len(reaction_boundary_candidates(grid, density)), 3)
        with self.assertRaises(ReactionBoundaryError):
            extract_reaction_boundary(grid, density)
        selected = extract_reaction_boundary(
            grid, density, selection="nearest_previous", previous_price=2.7
        )
        self.assertEqual(selected.price, 3.0)
        self.assertEqual(selected.candidate_count, 3)

    def test_nearest_previous_tie_is_rejected(self) -> None:
        grid = np.linspace(-4.0, 4.0, 17)
        density = (grid + 2.0) * grid * (grid - 3.0)
        with self.assertRaises(ReactionBoundaryError):
            extract_reaction_boundary(
                grid, density, selection="nearest_previous", previous_price=1.5
            )

    def test_near_edge_crossing_is_detected_and_exposed(self) -> None:
        grid = np.linspace(-2.0, 2.0, 9)
        target = grid[0] + 0.25 * (grid[1] - grid[0])
        boundary = extract_reaction_boundary(grid, grid - target)
        self.assertAlmostEqual(boundary.price, target, places=15)
        self.assertAlmostEqual(
            boundary.distance_to_domain_edge,
            0.25 * (grid[1] - grid[0]),
            places=15,
        )

    def test_stationary_uncoupled_state_is_a_one_step_fixed_point(self) -> None:
        _, histories, _, _, result = _reference_step(coupling_gamma=0.3)
        density_tolerance = 2e-12
        price_tolerance = 3e-12
        self.assertLess(
            float(np.max(np.abs(result.densities - histories[:, :, 0]))),
            density_tolerance,
        )
        minimum_boundary_slope = min(abs(item.slope) for item in result.boundaries)
        self.assertGreaterEqual(
            price_tolerance,
            density_tolerance / minimum_boundary_slope,
        )
        np.testing.assert_allclose(result.prices, 0.0, rtol=0.0, atol=price_tolerance)
        np.testing.assert_array_equal(result.total_coupling_fields, 0.0)
        self.assertTrue(all(item.candidate_count == 1 for item in result.boundaries))

    def test_two_books_use_one_immutable_previous_price_snapshot(self) -> None:
        prices = np.asarray([-0.5, 0.5])
        grid, _, source, coupling, result = _reference_step(
            previous_prices=prices, coupling_gamma=0.01
        )
        prices[:] = 7.0
        np.testing.assert_array_equal(result.previous_prices, [-0.5, 0.5])
        np.testing.assert_array_equal(result.price_inputs, [[-0.5, 0.5], [-0.5, 0.5]])
        expected = regularized_coupling_density(
            grid, -0.5, 0.5, source, coupling
        )
        np.testing.assert_allclose(
            result.directed_coupling_fields[0, 1], expected, rtol=0.0, atol=0.0
        )

    def test_external_shock_enters_once_through_the_source_increment(self) -> None:
        shock = np.zeros((2, 401))
        shock[0, 200] = -2.0
        _, _, _, _, result = _reference_step(shock_fields=shock)
        np.testing.assert_allclose(
            result.source_contributions,
            result.delta_u * result.net_sources,
            rtol=0.0,
            atol=0.0,
        )
        self.assertEqual(result.shock_fields[0, 200], -2.0)
        self.assertEqual(result.shock_fields[1, 200], 0.0)

    def test_outer_boundary_correction_is_explicit_and_interior_zero(self) -> None:
        _, _, _, _, result = _reference_step()
        np.testing.assert_array_equal(result.densities[:, [0, -1]], 0.0)
        np.testing.assert_array_equal(result.boundary_corrections[:, 1:-1], 0.0)
        np.testing.assert_allclose(
            result.densities,
            result.raw_densities + result.boundary_corrections,
            rtol=0.0,
            atol=0.0,
        )

    def test_solver_rejects_hidden_boundary_or_shape_policies(self) -> None:
        with self.assertRaises(ValueError):
            OperationalSolverSpec(0.1, 0.5, (0.0, 0.0), boundary_condition="neumann_zero_flux")
        density = np.ones((4, 2))
        with self.assertRaises(ValueError):
            spatial_neighbour_histories(density)
        with self.assertRaises(ReactionBoundaryError):
            extract_reaction_boundary(np.arange(5.0), np.ones(5))

    def test_target_solver_does_not_import_legacy_or_observation_layers(self) -> None:
        for filename in ("boundary.py", "solver.py"):
            path = PROJECT_ROOT / "functions" / "operational" / filename
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    self.assertFalse(module.startswith("functions.legacy"), filename)
                    self.assertFalse(module.startswith("functions.observation"), filename)

    def test_generated_solver_entry_diagnostic_contract(self) -> None:
        path = PROJECT_ROOT / "diagnostics" / "operational-solver-entry-v1.4.csv"
        self.assertTrue(path.is_file())
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 8)
        self.assertTrue(all(row["status"] == "Verified" for row in rows))
        self.assertEqual({row["software_version"] for row in rows}, {"1.4.0"})


if __name__ == "__main__":
    unittest.main()
