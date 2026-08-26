# Theory-conformity design — `v1.7.3`

Status: accepted

`v1.7.4` execution note: the design's candidate assignment of book rates
`0.05 s^-1` and pooled rate `0.1 s^-1` was rejected by exact estimator
conformity. For equal-rate previous-refresh sampling, the closed-form factor
uses each book rate. The displayed `0.1 s^-1` curve is therefore tested with
book rates `(0.1, 0.1)` and a separately recorded minimum-wait rate `0.2 s^-1`.
This is a theory-to-estimator correction, not a fit. General unequal or inverse
clocks continue to use their exact realised operational-interval overlap.

`v1.7.5` execution note: the reduced symmetric SDE recovers the registered
normalized covariance response and its separately calculated exact return
correlation. The accepted thick-boundary coupling does not satisfy the local
rate precondition: every positive `gamma` in the declared scan gives
non-positive paired exponential and local-drift response rates. The stochastic
thick-boundary Epps validation and combined no-refit prediction are therefore
not executed. This is an `invalid_experiment` precondition, not a failed curve
fit. The accepted source and coupling remain unchanged; no replacement is
selected by this gate.

`v1.7.6` design note: four correction candidates are compared without changing
the production coupling, solver or path. The selected primary source is the
current-front translation mode

\[
\ell_T^{(j,k)}=-\kappa_{jk}z_{jk}v_j,
\qquad v_j=-\partial_x\varphi^{(j)}.
\]

It realizes the normalized appendix projection directly, fixes the
receiving-book sign and inherits thickness from the current front. The
fixed-`epsilon` selector is excluded from the primary linear response; a later
side-selective residual must be projection-orthogonal. Nine deterministic
probes recover the target total rate to relative error below `0.001`. This is
tractability evidence, not the v1.7.7 implementation or stochastic recovery.

`v1.7.7` execution note: the selected coupling is implemented through distinct
translation-density, solver-entry and path modules while the accepted
regularised implementation remains hash-exact. Eight signed deterministic
relaxations pass before stochastic execution. Sixteen disjoint calibration
paths freeze the covariance normalization; 32 holdout paths recover both the
paper's normalized covariance response and the distinct exact return
correlation under identity clocks. The result retains the reduced theory but
requires its regularised source-amplitude-to-rate bridge to be stated as a
closure assumption. Subject to external acceptance, the combined no-refit
prediction is unblocked for v1.7.8.

## Purpose

The accepted `v1.7.2` Figure 18 establishes a real discrepancy under the old,
non-fitted registration. It does not establish that the analytical reduction
and the simulation are incompatible. The analytical rates were illustrative,
the simulation used a finite-window plateau proxy, and the Stage 6 factorial
cells were designed for mechanism contrasts rather than component-by-component
recovery of the theoretical envelopes.

Stage `v1.7.3` therefore reopens the simulation experiment, not the accepted
uniform operational solver. It fixes the calibration rules, independent rate
measurements, numerical resolution and holdout tests before any parameter is
changed. No stochastic path, clock path, solver, accepted figure or accepted
curve is changed at this design gate.

## Why the existing factorial cells are not conformity targets

The current uncoupled control has zero microscopic cross-book innovation
correlation. Applying two clocks to that control cannot recover the normalised
clock factor because the clock-only derivation requires a nonzero operational
correlation \(\rho_u\):

\[
\rho_{\Delta t}^{\mathrm{clk}}
=\rho_u F(\lambda_{12}^{\mathrm{clk}}\Delta t),
\qquad
F(x)=1-\frac{1-e^{-x}}{x}.
\]

The coupled identity-clock cell is a candidate coupling-only experiment, but
it becomes a conformity test only after the spread-relaxation rate \(\kappa\)
has been measured independently and the local Ornstein--Uhlenbeck reduction
has been diagnosed. The combined coupled/Poisson cell is a conformity test only
after both component parameters have been fixed without using its curve.

