"""Generate the v1.4.0 operational solver-entry evidence."""

from __future__ import annotations

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
    apply_spatial_boundary,
    extract_reaction_boundary,
    operational_sibuya_kernel,
    operational_source_density,
    operational_two_book_step,
    spatial_neighbour_histories,
    stationary_density,
)


OUTPUT_PATH = PROJECT_ROOT / "diagnostics" / "operational-solver-entry-v1.4.csv"


def _row(
    check_id: str,
    finding_id: str,
    check: str,
    observed: float,
    expected: float,
    tolerance: float,
) -> dict[str, object]:
    error = abs(float(observed) - float(expected))
    return {
        "check_id": check_id,
        "finding_id": finding_id,
        "check": check,
        "observed": observed,
        "expected": expected,
        "absolute_error": error,
        "tolerance": tolerance,
        "status": "Verified" if error <= tolerance else "Failed",
        "software_version": "1.4.0",
    }


def build_rows() -> list[dict[str, object]]:
    boundary_grid = np.linspace(-2.0, 2.0, 9)
    exact = extract_reaction_boundary(boundary_grid, boundary_grid.copy())
    interpolated = extract_reaction_boundary(boundary_grid, boundary_grid - 0.2)
    multiple_density = (boundary_grid + 1.0) * boundary_grid * (boundary_grid - 1.5)
    nearest = extract_reaction_boundary(
        boundary_grid,
        multiple_density,
        selection="nearest_previous",
        previous_price=1.4,
    )

    neighbour_density = np.asarray(
        [[0.0], [1.0], [3.0], [0.0]], dtype=float
    )
    left, right = spatial_neighbour_histories(neighbour_density)
    ghost_maximum = max(abs(left[0, 0]), abs(right[-1, 0]))

    grid = np.linspace(-10.0, 10.0, 401)
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
    histories = np.stack([stationary, stationary])[:, :, None]
    coupling = RegularizedCoupling(0.3, 0.5)
    step = operational_two_book_step(
        grid,
        histories,
        [0.0, 0.0],
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
    )
    fixed_point_error = float(np.max(np.abs(step.densities - histories[:, :, 0])))
    decomposition_error = float(
        np.max(
            np.abs(
                step.densities
                - step.raw_densities
                - step.boundary_corrections
            )
        )
    )
    return [
        _row("OS-01", "PA-10", "exact-grid reaction boundary", exact.price, 0.0, 0.0),
        _row("OS-02", "PA-10", "off-grid linear reaction boundary", interpolated.price, 0.2, 2e-16),
        _row("OS-03", "PA-10", "nearest previous multiple-root selection", nearest.price, 1.5, 2e-16),
        _row("OS-04", "PA-19", "Dirichlet ghost values", ghost_maximum, 0.0, 0.0),
        _row("OS-05", "PA-20", "uniform operational increment", step.delta_u, delta_u, 0.0),
        _row("OS-06", "PA-20", "stationary one-step fixed point", fixed_point_error, 0.0, 2e-12),
        _row(
            "OS-07",
            "PA-19",
            "exact outer boundary values",
            np.max(np.abs(step.densities[:, [0, -1]])),
            0.0,
            0.0,
        ),
        _row("OS-08", "PA-19", "explicit boundary correction decomposition", decomposition_error, 0.0, 1e-18),
    ]


def main() -> int:
    rows = build_rows()
    write_csv(OUTPUT_PATH, list(rows[0]), rows)
    failures = [row for row in rows if row["status"] != "Verified"]
    for row in rows:
        print(f"{row['check_id']}: {row['status']} - {row['check']}")
    if failures:
        print(f"Operational solver-entry route failed: {len(failures)} check(s).")
        return 1
    print(f"Operational solver-entry route completed: {len(rows)} checks verified, 0 failures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
