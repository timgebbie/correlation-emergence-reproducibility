"""Paired scheduled meta-orders on the uniform operational solver.

A meta-order is a declared sequence of child market-order events.  Each child
is applied immediately before its operational step.  Shocked and control paths
share supplied innovations; this module owns neither a random-number generator
nor a calendar clock.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np

from functions.events.records import (
    EVENT_MARKET_ORDER,
    EventApplication,
    OrderEvent,
    apply_order_event,
)
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
class MetaOrderSchedule:
    """One signed sequence of child market orders in one book."""

    meta_order_id: str
    book_index: int
    side: int
    child_operational_steps: tuple[int, ...]
    child_quantities: tuple[float, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.meta_order_id, str) or not self.meta_order_id.strip():
            raise ValueError("meta_order_id must be a nonempty string")
        if self.book_index not in {0, 1}:
            raise ValueError("book_index must be zero or one")
        if self.side not in {-1, 1}:
            raise ValueError("side must be -1 or +1")
        steps = tuple(int(value) for value in self.child_operational_steps)
        quantities = tuple(float(value) for value in self.child_quantities)
        if len(steps) < 2 or len(steps) != len(quantities):
            raise ValueError("meta-orders require matching sequences of at least two children")
        if steps[0] < 1 or any(right <= left for left, right in zip(steps, steps[1:])):
            raise ValueError("child operational steps must be positive and strictly increasing")
        if any(not math.isfinite(value) or value <= 0.0 for value in quantities):
            raise ValueError("child quantities must be positive and finite")
        object.__setattr__(self, "child_operational_steps", steps)
        object.__setattr__(self, "child_quantities", quantities)

    @property
    def child_count(self) -> int:
        return len(self.child_operational_steps)

    @property
    def total_quantity(self) -> float:
        return float(sum(self.child_quantities))

    @property
    def cumulative_quantities(self) -> np.ndarray:
        result = np.cumsum(np.asarray(self.child_quantities, dtype=float))
        result.setflags(write=False)
        return result

    @property
    def first_step(self) -> int:
        return self.child_operational_steps[0]

    @property
    def last_step(self) -> int:
        return self.child_operational_steps[-1]

    def events(self) -> tuple[OrderEvent, ...]:
        return tuple(
            OrderEvent(
                event_id=f"{self.meta_order_id}-child-{index:02d}",
                event_type=EVENT_MARKET_ORDER,
                book_index=self.book_index,
                operational_step=step,
                side=self.side,
                quantity=quantity,
                meta_order_id=self.meta_order_id,
                child_index=index,
            )
            for index, (step, quantity) in enumerate(
                zip(self.child_operational_steps, self.child_quantities)
            )
        )


@dataclass(frozen=True)
class PairedMetaOrderPathResult:
    """Control and shocked operational paths for one meta-order schedule."""

    operational_times: np.ndarray
    control_prices: np.ndarray
    shocked_prices: np.ndarray
    paired_price_difference: np.ndarray
    schedule: MetaOrderSchedule
    event_applications: tuple[EventApplication, ...]
    event_state_indices: np.ndarray
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
        result = self.schedule.side * self.paired_price_difference
        result = np.array(result, copy=True)
        result.setflags(write=False)
        return result


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


def operational_translation_meta_order_pair(
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
    schedule: MetaOrderSchedule,
) -> PairedMetaOrderPathResult:
    """Advance one control/meta-order pair without clocks or nonuniform steps."""

    grid = _uniform_grid(price_grid)
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
    if schedule.last_step > base.shape[0]:
        raise ValueError("meta-order schedule exceeds the supplied path")
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

    events_by_step = {event.operational_step: event for event in schedule.events()}
    steps = base.shape[0]
    prices = np.empty((steps + 1, 2), dtype=float)
    prices[0] = declared_prices
    candidate_counts = np.empty((steps + 1, 2), dtype=int)
    edge_distances = np.empty((steps + 1, 2), dtype=float)
    candidate_counts[0] = control.boundary_candidate_counts[0]
    edge_distances[0] = control.boundary_edge_distances[0]
    histories = np.array(initial[:, :, None], copy=True)
    applications: list[EventApplication] = []

    for zero_based_step in range(steps):
        one_based_step = zero_based_step + 1
        price_snapshot = prices[zero_based_step].copy()
        event = events_by_step.get(one_based_step)
        if event is not None:
            application = apply_order_event(
                event,
                grid,
                histories[event.book_index, :, -1],
                pre_event_mid_log_price=float(price_snapshot[event.book_index]),
            )
            event_state = np.array(histories[:, :, -1], copy=True)
            event_state[event.book_index] += application.density_delta
            if not np.allclose(event_state[:, [0, -1]], 0.0, rtol=0.0, atol=1e-14):
                raise RuntimeError("child density delta violates outer boundaries")
            histories[:, :, -1] = event_state
            applications.append(application)
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
                "reaction-boundary extraction failed during meta-order at operational "
                f"step {one_based_step}"
            ) from error
        prices[one_based_step] = result.prices
        for book, boundary in enumerate(result.boundaries):
            candidate_counts[one_based_step, book] = boundary.candidate_count
            edge_distances[one_based_step, book] = boundary.distance_to_domain_edge
        histories = np.concatenate((histories, result.densities[:, :, None]), axis=2)
        if histories.shape[2] > history_capacity:
            histories = histories[:, :, -history_capacity:]

    if len(applications) != schedule.child_count:
        raise RuntimeError("not every declared child event was applied")
    difference = prices - control.prices
    event_indices = np.asarray(schedule.child_operational_steps, dtype=int)
    for array in (prices, difference, event_indices, candidate_counts, edge_distances):
        array.setflags(write=False)
    return PairedMetaOrderPathResult(
        operational_times=control.operational_times,
        control_prices=control.prices,
        shocked_prices=prices,
        paired_price_difference=difference,
        schedule=schedule,
        event_applications=tuple(applications),
        event_state_indices=event_indices,
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
    "MetaOrderSchedule",
    "PairedMetaOrderPathResult",
    "operational_translation_meta_order_pair",
]
