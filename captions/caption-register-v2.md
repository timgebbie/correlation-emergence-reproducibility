# Caption register - v2.0.0

## Figure 1 - Ordinary Epps components

Clock and coupling components use `F(x)=1-(1-exp(-x))/x`; the combined curve is
their leading-order separable product. Panels vary the ratio of the coupling
and clock rates. The result is model-conditional and is neither an empirical
fit nor a proof of independence.

## Figure 2 - Ordinary-kernel sensitivity

Curves give the logarithmic sensitivity of the ordinary clock and coupling
components and of their product. The figure locates scales carrying rate
information; it is not a global-identifiability or empirical-uncertainty claim.

## Figure 3 - Fractional response sensitivity

Fractional clock and response components use the registered Mittag--Leffler
evaluation. Equal leading short-scale powers expose local confounding even
when later-scale curvature differs. The figure tests formula sensitivity and
the ordinary limit, not empirical identification of fractional orders.

## Figure 4 - Boundary-to-Epps propagation

Reaction-front moment, slope and coupling inputs are propagated through the
analytical response-rate mapping while the clock rate is fixed. This is a
conditional sensitivity calculation, not a unique inverse calibration and not
a pointwise equivalence claim for numerical source kernels.

## Figure 5 - Finite-grid boundary representation

Discrete-to-continuum first-moment ratios diagnose selector resolution,
lattice spacing, alignment and domain margin. The resulting rate envelope is
propagated into the Epps curve. The selector is a numerical diagnostic; the
production translation-mode coupling uses the resolved density front.

## Figure 6 - Calendar-time analytical Epps curve

The ordinary response is displayed on an illustrative linear seconds axis with
equal book refresh rates and explicit previous-refresh interpretation. The
seconds scale is not fitted to data, and the survival inset is not a simulated
path autocorrelation or spectrum.

## Figure 7 - Final estimator-aware Epps integration

Clock-only, translation-mode coupling-only and combined results share one linear
0--400 second, 0--1.1 normalized-covariance scale. The combined no-refit
holdout is compared with the paper's leading-order product and with the exact
finite-grid, finite-step conditional moment on the same realised clocks. The
estimator-aware RMSE is `0.039719`, standardized RMSE is `0.455132`, and
pointwise normal-band coverage is complete. No parameter or normalization is
refitted.

## Figure 8 - Translation-mode coupling

The translation-mode thick-boundary holdout is compared with the analytical
normalized covariance response and the distinct finite-scale return
correlation. Deterministic panels verify signed front relaxation at the frozen
response rate. Dynamics use uniform operational time and the current receiving
front's translation mode; no clock or interpolation enters this component
gate.

## Figure 9 - Single-trade own and cross impact

Paired shocked and matched-control paths measure aggressor-signed own- and
cross-boundary responses to one labelled market order. Operational and
previous-refresh calendar views use a common linear response scale. The event
is a declared model operation, not an empirical trade calibration.

## Figure 10 - Meta-order own and cross impact

Scheduled child market orders form matched meta-order experiments. Trajectory,
peak, relaxation and equal-volume horizon comparisons distinguish own from
cross impact. Schedule timing is not described as a true participation rate
because background market-order volume is not modelled.

## Figure 11 - Mid-price and trade-sign autocorrelations

Panels report log-mid increment autocorrelation for uniform operational and
previous-refresh calendar observations, same-book event-time trade-sign
autocorrelation for three sign conventions, subordinated calendar signed-flow
autocorrelation, and pairwise sign-convention agreement. Price-level
autocorrelation is excluded. The declared finite Markov persistence is an
estimator fixture, not empirical calibration or a long-memory claim.

## Table 1 - Parameter, timescale and identifiability register

The table maps paper notation to implementation names and records units,
roles, sensitivity paths and fixed or swept status. Identifiability labels are
conditional on the model and registered outputs.

## Table 2 - Numerical benchmarks

The table records claim-relevant analytical references, numerical tolerances,
observations and acceptance status. It supports reliability within the tested
runtime; it is not a mathematical proof or empirical validation.
