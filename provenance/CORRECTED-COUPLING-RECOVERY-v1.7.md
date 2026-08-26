# Corrected coupling recovery — `v1.7.7`

Status: accepted on 2026-08-20

## Scientific result

The selected current-front translation-mode source is now implemented through
three distinct operational modules:

- `translation_coupling.py` defines `TranslationModeCoupling` and
  \(\ell_T^{(j,k)}=-\kappa_{jk}z_{jk}v_j\);
- `translation_solver.py` constructs both ordered fields from one immutable
  pre-step density and price snapshot; and
- `translation_path.py` evolves the resulting books on the uniform operational
  grid.

The accepted `RegularizedCoupling`, its solver entry and its rolling path remain
hash-exact comparators. The faithful Bauer/Julia implementation also remains
separate and unchanged.

For ordered rates `1.25` and `1.25` per model-time unit, eight signed
perturbations recover the registered total rate. The largest exponential-rate
relative error is `0.006117`; the largest local-drift rate error is `0.000645`.
The source-level front-mode residual is exactly zero, the pair centre is
preserved to numerical precision, all reaction boundaries are unique and
interior, and the three-grid exponential-rate errors decrease from `0.025099`
to `0.005961` and `0.001425`.

Only after this deterministic gate passed was the stochastic identity-clock
experiment executed. Sixteen calibration paths freeze the covariance scale
from the pair-centre variance-growth rate on lags disjoint from validation.
The four calibration rates have relative range `0.027589`. Thirty-two holdout
paths then give:

| Estimand | Analytical target | Holdout RMSE | Standardized RMSE | Coverage |
|---|---|---:|---:|---:|
| Normalized covariance response | \(F(\kappa\Delta)\) | `0.016700` | `0.263834` | `1.0` |
| Realised return correlation | Exact symmetric closed-SDE correlation | `0.008772` | `0.416618` | `1.0` |

The stochastic conditional-drift diagnostic measures `2.449397` per
model-time unit, a relative error of about `0.02024`. The simulation therefore
recovers both the paper envelope under its correct covariance normalization and
the distinct exact return-correlation curve.

## Consequence for the paper

The paper is not rejected as mathematically incorrect. Its adjoint projection
and reduced response are conditional calculations. The audit shows that the
specific regularised `tanh` source does not, by itself, establish the assumed
map from `gamma_jk` to `kappa_jk` in the full numerical recurrence. The new
translation-mode source realizes the reduced boundary equation directly and
makes `kappa_jk` an explicit response rate.

The accepted source-v1 manuscript stays frozen at this gate. The source-v2
overlay `CORRECTED-COUPLING-RECOVERY-v1.7.tex` records the eventual revision:
retain the regularised source as a phenomenological or weak-moment
representation, qualify its source-to-rate closure, and identify the
translation-mode implementation as the direct numerical realization.

The source-kernel correction is separate. The target operational source uses
`exp(-mu*y^2)` as in the paper; the legacy Julia `exp(-(mu*y)^2)` remains only
inside the faithful historical port.

## Separation of time layers

All v1.7.7 density and boundary evolution occurs on the fixed uniform
operational grid. The coupling-only recovery uses the identity clock. No
realised waiting time, nonuniform update, subordination or interpolation enters
the recurrence. Book-specific calendar clocks remain an explicit later mapping
of completed operational paths.

## Outputs

- Figure 8, PDF and PNG;
- 20 machine-readable curve rows;
- eight primary signed-rate rows and three grid-convergence rows;
- 1,288 deterministic response rows;
- a compressed holdout price-path archive;
- one recovery-summary row; and
- 38 verified generated checks with zero failures.

## Stage boundary

This accepted gate unblocks the v1.7.8 combined no-refit prediction. Neither
the pair-centre covariance scale nor either ordered coupling rate may be
refitted to the combined curve.
