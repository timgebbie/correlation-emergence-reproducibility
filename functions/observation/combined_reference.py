"""Exact conditional moments for the reduced coupled process under clocks.

The operational process is the stationary symmetric two-price closure

``p1 = c + z/2`` and ``p2 = c - z/2``,

where the pair centre is Brownian and the spread is Ornstein--Uhlenbeck.  The
functions here condition on already-realised previous-refresh operational
indices.  They own no clock, random number generator, interpolation or
operational dynamics.
"""

from __future__ import annotations

from typing import Sequence
import math

import numpy as np


def _positive(name: str, value: float) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be positive and finite")
    return result


def _lags(values: Sequence[int], observations: int) -> np.ndarray:
    items = tuple(values)
    if any(not isinstance(value, (int, np.integer)) for value in items):
        raise ValueError("lags must contain integers")
    normalized = tuple(int(value) for value in items)
    if not normalized or tuple(sorted(set(normalized))) != normalized:
        raise ValueError("lags must be nonempty, sorted and unique")
    if any(value < 1 or value > observations - 2 for value in normalized):
        raise ValueError("lags must leave at least two return windows")
    return np.asarray(normalized, dtype=int)


def symmetric_previous_refresh_expected_components(
    operational_indices: np.ndarray,
    lags: Sequence[int],
    *,
    operational_step: float,
    response_rate: float,
) -> np.ndarray:
    """Return exact conditional cross- and marginal-moment sums.

    The output has columns ``cross_covariance``, ``variance_book_one`` and
    ``variance_book_two``.  Moments use a unit pair-centre variance rate; that
    common scale cancels from the correlation and makes the cross-covariance
    divided by ``windows * Delta`` directly comparable with the normalized
    paper envelope.

    The operational indices must be those actually selected by the
    previous-refresh then previous-uniform-state observation rule.  This is
    therefore an estimator-aware reduced reference, not the leading-order
    separable product.
    """

    indices = np.asarray(operational_indices)
    if (
        indices.ndim != 2
        or indices.shape[1] != 2
        or not np.issubdtype(indices.dtype, np.integer)
        or np.any(indices < 0)
        or np.any(np.diff(indices, axis=0) < 0)
    ):
        raise ValueError(
            "operational_indices must be nonnegative monotone integer pairs"
        )
    step = _positive("operational_step", operational_step)
    rate = _positive("response_rate", response_rate)
    lag_values = _lags(lags, indices.shape[0])
    components = np.empty((lag_values.size, 3), dtype=float)

    for position, lag in enumerate(lag_values):
        starts = indices[:-lag]
        stops = indices[lag:]
        a = step * starts[:, 0]
        b = step * stops[:, 0]
        c = step * starts[:, 1]
        d = step * stops[:, 1]

        overlap = np.maximum(0.0, np.minimum(b, d) - np.maximum(a, c))
        ou_increment_kernel = (
            np.exp(-rate * np.abs(b - d))
            - np.exp(-rate * np.abs(b - c))
            - np.exp(-rate * np.abs(a - d))
            + np.exp(-rate * np.abs(a - c))
        )
        cross_covariance = overlap - ou_increment_kernel / (2.0 * rate)

        length_one = b - a
        length_two = d - c
        variance_one = length_one - np.expm1(-rate * length_one) / rate
        variance_two = length_two - np.expm1(-rate * length_two) / rate
        if np.any(length_one < 0.0) or np.any(length_two < 0.0):
            raise RuntimeError("selected operational intervals must be nonnegative")

        components[position] = (
            np.sum(cross_covariance),
            np.sum(variance_one),
            np.sum(variance_two),
        )

    if not np.all(np.isfinite(components)) or np.any(components[:, 1:] <= 0.0):
        raise RuntimeError("exact conditional components must be finite and supported")
    components.setflags(write=False)
    return components


__all__ = ["symmetric_previous_refresh_expected_components"]
