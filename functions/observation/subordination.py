"""Pathwise operational-to-calendar evaluation under explicit book clocks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from functions.observation.clocks import (
    BookClockPath,
    inverse_clock_previous_state,
)


@dataclass(frozen=True)
class TwoBookSubordinationResult:
    """Two operational price paths evaluated on one declared calendar grid."""

    calendar_times: np.ndarray
    prices: np.ndarray
    operational_indices: np.ndarray
    inverse_operational_times: np.ndarray
    clock_horizons: np.ndarray
    clock_stream_ids: tuple[str, str]
    inverse_convention: str


def _operational_values(values: np.ndarray, states: int) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.ndim < 1 or result.shape[0] != states:
        raise ValueError("operational_values must have the clock state axis first")
    if not np.all(np.isfinite(result)):
        raise ValueError("operational_values must be finite")
    return result


def subordinate_operational_values(
    operational_values: np.ndarray,
    clock: BookClockPath,
    calendar_times: np.ndarray,
) -> np.ndarray:
    """Evaluate any stored operational field by the declared inverse clock."""

    values = _operational_values(operational_values, clock.states)
    inverse = inverse_clock_previous_state(clock, calendar_times)
    return np.array(values[inverse.operational_indices], copy=True)


def subordinate_two_book_prices(
    operational_prices: np.ndarray,
    clocks: Sequence[BookClockPath],
    calendar_times: np.ndarray,
) -> TwoBookSubordinationResult:
    """Map one two-book operational price path to common calendar timestamps."""

    prices = np.asarray(operational_prices, dtype=float)
    clock_values = tuple(clocks)
    if len(clock_values) != 2:
        raise ValueError("clocks must contain one explicit path per book")
    if prices.ndim != 2 or prices.shape[1] != 2:
        raise ValueError("operational_prices must have shape (states, 2)")
    if not np.all(np.isfinite(prices)):
        raise ValueError("operational_prices must be finite")
    first, second = clock_values
    if first.states != prices.shape[0] or second.states != prices.shape[0]:
        raise ValueError("each clock must cover every operational price state")
    if not np.array_equal(first.operational_times, second.operational_times):
        raise ValueError("both clocks must reference the same operational grid")
    if first.inverse_convention != second.inverse_convention:
        raise ValueError("both clocks must use the same inverse convention")

    inverse_results = (
        inverse_clock_previous_state(first, calendar_times),
        inverse_clock_previous_state(second, calendar_times),
    )
    query = inverse_results[0].calendar_times
    if not np.array_equal(query, inverse_results[1].calendar_times):
        raise RuntimeError("book inverse clocks returned inconsistent query grids")
    indices = np.column_stack(
        [result.operational_indices for result in inverse_results]
    )
    inverse_times = np.column_stack(
        [result.operational_times for result in inverse_results]
    )
    calendar_prices = np.column_stack(
        [prices[indices[:, book], book] for book in range(2)]
    )
    horizons = np.asarray(
        [first.supported_calendar_horizon, second.supported_calendar_horizon],
        dtype=float,
    )
    return TwoBookSubordinationResult(
        calendar_times=np.array(query, copy=True),
        prices=calendar_prices,
        operational_indices=indices,
        inverse_operational_times=inverse_times,
        clock_horizons=horizons,
        clock_stream_ids=(first.stream_id, second.stream_id),
        inverse_convention=first.inverse_convention,
    )


__all__ = [
    "TwoBookSubordinationResult",
    "subordinate_operational_values",
    "subordinate_two_book_prices",
]
