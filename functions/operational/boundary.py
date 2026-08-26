"""Outer-grid policy and reaction-boundary extraction in operational time."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


class ReactionBoundaryError(RuntimeError):
    """Raised when no unambiguous admissible reaction boundary is available."""


def _finite(name: str, value: float) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _uniform_grid(price_grid: np.ndarray) -> tuple[np.ndarray, float]:
    grid = np.asarray(price_grid, dtype=float)
    if grid.ndim != 1 or grid.size < 3 or not np.all(np.isfinite(grid)):
        raise ValueError("price_grid must be a finite vector of at least three points")
    differences = np.diff(grid)
    if np.any(differences <= 0.0) or not np.allclose(
        differences, differences[0], rtol=1e-12, atol=1e-14
    ):
        raise ValueError("price_grid must be strictly increasing and uniform")
    return grid, float(differences[0])


@dataclass(frozen=True)
class ReactionBoundary:
    """Selected simple zero and the complete candidate count."""

    price: float
    left_index: int
    right_index: int
    slope: float
    exact_grid_zero: bool
    candidate_count: int
    distance_to_domain_edge: float
    selection: str


def spatial_neighbour_histories(
    density_history: np.ndarray,
    *,
    boundary_condition: str = "dirichlet_zero",
) -> tuple[np.ndarray, np.ndarray]:
    """Return fixed-grid left/right histories under an explicit outer policy."""

    density = np.asarray(density_history, dtype=float)
    if density.ndim != 2 or density.shape[0] < 3 or density.shape[1] < 1:
        raise ValueError("density_history must be a grid-by-history matrix")
    if not np.all(np.isfinite(density)):
        raise ValueError("density_history must be finite")
    if boundary_condition != "dirichlet_zero":
        raise ValueError("v1.4.0 supports only the declared dirichlet_zero policy")
    if not np.allclose(density[[0, -1], :], 0.0, rtol=0.0, atol=1e-14):
        raise ValueError("dirichlet_zero histories must vanish at both domain edges")
    left = np.zeros_like(density)
    right = np.zeros_like(density)
    left[1:, :] = density[:-1, :]
    right[:-1, :] = density[1:, :]
    return left, right


def apply_spatial_boundary(
    field: np.ndarray,
    *,
    boundary_condition: str = "dirichlet_zero",
) -> np.ndarray:
    """Return a copy with the declared outer boundary imposed."""

    values = np.asarray(field, dtype=float)
    if values.ndim < 1 or values.shape[0] < 3 or not np.all(np.isfinite(values)):
        raise ValueError("field must be finite with at least three spatial entries")
    if boundary_condition != "dirichlet_zero":
        raise ValueError("v1.4.0 supports only the declared dirichlet_zero policy")
    result = np.array(values, copy=True)
    result[0, ...] = 0.0
    result[-1, ...] = 0.0
    return result


def reaction_boundary_candidates(
    price_grid: np.ndarray,
    density: np.ndarray,
    *,
    minimum_abs_slope: float = 0.0,
) -> tuple[ReactionBoundary, ...]:
    """Return every simple interior zero or adjacent strict sign crossing."""

    grid, delta_x = _uniform_grid(price_grid)
    values = np.asarray(density, dtype=float)
    if values.shape != grid.shape or not np.all(np.isfinite(values)):
        raise ValueError("density must be a finite vector matching price_grid")
    threshold = _finite("minimum_abs_slope", minimum_abs_slope)
    if threshold < 0.0:
        raise ValueError("minimum_abs_slope must be nonnegative")

    raw: list[tuple[float, int, int, float, bool]] = []
    for index in range(1, grid.size - 1):
        if values[index] == 0.0 and values[index - 1] * values[index + 1] < 0.0:
            slope = (values[index + 1] - values[index - 1]) / (2.0 * delta_x)
            if abs(slope) >= threshold:
                raw.append((float(grid[index]), index, index, float(slope), True))
    for left_index in range(grid.size - 1):
        left_value = values[left_index]
        right_value = values[left_index + 1]
        if left_value * right_value < 0.0:
            slope = (right_value - left_value) / delta_x
            if abs(slope) >= threshold:
                price = grid[left_index] - left_value / slope
                raw.append(
                    (
                        float(price),
                        left_index,
                        left_index + 1,
                        float(slope),
                        False,
                    )
                )
    count = len(raw)
    return tuple(
        ReactionBoundary(
            price=price,
            left_index=left_index,
            right_index=right_index,
            slope=slope,
            exact_grid_zero=exact,
            candidate_count=count,
            distance_to_domain_edge=float(
                min(price - grid[0], grid[-1] - price)
            ),
            selection="candidate",
        )
        for price, left_index, right_index, slope, exact in raw
    )


def extract_reaction_boundary(
    price_grid: np.ndarray,
    density: np.ndarray,
    *,
    selection: str = "unique",
    previous_price: float | None = None,
    minimum_abs_slope: float = 0.0,
) -> ReactionBoundary:
    """Select a reaction boundary without a local one-based search seed."""

    candidates = reaction_boundary_candidates(
        price_grid, density, minimum_abs_slope=minimum_abs_slope
    )
    if not candidates:
        raise ReactionBoundaryError("no admissible simple reaction boundary was found")
    if selection == "unique":
        if len(candidates) != 1:
            raise ReactionBoundaryError(
                f"unique selection requires one candidate; found {len(candidates)}"
            )
        selected = candidates[0]
    elif selection == "nearest_previous":
        if previous_price is None:
            raise ValueError("nearest_previous selection requires previous_price")
        previous = _finite("previous_price", previous_price)
        distances = np.asarray([abs(item.price - previous) for item in candidates])
        minimum = float(np.min(distances))
        candidate_prices = np.asarray([item.price for item in candidates])
        tolerance = 1e-12 * max(
            1.0, abs(previous), float(np.ptp(candidate_prices))
        )
        matches = np.flatnonzero(np.abs(distances - minimum) <= tolerance)
        if matches.size != 1:
            raise ReactionBoundaryError("nearest_previous selection has a distance tie")
        selected = candidates[int(matches[0])]
    else:
        raise ValueError("selection must be 'unique' or 'nearest_previous'")
    return ReactionBoundary(
        price=selected.price,
        left_index=selected.left_index,
        right_index=selected.right_index,
        slope=selected.slope,
        exact_grid_zero=selected.exact_grid_zero,
        candidate_count=selected.candidate_count,
        distance_to_domain_edge=selected.distance_to_domain_edge,
        selection=selection,
    )


__all__ = [
    "ReactionBoundary",
    "ReactionBoundaryError",
    "apply_spatial_boundary",
    "extract_reaction_boundary",
    "reaction_boundary_candidates",
    "spatial_neighbour_histories",
]
