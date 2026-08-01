"""Ordinary and fractional Epps build-up kernels.

The ordinary kernel implements Eq. (A.15)/(B.20) of the frozen target paper.
The fractional kernel implements Eq. (A.19)/(C.16) on the non-negative real
axis.  For 0 < alpha < 1 it uses the Pollard real-axis representation of the
Mittag-Leffler survival function, integrated with deterministic composite
Gauss-Legendre quadrature.  Small arguments use the defining series to avoid
loss of significance.  Alpha=1 is evaluated by the ordinary closed form.
"""

from __future__ import annotations

from functools import lru_cache
from math import gamma, pi

import numpy as np
from numpy.polynomial.legendre import leggauss


def _validated_nonnegative(values: np.ndarray | float, name: str) -> tuple[np.ndarray, bool]:
    array = np.asarray(values, dtype=float)
    scalar = array.ndim == 0
    array = np.atleast_1d(array)
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")
    if np.any(array < 0.0):
        raise ValueError(f"{name} must be non-negative")
    return array, scalar


def _restore_shape(values: np.ndarray, scalar: bool) -> np.ndarray | float:
    return float(values[0]) if scalar else values


def ordinary_build_up(x: np.ndarray | float, series_switch: float = 1.0e-3) -> np.ndarray | float:
    """Return F(x)=1-(1-exp(-x))/x for non-negative x.

    A local series is used near zero.  Elsewhere ``expm1`` avoids cancellation
    in the exponential difference.
    """

    values, scalar = _validated_nonnegative(x, "x")
    result = np.empty_like(values)
    small = values <= series_switch
    xs = values[small]
    result[small] = xs * (
        0.5
        + xs * (-1.0 / 6.0 + xs * (1.0 / 24.0 + xs * (-1.0 / 120.0 + xs / 720.0)))
    )
    large = ~small
    xl = values[large]
    result[large] = 1.0 + np.expm1(-xl) / xl
    result[values == 0.0] = 0.0
    return _restore_shape(result, scalar)


def ordinary_derivative(x: np.ndarray | float, series_switch: float = 1.0e-3) -> np.ndarray | float:
    """Return F'(x) with the continuous value F'(0)=1/2."""

    values, scalar = _validated_nonnegative(x, "x")
    result = np.empty_like(values)
    small = values <= series_switch
    xs = values[small]
    result[small] = 0.5 + xs * (
        -1.0 / 3.0 + xs * (1.0 / 8.0 + xs * (-1.0 / 30.0 + xs / 144.0))
    )
    large = ~small
    xl = values[large]
    result[large] = (1.0 - (1.0 + xl) * np.exp(-xl)) / (xl * xl)
    return _restore_shape(result, scalar)


def rate_elasticity(x: np.ndarray | float) -> np.ndarray | float:
    """Return the local log-elasticity x F'(x)/F(x), with limit one at zero."""

    values, scalar = _validated_nonnegative(x, "x")
    result = np.ones_like(values)
    positive = values > 0.0
    xp = values[positive]
    result[positive] = xp * np.asarray(ordinary_derivative(xp)) / np.asarray(ordinary_build_up(xp))
    return _restore_shape(result, scalar)


def exponential_memory(lag: np.ndarray | float, rate: float) -> np.ndarray | float:
    """Return the ordinary survival/memory diagnostic exp(-rate * lag)."""

    values, scalar = _validated_nonnegative(lag, "lag")
    if not np.isfinite(rate) or rate <= 0.0:
        raise ValueError("rate must be positive and finite")
    result = np.exp(-rate * values)
    return _restore_shape(result, scalar)


@lru_cache(maxsize=16)
def _composite_log_quadrature(order: int, log_limit: float) -> tuple[np.ndarray, np.ndarray]:
    if order < 24:
        raise ValueError("quadrature order must be at least 24")
    if log_limit < 12.0:
        raise ValueError("quadrature log limit must be at least 12")
    breaks = (-log_limit, -8.0, -2.0, 2.0, 8.0, log_limit)
    base_nodes, base_weights = leggauss(order)
    nodes: list[np.ndarray] = []
    weights: list[np.ndarray] = []
    for left, right in zip(breaks[:-1], breaks[1:]):
        nodes.append(0.5 * (right - left) * base_nodes + 0.5 * (right + left))
        weights.append(0.5 * (right - left) * base_weights)
    return np.concatenate(nodes), np.concatenate(weights)


