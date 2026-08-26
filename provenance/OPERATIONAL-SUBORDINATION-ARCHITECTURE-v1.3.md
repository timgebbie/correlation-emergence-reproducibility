# Operational-time and subordination architecture — `v1.3.3`

## Accepted decision

The corrected model evolves each order book on a fixed spatial grid and a
uniform operational-time grid,

```text
x_i = x_min + i*Delta x,       u_n = n*Delta u.
```

Random calendar waiting times are not numerical step sizes. They do not enter
the density recurrence, source accumulation, cancellation survival, spatial
transport, reaction-boundary extraction or book interaction.

After the operational paths have been completed, each book receives an
explicit clock `T_j(u)` and inverse clock

```text
E_j(t) = inf{u : T_j(u) > t}.
```

Calendar prices are then constructed pathwise as

```text
P_j(t) = p_j(E_j(t)).
```

Calendar observations may consequently be irregular. The essential rule is
that this irregularity is an observation-layer output and never a dynamics
mesh. This is the target separation in Angstmann--Gebbie rather than a repair
of the legacy nonuniform-step route.

## Required invariants

1. Replacing a clock while holding an operational path fixed must leave that
   operational path bitwise unchanged.
2. An identity clock must recover the corresponding operational path on the
   common grid.
3. Two books may use distinct clock paths even when their clock-law parameters
   are equal.
4. Clock seeds, clock paths and supported calendar horizons must be explicit
   provenance, not hidden inside a book constructor.
5. Subordination must define its endpoint and previous-state convention and
   must not extrapolate beyond clock support.
6. Calendar estimators must consume timestamps or an explicitly constructed
   common calendar grid. Raw operational indices cannot be presented as
   calendar time.
7. Boundary-response experiments and clock experiments must be independently
   switchable so their effects can be attributed separately.

## Implementation boundary

The legacy and target implementations must be physically separate. The target
layout is:

```text
functions/
    legacy/          frozen Julia-conformity source, coupling, memory and driver
    operational/     target source, thick coupling, memory, initialization,
                     boundary, innovations and uniform-grid solver
    observation/     clocks, inverse clocks, subordination and estimators
```

Existing flat `legacy_*` files remain valid during the transition and must not
be rewritten merely to obtain this directory layout. New corrected components
enter only under the target boundary. A single routine with a legacy/target
mode flag is not the intended final design because it permits accidental mixed
semantics.

Tests follow the same separation. Cross-imports from target modules into
legacy modules are prohibited, except in explicitly named comparison tests.

## Version allocation

- `v1.3.4`: corrected source, regularised thick-boundary coupling, raw-memory
  single-survival recurrence, simultaneous initialization and burn-in tests;
- `v1.3.5`: isolated innovation tractability and conformity, including one
  application of `sigma`, explicit cross-book operational dependence and
  Stage 3 closure;
- `v1.4.x`: assemble and verify the uniform operational-time solver;
- `v1.5.x`: construct book-specific clocks, explicit subordination and
  timestamp-aware estimators;
- `v1.6.x`: separate two-clock effects from boundary-response effects.
- `v1.7.x`: complete paired scientific verification and publication outputs.

Items accepted for `v1.3.4` are the source, coupling, cancellation and
initialization corrections. The innovation convention remains provisional
until its isolated tractability gate is accepted.

Stage: 3 — architecture decision within the port-correctness audit

Status: accepted at `v1.3.3`; no target dynamics implemented

## Implementation allocation refinement

Stage 4 subsequently implemented and accepted the uniform operational solver
through `v1.4.3`. Stage 5 is now split into `v1.5.0` for explicit clock paths,
the finite-grid inverse and pathwise subordination; `v1.5.1` for stochastic
two-book clock ensembles; and `v1.5.2` for timestamp-aware calendar estimators
and Stage 5 closure. This refinement preserves the accepted architecture and
prevents clock-law generation, path evaluation and statistical measurement
from being collapsed into one routine.
