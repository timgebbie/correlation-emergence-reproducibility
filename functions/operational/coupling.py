"""Regularised thick-boundary coupling for the operational-time model."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from functions.operational.source import OperationalSource, operational_source_density


def _finite(name: str, value: float) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


@dataclass(frozen=True)
class RegularizedCoupling:
    """Ordered-pair coupling parameters ``gamma`` and ``epsilon``."""

    gamma: float
    epsilon: float
    enabled: bool = True

    def __post_init__(self) -> None:
        if _finite("gamma", self.gamma) < 0.0:
            raise ValueError("gamma must be nonnegative")
        if _finite("epsilon", self.epsilon) <= 0.0:
            raise ValueError("epsilon must be positive")

    @classmethod
    def from_reference_scale(
        cls,
        gamma: float,
        reference_spread: float,
        reference_width: float,
        *,
        enabled: bool = True,
    ) -> "RegularizedCoupling":
        """Construct ``epsilon=abs(z_ref)*w_ref`` from the paper's scales."""

        epsilon = regularization_epsilon(reference_spread, reference_width)
        return cls(gamma=gamma, epsilon=epsilon, enabled=enabled)


def regularization_epsilon(reference_spread: float, reference_width: float) -> float:
    """Return the Angstmann--Gebbie reference-scale regularisation."""

    spread = abs(_finite("reference_spread", reference_spread))
    width = _finite("reference_width", reference_width)
    if spread <= 0.0:
        raise ValueError("reference_spread must be nonzero")
    if width <= 0.0:
        raise ValueError("reference_width must be positive")
    return spread * width


def regularized_transition_width(
    directed_spread: np.ndarray | float,
    epsilon: float,
) -> np.ndarray | float:
    """Return ``epsilon/abs(z)``; the zero-spread limiting width is infinite."""

    spreads = np.asarray(directed_spread, dtype=float)
    scalar = spreads.ndim == 0
    if not np.all(np.isfinite(spreads)):
        raise ValueError("directed_spread must be finite")
    eps = _finite("epsilon", epsilon)
    if eps <= 0.0:
        raise ValueError("epsilon must be positive")
    magnitudes = np.abs(spreads)
    result = np.full_like(magnitudes, np.inf, dtype=float)
    np.divide(eps, magnitudes, out=result, where=magnitudes > 0.0)
    return float(result) if scalar else result


def regularized_selector(
    displacement: np.ndarray | float,
    directed_spread: float,
    epsilon: float,
) -> np.ndarray | float:
    """Return ``0.5*(1+tanh(y*z/epsilon))``, including ``z=0``."""

    values = np.asarray(displacement, dtype=float)
    scalar = values.ndim == 0
    values = np.atleast_1d(values)
    if not np.all(np.isfinite(values)):
        raise ValueError("displacement must contain only finite values")
    spread = _finite("directed_spread", directed_spread)
    eps = _finite("epsilon", epsilon)
    if eps <= 0.0:
        raise ValueError("epsilon must be positive")
    result = 0.5 * (1.0 + np.tanh(values * spread / eps))
    return float(result[0]) if scalar else result


def regularized_coupling_density(
    price_grid: np.ndarray | float,
    own_boundary: float,
    other_boundary: float,
    source: OperationalSource,
    coupling: RegularizedCoupling,
) -> np.ndarray | float:
    """Evaluate ``gamma*z*q(y)*W(y,z;epsilon)`` for one ordered pair."""

    values = np.asarray(price_grid, dtype=float)
    scalar = values.ndim == 0
    values = np.atleast_1d(values)
    if not np.all(np.isfinite(values)):
        raise ValueError("price_grid must contain only finite values")
    own = _finite("own_boundary", own_boundary)
    other = _finite("other_boundary", other_boundary)
    if not coupling.enabled or coupling.gamma == 0.0 or not source.enabled:
        result = np.zeros_like(values)
    else:
        spread = own - other
        displacement = values - own
        source_values = np.asarray(
            operational_source_density(values, own, source), dtype=float
        )
        selector = np.asarray(
            regularized_selector(displacement, spread, coupling.epsilon),
            dtype=float,
        )
        result = coupling.gamma * spread * source_values * selector
    return float(result[0]) if scalar else result


def lattice_first_moment(
    price_grid: np.ndarray,
    boundary_price: float,
    field: np.ndarray,
) -> float:
    """Return the fixed-grid rectangle-rule raw first moment."""

    grid = np.asarray(price_grid, dtype=float)
    values = np.asarray(field, dtype=float)
    if grid.ndim != 1 or grid.size < 3 or values.shape != grid.shape:
        raise ValueError("price_grid and field must be same-length vectors")
    if not np.all(np.isfinite(grid)) or not np.all(np.isfinite(values)):
        raise ValueError("price_grid and field must be finite")
    differences = np.diff(grid)
    if np.any(differences <= 0.0) or not np.allclose(
        differences, differences[0], rtol=1e-12, atol=1e-14
    ):
        raise ValueError("price_grid must be strictly increasing and uniform")
    boundary = _finite("boundary_price", boundary_price)
    return float(differences[0] * np.sum((grid - boundary) * values))


__all__ = [
    "RegularizedCoupling",
    "lattice_first_moment",
    "regularization_epsilon",
    "regularized_coupling_density",
    "regularized_selector",
    "regularized_transition_width",
]
