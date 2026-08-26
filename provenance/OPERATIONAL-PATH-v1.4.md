# Rolling operational path — `v1.4.1`

## Scope

This checkpoint repeatedly applies the accepted simultaneous `v1.4.0` step on
one fixed spatial grid and one uniform operational-time grid. The state history
is bounded by the longest supplied raw-memory kernel. Full densities are kept
only at requested snapshot steps; price and boundary diagnostics are retained
for every completed step.

Innovations and shocks are external arrays. The path module owns no random
generator, seed, clock, nonuniform interval, calendar observation or estimator.

## Thickness authority

The target construction is the regularised source in the appendices of the
Angstmann--Gebbie theory paper. For directed spread `z=p_j-p_k`,

```text
W(y,z;epsilon) = 0.5*(1+tanh(y*z/epsilon)),
epsilon = abs(z_ref)*w_ref,
w_epsilon(z) = epsilon/abs(z),  z != 0,
Delta x << w_ref << L_q,j,
L_q,j ~ mu_j^(-1/2).
```

At zero spread, `W` tends to one half and the formal selector width diverges,
but the complete spread-proportional coupling is exactly zero. The path records
the directed spreads and selector widths so this limiting behaviour is visible.

Three scales remain separate:

1. the density-front scale, diagnosed by its zero-crossing slope and curvature;
2. the corrected source-kernel scale `mu^(-1/2)`; and
3. the selector transition width `epsilon/abs(z)`.

None is an explicit bid--ask spread. The Bauer `f(y/g)`, `g*f(y)` deformation
is a preliminary finite-grid construction retained solely in the legacy route.
It is not imported or used by the operational target path.

## Burn-in and storage

For every step, the path measures the relative L2 density change. A burn-in is
accepted only after the declared minimum operational step and the required
number of consecutive changes at or below tolerance. The first accepted step
is retained even if execution continues. An optional mode stops at that step.

The rolling history stores at most `max(len(K_1),len(K_2))` columns. A shorter
book-specific kernel still selects only its own available lags. Requested
density snapshots are copies and do not extend the rolling memory window.

## Evidence

Run:

```bash
python scripts/13_run_operational_path_checks.py
python -m unittest tests.test_operational_path -v
```

The generated checks cover reference-scale regularisation, state-dependent
width, the uniform time grid, stationary pre-shock evolution, burn-in, rolling
memory and external shock timing. Tests additionally cover deterministic input
copying, selective snapshots, initial-boundary validation and layer separation.

Stage: 4 — rolling uniform operational-time path (`v1.4.1`)

Science status: rolling path and thickness diagnostics accepted

Acceptance status: 157-entry manifest, eight generated checks and complete
170-test route passed from a fresh extraction

Next decision: establish the grid, domain, history-cutoff, front-geometry and
thickness-scale robustness gate at `v1.4.2`
