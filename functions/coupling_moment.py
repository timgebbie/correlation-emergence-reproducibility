"""Reaction-boundary first moments and finite-grid representation checks."""

from __future__ import annotations

from math import pi, sqrt

import numpy as np


def _positive_finite(value: float, name: str) -> float:
    value = float(value)
    if not np.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be positive and finite")
    return value


def source_kernel(y: np.ndarray | float, source_amplitude: float, source_width: float) -> np.ndarray | float:
    """Return q(y)=-a*mu*y*exp(-mu*y^2), the active decaying convention."""

    amplitude = _positive_finite(source_amplitude, "source_amplitude")
    width = _positive_finite(source_width, "source_width")
    values = np.asarray(y, dtype=float)
    if np.any(~np.isfinite(values)):
        raise ValueError("y must be finite")
    result = -amplitude * width * values * np.exp(-width * values * values)
    return float(result) if result.ndim == 0 else result


def smooth_selector(
    y: np.ndarray | float,
    directed_spread: float,
    epsilon: float,
    *,
    selector_shift: float = 0.0,
) -> np.ndarray | float:
    """Return W=0.5[1+tanh((y-shift)z/epsilon)]."""

    eps = _positive_finite(epsilon, "epsilon")
    spread = float(directed_spread)
    shift = float(selector_shift)
    if not np.isfinite(spread) or spread == 0.0:
        raise ValueError("directed_spread must be finite and non-zero")
    if not np.isfinite(shift):
        raise ValueError("selector_shift must be finite")
    values = np.asarray(y, dtype=float)
    result = 0.5 * (1.0 + np.tanh((values - shift) * spread / eps))
    return float(result) if result.ndim == 0 else result


def analytic_half_line_moment(source_amplitude: float, source_width: float) -> float:
    """Return M+=-a*sqrt(pi)/(4*sqrt(mu))."""

    amplitude = _positive_finite(source_amplitude, "source_amplitude")
    width = _positive_finite(source_width, "source_width")
    return -amplitude * sqrt(pi) / (4.0 * sqrt(width))


def numerical_continuum_moment(
    source_amplitude: float,
    source_width: float,
    directed_spread: float,
    epsilon: float,
    *,
    domain_halfwidth: float = 8.0,
    points: int = 200_001,
    selector_shift: float = 0.0,
) -> float:
    """Numerically integrate int y*q(y)*W(y,z;epsilon) dy on a finite domain."""

    halfwidth = _positive_finite(domain_halfwidth, "domain_halfwidth")
    if points < 1001 or points % 2 == 0:
        raise ValueError("points must be an odd integer of at least 1001")
    y = np.linspace(-halfwidth, halfwidth, points)
    integrand = y * source_kernel(y, source_amplitude, source_width) * smooth_selector(
        y, directed_spread, epsilon, selector_shift=selector_shift
    )
    return float(np.trapezoid(integrand, y))


def discrete_selected_moment(
    source_amplitude: float,
    source_width: float,
    directed_spread: float,
    epsilon: float,
    lattice_spacing: float,
    domain_halfwidth: float,
    *,
    selector_shift: float = 0.0,
) -> tuple[float, float, int]:
    """Return a rectangle-rule lattice moment, realised halfwidth, and node count.

    The lattice is symmetric about the analytic source centre.  A non-zero
    ``selector_shift`` represents misalignment between that centre and the
    numerically represented side selector.
    """

    dx = _positive_finite(lattice_spacing, "lattice_spacing")
    halfwidth = _positive_finite(domain_halfwidth, "domain_halfwidth")
    cells = max(1, int(round(halfwidth / dx)))
    y = np.arange(-cells, cells + 1, dtype=float) * dx
    weights = smooth_selector(y, directed_spread, epsilon, selector_shift=selector_shift)
    moment = dx * np.sum(y * source_kernel(y, source_amplitude, source_width) * weights)
    return float(moment), float(cells * dx), int(y.size)


def response_rate_single(
    coupling_strength: float,
    source_amplitude: float,
    source_width: float,
    front_slope_abs: float,
    *,
    moment_ratio: float = 1.0,
) -> float:
    """Return kappa_j=gamma*|M+|*|ratio|/|L_j|."""

    gamma_value = _positive_finite(coupling_strength, "coupling_strength")
    slope = _positive_finite(front_slope_abs, "front_slope_abs")
    ratio = float(moment_ratio)
    if not np.isfinite(ratio):
        raise ValueError("moment_ratio must be finite")
    return gamma_value * abs(analytic_half_line_moment(source_amplitude, source_width)) * abs(ratio) / slope


def response_rate_total(books: int = 2, **kwargs: float) -> float:
    """Return the symmetric two-book (or n-book) sum of single-book response rates."""

    if int(books) != books or books < 1:
        raise ValueError("books must be a positive integer")
    return int(books) * response_rate_single(**kwargs)


__all__ = [
    "source_kernel",
    "smooth_selector",
    "analytic_half_line_moment",
    "numerical_continuum_moment",
    "discrete_selected_moment",
    "response_rate_single",
    "response_rate_total",
]
