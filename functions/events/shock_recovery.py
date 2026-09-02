"""Fixed-time order-book shock chronology on the accepted operational solver.

The event is applied as a density delta immediately before its declared
operational step.  The intermediate post-event state is retained explicitly,
including the possibility that boundary-outward consumption creates a short
zero-density interval before the next solver step restores a simple reaction
boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np

from functions.events.records import EventApplication, OrderEvent, apply_order_event
from functions.operational.boundary import (
    ReactionBoundaryError,
    extract_reaction_boundary,
)
from functions.operational.solver import OperationalSolverSpec
from functions.operational.source import OperationalSource
from functions.operational.translation_coupling import TranslationModeCoupling
from functions.operational.translation_solver import operational_translation_two_book_step


@dataclass(frozen=True)
class FixedTimeShockRecoveryResult:
    """Nine registered views of one deterministic market-order experiment."""

    price_grid: np.ndarray
    snapshot_lag_steps: np.ndarray
    snapshot_lag_seconds: np.ndarray
    snapshot_kinds: np.ndarray
    densities: np.ndarray
    prices: np.ndarray
    price_is_registered: np.ndarray
    contribution_price_inputs: np.ndarray
    arrival_contributions: np.ndarray
    cancellation_contributions: np.ndarray
    impulse_contributions: np.ndarray
    coupling_contributions: np.ndarray
    history_contributions: np.ndarray
    boundary_corrections: np.ndarray
    ledger_errors: np.ndarray
    control_densities: np.ndarray
    control_prices: np.ndarray
    event_application: EventApplication
    pre_event_identity_error: float
    event_state_index: int
    delta_u: float
    seconds_per_model_time_unit: float


def _arrays(
    price_grid: np.ndarray,
    initial_densities: np.ndarray,
    initial_prices: Sequence[float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    grid = np.asarray(price_grid, dtype=float)
    densities = np.asarray(initial_densities, dtype=float)
    prices = np.asarray(initial_prices, dtype=float)
    if grid.ndim != 1 or grid.size < 3 or not np.all(np.isfinite(grid)):
        raise ValueError("price_grid must be a finite vector")
    differences = np.diff(grid)
    if np.any(differences <= 0.0) or not np.allclose(
        differences, differences[0], rtol=1e-12, atol=1e-14
    ):
        raise ValueError("price_grid must be strictly increasing and uniform")
    if densities.shape != (2, grid.size) or not np.all(np.isfinite(densities)):
        raise ValueError("initial_densities must have shape (2, grid)")
    if prices.shape != (2,) or not np.all(np.isfinite(prices)):
        raise ValueError("initial_prices must contain two finite values")
    return grid, densities, prices, float(differences[0])


def fixed_time_order_book_shock_recovery(
    price_grid: np.ndarray,
    initial_densities: np.ndarray,
    initial_prices: Sequence[float],
    sources: Sequence[OperationalSource],
    couplings: Sequence[Sequence[TranslationModeCoupling | None]],
    raw_kernels: Sequence[np.ndarray],
    solver_spec: OperationalSolverSpec,
    event: OrderEvent,
    *,
    pre_event_steps: int,
    evolved_snapshot_lag_steps: Sequence[int],
    seconds_per_model_time_unit: float,
) -> FixedTimeShockRecoveryResult:
    """Return the event pair and seven later states used by Figure 12.

    Innovations are identically zero so that the figure isolates the declared
    event, fixed-grid dynamics and active translation-mode coupling.  A matched
    no-event control is advanced through the same deterministic steps.
    """

    grid, initial, declared_prices, delta_x = _arrays(
        price_grid, initial_densities, initial_prices
    )
    if not isinstance(pre_event_steps, int) or pre_event_steps < 0:
        raise ValueError("pre_event_steps must be a nonnegative integer")
    if event.operational_step != pre_event_steps + 1:
        raise ValueError("event must occur immediately after pre_event_steps")
    lags = np.asarray(tuple(evolved_snapshot_lag_steps), dtype=int)
    if lags.shape != (7,) or np.any(lags <= 0) or np.any(np.diff(lags) <= 0):
        raise ValueError("seven strictly increasing positive evolved lags are required")
    seconds_scale = float(seconds_per_model_time_unit)
    if not math.isfinite(seconds_scale) or seconds_scale <= 0.0:
        raise ValueError("seconds_per_model_time_unit must be positive and finite")
    if len(raw_kernels) != 2:
        raise ValueError("raw_kernels must contain one kernel per book")
    kernels = tuple(np.asarray(kernel, dtype=float) for kernel in raw_kernels)
    if any(kernel.ndim != 1 or kernel.size < 1 for kernel in kernels):
        raise ValueError("raw_kernels must contain nonempty vectors")
    history_capacity = max(kernel.size for kernel in kernels)
    if event.book_index not in (0, 1):
        raise ValueError("event must identify one of the two books")

    histories = initial[:, :, None].copy()
    prices = declared_prices.copy()
    zero_bias = np.zeros(2, dtype=float)
    for _ in range(pre_event_steps):
        step = operational_translation_two_book_step(
            grid,
            histories,
            prices,
            sources,
            couplings,
            kernels,
            zero_bias,
            solver_spec,
        )
        prices = step.prices.copy()
        histories = np.concatenate((histories, step.densities[:, :, None]), axis=2)
        if histories.shape[2] > history_capacity:
            histories = histories[:, :, -history_capacity:]

    pre_event_density = histories[:, :, -1].copy()
    pre_event_prices = prices.copy()
    pre_event_identity_error = float(np.max(np.abs(pre_event_density - initial)))

    application = apply_order_event(
        event,
        grid,
        pre_event_density[event.book_index],
        pre_event_mid_log_price=float(pre_event_prices[event.book_index]),
    )
    post_event_density = pre_event_density.copy()
    post_event_density[event.book_index] += application.density_delta
    if not np.allclose(post_event_density[:, [0, -1]], 0.0, rtol=0.0, atol=1e-14):
        raise RuntimeError("event violates the fixed outer boundary")

    post_event_prices = pre_event_prices.copy()
    post_registered = np.ones(2, dtype=bool)
    event_density = post_event_density[event.book_index]
    near_zero = np.isclose(event_density[1:-1], 0.0, rtol=0.0, atol=1e-14)
    has_cleared_interval = bool(np.any(near_zero[:-1] & near_zero[1:]))
    if has_cleared_interval:
        # Boundary-outward market-order consumption can create a zero-density
        # interval.  Detect it directly instead of relying on the boundary
        # extractor to reject every platform-level near-zero representation.
        # The last registered boundary remains the state variable until the
        # ordinary operational step restores a simple zero crossing.
        post_registered[event.book_index] = False
    else:
        try:
            post_boundary = extract_reaction_boundary(
                grid,
                event_density,
                selection=solver_spec.boundary_selection,
                previous_price=float(pre_event_prices[event.book_index]),
                minimum_abs_slope=solver_spec.minimum_abs_boundary_slope,
            )
        except ReactionBoundaryError:
            post_registered[event.book_index] = False
        else:
            post_event_prices[event.book_index] = post_boundary.price

    control_histories = histories.copy()
    control_prices_state = pre_event_prices.copy()
    shocked_histories = histories.copy()
    shocked_histories[:, :, -1] = post_event_density
    shocked_prices_state = pre_event_prices.copy()

    snapshot_steps = np.concatenate((np.asarray([0, 0], dtype=int), lags))
    snapshot_seconds = np.round(
        snapshot_steps.astype(float) * solver_spec.delta_u * seconds_scale,
        decimals=12,
    )
    kinds = np.asarray(("event_pre", "event_post", *("evolved" for _ in lags)))
    count = snapshot_steps.size
    shape = (count, 2, grid.size)
    densities = np.empty(shape, dtype=float)
    snapshot_prices = np.empty((count, 2), dtype=float)
    registered = np.ones((count, 2), dtype=bool)
    contribution_prices = np.empty((count, 2), dtype=float)
    arrivals = np.zeros(shape, dtype=float)
    cancellations = np.zeros(shape, dtype=float)
    impulses = np.zeros(shape, dtype=float)
    coupling = np.zeros(shape, dtype=float)
    history_parts = np.zeros(shape, dtype=float)
    corrections = np.zeros(shape, dtype=float)
    ledger_errors = np.zeros((count, 2), dtype=float)
    control_densities = np.empty(shape, dtype=float)
    control_snapshot_prices = np.empty((count, 2), dtype=float)

    densities[0] = pre_event_density
    densities[1] = post_event_density
    snapshot_prices[0] = pre_event_prices
    snapshot_prices[1] = post_event_prices
    registered[1] = post_registered
    contribution_prices[0] = pre_event_prices
    contribution_prices[1] = pre_event_prices
    impulses[0, event.book_index] = application.density_delta
    control_densities[0] = pre_event_density
    control_densities[1] = pre_event_density
    control_snapshot_prices[0] = pre_event_prices
    control_snapshot_prices[1] = pre_event_prices

    lag_to_panel = {int(lag): index + 2 for index, lag in enumerate(lags)}
    first_step_fields: tuple[np.ndarray, np.ndarray] | None = None
    for lag in range(1, int(lags[-1]) + 1):
        shocked_input = shocked_histories[:, :, -1].copy()
        shocked_price_input = shocked_prices_state.copy()
        shocked_step = operational_translation_two_book_step(
            grid,
            shocked_histories,
            shocked_prices_state,
            sources,
            couplings,
            kernels,
            zero_bias,
            solver_spec,
        )
        control_step = operational_translation_two_book_step(
            grid,
            control_histories,
            control_prices_state,
            sources,
            couplings,
            kernels,
            zero_bias,
            solver_spec,
        )

        arrival = solver_spec.delta_u * shocked_step.source_fields
        cancel = shocked_step.survivor_contributions - shocked_input
        coupling_part = solver_spec.delta_u * shocked_step.total_coupling_fields
        reconstructed = (
            shocked_step.history_contributions
            + shocked_input
            + cancel
            + arrival
            + coupling_part
            + shocked_step.boundary_corrections
        )
        ledger_error = np.max(np.abs(reconstructed - shocked_step.densities), axis=1)
        if first_step_fields is None:
            first_step_fields = (arrival.copy(), coupling_part.copy())
            arrivals[0] = arrival
            arrivals[1] = arrival
            cancellations[0] = (
                math.exp(-solver_spec.cancellation_rates[0] * solver_spec.delta_u) - 1.0
            ) * pre_event_density
            cancellations[0, 1] = (
                math.exp(-solver_spec.cancellation_rates[1] * solver_spec.delta_u) - 1.0
            ) * pre_event_density[1]
            cancellations[1] = cancel
            coupling[0] = coupling_part
            coupling[1] = coupling_part

        shocked_prices_state = shocked_step.prices.copy()
        control_prices_state = control_step.prices.copy()
        shocked_histories = np.concatenate(
            (shocked_histories, shocked_step.densities[:, :, None]), axis=2
        )
        control_histories = np.concatenate(
            (control_histories, control_step.densities[:, :, None]), axis=2
        )
        if shocked_histories.shape[2] > history_capacity:
            shocked_histories = shocked_histories[:, :, -history_capacity:]
            control_histories = control_histories[:, :, -history_capacity:]

        if lag in lag_to_panel:
            panel = lag_to_panel[lag]
            densities[panel] = shocked_step.densities
            snapshot_prices[panel] = shocked_step.prices
            contribution_prices[panel] = shocked_price_input
            arrivals[panel] = arrival
            cancellations[panel] = cancel
            coupling[panel] = coupling_part
            history_parts[panel] = shocked_step.history_contributions
            corrections[panel] = shocked_step.boundary_corrections
            ledger_errors[panel] = ledger_error
            control_densities[panel] = control_step.densities
            control_snapshot_prices[panel] = control_step.prices

    if first_step_fields is None:
        raise RuntimeError("at least one evolved step is required")
    if not np.isclose(delta_x * np.sum(np.abs(application.density_delta)), event.quantity):
        raise RuntimeError("event quantity does not equal the density delta integral")

    result_arrays = (
        grid,
        snapshot_steps,
        snapshot_seconds,
        kinds,
        densities,
        snapshot_prices,
        registered,
        contribution_prices,
        arrivals,
        cancellations,
        impulses,
        coupling,
        history_parts,
        corrections,
        ledger_errors,
        control_densities,
        control_snapshot_prices,
    )
    for array in result_arrays:
        array.setflags(write=False)
    return FixedTimeShockRecoveryResult(
        price_grid=grid,
        snapshot_lag_steps=snapshot_steps,
        snapshot_lag_seconds=snapshot_seconds,
        snapshot_kinds=kinds,
        densities=densities,
        prices=snapshot_prices,
        price_is_registered=registered,
        contribution_price_inputs=contribution_prices,
        arrival_contributions=arrivals,
        cancellation_contributions=cancellations,
        impulse_contributions=impulses,
        coupling_contributions=coupling,
        history_contributions=history_parts,
        boundary_corrections=corrections,
        ledger_errors=ledger_errors,
        control_densities=control_densities,
        control_prices=control_snapshot_prices,
        event_application=application,
        pre_event_identity_error=pre_event_identity_error,
        event_state_index=event.operational_step,
        delta_u=solver_spec.delta_u,
        seconds_per_model_time_unit=seconds_scale,
    )


__all__ = [
    "FixedTimeShockRecoveryResult",
    "fixed_time_order_book_shock_recovery",
]