def _fractional_small_x_series(x: np.ndarray, alpha: float, tolerance: float = 2.0e-16) -> np.ndarray:
    """Evaluate 1-E_{alpha,2}(-x) from its alternating power series."""

    result = np.zeros_like(x)
    power = x.copy()
    sign = 1.0
    for k in range(1, 200):
        term = sign * power / gamma(alpha * k + 2.0)
        result += term
        if np.all(np.abs(term) <= tolerance * np.maximum(1.0, np.abs(result))):
            break
        power *= x
        sign *= -1.0
    else:
        raise RuntimeError("fractional small-argument series did not converge")
    return result


def fractional_build_up(
    delta: np.ndarray | float,
    alpha: float,
    characteristic_time: float = 1.0,
    *,
    series_switch: float = 0.25,
    quadrature_order: int = 96,
    quadrature_log_limit: float = 48.0,
) -> np.ndarray | float:
    """Return 1-E_{alpha,2}[-(delta/tau)^alpha] for 0 < alpha <= 1.

    The validated release profiles use alpha in {0.6, 0.8, 1.0}.  The real-axis
    quadrature is applicable to 0 < alpha < 1, while the ordinary endpoint is
    handled exactly.
    """

    values, scalar = _validated_nonnegative(delta, "delta")
    if not np.isfinite(alpha) or not (0.0 < alpha <= 1.0):
        raise ValueError("alpha must satisfy 0 < alpha <= 1")
    if not np.isfinite(characteristic_time) or characteristic_time <= 0.0:
        raise ValueError("characteristic_time must be positive and finite")

    dimensionless = values / characteristic_time
    x = np.power(dimensionless, alpha)
    if alpha == 1.0:
        return _restore_shape(np.asarray(ordinary_build_up(x)), scalar)

    result = np.empty_like(x)
    small = x <= series_switch
    if np.any(small):
        result[small] = _fractional_small_x_series(x[small], alpha)

    remaining = ~small
    if np.any(remaining):
        u, weights = _composite_log_quadrature(quadrature_order, quadrature_log_limit)
        r_alpha = np.exp(alpha * u)
        density_du = (
            np.sin(pi * alpha)
            / pi
            * r_alpha
            / (r_alpha * r_alpha + 2.0 * r_alpha * np.cos(pi * alpha) + 1.0)
        )
        t = np.power(x[remaining], 1.0 / alpha)
        rt = np.exp(u)[:, None] * t[None, :]
        averaging = np.empty_like(rt)
        tiny = rt < 1.0e-7
        y = rt[tiny]
        averaging[tiny] = 1.0 - y / 2.0 + y * y / 6.0 - y * y * y / 24.0
        averaging[~tiny] = -np.expm1(-rt[~tiny]) / rt[~tiny]
        survival_average = np.sum(weights[:, None] * density_du[:, None] * averaging, axis=0)
        result[remaining] = 1.0 - survival_average

    result[x == 0.0] = 0.0
    return _restore_shape(result, scalar)


def combined_build_up(clock: np.ndarray | float, response: np.ndarray | float) -> np.ndarray | float:
    """Return the paper's leading-order separable product of two attenuation factors."""

    left = np.asarray(clock, dtype=float)
    right = np.asarray(response, dtype=float)
    if np.any(~np.isfinite(left)) or np.any(~np.isfinite(right)):
        raise ValueError("components must be finite")
    if np.any((left < 0.0) | (left > 1.0)) or np.any((right < 0.0) | (right > 1.0)):
        raise ValueError("components must lie in [0, 1]")
    product = left * right
    return float(product) if product.ndim == 0 else product


__all__ = [
    "ordinary_build_up",
    "ordinary_derivative",
    "rate_elasticity",
    "exponential_memory",
    "fractional_build_up",
    "combined_build_up",
]
