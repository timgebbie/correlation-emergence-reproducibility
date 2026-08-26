"""Explicit book-clock paths and their finite-grid inverse convention."""

from __future__ import annotations

from dataclasses import dataclass

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


def _uniform_operational_times(values: np.ndarray) -> np.ndarray:
    times = _readonly_vector("operational_times", values, minimum_size=2)
    increments = np.diff(times)
    if times[0] != 0.0:
        raise ValueError("operational_times must start at zero")
    if np.any(increments <= 0.0) or not np.allclose(
        increments, increments[0], rtol=1e-12, atol=1e-14
    ):
        raise ValueError("operational_times must be strictly increasing and uniform")
    return times


def _stream_id(value: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError("stream_id must be a nonempty provenance identifier")
    return result


@dataclass(frozen=True)
class BookClockPath:
    """One book-specific map ``T_j(u_n)`` on the operational lattice."""

    operational_times: np.ndarray
    calendar_times: np.ndarray
    calendar_intervals: np.ndarray
    law: str
    stream_id: str
    seed: int | None
    inverse_convention: str = "previous_completed_operational_state"

    def __post_init__(self) -> None:
        operational = _uniform_operational_times(self.operational_times)
        calendar = _readonly_vector(
            "calendar_times", self.calendar_times, minimum_size=2
        )
        intervals = _readonly_vector(
            "calendar_intervals", self.calendar_intervals, minimum_size=1
        )
        if calendar.size != operational.size:
            raise ValueError("calendar_times must contain one value per operational state")
        if intervals.size != operational.size - 1:
            raise ValueError("calendar_intervals must contain one value per operational step")
        if calendar[0] != 0.0 or np.any(np.diff(calendar) <= 0.0):
            raise ValueError("calendar_times must start at zero and be strictly increasing")
        if np.any(intervals <= 0.0):
            raise ValueError("calendar_intervals must be strictly positive")
        constructed = np.concatenate(([0.0], np.cumsum(intervals)))
        if not np.array_equal(calendar, constructed):
            raise ValueError("calendar_times must be the cumulative calendar_intervals")
        law_name = str(self.law).strip()
        if not law_name:
            raise ValueError("law must be a nonempty declared clock-law name")
        identifier = _stream_id(self.stream_id)
        if self.seed is not None and (
            not isinstance(self.seed, int) or isinstance(self.seed, bool)
        ):
            raise ValueError("seed must be an integer or None")
        if self.inverse_convention != "previous_completed_operational_state":
            raise ValueError("unsupported finite-grid inverse convention")
        object.__setattr__(self, "operational_times", operational)
        object.__setattr__(self, "calendar_times", calendar)
        object.__setattr__(self, "calendar_intervals", intervals)
        object.__setattr__(self, "law", law_name)
        object.__setattr__(self, "stream_id", identifier)

    @property
    def states(self) -> int:
        return int(self.operational_times.size)

    @property
    def supported_calendar_horizon(self) -> float:
        return float(self.calendar_times[-1])

    @property
    def delta_u(self) -> float:
        return float(self.operational_times[1] - self.operational_times[0])


@dataclass(frozen=True)
class InverseClockResult:
    """Discrete inverse-clock evaluations with an explicit state convention."""

    calendar_times: np.ndarray
    operational_indices: np.ndarray
    operational_times: np.ndarray
    convention: str
    supported_calendar_horizon: float


def book_clock_from_intervals(
    operational_times: np.ndarray,
    calendar_intervals: np.ndarray,
    *,
    law: str,
    stream_id: str,
    seed: int | None = None,
) -> BookClockPath:
    """Build ``T_j`` from caller-supplied positive calendar increments.

    This function owns no random generator. A caller may record the seed used
    to construct the supplied increments, but the intervals themselves are the
    authoritative clock path.
    """

    operational = _uniform_operational_times(operational_times)
    intervals = _readonly_vector(
        "calendar_intervals", calendar_intervals, minimum_size=1
    )
    if intervals.size != operational.size - 1:
        raise ValueError("calendar_intervals must contain one value per operational step")
    if np.any(intervals <= 0.0):
        raise ValueError("calendar_intervals must be strictly positive")
    law_name = str(law).strip()
    if not law_name:
        raise ValueError("law must be a nonempty declared clock-law name")
    identifier = _stream_id(stream_id)
    if seed is not None and (not isinstance(seed, int) or isinstance(seed, bool)):
        raise ValueError("seed must be an integer or None")
    calendar = np.concatenate(([0.0], np.cumsum(intervals)))
    if not np.all(np.isfinite(calendar)):
        raise ValueError("calendar clock overflowed its finite support")
    calendar.setflags(write=False)
    return BookClockPath(
        operational_times=operational,
        calendar_times=calendar,
        calendar_intervals=intervals,
        law=law_name,
        stream_id=identifier,
        seed=seed,
    )


def identity_book_clock(
    operational_times: np.ndarray,
    *,
    stream_id: str,
) -> BookClockPath:
    """Return the deterministic identity map ``T(u)=u``."""

    operational = _uniform_operational_times(operational_times)
    return book_clock_from_intervals(
        operational,
        np.diff(operational),
        law="identity",
        stream_id=stream_id,
        seed=None,
    )


def inverse_clock_previous_state(
    clock: BookClockPath,
    calendar_times: np.ndarray,
) -> InverseClockResult:
    """Evaluate the finite-grid inverse without interpolation or extrapolation.

    The paper uses ``E(t)=inf{u:T(u)>t}``. At finite resolution, stored states
    exist only at operational nodes. The declared approximation therefore uses
    the latest completed node

    ``n(t)=max{n:T(u_n)<=t}``.

    Exact clock nodes map to their same-index operational states, so an identity
    clock recovers every stored operational state exactly.
    """

    queries = _readonly_vector("calendar_times", calendar_times, minimum_size=1)
    if np.any(np.diff(queries) < 0.0):
        raise ValueError("calendar_times must be nondecreasing")
    tolerance = 16.0 * np.finfo(float).eps * max(
        1.0, clock.supported_calendar_horizon
    )
    if queries[0] < -tolerance:
        raise ValueError("calendar_times must not precede zero")
    if queries[-1] > clock.supported_calendar_horizon + tolerance:
        raise ValueError("calendar_times exceed the clock's supported horizon")
    clipped = np.clip(queries, 0.0, clock.supported_calendar_horizon)
    indices = np.searchsorted(clock.calendar_times, clipped, side="right") - 1
    indices = np.clip(indices, 0, clock.states - 1).astype(np.int64)
    indices.setflags(write=False)
    inverse_times = np.asarray(clock.operational_times[indices], dtype=float)
    inverse_times.setflags(write=False)
    return InverseClockResult(
        calendar_times=queries,
        operational_indices=indices,
        operational_times=inverse_times,
        convention=clock.inverse_convention,
        supported_calendar_horizon=clock.supported_calendar_horizon,
    )


__all__ = [
    "BookClockPath",
    "InverseClockResult",
    "book_clock_from_intervals",
    "identity_book_clock",
    "inverse_clock_previous_state",
]
