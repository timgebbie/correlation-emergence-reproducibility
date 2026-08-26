"""Projection-consistent coupling of current reaction-front translation modes."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


def _finite(name: str, value: float) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _uniform_grid(price_grid: np.ndarray) -> np.ndarray:
    grid = np.asarray(price_grid, dtype=float)
    if grid.ndim != 1 or grid.size < 3 or not np.all(np.isfinite(grid)):
        raise ValueError("price_grid must be a finite vector of at least three points")
    differences = np.diff(grid)
    if np.any(differences <= 0.0) or not np.allclose(
        differences, differences[0], rtol=1e-12, atol=1e-14
    ):
        raise ValueError("price_grid must be strictly increasing and uniform")
    return grid


@dataclass(frozen=True)
class TranslationModeCoupling:
    """Ordered response-rate parameter for one receiving-book coupling."""

    kappa_jk: float
    enabled: bool = True

    def __post_init__(self) -> None:
        if _finite("kappa_jk", self.kappa_jk) < 0.0:
            raise ValueError("kappa_jk must be nonnegative")


def current_front_translation_mode(
    price_grid: np.ndarray,
    receiving_density: np.ndarray,
) -> np.ndarray:
    """Return ``v=-partial_x(phi_current)`` with zero outer source values."""

    grid = _uniform_grid(price_grid)
    density = np.asarray(receiving_density, dtype=float)
    if density.shape != grid.shape or not np.all(np.isfinite(density)):
        raise ValueError("receiving_density must be finite and match price_grid")
    mode = -np.gradient(density, grid, edge_order=2)
    mode = np.asarray(mode, dtype=float)
    mode[[0, -1]] = 0.0
    return mode


def translation_mode_coupling_density(
    price_grid: np.ndarray,
    own_boundary: float,
    other_boundary: float,
    receiving_density: np.ndarray,
    coupling: TranslationModeCoupling,
) -> np.ndarray:
    """Return ``ell_T=-kappa_jk*(p_j-p_k)*v_j`` on the fixed grid."""

    own = _finite("own_boundary", own_boundary)
    other = _finite("other_boundary", other_boundary)
    mode = current_front_translation_mode(price_grid, receiving_density)
    if not coupling.enabled or coupling.kappa_jk == 0.0:
        return np.zeros_like(mode)
    return -coupling.kappa_jk * (own - other) * mode


__all__ = [
    "TranslationModeCoupling",
    "current_front_translation_mode",
    "translation_mode_coupling_density",
]
