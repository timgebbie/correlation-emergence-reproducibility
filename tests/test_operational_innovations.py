"""Tests for the v1.3.5 operational innovation conformity gate."""

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
    TwoBookInnovationPolicy,
    correlate_two_book_normals,
    transport_weights_from_bias,
    two_book_operational_innovations,
    velocity_to_jump_bias,
)


def _orthogonal_standard_inputs(points: int = 4096) -> np.ndarray:
    angle = 2.0 * np.pi * (np.arange(points, dtype=float) + 0.5) / points
    return np.column_stack((np.sqrt(2.0) * np.cos(angle), np.sqrt(2.0) * np.sin(angle)))


class OperationalInnovationTests(unittest.TestCase):
    def test_default_is_independent_operational_forcing(self) -> None:
        policy = TwoBookInnovationPolicy(1.0, 1.0)
        self.assertEqual(policy.correlation, 0.0)
        transformed = correlate_two_book_normals(_orthogonal_standard_inputs(), policy.correlation)
        covariance = transformed.T @ transformed / transformed.shape[0]
        np.testing.assert_allclose(covariance, np.eye(2), rtol=0.0, atol=4e-16)

    def test_declared_correlation_is_recovered_on_orthogonal_inputs(self) -> None:
        base = _orthogonal_standard_inputs()
        for rho in (-0.8, 0.35, 0.9):
            transformed = correlate_two_book_normals(base, rho)
            covariance = transformed.T @ transformed / transformed.shape[0]
            np.testing.assert_allclose(
                covariance,
                np.asarray([[1.0, rho], [rho, 1.0]]),
                rtol=0.0,
                atol=8e-16,
            )

    def test_shared_and_antithetic_endpoints_are_exact(self) -> None:
        base = np.asarray([[0.25, 7.0], [-1.5, 2.0], [3.0, -4.0]])
        shared = correlate_two_book_normals(base, 1.0)
        antithetic = correlate_two_book_normals(base, -1.0)
        np.testing.assert_array_equal(shared[:, 1], shared[:, 0])
        np.testing.assert_array_equal(antithetic[:, 1], -antithetic[:, 0])

    def test_sigma_is_applied_once(self) -> None:
        base = np.asarray([[0.25, -0.5], [1.0, 2.0]])
        result = two_book_operational_innovations(
            base,
            TwoBookInnovationPolicy(2.0, 0.5, 0.0),
            transport_probability=0.5,
            delta_x=0.5,
            diffusion=[0.5, 0.5],
        )
        np.testing.assert_array_equal(result.velocities, base * np.asarray([2.0, 0.5]))
        self.assertEqual(result.velocities[0, 0], 0.5)
        self.assertNotEqual(result.velocities[0, 0], 2.0**2 * base[0, 0])

    def test_jump_bias_matches_logistic_difference_and_is_bounded(self) -> None:
        velocities = np.asarray([-1e6, -2.0, 0.0, 2.0, 1e6])
        bias = np.asarray(
            velocity_to_jump_bias(
                velocities,
                transport_probability=0.5,
                delta_x=0.5,
                diffusion=0.5,
            )
        )
        z_value = velocities * 0.5 / (4.0 * 0.5)
        logistic_difference = 0.5 * (
            np.exp(np.clip(z_value, -700.0, 700.0))
            - np.exp(np.clip(-z_value, -700.0, 700.0))
        ) / (
            np.exp(np.clip(z_value, -700.0, 700.0))
            + np.exp(np.clip(-z_value, -700.0, 700.0))
        )
        np.testing.assert_allclose(bias[1:-1], logistic_difference[1:-1], rtol=0.0, atol=6e-17)
        self.assertTrue(np.all(np.abs(bias) <= 0.5))
        self.assertEqual(bias[2], 0.0)

    def test_transport_weights_are_nonnegative_and_normalized(self) -> None:
        bias = np.asarray([-0.5, -0.2, 0.0, 0.2, 0.5])
        stay, plus, minus = transport_weights_from_bias(bias, 0.5)
        self.assertTrue(np.all(np.asarray(stay) >= 0.0))
        self.assertTrue(np.all(np.asarray(plus) >= 0.0))
        self.assertTrue(np.all(np.asarray(minus) >= 0.0))
        np.testing.assert_array_equal(np.asarray(stay) + np.asarray(plus) + np.asarray(minus), np.ones(5))

    def test_zero_scale_gives_centred_transport(self) -> None:
        result = two_book_operational_innovations(
            _orthogonal_standard_inputs(32),
            TwoBookInnovationPolicy(0.0, 0.0, 1.0),
            transport_probability=0.5,
            delta_x=0.5,
            diffusion=[0.5, 0.5],
        )
        np.testing.assert_array_equal(result.velocities, np.zeros((32, 2)))
        np.testing.assert_array_equal(result.jump_biases, np.zeros((32, 2)))
        np.testing.assert_array_equal(result.plus_weights, np.full((32, 2), 0.25))
        np.testing.assert_array_equal(result.minus_weights, np.full((32, 2), 0.25))

    def test_inputs_are_external_and_copied(self) -> None:
        path = PROJECT_ROOT / "functions" / "operational" / "innovations.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported_modules = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertNotIn("random", imported_modules)
        base = np.asarray([[1.0, 2.0]])
        result = two_book_operational_innovations(
            base,
            TwoBookInnovationPolicy(1.0, 1.0),
            transport_probability=0.5,
            delta_x=0.5,
            diffusion=[0.5, 0.5],
        )
        base[:] = 0.0
        np.testing.assert_array_equal(result.base_standard_normals, [[1.0, 2.0]])

    def test_validation_rejects_ambiguous_or_invalid_policies(self) -> None:
        with self.assertRaises(ValueError):
            TwoBookInnovationPolicy(-1.0, 1.0)
        with self.assertRaises(ValueError):
            TwoBookInnovationPolicy(1.0, 1.0, 1.01)
        with self.assertRaises(ValueError):
            correlate_two_book_normals(np.ones((4, 3)), 0.0)
        with self.assertRaises(ValueError):
            transport_weights_from_bias(np.asarray([0.6]), 0.5)
        with self.assertRaises(ValueError):
            two_book_operational_innovations(
                np.ones((4, 2)),
                TwoBookInnovationPolicy(1.0, 1.0),
                transport_probability=0.5,
                delta_x=0.5,
                diffusion=[0.5],
            )

    def test_generated_innovation_diagnostic_contract(self) -> None:
        path = PROJECT_ROOT / "diagnostics" / "operational-innovation-checks-v1.3.csv"
        self.assertTrue(path.is_file())
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 8)
        self.assertTrue(all(row["status"] == "Verified" for row in rows))
        self.assertEqual({row["software_version"] for row in rows}, {"1.3.5"})


if __name__ == "__main__":
    unittest.main()
