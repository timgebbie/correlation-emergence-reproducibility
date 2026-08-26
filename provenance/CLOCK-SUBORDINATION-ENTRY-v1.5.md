# Clock and subordination entry gate — `v1.5.0`

## Purpose

This gate implements the first observation-layer boundary after acceptance of
the uniform operational solver. It does not modify the density dynamics,
reaction-boundary rule, operational innovations or accepted Stage 4 paths.

For each book `j`, the input is one realised clock path on the operational
lattice,

```text
u_n = n*Delta u,                 T_j(u_0) = 0,
T_j(u_n) = sum_{k=1}^n Delta T_{j,k},   Delta T_{j,k} > 0.
```

The clock law, stream identifier, optional generating seed and complete
realised intervals are explicit provenance. The intervals are authoritative;
the observation module owns no random-number generator.

## Continuous theory and finite stored-grid convention

Angstmann--Gebbie define the inverse clock and calendar price by

```text
E_j(t) = inf{u >= 0 : T_j(u) > t},
P_j(t) = p_j(E_j(t)).
```

A computed operational path is available only at stored nodes `u_n`. This gate
therefore declares the discrete, left-continuous observation index

```text
n_j(t) = max{n : T_j(u_n) <= t},
P_j^Delta(t) = p_{j,n_j(t)}.
```

This is the previous completed operational state. It is a finite-grid
step-function approximation to the theoretical inverse, not an assertion that
the two definitions coincide pointwise at finite resolution. Its useful
numerical properties are explicit: a query exactly at `T_j(u_n)` selects state
`n`, and an identity clock selects every stored state exactly.

No state interpolation is performed. Queries before zero or beyond the
realised clock horizon are rejected rather than extrapolated. Calendar query
times must be nondecreasing; repeated query times are allowed.

The present clock constructor requires strictly positive realised intervals,
so each stored clock path is strictly increasing. General nondecreasing clocks
with flat stored intervals are outside this entry gate.

## Software boundary

```text
functions/observation/clocks.py
    validated immutable book-clock paths and discrete inverse evaluation

functions/observation/subordination.py
    generic stored-field evaluation and the two-book price map
```

The two-book map accepts one explicit clock per book. Both clocks must refer to
the same uniform operational grid, but their realised calendar paths and
supported horizons may differ. The common calendar query grid must lie inside
both supports.

Clock replacement cannot mutate the operational array. Consequently the same
accepted operational path can be evaluated under an identity clock, two
distinct clocks, or a clock swap without rerunning the density solver. This is
the required separation between boundary response and observation timing.

## Deterministic evidence

`config/config-v1.5.json` declares a nine-state operational fixture, a common
calendar query grid and two distinct book-clock paths. The clocks have the same
mean waiting interval but different realised sequences, stream identifiers and
seed provenance.

`scripts/16_run_clock_subordination_checks.py` writes:

- `diagnostics/clock-subordination-checks-v1.5.csv` — 15 contract checks;
- `outputs/clock-subordination-fixture-v1.5.csv` — 52 identity and
  book-specific calendar evaluations.

The regression suite adds 13 tests covering validation, immutable input
copies, identity recovery, the exact-node and endpoint rules, no
extrapolation, arbitrary stored fields, distinct two-book inverses, public
constructor validation and physical separation from legacy/operational code
and RNG/interpolation calls.

Gate verification: the 191-entry file manifest, all 15 generated entry checks
and the complete 203-test route pass from a fresh extraction.

## Scope and next gates

This gate provides deterministic clock paths and the numerical subordination
primitive only. It does not claim a calibrated waiting-time law, draw a
stochastic clock ensemble, compute a calendar-time Epps estimator, relabel a
density impulse as a trade, or generate the final two-clock Figure 5.

- `v1.5.1`: generate and retain stochastic two-book clock ensembles under
  declared laws and independent or controlled clock dependence;
- `v1.5.2`: add timestamp-aware calendar estimators, complete the subordinated
  Figure 5 comparison and close Stage 5;
- `v1.6.x`: hold operational dynamics or clocks fixed in paired experiments
  that separate clock effects from reaction-boundary response effects.

Stage: 5 — explicit calendar-time subordination entry (`v1.5.0`)

Status: accepted at `v1.5.0`; stochastic clock ensembles open at `v1.5.1`
