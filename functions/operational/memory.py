"""Raw Sibuya memory and single-survival operational-time update."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


def _finite(name: str, value: float) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


@dataclass(frozen=True)
class OperationalStepResult:
    density: np.ndarray
    history_contribution: np.ndarray
    survivor_contribution: np.ndarray
    source_contribution: np.ndarray


def operational_sibuya_kernel(order: float, terms: int) -> np.ndarray:
    """Return raw Sibuya coefficients with no cancellation weighting."""

    alpha = _finite("order", order)
    if not 0.0 < alpha <= 1.0:
        raise ValueError("order must lie in (0, 1]")
    if not isinstance(terms, int) or terms < 1:
        raise ValueError("terms must be a positive integer")
    coefficients = np.empty(terms, dtype=float)
    coefficients[0] = alpha
    if terms == 1:
        return coefficients
    coefficient = (alpha - 1.0) * (alpha / 2.0)
    coefficients[1] = coefficient
    for one_based_index in range(3, terms + 1):
        coefficient *= 1.0 - (2.0 - alpha) / one_based_index
        coefficients[one_based_index - 1] = coefficient
    return coefficients


def _history(name: str, values: np.ndarray) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.ndim != 2 or result.shape[0] < 3 or result.shape[1] < 1:
        raise ValueError(f"{name} must be a finite grid-by-history matrix")
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be finite")
    return result


def operational_uniform_memory_step(
    density_history: np.ndarray,
    left_neighbour_history: np.ndarray,
    right_neighbour_history: np.ndarray,
    raw_kernel: np.ndarray,
    total_source: np.ndarray,
    *,
    delta_u: float,
    cancellation_rate: float,
    transport_probability: float,
    jump_bias: float = 0.0,
) -> OperationalStepResult:
    """Apply one fixed-grid update with one elapsed-time survival factor.

    Neighbour histories are supplied explicitly so this primitive does not
    silently choose the final Stage 4 spatial boundary condition.
    """

    density = _history("density_history", density_history)
    left = _history("left_neighbour_history", left_neighbour_history)
    right = _history("right_neighbour_history", right_neighbour_history)
    if left.shape != density.shape or right.shape != density.shape:
        raise ValueError("neighbour histories must match density_history")
    kernel = np.asarray(raw_kernel, dtype=float)
    if kernel.ndim != 1 or kernel.size < 1 or not np.all(np.isfinite(kernel)):
        raise ValueError("raw_kernel must be a nonempty finite vector")
    source = np.asarray(total_source, dtype=float)
    if source.ndim != 1 or source.size != density.shape[0] or not np.all(np.isfinite(source)):
        raise ValueError("total_source must match the spatial grid")

    step = _finite("delta_u", delta_u)
    rate = _finite("cancellation_rate", cancellation_rate)
    transport = _finite("transport_probability", transport_probability)
    bias = _finite("jump_bias", jump_bias)
    if step <= 0.0:
        raise ValueError("delta_u must be positive")
    if rate < 0.0:
        raise ValueError("cancellation_rate must be nonnegative")
    if not 0.0 <= transport <= 1.0:
        raise ValueError("transport_probability must lie in [0, 1]")
    if abs(bias) > transport:
        raise ValueError("absolute jump_bias must not exceed transport_probability")

    target_index = density.shape[1]
    first_history_index = max(0, target_index - kernel.size)
    history = np.zeros(density.shape[0], dtype=float)
    plus = 0.5 * (transport + bias)
    minus = 0.5 * (transport - bias)
    for history_index in range(first_history_index, target_index):
        lag = target_index - history_index
        elapsed = (lag - 1) * step
        transported = (
            plus * left[:, history_index]
            + minus * right[:, history_index]
            - transport * density[:, history_index]
        )
        history += kernel[lag - 1] * math.exp(-rate * elapsed) * transported

    survivor = math.exp(-rate * step) * density[:, -1]
    source_contribution = step * source
    updated = history + survivor + source_contribution
    return OperationalStepResult(
        density=updated,
        history_contribution=history,
        survivor_contribution=survivor,
        source_contribution=source_contribution,
    )


__all__ = [
    "OperationalStepResult",
    "operational_sibuya_kernel",
    "operational_uniform_memory_step",
]
