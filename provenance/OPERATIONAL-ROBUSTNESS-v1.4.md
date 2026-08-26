# Operational numerical and thickness robustness — `v1.4.2`

## Scope

This checkpoint tests the numerical choices introduced in `v1.4.0` and
`v1.4.1`. It does not change the operational recurrence, construct a clock,
subordinate a path or run a publication ensemble.

## Reaction-front geometry

At a selected reaction boundary, a seven-point cubic fit is evaluated in the
local coordinate `y=x-p`. It returns the slope `L` and curvature `C`. For the
diagnostic convention

```text
L_curv = 2*abs(L)/abs(C),
eta_disp = abs(C)*abs(xi)/(2*abs(L)) = abs(xi)/L_curv.
```

If `C=0`, the curvature length is infinite. A zero fitted slope is rejected.
A boundary too near the domain edge for the declared stencil has no curvature
diagnostic; the path records this as unavailable rather than fabricating an
asymmetric stencil. Rolling results now retain slope, curvature and curvature
length for both fronts.

This operational definition makes the local-linear validity condition in the
Angstmann--Gebbie appendix measurable. It does not claim that a finite one-front
width is an explicit bid--ask spread.

## Thickness scales

The target coupling remains

```text
epsilon = abs(z_ref)*w_ref,
w_epsilon(z) = epsilon/abs(z),
L_q = mu^(-1/2).
```

The evidence reports

```text
Delta x/w_ref,
w_ref/L_q,
L_q/L_curv,
w_epsilon(z)/L_curv,
eta_disp.
```

No universal number is substituted for the two `<<` relations in the paper.
For the deterministic scale example, `Delta x=0.05`, `w_ref=0.5`,
`abs(z_ref)=1` and `mu=0.1`, giving `Delta x/w_ref=0.1` and
`w_ref/L_q=0.158113883`. These are diagnostic reference values, not empirical
calibration. At zero spread the formal selector width is infinite, but the
spread-proportional coupling is inactive and its curvature ratio is not
applicable.

## Convergence evidence

The generated series contains:

- spatial refinements `Delta x = 0.2, 0.1, 0.05, 0.025`, for which both the
  off-grid reaction-boundary price and slope errors decrease against the finest
  reference;
- Dirichlet half-widths `5, 10, 20`, for which the off-centre stationary
  boundary error decreases;
- raw Sibuya history cutoffs `8, 16, 32, 64, 128`, for which the final
  fractional-density error decreases against the 128-term reference; and
- selector-moment refinements `Delta x = 0.4, 0.2, 0.1, 0.05, 0.025`, for
  which lattice error decreases and the finest finite-domain moment is within
  one percent of its continuum value.

The sequences demonstrate convergence for the declared deterministic cases.
They are not a general convergence proof. The frozen-front timescale condition,
large-shock validity and production-ensemble uncertainty remain to be tested in
the operational experiments at `v1.4.3` and the later response stages.

## Evidence

Run:

```bash
python scripts/14_run_operational_robustness_checks.py
python -m unittest tests.test_operational_robustness tests.test_figure_io -v
```

Fifteen generated checks and 21 series rows cover geometry, scale ratios,
spatial refinement, domain truncation, history truncation, displacement
linearity, zero-spread limiting behaviour and coupling-moment convergence.
Eight robustness tests and three atomic-publication tests cover these records
and the renderer-staging correction exposed by the complete route.

Stage: 4 — numerical and mathematical robustness (`v1.4.2`)

Science status: accepted after exact-archive verification

Acceptance status: 165-entry manifest, 15 generated checks and complete
181-test route passed from a fresh extraction of the accepted archive.

Next decision: run complete operational ensembles, recover the operational
Figure/shock targets and close Stage 4 at `v1.4.3`.
