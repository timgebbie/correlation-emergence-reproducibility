"""Stable validation of predeclared representative-path choices."""

from __future__ import annotations

import math

import numpy as np


def _distances_and_tolerance(
    values: np.ndarray, distance_tolerance_ulps: int
) -> tuple[np.ndarray, float]:
    sample = np.asarray(values, dtype=float)
    if sample.ndim != 1 or sample.size < 1 or not np.all(np.isfinite(sample)):
        raise ValueError("values must be a nonempty finite vector")
    if isinstance(distance_tolerance_ulps, (bool, np.bool_)) or not isinstance(
        distance_tolerance_ulps, (int, np.integer)
    ):
        raise ValueError("distance_tolerance_ulps must be an integer")
    ulps = int(distance_tolerance_ulps)
    if ulps < 1:
        raise ValueError("distance_tolerance_ulps must be positive")
    median = float(np.median(sample))
    distances = np.abs(sample - median)
    scale = max(1.0, abs(median), float(np.max(np.abs(sample))))
    return distances, ulps * float(np.spacing(scale))


def stable_nearest_median_index(
    values: np.ndarray, *, distance_tolerance_ulps: int = 64
) -> int:
    """Return the lowest index in the roundoff-equivalent nearest class."""

    distances, tolerance = _distances_and_tolerance(
        values, distance_tolerance_ulps
    )
    minimum = float(np.min(distances))
    matches = np.flatnonzero(distances <= minimum + tolerance)
    return int(matches[0])


def validated_predeclared_nearest_median_index(
    values: np.ndarray,
    *,
    predeclared_index: int,
    distance_tolerance_ulps: int = 64,
) -> int:
    """Return a predeclared index only when it is nearest-median up to roundoff.

    Even antithetic ensembles can contain several paths whose distances from
    the cross-path median are mathematically equal.  Raw floating-point
    ordering can then change the selected path across otherwise equivalent
    runs.  This function preserves the declared path while independently
    checking that its distance is in the minimum-distance class within a small
    ULP-scaled tolerance.
    """

    sample = np.asarray(values, dtype=float)
    distances, tolerance = _distances_and_tolerance(
        sample, distance_tolerance_ulps
    )
    if isinstance(predeclared_index, (bool, np.bool_)) or not isinstance(
        predeclared_index, (int, np.integer)
    ):
        raise ValueError("predeclared_index must be an integer")
    index = int(predeclared_index)
    if not 0 <= index < sample.size:
        raise ValueError("predeclared_index lies outside values")
    minimum = float(np.min(distances))
    if not math.isclose(
        float(distances[index]), minimum, rel_tol=0.0, abs_tol=tolerance
    ):
        raise ValueError(
            "predeclared representative path is outside the nearest-median "
            f"class: distance={distances[index]:.17g}, minimum={minimum:.17g}, "
            f"tolerance={tolerance:.17g}"
        )
    return index


__all__ = [
    "stable_nearest_median_index",
    "validated_predeclared_nearest_median_index",
]
