"""Rolling two-book paths on the fixed operational-time lattice."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from functions.operational.boundary import (
    ReactionBoundaryError,
    extract_reaction_boundary,
)
from functions.operational.coupling import (
    RegularizedCoupling,
    regularized_transition_width,
)
from functions.operational.initialization import (
    BurnInPolicy,
    burn_in_converged,
    relative_state_change,
)
from functions.operational.innovations import (
    TwoBookInnovationPolicy,
    two_book_operational_innovations,
)
from functions.operational.robustness import local_reaction_front_geometry
from functions.operational.solver import (
    OperationalSolverSpec,
    operational_two_book_step,
)
from functions.operational.source import OperationalSource


class OperationalPathError(RuntimeError):
    """Raised when a declared operational path cannot be completed."""


@dataclass(frozen=True)
class OperationalTwoBookPathResult:
    """Stored observables and bounded rolling state from an operational path."""

    operational_times: np.ndarray
    prices: np.ndarray
    boundary_slopes: np.ndarray
    boundary_curvatures: np.ndarray
    boundary_curvature_lengths: np.ndarray
    boundary_candidate_counts: np.ndarray
    boundary_edge_distances: np.ndarray
    base_standard_normals: np.ndarray
    correlated_standard_normals: np.ndarray
    velocities: np.ndarray
    jump_biases: np.ndarray
    directed_spreads: np.ndarray
    selector_transition_widths: np.ndarray
    shock_l1_norms: np.ndarray
    relative_state_changes: np.ndarray
    consecutive_converged_checks: np.ndarray
    burn_in_step: int | None
    stopped_on_burn_in: bool
    density_snapshot_steps: np.ndarray
    density_snapshots: np.ndarray
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


def _snapshot_steps(values: Sequence[int], maximum_step: int) -> tuple[int, ...]:
    result = tuple(values)
    if any(not isinstance(value, int) for value in result):
        raise ValueError("density_snapshot_steps must contain integers")
    if tuple(sorted(set(result))) != result:
        raise ValueError("density_snapshot_steps must be sorted and unique")
    if any(value < 0 or value > maximum_step for value in result):
        raise ValueError("density snapshot step lies outside the supplied path")
    return result


def operational_two_book_path(
    price_grid: np.ndarray,
    initial_densities: np.ndarray,
    initial_prices: Sequence[float],
    sources: Sequence[OperationalSource],
    couplings: Sequence[Sequence[RegularizedCoupling | None]],
    raw_kernels: Sequence[np.ndarray],
    base_standard_normals: np.ndarray,
    innovation_policy: TwoBookInnovationPolicy,
    diffusion: Sequence[float],
    solver_spec: OperationalSolverSpec,
    *,
    shock_fields: np.ndarray | None = None,
    burn_in_policy: BurnInPolicy | None = None,
    stop_on_burn_in: bool = False,
    density_snapshot_steps: Sequence[int] = (),
) -> OperationalTwoBookPathResult:
    """Advance a two-book path while retaining only the finite memory window."""

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

    base = np.asarray(base_standard_normals, dtype=float)
    if base.ndim != 2 or base.shape[1] != 2 or base.shape[0] < 1:
        raise ValueError("base_standard_normals must have shape (steps, 2)")
    if not np.all(np.isfinite(base)):
        raise ValueError("base_standard_normals must be finite")
    maximum_steps = base.shape[0]
    requested_snapshots = _snapshot_steps(density_snapshot_steps, maximum_steps)
    if stop_on_burn_in and burn_in_policy is None:
        raise ValueError("stop_on_burn_in requires a burn_in_policy")

    if len(raw_kernels) != 2:
        raise ValueError("raw_kernels must contain one kernel per book")
    kernels = tuple(np.asarray(kernel, dtype=float) for kernel in raw_kernels)
    if any(
        kernel.ndim != 1 or kernel.size < 1 or not np.all(np.isfinite(kernel))
        for kernel in kernels
    ):
        raise ValueError("raw kernels must be nonempty finite vectors")
    history_capacity = max(kernel.size for kernel in kernels)

    if shock_fields is None:
        shocks = np.zeros((maximum_steps, 2, grid.size), dtype=float)
    else:
        shocks = np.asarray(shock_fields, dtype=float)
        if shocks.shape != (maximum_steps, 2, grid.size):
            raise ValueError("shock_fields must have shape (steps, 2, grid)")
        if not np.all(np.isfinite(shocks)):
            raise ValueError("shock_fields must be finite")
        shocks = np.array(shocks, copy=True)

    innovation = two_book_operational_innovations(
        base,
        innovation_policy,
        transport_probability=solver_spec.transport_probability,
        delta_x=delta_x,
        diffusion=diffusion_values,
    )

    prices = np.empty((maximum_steps + 1, 2), dtype=float)
    slopes = np.empty_like(prices)
    curvatures = np.full_like(prices, np.nan)
    curvature_lengths = np.full_like(prices, np.nan)
    candidate_counts = np.empty((maximum_steps + 1, 2), dtype=int)
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
            raise OperationalPathError(
                f"initial density for book {book + 1} has no admissible boundary"
            ) from error
        tolerance = 1e-10 * max(1.0, abs(boundary.price), delta_x)
        if abs(boundary.price - declared_prices[book]) > tolerance:
            raise ValueError("initial price does not match its density zero crossing")
        slopes[0, book] = boundary.slope
        try:
            geometry = local_reaction_front_geometry(
                grid, initial[book], boundary.price
            )
        except ValueError:
            pass
        else:
            curvatures[0, book] = geometry.curvature
            curvature_lengths[0, book] = geometry.curvature_length
        candidate_counts[0, book] = boundary.candidate_count
        edge_distances[0, book] = boundary.distance_to_domain_edge

    directed_spreads = np.full((maximum_steps, 2, 2), np.nan, dtype=float)
    transition_widths = np.full_like(directed_spreads, np.nan)
    shock_norms = np.sum(np.abs(shocks), axis=2)
    relative_changes = np.empty(maximum_steps, dtype=float)
    consecutive_checks = np.zeros(maximum_steps, dtype=int)
    histories = initial[:, :, None].copy()
    snapshots: list[np.ndarray] = []
    stored_steps: list[int] = []
    if 0 in requested_snapshots:
        stored_steps.append(0)
        snapshots.append(initial.copy())

    consecutive = 0
    burn_in_step: int | None = None
    completed_steps = 0
    for zero_based_step in range(maximum_steps):
        operational_step = zero_based_step + 1
        price_snapshot = prices[zero_based_step].copy()
        for receiving_book in range(2):
            for other_book in range(2):
                if receiving_book == other_book:
                    continue
                coupling = couplings[receiving_book][other_book]
                if coupling is None or not coupling.enabled or coupling.gamma == 0.0:
                    continue
                spread = price_snapshot[receiving_book] - price_snapshot[other_book]
                directed_spreads[zero_based_step, receiving_book, other_book] = spread
                transition_widths[zero_based_step, receiving_book, other_book] = (
                    regularized_transition_width(spread, coupling.epsilon)
                )
        try:
            step = operational_two_book_step(
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
            raise OperationalPathError(
                f"reaction-boundary extraction failed at operational step {operational_step}"
            ) from error

        prices[operational_step] = step.prices
        for book, boundary in enumerate(step.boundaries):
            slopes[operational_step, book] = boundary.slope
            try:
                geometry = local_reaction_front_geometry(
                    grid, step.densities[book], boundary.price
                )
            except ValueError:
                pass
            else:
                curvatures[operational_step, book] = geometry.curvature
                curvature_lengths[operational_step, book] = geometry.curvature_length
            candidate_counts[operational_step, book] = boundary.candidate_count
            edge_distances[operational_step, book] = boundary.distance_to_domain_edge
        relative_changes[zero_based_step] = relative_state_change(
            histories[:, :, -1], step.densities
        )
        if burn_in_policy is not None:
            if relative_changes[zero_based_step] <= burn_in_policy.relative_tolerance:
                consecutive += 1
            else:
                consecutive = 0
            if burn_in_step is None and burn_in_converged(
                histories[:, :, -1],
                step.densities,
                operational_step=operational_step,
                consecutive_converged_checks=consecutive,
                policy=burn_in_policy,
            ):
                burn_in_step = operational_step
        consecutive_checks[zero_based_step] = consecutive

        histories = np.concatenate((histories, step.densities[:, :, None]), axis=2)
        if histories.shape[2] > history_capacity:
            histories = histories[:, :, -history_capacity:]
        if operational_step in requested_snapshots:
            stored_steps.append(operational_step)
            snapshots.append(step.densities.copy())
        completed_steps = operational_step
        if stop_on_burn_in and burn_in_step is not None:
            break

    if snapshots:
        snapshot_array = np.stack(snapshots)
    else:
        snapshot_array = np.empty((0, 2, grid.size), dtype=float)
    used = slice(0, completed_steps)
    state_used = slice(0, completed_steps + 1)
    return OperationalTwoBookPathResult(
        operational_times=np.arange(completed_steps + 1, dtype=float)
        * solver_spec.delta_u,
        prices=prices[state_used].copy(),
        boundary_slopes=slopes[state_used].copy(),
        boundary_curvatures=curvatures[state_used].copy(),
        boundary_curvature_lengths=curvature_lengths[state_used].copy(),
        boundary_candidate_counts=candidate_counts[state_used].copy(),
        boundary_edge_distances=edge_distances[state_used].copy(),
        base_standard_normals=innovation.base_standard_normals[used].copy(),
        correlated_standard_normals=innovation.correlated_standard_normals[used].copy(),
        velocities=innovation.velocities[used].copy(),
        jump_biases=innovation.jump_biases[used].copy(),
        directed_spreads=directed_spreads[used].copy(),
        selector_transition_widths=transition_widths[used].copy(),
        shock_l1_norms=shock_norms[used].copy(),
        relative_state_changes=relative_changes[used].copy(),
        consecutive_converged_checks=consecutive_checks[used].copy(),
        burn_in_step=burn_in_step,
        stopped_on_burn_in=bool(stop_on_burn_in and burn_in_step is not None),
        density_snapshot_steps=np.asarray(stored_steps, dtype=int),
        density_snapshots=snapshot_array,
        final_density_histories=histories.copy(),
        history_capacity=history_capacity,
        completed_steps=completed_steps,
        delta_u=solver_spec.delta_u,
    )


__all__ = [
    "OperationalPathError",
    "OperationalTwoBookPathResult",
    "operational_two_book_path",
]
