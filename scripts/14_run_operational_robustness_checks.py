"""Generate the v1.4.2 operational robustness evidence."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from functions.io_utils import write_csv
from functions.operational import (
    OperationalSolverSpec,
    OperationalSource,
    RegularizedCoupling,
    TwoBookInnovationPolicy,
    appendix_thickness_scales,
    apply_spatial_boundary,
    errors_strictly_decrease,
    extract_reaction_boundary,
    front_displacement_ratio,
    lattice_first_moment,
    local_reaction_front_geometry,
    operational_sibuya_kernel,
    operational_source_density,
    operational_two_book_path,
    positive_half_first_moment,
    regularized_coupling_density,
    relative_l2_error,
    stationary_density,
)


CHECK_PATH = PROJECT_ROOT / "diagnostics" / "operational-robustness-checks-v1.4.csv"
SERIES_PATH = PROJECT_ROOT / "outputs" / "operational-robustness-series-v1.4.csv"


def _row(
    check_id: str,
    check: str,
    observed: float,
    expected: float,
    tolerance: float,
) -> dict[str, object]:
    error = abs(float(observed) - float(expected))
    return {
        "check_id": check_id,
        "check": check,
        "observed": observed,
        "expected": expected,
        "absolute_error": error,
        "tolerance": tolerance,
        "status": "Verified" if error <= tolerance else "Failed",
        "software_version": "1.4.2",
    }


def _series_row(
    experiment_id: str,
    control: str,
    control_value: float,
    metric: str,
    value: float,
    reference_value: float,
    error: float,
) -> dict[str, object]:
    return {
        "experiment_id": experiment_id,
        "control": control,
        "control_value": control_value,
        "metric": metric,
        "value": value,
        "reference_value": reference_value,
        "error": error,
        "software_version": "1.4.2",
    }


def _stationary_boundary(
    *,
    half_width: float,
    delta_x: float,
    source_price: float,
) -> tuple[float, float]:
    points = int(round(2.0 * half_width / delta_x)) + 1
    grid = np.linspace(-half_width, half_width, points)
    source = OperationalSource(1.0, 0.1)
    density = stationary_density(
        grid,
        np.asarray(operational_source_density(grid, source_price, source)),
        diffusion=0.5,
        cancellation_rate=1.0,
        boundary_condition="dirichlet_zero",
    )
    boundary = extract_reaction_boundary(
        grid,
        density,
        selection="nearest_previous",
        previous_price=source_price,
        minimum_abs_slope=1e-8,
    )
    return boundary.price, boundary.slope


def _history_cutoff_states() -> list[tuple[int, np.ndarray]]:
    grid = np.linspace(-10.0, 10.0, 201)
    delta_x = float(grid[1] - grid[0])
    alpha = 0.8
    diffusion = 0.5
    transport = 0.5
    delta_u = (transport * delta_x**2 / (2.0 * diffusion)) ** (1.0 / alpha)
    source = OperationalSource(1.0, 0.1)
    initial = apply_spatial_boundary(
        stationary_density(
            grid,
            np.asarray(operational_source_density(grid, 0.0, source)),
            diffusion=diffusion,
            cancellation_rate=1.0,
            boundary_condition="dirichlet_zero",
        )
    )
    coupling = RegularizedCoupling.from_reference_scale(0.01, 1.0, 0.5)
    results: list[tuple[int, np.ndarray]] = []
    for cutoff in (8, 16, 32, 64, 128):
        path = operational_two_book_path(
            grid,
            np.stack([initial, initial]),
            [0.0, 0.0],
            [source, source],
            [[None, coupling], [coupling, None]],
            [operational_sibuya_kernel(alpha, cutoff)] * 2,
            np.zeros((100, 2)),
            TwoBookInnovationPolicy(0.0, 0.0),
            [diffusion, diffusion],
            OperationalSolverSpec(
                delta_u,
                transport,
                (1.0, 1.0),
                minimum_abs_boundary_slope=1e-8,
            ),
            density_snapshot_steps=(100,),
        )
        results.append((cutoff, path.density_snapshots[-1]))
    return results


def build_evidence() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    series: list[dict[str, object]] = []

    geometry_grid = np.linspace(-2.0, 2.0, 81)
    boundary_price = 0.15
    local = geometry_grid - boundary_price
    geometry_density = 2.0 * local + 0.01 * local**2 + 0.001 * local**3
    geometry = local_reaction_front_geometry(
        geometry_grid, geometry_density, boundary_price
    )
    scales = appendix_thickness_scales(
        delta_x=0.05,
        source_mu=0.1,
        reference_spread=1.0,
        reference_width=0.5,
        directed_spread=0.5,
        curvature_length=geometry.curvature_length,
    )
    inactive_scales = appendix_thickness_scales(
        delta_x=0.05,
        source_mu=0.1,
        reference_spread=1.0,
        reference_width=0.5,
        directed_spread=0.0,
        curvature_length=geometry.curvature_length,
    )

    grid_controls = (0.2, 0.1, 0.05, 0.025)
    grid_values = [
        _stationary_boundary(half_width=20.0, delta_x=spacing, source_price=0.37)
        for spacing in grid_controls
    ]
    grid_reference_price, grid_reference_slope = grid_values[-1]
    grid_price_errors = np.asarray(
        [abs(value[0] - grid_reference_price) for value in grid_values[:-1]]
    )
    grid_slope_errors = np.asarray(
        [abs(value[1] - grid_reference_slope) for value in grid_values[:-1]]
    )
    for spacing, (price, slope) in zip(grid_controls, grid_values):
        series.append(
            _series_row(
                "GRID-BOUNDARY",
                "delta_x",
                spacing,
                "reaction_boundary_price",
                price,
                grid_reference_price,
                abs(price - grid_reference_price),
            )
        )
        series.append(
            _series_row(
                "GRID-SLOPE",
                "delta_x",
                spacing,
                "reaction_boundary_slope",
                slope,
                grid_reference_slope,
                abs(slope - grid_reference_slope),
            )
        )

    domain_controls = (5.0, 10.0, 20.0)
    domain_prices = [
        _stationary_boundary(half_width=width, delta_x=0.1, source_price=0.5)[0]
        for width in domain_controls
    ]
    domain_errors = np.asarray([abs(price - 0.5) for price in domain_prices])
    for width, price, error in zip(domain_controls, domain_prices, domain_errors):
        series.append(
            _series_row(
                "DOMAIN-BOUNDARY",
                "domain_half_width",
                width,
                "reaction_boundary_price",
                price,
                0.5,
                error,
            )
        )

    history_states = _history_cutoff_states()
    history_reference = history_states[-1][1]
    history_errors = np.asarray(
        [relative_l2_error(state, history_reference) for _, state in history_states[:-1]]
    )
    for cutoff, state in history_states:
        error = relative_l2_error(state, history_reference)
        series.append(
            _series_row(
                "HISTORY-CUTOFF",
                "kernel_terms",
                float(cutoff),
                "final_density_relative_l2_error",
                error,
                0.0,
                error,
            )
        )

    thickness_controls = (0.4, 0.2, 0.1, 0.05, 0.025)
    thickness_source = OperationalSource(1.0, 0.1)
    thickness_coupling = RegularizedCoupling.from_reference_scale(0.3, 1.0, 0.5)
    thickness_moments: list[float] = []
    for spacing in thickness_controls:
        thickness_grid = np.linspace(-8.0, 8.0, int(round(16.0 / spacing)) + 1)
        field = regularized_coupling_density(
            thickness_grid,
            0.37,
            -0.63,
            thickness_source,
            thickness_coupling,
        )
        thickness_moments.append(
            lattice_first_moment(thickness_grid, 0.37, np.asarray(field))
        )
    thickness_reference = thickness_moments[-1]
    thickness_errors = np.asarray(
        [abs(value - thickness_reference) for value in thickness_moments[:-1]]
    )
    continuum_moment = (
        thickness_coupling.gamma
        * positive_half_first_moment(thickness_source)
    )
    for spacing, moment in zip(thickness_controls, thickness_moments):
        series.append(
            _series_row(
                "THICKNESS-MOMENT",
                "delta_x",
                spacing,
                "regularized_coupling_first_moment",
                moment,
                thickness_reference,
                abs(moment - thickness_reference),
            )
        )

    checks = [
        _row("ROB-01", "local front slope", geometry.slope, 2.0, 1e-12),
        _row("ROB-02", "local front curvature", geometry.curvature, 0.02, 1e-12),
        _row("ROB-03", "local front curvature length", geometry.curvature_length, 200.0, 1e-9),
        _row("ROB-04", "grid boundary errors strictly decrease", float(errors_strictly_decrease(grid_price_errors)), 1.0, 0.0),
        _row("ROB-05", "grid slope errors strictly decrease", float(errors_strictly_decrease(grid_slope_errors)), 1.0, 0.0),
        _row("ROB-06", "domain boundary errors strictly decrease", float(errors_strictly_decrease(domain_errors)), 1.0, 0.0),
        _row("ROB-07", "history-cutoff errors strictly decrease", float(errors_strictly_decrease(history_errors)), 1.0, 0.0),
        _row("ROB-08", "grid-to-reference-width ratio", scales.grid_to_reference_ratio, 0.1, 1e-15),
        _row("ROB-09", "reference-to-source-width ratio", scales.reference_to_source_ratio, 0.5 * math.sqrt(0.1), 1e-15),
        _row("ROB-10", "dynamic selector width", scales.selector_width, 1.0, 0.0),
        _row("ROB-11", "source-to-curvature ratio", scales.source_to_curvature_ratio, math.sqrt(10.0) / 200.0, 1e-14),
        _row("ROB-12", "zero-spread layer is inactive with infinite limiting width", float((not inactive_scales.coupling_active) and math.isinf(inactive_scales.selector_width) and math.isnan(inactive_scales.selector_to_curvature_ratio)), 1.0, 0.0),
        _row("ROB-13", "appendix displacement nonlinearity ratio", front_displacement_ratio(0.5, slope=geometry.slope, curvature=geometry.curvature), 0.0025, 1e-15),
        _row("ROB-14", "regularized lattice-moment errors strictly decrease", float(errors_strictly_decrease(thickness_errors)), 1.0, 0.0),
        _row("ROB-15", "finite-domain moment is within one percent of the continuum value", float(abs(thickness_reference - continuum_moment) / abs(continuum_moment) < 0.01), 1.0, 0.0),
    ]
    return checks, series


def main() -> int:
    checks, series = build_evidence()
    write_csv(CHECK_PATH, list(checks[0]), checks)
    write_csv(SERIES_PATH, list(series[0]), series)
    failures = [row for row in checks if row["status"] != "Verified"]
    for row in checks:
        print(f"{row['check_id']}: {row['status']} - {row['check']}")
    if failures:
        print(f"Operational robustness route failed: {len(failures)} check(s).")
        return 1
    print(
        f"Operational robustness route completed: {len(checks)} checks verified, "
        f"{len(series)} convergence rows, 0 failures."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
