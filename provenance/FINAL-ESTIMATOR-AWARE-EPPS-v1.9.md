# Final estimator-aware combined Epps integration — `v1.9.0`

Status: accepted numerical gate; acceptance recorded 2026-08-24

Figures 7a--7c expose the accepted clock-only, corrected coupling-only and
combined holdout results as separate standalone square outputs without
rerunning or fitting the underlying models. All three use the same linear
0--400 second horizontal scale and the same 0--1.1 normalized-covariance
scale. The original three-panel composite is retained only as the compact
README overview.

The clock-only and coupling-only figures compare the frozen analytical curves
with their accepted thick reaction-boundary simulations. The combined panel
compares the accepted no-refit holdout with two distinct theoretical objects:

1. the paper's leading-order separable product
   `F(lambda Delta) F(kappa Delta)`; and
2. the exact finite-grid, finite-step conditional moment calculation evaluated
   on the operational indices selected by the same realized clocks as the
   holdout.

The estimator-aware combined figure has RMSE `0.039719`, below the leading-order
product RMSE `0.066963`. Its standardized RMSE is `0.455132`, and the
pointwise normal 95% band covers the same-clock reference at all 20 registered
lags. This improvement is obtained without changing a clock rate, coupling
rate, boundary normalization, time map or acceptance threshold.

Both books still evolve on a uniform operational-time grid. The independent
book-specific previous-refresh clocks act only after each operational path is
complete. No realized waiting interval enters the state recurrence, and no
calendar interpolation or nonuniform state update is used.

The estimator-aware curve refines the leading-order product for the declared
finite estimator; it is not a fitted replacement for the paper's asymptotic
mechanism decomposition. Source-v1 remains unchanged. Acceptance advances the
project to `v1.9.1`, which streamlines the release surface before `v2.0.0`.