The earlier Fourier/mode estimator remains a historical Bauer diagnostic. It
is not a claim-bearing observable in the conformity path.

## Two levels of recovery

Each mechanism is tested first in a reduced reference model and then in the
full thick-boundary simulation.

1. The reduced-reference tier tests the code and estimator in the processes
   from which the analytical expressions are derived: correlated Brownian
   operational prices for clock-only recovery and a two-price linear SDE with
   an OU spread for coupling recovery.
2. The thick-boundary tier tests whether the Angstmann--Gebbie reaction-front
   model lies in the local regime required by that reduction. Failure here
   after reduced-reference recovery is scientific evidence about the
   approximation, rather than an unresolved implementation error.

This distinction prevents a failed thick-boundary comparison from being
misclassified as a clock, estimator or subordination-code defect.

## Clock-only recovery — `v1.7.4`

The reduced benchmark uses a declared nonzero \(\rho_u=0.8\), no coupling and
two independent Poisson clocks. The thick-boundary benchmark uses uncoupled
books with the same declared nonzero operational innovation correlation. The
clock rates are set directly to

\[
\lambda_1^{\mathrm{clk}}=lambda_2^{\mathrm{clk}}
=0.05\ \mathrm{s}^{-1},
\qquad
\lambda_{12}^{\mathrm{clk}}=0.1\ \mathrm{s}^{-1}.
\]

The book rates are checked from realised waiting intervals and summed only
after measurement. They are not fitted to an Epps curve. The reduced curve is
normalised by known \(\rho_u\); the boundary curve is normalised by a frozen
identity-clock boundary-price reference generated on calibration paths. New
operational paths, clocks and lags are used for validation.

The Poisson pooled rate is exact, while the overlap envelope is an effective
approximation for the chosen previous-state observation rule. Any residual
envelope discrepancy must therefore be reported rather than hidden by silently
changing the rate definition.

## Coupling-only recovery — `v1.7.5`

Both coupling-only experiments use identity clocks and independent operational
innovations. The reduced SDE sets \(\kappa=0.025\ \mathrm{s}^{-1}\) directly.
In the thick-boundary experiment, \(\kappa\) is measured without using the
Epps curve from

\[
\frac{\mathbb E[\Delta z\mid z]}{\Delta u}
\simeq-\kappa z
\]

near the origin and from the exponential relaxation of separately generated
small spread perturbations. The two measurements must agree within the rate
tolerance. Diagnostics also test drift linearity, exponential response,
simple reaction boundaries, displacement remainders, response asymmetry and
the appendix condition

\[
\tau_{\mathrm{shape}}\gg \kappa^{-1}.
\]

Only the primary coupling amplitude `coupling_gamma` may be adjusted to reach
the independently measured target rate. Source width, source strength,
reference spread, reference transition width and regularisation scale remain
fixed in the primary recovery. They may later enter a separately labelled
robustness experiment, but they cannot be tuned against the Epps curve.

Execution shows that this one-parameter calibration is not tractable for the
accepted numerical coupling. Its expansion at small spread has only a
linear term proportional to the base source, which changes the stationary
front amplitude without translating the zero crossing to first order. The
first translating shape contribution enters at higher order. Accordingly,
the registered target rate is not bracketed by increasing `coupling_gamma`,
and a separately designed correction must resolve receiving-book sign,
selector limit and translation-mode projection before recovery is rerun.

## Originally scheduled combined prediction — `v1.7.6` (blocked)

The validated clock and coupling parameters are frozen. The same explicitly
subordinated operational construction then predicts

\[
\frac{\rho_{\Delta t}^{\mathrm{comb}}}{\rho_\infty}
\simeq
F(\lambda_{12}^{\mathrm{clk}}\Delta t)
F(\kappa\Delta t).
\]

No combined-curve refit is permitted. The reduced tier tests the implementation
of the product construction. The thick-boundary tier tests the leading-order
separability condition

