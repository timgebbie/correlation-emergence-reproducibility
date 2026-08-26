"""Declared order-event tapes on the uniform operational solver.

Events change the current density state immediately before their declared
operational step.  The complete path is produced before any observation clock
is introduced.  This module owns neither a random-number generator nor a
calendar-time map.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from functions.events.records import EventApplication, OrderEvent, apply_order_event
from functions.operational.boundary import ReactionBoundaryError, extract_reaction_boundary
from functions.operational.innovations import (
    TwoBookInnovationPolicy,
    two_book_operational_innovations,
)
from functions.operational.solver import OperationalSolverSpec
from functions.operational.source import OperationalSource
from functions.operational.translation_coupling import TranslationModeCoupling
from functions.operational.translation_path import TranslationModePathError
from functions.operational.translation_solver import operational_translation_two_book_step


@dataclass(frozen=True)
class OperationalEventTapeResult:
    """One complete two-book operational path with declared events."""

    operational_times: np.ndarray
    prices: np.ndarray
    events: tuple[OrderEvent, ...]
    event_applications: tuple[EventApplication, ...]
    event_state_indices: np.ndarray
    base_standard_normals: np.ndarray
    correlated_standard_normals: np.ndarray
    velocities: np.ndarray
    jump_biases: np.ndarray
    boundary_candidate_counts: np.ndarray
    boundary_edge_distances: np.ndarray
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


def _event_tape(events: Sequence[OrderEvent], steps: int) -> tuple[OrderEvent, ...]:
    tape = tuple(events)
    if not tape or any(not isinstance(event, OrderEvent) for event in tape):
        raise ValueError("events must contain at least one OrderEvent")
    keys = tuple((event.operational_step, event.book_index, event.event_id) for event in tape)
    if keys != tuple(sorted(keys)):
        raise ValueError("events must be sorted by operational step, book and event_id")
    if tape[-1].operational_step > steps:
        raise ValueError("event tape exceeds the supplied operational path")
    if len({event.event_id for event in tape}) != len(tape):
        raise ValueError("event_id values must be unique within a tape")
    state_keys = [(event.operational_step, event.book_index) for event in tape]
    if len(set(state_keys)) != len(state_keys):
        raise ValueError("a tape may contain at most one event per book and step")
    return tape


def operational_translation_event_tape_path(
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
    events: Sequence[OrderEvent],
) -> OperationalEventTapeResult:
    """Advance a declared event tape without clocks or nonuniform updates."""

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
    if len(sources) != 2 or len(couplings) != 2 or any(len(row) != 2 for row in couplings):
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
    tape = _event_tape(events, steps)

    innovation = two_book_operational_innovations(
        base,
        innovation_policy,
        transport_probability=solver_spec.transport_probability,
        delta_x=delta_x,
        diffusion=diffusion_values,
    )
    operational_times = np.arange(steps + 1, dtype=float) * solver_spec.delta_u
    prices = np.empty((steps + 1, 2), dtype=float)
    prices[0] = declared_prices
    candidate_counts = np.empty((steps + 1, 2), dtype=int)
    edge_distances = np.empty((steps + 1, 2), dtype=float)
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
        candidate_counts[0, book] = boundary.candidate_count
        edge_distances[0, book] = boundary.distance_to_domain_edge

    events_by_step: dict[int, list[OrderEvent]] = {}
    for event in tape:
        events_by_step.setdefault(event.operational_step, []).append(event)
    histories = np.array(initial[:, :, None], copy=True)
    applications: list[EventApplication] = []
    for zero_based_step in range(steps):
        one_based_step = zero_based_step + 1
        price_snapshot = np.array(prices[zero_based_step], copy=True)
        declared_at_step = events_by_step.get(one_based_step, ())
        if declared_at_step:
            event_state = np.array(histories[:, :, -1], copy=True)
            for event in declared_at_step:
                application = apply_order_event(
                    event,
                    grid,
                    event_state[event.book_index],
                    pre_event_mid_log_price=float(price_snapshot[event.book_index]),
                )
                event_state[event.book_index] += application.density_delta
                applications.append(application)
            if not np.allclose(event_state[:, [0, -1]], 0.0, rtol=0.0, atol=1e-14):
                raise RuntimeError("event tape violates the outer density boundaries")
            histories[:, :, -1] = event_state
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
            )
        except ReactionBoundaryError as error:
            raise TranslationModePathError(
                "reaction-boundary extraction failed during event tape at "
                f"operational step {one_based_step}"
            ) from error
        prices[one_based_step] = result.prices
        for book, boundary in enumerate(result.boundaries):
            candidate_counts[one_based_step, book] = boundary.candidate_count
            edge_distances[one_based_step, book] = boundary.distance_to_domain_edge
        histories = np.concatenate((histories, result.densities[:, :, None]), axis=2)
        if histories.shape[2] > history_capacity:
            histories = histories[:, :, -history_capacity:]

    if len(applications) != len(tape):
        raise RuntimeError("not every declared event was applied")
    state_indices = np.asarray([event.operational_step for event in tape], dtype=int)
    for array in (operational_times, prices, state_indices, candidate_counts, edge_distances, histories):
        array.setflags(write=False)
    return OperationalEventTapeResult(
        operational_times=operational_times,
        prices=prices,
        events=tape,
        event_applications=tuple(applications),
        event_state_indices=state_indices,
        base_standard_normals=innovation.base_standard_normals,
        correlated_standard_normals=innovation.correlated_standard_normals,
        velocities=innovation.velocities,
        jump_biases=innovation.jump_biases,
        boundary_candidate_counts=candidate_counts,
        boundary_edge_distances=edge_distances,
        final_density_histories=histories,
        history_capacity=history_capacity,
        completed_steps=steps,
        delta_u=solver_spec.delta_u,
    )


__all__ = ["OperationalEventTapeResult", "operational_translation_event_tape_path"]
