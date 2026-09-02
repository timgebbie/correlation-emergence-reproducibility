"""Registered transformations for the v2.1.0 stylised-facts recovery."""

from __future__ import annotations

from statistics import NormalDist

import numpy as np

from functions.path_diagnostics import increment_autocorrelation


def standardize_sample(values: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Standardize a finite sample with its mean and sample standard deviation."""

    sample = np.asarray(values, dtype=float)
    if sample.ndim != 1 or sample.size < 2 or not np.all(np.isfinite(sample)):
        raise ValueError("values must be a finite one-dimensional sample")
    mean = float(np.mean(sample))
    standard_deviation = float(np.std(sample, ddof=1))
    if standard_deviation <= 0.0:
        raise ValueError("sample standard deviation must be positive")
    return (sample - mean) / standard_deviation, mean, standard_deviation


def fixed_histogram(
    standardized: np.ndarray,
    *,
    lower: float,
    upper: float,
    bins: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return a fixed-support density histogram and standard-normal reference."""

    values = np.asarray(standardized, dtype=float)
    if values.ndim != 1 or bins < 2 or not lower < upper:
        raise ValueError("invalid fixed histogram design")
    edges = np.linspace(float(lower), float(upper), int(bins) + 1)
    if float(np.min(values)) < edges[0] or float(np.max(values)) > edges[-1]:
        raise ValueError("standardized return lies outside fixed histogram support")
    counts, _ = np.histogram(values, bins=edges)
    width = float(edges[1] - edges[0])
    density = counts.astype(float) / (values.size * width)
    centres = 0.5 * (edges[:-1] + edges[1:])
    normal = np.exp(-0.5 * centres**2) / np.sqrt(2.0 * np.pi)
    return edges, centres, density, normal


def fixed_normal_qq(
    standardized: np.ndarray,
    *,
    lower_probability: float,
    upper_probability: float,
    count: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return registered probabilities, normal quantiles, and sample quantiles."""

    values = np.asarray(standardized, dtype=float)
    if not 0.0 < lower_probability < upper_probability < 1.0 or count < 3:
        raise ValueError("invalid QQ design")
    probabilities = np.linspace(lower_probability, upper_probability, count)
    normal = np.asarray([NormalDist().inv_cdf(float(p)) for p in probabilities])
    sample = np.quantile(values, probabilities, method="linear")
    return probabilities, normal, np.asarray(sample)


def member_autocorrelations(series: np.ndarray, maximum_lag: int) -> np.ndarray:
    """Compute an ACF for every path and book in a ``(path,time,book)`` array."""

    values = np.asarray(series, dtype=float)
    if values.ndim != 3 or values.shape[2] != 2:
        raise ValueError("series must have shape (paths, observations, two books)")
    result = np.empty((values.shape[0], values.shape[2], maximum_lag + 1))
    for path in range(values.shape[0]):
        for book in range(values.shape[2]):
            result[path, book] = increment_autocorrelation(
                values[path, :, book], maximum_lag
            )
    return result


def aggregate_book_members(curves: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Average books within path, then report mean and standard error across paths."""

    values = np.asarray(curves, dtype=float)
    if values.ndim != 3 or values.shape[1] != 2 or values.shape[0] < 2:
        raise ValueError("curves must have shape (paths, two books, points)")
    path_curves = np.mean(values, axis=1)
    mean = np.mean(path_curves, axis=0)
    standard_error = np.std(path_curves, axis=0, ddof=1) / np.sqrt(path_curves.shape[0])
    return path_curves, mean, standard_error


def histogram_total_variation(
    first_density: np.ndarray,
    second_density: np.ndarray,
    bin_width: float,
) -> float:
    """Integrated total-variation distance for two equal-bin densities."""

    first = np.asarray(first_density, dtype=float)
    second = np.asarray(second_density, dtype=float)
    if first.shape != second.shape or first.ndim != 1 or bin_width <= 0.0:
        raise ValueError("histograms must have the same one-dimensional support")
    return float(0.5 * bin_width * np.sum(np.abs(first - second)))


def curve_difference(first: np.ndarray, second: np.ndarray) -> tuple[float, float]:
    """Return RMSE and maximum absolute difference for equal-shape curves."""

    difference = np.asarray(first, dtype=float) - np.asarray(second, dtype=float)
    if difference.ndim != 1:
        raise ValueError("curves must be one-dimensional")
    return float(np.sqrt(np.mean(difference**2))), float(np.max(np.abs(difference)))


__all__ = [
    "aggregate_book_members",
    "curve_difference",
    "fixed_histogram",
    "fixed_normal_qq",
    "histogram_total_variation",
    "member_autocorrelations",
    "standardize_sample",
]
