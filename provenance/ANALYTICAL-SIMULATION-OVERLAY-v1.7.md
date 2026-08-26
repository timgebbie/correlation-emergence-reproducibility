# Registered analytical Figure 6--simulation comparison — `v1.7.2`

Status: accepted discrepancy diagnostic

## Role

`OVL-EPP-01` is development Figure 18 and the accepted discrepancy diagnostic. It
superimposes immutable analytical Figure 6 and accepted simulated Figure 17
without changing either source object. Legacy Figure 7 remains the separate
Bauer test/reference case and is not used in the registration.

## Registration

Analytical Figure 6 has a 0.5-second grid from 0 through 400 seconds. Accepted
Figure 17 has 20 observations at 20-second multiples from 20 through 400
seconds. Every simulated abscissa is therefore already present in the
analytical register. The comparison uses an exact keyed lookup and performs no
interpolation or extrapolation. No simulated zero-lag value is invented.

The analytical curve retains its illustrative rates
`lambda_12=0.1 s^-1` and `kappa=0.025 s^-1` and the normalisation
`rho_Delta_t/rho_infinity`. The simulation retains the accepted rate map
`400/4000=0.1 s^-1` and the finite-window plateau proxy from lags 501--600.
Neither the time map nor either normalisation is fitted at this gate.

## Figure construction

The upper panel uses the accepted linear comparison limits: 0--400 seconds and
normalised correlation 0--1.05. It contains the analytical limiting, clock,
coupling and combined curves; the simulated path-group mean and normal 95%
standard-error band; and the separate pooled simulation estimate.

The lower panel reports simulation minus the analytical combined curve at the
20 exact common abscissae. Its band is formed by subtracting the same analytical
value from the accepted simulation lower and upper endpoints. It therefore
changes no uncertainty calculation and introduces no residual model.

## Conditional comparison result

The accepted simulation mean minus the analytical combined curve ranges from
approximately `-0.090` at 20 seconds to `-0.837` at 400 seconds. The shifted
upper band remains below zero at all 20 registered lags; its maximum is
approximately `-0.062`. Thus the illustrative analytical combined curve lies
above the complete accepted finite-ensemble simulation band throughout this
registered display range.

This separation is conditional on the analytical rates, the declared
simulation time map, the finite-window plateau normalisation, the eight
operational-path groups and the accepted realised clocks. It is not a fitted
goodness-of-fit statistic, empirical confidence statement or general rejection
of the reaction-boundary or subordination mechanisms. It identifies the scale
and response mismatch that any later calibration or structural refinement
would have to explain.

## Outputs and boundary

- `outputs/analytical-simulation-overlay-curves-v1.7.csv`: 3,244 long-form
  curve rows;
- `outputs/analytical-simulation-comparison-v1.7.csv`: 20 exact joined rows;
- `diagnostics/analytical-simulation-overlay-checks-v1.7.csv`: 25 checks; and
- `figures/figure-18-analytical-simulation-overlay-v1.pdf` and matching PNG.

Acceptance fixes Figure 18 but does not close Stage 7. It opens `v1.7.3`, the
theory-conformity design that will separately validate clock-only and
coupling-only recovery before testing their combination without a further
fit. No event is yet called a trade and no single-order, meta-order,
own-impact or cross-impact estimand is introduced in this overlay.
