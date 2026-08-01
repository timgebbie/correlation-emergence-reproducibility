# Numerical methods and tooling

Version: v1.0.0

## Computational route

The paper is the source of truth and all outputs are deterministic evaluations of analytic or discretised theoretical objects. No empirical data, calibration, stochastic path simulation, or Julia conversion enters v1.0.0.

The user route is standalone Python with one JSON configuration file, reusable functions, short executable scripts, CSV outputs, PDF/PNG figures, standalone LaTeX tables, and a root-level LaTeX supplement. It requires only NumPy and Matplotlib. Standard-library `unittest` supplies the local test command.

## Ordinary kernel

The ordinary build-up uses `numpy.expm1` away from zero and the local series

\[
F(x)=x/2-x^2/6+x^3/24-x^4/120+x^5/720+\cdots
\]

below the configured switch. The derivative uses the corresponding differentiated series. The rate elasticity is evaluated as (xF'(x)/F(x)), with its limiting value set explicitly to one at zero.

## Fractional kernel

For (0<\alpha<1), the evaluator uses the non-negative real-axis representation

\[
E_\alpha(-t^\alpha)=\int_0^\infty e^{-rt}K_\alpha(r)\,dr,
\]

and integrates the time average analytically inside the integral. A logarithmic change of variable converts the semi-infinite integral to a smooth integral on the real line, evaluated by deterministic composite Gauss-Legendre quadrature. Small arguments use the defining series for (1-E_{\alpha,2}(-x)). The endpoint (\alpha=1) uses the ordinary closed form exactly.

The release profiles are (\alpha\in\{0.6,0.8,1.0\}). Acceptance requires alpha-one recovery, series agreement, and separately generated adaptive-quadrature reference values. The method is intentionally limited to the non-negative real arguments required by this paper; it is not a general complex Mittag-Leffler library.

## Parameter profiles

- Aggregation scale: 301 logarithmic points from (10^{-3}) to (10^2), measured in clock characteristic-time units.
- Ordinary clock rate: one after nondimensionalisation.
- Response-to-clock rate ratios: (0.25,1,4).
- Fractional order pairs: ((1,1),(0.8,0.8),(0.6,1),(0.6,0.6)). The middle two equal-sum comparison cases are ((0.8,0.8)) and ((0.6,1.0)).
- Boundary baseline: two symmetric books, unit source amplitude/width/front slope, and coupling strength (2/\sqrt\pi), which gives total baseline response rate one.
- Conditional boundary perturbations: multiplicative factors (0.5,1,2), one input at a time.
- Discrete representation: four lattice spacings, five selector-resolution ratios, centred and half-cell-shifted selectors, and full/truncated finite domains.
- Calendar-time bridge: 801 linear aggregation points from 0 to 400 s, illustrative clock rate `0.1 s^-1`, response rate `0.025 s^-1`, and 301 inset lags from 0 to 200 s. These values assign readable units to the accepted ratio `kappa/lambda_12=0.25`; they are not a calibration.

These are restrained illustration and diagnostic profiles, not calibrated estimates.

## Finite-grid experiment

The active source is the decaying Gaussian. The continuum moment is exactly selector-width invariant for a centred symmetric domain because (yq(y)) is even and the hyperbolic-tangent contribution is odd. The discrete experiment therefore uses:

- a centred selector as the parity/invariance control;
- a half-cell selector displacement as the boundary-alignment error;
- a truncated symmetric domain as the finite-domain error;
- lattice refinement as the convergence variable.

The resulting moment ratio is propagated only through an effective response rate. It is labelled numerical representation sensitivity and is not treated as a new continuum mechanism.

## Numerical checks

- Non-finite or invalid domains, rates, times, orders, and kernel parameters raise clear errors.
- Scientific outputs are generated only after the diagnostic script passes.
- Fractional reference error must be below (2\times10^{-9}) at the recorded points.
- Analytic/numerical moment error and centred-grid refinement must satisfy configured tolerances.
- Every figure has long-form CSV data; each publication table has CSV and standalone LaTeX generated from the same values.
- PDF figure bytes are not expected to be identical across platforms; numerical CSV values and diagnostic statuses are the cross-platform check.

These numerical choices preserve the documented six-figure, two-table output set, sensitivity definitions, claim boundary, and v1-v2 overlay interface.
