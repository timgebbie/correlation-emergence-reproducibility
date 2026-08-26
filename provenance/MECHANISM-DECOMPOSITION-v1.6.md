# Paired clock and reaction-boundary decomposition — `v1.6.1`

## Purpose

Stage 5 held the coupled operational paths fixed and changed only their
calendar image. Stage 6 now crosses the boundary mechanism and the clock. This
separates the effect of the operational reaction boundary from the effect of
observing that path through two book-specific clocks.

The target is `DEC-EPP-01`. It extends the calendar-time Bauer comparison. It
does not alter the accepted Stage 5 Figure 13 or the released analytical
Figure 5.

## Factorial cells

The boundary factor has two levels:

1. `uncoupled_control`: the accepted matched-input Stage 4 control;
2. `regularized_coupling`: the accepted Angstmann--Gebbie reaction-boundary
   coupling.

The clock factor has four declared scenarios:

1. identity clocks;
2. independent Poisson-refresh clocks;
3. the 60% common-wait dependence diagnostic;
4. independent positive-stable clocks with distinct calendar exponents.

This gives eight cells. The two boundary levels use the same operational
innovations and path index. Each clock path is also reused across the two
boundary levels. Clock member `m` uses operational path `m mod 8`; hence each
of the eight operational paths has two clock replications.

Every cell uses the accepted calendar step `0.005`, common horizon `11.615`,
previous-completed-state inverse, and overlapping return lags 1 through 600.
No interpolation, extrapolation or final-state clamping is introduced.

## Contrasts

For one nonidentity clock let

- `Y00` be control under identity;
- `Y10` be regularised coupling under identity;
- `Y01` be control under the clock; and
- `Y11` be regularised coupling under the same clock.

At each aggregation scale the recorded terms are

```text
baseline       = Y00
boundary_main  = Y10 - Y00
clock_main     = Y01 - Y00
interaction    = Y11 - Y10 - Y01 + Y00
```

The reconstruction `Y00 + boundary_main + clock_main + interaction = Y11` is
an algebraic invariant and is tested for pooled curves and every member. The
interaction measures how the calendar-clock change differs between the two
boundary mechanisms. These are descriptive computational contrasts. They are
not empirical causal estimates.

## Uncertainty

The nonlinear correlation estimate is retained at pooled and member levels.
For uncertainty, the four-cell contrasts are first formed memberwise. The two
clock replications are then averaged within operational path. Sample standard
deviations and standard errors are calculated across the eight resulting path
groups. This avoids treating 16 clock images as 16 independent operational
simulations.

## Outputs

- `outputs/mechanism-factorial-design-v1.6.csv`: eight declared cells;
- `outputs/mechanism-factorial-curves-v1.6.csv`: 4,800 aggregate rows;
- `outputs/mechanism-factorial-members-v1.6.csv`: 76,800 member rows;
- `outputs/mechanism-decomposition-curves-v1.6.csv`: 1,800 contrast rows;
- `outputs/stage6-stability-register-v1.6.csv`: accepted-input and workspace
  stability records;
- `diagnostics/mechanism-entry-checks-v1.6.csv`: 22 entry checks; and
- Figure 14 as PDF and PNG.

Figure 14 displays the independent-Poisson slice. At the longest reported lag
`Delta t=3`, its pooled control/identity baseline is `-0.030376`, the boundary
main contrast is `0.512663`, the clock main contrast is `0.026734`, and the
interaction is `-0.011016`. These finite-sample values reconstruct the
coupled/Poisson correlation `0.498005`. The boundary contrast is dominant in
this declared simulation. That is a conditional numerical result, not a
general identification theorem.

## Gate boundary

Status: accepted `v1.6.1` entry gate. The independently passed and accepted
`v1.6.2` robustness gate closes Stage 6. The publication-figure comparison
follows in Stage 7; explicit limit/market-event and impact extensions remain
Stage 8.
