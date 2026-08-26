# Timestamp-aware calendar Epps target — `v1.5.2`

## Target and naming

This gate completes `SUB-EPP-01`: the accepted coupled operational paths are
observed through explicit book-specific clocks and measured on a declared
calendar grid. The project originally called the frozen Bauer curve “Figure
5”; it is Figure 4 in arXiv:2408.03181v2. The new bundle output is Figure 13 so
that the released analytical Figure 5 remains unchanged.

## Stored operational input

`scripts/15_run_operational_ensemble.py` now retains the two Stage 4 boundary
ensembles in `outputs/operational-boundary-paths-v1.4.npz`. Its JSON companion
records the v1.4.3 configuration hash, archive hash and array hashes. The
archive contains:

```text
operational_times                 (2401,)
regularized_coupling_prices       (8,2401,2)
uncoupled_control_prices          (8,2401,2)
```

It contains no clock, calendar interpolation or random generator. The v1.5.2
target uses the regularised-coupling prices. The matched control is retained
for the paired Stage 6 mechanism experiments.

The Stage 4 increment calculated from the spatial scaling is
`0.0049999999999999645`; the v1.5.1 clock configuration records the intended
nominal value `0.005`. Their maximum accumulated node difference is about
`8.53e-14`, below the declared `1e-12` grid-agreement tolerance. State indices,
not approximate time interpolation, link the two layers.

## Calendar support and estimator

For every scenario, book and path, let `H_jm=T_jm(u_N)` be its realised
calendar support. The common analysis horizon is

```text
H = 0.005 * floor(min_{scenario,m,j} H_jm / 0.005) = 11.615.
```

Calendar query times are `t_q=0.005q` from zero through `H`. Since `H` lies
strictly below every book support, no query is extrapolated and no final state
is repeated beyond support. The accepted finite-grid inverse selects

```text
n_jm(t_q)=max{n:T_jm(u_n)<=t_q},
P_jm(t_q)=p_jm,n_jm(t_q).
```

At calendar lag `ell`, overlapping returns are

```text
R_jm(q;ell)=P_jm(t_{q+ell})-P_jm(t_q).
```

The pooled statistic is the uncentred realised correlation of all member
return windows. Individual member correlations are also retained. At every
lag the output records the total number of windows, the number with a nonzero
return in each book, and the number jointly nonzero. These counts describe
the actual asynchronous sample and replace the legacy horizon extension.

## Pairing and uncertainty

There are 16 clock paths and eight accepted operational paths. Clock member
`m` is paired with operational path `m mod 8`, giving two clock replications
per operational path. The 16 member correlations are not treated as 16
independent boundary paths. They are averaged within each operational-path
group; means, sample standard deviations and normal standard errors are then
computed over the eight grouped values. Pooled and grouped summaries remain
separate fields.

## Scenarios and analytical reference

Figure 13 reports:

1. the identity-clock reference;
2. independent equal-rate Poisson clocks;
3. the 60% common-wait dependence diagnostic;
4. independent stable clocks with `alpha_t=(0.8,0.65)`.

For the independent Poisson curve only, the dotted reference is

```text
rho_identity(Delta t) * F(400 Delta t),
F(x)=1-(1-exp(-x))/x.
```

The rate 400 is the declared pooled rate `200+200`. This is not fitted. It is
the leading-order separable overlap reference applied to the measured
identity-clock boundary curve. The coupled finite sample need not be ordered
below the identity curve at every lag. The paper explicitly qualifies the
overlap envelope and the clock/coupling product approximation. No exact joint
overlap curve is constructed for the two unequal stable exponents.

The lower Figure 13 panel subtracts the identity result pathwise at the curve
level. It measures how the fixed finite sample changes under each clock. It is
not yet the complete Stage 6 causal decomposition, which will also switch the
reaction-boundary response and clock mechanisms through matched controls.

## Evidence

`scripts/19_generate_calendar_epps.py` writes:

- 20 checks in `diagnostics/calendar-estimator-checks-v1.5.csv`;
- 2,400 aggregate curve rows;
- 38,400 member-lag rows;
- 64 member support and provenance rows;
- Figure 13 as PDF and PNG.

Twelve tests cover exact identity recovery, grouped uncertainty, support and
lag validation, mutation protection, archive integrity, output schemas,
qualified analytical-reference roles, figure publication and the absence of
RNG, interpolation and legacy/operational imports in the estimator module.

Stage: 5 — timestamp-aware calendar estimation and `SUB-EPP-01` (`v1.5.2`)

Status: accepted at `v1.5.2`; Stage 5 closed
