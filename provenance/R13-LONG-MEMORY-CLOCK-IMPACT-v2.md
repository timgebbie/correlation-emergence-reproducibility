# R13 long-memory clock and impact provenance

## Accepted parent and scope

R13 starts from the accepted local R12 commit
`cd4ff8abda45b4162c614f5e7627578aa71c46dc`. It does not alter the frozen
`source/source-v1/` paper, refit a parameter, replace the operational solver,
or modify the public `v2.0.0` tag or release.

The stage changes two declared inputs and adds one comparison:

1. Figure 13 order signs use exogenous heavy-tailed meta-order runs instead of
   the earlier finite Markov fixture.
2. The completed operational paths are observed through Poisson,
   Mittag--Leffler and exponentially tempered Mittag--Leffler renewal clocks.
3. Figure 14 applies those clocks to the already-established common-input
   single-trade and meta-order impact experiments.

## Clock law and numerical boundary

The untempered waiting law is defined by
`E[exp(-sW)] = 1 / (1 + (tau*s)^beta)`. The implementation uses
`W = tau * E**(1/beta) * S_beta`, with the Kanter representation for the
positive stable variate. At `beta=1` this reduces to an exponential wait.

Tempering is the exact exponential probability tilt with acceptance
probability `exp(-lambda_T * W)`. It is not a hard cutoff. Its Laplace
transform and finite mean are recorded in the computational supplement. The
R13 values are `beta=0.8`, `tau=10 s` and `lambda_T=0.0125 s^-1`.

All uniforms are caller-supplied and book-specific. A clock selects the last
refresh and then the last completed operational node. It performs no
interpolation, operational update, clipping or path feedback. A finite-horizon
path with no varying sampled increments remains in distributions and impact
means; its undefined ACF is marked unavailable rather than assigned zero.

## Impact-method audit

Reference repository:
<https://github.com/DerickDiana/InteractingLOBs.jl>

Audited commit: `098f180729f0b678109c53f86c514dfdc12ec708`

The repository-root `plot_price_impact.jl` is a stub. The substantive method is
`src/useful_functions.jl:calculate_price_impacts`, called from
`src/MakePlots.jl`. It injects signed orders, measures raw-price displacement
after a declared lag, and aggregates paths. The associated paper is Diana and
Gebbie, “Non-uniformly sampled simulated price impact of an order-book,”
arXiv:2310.06079 and <https://doi.org/10.1016/j.cam.2024.116202>.

R13 preserves the signed-response logic but does not port the Julia routine.
It retains the stronger local estimator established in Figures 9 and 10:
aggressor sign times shocked-minus-control log-mid displacement, with identical
initial state, operational innovations and realised observation clock in each
pair. No spline smoothing, log/power fit or empirical impact-law claim is made.

## Registered evidence

- `config/config-v2.1.0-r13.json`
- `diagnostics/r13-science-math-checks-v2.1.csv`
- `outputs/r13-observation-clock-summary-v2.1.csv`
- `outputs/figure-13-long-memory-clock-comparison-v2.1.npz`
- `outputs/clock-subordinated-impact-curves-v2.1.csv`
- `outputs/clock-subordinated-impact-v2.1.npz`
- `figures/figure-13-stylised-facts-recovery-v2.{png,pdf}`
- `figures/figure-14-clock-subordinated-impact-v2.{png,pdf}`

The diagnostic register verifies the two Laplace transforms, tempered mean,
tail reduction, exact previous-refresh map, long-memory input signature,
unchanged common-input controls, frozen source paper and absence of refitting.
