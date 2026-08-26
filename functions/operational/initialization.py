"""Simultaneous stationary initialization and declared burn-in policy."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np

from functions.operational.coupling import (
    RegularizedCoupling,
    regularized_coupling_density,
)
from functions.operational.source import OperationalSource, operational_source_density


def _finite(name: str, value: float) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


@dataclass(frozen=True)
class BurnInPolicy:
    minimum_steps: int
    relative_tolerance: float
    consecutive_checks: int

    def __post_init__(self) -> None:
        if not isinstance(self.minimum_steps, int) or self.minimum_steps < 0:
            raise ValueError("minimum_steps must be a nonnegative integer")
        tolerance = _finite("relative_tolerance", self.relative_tolerance)
        if tolerance <= 0.0:
            raise ValueError("relative_tolerance must be positive")
        if not isinstance(self.consecutive_checks, int) or self.consecutive_checks < 1:
            raise ValueError("consecutive_checks must be a positive integer")


@dataclass(frozen=True)
class OperationalInitializationResult:
    densities: np.ndarray
    initial_prices: np.ndarray
    price_inputs: np.ndarray
    source_fields: np.ndarray
    directed_coupling_fields: np.ndarray
    total_coupling_fields: np.ndarray
    net_sources: np.ndarray
    boundary_condition: str
    burn_in_policy: BurnInPolicy


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


def stationary_density(
    price_grid: np.ndarray,
    net_source: np.ndarray,
    *,
    diffusion: float,
    cancellation_rate: float,
    boundary_condition: str,
) -> np.ndarray:
    """Solve ``D*phi_xx-nu*phi+source=0`` under an explicit boundary rule."""

    grid, delta_x = _uniform_grid(price_grid)
    source = np.asarray(net_source, dtype=float)
    if source.shape != grid.shape or not np.all(np.isfinite(source)):
        raise ValueError("net_source must be a finite vector matching price_grid")
    diffusion_value = _finite("diffusion", diffusion)
    cancellation = _finite("cancellation_rate", cancellation_rate)
    if diffusion_value <= 0.0:
        raise ValueError("diffusion must be positive")
    if cancellation < 0.0:
        raise ValueError("cancellation_rate must be nonnegative")
    if boundary_condition not in ("dirichlet_zero", "neumann_zero_flux"):
        raise ValueError("boundary_condition must be explicitly supported")
    if boundary_condition == "neumann_zero_flux" and cancellation == 0.0:
        raise ValueError("neumann_zero_flux requires positive cancellation for uniqueness")

    scale = diffusion_value / delta_x**2
    points = grid.size
    matrix = np.diag(np.full(points, -2.0 * scale - cancellation, dtype=float))
    matrix += np.diag(np.full(points - 1, scale), 1)
    matrix += np.diag(np.full(points - 1, scale), -1)
    right_hand_side = -source.copy()
    if boundary_condition == "dirichlet_zero":
        matrix[0] = 0.0
        matrix[-1] = 0.0
        matrix[0, 0] = 1.0
        matrix[-1, -1] = 1.0
        right_hand_side[0] = 0.0
        right_hand_side[-1] = 0.0
    else:
        matrix[0, 1] = 2.0 * scale
        matrix[-1, -2] = 2.0 * scale
    return np.linalg.solve(matrix, right_hand_side)


def _book_vector(name: str, values: Sequence[float], books: int, *, positive: bool) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.shape != (books,) or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain one finite value per book")
    if positive and np.any(result <= 0.0):
        raise ValueError(f"{name} must be positive")
    if not positive and np.any(result < 0.0):
        raise ValueError(f"{name} must be nonnegative")
    return result


def simultaneous_stationary_initialization(
    price_grid: np.ndarray,
    initial_prices: Sequence[float],
    sources: Sequence[OperationalSource],
    couplings: Sequence[Sequence[RegularizedCoupling | None]],
    *,
    diffusion: Sequence[float],
    cancellation_rates: Sequence[float],
    boundary_condition: str,
    burn_in_policy: BurnInPolicy,
) -> OperationalInitializationResult:
    """Construct all book fields from one immutable initial-price snapshot."""

    grid, _ = _uniform_grid(price_grid)
    prices = np.asarray(initial_prices, dtype=float)
    if prices.ndim != 1 or prices.size < 1 or not np.all(np.isfinite(prices)):
        raise ValueError("initial_prices must be a nonempty finite vector")
    books = prices.size
    if len(sources) != books or len(couplings) != books:
        raise ValueError("sources and coupling rows must match the number of books")
    if any(len(row) != books for row in couplings):
        raise ValueError("couplings must be a square ordered-pair matrix")
    diffusion_values = _book_vector("diffusion", diffusion, books, positive=True)
    cancellation_values = _book_vector(
        "cancellation_rates", cancellation_rates, books, positive=False
    )

    source_fields = np.empty((books, grid.size), dtype=float)
    directed = np.zeros((books, books, grid.size), dtype=float)
    price_inputs = np.tile(prices, (books, 1))
    for receiving_book in range(books):
        source_fields[receiving_book] = np.asarray(
            operational_source_density(
                grid, prices[receiving_book], sources[receiving_book]
            ),
            dtype=float,
        )
        for other_book in range(books):
            coupling = couplings[receiving_book][other_book]
            if receiving_book == other_book:
                if coupling is not None and coupling.enabled and coupling.gamma != 0.0:
                    raise ValueError("diagonal self-coupling must be absent or zero")
                continue
            if coupling is not None:
                directed[receiving_book, other_book] = np.asarray(
                    regularized_coupling_density(
                        grid,
                        prices[receiving_book],
                        prices[other_book],
                        sources[receiving_book],
                        coupling,
                    ),
                    dtype=float,
                )

    total_coupling = np.sum(directed, axis=1)
    net_sources = source_fields + total_coupling
    densities = np.empty_like(source_fields)
    for book in range(books):
        densities[book] = stationary_density(
            grid,
            net_sources[book],
            diffusion=diffusion_values[book],
            cancellation_rate=cancellation_values[book],
            boundary_condition=boundary_condition,
        )
    return OperationalInitializationResult(
        densities=densities,
        initial_prices=prices.copy(),
        price_inputs=price_inputs,
        source_fields=source_fields,
        directed_coupling_fields=directed,
        total_coupling_fields=total_coupling,
        net_sources=net_sources,
        boundary_condition=boundary_condition,
        burn_in_policy=burn_in_policy,
    )


def relative_state_change(previous: np.ndarray, current: np.ndarray) -> float:
    """Return a scale-safe relative L2 change for a burn-in diagnostic."""

    prior = np.asarray(previous, dtype=float)
    present = np.asarray(current, dtype=float)
    if prior.shape != present.shape or prior.size == 0:
        raise ValueError("previous and current states must have the same nonempty shape")
    if not np.all(np.isfinite(prior)) or not np.all(np.isfinite(present)):
        raise ValueError("burn-in states must be finite")
    difference = float(np.linalg.norm(present - prior))
    scale = max(float(np.linalg.norm(prior)), float(np.linalg.norm(present)))
    return 0.0 if scale == 0.0 else difference / scale


def burn_in_converged(
    previous: np.ndarray,
    current: np.ndarray,
    *,
    operational_step: int,
    consecutive_converged_checks: int,
    policy: BurnInPolicy,
) -> bool:
    """Apply the declared minimum-step, tolerance and persistence conditions."""

    if not isinstance(operational_step, int) or operational_step < 0:
        raise ValueError("operational_step must be a nonnegative integer")
    if not isinstance(consecutive_converged_checks, int) or consecutive_converged_checks < 0:
        raise ValueError("consecutive_converged_checks must be nonnegative")
    return bool(
        operational_step >= policy.minimum_steps
        and consecutive_converged_checks >= policy.consecutive_checks
        and relative_state_change(previous, current) <= policy.relative_tolerance
    )


__all__ = [
    "BurnInPolicy",
    "OperationalInitializationResult",
    "burn_in_converged",
    "relative_state_change",
    "simultaneous_stationary_initialization",
    "stationary_density",
]
