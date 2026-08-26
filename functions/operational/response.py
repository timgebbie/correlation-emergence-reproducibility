"""Reduced coupling response and local reaction-front diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from functions.operational.boundary import apply_spatial_boundary


def _positive(name: str, value: float) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be positive and finite")
    return result


def coupling_covariance_build_up(
    response_rate: float,
    aggregation_scales: np.ndarray | float,
) -> np.ndarray | float:
    """Return ``1-(1-exp(-kappa*Delta))/(kappa*Delta)`` stably."""

    rate = _positive("response_rate", response_rate)
    scales = np.asarray(aggregation_scales, dtype=float)
    scalar = scales.ndim == 0
    values = np.atleast_1d(scales)
    if not np.all(np.isfinite(values)) or np.any(values < 0.0):
        raise ValueError("aggregation_scales must be finite and nonnegative")
    arguments = rate * values
    result = np.zeros_like(arguments)
    positive = arguments > 0.0
    result[positive] = 1.0 + np.expm1(-arguments[positive]) / arguments[positive]
    return float(result[0]) if scalar else result


def symmetric_closed_sde_correlation(
    response_rate: float,
    aggregation_scales: np.ndarray | float,
) -> np.ndarray | float:
    """Return the exact correlation of the symmetric closed two-price SDE.

    This is distinct from the covariance response normalized by ``C*Delta``.
    For ``x=kappa*Delta`` it equals
    ``(x-(1-exp(-x)))/(x+(1-exp(-x)))``.
    """

    rate = _positive("response_rate", response_rate)
    scales = np.asarray(aggregation_scales, dtype=float)
    scalar = scales.ndim == 0
    values = np.atleast_1d(scales)
    if not np.all(np.isfinite(values)) or np.any(values < 0.0):
        raise ValueError("aggregation_scales must be finite and nonnegative")
    arguments = rate * values
    result = np.zeros_like(arguments)
    positive = arguments > 0.0
    one_minus_survival = -np.expm1(-arguments[positive])
    result[positive] = (
        arguments[positive] - one_minus_survival
    ) / (arguments[positive] + one_minus_survival)
    return float(result[0]) if scalar else result


@dataclass(frozen=True)
class SymmetricLinearCouplingPaths:
    """Exact-grid paths for the symmetric linear coupling closure."""

    times: np.ndarray
    prices: np.ndarray
    centres: np.ndarray
    spreads: np.ndarray
    centre_standard_normals: np.ndarray
    spread_standard_normals: np.ndarray
    initial_spread_standard_normals: np.ndarray
    response_rate: float
    innovation_scale: float
    delta_time: float


def symmetric_linear_coupling_paths(
    centre_standard_normals: np.ndarray,
    spread_standard_normals: np.ndarray,
    initial_spread_standard_normals: np.ndarray,
    *,
    delta_time: float,
    response_rate: float,
    innovation_scale: float,
) -> SymmetricLinearCouplingPaths:
    """Advance the exact symmetric OU-spread closure on a uniform grid.

    The inputs are externally generated standard normals.  For equal book
    innovation scale ``sigma``, the centre has variance rate ``sigma^2/2``
    and the spread solves ``dz=-kappa*z*dt+sqrt(2)*sigma*dB``.  The spread is
    initialized from its stationary law.
    """

    centre_inputs = np.asarray(centre_standard_normals, dtype=float)
    spread_inputs = np.asarray(spread_standard_normals, dtype=float)
    initial_inputs = np.asarray(initial_spread_standard_normals, dtype=float)
    if (
        centre_inputs.ndim != 2
        or spread_inputs.shape != centre_inputs.shape
        or centre_inputs.shape[0] < 1
        or centre_inputs.shape[1] < 1
    ):
        raise ValueError("centre and spread normals must share shape (paths, steps)")
    if initial_inputs.shape != (centre_inputs.shape[0],):
        raise ValueError("initial spread normals must contain one value per path")
    if not (
        np.all(np.isfinite(centre_inputs))
        and np.all(np.isfinite(spread_inputs))
        and np.all(np.isfinite(initial_inputs))
    ):
        raise ValueError("all standard-normal inputs must be finite")
    step = _positive("delta_time", delta_time)
    rate = _positive("response_rate", response_rate)
    sigma = _positive("innovation_scale", innovation_scale)

    paths, steps = centre_inputs.shape
    decay = math.exp(-rate * step)
    centre_scale = sigma * math.sqrt(step / 2.0)
    spread_scale = sigma * math.sqrt((1.0 - decay * decay) / rate)
    centres = np.zeros((paths, steps + 1), dtype=float)
    spreads = np.empty_like(centres)
    spreads[:, 0] = sigma * initial_inputs / math.sqrt(rate)
    for index in range(steps):
        centres[:, index + 1] = (
            centres[:, index] + centre_scale * centre_inputs[:, index]
        )
        spreads[:, index + 1] = (
            decay * spreads[:, index] + spread_scale * spread_inputs[:, index]
        )
    prices = np.stack(
        (centres + 0.5 * spreads, centres - 0.5 * spreads), axis=2
    )
    return SymmetricLinearCouplingPaths(
        times=step * np.arange(steps + 1, dtype=float),
        prices=prices,
        centres=centres,
        spreads=spreads,
        centre_standard_normals=np.array(centre_inputs, copy=True),
        spread_standard_normals=np.array(spread_inputs, copy=True),
        initial_spread_standard_normals=np.array(initial_inputs, copy=True),
        response_rate=rate,
        innovation_scale=sigma,
        delta_time=step,
    )


def linearized_translation_mode(
    price_grid: np.ndarray,
    density: np.ndarray,
    displacement: float,
) -> np.ndarray:
    """Return ``phi(x)-displacement*phi_x(x)`` on the supplied grid.

    This constructs a controlled small front displacement without resampling
    the density or changing the operational grid.
    """

    grid = np.asarray(price_grid, dtype=float)
    field = np.asarray(density, dtype=float)
    shift = float(displacement)
    if (
        grid.ndim != 1
        or grid.size < 3
        or field.shape != grid.shape
        or not np.all(np.isfinite(grid))
        or not np.all(np.isfinite(field))
        or not math.isfinite(shift)
    ):
        raise ValueError("grid, density and displacement must be finite and compatible")
    differences = np.diff(grid)
    if np.any(differences <= 0.0) or not np.allclose(
        differences, differences[0], rtol=1e-12, atol=1e-14
    ):
        raise ValueError("price_grid must be strictly increasing and uniform")
    derivative = np.gradient(field, grid, edge_order=2)
    return apply_spatial_boundary(field - shift * derivative)


@dataclass(frozen=True)
class SpreadRelaxationEstimate:
    response_rate: float
    root_mean_square_residual: float
    observations: int
    sign_preserved: bool


def exponential_relaxation_rate(
    times: np.ndarray,
    coupled_spreads: np.ndarray,
    control_spreads: np.ndarray,
    *,
    maximum_time: float,
) -> SpreadRelaxationEstimate:
    """Fit ``log(abs(z_c/z_0))=-kappa*t`` through the origin."""

    time = np.asarray(times, dtype=float)
    coupled = np.asarray(coupled_spreads, dtype=float)
    control = np.asarray(control_spreads, dtype=float)
    limit = _positive("maximum_time", maximum_time)
    if time.ndim != 1 or coupled.ndim != 2 or coupled.shape != control.shape:
        raise ValueError("times must be a vector and spread arrays matching matrices")
    if coupled.shape[1] != time.size or time.size < 2:
        raise ValueError("spread time dimension must match at least two times")
    if not (
        np.all(np.isfinite(time))
        and np.all(np.isfinite(coupled))
        and np.all(np.isfinite(control))
    ):
        raise ValueError("times and spread arrays must be finite")
    if not np.isclose(time[0], 0.0) or np.any(np.diff(time) <= 0.0):
        raise ValueError("times must start at zero and increase strictly")
    selected = (time > 0.0) & (time <= limit)
    if not np.any(selected) or np.any(np.abs(control[:, selected]) <= 1e-15):
        raise ValueError("fit window must contain supported nonzero control spreads")
    ratios = coupled[:, selected] / control[:, selected]
    if np.any(np.abs(ratios) <= 1e-15):
        raise ValueError("coupled/control spread ratios must be nonzero")
    repeated_time = np.broadcast_to(time[selected], ratios.shape).ravel()
    logarithms = np.log(np.abs(ratios)).ravel()
    rate = -float(np.dot(repeated_time, logarithms) / np.dot(repeated_time, repeated_time))
    residuals = logarithms + rate * repeated_time
    sign_preserved = bool(
        np.all(np.sign(coupled[:, selected]) == np.sign(control[:, selected]))
    )
    return SpreadRelaxationEstimate(
        response_rate=rate,
        root_mean_square_residual=float(np.sqrt(np.mean(residuals**2))),
        observations=int(logarithms.size),
        sign_preserved=sign_preserved,
    )


def local_drift_relaxation_rate(
    coupled_spreads: np.ndarray,
    control_spreads: np.ndarray,
    *,
    delta_time: float,
    fit_steps: int,
) -> SpreadRelaxationEstimate:
    """Regress paired coupling-induced spread drift on the current spread."""

    coupled = np.asarray(coupled_spreads, dtype=float)
    control = np.asarray(control_spreads, dtype=float)
    step = _positive("delta_time", delta_time)
    if coupled.ndim != 2 or coupled.shape != control.shape or coupled.shape[1] < 2:
        raise ValueError("coupled and control spreads must be matching path matrices")
    if not np.all(np.isfinite(coupled)) or not np.all(np.isfinite(control)):
        raise ValueError("spread arrays must be finite")
    if not isinstance(fit_steps, int) or fit_steps < 1 or fit_steps >= coupled.shape[1]:
        raise ValueError("fit_steps must select available spread increments")
    predictor = coupled[:, :fit_steps].ravel()
    induced_drift = (
        np.diff(coupled[:, : fit_steps + 1], axis=1)
        - np.diff(control[:, : fit_steps + 1], axis=1)
    ).ravel() / step
    denominator = float(np.dot(predictor, predictor))
    if denominator <= 0.0:
        raise ValueError("spread predictor must have nonzero variation")
    rate = -float(np.dot(predictor, induced_drift) / denominator)
    residuals = induced_drift + rate * predictor
    return SpreadRelaxationEstimate(
        response_rate=rate,
        root_mean_square_residual=float(np.sqrt(np.mean(residuals**2))),
        observations=int(predictor.size),
        sign_preserved=bool(
            np.all(
                np.sign(coupled[:, : fit_steps + 1])
                == np.sign(control[:, : fit_steps + 1])
            )
        ),
    )


__all__ = [
    "SpreadRelaxationEstimate",
    "SymmetricLinearCouplingPaths",
    "coupling_covariance_build_up",
    "exponential_relaxation_rate",
    "linearized_translation_mode",
    "local_drift_relaxation_rate",
    "symmetric_closed_sde_correlation",
    "symmetric_linear_coupling_paths",
]
