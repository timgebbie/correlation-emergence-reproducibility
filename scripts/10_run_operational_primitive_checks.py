"""Generate the v1.3.4 corrected operational-primitive evidence."""

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
    BurnInPolicy,
    OperationalSource,
    RegularizedCoupling,
    lattice_first_moment,
    operational_sibuya_kernel,
    operational_source_density,
    operational_uniform_memory_step,
    positive_half_first_moment,
    regularized_coupling_density,
    simultaneous_stationary_initialization,
)


OUTPUT_PATH = PROJECT_ROOT / "diagnostics" / "operational-primitive-checks-v1.3.csv"


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
        "software_version": "1.3.4",
    }


def build_rows() -> list[dict[str, object]]:
    source = OperationalSource(1.0, 0.1)
    coupling = RegularizedCoupling(0.3, 0.5)
    fine_grid = np.linspace(-50.0, 50.0, 20_001)
    positive_field = np.asarray(
        regularized_coupling_density(fine_grid, 1.0, -1.0, source, coupling)
    )
    negative_field = np.asarray(
        regularized_coupling_density(fine_grid, -1.0, 1.0, source, coupling)
    )
    zero_field = np.asarray(
        regularized_coupling_density(fine_grid, 0.0, 0.0, source, coupling)
    )
    expected_positive_moment = coupling.gamma * positive_half_first_moment(source) * 2.0
    expected_negative_moment = -expected_positive_moment

    density = np.asarray([[1.0], [2.0], [3.0]])
    left = density + 2.0
    right = density - 1.0
    step = operational_uniform_memory_step(
        density,
        left,
        right,
        operational_sibuya_kernel(1.0, 1),
        np.zeros(3),
        delta_u=0.125,
        cancellation_rate=14.0,
        transport_probability=0.5,
    )
    recent_transport = 0.25 * left[:, 0] + 0.25 * right[:, 0] - 0.5 * density[:, 0]

    initialization_grid = np.linspace(130.0, 330.0, 401)
    initialization = simultaneous_stationary_initialization(
        initialization_grid,
        [230.0, 230.0],
        [source, source],
        [[None, coupling], [coupling, None]],
        diffusion=[0.5, 0.5],
        cancellation_rates=[14.0, 14.0],
        boundary_condition="dirichlet_zero",
        burn_in_policy=BurnInPolicy(100, 1e-8, 5),
    )
    dx = initialization_grid[1] - initialization_grid[0]
    density0 = initialization.densities[0]
    stationary_residual = (
        0.5 * (density0[:-2] - 2.0 * density0[1:-1] + density0[2:]) / dx**2
        - 14.0 * density0[1:-1]
        + initialization.net_sources[0, 1:-1]
    )

    raw_kernel = operational_sibuya_kernel(0.8, 4)
    return [
        _row("OP-01", "PA-02", "corrected source value at y=1", operational_source_density(1.0, 0.0, source), -0.1 * math.exp(-0.1), 1e-15),
        _row("OP-02", "PA-02", "corrected source positive-half first moment", positive_half_first_moment(source), -math.sqrt(math.pi) / (4.0 * math.sqrt(0.1)), 1e-15),
        _row("OP-03", "PA-03", "zero-spread target coupling", np.max(np.abs(zero_field)), 0.0, 0.0),
        _row("OP-04", "PA-03", "positive-spread lattice moment", lattice_first_moment(fine_grid, 1.0, positive_field), expected_positive_moment, 2e-11),
        _row("OP-05", "PA-03", "negative-spread lattice moment", lattice_first_moment(fine_grid, -1.0, negative_field), expected_negative_moment, 2e-11),
        _row("OP-06", "PA-04", "raw Sibuya first coefficient", raw_kernel[0], 0.8, 0.0),
        _row("OP-07", "PA-04", "raw Sibuya second coefficient", raw_kernel[1], -0.08, 2e-17),
        _row("OP-08", "PA-04", "most-recent history has unit survival", np.max(np.abs(step.history_contribution - recent_transport)), 0.0, 1e-15),
        _row("OP-09", "PA-05", "simultaneous initial price snapshot", np.max(np.abs(initialization.price_inputs - 230.0)), 0.0, 0.0),
        _row("OP-10", "PA-05", "stationary initialization residual", np.max(np.abs(stationary_residual)), 0.0, 2e-13),
    ]


def main() -> int:
    rows = build_rows()
    write_csv(OUTPUT_PATH, list(rows[0]), rows)
    failures = [row for row in rows if row["status"] != "Verified"]
    for row in rows:
        print(f"{row['check_id']}: {row['status']} - {row['check']}")
    if failures:
        print(f"Operational primitive route failed: {len(failures)} check(s).")
        return 1
    print(f"Operational primitive route completed: {len(rows)} checks verified, 0 failures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
