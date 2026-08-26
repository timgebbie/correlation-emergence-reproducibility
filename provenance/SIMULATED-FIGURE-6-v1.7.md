# Simulation analogue of analytical Figure 6 — `v1.7.1`

Status: accepted at `v1.7.1`

## Role

`SIM-F6-01` is development Figure 17. It supplies the simulated counterpart
to immutable analytical Figure 6 without yet superimposing the two. The
registered overlay is a separate `v1.7.2` decision.

## Dimensional map

The accepted independent-Poisson clocks have book rates `200` and `200` per
model-calendar unit. Their pooled rate is therefore `400`. Analytical Figure
6 declares `lambda_12=0.1 s^-1`. The rate identity

```text
400 / (4000 seconds) = 0.1 per second
```

fixes one model-calendar unit at 4,000 seconds and the stored `0.005` calendar
step at 20 seconds. This is an a priori clock-rate map. It is not fitted to the
simulated Epps curve or its plateau.

The Figure 6 range 0--400 seconds therefore contains simulated lags 1--20, or
20--400 seconds. No simulated value is invented at zero aggregation lag.

## Display scale

The figure retains a linear comparison panel with the analytical Figure 6
limits: 0--400 seconds and normalised correlation 0--1.05. Because the
finite-ensemble simulation mean occupies only approximately 0.028--0.059 on
that scale, an aligned detail panel repeats the identical data on the same
linear time axis with fixed limits -0.22--0.30. Those limits contain the
complete normal 95% path-group band, whose observed range is approximately
-0.188--0.268.

The detail panel is a display magnification, not a renormalisation. A
logarithmic correlation axis is excluded because the uncertainty band crosses
zero. The legacy Figure 7 vertical convention is excluded because it contains
the historical sparse-allocation divisor and its horizontal coordinate is in
simulation-index rather than calendar-time units.

## Normalisation

The primary curve remains the equal-weight mean across eight operational-path
groups after two clock replications have been averaged within path. Its
registered plateau proxy is the arithmetic mean of that accepted raw curve
over lags 501--600. The observed value is approximately `0.248704`. Main-curve
means and standard errors are divided by this one fixed positive scalar.

This is a finite-window display normalisation. It is not an asymptotic limit,
empirical calibration or pathwise plateau estimate. Several individual paths
have negative long-window correlations, so pathwise division would be unstable
and is deliberately excluded.

## Path-derived diagnostics

The accepted Stage 4 reaction-boundary prices are evaluated under the accepted
independent book-specific Poisson clocks on the common Stage 5 grid through
model-calendar time `11.615`. Previous-completed-state inversion is used. No
interpolation, extrapolation, clock generation or solver rerun occurs.

Each of the 16 clock members supplies two one-step boundary-price increment
series of length 2,323. For positive lag `k`, the increment autocorrelation is
the Pearson correlation between the two overlapping lagged slices after each
slice is centred by its own mean. Lags 0--10 correspond to 0--200 seconds.

The spectrum is the one-sided Hann Welch periodogram of the same increments:
256 observations per segment, 128-observation overlap, 17 complete segments,
20-second sampling and Nyquist frequency `0.025 Hz`. Each member-book density
is divided by its trapezoidal integral so that it integrates to one.

For both diagnostics, the two books and two clock replications are averaged
within operational path. Means, sample standard deviations and standard
errors are then formed across the eight operational paths. The normal 95%
band is a finite-ensemble summary, not empirical confidence coverage.

## Outputs and boundary

- `outputs/simulated-figure-6-curves-v1.7.csv`: 20 aggregate curve rows;
- `outputs/simulated-figure-6-members-v1.7.csv`: 320 curve-member rows;
- `outputs/simulated-figure-6-path-diagnostics-v1.7.csv`: 140 summary rows;
- `outputs/simulated-figure-6-path-diagnostic-members-v1.7.csv`: 4,480
  member-book rows;
- `diagnostics/simulated-figure-6-checks-v1.7.csv`: 30 checks; and
- `figures/figure-17-simulated-figure-6-v1.pdf` and matching PNG.

The figure is a synthetic finite-ensemble result. It is not a market-data fit,
trade-sign diagnostic, price-impact estimate or claim of agreement with the
analytical curve. Analytical and simulated curves are joined only at the
registered `v1.7.2` overlay gate.
