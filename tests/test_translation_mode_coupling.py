"""Unit and integration tests for the v1.7.7 corrected coupling path."""

from __future__ import annotations

import ast
import hashlib
import json
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
    TranslationModeCoupling,
    TwoBookInnovationPolicy,
    apply_spatial_boundary,
    current_front_translation_mode,
    exponential_relaxation_rate,
    extract_reaction_boundary,
    linearized_translation_mode,
    local_drift_relaxation_rate,
    operational_sibuya_kernel,
    operational_source_density,
    operational_translation_two_book_path,
    operational_translation_two_book_step,
    stationary_density,
    translation_mode_coupling_density,
)


def _model(points: int = 201):
    grid = np.linspace(-10.0, 10.0, points)
    delta_x = float(grid[1] - grid[0])
    diffusion = 0.5
    transport = 0.5
    delta_u = transport * delta_x**2 / (2.0 * diffusion)
    source = OperationalSource(1.0, 0.1)
    stationary = apply_spatial_boundary(
        stationary_density(
            grid,
            np.asarray(operational_source_density(grid, 0.0, source)),
            diffusion=diffusion,
            cancellation_rate=0.0,
            boundary_condition="dirichlet_zero",
        )
    )
    kernels = (operational_sibuya_kernel(1.0, 1),) * 2
    specification = OperationalSolverSpec(
        delta_u,
        transport,
        (0.0, 0.0),
        minimum_abs_boundary_slope=1e-6,
    )
    return grid, diffusion, source, stationary, kernels, specification


def _perturbed_state(displacement: float):
    grid, diffusion, source, stationary, kernels, specification = _model()
    densities = np.stack(
        (
            linearized_translation_mode(grid, stationary, displacement),
            linearized_translation_mode(grid, stationary, -displacement),
        )
    )
    prices = np.empty(2, dtype=float)
    for book, expected in enumerate((displacement, -displacement)):
        prices[book] = extract_reaction_boundary(
            grid,
            densities[book],
            selection="nearest_previous",
            previous_price=expected,
            minimum_abs_slope=1e-6,
        ).price
    return grid, diffusion, source, densities, prices, kernels, specification


