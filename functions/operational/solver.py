"""One-step assembly for two books on a uniform operational-time grid."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np

from functions.operational.boundary import (
    ReactionBoundary,
    apply_spatial_boundary,
    extract_reaction_boundary,
    spatial_neighbour_histories,
)
from functions.operational.coupling import (
    RegularizedCoupling,
    regularized_coupling_density,
)
from functions.operational.memory import operational_uniform_memory_step
from functions.operational.source import OperationalSource, operational_source_density


def _finite(name: str, value: float) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


@dataclass(frozen=True)
class OperationalSolverSpec:
    """Numerical policy for one uniform operational step."""

    delta_u: float
    transport_probability: float
    cancellation_rates: tuple[float, float]
    boundary_condition: str = "dirichlet_zero"
    boundary_selection: str = "nearest_previous"
    minimum_abs_boundary_slope: float = 0.0

    def __post_init__(self) -> None:
        if _finite("delta_u", self.delta_u) <= 0.0:
            raise ValueError("delta_u must be positive")
        transport = _finite("transport_probability", self.transport_probability)
        if not 0.0 <= transport <= 1.0:
            raise ValueError("transport_probability must lie in [0, 1]")
        if len(self.cancellation_rates) != 2:
            raise ValueError("cancellation_rates must contain two values")
        if any(_finite("cancellation_rate", value) < 0.0 for value in self.cancellation_rates):
            raise ValueError("cancellation rates must be nonnegative")
        if self.boundary_condition != "dirichlet_zero":
            raise ValueError("v1.4.0 supports only dirichlet_zero outer boundaries")
        if self.boundary_selection not in ("unique", "nearest_previous"):
            raise ValueError("unsupported reaction-boundary selection")
        if _finite("minimum_abs_boundary_slope", self.minimum_abs_boundary_slope) < 0.0:
            raise ValueError("minimum_abs_boundary_slope must be nonnegative")


@dataclass(frozen=True)
class OperationalTwoBookStepResult:
    """Complete term decomposition of one simultaneous two-book step."""

    densities: np.ndarray
    raw_densities: np.ndarray
    prices: np.ndarray
    boundaries: tuple[ReactionBoundary, ReactionBoundary]
    previous_prices: np.ndarray
    price_inputs: np.ndarray
    source_fields: np.ndarray
    directed_coupling_fields: np.ndarray
    total_coupling_fields: np.ndarray
    shock_fields: np.ndarray
    net_sources: np.ndarray
    history_contributions: np.ndarray
    survivor_contributions: np.ndarray
    source_contributions: np.ndarray
    boundary_corrections: np.ndarray
    delta_u: float


def _uniform_grid(price_grid: np.ndarray) -> np.ndarray:
    grid = np.asarray(price_grid, dtype=float)
    if grid.ndim != 1 or grid.size < 3 or not np.all(np.isfinite(grid)):
        raise ValueError("price_grid must be a finite vector of at least three points")
    differences = np.diff(grid)
    if np.any(differences <= 0.0) or not np.allclose(
        differences, differences[0], rtol=1e-12, atol=1e-14
    ):
        raise ValueError("price_grid must be strictly increasing and uniform")
    return grid


def operational_two_book_step(
    price_grid: np.ndarray,
    density_histories: np.ndarray,
    previous_prices: Sequence[float],
    sources: Sequence[OperationalSource],
    couplings: Sequence[Sequence[RegularizedCoupling | None]],
    raw_kernels: Sequence[np.ndarray],
    jump_biases: Sequence[float],
    spec: OperationalSolverSpec,
    *,
    shock_fields: np.ndarray | None = None,
) -> OperationalTwoBookStepResult:
    """Advance both books once from one immutable operational state snapshot."""

    grid = _uniform_grid(price_grid)
    histories = np.asarray(density_histories, dtype=float)
    if (
        histories.ndim != 3
        or histories.shape[0] != 2
        or histories.shape[1] != grid.size
        or histories.shape[2] < 1
        or not np.all(np.isfinite(histories))
    ):
        raise ValueError("density_histories must have shape (2, grid, history)")
    prices = np.asarray(previous_prices, dtype=float)
    biases = np.asarray(jump_biases, dtype=float)
    if prices.shape != (2,) or not np.all(np.isfinite(prices)):
        raise ValueError("previous_prices must contain two finite values")
    if biases.shape != (2,) or not np.all(np.isfinite(biases)):
        raise ValueError("jump_biases must contain two finite values")
    if len(sources) != 2 or len(couplings) != 2 or any(len(row) != 2 for row in couplings):
        raise ValueError("sources and couplings must define two ordered books")
    if len(raw_kernels) != 2:
        raise ValueError("raw_kernels must contain one kernel per book")
    if shock_fields is None:
        shocks = np.zeros((2, grid.size), dtype=float)
    else:
        shocks = np.asarray(shock_fields, dtype=float)
        if shocks.shape != (2, grid.size) or not np.all(np.isfinite(shocks)):
            raise ValueError("shock_fields must have shape (2, grid)")
        shocks = np.array(shocks, copy=True)

    price_snapshot = np.array(prices, copy=True)
    price_inputs = np.tile(price_snapshot, (2, 1))
    source_fields = np.empty((2, grid.size), dtype=float)
    directed = np.zeros((2, 2, grid.size), dtype=float)
    for receiving_book in range(2):
        source_fields[receiving_book] = np.asarray(
            operational_source_density(
                grid, price_snapshot[receiving_book], sources[receiving_book]
            ),
            dtype=float,
        )
        for other_book in range(2):
            coupling = couplings[receiving_book][other_book]
            if receiving_book == other_book:
                if coupling is not None and coupling.enabled and coupling.gamma != 0.0:
                    raise ValueError("diagonal self-coupling must be absent or zero")
                continue
            if coupling is not None:
                directed[receiving_book, other_book] = np.asarray(
                    regularized_coupling_density(
                        grid,
                        price_snapshot[receiving_book],
                        price_snapshot[other_book],
                        sources[receiving_book],
                        coupling,
                    ),
                    dtype=float,
                )
    total_coupling = np.sum(directed, axis=1)
    net_sources = source_fields + total_coupling + shocks

    raw_densities = np.empty((2, grid.size), dtype=float)
    densities = np.empty_like(raw_densities)
    history_parts = np.empty_like(raw_densities)
    survivor_parts = np.empty_like(raw_densities)
    source_parts = np.empty_like(raw_densities)
    corrections = np.empty_like(raw_densities)
    boundaries: list[ReactionBoundary] = []
    next_prices = np.empty(2, dtype=float)
    for book in range(2):
        left, right = spatial_neighbour_histories(
            histories[book], boundary_condition=spec.boundary_condition
        )
        step = operational_uniform_memory_step(
            histories[book],
            left,
            right,
            np.asarray(raw_kernels[book], dtype=float),
            net_sources[book],
            delta_u=spec.delta_u,
            cancellation_rate=spec.cancellation_rates[book],
            transport_probability=spec.transport_probability,
            jump_bias=float(biases[book]),
        )
        raw_densities[book] = step.density
        densities[book] = apply_spatial_boundary(
            step.density, boundary_condition=spec.boundary_condition
        )
        history_parts[book] = step.history_contribution
        survivor_parts[book] = step.survivor_contribution
        source_parts[book] = step.source_contribution
        corrections[book] = densities[book] - raw_densities[book]
        boundary = extract_reaction_boundary(
            grid,
            densities[book],
            selection=spec.boundary_selection,
            previous_price=float(price_snapshot[book])
            if spec.boundary_selection == "nearest_previous"
            else None,
            minimum_abs_slope=spec.minimum_abs_boundary_slope,
        )
        boundaries.append(boundary)
        next_prices[book] = boundary.price

    return OperationalTwoBookStepResult(
        densities=densities,
        raw_densities=raw_densities,
        prices=next_prices,
        boundaries=(boundaries[0], boundaries[1]),
        previous_prices=price_snapshot,
        price_inputs=price_inputs,
        source_fields=source_fields,
        directed_coupling_fields=directed,
        total_coupling_fields=total_coupling,
        shock_fields=shocks,
        net_sources=net_sources,
        history_contributions=history_parts,
        survivor_contributions=survivor_parts,
        source_contributions=source_parts,
        boundary_corrections=corrections,
        delta_u=spec.delta_u,
    )


__all__ = [
    "OperationalSolverSpec",
    "OperationalTwoBookStepResult",
    "operational_two_book_step",
]
