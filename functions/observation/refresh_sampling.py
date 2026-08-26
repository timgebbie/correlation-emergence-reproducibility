"""Explicit previous-refresh time changes and pooled correlation statistics.

The general inverse-clock implementation in :mod:`functions.observation.clocks`
maps calendar time to an operational event count.  The equal-rate Poisson
benchmark used by Toth, Toth and Kertesz instead samples a common uniform-time
price process at each book's latest refresh time.  These are distinct clock
objects and are kept in distinct modules deliberately.

All random uniforms are supplied by the caller.  This module owns no random
number generator, performs no interpolation, and never changes an operational
path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


def _readonly_vector(name: str, values: np.ndarray, *, minimum_size: int) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.ndim != 1 or result.size < minimum_size:
        raise ValueError(f"{name} must be a vector with at least {minimum_size} values")
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be finite")
    result = np.array(result, copy=True)
    result.setflags(write=False)
    return result


def _uniform_grid(name: str, values: np.ndarray) -> np.ndarray:
    result = _readonly_vector(name, values, minimum_size=2)
    increments = np.diff(result)
    if result[0] != 0.0 or np.any(increments <= 0.0) or not np.allclose(
        increments, increments[0], rtol=1e-12, atol=1e-14
    ):
        raise ValueError(f"{name} must be a strictly increasing uniform grid from zero")
    return result


@dataclass(frozen=True)
class PoissonRefreshPath:
    """One realised Poisson refresh process through a declared horizon."""

    event_times: np.ndarray
    waiting_intervals: np.ndarray
    input_rate: float
    stream_id: str
    supported_horizon: float

    def __post_init__(self) -> None:
        events = _readonly_vector("event_times", self.event_times, minimum_size=2)
        waits = _readonly_vector(
            "waiting_intervals", self.waiting_intervals, minimum_size=1
        )
        rate = float(self.input_rate)
        horizon = float(self.supported_horizon)
        identifier = str(self.stream_id).strip()
        if events[0] != 0.0 or np.any(np.diff(events) <= 0.0):
            raise ValueError("event_times must start at zero and be strictly increasing")
        if waits.size != events.size - 1 or not np.allclose(
            np.diff(events), waits, rtol=1e-12, atol=1e-11
        ):
            raise ValueError("waiting_intervals must generate event_times")
        if np.any(waits <= 0.0):
            raise ValueError("waiting_intervals must be strictly positive")
        if not np.isfinite(rate) or rate <= 0.0:
            raise ValueError("input_rate must be finite and positive")
        if not np.isfinite(horizon) or horizon <= 0.0 or events[-1] < horizon:
            raise ValueError("event_times must support the declared positive horizon")
        if not identifier:
            raise ValueError("stream_id must be nonempty")
        object.__setattr__(self, "event_times", events)
        object.__setattr__(self, "waiting_intervals", waits)
        object.__setattr__(self, "input_rate", rate)
        object.__setattr__(self, "stream_id", identifier)
        object.__setattr__(self, "supported_horizon", horizon)

    @property
    def measured_rate(self) -> float:
        """Maximum-likelihood exponential rate from the retained waits."""

        return float(1.0 / np.mean(self.waiting_intervals))


def poisson_refresh_path_from_uniforms(
    uniforms: np.ndarray,
    rate: float,
    horizon: float,
    *,
    stream_id: str,
) -> PoissonRefreshPath:
    """Build a Poisson refresh path from caller-supplied open uniforms."""

    values = _readonly_vector("uniforms", uniforms, minimum_size=1)
    if np.any(values <= 0.0) or np.any(values >= 1.0):
        raise ValueError("uniforms must lie strictly inside the unit interval")
    rate_value = float(rate)
    horizon_value = float(horizon)
    if not np.isfinite(rate_value) or rate_value <= 0.0:
        raise ValueError("rate must be finite and positive")
    if not np.isfinite(horizon_value) or horizon_value <= 0.0:
        raise ValueError("horizon must be finite and positive")
    waits = -np.log1p(-values) / rate_value
    cumulative = np.cumsum(waits)
    crossing = int(np.searchsorted(cumulative, horizon_value, side="left"))
    if crossing >= cumulative.size:
        raise ValueError("supplied uniforms do not support the declared horizon")
    retained_waits = np.asarray(waits[: crossing + 1], dtype=float)
    event_times = np.concatenate(([0.0], np.cumsum(retained_waits)))
    return PoissonRefreshPath(
        event_times=event_times,
        waiting_intervals=retained_waits,
        input_rate=rate_value,
        stream_id=stream_id,
        supported_horizon=horizon_value,
    )


@dataclass(frozen=True)
class PreviousRefreshSubordinationResult:
    """Two operational price paths sampled at book-specific refresh times."""

    query_times: np.ndarray
    prices: np.ndarray
    refresh_times: np.ndarray
    operational_indices: np.ndarray
    stream_ids: tuple[str, str]
    convention: str = "previous_refresh_then_previous_uniform_state"


def subordinate_two_book_previous_refresh(
    operational_times: np.ndarray,
    operational_prices: np.ndarray,
    refresh_paths: Sequence[PoissonRefreshPath],
    query_times: np.ndarray,
) -> PreviousRefreshSubordinationResult:
    """Apply a previous-refresh time change without interpolation."""

    operational = _uniform_grid("operational_times", operational_times)
    prices = np.asarray(operational_prices, dtype=float)
    paths = tuple(refresh_paths)
    queries = _readonly_vector("query_times", query_times, minimum_size=2)
    if prices.shape != (operational.size, 2) or not np.all(np.isfinite(prices)):
        raise ValueError("operational_prices must be finite with shape (states, 2)")
    if len(paths) != 2:
        raise ValueError("refresh_paths must contain one path per book")
    if np.any(np.diff(queries) < 0.0) or queries[0] < 0.0:
        raise ValueError("query_times must be nonnegative and nondecreasing")
    tolerance = 128.0 * np.finfo(float).eps * max(1.0, operational[-1])
    if queries[-1] > operational[-1] + tolerance:
        raise ValueError("query_times exceed the operational price support")
    if any(queries[-1] > path.supported_horizon for path in paths):
        raise ValueError("query_times exceed at least one refresh-path support")

    refresh_times = np.empty((queries.size, 2), dtype=float)
    indices = np.empty((queries.size, 2), dtype=np.int64)
    sampled = np.empty((queries.size, 2), dtype=float)
    for book, path in enumerate(paths):
        event_indices = np.searchsorted(path.event_times, queries, side="right") - 1
        if np.any(event_indices < 0):
            raise RuntimeError("refresh path does not contain an initial event")
        selected_times = path.event_times[event_indices]
        operational_indices = (
            np.searchsorted(operational, selected_times, side="right") - 1
        )
        if np.any(operational_indices < 0) or np.any(
            operational_indices >= operational.size
        ):
            raise RuntimeError("refresh time lies outside the operational grid")
        refresh_times[:, book] = selected_times
        indices[:, book] = operational_indices
        sampled[:, book] = prices[operational_indices, book]

    for array in (refresh_times, indices, sampled):
        array.setflags(write=False)
    return PreviousRefreshSubordinationResult(
        query_times=queries,
        prices=sampled,
        refresh_times=refresh_times,
        operational_indices=indices,
        stream_ids=(paths[0].stream_id, paths[1].stream_id),
    )


def _validated_lags(values: Sequence[int], observations: int) -> np.ndarray:
    items = tuple(values)
    if any(not isinstance(value, (int, np.integer)) for value in items):
        raise ValueError("lags must contain integers")
    normalized = tuple(int(value) for value in items)
    if tuple(sorted(set(normalized))) != normalized:
        raise ValueError("lags must be sorted and unique")
    if not normalized or any(value < 1 or value > observations - 2 for value in normalized):
        raise ValueError("lags must leave at least two return windows")
    return np.asarray(normalized, dtype=int)


def return_component_sums(prices: np.ndarray, lags: Sequence[int]) -> np.ndarray:
    """Return cross-product and two square sums at each aggregation lag."""

    values = np.asarray(prices, dtype=float)
    if values.ndim != 2 or values.shape[1] != 2 or not np.all(np.isfinite(values)):
        raise ValueError("prices must be finite with shape (observations, 2)")
    lag_values = _validated_lags(lags, values.shape[0])
    components = np.empty((lag_values.size, 3), dtype=float)
    for position, lag in enumerate(lag_values):
        returns = values[lag:] - values[:-lag]
        components[position] = (
            np.sum(returns[:, 0] * returns[:, 1]),
            np.sum(returns[:, 0] ** 2),
            np.sum(returns[:, 1] ** 2),
        )
    if np.any(components[:, 1:] <= 0.0):
        raise ValueError("each return series must have nonzero variation")
    components.setflags(write=False)
    return components


def overlap_component_sums(
    operational_indices: np.ndarray,
    lags: Sequence[int],
    *,
    operational_step: float,
) -> np.ndarray:
    """Return exact sampled-interval overlap and two interval-length sums."""

    indices = np.asarray(operational_indices)
    if (
        indices.ndim != 2
        or indices.shape[1] != 2
        or not np.issubdtype(indices.dtype, np.integer)
        or np.any(indices < 0)
        or np.any(np.diff(indices, axis=0) < 0)
    ):
        raise ValueError("operational_indices must be nonnegative monotone integer pairs")
    step = float(operational_step)
    if not np.isfinite(step) or step <= 0.0:
        raise ValueError("operational_step must be finite and positive")
    lag_values = _validated_lags(lags, indices.shape[0])
    components = np.empty((lag_values.size, 3), dtype=float)
    for position, lag in enumerate(lag_values):
        starts = indices[:-lag]
        stops = indices[lag:]
        overlap = np.maximum(
            0,
            np.minimum(stops[:, 0], stops[:, 1])
            - np.maximum(starts[:, 0], starts[:, 1]),
        )
        lengths = stops - starts
        components[position] = (
            step * np.sum(overlap),
            step * np.sum(lengths[:, 0]),
            step * np.sum(lengths[:, 1]),
        )
    if np.any(components[:, 1:] <= 0.0):
        raise ValueError("sampled intervals must have positive total length")
    components.setflags(write=False)
    return components


@dataclass(frozen=True)
class PooledCorrelationSummary:
    """Ratio-of-sums correlation and path-group jackknife uncertainty."""

    correlation: np.ndarray
    jackknife_standard_error: np.ndarray
    leave_one_group_out_correlations: np.ndarray
    pooled_components: np.ndarray


def pooled_correlation_summary(group_components: np.ndarray) -> PooledCorrelationSummary:
    """Pool sufficient statistics and jackknife over operational-path groups."""

    values = np.asarray(group_components, dtype=float)
    if (
        values.ndim != 3
        or values.shape[0] < 2
        or values.shape[1] < 1
        or values.shape[2] != 3
        or not np.all(np.isfinite(values))
    ):
        raise ValueError("group_components must be finite with shape (groups, lags, 3)")
    total = np.sum(values, axis=0)

    def ratio(components: np.ndarray) -> np.ndarray:
        denominator = np.sqrt(components[..., 1] * components[..., 2])
        if np.any(denominator <= 0.0):
            raise ValueError("pooled return variation must be positive")
        return components[..., 0] / denominator

    full = ratio(total)
    leave_one_out = ratio(total[None, ...] - values)
    centre = np.mean(leave_one_out, axis=0)
    groups = values.shape[0]
    standard_error = np.sqrt(
        (float(groups - 1) / float(groups))
        * np.sum((leave_one_out - centre) ** 2, axis=0)
    )
    immutable = []
    for array in (full, standard_error, leave_one_out, total):
        result = np.array(array, copy=True)
        result.setflags(write=False)
        immutable.append(result)
    return PooledCorrelationSummary(*immutable)


__all__ = [
    "PoissonRefreshPath",
    "PooledCorrelationSummary",
    "PreviousRefreshSubordinationResult",
    "overlap_component_sums",
    "poisson_refresh_path_from_uniforms",
    "pooled_correlation_summary",
    "return_component_sums",
    "subordinate_two_book_previous_refresh",
]
