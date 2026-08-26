"""Paired single-event paths on the accepted uniform operational solver.

This module is the explicit bridge between the deterministic event records and
the operational dynamics.  It applies one event density delta immediately
before its declared operational step, advances shocked and control paths with
identical supplied innovations, and owns no calendar clock or interpolation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from functions.events.records import EventApplication, OrderEvent, apply_order_event
from functions.operational.boundary import ReactionBoundaryError
from functions.operational.innovations import (
    TwoBookInnovationPolicy,
    two_book_operational_innovations,
)
from functions.operational.solver import OperationalSolverSpec
from functions.operational.source import OperationalSource
from functions.operational.translation_coupling import TranslationModeCoupling
from functions.operational.translation_path import (
    TranslationModePathError,
    operational_translation_two_book_path,
)
from functions.operational.translation_solver import operational_translation_two_book_step


@dataclass(frozen=True)
class PairedSingleEventPathResult:
    """Control and shocked operational prices under common innovations."""

    operational_times: np.ndarray
    control_prices: np.ndarray
    shocked_prices: np.ndarray
    paired_price_difference: np.ndarray
    event_application: EventApplication
    event_state_index: int
    base_standard_normals: np.ndarray
    correlated_standard_normals: np.ndarray
    velocities: np.ndarray
    jump_biases: np.ndarray
    shocked_boundary_candidate_counts: np.ndarray
    shocked_boundary_edge_distances: np.ndarray
    history_capacity: int
    completed_steps: int
    delta_u: float

    @property
    def signed_price_response(self) -> np.ndarray:
        """Return aggressor-signed shocked-minus-control price differences."""

        result = self.event_application.event.side * self.paired_price_difference
        result = np.array(result, copy=True)
        result.setflags(write=False)
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


def operational_translation_single_event_pair(
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
    event: OrderEvent,
) -> PairedSingleEventPathResult:
    """Advance one control/event pair without clocks or nonuniform updates."""

    grid, _ = _uniform_grid(price_grid)
    initial = np.asarray(initial_densities, dtype=float)
    if initial.shape != (2, grid.size) or not np.all(np.isfinite(initial)):
        raise ValueError("initial_densities must have shape (2, grid)")
    declared_prices = np.asarray(initial_prices, dtype=float)
    if declared_prices.shape != (2,) or not np.all(np.isfinite(declared_prices)):
        raise ValueError("initial_prices must contain two finite values")
    base = np.asarray(base_standard_normals, dtype=float)
    if base.ndim != 2 or base.shape[1] != 2 or base.shape[0] < 1:
        raise ValueError("base_standard_normals must have shape (steps, 2)")
    if not np.all(np.isfinite(base)):
        raise ValueError("base_standard_normals must be finite")
    if event.operational_step > base.shape[0]:
        raise ValueError("event operational_step exceeds the supplied path")
    if len(raw_kernels) != 2:
        raise ValueError("raw_kernels must contain one kernel per book")
    kernels = tuple(np.asarray(kernel, dtype=float) for kernel in raw_kernels)
    if any(kernel.ndim != 1 or kernel.size < 1 for kernel in kernels):
        raise ValueError("raw kernels must be nonempty vectors")
    history_capacity = max(kernel.size for kernel in kernels)

    control = operational_translation_two_book_path(
        grid,
        initial,
        declared_prices,
        sources,
        couplings,
        kernels,
        base,
        innovation_policy,
        diffusion,
        solver_spec,
    )
    innovation = two_book_operational_innovations(
        base,
        innovation_policy,
        transport_probability=solver_spec.transport_probability,
        delta_x=float(grid[1] - grid[0]),
        diffusion=diffusion,
    )

    steps = base.shape[0]
    prices = np.empty((steps + 1, 2), dtype=float)
    prices[0] = declared_prices
    candidate_counts = np.empty((steps + 1, 2), dtype=int)
    edge_distances = np.empty((steps + 1, 2), dtype=float)
    candidate_counts[0] = control.boundary_candidate_counts[0]
    edge_distances[0] = control.boundary_edge_distances[0]
    histories = np.array(initial[:, :, None], copy=True)
    application: EventApplication | None = None

    for zero_based_step in range(steps):
        one_based_step = zero_based_step + 1
        price_snapshot = prices[zero_based_step].copy()
        if one_based_step == event.operational_step:
            application = apply_order_event(
                event,
                grid,
                histories[event.book_index, :, -1],
                pre_event_mid_log_price=float(price_snapshot[event.book_index]),
            )
            event_state = np.array(histories[:, :, -1], copy=True)
            event_state[event.book_index] += application.density_delta
            if not np.allclose(event_state[:, [0, -1]], 0.0, rtol=0.0, atol=1e-14):
                raise RuntimeError("event density delta violates outer boundaries")
            histories[:, :, -1] = event_state
        try:
            step = operational_translation_two_book_step(
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
                "reaction-boundary extraction failed after event at operational step "
                f"{one_based_step}"
            ) from error
        prices[one_based_step] = step.prices
        for book, boundary in enumerate(step.boundaries):
            candidate_counts[one_based_step, book] = boundary.candidate_count
            edge_distances[one_based_step, book] = boundary.distance_to_domain_edge
        histories = np.concatenate((histories, step.densities[:, :, None]), axis=2)
        if histories.shape[2] > history_capacity:
            histories = histories[:, :, -history_capacity:]

    if application is None:
        raise RuntimeError("declared event was not applied")
    difference = prices - control.prices
    arrays = (
        prices,
        difference,
        candidate_counts,
        edge_distances,
    )
    for array in arrays:
        array.setflags(write=False)
    return PairedSingleEventPathResult(
        operational_times=control.operational_times,
        control_prices=control.prices,
        shocked_prices=prices,
        paired_price_difference=difference,
        event_application=application,
        event_state_index=event.operational_step,
        base_standard_normals=innovation.base_standard_normals,
        correlated_standard_normals=innovation.correlated_standard_normals,
        velocities=innovation.velocities,
        jump_biases=innovation.jump_biases,
        shocked_boundary_candidate_counts=candidate_counts,
        shocked_boundary_edge_distances=edge_distances,
        history_capacity=history_capacity,
        completed_steps=steps,
        delta_u=solver_spec.delta_u,
    )


__all__ = [
    "PairedSingleEventPathResult",
    "operational_translation_single_event_pair",
]
