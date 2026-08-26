"""Complete ensembles and scale-dependent statistics in operational time."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from functions.operational.coupling import RegularizedCoupling
from functions.operational.initialization import BurnInPolicy
from functions.operational.innovations import TwoBookInnovationPolicy
from functions.operational.path import (
    OperationalPathError,
    operational_two_book_path,
)
from functions.operational.solver import OperationalSolverSpec
from functions.operational.source import OperationalSource


class OperationalEnsembleError(RuntimeError):
    """Raised when a declared member of an operational ensemble fails."""


@dataclass(frozen=True)
class OperationalTwoBookEnsembleResult:
    """Boundary observables and selected states from complete path members."""

    operational_times: np.ndarray
    prices: np.ndarray
    boundary_slopes: np.ndarray
    boundary_curvatures: np.ndarray
    boundary_curvature_lengths: np.ndarray
    boundary_candidate_counts: np.ndarray
    boundary_edge_distances: np.ndarray
    base_standard_normals: np.ndarray
    correlated_standard_normals: np.ndarray
    velocities: np.ndarray
    jump_biases: np.ndarray
    shock_l1_norms: np.ndarray
    burn_in_steps: np.ndarray
    density_snapshot_steps: np.ndarray
    density_snapshots: np.ndarray
    final_density_histories: np.ndarray
    completed_steps: int
    delta_u: float

    @property
    def paths(self) -> int:
        return int(self.prices.shape[0])


@dataclass(frozen=True)
class OperationalCorrelationCurve:
    """Realised two-boundary correlations across aggregation lags."""

    lags: np.ndarray
    operational_scales: np.ndarray
    pooled_correlations: np.ndarray
    path_correlations: np.ndarray
    path_mean_correlations: np.ndarray
    path_standard_deviations: np.ndarray
    path_standard_errors: np.ndarray
    sample_counts: np.ndarray
    estimator: str
    analysis_start_step: int


def operational_two_book_ensemble(
    price_grid: np.ndarray,
    initial_densities: np.ndarray,
    initial_prices: Sequence[float],
    sources: Sequence[OperationalSource],
    couplings: Sequence[Sequence[RegularizedCoupling | None]],
    raw_kernels: Sequence[np.ndarray],
    base_standard_normals: np.ndarray,
    innovation_policy: TwoBookInnovationPolicy,
    diffusion: Sequence[float],
    solver_spec: OperationalSolverSpec,
    *,
    shock_fields: np.ndarray | None = None,
    burn_in_policy: BurnInPolicy | None = None,
    density_snapshot_steps: Sequence[int] = (),
) -> OperationalTwoBookEnsembleResult:
    """Run every supplied operational path without owning a random generator."""

    base = np.asarray(base_standard_normals, dtype=float)
    if base.ndim != 3 or base.shape[0] < 1 or base.shape[1] < 1 or base.shape[2] != 2:
        raise ValueError("base_standard_normals must have shape (paths, steps, 2)")
    if not np.all(np.isfinite(base)):
        raise ValueError("base_standard_normals must be finite")
    paths, steps, _ = base.shape

    shocks: np.ndarray | None
    if shock_fields is None:
        shocks = None
    else:
        shocks = np.asarray(shock_fields, dtype=float)
        expected = (paths, steps, 2, np.asarray(price_grid).size)
        if shocks.shape != expected or not np.all(np.isfinite(shocks)):
            raise ValueError(
                "shock_fields must be finite with shape (paths, steps, 2, grid)"
            )
        shocks = np.array(shocks, copy=True)

    results = []
    for path_index in range(paths):
        try:
            result = operational_two_book_path(
                price_grid,
                initial_densities,
                initial_prices,
                sources,
                couplings,
                raw_kernels,
                base[path_index],
                innovation_policy,
                diffusion,
                solver_spec,
                shock_fields=None if shocks is None else shocks[path_index],
                burn_in_policy=burn_in_policy,
                stop_on_burn_in=False,
                density_snapshot_steps=density_snapshot_steps,
            )
        except OperationalPathError as error:
            raise OperationalEnsembleError(
                f"operational ensemble failed at path index {path_index}"
            ) from error
        if result.completed_steps != steps:
            raise OperationalEnsembleError(
                f"operational path index {path_index} stopped before the declared horizon"
            )
        results.append(result)

    first = results[0]
    for result in results[1:]:
        if not np.array_equal(result.operational_times, first.operational_times):
            raise OperationalEnsembleError("ensemble members do not share one operational grid")
        if not np.array_equal(
            result.density_snapshot_steps, first.density_snapshot_steps
        ):
            raise OperationalEnsembleError("ensemble snapshot steps are inconsistent")

    return OperationalTwoBookEnsembleResult(
        operational_times=first.operational_times.copy(),
        prices=np.stack([result.prices for result in results]),
        boundary_slopes=np.stack([result.boundary_slopes for result in results]),
        boundary_curvatures=np.stack(
            [result.boundary_curvatures for result in results]
        ),
        boundary_curvature_lengths=np.stack(
            [result.boundary_curvature_lengths for result in results]
        ),
        boundary_candidate_counts=np.stack(
            [result.boundary_candidate_counts for result in results]
        ),
        boundary_edge_distances=np.stack(
            [result.boundary_edge_distances for result in results]
        ),
        base_standard_normals=np.stack(
            [result.base_standard_normals for result in results]
        ),
        correlated_standard_normals=np.stack(
            [result.correlated_standard_normals for result in results]
        ),
        velocities=np.stack([result.velocities for result in results]),
        jump_biases=np.stack([result.jump_biases for result in results]),
        shock_l1_norms=np.stack([result.shock_l1_norms for result in results]),
        burn_in_steps=np.asarray(
            [-1 if result.burn_in_step is None else result.burn_in_step for result in results],
            dtype=int,
        ),
        density_snapshot_steps=first.density_snapshot_steps.copy(),
        density_snapshots=np.stack([result.density_snapshots for result in results]),
        final_density_histories=np.stack(
            [result.final_density_histories for result in results]
        ),
        completed_steps=steps,
        delta_u=solver_spec.delta_u,
    )


def _realised_correlation(two_book_returns: np.ndarray) -> float:
    values = np.asarray(two_book_returns, dtype=float)
    if values.ndim != 2 or values.shape[0] < 2 or values.shape[1] != 2:
        raise ValueError("two_book_returns must have shape (observations, 2)")
    if not np.all(np.isfinite(values)):
        raise ValueError("two_book_returns must be finite")
    scale = float(np.sqrt(np.sum(values[:, 0] ** 2) * np.sum(values[:, 1] ** 2)))
    if scale <= 0.0:
        raise ValueError("each boundary-return series must have nonzero variation")
    return float(np.sum(values[:, 0] * values[:, 1]) / scale)


def operational_correlation_curve(
    ensemble: OperationalTwoBookEnsembleResult,
    lags: Sequence[int],
    *,
    analysis_start_step: int = 0,
    estimator: str = "overlapping",
) -> OperationalCorrelationCurve:
    """Measure synchronous boundary-return correlation on the operational grid.

    ``overlapping`` uses every window of a declared lag. ``nonoverlapping``
    samples states at that lag before differencing. Both operate directly on
    the fixed operational grid and perform no interpolation or subordination.
    """

    if not isinstance(analysis_start_step, int) or analysis_start_step < 0:
        raise ValueError("analysis_start_step must be a nonnegative integer")
    if analysis_start_step >= ensemble.completed_steps:
        raise ValueError("analysis_start_step must precede the final state")
    lag_values = tuple(lags)
    if any(not isinstance(lag, (int, np.integer)) for lag in lag_values):
        raise ValueError("lags must contain integers")
    if tuple(sorted(set(int(lag) for lag in lag_values))) != lag_values:
        raise ValueError("lags must be sorted and unique")
    remaining = ensemble.completed_steps - analysis_start_step
    if not lag_values or any(lag < 1 or lag > remaining // 2 for lag in lag_values):
        raise ValueError("lags must allow at least two returns after analysis_start_step")
    if estimator not in ("overlapping", "nonoverlapping"):
        raise ValueError("estimator must be 'overlapping' or 'nonoverlapping'")

    prices = ensemble.prices[:, analysis_start_step:, :]
    path_values = np.empty((ensemble.paths, len(lag_values)), dtype=float)
    pooled_values = np.empty(len(lag_values), dtype=float)
    counts = np.empty(len(lag_values), dtype=int)
    for lag_index, lag in enumerate(lag_values):
        if estimator == "overlapping":
            returns = prices[:, lag:, :] - prices[:, :-lag, :]
        else:
            returns = np.diff(prices[:, ::lag, :], axis=1)
        counts[lag_index] = returns.shape[0] * returns.shape[1]
        pooled_values[lag_index] = _realised_correlation(returns.reshape(-1, 2))
        for path_index in range(ensemble.paths):
            path_values[path_index, lag_index] = _realised_correlation(
                returns[path_index]
            )

    means = np.mean(path_values, axis=0)
    if ensemble.paths == 1:
        deviations = np.zeros_like(means)
    else:
        deviations = np.std(path_values, axis=0, ddof=1)
    return OperationalCorrelationCurve(
        lags=np.asarray(lag_values, dtype=int),
        operational_scales=np.asarray(lag_values, dtype=float) * ensemble.delta_u,
        pooled_correlations=pooled_values,
        path_correlations=path_values,
        path_mean_correlations=means,
        path_standard_deviations=deviations,
        path_standard_errors=deviations / np.sqrt(float(ensemble.paths)),
        sample_counts=counts,
        estimator=estimator,
        analysis_start_step=analysis_start_step,
    )


def paired_boundary_price_response(
    control_prices: np.ndarray,
    shocked_prices: np.ndarray,
) -> np.ndarray:
    """Return shocked-minus-control boundary prices for matched paths."""

    control = np.asarray(control_prices, dtype=float)
    shocked = np.asarray(shocked_prices, dtype=float)
    if control.shape != shocked.shape or control.ndim < 2 or control.shape[-1] != 2:
        raise ValueError("control and shocked prices must have matching (..., time, 2) shapes")
    if not np.all(np.isfinite(control)) or not np.all(np.isfinite(shocked)):
        raise ValueError("control and shocked prices must be finite")
    return shocked - control


__all__ = [
    "OperationalCorrelationCurve",
    "OperationalEnsembleError",
    "OperationalTwoBookEnsembleResult",
    "operational_correlation_curve",
    "operational_two_book_ensemble",
    "paired_boundary_price_response",
]
