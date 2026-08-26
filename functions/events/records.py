"""Order-event records and deterministic operational-grid applications.

The signed density convention is positive bid liquidity below the reaction
boundary and negative ask liquidity above it.  Events create a density delta;
they do not advance the operational solver, own a random number generator, or
observe the resulting path in calendar time.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np


EVENT_LIMIT_ORDER = "limit_order"
EVENT_MARKET_ORDER = "market_order"


class InsufficientLiquidityError(RuntimeError):
    """Raised when a market order cannot be filled by available liquidity."""


def _positive_finite(name: str, value: float) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be positive and finite")
    return result


@dataclass(frozen=True)
class OrderEvent:
    """One declared order event before application to an operational state."""

    event_id: str
    event_type: str
    book_index: int
    operational_step: int
    side: int
    quantity: float
    limit_log_price: float | None = None
    meta_order_id: str | None = None
    child_index: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, str) or not self.event_id.strip():
            raise ValueError("event_id must be a nonempty string")
        if self.event_type not in {EVENT_LIMIT_ORDER, EVENT_MARKET_ORDER}:
            raise ValueError("event_type must be limit_order or market_order")
        if self.book_index not in {0, 1}:
            raise ValueError("book_index must be zero or one")
        if not isinstance(self.operational_step, (int, np.integer)) or self.operational_step < 1:
            raise ValueError("operational_step must be a positive integer")
        if self.side not in {-1, 1}:
            raise ValueError("side must be -1 for sell or +1 for buy")
        object.__setattr__(self, "quantity", _positive_finite("quantity", self.quantity))
        if self.event_type == EVENT_LIMIT_ORDER:
            if self.limit_log_price is None or not math.isfinite(float(self.limit_log_price)):
                raise ValueError("limit orders require a finite limit_log_price")
            object.__setattr__(self, "limit_log_price", float(self.limit_log_price))
        elif self.limit_log_price is not None:
            raise ValueError("market orders must not declare limit_log_price")
        if (self.meta_order_id is None) != (self.child_index is None):
            raise ValueError("meta_order_id and child_index must be supplied together")
        if self.meta_order_id is not None:
            if not isinstance(self.meta_order_id, str) or not self.meta_order_id.strip():
                raise ValueError("meta_order_id must be a nonempty string")
            if not isinstance(self.child_index, (int, np.integer)) or self.child_index < 0:
                raise ValueError("child_index must be a nonnegative integer")


@dataclass(frozen=True)
class EventApplication:
    """The deterministic density delta and accounting produced by an event."""

    event: OrderEvent
    pre_event_mid_log_price: float
    density_delta: np.ndarray
    affected_grid_indices: tuple[int, ...]
    placed_quantity: float
    filled_quantity: float
    execution_log_price: float | None
    semantic_role: str

    @property
    def is_trade(self) -> bool:
        return self.event.event_type == EVENT_MARKET_ORDER and self.filled_quantity > 0.0

    @property
    def aggressor_sign(self) -> int:
        return ground_truth_aggressor_sign(self)


def _state_arrays(grid: np.ndarray, density: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    x = np.asarray(grid, dtype=float)
    phi = np.asarray(density, dtype=float)
    if x.ndim != 1 or phi.shape != x.shape or x.size < 3:
        raise ValueError("grid and density must be matching one-dimensional arrays")
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(phi)) or np.any(np.diff(x) <= 0.0):
        raise ValueError("grid and density must be finite and the grid strictly increasing")
    steps = np.diff(x)
    if not np.allclose(steps, steps[0], rtol=1e-12, atol=1e-14):
        raise ValueError("event applications require a uniform operational grid")
    return x, phi, float(steps[0])


def apply_limit_order(
    event: OrderEvent,
    grid: np.ndarray,
    density: np.ndarray,
    *,
    pre_event_mid_log_price: float,
) -> EventApplication:
    """Place passive liquidity in one interior, noncrossing grid cell."""

    if event.event_type != EVENT_LIMIT_ORDER:
        raise ValueError("apply_limit_order requires a limit_order event")
    x, phi, dx = _state_arrays(grid, density)
    mid = float(pre_event_mid_log_price)
    if not math.isfinite(mid):
        raise ValueError("pre_event_mid_log_price must be finite")
    price = float(event.limit_log_price)
    if (event.side == 1 and price >= mid) or (event.side == -1 and price <= mid):
        raise ValueError("limit order must be passive and noncrossing")
    matches = np.flatnonzero(np.isclose(x, price, rtol=1e-12, atol=1e-14))
    if matches.size != 1:
        raise ValueError("limit_log_price must lie exactly on one grid point")
    index = int(matches[0])
    if index in {0, x.size - 1}:
        raise ValueError("limit placement must use an interior grid cell")
    if (event.side == 1 and x[index] >= mid) or (event.side == -1 and x[index] <= mid):
        raise ValueError("limit placement is on the wrong side of the boundary")

    delta = np.zeros_like(phi)
    delta[index] = event.side * event.quantity / dx
    delta.setflags(write=False)
    return EventApplication(
        event=event,
        pre_event_mid_log_price=mid,
        density_delta=delta,
        affected_grid_indices=(index,),
        placed_quantity=event.quantity,
        filled_quantity=0.0,
        execution_log_price=None,
        semantic_role="passive_liquidity_placement",
    )


def apply_market_order(
    event: OrderEvent,
    grid: np.ndarray,
    density: np.ndarray,
    *,
    pre_event_mid_log_price: float,
    allow_partial: bool = False,
) -> EventApplication:
    """Consume opposing density from the reaction boundary outwards."""

    if event.event_type != EVENT_MARKET_ORDER:
        raise ValueError("apply_market_order requires a market_order event")
    x, phi, dx = _state_arrays(grid, density)
    mid = float(pre_event_mid_log_price)
    if not math.isfinite(mid):
        raise ValueError("pre_event_mid_log_price must be finite")
    if event.side == 1:
        candidates = np.flatnonzero((x > mid) & (phi < 0.0))
    else:
        candidates = np.flatnonzero((x < mid) & (phi > 0.0))[::-1]
    available = float(np.sum(np.abs(phi[candidates])) * dx)
    tolerance = 32.0 * np.finfo(float).eps * max(1.0, event.quantity, available)
    if available + tolerance < event.quantity and not allow_partial:
        raise InsufficientLiquidityError(
            f"requested quantity {event.quantity} exceeds available opposing liquidity {available}"
        )
    target = min(event.quantity, available)
    remaining = target
    delta = np.zeros_like(phi)
    affected: list[int] = []
    weighted_price = 0.0
    for raw_index in candidates:
        index = int(raw_index)
        capacity = abs(float(phi[index])) * dx
        consumed = min(remaining, capacity)
        if consumed <= tolerance:
            continue
        delta[index] = event.side * consumed / dx
        affected.append(index)
        weighted_price += consumed * float(x[index])
        remaining -= consumed
        if remaining <= tolerance:
            remaining = 0.0
            break
    filled = target - remaining
    execution = weighted_price / filled if filled > 0.0 else None
    delta.setflags(write=False)
    return EventApplication(
        event=event,
        pre_event_mid_log_price=mid,
        density_delta=delta,
        affected_grid_indices=tuple(affected),
        placed_quantity=0.0,
        filled_quantity=filled,
        execution_log_price=execution,
        semantic_role="aggressive_opposing_liquidity_consumption",
    )


def apply_order_event(
    event: OrderEvent,
    grid: np.ndarray,
    density: np.ndarray,
    *,
    pre_event_mid_log_price: float,
    allow_partial: bool = False,
) -> EventApplication:
    """Dispatch one declared event without advancing or observing the solver."""

    if event.event_type == EVENT_LIMIT_ORDER:
        if allow_partial:
            raise ValueError("allow_partial applies only to market orders")
        return apply_limit_order(
            event,
            grid,
            density,
            pre_event_mid_log_price=pre_event_mid_log_price,
        )
    return apply_market_order(
        event,
        grid,
        density,
        pre_event_mid_log_price=pre_event_mid_log_price,
        allow_partial=allow_partial,
    )


def ground_truth_aggressor_sign(application: EventApplication) -> int:
    """Return recorded aggressor side; passive events are not trades."""

    return application.event.side if application.is_trade else 0


def quote_midpoint_sign(application: EventApplication) -> int:
    """Classify a trade by execution price relative to the pre-event midpoint."""

    if not application.is_trade or application.execution_log_price is None:
        return 0
    difference = application.execution_log_price - application.pre_event_mid_log_price
    return int(difference > 0.0) - int(difference < 0.0)


def tick_rule_signs(execution_log_prices: Sequence[float]) -> np.ndarray:
    """Return the frozen legacy tick rule: first zero, zero tick carries sign."""

    prices = np.asarray(tuple(execution_log_prices), dtype=float)
    if prices.ndim != 1 or not np.all(np.isfinite(prices)):
        raise ValueError("execution_log_prices must be a finite one-dimensional sequence")
    signs = np.zeros(prices.size, dtype=int)
    previous = 0
    for index in range(1, prices.size):
        difference = prices[index] - prices[index - 1]
        if difference > 0.0:
            previous = 1
        elif difference < 0.0:
            previous = -1
        signs[index] = previous
    signs.setflags(write=False)
    return signs


__all__ = [
    "EVENT_LIMIT_ORDER",
    "EVENT_MARKET_ORDER",
    "EventApplication",
    "InsufficientLiquidityError",
    "OrderEvent",
    "apply_limit_order",
    "apply_market_order",
    "apply_order_event",
    "ground_truth_aggressor_sign",
    "quote_midpoint_sign",
    "tick_rule_signs",
]
