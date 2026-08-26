"""Front geometry and appendix-scale diagnostics for operational paths."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from functions.operational.coupling import (
    regularization_epsilon,
    regularized_transition_width,
)


def _finite(name: str, value: float) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _uniform_grid(price_grid: np.ndarray) -> tuple[np.ndarray, float]:
    grid = np.asarray(price_grid, dtype=float)
    if grid.ndim != 1 or grid.size < 5 or not np.all(np.isfinite(grid)):
        raise ValueError("price_grid must be a finite vector of at least five points")
    differences = np.diff(grid)
    if np.any(differences <= 0.0) or not np.allclose(
        differences, differences[0], rtol=1e-12, atol=1e-14
    ):
        raise ValueError("price_grid must be strictly increasing and uniform")
    return grid, float(differences[0])


@dataclass(frozen=True)
class ReactionFrontGeometry:
    """Local polynomial geometry around a declared simple zero crossing."""

    boundary_price: float
    slope: float
    curvature: float
    curvature_length: float
    stencil_points: int
    polynomial_degree: int
    distance_to_domain_edge: float


@dataclass(frozen=True)
class AppendixThicknessScales:
    """Dimensionless ratios used in the Angstmann--Gebbie appendices."""

    delta_x: float
    source_width: float
    reference_spread: float
    reference_width: float
    epsilon: float
    directed_spread: float
    selector_width: float
    curvature_length: float
    coupling_active: bool
    grid_to_reference_ratio: float
    reference_to_source_ratio: float
    source_to_curvature_ratio: float
    selector_to_curvature_ratio: float


def local_reaction_front_geometry(
    price_grid: np.ndarray,
    density: np.ndarray,
    boundary_price: float,
    *,
    stencil_points: int = 7,
    polynomial_degree: int = 3,
) -> ReactionFrontGeometry:
    """Estimate slope and curvature in coordinates centred on the boundary."""

    grid, _ = _uniform_grid(price_grid)
    values = np.asarray(density, dtype=float)
    if values.shape != grid.shape or not np.all(np.isfinite(values)):
        raise ValueError("density must be a finite vector matching price_grid")
    boundary = _finite("boundary_price", boundary_price)
    if not isinstance(stencil_points, int) or stencil_points < 5:
        raise ValueError("stencil_points must be an integer of at least five")
    if stencil_points % 2 == 0 or stencil_points > grid.size:
        raise ValueError("stencil_points must be odd and no larger than the grid")
    if not isinstance(polynomial_degree, int) or not 2 <= polynomial_degree < stencil_points:
        raise ValueError("polynomial_degree must lie between two and stencil_points-1")

    insertion = int(np.searchsorted(grid, boundary, side="left"))
    start = insertion - stencil_points // 2
    stop = start + stencil_points
    if start < 0 or stop > grid.size:
        raise ValueError("reaction boundary is too close to the domain edge for the stencil")
    local_grid = grid[start:stop] - boundary
    coefficients = np.polynomial.polynomial.polyfit(
        local_grid, values[start:stop], polynomial_degree
    )
    slope = float(coefficients[1])
    curvature = float(2.0 * coefficients[2])
    if slope == 0.0:
        raise ValueError("reaction boundary must have nonzero fitted slope")
    curvature_length = (
        math.inf if curvature == 0.0 else 2.0 * abs(slope) / abs(curvature)
    )
    return ReactionFrontGeometry(
        boundary_price=boundary,
        slope=slope,
        curvature=curvature,
        curvature_length=curvature_length,
        stencil_points=stencil_points,
        polynomial_degree=polynomial_degree,
        distance_to_domain_edge=min(boundary - grid[0], grid[-1] - boundary),
    )


def appendix_thickness_scales(
    *,
    delta_x: float,
    source_mu: float,
    reference_spread: float,
    reference_width: float,
    directed_spread: float,
    curvature_length: float,
) -> AppendixThicknessScales:
    """Evaluate, but do not hide behind thresholds, the appendix scale ratios."""

    spacing = _finite("delta_x", delta_x)
    mu = _finite("source_mu", source_mu)
    spread_reference = abs(_finite("reference_spread", reference_spread))
    width_reference = _finite("reference_width", reference_width)
    spread = _finite("directed_spread", directed_spread)
    curvature_scale = float(curvature_length)
    if spacing <= 0.0:
        raise ValueError("delta_x must be positive")
    if mu <= 0.0:
        raise ValueError("source_mu must be positive")
    if spread_reference <= 0.0:
        raise ValueError("reference_spread must be nonzero")
    if width_reference <= 0.0:
        raise ValueError("reference_width must be positive")
    if not (curvature_scale > 0.0 and math.isfinite(curvature_scale)):
        if not math.isinf(curvature_scale) or curvature_scale < 0.0:
            raise ValueError("curvature_length must be positive or infinite")

    source_width = 1.0 / math.sqrt(mu)
    epsilon = regularization_epsilon(spread_reference, width_reference)
    selector_width = float(regularized_transition_width(spread, epsilon))
    active = spread != 0.0
    source_curvature_ratio = (
        0.0 if math.isinf(curvature_scale) else source_width / curvature_scale
    )
    selector_curvature_ratio = (
        math.nan
        if not active
        else 0.0
        if math.isinf(curvature_scale)
        else selector_width / curvature_scale
    )
    return AppendixThicknessScales(
        delta_x=spacing,
        source_width=source_width,
        reference_spread=spread_reference,
        reference_width=width_reference,
        epsilon=epsilon,
        directed_spread=spread,
        selector_width=selector_width,
        curvature_length=curvature_scale,
        coupling_active=active,
        grid_to_reference_ratio=spacing / width_reference,
        reference_to_source_ratio=width_reference / source_width,
        source_to_curvature_ratio=source_curvature_ratio,
        selector_to_curvature_ratio=selector_curvature_ratio,
    )


def front_displacement_ratio(
    displacement: np.ndarray | float,
    *,
    slope: float,
    curvature: float,
) -> np.ndarray | float:
    """Return ``abs(C)*abs(xi)/(2*abs(L))`` from the appendix expansion."""

    values = np.asarray(displacement, dtype=float)
    scalar = values.ndim == 0
    if not np.all(np.isfinite(values)):
        raise ValueError("displacement must be finite")
    slope_value = _finite("slope", slope)
    curvature_value = _finite("curvature", curvature)
    if slope_value == 0.0:
        raise ValueError("slope must be nonzero")
    result = abs(curvature_value) * np.abs(values) / (2.0 * abs(slope_value))
    return float(result) if scalar else result


def relative_l2_error(candidate: np.ndarray, reference: np.ndarray) -> float:
    """Return a scale-safe relative L2 error for equal-shaped states."""

    values = np.asarray(candidate, dtype=float)
    target = np.asarray(reference, dtype=float)
    if values.shape != target.shape or values.size == 0:
        raise ValueError("candidate and reference must have the same nonempty shape")
    if not np.all(np.isfinite(values)) or not np.all(np.isfinite(target)):
        raise ValueError("candidate and reference must be finite")
    denominator = float(np.linalg.norm(target))
    numerator = float(np.linalg.norm(values - target))
    return numerator if denominator == 0.0 else numerator / denominator


def errors_strictly_decrease(errors: np.ndarray) -> bool:
    """Return whether a finite positive convergence sequence strictly decreases."""

    values = np.asarray(errors, dtype=float)
    if values.ndim != 1 or values.size < 2 or not np.all(np.isfinite(values)):
        raise ValueError("errors must be a finite vector with at least two entries")
    if np.any(values <= 0.0):
        raise ValueError("errors must be positive")
    return bool(np.all(np.diff(values) < 0.0))


__all__ = [
    "AppendixThicknessScales",
    "ReactionFrontGeometry",
    "appendix_thickness_scales",
    "errors_strictly_decrease",
    "front_displacement_ratio",
    "local_reaction_front_geometry",
    "relative_l2_error",
]
