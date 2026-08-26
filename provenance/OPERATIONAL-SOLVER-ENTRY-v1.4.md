# Uniform operational-solver entry — `v1.4.0`

## Scope

This checkpoint composes the accepted source, coupling, memory, initialization
and innovation policies for one simultaneous two-book step. It establishes the
fixed-grid boundary contract before a rolling path is written.

It does not construct random inputs, execute burn-in, create a complete path,
build a clock, subordinate a field or estimate calendar-time correlation.

## Outer spatial boundary

The finite lit-book domain uses

```text
phi(x_min,u) = phi(x_max,u) = 0.
```

For every stored history, the left and right neighbours are ordinary adjacent
fixed-grid values with zero ghosts outside the domain. After the recurrence,
the two endpoint values are set to zero exactly. The resulting outer-boundary
correction is returned as a separate term so the complete update remains
auditable.

This replaces the legacy endpoint repetition. Domain-size convergence is not
claimed at v1.4.0; it is a required v1.4.2 test.

## Reaction boundary

All simple reaction-boundary candidates are identified globally:

- an interior exact grid zero is accepted only when its two neighbours have
  opposite signs;
- an off-grid zero is obtained by linear interpolation across two adjacent
  values with strictly opposite signs;
- endpoint zeros are not treated as reaction prices; and
- a minimum absolute slope may be imposed to reject flat roots.

The default scientific assumption is one unique simple zero. A path may use
`nearest_previous` when several candidates occur, but only if one candidate is
uniquely closest to the previous reaction boundary. A distance tie fails. The
result records the bracket, slope, total candidate count and distance to the
outer domain. This resolves the legacy one-cell index-seed error without
silently selecting an arbitrary root.

## Simultaneous operational step

For book `j`, the step consumes a fixed history `phi_j(x_i,u_m)`, raw Sibuya
kernel, externally supplied jump bias `F_j`, and an external shock field. Both
book sources and both ordered-pair couplings are first constructed from the
same immutable price snapshot `(p_1(u_n),p_2(u_n))`. Each book is then advanced
with the accepted single-survival recurrence on the same `Delta u`.

The returned decomposition contains

```text
raw density
  = history transport
  + previous-state survival
  + Delta u * (source + coupling + shock),

bounded density
  = raw density + explicit outer-boundary correction.
```

No realised calendar interval or effective spatial displacement is accepted by
the API. Operational irregularity therefore cannot enter the numerical step.

## Independent fixed-point check

For `alpha_u=1`, zero cancellation, zero spread, centred forcing and

```text
Delta u = r*Delta x^2/(2*D),
```

an independently solved Dirichlet stationary state satisfies

```text
D*phi_xx + q = 0.
```

The assembled update returns this state to within the declared floating-point
tolerance. This checks the source, neighbour orientation, transport weights,
uniform increment and outer boundary together rather than by self-comparison
of one expression.

## Evidence

Run:

```bash
python scripts/12_run_operational_solver_entry_checks.py
python -m unittest tests.test_operational_solver_entry -v
```

Eight generated checks cover exact, interpolated and multiple-root boundary
selection, Dirichlet ghosts, the common operational increment, the stationary
fixed point, exact endpoint values and the boundary-correction decomposition.
Fourteen tests also cover tie rejection, near-edge exposure, immutable
two-book prices, external shocks, validation and layer separation.

## Stage 4 sequence

- `v1.4.0`: boundary and simultaneous one-step contract;
- `v1.4.1`: rolling path, finite memory storage and burn-in execution;
- `v1.4.2`: grid, domain, history-cutoff and reaction-boundary robustness;
- `v1.4.3`: complete operational ensembles, operational Figure/shock targets,
  effective boundary-price correlation and Stage 4 closure.

Book-specific clocks and explicit subordination begin only at `v1.5.0`.

Stage: 4 — uniform operational-time solver entry (`v1.4.0`)

Science status: boundary and one-step implementation accepted

Acceptance status: 151-entry manifest, eight generated checks and complete
157-test route passed from a fresh extraction

Next decision: assemble the rolling operational path and execute the declared
burn-in policy at `v1.4.1`
