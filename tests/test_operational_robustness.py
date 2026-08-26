"""Regression tests for the v1.4.2 operational robustness gate."""

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
    appendix_thickness_scales,
    errors_strictly_decrease,
    front_displacement_ratio,
    local_reaction_front_geometry,
    relative_l2_error,
)


class OperationalRobustnessTests(unittest.TestCase):
    def test_local_polynomial_recovers_front_geometry(self) -> None:
        grid = np.linspace(-2.0, 2.0, 81)
        boundary = 0.15
        local = grid - boundary
        density = 2.0 * local + 0.01 * local**2 + 0.001 * local**3
        geometry = local_reaction_front_geometry(grid, density, boundary)
        self.assertAlmostEqual(geometry.slope, 2.0, places=13)
        self.assertAlmostEqual(geometry.curvature, 0.02, places=13)
        self.assertAlmostEqual(geometry.curvature_length, 200.0, delta=1e-9)
        self.assertEqual(geometry.stencil_points, 7)

    def test_front_geometry_rejects_an_edge_stencil(self) -> None:
        grid = np.linspace(-2.0, 2.0, 81)
        with self.assertRaises(ValueError):
            local_reaction_front_geometry(grid, grid + 1.95, -1.95)

    def test_appendix_scales_preserve_each_distinct_width(self) -> None:
        scales = appendix_thickness_scales(
            delta_x=0.05,
            source_mu=0.1,
            reference_spread=1.0,
            reference_width=0.5,
            directed_spread=0.5,
            curvature_length=200.0,
        )
        self.assertAlmostEqual(scales.source_width, math.sqrt(10.0), places=15)
        self.assertEqual(scales.epsilon, 0.5)
        self.assertEqual(scales.selector_width, 1.0)
        self.assertEqual(scales.grid_to_reference_ratio, 0.1)
        self.assertAlmostEqual(
            scales.reference_to_source_ratio, 0.5 / math.sqrt(10.0), places=15
        )
        self.assertEqual(scales.selector_to_curvature_ratio, 0.005)
        self.assertEqual(
            front_displacement_ratio(0.5, slope=2.0, curvature=0.02), 0.0025
        )

    def test_zero_spread_width_is_a_declared_inactive_limit(self) -> None:
        scales = appendix_thickness_scales(
            delta_x=0.05,
            source_mu=0.1,
            reference_spread=1.0,
            reference_width=0.5,
            directed_spread=0.0,
            curvature_length=math.inf,
        )
        self.assertFalse(scales.coupling_active)
        self.assertTrue(math.isinf(scales.selector_width))
        self.assertTrue(math.isnan(scales.selector_to_curvature_ratio))
        self.assertEqual(scales.source_to_curvature_ratio, 0.0)

    def test_error_helpers_have_explicit_contracts(self) -> None:
        self.assertAlmostEqual(
            relative_l2_error(np.asarray([1.0, 2.1]), np.asarray([1.0, 2.0])),
            0.1 / math.sqrt(5.0),
            places=15,
        )
        self.assertTrue(errors_strictly_decrease(np.asarray([0.1, 0.02, 0.003])))
        self.assertFalse(errors_strictly_decrease(np.asarray([0.1, 0.02, 0.03])))
        with self.assertRaises(ValueError):
            errors_strictly_decrease(np.asarray([0.1, 0.0]))

    def test_generated_check_and_series_contracts(self) -> None:
        check_path = PROJECT_ROOT / "diagnostics" / "operational-robustness-checks-v1.4.csv"
        series_path = PROJECT_ROOT / "outputs" / "operational-robustness-series-v1.4.csv"
        with check_path.open("r", encoding="utf-8", newline="") as handle:
            checks = list(csv.DictReader(handle))
        with series_path.open("r", encoding="utf-8", newline="") as handle:
            series = list(csv.DictReader(handle))
        self.assertEqual(len(checks), 15)
        self.assertTrue(all(row["status"] == "Verified" for row in checks))
        self.assertEqual({row["software_version"] for row in checks}, {"1.4.2"})
        self.assertEqual(len(series), 21)
        self.assertEqual(
            {row["experiment_id"] for row in series},
            {
                "GRID-BOUNDARY",
                "GRID-SLOPE",
                "DOMAIN-BOUNDARY",
                "HISTORY-CUTOFF",
                "THICKNESS-MOMENT",
            },
        )

    def test_recorded_convergence_sequences_decrease(self) -> None:
        series_path = PROJECT_ROOT / "outputs" / "operational-robustness-series-v1.4.csv"
        with series_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        for experiment in (
            "GRID-BOUNDARY",
            "GRID-SLOPE",
            "DOMAIN-BOUNDARY",
            "HISTORY-CUTOFF",
            "THICKNESS-MOMENT",
        ):
            errors = [
                float(row["error"])
                for row in rows
                if row["experiment_id"] == experiment and float(row["error"]) > 0.0
            ]
            self.assertTrue(errors_strictly_decrease(np.asarray(errors)), experiment)

    def test_robustness_module_does_not_import_legacy_clock_or_observation_layers(self) -> None:
        path = PROJECT_ROOT / "functions" / "operational" / "robustness.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                self.assertFalse(module.startswith("functions.legacy"))
                self.assertFalse(module.startswith("functions.observation"))
                self.assertNotIn("clock", module)


if __name__ == "__main__":
    unittest.main()
