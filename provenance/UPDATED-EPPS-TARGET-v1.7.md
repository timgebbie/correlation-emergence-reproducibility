# New Figure 16 corrected Epps target — `v1.7.0`

Status: accepted at `v1.7.0` on 2026-08-14

## Role

Figure 7 remains the immutable legacy test and reference case. It retains the
Bauer nonuniform implementation, historical estimator and sparse-allocation
plotting convention. It is neither overwritten nor renumbered.

`v1.7.0` adds a new Figure 16 and target `UPD-EPP-01`. Figure 16 has the
eventual scientific role of replacing the legacy construction in the final
publication comparison, but it is a distinct output with a new number during
development.

## Construction

The upper panel uses the accepted corrected Stage 4 reaction-boundary paths on
the uniform operational grid. The lower panel uses the same class of accepted
paths after the Stage 5 independent book-specific Poisson clocks have been
applied by explicit previous-completed-state subordination. Both panels use
lags 1--600. Their numerical increments are both `0.005`, but the upper axis is
operational scale `Delta u` and the lower axis is calendar scale `Delta t`.
They remain separate mathematical objects.

The figure is assembled from exact-hash accepted outputs. It does not rerun
the solver, construct new clocks, interpolate paths or import the legacy
implementation. The two realised Poisson book clocks use distinct streams and
are not equal pathwise.

## Estimate and uncertainty

The main curve is the equal-weight mean of the eight operational-path
correlations. For the calendar panel, the two clock replications are first
averaged within operational path. The shaded region is the path-group mean
plus or minus `1.96` standard errors across those eight groups. It is a normal
finite-ensemble summary, not an empirical confidence claim.

The pooled realised correlation is retained as a separate dotted curve. It is
not used as the centre of the path-group band. This distinction matters in the
small declared ensemble. At scale `3`, the operational path-group mean is
`0.243136` with standard error `0.195043`, while the pooled estimate is
`0.510121`. After independent Poisson subordination the corresponding values
are `0.254260`, `0.192651` and `0.498005`.

No plateau normalisation is applied at this gate. Raw realised correlation is
required so that the scale and normalisation map for analytical Figure 6 can
be declared explicitly at `v1.7.1` and tested in the overlay at `v1.7.2`.

## Outputs

- `outputs/updated-figure-16-curves-v1.7.csv`: 1,200 operational/calendar
  panel-lag rows;
- `outputs/updated-figure-16-members-v1.7.csv`: 14,400 path and clock-member
  rows;
- `diagnostics/updated-figure-16-checks-v1.7.csv`: 26 entry checks; and
- `figures/figure-16-updated-epps-target-v1.pdf` and matching PNG.

## Limits and next gate

Figure 16 is a synthetic finite-ensemble result, not a calibration or
pointwise recovery of the legacy Julia path. It contains no price-path
autocorrelation or power-spectrum inset. Those path-derived diagnostics belong
to the simulation analogue of analytical Figure 6 at `v1.7.1`. The registered
analytical/simulation overlay remains `v1.7.2`.
