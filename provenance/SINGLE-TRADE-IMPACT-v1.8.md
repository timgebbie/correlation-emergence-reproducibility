# Paired single-trade own and cross impact — `v1.8.1`

Status: provisional gate; external acceptance pending

Accepted parent: `v1.8.0` at commit
`adb8192f89f3ddaa0466464397bf8580f2fcf40c`

## Experiment

One labelled market order consumes opposing density from the reaction boundary
outwards immediately before operational step 301. The event quantity is 0.05,
all events must fill completely, and the execution price is only the registered
volume-weighted consumed-grid proxy. Each shocked path is paired with a control
having the same initial density and exactly the same supplied innovations.

Eight symmetry-controlled operational paths cover both event books and both
aggressor sides, giving 32 event scenarios. The full two-by-two response matrix
is measured at 12 lags from 0 to 200 seconds. The operational grid step is 0.5
seconds. Complete paths are then observed through two distinct independent
Poisson previous-refresh clocks, each with rate 0.1 per second. There is no
calendar interpolation and no nonuniform state update.

## Boundary architecture and relation to the paper

The production numerical coupling is

\[
v_j(x,u)=-\partial_x\varphi^{(j)}(x,u),\qquad
\ell_T^{(j,k)}(x,u)=-\kappa_{jk}z_{jk}(u)v_j(x,u).
\]

It excites the receiving book's current reaction-front translation mode. Under
the normalized adjoint projection this gives
\(\dot p_j=-\kappa_{jk}(p_j-p_k)\) directly, because the translation-mode
normalization occurs in both numerator and denominator and cancels.

Consequently the production numerics need no independently selected boundary
selector width, regularisation parameter or mesoscale thickness closure. This
does not mean that the numerical front is infinitely thin. Its finite,
grid-resolved profile remains part of the density state and is determined by
the source, diffusion, grid, boundary conditions and path history. The coupling
inherits that profile through the current derivative rather than replacing it
with an external smoothing kernel.

The accepted Angstmann--Gebbie paper instead introduces a bounded regularised
source to obtain an analytically tractable local and weak-moment closure. That
source and the translation-mode source are not pointwise identical. Their
relation is only at the projected front-displacement level, subject to the
paper's stated reduction assumptions. The paper's conditional reduced boundary
law is retained; the numerical architecture removes the unsupported inference
that a fixed regularised source amplitude automatically equals the boundary
response rate in the full recurrence.

This contrast must appear in the v2 supplementary material. The source-v1 paper
remains frozen, the accepted regularised implementation remains a historical
comparator, and the draft supplementary insert is
`source/source-v2/TRANSLATION-MODE-NUMERICAL-ARCHITECTURE-v1.8.tex`.

## Result

- operational own impact at the event state: `0.147074`;
- operational cross-impact at 20 seconds: `0.015197`;
- calendar own impact at 40 seconds: `0.029101`;
- long-lag operational own/cross ratio: `0.874416`; and
- domain-scaled buy/sell difference: `0.010374`.

The original cellwise buy/sell relative diagnostic reached `0.419570` only at
one-second calendar cross-impact, where the two absolute responses were about
`1.45e-4` and `0.84e-4`. That statistic divided by a near-zero local response.
The gate therefore uses the maximum absolute side difference normalized by the
peak own impact in each measurement domain, while retaining the cellwise value
as a non-gating diagnostic. The scientific tolerance remains 0.15.

All 44 generated checks pass. Figure 23 uses one common linear response scale.
The machine-readable evidence comprises 96 curve rows, 1,536 member rows, 32
event records, 16 clock records and the paired operational/calendar path
archive.

## Boundary

This is a controlled one-front model experiment, not an empirical impact
estimate or a complete matching engine. It does not implement a meta-order,
separate best bid and ask fronts, cancellations, mid-price autocorrelation or
trade-sign dependence. Acceptance advances the numeric sequence to `v1.8.2`,
scheduled meta-order own and cross-impact.
