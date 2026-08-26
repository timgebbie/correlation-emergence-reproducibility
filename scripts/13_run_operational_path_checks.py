"""Generate the v1.4.1 rolling operational-path evidence."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from functions.io_utils import write_csv
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


OUTPUT_PATH = PROJECT_ROOT / "diagnostics" / "operational-path-checks-v1.4.csv"


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
        "software_version": "1.4.1",
    }


def build_rows() -> list[dict[str, object]]:
    grid = np.linspace(-10.0, 10.0, 201)
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
    coupling = RegularizedCoupling.from_reference_scale(0.01, 1.0, 0.5)
    shocks = np.zeros((10, 2, grid.size))
    shocks[7, 0, grid.size // 2] = 1e-3
    path = operational_two_book_path(
        grid,
        np.stack([stationary, stationary]),
        [0.0, 0.0],
        [source, source],
        [[None, coupling], [coupling, None]],
        [operational_sibuya_kernel(1.0, 5)] * 2,
        np.zeros((10, 2)),
        TwoBookInnovationPolicy(1.0, 1.0),
        [diffusion, diffusion],
        OperationalSolverSpec(
            delta_u,
            transport,
            (0.0, 0.0),
            minimum_abs_boundary_slope=1e-6,
        ),
        shock_fields=shocks,
        burn_in_policy=BurnInPolicy(4, 1e-10, 2),
        density_snapshot_steps=(0, 5, 10),
    )
    width_values = regularized_transition_width(
        np.asarray([0.5, 2.0]), coupling.epsilon
    )
    no_shock_prefix_error = float(
        np.max(path.relative_state_changes[:7])
    )
    return [
        _row("OPATH-01", "reference-scale epsilon", regularization_epsilon(1.0, 0.5), 0.5, 0.0),
        _row("OPATH-02", "state-dependent width at z=0.5", width_values[0], 1.0, 0.0),
        _row("OPATH-03", "state-dependent width at z=2", width_values[1], 0.25, 0.0),
        _row("OPATH-04", "uniform operational-time increments", np.max(np.abs(np.diff(path.operational_times) - delta_u)), 0.0, 2e-18),
        _row("OPATH-05", "stationary pre-shock path", no_shock_prefix_error, 0.0, 2e-14),
        _row("OPATH-06", "executed burn-in step", path.burn_in_step or -1, 4.0, 0.0),
        _row("OPATH-07", "bounded rolling history columns", path.final_density_histories.shape[-1], 5.0, 0.0),
        _row("OPATH-08", "external shock operational step", np.argmax(path.shock_l1_norms[:, 0]) + 1, 8.0, 0.0),
    ]


def main() -> int:
    rows = build_rows()
    write_csv(OUTPUT_PATH, list(rows[0]), rows)
    failures = [row for row in rows if row["status"] != "Verified"]
    for row in rows:
        print(f"{row['check_id']}: {row['status']} - {row['check']}")
    if failures:
        print(f"Operational path route failed: {len(failures)} check(s).")
        return 1
    print(f"Operational path route completed: {len(rows)} checks verified, 0 failures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
