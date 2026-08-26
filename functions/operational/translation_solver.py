"""Simultaneous two-book step for projection-consistent coupling."""

from __future__ import annotations

from dataclasses import replace
from typing import Sequence

import numpy as np

from functions.operational.solver import (
    OperationalSolverSpec,
    OperationalTwoBookStepResult,
    operational_two_book_step,
)
from functions.operational.source import OperationalSource
from functions.operational.translation_coupling import (
    TranslationModeCoupling,
    translation_mode_coupling_density,
)


def operational_translation_two_book_step(
    price_grid: np.ndarray,
    density_histories: np.ndarray,
    previous_prices: Sequence[float],
    sources: Sequence[OperationalSource],
    couplings: Sequence[Sequence[TranslationModeCoupling | None]],
    raw_kernels: Sequence[np.ndarray],
    jump_biases: Sequence[float],
    spec: OperationalSolverSpec,
    *,
    shock_fields: np.ndarray | None = None,
) -> OperationalTwoBookStepResult:
    """Advance both books using one immutable pre-step density snapshot.

    The accepted regularised solver remains frozen.  This distinct entry
    constructs the new coupling fields, passes their total through the
    existing source-increment primitive, and restores the term decomposition
    so external shocks and coupling remain separate observables.
    """

    grid = np.asarray(price_grid, dtype=float)
    histories = np.asarray(density_histories, dtype=float)
    prices = np.asarray(previous_prices, dtype=float)
    if (
        histories.ndim != 3
        or histories.shape[0] != 2
        or histories.shape[1] != grid.size
        or histories.shape[2] < 1
        or not np.all(np.isfinite(histories))
    ):
        raise ValueError("density_histories must have shape (2, grid, history)")
    if prices.shape != (2,) or not np.all(np.isfinite(prices)):
        raise ValueError("previous_prices must contain two finite values")
    if len(couplings) != 2 or any(len(row) != 2 for row in couplings):
        raise ValueError("couplings must define two ordered books")

    if shock_fields is None:
        external = np.zeros((2, grid.size), dtype=float)
    else:
        external = np.asarray(shock_fields, dtype=float)
        if external.shape != (2, grid.size) or not np.all(np.isfinite(external)):
            raise ValueError("shock_fields must have shape (2, grid)")
        external = np.array(external, copy=True)

    density_snapshot = np.array(histories[:, :, -1], copy=True)
    price_snapshot = np.array(prices, copy=True)
    directed = np.zeros((2, 2, grid.size), dtype=float)
    for receiving_book in range(2):
        for other_book in range(2):
            coupling = couplings[receiving_book][other_book]
            if receiving_book == other_book:
                if (
                    coupling is not None
                    and coupling.enabled
                    and coupling.kappa_jk != 0.0
                ):
                    raise ValueError("diagonal self-coupling must be absent or zero")
                continue
            if coupling is not None:
                if not isinstance(coupling, TranslationModeCoupling):
                    raise TypeError("translation solver requires TranslationModeCoupling")
                directed[receiving_book, other_book] = (
                    translation_mode_coupling_density(
                        grid,
                        price_snapshot[receiving_book],
                        price_snapshot[other_book],
                        density_snapshot[receiving_book],
                        coupling,
                    )
                )

    total_coupling = np.sum(directed, axis=1)
    base = operational_two_book_step(
        grid,
        histories,
        price_snapshot,
        sources,
        ((None, None), (None, None)),
        raw_kernels,
        jump_biases,
        spec,
        shock_fields=external + total_coupling,
    )
    net_sources = base.source_fields + total_coupling + external
    return replace(
        base,
        directed_coupling_fields=directed,
        total_coupling_fields=total_coupling,
        shock_fields=external,
        net_sources=net_sources,
    )


__all__ = ["operational_translation_two_book_step"]