\[
\mathbb E[\Theta_{12}(I)H_\kappa(I)]
\simeq
\mathbb E[\Theta_{12}(I)]\mathbb E[H_\kappa(I)].
\]

A remaining combined residual is therefore reported as a nonseparability
diagnostic. It is not removed by retuning either component.

## Candidate dimensional resolution

The previous map used 4,000 seconds per model-time unit. With
\(\Delta u=0.005\), the analytical 40-second coupling timescale occupied only
two operational steps. That is inadequate for a rate-conformity experiment.

The candidate map for testing is 100 seconds per model-time unit. It retains
\(\Delta u=0.005\), giving a 0.5-second operational step. Book clock rates of
5 per model unit give 0.05 per second each, and a target model-time coupling
rate of 2.5 gives 0.025 per second. The 10-second clock timescale then has 20
steps and the 40-second coupling timescale has 80 steps. A minimum 2,000-second
path contains 4,000 operational steps.

This is a numerical-resolution proposal, not an accepted simulation parameter
set. `v1.7.4` must first verify waiting-time laws, supports, stability and the
absence of terminal-state extension.

## Calibration, validation and acceptance

Calibration and validation use disjoint random seeds and disjoint lag sets.
The design uses 16 operational calibration paths, 32 validation paths and four
clock replications per validation path. Clock replications are averaged within
operational path before across-path uncertainty is calculated. The registered
20--400 second Figure 18 lags are validation lags.

The predeclared primary criteria are:

- at most 5% relative error in independently measured \(\lambda\) and
  \(\kappa\);
- at most 5% plateau shift between adjacent nonoverlapping long-lag bands;
- curve RMSE at most 0.03 in normalised correlation;
- standardised curve RMSE at most 2.0; and
- at least 90% coverage of the registered analytical values by pointwise
  normal 95% simulation bands.

Results are labelled `recovered`, `qualified_nonconformity`, or
`invalid_experiment`. A reduced-reference failure invalidates the corresponding
full-model claim. A thick-boundary failure after reduced-reference recovery is
a qualified nonconformity with the analytical reduction. A failed numerical,
support or parameter-measurement invariant is an invalid experiment and must
be repaired before interpretation.

## Stage boundary

The accepted design sequence was:

- `v1.7.3`: conformity design;
- `v1.7.4`: clock-only recovery;
- `v1.7.5`: coupling-only recovery;
- `v1.7.6`: combined no-refit prediction; and
- `v1.7.7`: stability, integrity and Stage 7 closure.

The accepted v1.7.5 result blocks the last two planned steps. The adopted
revised sequence is:

- `v1.7.6`: coupling-correction design;
- `v1.7.7`: corrected coupling implementation and independent local-rate
  recovery;
- `v1.7.8`: superseded combined no-refit candidate;
- `v1.7.10`: superseded corrected combined no-refit and cross-platform
  reproducibility candidate;
- `v1.7.11`: slope-consistent fixed-point tolerance and corrected combined
  reproducibility gate; and
- `v1.7.12`: stability, integrity and Stage 7 closure.

`v1.7.11` execution note: the frozen combined experiment completes the uniform
operational paths before applying independent book-specific previous-refresh
clocks. An exact conditional reduced reference recovers the implemented
estimator, but differs from the leading-order product by RMSE `0.037391`.
The thick-boundary covariance adds RMSE `0.039719` relative to the exact
same-clock reference. The result is therefore a qualified scientific
nonconformity with the separability approximation, not an invalid experiment;
no rate, normalization, threshold or curve is refitted. The `v1.7.8` candidate
was superseded solely because its Windows figure-publication durability call
failed; it was not accepted or tagged.

Stage 8 event semantics and impact remain unchanged and begin only after
Stage 7 closure is accepted.

`v1.7.12` closure note: no theory, simulation parameter or estimator is
changed. The gate checks the accepted diagnostic/result inventory and freezes
the uniform-operational-then-subordinated architecture before Stage 8 begins.