class TranslationModeCouplingTests(unittest.TestCase):
    def test_parameter_validation_and_zero_rate(self) -> None:
        self.assertEqual(TranslationModeCoupling(1.25).kappa_jk, 1.25)
        self.assertFalse(TranslationModeCoupling(1.25, enabled=False).enabled)
        with self.assertRaises(ValueError):
            TranslationModeCoupling(-1.0)
        with self.assertRaises(ValueError):
            TranslationModeCoupling(float("nan"))

    def test_current_front_mode_is_negative_spatial_derivative(self) -> None:
        grid = np.linspace(-2.0, 2.0, 41)
        density = grid**2 - 1.0
        mode = current_front_translation_mode(grid, density)
        np.testing.assert_allclose(mode[1:-1], -2.0 * grid[1:-1], atol=2e-14)
        np.testing.assert_array_equal(mode[[0, -1]], 0.0)

    def test_density_has_registered_sign_and_does_not_mutate_state(self) -> None:
        grid, _, _, stationary, _, _ = _model()
        stored = stationary.copy()
        coupling = TranslationModeCoupling(1.25)
        field = translation_mode_coupling_density(
            grid, 0.02, -0.02, stationary, coupling
        )
        mode = current_front_translation_mode(grid, stationary)
        np.testing.assert_allclose(field, -1.25 * 0.04 * mode, rtol=0.0, atol=0.0)
        np.testing.assert_array_equal(stationary, stored)
        np.testing.assert_array_equal(
            translation_mode_coupling_density(
                grid, 0.0, 0.0, stationary, coupling
            ),
            0.0,
        )

    def test_solver_uses_one_immutable_receiving_density_snapshot(self) -> None:
        grid, _, source, densities, prices, kernels, specification = (
            _perturbed_state(0.02)
        )
        stored = densities.copy()
        coupling = TranslationModeCoupling(1.25)
        result = operational_translation_two_book_step(
            grid,
            densities[:, :, None],
            prices,
            (source, source),
            ((None, coupling), (coupling, None)),
            kernels,
            (0.0, 0.0),
            specification,
        )
        for receiving, other in ((0, 1), (1, 0)):
            expected = translation_mode_coupling_density(
                grid,
                prices[receiving],
                prices[other],
                stored[receiving],
                coupling,
            )
            np.testing.assert_allclose(
                result.directed_coupling_fields[receiving, other],
                expected,
                rtol=0.0,
                atol=0.0,
            )
        np.testing.assert_array_equal(densities, stored)
        np.testing.assert_allclose(
            result.net_sources,
            result.source_fields + result.total_coupling_fields + result.shock_fields,
            rtol=0.0,
            atol=0.0,
        )

    def test_zero_spread_stationary_state_is_unchanged(self) -> None:
        grid, _, source, stationary, kernels, specification = _model()
        coupling = TranslationModeCoupling(1.25)
        result = operational_translation_two_book_step(
            grid,
            np.stack((stationary, stationary))[:, :, None],
            (0.0, 0.0),
            (source, source),
            ((None, coupling), (coupling, None)),
            kernels,
            (0.0, 0.0),
            specification,
        )
        np.testing.assert_array_equal(result.total_coupling_fields, 0.0)
        np.testing.assert_allclose(result.prices, 0.0, rtol=0.0, atol=5e-13)
        self.assertLess(
            float(np.max(np.abs(result.densities - stationary[None, :]))),
            2e-12,
        )

    def test_deterministic_path_recovers_registered_rate(self) -> None:
        grid, diffusion, source, densities, prices, kernels, specification = (
            _perturbed_state(0.02)
        )
        coupling = TranslationModeCoupling(1.25)
        common = {
            "price_grid": grid,
            "initial_densities": densities,
            "initial_prices": prices,
            "sources": (source, source),
            "raw_kernels": kernels,
            "base_standard_normals": np.zeros((160, 2)),
            "innovation_policy": TwoBookInnovationPolicy(0.0, 0.0, 0.0),
            "diffusion": (diffusion, diffusion),
            "solver_spec": specification,
        }
        coupled = operational_translation_two_book_path(
            **common,
            couplings=((None, coupling), (coupling, None)),
        )
        control = operational_translation_two_book_path(
            **common,
            couplings=((None, None), (None, None)),
        )
        coupled_spread = (coupled.prices[:, 0] - coupled.prices[:, 1])[None, :]
        control_spread = (control.prices[:, 0] - control.prices[:, 1])[None, :]
        exponential = exponential_relaxation_rate(
            coupled.operational_times,
            coupled_spread,
            control_spread,
            maximum_time=0.4,
        )
        local = local_drift_relaxation_rate(
            coupled_spread,
            control_spread,
            delta_time=specification.delta_u,
            fit_steps=80,
        )
        self.assertLess(abs(exponential.response_rate - 2.5) / 2.5, 0.01)
        self.assertLess(abs(local.response_rate - 2.5) / 2.5, 0.01)
        self.assertLess(
            float(np.max(np.abs(coupled.pair_centres - coupled.pair_centres[0]))),
            1e-12,
        )
        self.assertTrue(np.all(coupled.boundary_candidate_counts == 1))
        self.assertGreater(float(np.min(coupled.boundary_edge_distances)), 8.0)

    def test_accepted_comparator_modules_remain_exact(self) -> None:
        configuration = json.loads(
            (PROJECT_ROOT / "config" / "config-v1.7.6.json").read_text(
                encoding="utf-8"
            )
        )
        frozen = {
            record["path"]: record["sha256"]
            for record in configuration["accepted_inputs"]
            if record["path"]
            in {
                "functions/operational/coupling.py",
                "functions/operational/solver.py",
                "functions/operational/path.py",
            }
        }
        self.assertEqual(len(frozen), 3)
        for relative, expected in frozen.items():
            actual = hashlib.sha256((PROJECT_ROOT / relative).read_bytes()).hexdigest()
            self.assertEqual(actual, expected, relative)

    def test_corrected_modules_exclude_legacy_clock_and_observation_layers(self) -> None:
        for filename in (
            "translation_coupling.py",
            "translation_solver.py",
            "translation_path.py",
        ):
            path = PROJECT_ROOT / "functions" / "operational" / filename
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    self.assertFalse(module.startswith("functions.legacy"), filename)
                    self.assertFalse(module.startswith("functions.observation"), filename)
                    self.assertNotIn("clock", module, filename)


if __name__ == "__main__":
    unittest.main()
