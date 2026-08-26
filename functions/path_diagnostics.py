"""Path-derived autocorrelation and spectral diagnostics."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def increment_autocorrelation(increments: np.ndarray, maximum_lag: int) -> np.ndarray:
    """Pearson autocorrelation of overlapping increment pairs.

    Each positive lag uses the Pearson correlation between the two overlapping
    slices, with each slice centred by its own sample mean. Lag zero is one.
    """

    values = np.asarray(increments, dtype=float)
    if values.ndim != 1 or values.size < 4 or not np.all(np.isfinite(values)):
        raise ValueError("increments must be a finite one-dimensional array")
    if not isinstance(maximum_lag, (int, np.integer)) or not (0 <= maximum_lag <= values.size - 2):
        raise ValueError("maximum_lag must leave at least two increment pairs")
    result = np.empty(maximum_lag + 1, dtype=float)
    result[0] = 1.0
    for lag in range(1, maximum_lag + 1):
        left = values[:-lag]
        right = values[lag:]
        left = left - np.mean(left)
        right = right - np.mean(right)
        scale = float(np.sqrt(np.sum(left * left) * np.sum(right * right)))
        if scale <= 0.0:
            raise ValueError("lagged increment slices must have nonzero variation")
        result[lag] = float(np.sum(left * right) / scale)
    return result


@dataclass(frozen=True)
class WelchDensity:
    frequencies: np.ndarray
    density: np.ndarray
    segments: int
    sample_interval: float
    segment_length: int
    overlap: int


def normalized_welch_density(
    increments: np.ndarray,
    *,
    sample_interval: float,
    segment_length: int,
    overlap: int,
) -> WelchDensity:
    """Return a one-sided Hann Welch density normalized to unit integral."""

    values = np.asarray(increments, dtype=float)
    if values.ndim != 1 or values.size < 4 or not np.all(np.isfinite(values)):
        raise ValueError("increments must be a finite one-dimensional array")
    interval = float(sample_interval)
    if not np.isfinite(interval) or interval <= 0.0:
        raise ValueError("sample_interval must be finite and positive")
    if not isinstance(segment_length, (int, np.integer)) or segment_length < 4 or segment_length > values.size:
        raise ValueError("segment_length must lie between four and the input length")
    if not isinstance(overlap, (int, np.integer)) or not (0 <= overlap < segment_length):
        raise ValueError("overlap must be an integer below segment_length")
    step = segment_length - overlap
    starts = np.arange(0, values.size - segment_length + 1, step, dtype=int)
    if starts.size < 1:
        raise ValueError("the Welch design contains no complete segment")
    window = np.hanning(segment_length)
    window_energy = float(np.sum(window * window))
    densities = []
    for start in starts:
        segment = values[start : start + segment_length]
        segment = (segment - np.mean(segment)) * window
        transform = np.fft.rfft(segment)
        density = interval * np.abs(transform) ** 2 / window_energy
        if segment_length % 2 == 0:
            density[1:-1] *= 2.0
        else:
            density[1:] *= 2.0
        densities.append(density)
    mean_density = np.mean(np.asarray(densities), axis=0)
    frequencies = np.fft.rfftfreq(segment_length, d=interval)
    area = float(np.sum(0.5 * (mean_density[:-1] + mean_density[1:]) * np.diff(frequencies)))
    if not np.isfinite(area) or area <= 0.0:
        raise ValueError("Welch density must have a positive finite integral")
    return WelchDensity(
        frequencies=np.asarray(frequencies),
        density=np.asarray(mean_density / area),
        segments=int(starts.size),
        sample_interval=interval,
        segment_length=int(segment_length),
        overlap=int(overlap),
    )


@dataclass(frozen=True)
class GroupedCurves:
    grouped_values: np.ndarray
    mean: np.ndarray
    standard_deviation: np.ndarray
    standard_error: np.ndarray
    group_ids: np.ndarray


def group_member_curves(values: np.ndarray, group_indices: np.ndarray) -> GroupedCurves:
    """Average member curves within groups before across-group uncertainty."""

    curves = np.asarray(values, dtype=float)
    mapping = np.asarray(group_indices, dtype=int)
    if curves.ndim != 2 or curves.shape[0] < 1 or curves.shape[1] < 1:
        raise ValueError("values must have shape (members, points)")
    if mapping.shape != (curves.shape[0],) or np.any(mapping < 0):
        raise ValueError("group_indices must contain one nonnegative entry per member")
    if not np.all(np.isfinite(curves)):
        raise ValueError("values must be finite")
    groups = np.unique(mapping)
    grouped = np.asarray([np.mean(curves[mapping == group], axis=0) for group in groups])
    mean = np.mean(grouped, axis=0)
    deviation = np.zeros(curves.shape[1]) if groups.size == 1 else np.std(grouped, axis=0, ddof=1)
    return GroupedCurves(
        grouped_values=grouped,
        mean=mean,
        standard_deviation=deviation,
        standard_error=deviation / np.sqrt(float(groups.size)),
        group_ids=groups,
    )


__all__ = [
    "GroupedCurves",
    "WelchDensity",
    "group_member_curves",
    "increment_autocorrelation",
    "normalized_welch_density",
]
