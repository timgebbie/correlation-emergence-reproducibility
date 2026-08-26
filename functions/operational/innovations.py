"""Explicit two-book innovations for the uniform operational-time model."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np


def _finite(name: str, value: float) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


@dataclass(frozen=True)
class TwoBookInnovationPolicy:
    """Operational innovation scales and instantaneous correlation.

    ``sigma_1`` and ``sigma_2`` multiply standard inputs exactly once.
    ``correlation`` controls the microscopic operational forcing. It is not a
    calendar-clock correlation, and the nonlinear boundary-price correlation
    must be measured rather than identified with it automatically.
    """

    sigma_1: float
    sigma_2: float
    correlation: float = 0.0

    def __post_init__(self) -> None:
        if _finite("sigma_1", self.sigma_1) < 0.0:
            raise ValueError("sigma_1 must be nonnegative")
        if _finite("sigma_2", self.sigma_2) < 0.0:
            raise ValueError("sigma_2 must be nonnegative")
        rho = _finite("correlation", self.correlation)
        if not -1.0 <= rho <= 1.0:
            raise ValueError("correlation must lie in [-1, 1]")

    @property
    def sigmas(self) -> np.ndarray:
        """Return the two declared innovation scales."""

        return np.asarray([self.sigma_1, self.sigma_2], dtype=float)


@dataclass(frozen=True)
class OperationalInnovationResult:
    """Term-level result of the two-book innovation construction."""

    base_standard_normals: np.ndarray
    correlated_standard_normals: np.ndarray
    velocities: np.ndarray
    jump_biases: np.ndarray
    stay_weights: np.ndarray
    plus_weights: np.ndarray
    minus_weights: np.ndarray


def correlate_two_book_normals(
    base_standard_normals: np.ndarray,
    correlation: float,
) -> np.ndarray:
    """Apply the two-dimensional Gaussian correlation transform.

    The last array axis indexes the two books. Inputs are supplied externally;
    this module neither owns a random generator nor a seed.
    """

    base = np.asarray(base_standard_normals, dtype=float)
    if base.ndim < 1 or base.shape[-1] != 2 or not np.all(np.isfinite(base)):
        raise ValueError("base_standard_normals must be finite with final dimension two")
    rho = _finite("correlation", correlation)
    if not -1.0 <= rho <= 1.0:
        raise ValueError("correlation must lie in [-1, 1]")
    result = np.empty_like(base)
    result[..., 0] = base[..., 0]
    orthogonal_scale = math.sqrt(max(0.0, 1.0 - rho * rho))
    result[..., 1] = rho * base[..., 0] + orthogonal_scale * base[..., 1]
    return result


def velocity_to_jump_bias(
    velocities: np.ndarray | float,
    *,
    transport_probability: float,
    delta_x: float,
    diffusion: np.ndarray | Sequence[float] | float,
) -> np.ndarray | float:
    """Map velocity to the bounded DTRW bias ``F=r*tanh(V*dx/(4D))``."""

    values = np.asarray(velocities, dtype=float)
    scalar = values.ndim == 0
    if not np.all(np.isfinite(values)):
        raise ValueError("velocities must be finite")
    transport = _finite("transport_probability", transport_probability)
    spacing = _finite("delta_x", delta_x)
    diffusion_values = np.asarray(diffusion, dtype=float)
    if not np.all(np.isfinite(diffusion_values)):
        raise ValueError("diffusion must be finite")
    if not 0.0 <= transport <= 1.0:
        raise ValueError("transport_probability must lie in [0, 1]")
    if spacing <= 0.0:
        raise ValueError("delta_x must be positive")
    if np.any(diffusion_values <= 0.0):
        raise ValueError("diffusion must be positive")
    try:
        result = transport * np.tanh(values * spacing / (4.0 * diffusion_values))
    except ValueError as error:
        raise ValueError("diffusion must broadcast against velocities") from error
    return float(result) if scalar else np.asarray(result, dtype=float)


def transport_weights_from_bias(
    jump_biases: np.ndarray | float,
    transport_probability: float,
) -> tuple[np.ndarray | float, np.ndarray | float, np.ndarray | float]:
    """Return stay, plus and minus weights from a bounded signed bias."""

    biases = np.asarray(jump_biases, dtype=float)
    scalar = biases.ndim == 0
    if not np.all(np.isfinite(biases)):
        raise ValueError("jump_biases must be finite")
    transport = _finite("transport_probability", transport_probability)
    if not 0.0 <= transport <= 1.0:
        raise ValueError("transport_probability must lie in [0, 1]")
    if np.any(np.abs(biases) > transport + 1e-15):
        raise ValueError("absolute jump bias must not exceed transport_probability")
    stay = np.full_like(biases, 1.0 - transport)
    plus = 0.5 * (transport + biases)
    minus = 0.5 * (transport - biases)
    if scalar:
        return float(stay), float(plus), float(minus)
    return stay, plus, minus


def two_book_operational_innovations(
    base_standard_normals: np.ndarray,
    policy: TwoBookInnovationPolicy,
    *,
    transport_probability: float,
    delta_x: float,
    diffusion: Sequence[float],
) -> OperationalInnovationResult:
    """Construct correlated, once-scaled operational forcing and DTRW weights."""

    base = np.asarray(base_standard_normals, dtype=float)
    correlated = correlate_two_book_normals(base, policy.correlation)
    diffusion_values = np.asarray(diffusion, dtype=float)
    if diffusion_values.shape != (2,):
        raise ValueError("diffusion must contain one value per book")
    velocities = correlated * policy.sigmas
    biases = np.asarray(
        velocity_to_jump_bias(
            velocities,
            transport_probability=transport_probability,
            delta_x=delta_x,
            diffusion=diffusion_values,
        ),
        dtype=float,
    )
    stay, plus, minus = transport_weights_from_bias(
        biases, transport_probability
    )
    return OperationalInnovationResult(
        base_standard_normals=base.copy(),
        correlated_standard_normals=correlated,
        velocities=velocities,
        jump_biases=biases,
        stay_weights=np.asarray(stay, dtype=float),
        plus_weights=np.asarray(plus, dtype=float),
        minus_weights=np.asarray(minus, dtype=float),
    )


__all__ = [
    "OperationalInnovationResult",
    "TwoBookInnovationPolicy",
    "correlate_two_book_normals",
    "transport_weights_from_bias",
    "two_book_operational_innovations",
    "velocity_to_jump_bias",
]
