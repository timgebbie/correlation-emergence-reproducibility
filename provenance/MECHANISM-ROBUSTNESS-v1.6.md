# Mechanism-decomposition robustness and Stage 6 closure — `v1.6.2`

## Purpose

This closing gate asks whether the accepted `v1.6.1` clock-versus-boundary
decomposition is driven by any one of the eight operational paths. It does not
rerun the solver, regenerate clocks or change the accepted estimator. It reads
the hash-frozen member and decomposition outputs, groups the two clock
replications within operational path, and then omits one operational-path
group at a time.

The analysis remains conditional on the declared finite ensemble. A stable
leave-one-path-out sign is evidence of path robustness inside this experiment;
it is not an empirical confidence statement or a general mechanism theorem.

## Design

For grouped contrast values `z_1,...,z_8`, the full mean is

```text
z_bar = (1/8) sum_i z_i
```

and omission `i` gives

```text
z_bar_(-i) = (1/7) sum_(j != i) z_j.
```

The envelope is the minimum and maximum of the eight omission means. The
jackknife standard error computed from those omission means is checked against
the accepted eight-group standard error at every clock, contrast and lag. The
three reporting bands form an exact partition of lags 1--600:

- short: lags 1--10, or calendar scales 0.005--0.05;
- medium: lags 11--100, or calendar scales 0.055--0.5; and
- long: lags 101--600, or calendar scales 0.505--3.0.

The deterministic robustness module has no solver, clock-construction,
observation or random-number dependency. Accepted `v1.6.1` inputs are protected
by exact SHA-256 values before and after the analysis.

## Results

All 22 closing checks pass. Memberwise, grouped and leave-one-path-out
factorial reconstructions are within `4.45e-16`, `3.34e-16` and `2.23e-16`,
respectively. Accepted grouped means are recovered exactly; jackknife and
accepted standard errors agree within `8.33e-17`.

The boundary main contrast is positive at every reported lag. Its long-band
mean is `0.214287`, and every omission mean lies between `0.138335` and
`0.310500`. The long-band total change also stays positive for every omission
under all three nonidentity clock scenarios; its smallest omission mean is
`0.130936`. For the independent stable clocks, the long-band interaction mean
is `-0.187882`, and all omission means remain negative, from `-0.282618` to
`-0.107172`.

These results support the Stage 6 claim that the positive long-scale boundary
contribution and total change do not depend on a single operational path in
the declared ensemble. They do not imply that all short-scale clock or
interaction signs are stable: the machine-readable band summaries retain
those sign-agreement fractions explicitly.

## Outputs

- `outputs/mechanism-robustness-leave-one-path-out-v1.6.csv`: 57,600
  pointwise omission rows;
- `outputs/mechanism-robustness-band-members-v1.6.csv`: 288 bandwise omission
  rows;
- `outputs/mechanism-robustness-bands-v1.6.csv`: 36 clock-term-band summaries;
- `diagnostics/mechanism-robustness-checks-v1.6.csv`: 22 closing checks; and
- Figure 15 as PDF and PNG.

Figure 15 displays the full grouped contrast and the leave-one-operational-
path-out envelope for all four terms under each nonidentity clock. It is a
robustness diagnostic for Figure 14, not a new fitted model.

## Stage boundary

The independently passed and accepted `v1.6.2` gate closes Stage 6. Stage 7
begins at `v1.7.0` with the corrected, separately named replacement target for
the legacy Figure 7. The simulation analogue of analytical Figure 6 follows
at `v1.7.1`, and their registered analytical/simulation overlay follows at
`v1.7.2`. Event semantics and impact remain Stage 8.
