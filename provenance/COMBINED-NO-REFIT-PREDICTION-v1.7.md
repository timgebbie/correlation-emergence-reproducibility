# Combined clock and corrected-coupling no-refit prediction — `v1.7.11`

Status: accepted gate; external acceptance recorded 2026-08-21

## Frozen experiment

This gate combines the accepted `v1.7.4` clock component and accepted
`v1.7.7` corrected coupling component without fitting the combined curve.
It retains:

- equal book refresh rates `0.1 s^-1`;
- ordered coupling rates `1.25` and `1.25` per model-time unit, giving total
  dimensional response rate `0.025 s^-1`;
- thick-boundary covariance scale `1.0568450226140758e-06`;
- all accepted operational solver, path and previous-refresh modules; and
- the 20 registered lags from 20 to 400 seconds.

The accepted component files and source overlays are hash-frozen in
`config/config-v1.7.11.json`. No component or combined refit is permitted.

## Time-layer conformity

Every reduced and thick-boundary state is completed on a fixed uniform
operational grid. Only then are two independent equal-rate previous-refresh
clocks generated and mapped to the previous completed uniform state. Realised
waiting times never enter the order-density recurrence. There is no
interpolation, nonuniform state update, extrapolation or terminal-state clamp.

The subordination step therefore conforms to the Angstmann--Gebbie separation
of operational dynamics from the observation clock. It replaces the Bauer
construction in which nonuniform increments alter the evolving state itself.

## Independent estimator-aware reference

`functions/observation/combined_reference.py` computes exact conditional
Gaussian moment sums for the stationary symmetric reduced process given the
operational indices already selected by the two clocks. It owns no clock, RNG,
interpolation or dynamics. The numerical estimator and exact reference use the
same realised indices and aggregation windows.

The reduced result is recovered:

| Comparison | RMSE | Standardized RMSE | Coverage |
|---|---:|---:|---:|
| Normalized covariance versus exact conditional reference | `0.008530` | `0.400263` | `1.0` |
| Return correlation versus exact conditional reference | `0.002296` | `0.386438` | `1.0` |

The exact reduced estimator-aware covariance differs from the paper's
leading-order product by RMSE `0.037391`. Because the registered product
threshold is `0.03`, this is a qualified scientific nonconformity, not an
implementation failure.

## Thick-boundary decomposition

The same frozen clock realizations define an exact reduced same-clock reference
for every thick-boundary holdout group. This separates the residuals:

| Residual | RMSE | Status |
|---|---:|---|
| Exact reduced estimator-aware reference minus analytical product | `0.037391` | Qualified |
| Thick boundary minus exact reduced same-clock covariance | `0.039719` | Qualified by absolute threshold; standardized RMSE `0.454980`, coverage `1.0` |
| Thick boundary minus accepted component product | `0.056040` | Qualified |
| Thick boundary minus analytical product | `0.066963` | Qualified; standardized RMSE `1.469081`, coverage `0.9` |

The thick-boundary return-correlation residual relative to the exact reduced
same-clock reference is `0.014858`, within the `0.03` criterion. The combined
plateau proxy has relative shift `0.077190`, above its registered `0.05`
criterion and is retained as a qualification.

## Interpretation

The source-v1 paper is not rejected. Its Appendix C explicitly presents the
product as a leading-order separability approximation and states conditions
under which factorisation need not hold. The v1.7.11 result quantifies two
departures that the product suppresses:

1. intrinsic estimator-level nonseparability caused by applying two asynchronous
   previous-refresh clocks to a dynamically coupled process; and
2. an additional residual due to the thick reaction-boundary dynamics.

The operational-time/subordination architecture is recovered independently.
The scientific outcome is therefore `qualified_nonconformity`, with zero
failed execution checks and no parameter tuning.

## Outputs and boundary

- Figure 22 in PDF and PNG;
- 20 curve/decomposition rows;
- three summary rows;
- four realised clock-rate rows;
- a compressed exact/thick component and path archive; and
- 38 generated checks: 33 verified, five qualified and zero failed.

The accepted source-v1 manuscript remains hash-exact. This accepted gate
does not close Stage 7. On acceptance it opens `v1.7.12`, the stability,
integrity and Stage 7 closure audit.
