"""Target one-book source on the fixed operational-time price grid."""

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
class OperationalSource:
    """Parameters of ``q(y)=-lambda*mu*y*exp(-mu*y^2)``."""

    lambda_value: float
    mu: float
    enabled: bool = True

    def __post_init__(self) -> None:
        if _finite("lambda_value", self.lambda_value) < 0.0:
            raise ValueError("lambda_value must be nonnegative")
        if _finite("mu", self.mu) <= 0.0:
            raise ValueError("mu must be positive")


def operational_source_density(
    price_grid: np.ndarray | float,
    boundary_price: float,
    source: OperationalSource,
) -> np.ndarray | float:
    """Evaluate the corrected source without periodic coordinate wrapping."""

    values = np.asarray(price_grid, dtype=float)
    scalar = values.ndim == 0
    values = np.atleast_1d(values)
    if not np.all(np.isfinite(values)):
        raise ValueError("price_grid must contain only finite values")
    boundary = _finite("boundary_price", boundary_price)
    if not source.enabled or source.lambda_value == 0.0:
        result = np.zeros_like(values)
    else:
        displacement = values - boundary
        result = (
            -source.lambda_value
            * source.mu
            * displacement
            * np.exp(-source.mu * displacement * displacement)
        )
    return float(result[0]) if scalar else result


def positive_half_first_moment(source: OperationalSource) -> float:
    """Return ``int_0^infinity y*q(y)dy`` for the target source."""

    if not source.enabled:
        return 0.0
    return -source.lambda_value * math.sqrt(math.pi) / (4.0 * math.sqrt(source.mu))


__all__ = [
    "OperationalSource",
    "operational_source_density",
    "positive_half_first_moment",
]
