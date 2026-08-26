"""Generate the v1.3.5 operational innovation conformity evidence."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from functions.io_utils import write_csv
from functions.operational import (
    TwoBookInnovationPolicy,
    correlate_two_book_normals,
    two_book_operational_innovations,
)


OUTPUT_PATH = PROJECT_ROOT / "diagnostics" / "operational-innovation-checks-v1.3.csv"


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
        "software_version": "1.3.5",
    }


def _orthogonal_standard_inputs(points: int = 4096) -> np.ndarray:
    angle = 2.0 * np.pi * (np.arange(points, dtype=float) + 0.5) / points
    return np.column_stack((np.sqrt(2.0) * np.cos(angle), np.sqrt(2.0) * np.sin(angle)))


def build_rows() -> list[dict[str, object]]:
    base = _orthogonal_standard_inputs()
    independent = correlate_two_book_normals(base, 0.0)
    correlated = correlate_two_book_normals(base, 0.6)
    shared = correlate_two_book_normals(base, 1.0)
    antithetic = correlate_two_book_normals(base, -1.0)
    result = two_book_operational_innovations(
        base,
        TwoBookInnovationPolicy(2.0, 0.5, 0.6),
        transport_probability=0.5,
        delta_x=0.5,
        diffusion=[0.5, 0.5],
    )
    independent_covariance = independent.T @ independent / independent.shape[0]
    correlated_covariance = correlated.T @ correlated / correlated.shape[0]
    total_weight = result.stay_weights + result.plus_weights + result.minus_weights
    return [
        _row("IN-01", "PA-07", "book-one sigma applied once", np.sqrt(np.mean(result.velocities[:, 0] ** 2)), 2.0, 5e-16),
        _row("IN-02", "PA-07", "book-two sigma applied once", np.sqrt(np.mean(result.velocities[:, 1] ** 2)), 0.5, 2e-16),
        _row("IN-03", "PA-08", "independent operational covariance", independent_covariance[0, 1], 0.0, 2e-16),
        _row("IN-04", "PA-08", "declared operational correlation", correlated_covariance[0, 1], 0.6, 3e-16),
        _row("IN-05", "PA-08", "shared forcing endpoint", np.max(np.abs(shared[:, 1] - shared[:, 0])), 0.0, 0.0),
        _row("IN-06", "PA-08", "antithetic forcing endpoint", np.max(np.abs(antithetic[:, 1] + antithetic[:, 0])), 0.0, 0.0),
        _row("IN-07", "PA-07", "bounded DTRW jump bias", np.max(np.maximum(np.abs(result.jump_biases) - 0.5, 0.0)), 0.0, 0.0),
        _row("IN-08", "PA-07", "transport weights normalized", np.max(np.abs(total_weight - 1.0)), 0.0, 2e-16),
    ]


def main() -> int:
    rows = build_rows()
    write_csv(OUTPUT_PATH, list(rows[0]), rows)
    failures = [row for row in rows if row["status"] != "Verified"]
    for row in rows:
        print(f"{row['check_id']}: {row['status']} - {row['check']}")
    if failures:
        print(f"Operational innovation route failed: {len(failures)} check(s).")
        return 1
    print(f"Operational innovation route completed: {len(rows)} checks verified, 0 failures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
