# Target operational-dynamics prerequisites — `v1.3.4`–`v1.3.5`

## Scope

This record consolidates the target primitives and innovation policy required
before the fixed-grid operational solver is assembled. The implementation is
physically separate under `functions/operational/`; no target module imports a
`legacy_*` implementation. Legacy outputs remain the accepted statistical
recovery baseline.

Neither checkpoint implements clocks, subordination, calendar observations,
reaction-boundary extraction or a complete path driver.

## Corrected source

The target source is

```text
q_j(y) = -lambda_j*mu_j*y*exp(-mu_j*y^2),
        y = x-p_j.
```

It is evaluated directly on the fixed spatial grid without the legacy
periodic displacement. Its positive-half first moment is

```text
M_j^+ = -lambda_j*sqrt(pi)/(4*sqrt(mu_j)).
```

## Regularised thick coupling

For the ordered pair from book `k` into book `j`,

```text
z_jk = p_j-p_k,
W(y,z;epsilon) = 0.5*(1+tanh(y*z/epsilon)),
ell_jk = gamma_jk*z_jk*q_j(y)*W(y,z_jk;epsilon).
```

The target field is bounded by `gamma*abs(z)*abs(q)`, is exactly zero at equal
book prices, and reverses its raw first moment when the spread reverses. On a
uniform grid the checked correspondence is

```text
Delta x * sum_i y_i*ell_i = gamma_jk*M_j^+*z_jk
```

up to the declared domain and lattice error.

## Raw memory and one survival factor

The Sibuya kernel stores raw coefficients only. For target index `n`, history
index `m` and lag `l=n-m`, transport is weighted by

```text
K_l * exp[-nu*(l-1)*Delta u].
```

The most recent history has zero elapsed operational time. The separate
survivor term is `exp(-nu*Delta u)*phi_(n-1)`. Neighbour histories are supplied
explicitly so the memory primitive does not hide the final spatial boundary
condition.

## Simultaneous initialization and burn-in

All initial book prices are copied into one immutable snapshot. Every
single-book source and ordered-pair field is computed from that snapshot before
any stationary solve. Dirichlet-zero and Neumann-zero-flux reference systems
are explicitly named; the final boundary policy remains a Stage 4 decision.

Burn-in is specified by a minimum operational-step count, relative state-change
tolerance, and required number of consecutive converged checks. The complete
solver must execute the policy and record the achieved stopping diagnostic.

## Innovation scale and dependence

The target innovation boundary consumes externally supplied standard arrays
with final dimension two. It does not create an RNG or own a seed. For
independent standard inputs `Z_1,Z_2` and declared microscopic operational
correlation `rho_F`,

```text
eta_1 = Z_1,
eta_2 = rho_F*Z_1 + sqrt(1-rho_F^2)*Z_2,
V_j = sigma_j*eta_j.
```

Thus each `sigma_j` is applied exactly once. The cases `rho_F=0`, `rho_F=1`
and `rho_F=-1` give independent, shared and antithetic forcing. Intermediate
values give correlated forcing. Independent forcing is the default for the
correlation-emergence experiment so that cross-book dependence is transmitted
by the pair coupling rather than hidden in the innovations.

The DTRW jump bias is

```text
F_j = r*tanh(V_j*Delta x/(4*D_j)),
P_stay = 1-r,
P_plus = (r+F_j)/2,
P_minus = (r-F_j)/2.
```

This is the difference of the legacy logistic left/right weights, but omits
the erroneous second application of `sigma`. The hyperbolic-tangent map already
enforces `abs(F_j)<=r`; no nonuniform calendar interval or hidden velocity cap
enters the target innovation primitive.

The microscopic forcing correlation `rho_F` is not automatically the
effective Brownian reaction-boundary correlation `rho_u` used in the paper's
local subordination benchmark. The complete nonlinear operational solver may
filter it through the density fields and moving boundaries. The effective
price-path correlation must therefore be measured from completed operational
paths. This keeps the microscopic simulation claim distinct from the reduced
log-price approximation.

## Evidence

Run:

```bash
python scripts/10_run_operational_primitive_checks.py
python scripts/11_run_operational_innovation_checks.py
python -m unittest tests.test_operational_primitives tests.test_operational_innovations -v
```

The primitive CSV contains ten checks. The innovation CSV contains eight checks
for single scaling, independent and correlated covariance, shared and
antithetic endpoints, bounded bias and normalized weights. The tests additionally
cover validation, deterministic external inputs, boundary cases and the
no-target-RNG rule.

## Remaining decisions

- PA-10 reaction-boundary indexing and PA-19 final spatial boundary: Stage 4;
- complete fixed-grid uniform-operational-time path assembly: Stage 4;
- book clocks and explicit subordination: Stage 5;
- timestamp-aware calendar estimators: subsequent observation gate;
- effective operational boundary-price correlation: measured from completed
  Stage 4 paths rather than assumed from `rho_F`.

Stage: 3 — target operational prerequisites (`v1.3.4`–`v1.3.5`)

Science status: v1.3.4 and v1.3.5 accepted; Stage 3 closed

Acceptance status: 145-entry manifest, eight generated checks and complete
143-test route passed from a fresh extraction

Next decision: open the uniform operational solver at `v1.4.0`
