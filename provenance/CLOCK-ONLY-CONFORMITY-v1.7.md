# Clock-only theory/estimator conformity — `v1.7.4`

Status: accepted on 2026-08-14 after complete fresh-extraction verification

## Decision

The reduced correlated-Brownian previous-refresh reference recovers the exact
equal-rate Poisson clock curve. The full uncoupled Angstmann--Gebbie
reaction-boundary benchmark is a qualified nonconformity: its standardised
error, pointwise coverage, plateau, exact clock overlap and all numerical
invariants pass, while its absolute curve RMSE is `0.032471`, slightly above
the predeclared `0.03` threshold.

This gate corrects the clock-rate interpretation without fitting a curve. For
equal independent Poisson previous-refresh clocks, the exact result is

\[
F(\lambda\Delta t)
=1-\frac{1-e^{-\lambda\Delta t}}{\lambda\Delta t},
\qquad \lambda_1=\lambda_2=\lambda.
\]

The displayed analytical rate `0.1 s^-1` is therefore the rate of each equal
book clock. The minimum of the two forward waits has the exact pooled rate
`0.2 s^-1`, but that minimum-wait rate is not the attenuation parameter of the
previous-refresh estimator. The old pooled-rate curve is retained in Figure
19 and the CSV as a rejected diagnostic. Its RMSE from the exact equal-rate
curve is `0.059585`.

The correction follows the exact previous-tick Brownian calculation in Toth,
Toth and Kertesz, arXiv:0704.3798, Equation 29. Angstmann and Gebbie,
arXiv:2606.14182v2, remains the authority for the fixed-grid operational-time
dynamics, the general pathwise inverse clock, and the exact operational-
interval overlap object. The general inverse-clock implementation is not
deleted or relabelled as the previous-refresh benchmark.

The accepted v1.7.3 paper source remains byte-identical in
`source/source-v1/`. The correction is recorded separately in
`source/source-v2/CLOCK-RATE-CORRECTION-v1.7.tex`; this prevents a later gate
from silently rewriting accepted evidence.

## Separation of the two clock objects

1. `functions/observation/clocks.py` retains the general map `T_j(u)` and its
   finite-grid inverse `E_j(t)`. Its exact claim-bearing diagnostic is the
   realised overlap of the sampled operational intervals.
2. `functions/observation/refresh_sampling.py` implements the separate
   equal-rate previous-refresh reference. It samples a completed uniform-grid
   operational path at the latest book-specific refresh time and then at the
   previous stored operational state. It owns no random generator and performs
   no interpolation or state update.

Both routes preserve the accepted order: uniform operational dynamics,
external clock construction, explicit time change, then calendar-time
measurement. No realised wait enters the density recurrence.

## Registered experiment

The common operational step is `0.005` model units or `0.5` seconds under the
accepted 100-seconds-per-model-unit map. The registered lags are 20 through
400 seconds in 20-second increments. Each book refreshes at `0.1 s^-1`, giving
20 operational steps per clock characteristic time.

The reduced reference uses 32 operational Brownian paths with known
`rho_u=0.8`, four clock replications per path, a 200-second warm-up and a
10,000-second analysis horizon. Increasing this cheap reference horizon from
the 2,000-second design minimum was a numerical-precision response to the
first gate run: the shorter run met standardised error and coverage but not the
absolute-RMSE threshold. No rate, lag, seed count or theoretical value was
retuned.

The thick-boundary experiment uses 16 calibration paths to freeze the
identity-clock correlation and 32 disjoint validation paths, with four clock
replications per validation path. Each path has 4,400 operational steps: 200
seconds of warm-up plus a 2,000-second analysis interval. The books are
uncoupled and receive exactly correlated operational innovations with
`rho_u=0.8`.

The primary estimate is a ratio of pooled covariance and variance sums. Clock
replications are summed within operational path, and uncertainty is obtained
by deleting one operational-path group at a time. The thick-boundary
normalised uncertainty combines independent calibration and validation
jackknife errors by the delta method. A mean of pathwise correlations is not
used as the claim-bearing estimator.

## Results

| Tier | Label | Curve RMSE | Standardised RMSE | 95% coverage | Plateau shift | Exact-overlap RMSE |
|---|---:|---:|---:|---:|---:|---:|
| Reduced Brownian | `recovered` | 0.006474 | 0.518405 | 1.00 | 0.006667 | 0.000162 |
| Thick boundary | `qualified_nonconformity` | 0.032471 | 0.815378 | 0.95 | 0.026719 | 0.000883 |

The independently measured calibration book rates differ from their inputs by
at most `0.003786` relatively. Both thick-boundary input streams recover
`rho_u=0.8` to floating-point precision. Every reaction boundary is unique,
the minimum edge distance is `9.802404`, and no clock selects the terminal
state by extension or clamping.

The full-model qualification is not evidence of a clock-code defect: the
realised clock overlap recovers the exact curve, while the residual appears
only after projecting through the reaction boundary and normalising by the
independent calibration ensemble. It is retained for the coupling and
combined stages rather than removed by changing the clock rate.

## Outputs

- `figures/figure-19-clock-only-conformity-v1.pdf` and `.png`;
- `outputs/clock-only-conformity-curves-v1.7.csv` (40 rows);
- `outputs/clock-only-conformity-summary-v1.7.csv` (two tier summaries);
- `outputs/clock-only-boundary-paths-v1.7.npz` (frozen calibration and
  validation price paths);
- `diagnostics/clock-only-conformity-checks-v1.7.csv` (21 verified checks, one
  qualified full-model check and zero failures);
- `source/source-v2/CLOCK-RATE-CORRECTION-v1.7.tex` (theory-to-estimator rate
  correction overlay; the accepted source remains frozen).

## Stage consequence

Recovery of `CNF-CLK-REF-01` permits the independent coupling-only experiment
at `v1.7.5` after this gate is accepted. `CNF-CLK-LOB-01` remains explicitly
qualified and must be carried into the full combined-model interpretation at
`v1.7.6`; it cannot be converted to a pass by refitting the combined curve.

The later v1.7.5 local-response audit blocks that originally scheduled
combined gate. The registered combined version is v1.7.8, after a
separate correction design and corrected coupling recovery.
