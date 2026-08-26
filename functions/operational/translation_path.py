"""Rolling operational paths for projection-consistent two-book coupling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from functions.operational.boundary import ReactionBoundaryError, extract_reaction_boundary
from functions.operational.initialization import relative_state_change
from functions.operational.innovations import (
    TwoBookInnovationPolicy,
    two_book_operational_innovations,
)
from functions.operational.solver import OperationalSolverSpec
from functions.operational.source import OperationalSource
from functions.operational.translation_coupling import TranslationModeCoupling
from functions.operational.translation_solver import operational_translation_two_book_step


class TranslationModePathError(RuntimeError):
    """Raised when a projection-consistent path cannot be completed."""


@dataclass(frozen=True)
class TranslationModeTwoBookPathResult:
    """Boundary observables and bounded rolling state on operational time."""

    operational_times: np.ndarray
    prices: np.ndarray
    boundary_slopes: np.ndarray
    boundary_candidate_counts: np.ndarray
    boundary_edge_distances: np.ndarray
    base_standard_normals: np.ndarray
    correlated_standard_normals: np.ndarray
    velocities: np.ndarray
    jump_biases: np.ndarray
    directed_spreads: np.ndarray
    directed_coupling_l1_norms: np.ndarray
    pair_centres: np.ndarray
    relative_state_changes: np.ndarray
    final_density_histories: np.ndarray
    history_capacity: int
    completed_steps: int
    delta_u: float


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


def operational_translation_two_book_path(
    price_grid: np.ndarray,
    initial_densities: np.ndarray,
    initial_prices: Sequence[float],
    sources: Sequence[OperationalSource],
    couplings: Sequence[Sequence[TranslationModeCoupling | None]],
    raw_kernels: Sequence[np.ndarray],
    base_standard_normals: np.ndarray,
    innovation_policy: TwoBookInnovationPolicy,
    diffusion: Sequence[float],
    solver_spec: OperationalSolverSpec,
    *,
    shock_fields: np.ndarray | None = None,
) -> TranslationModeTwoBookPathResult:
    """Advance a corrected two-book path without clocks or interpolation."""

    grid, delta_x = _uniform_grid(price_grid)
    initial = np.asarray(initial_densities, dtype=float)
    if initial.shape != (2, grid.size) or not np.all(np.isfinite(initial)):
        raise ValueError("initial_densities must have shape (2, grid)")
    if not np.allclose(initial[:, [0, -1]], 0.0, rtol=0.0, atol=1e-14):
        raise ValueError("initial densities must satisfy dirichlet_zero boundaries")
    declared_prices = np.asarray(initial_prices, dtype=float)
    if declared_prices.shape != (2,) or not np.all(np.isfinite(declared_prices)):
        raise ValueError("initial_prices must contain two finite values")
    diffusion_values = np.asarray(diffusion, dtype=float)
    if diffusion_values.shape != (2,) or np.any(diffusion_values <= 0.0):
        raise ValueError("diffusion must contain two positive values")
    if len(sources) != 2 or len(couplings) != 2 or any(
        len(row) != 2 for row in couplings
    ):
        raise ValueError("sources and couplings must define two ordered books")
    if len(raw_kernels) != 2:
        raise ValueError("raw_kernels must contain one kernel per book")
    kernels = tuple(np.asarray(kernel, dtype=float) for kernel in raw_kernels)
    if any(
        kernel.ndim != 1 or kernel.size < 1 or not np.all(np.isfinite(kernel))
        for kernel in kernels
    ):
        raise ValueError("raw kernels must be nonempty finite vectors")
    history_capacity = max(kernel.size for kernel in kernels)

    base = np.asarray(base_standard_normals, dtype=float)
    if base.ndim != 2 or base.shape[1] != 2 or base.shape[0] < 1:
        raise ValueError("base_standard_normals must have shape (steps, 2)")
    if not np.all(np.isfinite(base)):
        raise ValueError("base_standard_normals must be finite")
    steps = base.shape[0]
    if shock_fields is None:
        shocks = np.zeros((steps, 2, grid.size), dtype=float)
    else:
        shocks = np.asarray(shock_fields, dtype=float)
        if shocks.shape != (steps, 2, grid.size) or not np.all(np.isfinite(shocks)):
            raise ValueError("shock_fields must have shape (steps, 2, grid)")
        shocks = np.array(shocks, copy=True)

    innovation = two_book_operational_innovations(
        base,
        innovation_policy,
        transport_probability=solver_spec.transport_probability,
        delta_x=delta_x,
        diffusion=diffusion_values,
    )

    prices = np.empty((steps + 1, 2), dtype=float)
    slopes = np.empty_like(prices)
    candidate_counts = np.empty((steps + 1, 2), dtype=int)
    edge_distances = np.empty_like(prices)
    prices[0] = declared_prices
    for book in range(2):
        try:
            boundary = extract_reaction_boundary(
                grid,
                initial[book],
                selection=solver_spec.boundary_selection,
                previous_price=float(declared_prices[book])
                if solver_spec.boundary_selection == "nearest_previous"
                else None,
                minimum_abs_slope=solver_spec.minimum_abs_boundary_slope,
            )
        except ReactionBoundaryError as error:
            raise TranslationModePathError(
                f"initial density for book {book + 1} has no admissible boundary"
            ) from error
        tolerance = 1e-10 * max(1.0, abs(boundary.price), delta_x)
        if abs(boundary.price - declared_prices[book]) > tolerance:
            raise ValueError("initial price does not match its density zero crossing")
        slopes[0, book] = boundary.slope
        candidate_counts[0, book] = boundary.candidate_count
        edge_distances[0, book] = boundary.distance_to_domain_edge

    spreads = np.full((steps, 2, 2), np.nan, dtype=float)
    coupling_norms = np.zeros((steps, 2, 2), dtype=float)
    relative_changes = np.empty(steps, dtype=float)
    histories = initial[:, :, None].copy()
    for zero_based_step in range(steps):
        price_snapshot = prices[zero_based_step].copy()
        for receiving_book in range(2):
            for other_book in range(2):
                if receiving_book == other_book:
                    continue
                coupling = couplings[receiving_book][other_book]
                if coupling is None or not coupling.enabled:
                    continue
                spreads[zero_based_step, receiving_book, other_book] = (
                    price_snapshot[receiving_book] - price_snapshot[other_book]
                )
        try:
            result = operational_translation_two_book_step(
                grid,
                histories,
                price_snapshot,
                sources,
                couplings,
                kernels,
                innovation.jump_biases[zero_based_step],
                solver_spec,
                shock_fields=shocks[zero_based_step],
            )
        except ReactionBoundaryError as error:
            raise TranslationModePathError(
                "reaction-boundary extraction failed at operational step "
                f"{zero_based_step + 1}"
            ) from error

        prices[zero_based_step + 1] = result.prices
        coupling_norms[zero_based_step] = delta_x * np.sum(
            np.abs(result.directed_coupling_fields), axis=2
        )
        for book, boundary in enumerate(result.boundaries):
            slopes[zero_based_step + 1, book] = boundary.slope
            candidate_counts[zero_based_step + 1, book] = boundary.candidate_count
            edge_distances[zero_based_step + 1, book] = boundary.distance_to_domain_edge
        relative_changes[zero_based_step] = relative_state_change(
            histories[:, :, -1], result.densities
        )
        histories = np.concatenate((histories, result.densities[:, :, None]), axis=2)
        if histories.shape[2] > history_capacity:
            histories = histories[:, :, -history_capacity:]

    return TranslationModeTwoBookPathResult(
        operational_times=np.arange(steps + 1, dtype=float) * solver_spec.delta_u,
        prices=prices,
        boundary_slopes=slopes,
        boundary_candidate_counts=candidate_counts,
        boundary_edge_distances=edge_distances,
        base_standard_normals=innovation.base_standard_normals.copy(),
        correlated_standard_normals=innovation.correlated_standard_normals.copy(),
        velocities=innovation.velocities.copy(),
        jump_biases=innovation.jump_biases.copy(),
        directed_spreads=spreads,
        directed_coupling_l1_norms=coupling_norms,
        pair_centres=np.mean(prices, axis=1),
        relative_state_changes=relative_changes,
        final_density_histories=histories.copy(),
        history_capacity=history_capacity,
        completed_steps=steps,
        delta_u=solver_spec.delta_u,
    )


__all__ = [
    "TranslationModePathError",
    "TranslationModeTwoBookPathResult",
    "operational_translation_two_book_path",
]
