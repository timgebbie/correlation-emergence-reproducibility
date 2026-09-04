"""Caller-driven Mittag-Leffler renewal clocks for observation subordination.

The operational solver is deliberately absent from this module.  These
functions construct positive waiting intervals for a book-specific observation
process; :mod:`functions.observation.refresh_sampling` subsequently applies the
same previous-refresh map used by the accepted Poisson benchmark.

For ``0 < beta <= 1`` and scale ``tau``, the untempered waiting time ``W`` has

``E[exp(-s W)] = 1 / (1 + (tau s)**beta)``.

For ``beta < 1`` it is generated as ``tau * E**(1/beta) * S_beta``, where ``E``
is unit exponential and ``S_beta`` is a positive stable variable with Laplace
transform ``exp(-s**beta)``.  The tempered law is the exact exponential tilt
with rate ``lambda`` and therefore has transform

``(1 + (tau lambda)**beta) / (1 + (tau (s + lambda))**beta)``.

All uniforms are supplied by the caller.  This module owns no random-number
generator and performs neither interpolation nor operational state updates.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def _open_uniforms(name: str, values: np.ndarray) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.ndim != 1 or result.size < 1 or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be a nonempty finite vector")
    if np.any(result <= 0.0) or np.any(result >= 1.0):
        raise ValueError(f"{name} must lie strictly inside the unit interval")
    result = np.array(result, copy=True)
    result.setflags(write=False)
    return result


def _beta(value: float) -> float:
    result = float(value)
    if not np.isfinite(result) or not 0.0 < result <= 1.0:
        raise ValueError("beta must be finite and lie in (0, 1]")
    return result


def _positive(name: str, value: float) -> float:
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return result


def positive_stable_from_uniforms(
    angle_uniforms: np.ndarray,
    exponential_uniforms: np.ndarray,
    beta: float,
) -> np.ndarray:
    """Return positive stable variates using the Kanter representation.

    The returned variable has Laplace transform ``exp(-s**beta)``.  At
    ``beta=1`` the positive stable law is deterministic at one.
    """

    angles_u = _open_uniforms("angle_uniforms", angle_uniforms)
    exponential_u = _open_uniforms(
        "exponential_uniforms", exponential_uniforms
    )
    if angles_u.shape != exponential_u.shape:
        raise ValueError("positive-stable uniform vectors must have equal shape")
    order = _beta(beta)
    if order == 1.0:
        result = np.ones(angles_u.shape, dtype=float)
    else:
        angle = np.pi * angles_u
        exponential = -np.log(exponential_u)
        first = np.sin(order * angle) / np.sin(angle) ** (1.0 / order)
        second = (
            np.sin((1.0 - order) * angle) / exponential
        ) ** ((1.0 - order) / order)
        result = first * second
    if not np.all(np.isfinite(result)) or np.any(result <= 0.0):
        raise FloatingPointError("positive-stable transform produced invalid values")
    result.setflags(write=False)
    return result


def mittag_leffler_waits_from_uniforms(
    angle_uniforms: np.ndarray,
    stable_exponential_uniforms: np.ndarray,
    mixture_uniforms: np.ndarray,
    *,
    beta: float,
    scale_seconds: float,
) -> np.ndarray:
    """Return Mittag-Leffler renewal waits from three caller-owned streams."""

    mixture_u = _open_uniforms("mixture_uniforms", mixture_uniforms)
    stable = positive_stable_from_uniforms(
        angle_uniforms, stable_exponential_uniforms, beta
    )
    if stable.shape != mixture_u.shape:
        raise ValueError("all Mittag-Leffler uniform vectors must have equal shape")
    order = _beta(beta)
    scale = _positive("scale_seconds", scale_seconds)
    exponential = -np.log(mixture_u)
    waits = scale * exponential ** (1.0 / order) * stable
    if not np.all(np.isfinite(waits)) or np.any(waits <= 0.0):
        raise FloatingPointError("Mittag-Leffler transform produced invalid waits")
    waits.setflags(write=False)
    return waits


def mittag_leffler_wait_laplace(
    s: np.ndarray | float, *, beta: float, scale_seconds: float
) -> np.ndarray:
    """Evaluate the declared untempered waiting-time Laplace transform."""

    values = np.asarray(s, dtype=float)
    if not np.all(np.isfinite(values)) or np.any(values < 0.0):
        raise ValueError("Laplace arguments must be finite and nonnegative")
    order = _beta(beta)
    scale = _positive("scale_seconds", scale_seconds)
    return 1.0 / (1.0 + (scale * values) ** order)


def tempered_mittag_leffler_wait_laplace(
    s: np.ndarray | float,
    *,
    beta: float,
    scale_seconds: float,
    tempering_rate_per_second: float,
) -> np.ndarray:
    """Evaluate the Laplace transform of the exponentially tilted law."""

    values = np.asarray(s, dtype=float)
    if not np.all(np.isfinite(values)) or np.any(values < 0.0):
        raise ValueError("Laplace arguments must be finite and nonnegative")
    order = _beta(beta)
    scale = _positive("scale_seconds", scale_seconds)
    rate = _positive("tempering_rate_per_second", tempering_rate_per_second)
    numerator = 1.0 + (scale * rate) ** order
    denominator = 1.0 + (scale * (values + rate)) ** order
    return numerator / denominator


def tempered_mittag_leffler_mean_wait(
    *, beta: float, scale_seconds: float, tempering_rate_per_second: float
) -> float:
    """Return the finite mean wait of the exponentially tilted law."""

    order = _beta(beta)
    scale = _positive("scale_seconds", scale_seconds)
    rate = _positive("tempering_rate_per_second", tempering_rate_per_second)
    return float(
        order
        * scale**order
        * rate ** (order - 1.0)
        / (1.0 + (scale * rate) ** order)
    )


def tempered_mittag_leffler_waits_from_uniforms(
    angle_uniforms: np.ndarray,
    stable_exponential_uniforms: np.ndarray,
    mixture_uniforms: np.ndarray,
    acceptance_uniforms: np.ndarray,
    *,
    beta: float,
    scale_seconds: float,
    tempering_rate_per_second: float,
) -> np.ndarray:
    """Return accepted waits from exact exponential-tilting rejection sampling."""

    candidates = mittag_leffler_waits_from_uniforms(
        angle_uniforms,
        stable_exponential_uniforms,
        mixture_uniforms,
        beta=beta,
        scale_seconds=scale_seconds,
    )
    acceptance = _open_uniforms("acceptance_uniforms", acceptance_uniforms)
    if candidates.shape != acceptance.shape:
        raise ValueError("candidate and acceptance uniform vectors must have equal shape")
    rate = _positive("tempering_rate_per_second", tempering_rate_per_second)
    retained = np.asarray(candidates[acceptance <= np.exp(-rate * candidates)])
    if retained.size < 1:
        raise ValueError("no tempered Mittag-Leffler candidate was accepted")
    retained.setflags(write=False)
    return retained


@dataclass(frozen=True)
class RenewalRefreshPath:
    """One realised non-Poisson observation renewal process."""

    event_times: np.ndarray
    waiting_intervals: np.ndarray
    law: str
    stream_id: str
    supported_horizon: float
    beta: float
    scale_seconds: float
    tempering_rate_per_second: float | None = None

    def __post_init__(self) -> None:
        events = np.asarray(self.event_times, dtype=float)
        waits = np.asarray(self.waiting_intervals, dtype=float)
        horizon = _positive("supported_horizon", self.supported_horizon)
        order = _beta(self.beta)
        scale = _positive("scale_seconds", self.scale_seconds)
        law_name = str(self.law).strip()
        identifier = str(self.stream_id).strip()
        if events.ndim != 1 or events.size < 2 or events[0] != 0.0:
            raise ValueError("event_times must be a vector starting at zero")
        if waits.ndim != 1 or waits.size != events.size - 1:
            raise ValueError("waiting_intervals must match event_times")
        if not np.all(np.isfinite(events)) or np.any(np.diff(events) <= 0.0):
            raise ValueError("event_times must be finite and strictly increasing")
        if not np.all(np.isfinite(waits)) or np.any(waits <= 0.0):
            raise ValueError("waiting_intervals must be finite and positive")
        if not np.allclose(np.diff(events), waits, rtol=1e-12, atol=1e-10):
            raise ValueError("waiting_intervals must generate event_times")
        if events[-1] < horizon:
            raise ValueError("event_times do not support the declared horizon")
        if not law_name or not identifier:
            raise ValueError("law and stream_id must be nonempty")
        rate = self.tempering_rate_per_second
        if rate is not None:
            rate = _positive("tempering_rate_per_second", rate)
        events = np.array(events, copy=True)
        waits = np.array(waits, copy=True)
        events.setflags(write=False)
        waits.setflags(write=False)
        object.__setattr__(self, "event_times", events)
        object.__setattr__(self, "waiting_intervals", waits)
        object.__setattr__(self, "supported_horizon", horizon)
        object.__setattr__(self, "beta", order)
        object.__setattr__(self, "scale_seconds", scale)
        object.__setattr__(self, "law", law_name)
        object.__setattr__(self, "stream_id", identifier)
        object.__setattr__(self, "tempering_rate_per_second", rate)

    @property
    def realised_mean_wait(self) -> float:
        return float(np.mean(self.waiting_intervals))


def _path_from_waits(
    waits: np.ndarray,
    horizon: float,
    *,
    law: str,
    stream_id: str,
    beta: float,
    scale_seconds: float,
    tempering_rate_per_second: float | None,
) -> RenewalRefreshPath:
    horizon_value = _positive("horizon", horizon)
    cumulative = np.cumsum(np.asarray(waits, dtype=float))
    crossing = int(np.searchsorted(cumulative, horizon_value, side="left"))
    if crossing >= cumulative.size:
        raise ValueError("supplied uniforms do not support the declared horizon")
    retained = np.asarray(waits[: crossing + 1], dtype=float)
    events = np.concatenate(([0.0], np.cumsum(retained)))
    return RenewalRefreshPath(
        event_times=events,
        waiting_intervals=retained,
        law=law,
        stream_id=stream_id,
        supported_horizon=horizon_value,
        beta=beta,
        scale_seconds=scale_seconds,
        tempering_rate_per_second=tempering_rate_per_second,
    )


def mittag_leffler_refresh_path_from_uniforms(
    angle_uniforms: np.ndarray,
    stable_exponential_uniforms: np.ndarray,
    mixture_uniforms: np.ndarray,
    *,
    beta: float,
    scale_seconds: float,
    horizon: float,
    stream_id: str,
) -> RenewalRefreshPath:
    """Build one untempered Mittag-Leffler refresh path."""

    waits = mittag_leffler_waits_from_uniforms(
        angle_uniforms,
        stable_exponential_uniforms,
        mixture_uniforms,
        beta=beta,
        scale_seconds=scale_seconds,
    )
    return _path_from_waits(
        waits,
        horizon,
        law="mittag_leffler_renewal",
        stream_id=stream_id,
        beta=beta,
        scale_seconds=scale_seconds,
        tempering_rate_per_second=None,
    )


def tempered_mittag_leffler_refresh_path_from_uniforms(
    angle_uniforms: np.ndarray,
    stable_exponential_uniforms: np.ndarray,
    mixture_uniforms: np.ndarray,
    acceptance_uniforms: np.ndarray,
    *,
    beta: float,
    scale_seconds: float,
    tempering_rate_per_second: float,
    horizon: float,
    stream_id: str,
) -> RenewalRefreshPath:
    """Build one exponentially tempered Mittag-Leffler refresh path."""

    waits = tempered_mittag_leffler_waits_from_uniforms(
        angle_uniforms,
        stable_exponential_uniforms,
        mixture_uniforms,
        acceptance_uniforms,
        beta=beta,
        scale_seconds=scale_seconds,
        tempering_rate_per_second=tempering_rate_per_second,
    )
    return _path_from_waits(
        waits,
        horizon,
        law="exponentially_tempered_mittag_leffler_renewal",
        stream_id=stream_id,
        beta=beta,
        scale_seconds=scale_seconds,
        tempering_rate_per_second=tempering_rate_per_second,
    )


__all__ = [
    "RenewalRefreshPath",
    "mittag_leffler_refresh_path_from_uniforms",
    "mittag_leffler_wait_laplace",
    "mittag_leffler_waits_from_uniforms",
    "positive_stable_from_uniforms",
    "tempered_mittag_leffler_mean_wait",
    "tempered_mittag_leffler_refresh_path_from_uniforms",
    "tempered_mittag_leffler_wait_laplace",
    "tempered_mittag_leffler_waits_from_uniforms",
]
